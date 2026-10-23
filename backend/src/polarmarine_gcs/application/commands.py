from __future__ import annotations

import asyncio
import math
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta
from typing import Any

from polarmarine_gcs.application.events import EventService
from polarmarine_gcs.application.links import LinkCoordinator
from polarmarine_gcs.application.ports.drivers import DriverGateway
from polarmarine_gcs.application.ports.repositories import Repository
from polarmarine_gcs.application.registry import RegistryService
from polarmarine_gcs.domain.commands import (
    COMMAND_CAPABILITIES,
    TERMINAL_COMMAND_STATUSES,
    Command,
    CommandStatus,
    CommandType,
)
from polarmarine_gcs.domain.common import NotFoundError, ValidationError, new_id, utc_now
from polarmarine_gcs.domain.events import AlarmSeverity, SystemEvent


class CommandService:
    def __init__(
        self,
        repository: Repository,
        registry: RegistryService,
        links: LinkCoordinator,
        drivers: DriverGateway,
        events: EventService,
        *,
        acknowledgement_timeout_seconds: float = 5.0,
        state_confirmation_timeout_seconds: float = 5.0,
    ) -> None:
        self.repository = repository
        self.registry = registry
        self.links = links
        self.drivers = drivers
        self.events = events
        self.acknowledgement_timeout_seconds = acknowledgement_timeout_seconds
        self.state_confirmation_timeout_seconds = state_confirmation_timeout_seconds
        self._timeout_tasks: dict[str, asyncio.Task[None]] = {}
        self._status_listeners: list[Callable[[Command, dict[str, Any]], Awaitable[None]]] = []
        self._device_sequences: dict[str, int] = {}
        self._execution_deadlines: dict[str, datetime] = {}
        self._awaiting_state_confirmation: set[str] = set()

    def add_status_listener(
        self, listener: Callable[[Command, dict[str, Any]], Awaitable[None]]
    ) -> None:
        self._status_listeners.append(listener)

    async def stop(self) -> None:
        for task in self._timeout_tasks.values():
            task.cancel()
        if self._timeout_tasks:
            await asyncio.gather(*self._timeout_tasks.values(), return_exceptions=True)
        self._timeout_tasks.clear()
        self._execution_deadlines.clear()
        self._awaiting_state_confirmation.clear()

    async def recover_interrupted_commands(self) -> None:
        for command in self.repository.list_commands(limit=100_000):
            if command.status in TERMINAL_COMMAND_STATUSES:
                continue
            command.expires_at = None
            await self._transition(
                command,
                CommandStatus.STATE_UNCONFIRMED,
                reason_code="CORE_RESTARTED_DURING_COMMAND",
                reason_message="The core restarted before the device outcome was confirmed",
            )

    def has_inflight_commands(self, device_id: str) -> bool:
        return any(
            item.status not in TERMINAL_COMMAND_STATUSES
            for item in self.repository.list_commands(device_id=device_id, limit=100)
        )

    async def submit(
        self,
        *,
        device_id: str,
        command_type: CommandType,
        payload: dict[str, Any],
        idempotency_key: str | None = None,
        execution_timeout_seconds: float | None = None,
    ) -> Command:
        device = self.registry.require_device(device_id)
        if not device.enabled:
            raise ValidationError("Commands cannot be sent to a disabled device")
        template = self.registry.require_template(device.template_id)
        capability = _required_capability(command_type, payload)
        if capability not in template.capabilities:
            raise ValidationError(
                f"Device template {template.id} does not declare capability {capability}",
                details={"capability": capability},
            )
        _validate_payload(command_type, payload)
        if execution_timeout_seconds is not None and (
            not math.isfinite(execution_timeout_seconds) or execution_timeout_seconds <= 0
        ):
            raise ValidationError("Execution timeout must be a finite positive number")
        if idempotency_key:
            existing = self.repository.get_command_by_idempotency_key(device_id, idempotency_key)
            if existing:
                return existing
        command = Command(
            id=new_id(),
            device_id=device_id,
            command_type=command_type,
            payload=payload,
            idempotency_key=idempotency_key,
            expires_at=utc_now() + timedelta(seconds=self.acknowledgement_timeout_seconds),
        )
        if execution_timeout_seconds is not None:
            self._execution_deadlines[command.id] = utc_now() + timedelta(
                seconds=execution_timeout_seconds
            )
        self.repository.save_command(command)
        await self._emit(command)
        broadcast = command_type is CommandType.EMERGENCY_STOP
        routes = self.links.routing_links(device_id, capability, broadcast=broadcast)
        if not routes:
            return await self._transition(
                command,
                CommandStatus.REJECTED,
                reason_code="NO_HEALTHY_ROUTE",
                reason_message="No healthy capability-matching link is available",
            )
        command.routed_link_ids = tuple(item.id for item in routes)
        command.link_acknowledgements = {item.id: "pending" for item in routes}
        await self._transition(command, CommandStatus.DISPATCHED)
        request = {
            "schemaVersion": "1.0",
            "messageId": new_id(),
            "deviceId": device_id,
            "sequence": self._next_sequence(device_id),
            "type": "command.request",
            "correlationId": command.id,
            "sentAt": utc_now().isoformat(),
            "payload": {
                "commandId": command.id,
                "commandType": command.command_type.value,
                "arguments": command.payload,
            },
        }
        for profile in routes:
            try:
                await self.drivers.send_command(profile, request)
            except Exception as exc:
                command = self.repository.get_command(command.id) or command
                command.link_acknowledgements[profile.id] = "dispatch_failed"
                command.reason_code = "DRIVER_DISPATCH_FAILED"
                command.reason_message = str(exc)
                command.revision += 1
                command.updated_at = utc_now()
                self.repository.save_command(command)
                await self._emit(command)
            else:
                command = self.repository.get_command(command.id) or command
        if all(value == "dispatch_failed" for value in command.link_acknowledgements.values()):
            return await self._transition(
                command,
                CommandStatus.REJECTED,
                reason_code="ALL_DISPATCHES_FAILED",
                reason_message="The command could not be delivered to any selected link",
            )
        if command.status is CommandStatus.DISPATCHED:
            self._schedule_timeout(command.id, self.acknowledgement_timeout_seconds)
        return command

    def _next_sequence(self, device_id: str) -> int:
        sequence = (self._device_sequences.get(device_id, -1) + 1) & 0xFFFFFFFF
        self._device_sequences[device_id] = sequence
        return sequence

    async def handle_driver_event(self, message: dict[str, Any]) -> None:
        payload = message.get("payload")
        if not isinstance(payload, dict):
            return
        if message.get("type") == "command.link_lost":
            await self._handle_link_lost(str(payload.get("linkId", "")))
            return
        command_id = payload.get("commandId")
        link_id = payload.get("linkId")
        if not isinstance(command_id, str) or not isinstance(link_id, str):
            return
        command = self.repository.get_command(command_id)
        if command is None:
            return
        if link_id not in command.routed_link_ids:
            await self.events.emit(
                SystemEvent(
                    type="command.unrouted_acknowledgement_ignored",
                    aggregate_type="command",
                    aggregate_id=command.id,
                    aggregate_revision=command.revision,
                    payload={"linkId": link_id},
                )
            )
            return
        if command.status in TERMINAL_COMMAND_STATUSES:
            late_status = str(payload.get("status", "")) or "invalid"
            command.link_acknowledgements[link_id] = late_status
            command.revision += 1
            command.updated_at = utc_now()
            self.repository.save_command(command)
            await self._emit(command)
            await self.events.emit(
                SystemEvent(
                    type="command.late_acknowledgement",
                    aggregate_type="command",
                    aggregate_id=command.id,
                    aggregate_revision=command.revision,
                    payload={"linkId": link_id, "status": late_status},
                )
            )
            return
        status = str(payload.get("status", ""))
        command.link_acknowledgements[link_id] = status or "invalid"
        progress = payload.get("progress")
        if isinstance(progress, (int, float)) and not isinstance(progress, bool):
            command.progress = max(0.0, min(1.0, float(progress)))
        if status == "accepted":
            if command.id in self._awaiting_state_confirmation:
                await self._persist_progress(command)
                return
            self._set_execution_expiry(command)
            if command.status in {CommandStatus.QUEUED, CommandStatus.DISPATCHED}:
                await self._transition(command, CommandStatus.ACCEPTED)
            else:
                await self._persist_progress(command)
            self._schedule_until_expiry(command)
        elif status == "in_progress":
            if command.id in self._awaiting_state_confirmation:
                await self._persist_progress(command)
                return
            self._set_execution_expiry(command)
            await self._transition(command, CommandStatus.IN_PROGRESS)
            self._schedule_until_expiry(command)
        elif status == "rejected":
            if command.command_type is not CommandType.EMERGENCY_STOP or all(
                value in {"rejected", "dispatch_failed"}
                for value in command.link_acknowledgements.values()
            ):
                await self._transition(
                    command,
                    CommandStatus.REJECTED,
                    reason_code=str(payload.get("reasonCode") or "DEVICE_REJECTED"),
                    reason_message=str(
                        payload.get("reasonMessage") or "Device rejected the command"
                    ),
                    event_payload=payload,
                )
            else:
                await self._persist_progress(command)
        elif status == "completed":
            if command.requires_state_confirmation:
                self._awaiting_state_confirmation.add(command.id)
                command.expires_at = utc_now() + timedelta(
                    seconds=self.state_confirmation_timeout_seconds
                )
                await self._transition(command, CommandStatus.IN_PROGRESS)
                self._schedule_timeout(command.id, self.state_confirmation_timeout_seconds)
            else:
                await self._transition(command, CommandStatus.COMPLETED)
        elif status == "state_confirmed" or payload.get("stateConfirmed") is True:
            await self._transition(command, CommandStatus.COMPLETED, event_payload=payload)
        else:
            await self._persist_progress(command)

    def get(self, command_id: str) -> Command:
        command = self.repository.get_command(command_id)
        if command is None:
            raise NotFoundError(f"Command {command_id} does not exist")
        return command

    async def cancel(self, command_id: str) -> Command:
        command = self.get(command_id)
        if command.status in TERMINAL_COMMAND_STATUSES:
            return command
        return await self._transition(command, CommandStatus.CANCELLED)

    async def _handle_link_lost(self, link_id: str) -> None:
        for command in self.repository.list_commands(limit=1_000):
            if (
                command.status in TERMINAL_COMMAND_STATUSES
                or link_id not in command.routed_link_ids
            ):
                continue
            command.link_acknowledgements[link_id] = "link_lost"
            other_possible = any(
                value not in {"link_lost", "dispatch_failed", "rejected"}
                for candidate, value in command.link_acknowledgements.items()
                if candidate != link_id
            )
            if command.command_type is CommandType.EMERGENCY_STOP and other_possible:
                await self._persist_progress(command)
                continue
            await self._transition(
                command,
                CommandStatus.STATE_UNCONFIRMED,
                reason_code="LINK_LOST_DURING_COMMAND",
                reason_message="Command outcome is uncertain and was not automatically retried",
            )

    async def _persist_progress(self, command: Command) -> None:
        command.revision += 1
        command.updated_at = utc_now()
        self.repository.save_command(command)
        await self._emit(command)

    async def _transition(
        self,
        command: Command,
        status: CommandStatus,
        *,
        reason_code: str | None = None,
        reason_message: str | None = None,
        event_payload: dict[str, Any] | None = None,
    ) -> Command:
        if command.status in TERMINAL_COMMAND_STATUSES:
            return command
        command.status = status
        result = (event_payload or {}).get("result")
        if isinstance(result, dict):
            command.result = result
        command.reason_code = reason_code or command.reason_code
        command.reason_message = reason_message or command.reason_message
        command.revision += 1
        command.updated_at = utc_now()
        self.repository.save_command(command)
        await self._emit(command)
        for listener in self._status_listeners:
            await listener(command, event_payload or {})
        if status in TERMINAL_COMMAND_STATUSES:
            self._execution_deadlines.pop(command.id, None)
            self._awaiting_state_confirmation.discard(command.id)
            task = self._timeout_tasks.pop(command.id, None)
            if task and task is not asyncio.current_task():
                task.cancel()
            if status in {CommandStatus.STATE_UNCONFIRMED, CommandStatus.TIMED_OUT}:
                await self.events.raise_alarm(
                    code="COMMAND_OUTCOME_UNCONFIRMED",
                    severity=AlarmSeverity.CRITICAL,
                    message=f"Command {command.id} ended as {status.value}",
                    device_id=command.device_id,
                )
        return command

    async def _emit(self, command: Command) -> None:
        await self.events.emit(
            SystemEvent(
                type="command.changed",
                aggregate_type="command",
                aggregate_id=command.id,
                aggregate_revision=command.revision,
                payload=command_payload(command),
            )
        )

    def _schedule_timeout(self, command_id: str, delay: float) -> None:
        current = self._timeout_tasks.pop(command_id, None)
        if current:
            current.cancel()
        self._timeout_tasks[command_id] = asyncio.create_task(
            self._expire(command_id, delay),
            name=f"command-timeout-{command_id}",
        )

    async def _expire(self, command_id: str, delay: float) -> None:
        current_task = asyncio.current_task()
        try:
            await asyncio.sleep(delay)
            command = self.repository.get_command(command_id)
            if command is None or command.status in TERMINAL_COMMAND_STATUSES:
                return
            if command.status in {CommandStatus.ACCEPTED, CommandStatus.IN_PROGRESS}:
                await self._transition(
                    command,
                    CommandStatus.STATE_UNCONFIRMED,
                    reason_code="STATE_CONFIRMATION_TIMEOUT",
                    reason_message="Device state did not confirm the command outcome",
                )
            else:
                await self._transition(
                    command,
                    CommandStatus.TIMED_OUT,
                    reason_code="ACK_TIMEOUT",
                    reason_message="No device acknowledgement was received",
                )
        finally:
            if self._timeout_tasks.get(command_id) is current_task:
                self._timeout_tasks.pop(command_id, None)

    def _set_execution_expiry(self, command: Command) -> None:
        deadline = self._execution_deadlines.get(command.id)
        command.expires_at = deadline or (
            utc_now() + timedelta(seconds=self.state_confirmation_timeout_seconds)
        )

    def _schedule_until_expiry(self, command: Command) -> None:
        expires_at = command.expires_at or utc_now()
        delay = max(0.0, (expires_at - utc_now()).total_seconds())
        self._schedule_timeout(command.id, delay)


def command_payload(command: Command) -> dict[str, Any]:
    return {
        "id": command.id,
        "deviceId": command.device_id,
        "commandType": command.command_type.value,
        "payload": command.payload,
        "status": command.status.value,
        "progress": command.progress,
        "result": command.result,
        "routedLinkIds": list(command.routed_link_ids),
        "linkAcknowledgements": command.link_acknowledgements,
        "idempotencyKey": command.idempotency_key,
        "reasonCode": command.reason_code,
        "reasonMessage": command.reason_message,
        "requiresStateConfirmation": command.requires_state_confirmation,
        "createdAt": command.created_at.isoformat(),
        "updatedAt": command.updated_at.isoformat(),
        "expiresAt": command.expires_at.isoformat() if command.expires_at else None,
        "revision": command.revision,
    }


def _required_capability(command_type: CommandType, payload: dict[str, Any]) -> str:
    if command_type is CommandType.CUSTOM_ACTION:
        capability = payload.get("capability")
        if not isinstance(capability, str) or not capability:
            raise ValidationError("A custom action must name its required capability")
        return capability
    return COMMAND_CAPABILITIES[command_type]


def _validate_payload(command_type: CommandType, payload: dict[str, Any]) -> None:
    if command_type is CommandType.MANUAL_CONTROL:
        if payload.get("direction") not in {"forward", "backward", "left", "right", "stop"}:
            raise ValidationError("Invalid manual control direction")
        speed = payload.get("speed", 0.0)
        if (
            isinstance(speed, bool)
            or not isinstance(speed, (int, float))
            or not math.isfinite(speed)
            or speed < 0
        ):
            raise ValidationError("Manual speed must be a finite non-negative number")
    elif command_type is CommandType.SET_MODE and not isinstance(payload.get("mode"), str):
        raise ValidationError("Mode command requires a stable mode code")
    elif command_type is CommandType.SET_ARMED and not isinstance(payload.get("armed"), bool):
        raise ValidationError("Arm command requires a boolean armed value")
    elif command_type is CommandType.WRITE_PARAMETERS and not isinstance(
        payload.get("values"), dict
    ):
        raise ValidationError("Parameter command requires a values object")

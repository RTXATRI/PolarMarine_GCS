from __future__ import annotations

import math
from typing import Any

from polarmarine_gcs.application.commands import CommandService
from polarmarine_gcs.application.events import EventService
from polarmarine_gcs.application.ports.repositories import Repository
from polarmarine_gcs.application.registry import RegistryService
from polarmarine_gcs.domain.commands import (
    TERMINAL_COMMAND_STATUSES,
    Command,
    CommandStatus,
    CommandType,
)
from polarmarine_gcs.domain.common import ValidationError
from polarmarine_gcs.domain.devices import ParameterDefinition, ParameterValueType
from polarmarine_gcs.domain.events import AlarmSeverity, SystemEvent


class ParameterService:
    def __init__(
        self,
        repository: Repository,
        registry: RegistryService,
        commands: CommandService,
        events: EventService,
    ) -> None:
        self.repository = repository
        self.registry = registry
        self.commands = commands
        self.events = events
        commands.add_status_listener(self._on_command_status)

    def read(self, device_id: str) -> list[dict[str, Any]]:
        device = self.registry.require_device(device_id)
        template = self.registry.require_template(device.template_id)
        saved = self.repository.get_parameter_values(device_id)
        return [
            {
                "definition": definition,
                "value": saved.get(definition.key, definition.default_value),
                "source": "device_confirmed" if definition.key in saved else "template_default",
            }
            for definition in template.parameters
        ]

    async def refresh(self, device_id: str) -> Command:
        device = self.registry.require_device(device_id)
        template = self.registry.require_template(device.template_id)
        return await self.commands.submit(
            device_id=device_id,
            command_type=CommandType.READ_PARAMETERS,
            payload={
                "requestedKeys": [item.key for item in template.parameters],
                "defaults": {item.key: item.default_value for item in template.parameters},
            },
        )

    async def write(self, device_id: str, values: dict[str, Any]) -> Command:
        device = self.registry.require_device(device_id)
        template = self.registry.require_template(device.template_id)
        definitions = {item.key: item for item in template.parameters}
        unknown = sorted(set(values).difference(definitions))
        if unknown:
            raise ValidationError("Unknown parameters", details={"keys": unknown})
        for key, value in values.items():
            _validate_value(definitions[key], value)
        confirmed = self.repository.get_parameter_values(device_id)
        effective = {
            item.key: confirmed.get(item.key, item.default_value) for item in template.parameters
        }
        changes = {key: value for key, value in values.items() if effective.get(key) != value}
        if not changes:
            raise ValidationError("No parameter values differ from the current snapshot")
        return await self.commands.submit(
            device_id=device_id,
            command_type=CommandType.WRITE_PARAMETERS,
            payload={
                "values": changes,
                "parameterTransaction": {
                    "kind": "write",
                    "previousConfirmedValues": {
                        key: confirmed[key] for key in changes if key in confirmed
                    },
                },
            },
        )

    async def _on_command_status(self, command: Command, payload: dict[str, Any]) -> None:
        if command.command_type is CommandType.READ_PARAMETERS:
            if command.status is CommandStatus.COMPLETED:
                await self._store_read_result(command)
            return
        if (
            command.command_type is not CommandType.WRITE_PARAMETERS
            or command.status not in TERMINAL_COMMAND_STATUSES
        ):
            return
        transaction = command.payload.get("parameterTransaction")
        kind = transaction.get("kind") if isinstance(transaction, dict) else "write"
        if kind == "rollback":
            await self._finish_rollback(command)
            return
        await self._finish_write(command)

    async def _store_read_result(self, command: Command) -> None:
        raw_values = command.result.get("values")
        values = raw_values if isinstance(raw_values, dict) else {}
        valid, invalid = self._validate_confirmed(command.device_id, values)
        if valid:
            existing = self.repository.get_parameter_values(command.device_id)
            existing.update(valid)
            self.repository.set_parameter_values(command.device_id, existing)
        await self.events.emit(
            SystemEvent(
                type="parameters.read_confirmed",
                aggregate_type="device_parameters",
                aggregate_id=command.device_id,
                aggregate_revision=command.revision,
                payload={
                    "deviceId": command.device_id,
                    "values": valid,
                    "invalidKeys": invalid,
                    "commandId": command.id,
                },
            )
        )

    async def _finish_write(self, command: Command) -> None:
        requested = command.payload.get("values")
        requested = requested if isinstance(requested, dict) else {}
        applied, failed = _parameter_outcomes(command, requested)
        if command.status is CommandStatus.COMPLETED and not failed:
            valid, invalid = self._validate_confirmed(command.device_id, applied)
            if invalid:
                failed.extend(invalid)
            else:
                await self._store_confirmed(command, valid, event_type="parameters.confirmed")
                return

        await self.events.emit(
            SystemEvent(
                type="parameters.write_failed",
                aggregate_type="device_parameters",
                aggregate_id=command.device_id,
                aggregate_revision=command.revision,
                payload={
                    "deviceId": command.device_id,
                    "commandId": command.id,
                    "commandStatus": command.status.value,
                    "appliedValues": applied,
                    "failedKeys": sorted(set(failed)),
                },
            )
        )
        if not applied:
            return
        transaction = command.payload.get("parameterTransaction")
        previous: dict[str, Any] = {}
        if isinstance(transaction, dict):
            raw_previous = transaction.get("previousConfirmedValues")
            if isinstance(raw_previous, dict):
                previous = {str(key): value for key, value in raw_previous.items()}
        rollback_values = {key: previous[key] for key in applied if key in previous}
        missing = sorted(set(applied).difference(rollback_values))
        if missing:
            await self.events.raise_alarm(
                code="PARAMETER_ROLLBACK_UNAVAILABLE",
                severity=AlarmSeverity.CRITICAL,
                message=(
                    f"Cannot safely roll back parameters without confirmed baselines: {missing}"
                ),
                device_id=command.device_id,
            )
            return
        await self.commands.submit(
            device_id=command.device_id,
            command_type=CommandType.WRITE_PARAMETERS,
            payload={
                "values": rollback_values,
                "parameterTransaction": {
                    "kind": "rollback",
                    "originalCommandId": command.id,
                },
            },
            idempotency_key=f"parameter-rollback:{command.id}",
        )

    async def _finish_rollback(self, command: Command) -> None:
        if command.status is not CommandStatus.COMPLETED:
            await self.events.raise_alarm(
                code="PARAMETER_ROLLBACK_FAILED",
                severity=AlarmSeverity.CRITICAL,
                message=f"Parameter rollback command {command.id} was not confirmed",
                device_id=command.device_id,
            )
            return
        values = command.payload.get("values")
        values = values if isinstance(values, dict) else {}
        valid, invalid = self._validate_confirmed(command.device_id, values)
        if invalid:
            await self.events.raise_alarm(
                code="PARAMETER_ROLLBACK_INVALID",
                severity=AlarmSeverity.CRITICAL,
                message=f"Parameter rollback returned invalid values: {invalid}",
                device_id=command.device_id,
            )
            return
        await self._store_confirmed(command, valid, event_type="parameters.rollback_confirmed")

    async def _store_confirmed(
        self, command: Command, confirmed: dict[str, Any], *, event_type: str
    ) -> None:
        existing = self.repository.get_parameter_values(command.device_id)
        existing.update(confirmed)
        self.repository.set_parameter_values(command.device_id, existing)
        await self.events.emit(
            SystemEvent(
                type=event_type,
                aggregate_type="device_parameters",
                aggregate_id=command.device_id,
                aggregate_revision=command.revision,
                payload={
                    "deviceId": command.device_id,
                    "values": confirmed,
                    "commandId": command.id,
                },
            )
        )

    def _validate_confirmed(
        self, device_id: str, values: dict[str, Any]
    ) -> tuple[dict[str, Any], list[str]]:
        device = self.registry.require_device(device_id)
        definitions = {
            item.key: item for item in self.registry.require_template(device.template_id).parameters
        }
        valid: dict[str, Any] = {}
        invalid: list[str] = []
        for key, value in values.items():
            definition = definitions.get(key)
            if definition is None:
                invalid.append(key)
                continue
            try:
                _validate_value(definition, value, allow_read_only=True)
            except ValidationError:
                invalid.append(key)
            else:
                valid[key] = value
        return valid, invalid


def parameter_definition_payload(definition: ParameterDefinition) -> dict[str, Any]:
    return {
        "key": definition.key,
        "displayName": definition.display_name,
        "valueType": definition.value_type.value,
        "defaultValue": definition.default_value,
        "unit": definition.unit,
        "minimum": definition.minimum,
        "maximum": definition.maximum,
        "step": definition.step,
        "description": definition.description,
        "enumValues": list(definition.enum_values),
        "readOnly": definition.read_only,
    }


def _validate_value(
    definition: ParameterDefinition, value: Any, *, allow_read_only: bool = False
) -> None:
    if definition.read_only and not allow_read_only:
        raise ValidationError(f"Parameter {definition.key} is read-only")
    if definition.value_type is ParameterValueType.BOOLEAN:
        if not isinstance(value, bool):
            raise ValidationError(f"Parameter {definition.key} must be boolean")
        return
    if definition.value_type in {ParameterValueType.NUMBER, ParameterValueType.INTEGER}:
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
        ):
            raise ValidationError(f"Parameter {definition.key} must be numeric")
        if definition.value_type is ParameterValueType.INTEGER and not float(value).is_integer():
            raise ValidationError(f"Parameter {definition.key} must be an integer")
        if definition.minimum is not None and value < definition.minimum:
            raise ValidationError(f"Parameter {definition.key} is below its minimum")
        if definition.maximum is not None and value > definition.maximum:
            raise ValidationError(f"Parameter {definition.key} exceeds its maximum")
        return
    if definition.value_type is ParameterValueType.ENUM:
        if not isinstance(value, str) or value not in definition.enum_values:
            raise ValidationError(f"Parameter {definition.key} has an invalid enum value")
        return
    if not isinstance(value, str):
        raise ValidationError(f"Parameter {definition.key} must be a string")


def _parameter_outcomes(
    command: Command, requested: dict[str, Any]
) -> tuple[dict[str, Any], list[str]]:
    raw_results = command.result.get("parameterResults")
    if isinstance(raw_results, dict):
        applied: dict[str, Any] = {}
        failed: list[str] = []
        for key, requested_value in requested.items():
            outcome = raw_results.get(key)
            if not isinstance(outcome, dict) or outcome.get("status") not in {
                "applied",
                "completed",
                "confirmed",
            }:
                failed.append(key)
                continue
            applied[key] = outcome.get("value", requested_value)
        return applied, failed
    raw_values = command.result.get("values")
    if isinstance(raw_values, dict):
        applied = {key: raw_values[key] for key in requested if key in raw_values}
        return applied, sorted(set(requested).difference(applied))
    if command.status is CommandStatus.COMPLETED:
        return dict(requested), []
    return {}, sorted(requested)

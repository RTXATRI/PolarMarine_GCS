from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from polarmarine_gcs.application.events import EventService
from polarmarine_gcs.application.ports.drivers import DriverGateway
from polarmarine_gcs.application.ports.repositories import Repository
from polarmarine_gcs.application.registry import RegistryService
from polarmarine_gcs.domain.common import ConflictError, utc_now
from polarmarine_gcs.domain.events import AlarmSeverity, SystemEvent
from polarmarine_gcs.domain.links import (
    DeviceOperationalState,
    LinkProfile,
    LinkSession,
    LinkSessionState,
    OperationalStatus,
)

RuntimeEventHandler = Callable[[dict[str, Any]], Awaitable[None]]


class LinkCoordinator:
    def __init__(
        self,
        repository: Repository,
        registry: RegistryService,
        events: EventService,
        drivers: DriverGateway,
        *,
        heartbeat_interval_seconds: float = 1.0,
        missed_heartbeats: int = 3,
        failback_stable_seconds: float = 10.0,
        failback_debounce_seconds: float = 30.0,
        max_online_devices: int = 20,
    ) -> None:
        self.repository = repository
        self.registry = registry
        self.events = events
        self.drivers = drivers
        self.heartbeat_timeout = heartbeat_interval_seconds * missed_heartbeats
        self.failback_stable_seconds = failback_stable_seconds
        self.failback_debounce_seconds = failback_debounce_seconds
        self.max_online_devices = max_online_devices
        self.sessions: dict[str, LinkSession] = {}
        self._active_links: dict[str, str] = {}
        self._last_failovers: dict[str, Any] = {}
        self._operational_revisions: dict[str, int] = {}
        self._state_changed_at: dict[str, Any] = {}
        self._recovery_attempts: dict[str, int] = {}
        self._recovery_tasks: dict[str, asyncio.Task[None]] = {}
        self._monitor_task: asyncio.Task[None] | None = None
        self._lock = asyncio.Lock()
        self._telemetry_handler: RuntimeEventHandler | None = None
        self._command_handler: RuntimeEventHandler | None = None
        self._raw_handler: RuntimeEventHandler | None = None
        self._has_inflight_commands: Callable[[str], bool] = lambda _device_id: False
        self._stopping = False
        drivers.set_event_handler(self.handle_driver_event)

    def set_runtime_handlers(
        self,
        *,
        telemetry: RuntimeEventHandler,
        command: RuntimeEventHandler,
        has_inflight_commands: Callable[[str], bool],
        raw: RuntimeEventHandler | None = None,
    ) -> None:
        self._telemetry_handler = telemetry
        self._command_handler = command
        self._has_inflight_commands = has_inflight_commands
        self._raw_handler = raw

    async def start(self) -> None:
        self._stopping = False
        await self.drivers.start()
        if self._monitor_task is None:
            self._monitor_task = asyncio.create_task(self._monitor(), name="link-health-monitor")

    async def stop(self) -> None:
        self._stopping = True
        if self._monitor_task is not None:
            self._monitor_task.cancel()
            await asyncio.gather(self._monitor_task, return_exceptions=True)
            self._monitor_task = None
        recovery_tasks = list(self._recovery_tasks.values())
        self._recovery_tasks.clear()
        for task in recovery_tasks:
            task.cancel()
        if recovery_tasks:
            await asyncio.gather(*recovery_tasks, return_exceptions=True)
        profiles = {item.id: item for item in self.repository.list_links()}
        for link_id, session in list(self.sessions.items()):
            profile = profiles.get(link_id)
            if profile and session.state is not LinkSessionState.STOPPED:
                await self.drivers.stop_link(profile)
        self.sessions.clear()
        self._active_links.clear()
        self._state_changed_at.clear()
        self._recovery_attempts.clear()
        await self.drivers.stop()

    async def connect(self, device_id: str, link_id: str) -> LinkSession:
        profile = self.registry.require_link(link_id, device_id=device_id)
        device = self.registry.require_device(device_id)
        if not device.enabled or not profile.enabled:
            raise ConflictError("Disabled devices or link profiles cannot be connected")
        online_devices = {
            item.device_id
            for item in self.sessions.values()
            if item.state not in {LinkSessionState.STOPPED, LinkSessionState.FAILED}
        }
        if device_id not in online_devices and len(online_devices) >= self.max_online_devices:
            raise ConflictError(f"At most {self.max_online_devices} devices may be online")
        template = self.registry.require_template(device.template_id)
        self._cancel_recovery(link_id, reset_attempts=True)
        async with self._lock:
            existing = self.sessions.get(link_id)
            if existing and existing.state not in {
                LinkSessionState.STOPPED,
                LinkSessionState.FAILED,
            }:
                return existing
            session = LinkSession(
                link_id=link_id,
                device_id=device_id,
                driver=profile.driver,
                state=LinkSessionState.STARTING,
                started_at=utc_now(),
                revision=(existing.revision + 1) if existing else 1,
            )
            self.sessions[link_id] = session
            self._state_changed_at[link_id] = utc_now()
        await self._emit_session(session)
        try:
            await self.drivers.start_link(
                profile,
                expected_device_id=device_id,
                requested_capabilities=template.capabilities,
            )
        except Exception as exc:
            await self._transition(
                session,
                LinkSessionState.RECOVERING,
                error_code="DRIVER_START_FAILED",
                error_message=str(exc),
            )
            self._schedule_recovery(link_id)
        return session

    async def disconnect(self, device_id: str, link_id: str) -> LinkSession:
        profile = self.registry.require_link(link_id, device_id=device_id)
        session = self.sessions.get(link_id) or LinkSession(
            link_id=link_id,
            device_id=device_id,
            driver=profile.driver,
        )
        self._cancel_recovery(link_id, reset_attempts=True)
        await self.drivers.stop_link(profile)
        await self._transition(session, LinkSessionState.STOPPED)
        await self._recompute_route(device_id)
        return session

    async def handle_driver_event(self, message: dict[str, Any]) -> None:
        if self._raw_handler:
            await self._raw_handler(message)
        event_type = str(message.get("type", ""))
        payload = message.get("payload")
        if not isinstance(payload, dict):
            payload = {}
        link_id = str(payload.get("linkId", ""))
        session = self.sessions.get(link_id)
        if session is None:
            return
        if event_type == "link.handshaking":
            self._cancel_recovery(link_id)
            await self._transition(session, LinkSessionState.HANDSHAKING)
        elif event_type == "link.device_info":
            await self._handle_device_info(session, payload)
        elif event_type == "link.heartbeat":
            session.last_heartbeat_at = utc_now()
            session.latency_ms = _optional_float(payload.get("latencyMs"))
            session.packet_loss_percent = _optional_float(payload.get("packetLossPercent"))
            if session.state in {LinkSessionState.DEGRADED, LinkSessionState.RECOVERING}:
                await self._transition(session, LinkSessionState.HEALTHY)
        elif event_type == "link.debug_ready":
            session.debug_available = True
            session.revision += 1
            await self._emit_session(session)
        elif event_type == "link.degraded":
            await self._transition(
                session,
                LinkSessionState.DEGRADED,
                error_code=_optional_str(payload.get("code")),
                error_message=_optional_str(payload.get("message")),
            )
        elif event_type in {"link.failed", "driver.link_failed"}:
            error_code = _optional_str(payload.get("code")) or "LINK_FAILED"
            recovering = error_code != "DEVICE_ID_MISMATCH"
            await self._transition(
                session,
                LinkSessionState.RECOVERING if recovering else LinkSessionState.FAILED,
                error_code=error_code,
                error_message=_optional_str(payload.get("message")),
            )
            await self._recompute_route(session.device_id)
            if event_type == "link.failed" and recovering:
                self._schedule_recovery(link_id)
        elif event_type == "telemetry.received" and self._telemetry_handler:
            await self._telemetry_handler(message)
        elif event_type.startswith("command.") and self._command_handler:
            await self._command_handler(message)
        elif event_type.startswith("debug.ros"):
            await self.events.transient(
                type=event_type,
                aggregate_type="ros_debug",
                aggregate_id=link_id,
                aggregate_revision=session.revision,
                payload=payload,
            )

    def get_session(self, link_id: str) -> LinkSession | None:
        return self.sessions.get(link_id)

    def list_sessions(self, device_id: str | None = None) -> list[LinkSession]:
        values = list(self.sessions.values())
        if device_id is not None:
            values = [item for item in values if item.device_id == device_id]
        return sorted(values, key=lambda item: item.link_id)

    def operational_state(self, device_id: str) -> DeviceOperationalState:
        sessions = self.list_sessions(device_id)
        healthy = tuple(
            item.link_id
            for item in sessions
            if item.state in {LinkSessionState.HEALTHY, LinkSessionState.DEGRADED}
        )
        active = self._active_links.get(device_id)
        if not healthy:
            status = OperationalStatus.OFFLINE
        elif any(
            item.state
            in {
                LinkSessionState.DEGRADED,
                LinkSessionState.RECOVERING,
                LinkSessionState.FAILED,
            }
            for item in sessions
        ):
            status = OperationalStatus.DEGRADED
        else:
            status = OperationalStatus.ONLINE
        return DeviceOperationalState(
            device_id=device_id,
            status=status,
            active_link_id=active if active in healthy else None,
            healthy_link_ids=healthy,
            last_failover_at=self._last_failovers.get(device_id),
            revision=self._operational_revisions.get(device_id, 0),
        )

    def routing_links(
        self, device_id: str, capability: str, *, broadcast: bool = False
    ) -> list[LinkProfile]:
        candidates: list[LinkProfile] = []
        for profile in self.repository.list_links(device_id):
            session = self.sessions.get(profile.id)
            if (
                profile.enabled
                and session is not None
                and session.state is LinkSessionState.HEALTHY
                and capability in session.capabilities
            ):
                candidates.append(profile)
        candidates.sort(key=lambda item: (item.priority, item.id))
        if broadcast:
            return candidates
        active = self._active_links.get(device_id)
        for candidate in candidates:
            if candidate.id == active:
                return [candidate]
        return candidates[:1]

    async def _handle_device_info(self, session: LinkSession, payload: dict[str, Any]) -> None:
        reported_id = payload.get("deviceId")
        if reported_id != session.device_id:
            await self._transition(
                session,
                LinkSessionState.FAILED,
                error_code="DEVICE_ID_MISMATCH",
                error_message=f"Expected {session.device_id}, received {reported_id}",
            )
            await self.events.raise_alarm(
                code="DEVICE_ID_MISMATCH",
                severity=AlarmSeverity.CRITICAL,
                message=f"Link {session.link_id} reported device {reported_id}",
                device_id=session.device_id,
            )
            profile = self.repository.get_link(session.link_id)
            if profile:
                await self.drivers.stop_link(profile)
            return
        device = self.registry.require_device(session.device_id)
        declared = self.registry.require_template(device.template_id).capabilities
        reported_raw = payload.get("capabilities", [])
        reported = frozenset(str(item) for item in reported_raw if isinstance(item, str))
        session.capabilities = declared.intersection(reported)
        session.last_heartbeat_at = utc_now()
        self._cancel_recovery(session.link_id, reset_attempts=True)
        await self._transition(session, LinkSessionState.HEALTHY)
        await self._recompute_route(session.device_id)

    async def _transition(
        self,
        session: LinkSession,
        state: LinkSessionState,
        *,
        error_code: str | None = None,
        error_message: str | None = None,
    ) -> None:
        previous = session.state
        session.state = state
        self._state_changed_at[session.link_id] = utc_now()
        session.error_code = error_code
        session.error_message = error_message
        session.revision += 1
        if state is LinkSessionState.HEALTHY:
            now = utc_now()
            session.healthy_since = session.healthy_since or now
            session.last_heartbeat_at = session.last_heartbeat_at or now
        elif state not in {LinkSessionState.DEGRADED}:
            session.healthy_since = None
        if state in {LinkSessionState.STOPPED, LinkSessionState.FAILED}:
            session.debug_available = False
        if previous != state or error_code:
            await self._emit_session(session)
        if (
            state in {LinkSessionState.RECOVERING, LinkSessionState.FAILED}
            and self._command_handler
        ):
            await self._command_handler(
                {"type": "command.link_lost", "payload": {"linkId": session.link_id}}
            )

    async def _emit_session(self, session: LinkSession) -> None:
        await self.events.emit(
            SystemEvent(
                type="link_session.changed",
                aggregate_type="link_session",
                aggregate_id=session.link_id,
                aggregate_revision=session.revision,
                payload=_session_payload(session),
            )
        )

    async def _recompute_route(self, device_id: str) -> None:
        now = utc_now()
        profiles = {item.id: item for item in self.repository.list_links(device_id)}
        healthy = [
            item
            for item in self.list_sessions(device_id)
            if item.state is LinkSessionState.HEALTHY and item.link_id in profiles
        ]
        healthy.sort(key=lambda item: (profiles[item.link_id].priority, item.link_id))
        previous = self._active_links.get(device_id)
        selected = (
            previous if previous and any(item.link_id == previous for item in healthy) else None
        )
        if selected is None and healthy:
            selected = healthy[0].link_id
        elif selected and healthy and healthy[0].link_id != selected:
            preferred = healthy[0]
            stable_for = (now - (preferred.healthy_since or now)).total_seconds()
            last_switch = self._last_failovers.get(device_id)
            debounce_elapsed = (
                last_switch is None
                or (now - last_switch).total_seconds() >= self.failback_debounce_seconds
            )
            if (
                stable_for >= self.failback_stable_seconds
                and debounce_elapsed
                and not self._has_inflight_commands(device_id)
            ):
                selected = preferred.link_id
        if selected is None:
            self._active_links.pop(device_id, None)
        else:
            self._active_links[device_id] = selected
        if selected != previous:
            self._last_failovers[device_id] = now
            revision = self._operational_revisions.get(device_id, 0) + 1
            self._operational_revisions[device_id] = revision
            await self.events.emit(
                SystemEvent(
                    type="device.route_changed",
                    aggregate_type="device_operational_state",
                    aggregate_id=device_id,
                    aggregate_revision=revision,
                    payload={
                        "deviceId": device_id,
                        "previousLinkId": previous,
                        "activeLinkId": selected,
                        "occurredAt": now.isoformat(),
                    },
                )
            )

    async def _monitor(self) -> None:
        while True:
            await asyncio.sleep(min(0.5, self.heartbeat_timeout / 3))
            now = utc_now()
            for session in list(self.sessions.values()):
                if session.state not in {LinkSessionState.HEALTHY, LinkSessionState.DEGRADED}:
                    continue
                if session.last_heartbeat_at is None:
                    continue
                age = (now - session.last_heartbeat_at).total_seconds()
                if age >= self.heartbeat_timeout:
                    await self._transition(
                        session,
                        LinkSessionState.RECOVERING,
                        error_code="HEARTBEAT_TIMEOUT",
                        error_message=f"No heartbeat for {age:.1f} seconds",
                    )
                    await self._recompute_route(session.device_id)
                    self._schedule_recovery(session.link_id)
            for session in list(self.sessions.values()):
                if session.state not in {LinkSessionState.STARTING, LinkSessionState.HANDSHAKING}:
                    continue
                changed_at = self._state_changed_at.get(session.link_id, now)
                if (now - changed_at).total_seconds() < self.heartbeat_timeout:
                    continue
                await self._transition(
                    session,
                    LinkSessionState.RECOVERING,
                    error_code="HANDSHAKE_TIMEOUT",
                    error_message="The device identity handshake timed out",
                )
                self._schedule_recovery(session.link_id)
            for device_id in {item.device_id for item in self.sessions.values()}:
                await self._recompute_route(device_id)

    def _schedule_recovery(self, link_id: str) -> None:
        if self._stopping:
            return
        current = self._recovery_tasks.get(link_id)
        if current is not None and not current.done():
            return
        attempt = self._recovery_attempts.get(link_id, 0)
        delay = (1.0, 2.0, 4.0, 8.0)[min(attempt, 3)]
        self._recovery_attempts[link_id] = attempt + 1

        async def recover() -> None:
            try:
                await asyncio.sleep(delay)
                session = self.sessions.get(link_id)
                profile = self.repository.get_link(link_id)
                if (
                    self._stopping
                    or session is None
                    or profile is None
                    or not profile.enabled
                    or session.state not in {LinkSessionState.RECOVERING, LinkSessionState.FAILED}
                ):
                    return
                device = self.registry.require_device(profile.device_id)
                template = self.registry.require_template(device.template_id)
                await self.drivers.start_link(
                    profile,
                    expected_device_id=profile.device_id,
                    requested_capabilities=template.capabilities,
                )
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                session = self.sessions.get(link_id)
                if session is not None:
                    await self._transition(
                        session,
                        LinkSessionState.RECOVERING,
                        error_code="LINK_RECOVERY_FAILED",
                        error_message=str(exc),
                    )
            finally:
                if self._recovery_tasks.get(link_id) is asyncio.current_task():
                    self._recovery_tasks.pop(link_id, None)
                session = self.sessions.get(link_id)
                if (
                    not self._stopping
                    and session is not None
                    and session.state is LinkSessionState.RECOVERING
                ):
                    self._schedule_recovery(link_id)

        self._recovery_tasks[link_id] = asyncio.create_task(
            recover(), name=f"link-recovery-{link_id}"
        )

    def _cancel_recovery(self, link_id: str, *, reset_attempts: bool = False) -> None:
        task = self._recovery_tasks.pop(link_id, None)
        if task is not None and task is not asyncio.current_task():
            task.cancel()
        if reset_attempts:
            self._recovery_attempts.pop(link_id, None)


def _session_payload(session: LinkSession) -> dict[str, Any]:
    return {
        "linkId": session.link_id,
        "deviceId": session.device_id,
        "driver": session.driver.value,
        "state": session.state.value,
        "capabilities": sorted(session.capabilities),
        "startedAt": session.started_at.isoformat() if session.started_at else None,
        "healthySince": session.healthy_since.isoformat() if session.healthy_since else None,
        "lastHeartbeatAt": session.last_heartbeat_at.isoformat()
        if session.last_heartbeat_at
        else None,
        "latencyMs": session.latency_ms,
        "packetLossPercent": session.packet_loss_percent,
        "debugAvailable": session.debug_available,
        "errorCode": session.error_code,
        "errorMessage": session.error_message,
        "revision": session.revision,
    }


def _optional_float(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _optional_str(value: object) -> str | None:
    return value if isinstance(value, str) else None

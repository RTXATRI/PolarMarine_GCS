from __future__ import annotations

import asyncio
from dataclasses import replace
from typing import Any

from polarmarine_gcs.application.commands import CommandService
from polarmarine_gcs.application.events import EventService
from polarmarine_gcs.application.links import LinkCoordinator
from polarmarine_gcs.application.ports.recording import RecordingGateway
from polarmarine_gcs.application.ports.repositories import Repository
from polarmarine_gcs.application.registry import RegistryService
from polarmarine_gcs.application.telemetry import TelemetryService
from polarmarine_gcs.domain.commands import Command, CommandStatus, CommandType
from polarmarine_gcs.domain.common import (
    ConflictError,
    NotFoundError,
    ValidationError,
    new_id,
    utc_now,
)
from polarmarine_gcs.domain.events import SystemEvent
from polarmarine_gcs.domain.links import OperationalStatus
from polarmarine_gcs.domain.missions import (
    MissionPlan,
    MissionPlanStatus,
    MissionRun,
    MissionRunStatus,
    MissionStep,
)
from polarmarine_gcs.domain.telemetry import TelemetryQuality


class MissionService:
    def __init__(
        self,
        repository: Repository,
        registry: RegistryService,
        links: LinkCoordinator,
        telemetry: TelemetryService,
        commands: CommandService,
        events: EventService,
        recordings: RecordingGateway,
    ) -> None:
        self.repository = repository
        self.registry = registry
        self.links = links
        self.telemetry = telemetry
        self.commands = commands
        self.events = events
        self.recordings = recordings
        self._command_steps: dict[str, tuple[str, str]] = {}
        self._control_commands: dict[str, tuple[str, str]] = {}
        self._lock = asyncio.Lock()
        commands.add_status_listener(self._on_command_status)

    async def recover_interrupted_runs(self) -> None:
        for run in self.repository.list_mission_runs(limit=1_000):
            if run.status in {
                MissionRunStatus.QUEUED,
                MissionRunStatus.RUNNING,
                MissionRunStatus.PAUSED,
            }:
                run.status = MissionRunStatus.FAILED
                run.ended_at = utc_now()
                run.revision += 1
                self.repository.save_mission_run(run)
                await self._emit_run(run, reason="core_restarted")

    async def create_plan(
        self,
        *,
        name: str,
        description: str,
        steps: tuple[MissionStep, ...],
    ) -> MissionPlan:
        self._validate_steps(steps)
        plan = MissionPlan(
            id=new_id(),
            name=name,
            version=1,
            status=MissionPlanStatus.VALID,
            steps=steps,
            description=description,
        )
        self.repository.save_mission_plan(plan)
        await self._emit_plan(plan, "mission_plan.created")
        return plan

    async def update_plan(
        self,
        plan_id: str,
        *,
        name: str,
        description: str,
        steps: tuple[MissionStep, ...],
    ) -> MissionPlan:
        current = self.require_plan(plan_id)
        if any(
            run.mission_plan_id == plan_id
            and run.status
            in {MissionRunStatus.QUEUED, MissionRunStatus.RUNNING, MissionRunStatus.PAUSED}
            for run in self.repository.list_mission_runs(limit=1_000)
        ):
            raise ConflictError("An active mission plan version cannot be edited")
        self._validate_steps(steps)
        updated = replace(
            current,
            name=name,
            description=description,
            steps=steps,
            version=current.version + 1,
            revision=current.revision + 1,
            updated_at=utc_now(),
        )
        self.repository.save_mission_plan(updated)
        await self._emit_plan(updated, "mission_plan.updated")
        return updated

    async def delete_plan(self, plan_id: str) -> None:
        plan = self.require_plan(plan_id)
        if any(
            run.mission_plan_id == plan_id for run in self.repository.list_mission_runs(limit=1_000)
        ):
            plan.status = MissionPlanStatus.ARCHIVED
            plan.revision += 1
            plan.updated_at = utc_now()
            self.repository.save_mission_plan(plan)
            await self._emit_plan(plan, "mission_plan.archived")
            return
        self.repository.delete_mission_plan(plan_id)
        await self.events.emit(
            SystemEvent(
                type="mission_plan.deleted",
                aggregate_type="mission_plan",
                aggregate_id=plan_id,
                aggregate_revision=plan.revision + 1,
                payload={},
            )
        )

    def require_plan(self, plan_id: str) -> MissionPlan:
        plan = self.repository.get_mission_plan(plan_id)
        if plan is None:
            raise NotFoundError(f"Mission plan {plan_id} does not exist")
        return plan

    def require_run(self, run_id: str) -> MissionRun:
        run = self.repository.get_mission_run(run_id)
        if run is None:
            raise NotFoundError(f"Mission run {run_id} does not exist")
        return run

    async def start_run(self, plan_id: str) -> MissionRun:
        plan = self.require_plan(plan_id)
        if plan.status is not MissionPlanStatus.VALID:
            raise ConflictError("Only valid mission plans can be started")
        self._preflight(plan)
        active_devices = self._active_mission_devices()
        requested_devices = {step.device_id for step in plan.steps}
        conflicts = sorted(active_devices.intersection(requested_devices))
        if conflicts:
            raise ConflictError(
                "Devices are already assigned to an active mission", details={"devices": conflicts}
            )
        run = MissionRun(
            id=new_id(),
            mission_plan_id=plan.id,
            mission_plan_version=plan.version,
            status=MissionRunStatus.RUNNING,
            step_states={step.id: "pending" for step in plan.steps},
            plan_steps=plan.steps,
            started_at=utc_now(),
        )
        self.repository.save_mission_run(run)
        await self.recordings.begin(run.id, frozenset(requested_devices))
        await self._emit_run(run)
        await self._schedule_ready_steps(run, plan.steps)
        return run

    async def pause(self, run_id: str) -> list[Command]:
        return await self._control(run_id, "pause", CommandType.PAUSE_MISSION)

    async def resume(self, run_id: str) -> list[Command]:
        return await self._control(run_id, "resume", CommandType.RESUME_MISSION)

    async def cancel(self, run_id: str) -> list[Command]:
        return await self._control(run_id, "cancel", CommandType.CANCEL_MISSION)

    async def _control(self, run_id: str, action: str, command_type: CommandType) -> list[Command]:
        run = self.require_run(run_id)
        if run.status in {
            MissionRunStatus.COMPLETED,
            MissionRunStatus.FAILED,
            MissionRunStatus.CANCELLED,
        }:
            return []
        commands: list[Command] = []
        for device_id in sorted({step.device_id for step in self._steps_for_run(run)}):
            command = await self.commands.submit(
                device_id=device_id,
                command_type=command_type,
                payload={"missionRunId": run.id},
            )
            self._control_commands[command.id] = (run.id, action)
            commands.append(command)
        for command in commands:
            if command.status in {
                CommandStatus.COMPLETED,
                CommandStatus.REJECTED,
                CommandStatus.TIMED_OUT,
                CommandStatus.STATE_UNCONFIRMED,
            }:
                await self._on_command_status(command, {})
        return commands

    async def _schedule_ready_steps(self, run: MissionRun, steps: tuple[MissionStep, ...]) -> None:
        if run.status is not MissionRunStatus.RUNNING:
            return
        for step in steps:
            if run.step_states.get(step.id) != "pending":
                continue
            if any(
                run.step_states.get(dependency) != "completed" for dependency in step.depends_on
            ):
                continue
            command_type, payload = _step_command(step)
            run.step_states[step.id] = "dispatching"
            run.revision += 1
            self.repository.save_mission_run(run)
            await self._emit_run(run)
            command = await self.commands.submit(
                device_id=step.device_id,
                command_type=command_type,
                payload={**payload, "missionRunId": run.id, "missionStepId": step.id},
                idempotency_key=f"mission:{run.id}:step:{step.id}",
                execution_timeout_seconds=step.timeout_seconds,
            )
            self._command_steps[command.id] = (run.id, step.id)
            run.step_states[step.id] = (
                "running"
                if command.status not in {CommandStatus.REJECTED, CommandStatus.TIMED_OUT}
                else "failed"
            )
            run.revision += 1
            self.repository.save_mission_run(run)
            await self._emit_run(run)
            if command.status in {
                CommandStatus.COMPLETED,
                CommandStatus.REJECTED,
                CommandStatus.TIMED_OUT,
                CommandStatus.CANCELLED,
                CommandStatus.STATE_UNCONFIRMED,
            }:
                await self._on_command_status(command, {})

    async def _on_command_status(self, command: Command, _payload: dict[str, Any]) -> None:
        step_ref = self._command_steps.get(command.id)
        if step_ref and command.status in {
            CommandStatus.COMPLETED,
            CommandStatus.REJECTED,
            CommandStatus.TIMED_OUT,
            CommandStatus.CANCELLED,
            CommandStatus.STATE_UNCONFIRMED,
        }:
            async with self._lock:
                self._command_steps.pop(command.id, None)
                run = self.require_run(step_ref[0])
                if run.status in {
                    MissionRunStatus.COMPLETED,
                    MissionRunStatus.FAILED,
                    MissionRunStatus.CANCELLED,
                }:
                    return
                steps = self._steps_for_run(run)
                if command.status is CommandStatus.COMPLETED:
                    run.step_states[step_ref[1]] = "completed"
                    if all(value == "completed" for value in run.step_states.values()):
                        run.status = MissionRunStatus.COMPLETED
                        run.ended_at = utc_now()
                else:
                    run.step_states[step_ref[1]] = "failed"
                    run.status = MissionRunStatus.FAILED
                    run.ended_at = utc_now()
                run.revision += 1
                self.repository.save_mission_run(run)
                await self._emit_run(run)
                if run.status is MissionRunStatus.RUNNING:
                    await self._schedule_ready_steps(run, steps)
                elif run.status in {MissionRunStatus.COMPLETED, MissionRunStatus.FAILED}:
                    await self.recordings.finish(
                        run.id, interrupted=run.status is MissionRunStatus.FAILED
                    )
        control_ref = self._control_commands.get(command.id)
        if control_ref and command.status in {
            CommandStatus.COMPLETED,
            CommandStatus.REJECTED,
            CommandStatus.TIMED_OUT,
            CommandStatus.STATE_UNCONFIRMED,
        }:
            self._control_commands.pop(command.id, None)
            run = self.require_run(control_ref[0])
            action = control_ref[1]
            if command.status is not CommandStatus.COMPLETED:
                run.status = MissionRunStatus.FAILED
                run.ended_at = utc_now()
            elif not any(reference[0] == run.id for reference in self._control_commands.values()):
                if action == "pause":
                    run.status = MissionRunStatus.PAUSED
                elif action == "resume":
                    run.status = MissionRunStatus.RUNNING
                else:
                    run.status = MissionRunStatus.CANCELLED
                    run.ended_at = utc_now()
            run.revision += 1
            self.repository.save_mission_run(run)
            await self._emit_run(run)
            if run.status is MissionRunStatus.RUNNING:
                await self._schedule_ready_steps(run, self._steps_for_run(run))
            if run.status in {MissionRunStatus.FAILED, MissionRunStatus.CANCELLED}:
                await self.recordings.finish(
                    run.id, interrupted=run.status is MissionRunStatus.FAILED
                )

    def _preflight(self, plan: MissionPlan) -> None:
        errors: list[dict[str, str]] = []
        for device_id in sorted({step.device_id for step in plan.steps}):
            device_steps = [step for step in plan.steps if step.device_id == device_id]
            operational = self.links.operational_state(device_id)
            if operational.status is OperationalStatus.OFFLINE:
                errors.append({"deviceId": device_id, "code": "DEVICE_OFFLINE"})
                continue
            snapshot = self.telemetry.get_snapshot(device_id)
            if snapshot is None:
                errors.append({"deviceId": device_id, "code": "TELEMETRY_UNKNOWN"})
                continue
            latitude = snapshot.fields.get("position.latitude")
            longitude = snapshot.fields.get("position.longitude")
            if (
                latitude is None
                or longitude is None
                or latitude.quality
                in {TelemetryQuality.INVALID, TelemetryQuality.STALE, TelemetryQuality.UNKNOWN}
                or longitude.quality
                in {TelemetryQuality.INVALID, TelemetryQuality.STALE, TelemetryQuality.UNKNOWN}
            ):
                errors.append({"deviceId": device_id, "code": "POSITION_UNAVAILABLE"})
            battery = snapshot.fields.get("battery.percent")
            if (
                battery is None
                or battery.quality
                in {TelemetryQuality.INVALID, TelemetryQuality.STALE, TelemetryQuality.UNKNOWN}
                or not isinstance(battery.value, (int, float))
            ):
                errors.append({"deviceId": device_id, "code": "BATTERY_UNAVAILABLE"})
            elif battery.value < 15:
                errors.append({"deviceId": device_id, "code": "BATTERY_TOO_LOW"})
            for capability in sorted({_step_capability(step) for step in device_steps}):
                if not self.links.routing_links(device_id, capability):
                    errors.append(
                        {
                            "deviceId": device_id,
                            "code": "CAPABILITY_ROUTE_UNAVAILABLE",
                        }
                    )
            if any(step.step_type == "return_home" for step in device_steps):
                home_latitude = snapshot.fields.get("home.latitude")
                home_longitude = snapshot.fields.get("home.longitude")
                if not _usable_telemetry(home_latitude) or not _usable_telemetry(home_longitude):
                    errors.append({"deviceId": device_id, "code": "HOME_UNAVAILABLE"})
        if errors:
            raise ConflictError("Mission preflight failed", details={"failures": errors})

    def _active_mission_devices(self) -> set[str]:
        active: set[str] = set()
        for run in self.repository.list_mission_runs(limit=1_000):
            if run.status not in {
                MissionRunStatus.QUEUED,
                MissionRunStatus.RUNNING,
                MissionRunStatus.PAUSED,
            }:
                continue
            active.update(step.device_id for step in self._steps_for_run(run))
        return active

    def _steps_for_run(self, run: MissionRun) -> tuple[MissionStep, ...]:
        if run.plan_steps:
            return run.plan_steps
        plan = self.repository.get_mission_plan(run.mission_plan_id)
        return plan.steps if plan else ()

    def _validate_steps(self, steps: tuple[MissionStep, ...]) -> None:
        if not steps:
            raise ValidationError("A mission plan must contain at least one step")
        ids = {step.id for step in steps}
        if len(ids) != len(steps):
            raise ValidationError("Mission step ids must be unique")
        for step in steps:
            device = self.registry.require_device(step.device_id)
            template = self.registry.require_template(device.template_id)
            capability = _step_capability(step)
            if capability not in template.capabilities:
                raise ValidationError(
                    f"Device {step.device_id} does not support {capability}",
                    details={"stepId": step.id, "capability": capability},
                )
            missing = set(step.depends_on).difference(ids)
            if missing:
                raise ValidationError(
                    f"Mission step {step.id} has missing dependencies",
                    details={"dependencies": sorted(missing)},
                )
        _assert_acyclic(steps)

    async def _emit_plan(self, plan: MissionPlan, event_type: str) -> None:
        await self.events.emit(
            SystemEvent(
                type=event_type,
                aggregate_type="mission_plan",
                aggregate_id=plan.id,
                aggregate_revision=plan.revision,
                payload={"id": plan.id, "version": plan.version, "status": plan.status.value},
            )
        )

    async def _emit_run(self, run: MissionRun, *, reason: str | None = None) -> None:
        await self.events.emit(
            SystemEvent(
                type="mission_run.changed",
                aggregate_type="mission_run",
                aggregate_id=run.id,
                aggregate_revision=run.revision,
                payload={
                    "id": run.id,
                    "missionPlanId": run.mission_plan_id,
                    "status": run.status.value,
                    "stepStates": run.step_states,
                    "reason": reason,
                },
            )
        )


def _step_capability(step: MissionStep) -> str:
    mapping = {
        "waypoint": "mission.waypoint",
        "route": "mission.route",
        "return_home": "mission.return_home",
    }
    if step.step_type == "custom_action":
        capability = step.payload.get("capability")
        if not isinstance(capability, str):
            raise ValidationError(f"Custom mission step {step.id} requires a capability")
        return capability
    try:
        return mapping[step.step_type]
    except KeyError as exc:
        raise ValidationError(f"Unsupported mission step type {step.step_type}") from exc


def _step_command(step: MissionStep) -> tuple[CommandType, dict[str, Any]]:
    if step.step_type == "return_home":
        return CommandType.RETURN_HOME, dict(step.payload)
    if step.step_type == "custom_action":
        return CommandType.CUSTOM_ACTION, dict(step.payload)
    return CommandType.START_MISSION, {"stepType": step.step_type, **step.payload}


def _assert_acyclic(steps: tuple[MissionStep, ...]) -> None:
    graph = {step.id: step.depends_on for step in steps}
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(step_id: str) -> None:
        if step_id in visited:
            return
        if step_id in visiting:
            raise ValidationError("Mission dependency graph contains a cycle")
        visiting.add(step_id)
        for dependency in graph[step_id]:
            visit(dependency)
        visiting.remove(step_id)
        visited.add(step_id)

    for step_id in graph:
        visit(step_id)


def _usable_telemetry(value: Any) -> bool:
    return bool(
        value is not None
        and value.quality
        not in {TelemetryQuality.INVALID, TelemetryQuality.STALE, TelemetryQuality.UNKNOWN}
        and isinstance(value.value, (int, float))
    )

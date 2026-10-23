from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, func, select

from polarmarine_gcs.application.ports.repositories import Repository
from polarmarine_gcs.domain.commands import Command, CommandStatus, CommandType
from polarmarine_gcs.domain.devices import (
    Device,
    DeviceCategory,
    DeviceTemplate,
    MediaChannelDefinition,
    ParameterDefinition,
    ParameterValueType,
)
from polarmarine_gcs.domain.events import Alarm, AlarmSeverity, SystemEvent
from polarmarine_gcs.domain.links import DriverKind, LinkProfile, LinkRole
from polarmarine_gcs.domain.missions import (
    MissionPlan,
    MissionPlanStatus,
    MissionRun,
    MissionRunStatus,
    MissionStep,
)
from polarmarine_gcs.domain.recordings import Recording, RecordingStatus

from .database import (
    AlarmRecord,
    CommandRecord,
    Database,
    DeviceRecord,
    DeviceTemplateRecord,
    LinkProfileRecord,
    MissionPlanRecord,
    MissionPlanVersionRecord,
    MissionRunRecord,
    ParameterValuesRecord,
    RecordingRecord,
    SystemEventRecord,
)


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _parameter_to_json(value: ParameterDefinition) -> dict[str, Any]:
    result = asdict(value)
    result["value_type"] = value.value_type.value
    result["enum_values"] = list(value.enum_values)
    return result


def _parameter_from_json(value: dict[str, Any]) -> ParameterDefinition:
    return ParameterDefinition(
        key=str(value["key"]),
        display_name=str(value["display_name"]),
        value_type=ParameterValueType(value["value_type"]),
        default_value=value.get("default_value"),
        unit=value.get("unit"),
        minimum=value.get("minimum"),
        maximum=value.get("maximum"),
        step=value.get("step"),
        description=str(value.get("description", "")),
        enum_values=tuple(value.get("enum_values", ())),
        read_only=bool(value.get("read_only", False)),
    )


def _media_to_json(value: MediaChannelDefinition) -> dict[str, Any]:
    return asdict(value)


def _media_from_json(value: dict[str, Any]) -> MediaChannelDefinition:
    return MediaChannelDefinition(
        id=str(value["id"]),
        display_name=str(value["display_name"]),
        role=str(value.get("role", "video")),
        required=bool(value.get("required", False)),
    )


def _step_to_json(value: MissionStep) -> dict[str, Any]:
    result = asdict(value)
    result["depends_on"] = list(value.depends_on)
    return result


def _step_from_json(value: dict[str, Any]) -> MissionStep:
    return MissionStep(
        id=str(value["id"]),
        step_type=str(value["step_type"]),
        device_id=str(value["device_id"]),
        depends_on=tuple(value.get("depends_on", ())),
        timeout_seconds=float(value.get("timeout_seconds", 60.0)),
        payload=dict(value.get("payload", {})),
    )


class SqliteRepository(Repository):
    def __init__(self, database: Database) -> None:
        self.database = database

    def list_templates(self) -> list[DeviceTemplate]:
        with self.database.session() as session:
            records = session.scalars(
                select(DeviceTemplateRecord).order_by(DeviceTemplateRecord.id)
            ).all()
            return [self._template(record) for record in records]

    def get_template(self, template_id: str) -> DeviceTemplate | None:
        with self.database.session() as session:
            record = session.get(DeviceTemplateRecord, template_id)
            return self._template(record) if record else None

    def save_template(self, template: DeviceTemplate) -> DeviceTemplate:
        record = DeviceTemplateRecord(
            id=template.id,
            display_name=template.display_name,
            category=template.category.value,
            description=template.description,
            capabilities=sorted(template.capabilities),
            parameters=[_parameter_to_json(item) for item in template.parameters],
            media_channels=[_media_to_json(item) for item in template.media_channels],
            revision=template.revision,
            created_at=template.created_at,
            updated_at=template.updated_at,
        )
        with self.database.session() as session:
            session.merge(record)
        return template

    def delete_template(self, template_id: str) -> None:
        with self.database.session() as session:
            session.execute(
                delete(DeviceTemplateRecord).where(DeviceTemplateRecord.id == template_id)
            )

    def list_devices(self) -> list[Device]:
        with self.database.session() as session:
            records = session.scalars(select(DeviceRecord).order_by(DeviceRecord.created_at)).all()
            return [self._device(record) for record in records]

    def get_device(self, device_id: str) -> Device | None:
        with self.database.session() as session:
            record = session.get(DeviceRecord, device_id)
            return self._device(record) if record else None

    def save_device(self, device: Device) -> Device:
        record = DeviceRecord(
            id=device.id,
            template_id=device.template_id,
            display_name=device.display_name,
            enabled=device.enabled,
            description=device.description,
            tags=list(device.tags),
            revision=device.revision,
            created_at=device.created_at,
            updated_at=device.updated_at,
        )
        with self.database.session() as session:
            session.merge(record)
        return device

    def delete_device(self, device_id: str) -> None:
        with self.database.session() as session:
            session.execute(delete(DeviceRecord).where(DeviceRecord.id == device_id))

    def list_links(self, device_id: str | None = None) -> list[LinkProfile]:
        statement = select(LinkProfileRecord)
        if device_id is not None:
            statement = statement.where(LinkProfileRecord.device_id == device_id)
        statement = statement.order_by(LinkProfileRecord.device_id, LinkProfileRecord.priority)
        with self.database.session() as session:
            return [self._link(record) for record in session.scalars(statement).all()]

    def get_link(self, link_id: str) -> LinkProfile | None:
        with self.database.session() as session:
            record = session.get(LinkProfileRecord, link_id)
            return self._link(record) if record else None

    def save_link(self, profile: LinkProfile) -> LinkProfile:
        record = LinkProfileRecord(
            id=profile.id,
            device_id=profile.device_id,
            display_name=profile.display_name,
            driver=profile.driver.value,
            role=profile.role.value,
            priority=profile.priority,
            config=profile.config,
            enabled=profile.enabled,
            revision=profile.revision,
            created_at=profile.created_at,
            updated_at=profile.updated_at,
        )
        with self.database.session() as session:
            session.merge(record)
        return profile

    def delete_link(self, link_id: str) -> None:
        with self.database.session() as session:
            session.execute(delete(LinkProfileRecord).where(LinkProfileRecord.id == link_id))

    def save_command(self, command: Command) -> Command:
        record = CommandRecord(
            id=command.id,
            device_id=command.device_id,
            command_type=command.command_type.value,
            payload=command.payload,
            status=command.status.value,
            progress=command.progress,
            result=command.result,
            routed_link_ids=list(command.routed_link_ids),
            link_acknowledgements=command.link_acknowledgements,
            idempotency_key=command.idempotency_key,
            reason_code=command.reason_code,
            reason_message=command.reason_message,
            requires_state_confirmation=command.requires_state_confirmation,
            created_at=command.created_at,
            updated_at=command.updated_at,
            expires_at=command.expires_at,
            revision=command.revision,
        )
        with self.database.session() as session:
            session.merge(record)
        return command

    def get_command(self, command_id: str) -> Command | None:
        with self.database.session() as session:
            record = session.get(CommandRecord, command_id)
            return self._command(record) if record else None

    def get_command_by_idempotency_key(
        self, device_id: str, idempotency_key: str
    ) -> Command | None:
        statement = select(CommandRecord).where(
            CommandRecord.device_id == device_id,
            CommandRecord.idempotency_key == idempotency_key,
        )
        with self.database.session() as session:
            record = session.scalar(statement)
            return self._command(record) if record else None

    def list_commands(self, device_id: str | None = None, limit: int = 100) -> list[Command]:
        statement = select(CommandRecord)
        if device_id is not None:
            statement = statement.where(CommandRecord.device_id == device_id)
        statement = statement.order_by(CommandRecord.created_at.desc()).limit(limit)
        with self.database.session() as session:
            return [self._command(record) for record in session.scalars(statement).all()]

    def append_event(self, event: SystemEvent) -> SystemEvent:
        record = SystemEventRecord(
            id=event.id,
            type=event.type,
            aggregate_type=event.aggregate_type,
            aggregate_id=event.aggregate_id,
            aggregate_revision=event.aggregate_revision,
            payload=event.payload,
            occurred_at=event.occurred_at,
        )
        with self.database.session() as session:
            session.add(record)
            session.flush()
            event.cursor = record.cursor
        return event

    def list_events(
        self,
        *,
        after: int | None = None,
        before: int | None = None,
        event_type: str | None = None,
        aggregate_id: str | None = None,
        limit: int = 200,
    ) -> list[SystemEvent]:
        statement = select(SystemEventRecord)
        if after is not None:
            statement = statement.where(SystemEventRecord.cursor > after)
        if before is not None:
            statement = statement.where(SystemEventRecord.cursor < before)
        if event_type is not None:
            statement = statement.where(SystemEventRecord.type == event_type)
        if aggregate_id is not None:
            statement = statement.where(SystemEventRecord.aggregate_id == aggregate_id)
        order = SystemEventRecord.cursor if after is not None else SystemEventRecord.cursor.desc()
        statement = statement.order_by(order).limit(limit)
        with self.database.session() as session:
            return [self._event(record) for record in session.scalars(statement).all()]

    def latest_event_cursor(self) -> int:
        with self.database.session() as session:
            return int(session.scalar(select(func.max(SystemEventRecord.cursor))) or 0)

    def save_alarm(self, alarm: Alarm) -> Alarm:
        record = AlarmRecord(
            id=alarm.id,
            code=alarm.code,
            severity=alarm.severity.value,
            message=alarm.message,
            device_id=alarm.device_id,
            acknowledged=alarm.acknowledged,
            created_at=alarm.created_at,
            acknowledged_at=alarm.acknowledged_at,
            revision=alarm.revision,
        )
        with self.database.session() as session:
            session.merge(record)
        return alarm

    def get_alarm(self, alarm_id: str) -> Alarm | None:
        with self.database.session() as session:
            record = session.get(AlarmRecord, alarm_id)
            return self._alarm(record) if record else None

    def list_alarms(self, active_only: bool = False, limit: int = 200) -> list[Alarm]:
        statement = select(AlarmRecord)
        if active_only:
            statement = statement.where(AlarmRecord.acknowledged.is_(False))
        statement = statement.order_by(AlarmRecord.created_at.desc()).limit(limit)
        with self.database.session() as session:
            return [self._alarm(record) for record in session.scalars(statement).all()]

    def save_mission_plan(self, plan: MissionPlan) -> MissionPlan:
        record = MissionPlanRecord(
            id=plan.id,
            name=plan.name,
            version=plan.version,
            status=plan.status.value,
            steps=[_step_to_json(item) for item in plan.steps],
            description=plan.description,
            revision=plan.revision,
            created_at=plan.created_at,
            updated_at=plan.updated_at,
        )
        version_record = MissionPlanVersionRecord(
            plan_id=plan.id,
            version=plan.version,
            name=plan.name,
            status=plan.status.value,
            steps=[_step_to_json(item) for item in plan.steps],
            description=plan.description,
            created_at=plan.updated_at,
        )
        with self.database.session() as session:
            session.merge(record)
            session.merge(version_record)
        return plan

    def get_mission_plan(self, plan_id: str) -> MissionPlan | None:
        with self.database.session() as session:
            record = session.get(MissionPlanRecord, plan_id)
            return self._mission_plan(record) if record else None

    def list_mission_plans(self) -> list[MissionPlan]:
        with self.database.session() as session:
            statement = select(MissionPlanRecord).order_by(MissionPlanRecord.updated_at.desc())
            return [self._mission_plan(record) for record in session.scalars(statement).all()]

    def list_mission_plan_versions(self, plan_id: str) -> list[MissionPlan]:
        with self.database.session() as session:
            statement = (
                select(MissionPlanVersionRecord)
                .where(MissionPlanVersionRecord.plan_id == plan_id)
                .order_by(MissionPlanVersionRecord.version.desc())
            )
            return [self._mission_plan_version(record) for record in session.scalars(statement)]

    def delete_mission_plan(self, plan_id: str) -> None:
        with self.database.session() as session:
            session.execute(delete(MissionPlanRecord).where(MissionPlanRecord.id == plan_id))

    def save_mission_run(self, run: MissionRun) -> MissionRun:
        record = MissionRunRecord(
            id=run.id,
            mission_plan_id=run.mission_plan_id,
            mission_plan_version=run.mission_plan_version,
            status=run.status.value,
            step_states=run.step_states,
            plan_steps=[_step_to_json(item) for item in run.plan_steps],
            started_at=run.started_at,
            ended_at=run.ended_at,
            revision=run.revision,
            created_at=run.created_at,
        )
        with self.database.session() as session:
            session.merge(record)
        return run

    def get_mission_run(self, run_id: str) -> MissionRun | None:
        with self.database.session() as session:
            record = session.get(MissionRunRecord, run_id)
            return self._mission_run(record) if record else None

    def list_mission_runs(self, limit: int = 100) -> list[MissionRun]:
        with self.database.session() as session:
            statement = (
                select(MissionRunRecord).order_by(MissionRunRecord.created_at.desc()).limit(limit)
            )
            return [self._mission_run(record) for record in session.scalars(statement).all()]

    def get_parameter_values(self, device_id: str) -> dict[str, object]:
        with self.database.session() as session:
            record = session.get(ParameterValuesRecord, device_id)
            return dict(record.values) if record else {}

    def set_parameter_values(self, device_id: str, values: dict[str, object]) -> None:
        record = ParameterValuesRecord(
            device_id=device_id,
            values=values,
            updated_at=datetime.now(UTC),
        )
        with self.database.session() as session:
            session.merge(record)

    def save_recording(self, recording: Recording) -> Recording:
        record = RecordingRecord(
            id=recording.id,
            mission_run_id=recording.mission_run_id,
            path=recording.path,
            size_bytes=recording.size_bytes,
            status=recording.status.value,
            started_at=recording.started_at,
            ended_at=recording.ended_at,
        )
        with self.database.session() as session:
            session.merge(record)
        return recording

    def get_recording(self, recording_id: str) -> Recording | None:
        with self.database.session() as session:
            record = session.get(RecordingRecord, recording_id)
            return self._recording(record) if record else None

    def list_recordings(self) -> list[Recording]:
        with self.database.session() as session:
            statement = select(RecordingRecord).order_by(RecordingRecord.started_at.desc())
            return [self._recording(record) for record in session.scalars(statement).all()]

    def delete_recording(self, recording_id: str) -> None:
        with self.database.session() as session:
            session.execute(delete(RecordingRecord).where(RecordingRecord.id == recording_id))

    @staticmethod
    def _template(record: DeviceTemplateRecord) -> DeviceTemplate:
        return DeviceTemplate(
            id=record.id,
            display_name=record.display_name,
            category=DeviceCategory(record.category),
            description=record.description,
            capabilities=frozenset(record.capabilities),
            parameters=tuple(_parameter_from_json(item) for item in record.parameters),
            media_channels=tuple(_media_from_json(item) for item in record.media_channels),
            revision=record.revision,
            created_at=_aware(record.created_at) or datetime.now(UTC),
            updated_at=_aware(record.updated_at) or datetime.now(UTC),
        )

    @staticmethod
    def _device(record: DeviceRecord) -> Device:
        return Device(
            id=record.id,
            template_id=record.template_id,
            display_name=record.display_name,
            enabled=record.enabled,
            description=record.description,
            tags=tuple(record.tags),
            revision=record.revision,
            created_at=_aware(record.created_at) or datetime.now(UTC),
            updated_at=_aware(record.updated_at) or datetime.now(UTC),
        )

    @staticmethod
    def _link(record: LinkProfileRecord) -> LinkProfile:
        return LinkProfile(
            id=record.id,
            device_id=record.device_id,
            display_name=record.display_name,
            driver=DriverKind(record.driver),
            role=LinkRole(record.role),
            priority=record.priority,
            config=dict(record.config),
            enabled=record.enabled,
            revision=record.revision,
            created_at=_aware(record.created_at) or datetime.now(UTC),
            updated_at=_aware(record.updated_at) or datetime.now(UTC),
        )

    @staticmethod
    def _command(record: CommandRecord) -> Command:
        return Command(
            id=record.id,
            device_id=record.device_id,
            command_type=CommandType(record.command_type),
            payload=dict(record.payload),
            status=CommandStatus(record.status),
            progress=record.progress,
            result=dict(record.result),
            routed_link_ids=tuple(record.routed_link_ids),
            link_acknowledgements=dict(record.link_acknowledgements),
            idempotency_key=record.idempotency_key,
            reason_code=record.reason_code,
            reason_message=record.reason_message,
            requires_state_confirmation=record.requires_state_confirmation,
            created_at=_aware(record.created_at) or datetime.now(UTC),
            updated_at=_aware(record.updated_at) or datetime.now(UTC),
            expires_at=_aware(record.expires_at),
            revision=record.revision,
        )

    @staticmethod
    def _event(record: SystemEventRecord) -> SystemEvent:
        return SystemEvent(
            id=record.id,
            type=record.type,
            aggregate_type=record.aggregate_type,
            aggregate_id=record.aggregate_id,
            aggregate_revision=record.aggregate_revision,
            payload=dict(record.payload),
            occurred_at=_aware(record.occurred_at) or datetime.now(UTC),
            cursor=record.cursor,
        )

    @staticmethod
    def _alarm(record: AlarmRecord) -> Alarm:
        return Alarm(
            id=record.id,
            code=record.code,
            severity=AlarmSeverity(record.severity),
            message=record.message,
            device_id=record.device_id,
            acknowledged=record.acknowledged,
            created_at=_aware(record.created_at) or datetime.now(UTC),
            acknowledged_at=_aware(record.acknowledged_at),
            revision=record.revision,
        )

    @staticmethod
    def _mission_plan(record: MissionPlanRecord) -> MissionPlan:
        return MissionPlan(
            id=record.id,
            name=record.name,
            version=record.version,
            status=MissionPlanStatus(record.status),
            steps=tuple(_step_from_json(item) for item in record.steps),
            description=record.description,
            revision=record.revision,
            created_at=_aware(record.created_at) or datetime.now(UTC),
            updated_at=_aware(record.updated_at) or datetime.now(UTC),
        )

    @staticmethod
    def _mission_plan_version(record: MissionPlanVersionRecord) -> MissionPlan:
        created_at = _aware(record.created_at) or datetime.now(UTC)
        return MissionPlan(
            id=record.plan_id,
            name=record.name,
            version=record.version,
            status=MissionPlanStatus(record.status),
            steps=tuple(_step_from_json(item) for item in record.steps),
            description=record.description,
            revision=record.version,
            created_at=created_at,
            updated_at=created_at,
        )

    @staticmethod
    def _mission_run(record: MissionRunRecord) -> MissionRun:
        return MissionRun(
            id=record.id,
            mission_plan_id=record.mission_plan_id,
            mission_plan_version=record.mission_plan_version,
            status=MissionRunStatus(record.status),
            step_states=dict(record.step_states),
            plan_steps=tuple(_step_from_json(item) for item in record.plan_steps),
            started_at=_aware(record.started_at),
            ended_at=_aware(record.ended_at),
            revision=record.revision,
            created_at=_aware(record.created_at) or datetime.now(UTC),
        )

    @staticmethod
    def _recording(record: RecordingRecord) -> Recording:
        return Recording(
            id=record.id,
            mission_run_id=record.mission_run_id,
            path=record.path,
            size_bytes=record.size_bytes,
            status=RecordingStatus(record.status),
            started_at=_aware(record.started_at) or datetime.now(UTC),
            ended_at=_aware(record.ended_at),
        )

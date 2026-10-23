from __future__ import annotations

from pathlib import Path
from typing import Any

from polarmarine_gcs.application.commands import command_payload
from polarmarine_gcs.application.parameters import parameter_definition_payload
from polarmarine_gcs.domain.commands import Command
from polarmarine_gcs.domain.devices import Device, DeviceTemplate
from polarmarine_gcs.domain.events import Alarm, SystemEvent
from polarmarine_gcs.domain.links import DeviceOperationalState, LinkProfile, LinkSession
from polarmarine_gcs.domain.missions import MissionPlan, MissionRun
from polarmarine_gcs.domain.recordings import Recording
from polarmarine_gcs.domain.telemetry import TelemetrySnapshot

from .schemas import (
    AlarmDto,
    CommandDto,
    DeviceDto,
    DeviceTemplateDto,
    LinkProfileDto,
    LinkSessionDto,
    MissionPlanDto,
    MissionRunDto,
    OperationalStateDto,
    ParameterStateDto,
    PersistedEventDto,
    RecordingDto,
    TelemetrySnapshotDto,
)


def template_dto(value: DeviceTemplate) -> DeviceTemplateDto:
    return DeviceTemplateDto.model_validate(value)


def device_dto(value: Device) -> DeviceDto:
    return DeviceDto.model_validate(value)


def link_dto(value: LinkProfile) -> LinkProfileDto:
    return LinkProfileDto.model_validate(value)


def session_dto(value: LinkSession) -> LinkSessionDto:
    return LinkSessionDto.model_validate(value)


def operational_dto(value: DeviceOperationalState) -> OperationalStateDto:
    return OperationalStateDto.model_validate(value)


def telemetry_dto(value: TelemetrySnapshot) -> TelemetrySnapshotDto:
    return TelemetrySnapshotDto.model_validate(value)


def command_dto(value: Command) -> CommandDto:
    return CommandDto.model_validate(command_payload(value))


def alarm_dto(value: Alarm) -> AlarmDto:
    return AlarmDto.model_validate(value)


def mission_plan_dto(value: MissionPlan) -> MissionPlanDto:
    return MissionPlanDto.model_validate(value)


def mission_run_dto(value: MissionRun) -> MissionRunDto:
    return MissionRunDto.model_validate(value)


def recording_dto(value: Recording) -> RecordingDto:
    return RecordingDto(
        id=value.id,
        mission_run_id=value.mission_run_id,
        file_name=Path(value.path).name,
        status=value.status,
        size_bytes=value.size_bytes,
        started_at=value.started_at,
        ended_at=value.ended_at,
    )


def parameter_state_dto(value: dict[str, Any]) -> ParameterStateDto:
    definition = parameter_definition_payload(value["definition"])
    return ParameterStateDto.model_validate(
        {"definition": definition, "value": value["value"], "source": value["source"]}
    )


def event_dto(value: SystemEvent) -> PersistedEventDto:
    if value.cursor is None:
        raise ValueError("A persisted event must have a cursor")
    return PersistedEventDto(
        event_id=value.id,
        event_cursor=value.cursor,
        aggregate_type=value.aggregate_type,
        aggregate_id=value.aggregate_id,
        aggregate_revision=value.aggregate_revision,
        occurred_at=value.occurred_at,
        type=value.type,
        payload=value.payload,
    )

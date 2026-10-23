from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from polarmarine_gcs.domain.commands import CommandStatus, CommandType
from polarmarine_gcs.domain.devices import DeviceCategory, ParameterValueType
from polarmarine_gcs.domain.events import AlarmSeverity
from polarmarine_gcs.domain.links import DriverKind, LinkRole, LinkSessionState, OperationalStatus
from polarmarine_gcs.domain.missions import MissionPlanStatus, MissionRunStatus
from polarmarine_gcs.domain.recordings import RecordingStatus
from polarmarine_gcs.domain.telemetry import TelemetryQuality


def to_camel(value: str) -> str:
    head, *tail = value.split("_")
    return head + "".join(item.capitalize() for item in tail)


class WireModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )


class ErrorBody(WireModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    request_id: str


class ErrorResponse(WireModel):
    error: ErrorBody


class ParameterDefinitionDto(WireModel):
    key: str
    display_name: str
    value_type: ParameterValueType
    default_value: Any
    unit: str | None = None
    minimum: float | None = None
    maximum: float | None = None
    step: float | None = None
    description: str = ""
    enum_values: list[str] = Field(default_factory=list)
    read_only: bool = False


class MediaChannelDto(WireModel):
    id: str
    display_name: str
    role: str = "video"
    required: bool = False


class DeviceTemplateWrite(WireModel):
    id: str | None = None
    display_name: str = Field(min_length=1, max_length=128)
    category: DeviceCategory
    description: str = Field(default="", max_length=2_000)
    capabilities: list[str] = Field(default_factory=list)
    parameters: list[ParameterDefinitionDto] = Field(default_factory=list)
    media_channels: list[MediaChannelDto] = Field(default_factory=list)


class DeviceTemplateDto(DeviceTemplateWrite):
    id: str
    revision: int
    created_at: datetime
    updated_at: datetime


class DeviceWrite(WireModel):
    id: str | None = None
    template_id: str
    display_name: str = Field(min_length=1, max_length=128)
    enabled: bool = True
    description: str = Field(default="", max_length=2_000)
    tags: list[str] = Field(default_factory=list, max_length=32)


class DeviceDto(DeviceWrite):
    id: str
    revision: int
    created_at: datetime
    updated_at: datetime


class LinkProfileWrite(WireModel):
    display_name: str = Field(min_length=1, max_length=128)
    driver: DriverKind
    role: LinkRole = LinkRole.PRIMARY
    priority: int = Field(default=100, ge=0, le=10_000)
    config: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True


class LinkProfileDto(LinkProfileWrite):
    id: str
    device_id: str
    revision: int
    created_at: datetime
    updated_at: datetime


class LinkSessionDto(WireModel):
    link_id: str
    device_id: str
    driver: DriverKind
    state: LinkSessionState
    capabilities: list[str]
    started_at: datetime | None = None
    healthy_since: datetime | None = None
    last_heartbeat_at: datetime | None = None
    latency_ms: float | None = None
    packet_loss_percent: float | None = None
    debug_available: bool = False
    error_code: str | None = None
    error_message: str | None = None
    revision: int


class OperationalStateDto(WireModel):
    device_id: str
    status: OperationalStatus
    active_link_id: str | None
    healthy_link_ids: list[str]
    last_failover_at: datetime | None
    revision: int


class AsyncOperationReceipt(WireModel):
    operation_id: str
    status: str = "accepted"
    session: LinkSessionDto


class TelemetryValueDto(WireModel):
    value: Any
    source_link_id: str
    collected_at: datetime
    received_at: datetime
    quality: TelemetryQuality
    unit: str | None = None


class TelemetrySnapshotDto(WireModel):
    device_id: str
    fields: dict[str, TelemetryValueDto]
    revision: int
    updated_at: datetime


class CommandRequest(WireModel):
    command_type: CommandType
    payload: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str | None = Field(default=None, max_length=128)


class CommandDto(WireModel):
    id: str
    device_id: str
    command_type: CommandType
    payload: dict[str, Any]
    status: CommandStatus
    progress: float | None
    result: dict[str, Any]
    routed_link_ids: list[str]
    link_acknowledgements: dict[str, str]
    idempotency_key: str | None
    reason_code: str | None
    reason_message: str | None
    requires_state_confirmation: bool
    created_at: datetime
    updated_at: datetime
    expires_at: datetime | None
    revision: int


class EventDto(WireModel):
    schema_version: str = "1.0"
    event_id: str
    server_instance_id: str
    connection_sequence: int
    event_cursor: int | None
    aggregate_type: str
    aggregate_id: str
    aggregate_revision: int
    occurred_at: datetime
    type: str
    payload: dict[str, Any]


class PersistedEventDto(WireModel):
    event_id: str
    event_cursor: int
    aggregate_type: str
    aggregate_id: str
    aggregate_revision: int
    occurred_at: datetime
    type: str
    payload: dict[str, Any]


class AlarmDto(WireModel):
    id: str
    code: str
    severity: AlarmSeverity
    message: str
    device_id: str | None
    acknowledged: bool
    created_at: datetime
    acknowledged_at: datetime | None
    revision: int


class MissionStepDto(WireModel):
    id: str
    step_type: str
    device_id: str
    depends_on: list[str] = Field(default_factory=list)
    timeout_seconds: float = Field(default=60.0, gt=0, le=86_400)
    payload: dict[str, Any] = Field(default_factory=dict)


class MissionPlanWrite(WireModel):
    name: str = Field(min_length=1, max_length=128)
    description: str = Field(default="", max_length=2_000)
    steps: list[MissionStepDto]


class MissionPlanDto(MissionPlanWrite):
    id: str
    version: int
    status: MissionPlanStatus
    revision: int
    created_at: datetime
    updated_at: datetime


class MissionRunDto(WireModel):
    id: str
    mission_plan_id: str
    mission_plan_version: int
    status: MissionRunStatus
    step_states: dict[str, str]
    plan_steps: list[MissionStepDto]
    started_at: datetime | None
    ended_at: datetime | None
    revision: int
    created_at: datetime


class MissionControlReceipt(WireModel):
    mission_run_id: str
    commands: list[CommandDto]


class ParameterStateDto(WireModel):
    definition: ParameterDefinitionDto
    value: Any
    source: str


class ParameterWriteRequest(WireModel):
    values: dict[str, Any]


class RecordingDto(WireModel):
    id: str
    mission_run_id: str
    file_name: str
    status: RecordingStatus
    size_bytes: int
    started_at: datetime
    ended_at: datetime | None


class RecordingMessageDto(WireModel):
    topic: str
    log_time_ns: int
    publish_time_ns: int
    payload: Any


class RosDebugRequest(WireModel):
    link_id: str
    operation: str
    topic: str | None = None
    service: str | None = None
    action: str | None = None
    parameter: str | None = None
    message: dict[str, Any] = Field(default_factory=dict)
    arguments: dict[str, Any] = Field(default_factory=dict)
    throttle_ms: int = Field(default=20, ge=20, le=60_000)


class NetworkDiscoveryCandidate(WireModel):
    service_name: str
    host: str
    port: int
    addresses: list[str] = Field(default_factory=list)
    device_id: str | None = None
    schema_version: str | None = None
    ros_version: str | None = None
    identity_verified: bool = False


class NetworkDiscoveryResponse(WireModel):
    ok: bool
    driver: DriverKind
    candidates: list[NetworkDiscoveryCandidate] = Field(default_factory=list)


class BootstrapSettingsDto(WireModel):
    baidu_map_ak: str | None
    offline_map_style_url: str | None
    simulator_label: str = "仿真数据"
    max_configured_devices: int
    max_online_devices: int


class BootstrapDto(WireModel):
    server_instance_id: str
    event_cursor: int
    templates: list[DeviceTemplateDto]
    devices: list[DeviceDto]
    links: list[LinkProfileDto]
    link_sessions: list[LinkSessionDto]
    operational_states: list[OperationalStateDto]
    telemetry_snapshots: list[TelemetrySnapshotDto]
    active_alarms: list[AlarmDto]
    recent_commands: list[CommandDto]
    active_mission_runs: list[MissionRunDto]
    settings: BootstrapSettingsDto


class HealthDto(WireModel):
    status: str = "ok"
    version: str
    server_instance_id: str

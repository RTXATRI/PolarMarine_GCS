from __future__ import annotations

from datetime import datetime
from ipaddress import IPv4Address
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, computed_field, field_validator, model_validator

RobotId = str
LinkType = Literal["有线", "WIFI", "4G", "数传"]
ControlMode = Literal["手动", "自动", "离线", "急停"]
LinkStatus = Literal["正常", "延迟高", "丢包", "断开"]
DeviceType = Literal["uav", "usv", "dock"]
NavState = Literal["idle", "navigating", "paused", "returning_home"]
MissionStatus = Literal["空闲", "正在前往目标点", "导航中", "巡航中", "返航中", "暂停", "急停", "无任务"]
LogType = Literal["操作", "通信", "报警", "系统"]
AlarmLevel = Literal["提示", "警告", "严重"]
ConnectionState = Literal["disconnected", "connecting", "connected", "error"]
ConnectionMethod = Literal["serial", "network"]
DataMode = Literal["none", "virtual", "live"]
CommandMode = Literal["none", "virtual", "live"]
BaudRate = Literal[9600, 19200, 38400, 57600, 115200]


class Position(BaseModel):
    lat: float
    lon: float


class GoalPoint(BaseModel):
    id: str
    lat: float
    lon: float
    speed: float = 0.0


class SerialConnectionProfile(BaseModel):
    method: Literal["serial"]
    port: str = Field(min_length=1, max_length=255)
    baudRate: BaudRate = 115200

    @field_validator("port")
    @classmethod
    def normalize_port(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("串口设备不能为空")
        return value


class NetworkConnectionProfile(BaseModel):
    method: Literal["network"]
    host: IPv4Address
    port: int = Field(ge=1, le=65535)


ConnectionProfile = Annotated[
    SerialConnectionProfile | NetworkConnectionProfile,
    Field(discriminator="method"),
]


class ConnectionErrorInfo(BaseModel):
    code: str
    message: str


class ConnectionRuntime(BaseModel):
    state: ConnectionState = "disconnected"
    activeMethod: ConnectionMethod | None = None
    endpoint: str | None = None
    dataMode: DataMode = "none"
    commandMode: CommandMode = "none"
    connectedAt: str | None = None
    error: ConnectionErrorInfo | None = None


class Robot(BaseModel):
    id: RobotId
    robotType: DeviceType
    connectionProfile: ConnectionProfile | None = None
    connection: ConnectionRuntime = Field(default_factory=ConnectionRuntime)
    # Deprecated compatibility field. New clients derive the label from
    # connection.activeMethod. It is deliberately null while disconnected.
    link: LinkType | None = None
    battery: int | None = None
    mode: ControlMode | None = None
    px4Mode: str | None = None
    missionStatus: MissionStatus | None = None
    linkStatus: LinkStatus | None = None
    latencyMs: int | None = None
    packetLoss: float | None = None
    rssi: int | None = None
    position: Position | None = None
    altitude: float | None = None
    speed: float | None = None
    heading: float | None = None
    alarm: str | None = None
    trail: list[Position] = Field(default_factory=list)
    lastCommAt: str | None = None
    unlocked: bool | None = None
    relayEnabled: bool | None = None
    maxSpeed: float
    homePosition: Position | None = None
    navState: NavState = "idle"
    navGoals: list[GoalPoint] = Field(default_factory=list)
    navGoalIndex: int = 0
    wobbleAnchor: Position | None = None

    @computed_field(return_type=bool)
    @property
    def online(self) -> bool:
        """Compatibility field derived exclusively from connection runtime."""
        return self.connection.state == "connected"


class SerialPortInfo(BaseModel):
    port: str
    description: str
    manufacturer: str | None = None
    hwid: str | None = None


class NetworkCandidate(BaseModel):
    host: str
    hostname: str | None = None
    port: int
    latencyMs: int | None = None


class LogEntry(BaseModel):
    id: int
    time: str
    type: LogType
    robotId: RobotId | None
    content: str


class Alarm(BaseModel):
    id: int
    time: str
    level: AlarmLevel
    robotId: RobotId
    content: str
    acknowledged: bool = False


class Parameter(BaseModel):
    key: str
    name: str
    currentValue: float
    editValue: float
    unit: str
    description: str
    defaultValue: float


class TelemetryMsg(BaseModel):
    id: int
    time: str
    robotId: RobotId
    fields: dict[str, str]


class HealthResponse(BaseModel):
    status: Literal["ok"]
    app: str
    rosbridgeConnected: bool
    rosbridgeConnectedCount: int = 0
    mockSimulatorEnabled: bool


class RosTelemetryData(BaseModel):
    """Versioned status payload emitted by the onboard ROS1 adapter."""

    model_config = ConfigDict(extra="ignore")

    sourceConnected: StrictBool
    battery: int | None = Field(default=None, ge=0, le=100)
    mode: ControlMode | None = None
    px4Mode: str | None = Field(default=None, max_length=64)
    # Accepted for wire compatibility, but task status remains owned by the
    # ground station's virtual task service and is never mapped to Robot.
    missionStatus: MissionStatus | None = None
    linkStatus: LinkStatus | None = None
    latencyMs: int | None = Field(default=None, ge=0)
    packetLoss: float | None = Field(default=None, ge=0, le=100, allow_inf_nan=False)
    rssi: int | None = None
    lat: float | None = Field(default=None, ge=-90, le=90, allow_inf_nan=False)
    lon: float | None = Field(default=None, ge=-180, le=180, allow_inf_nan=False)
    altitude: float | None = Field(default=None, allow_inf_nan=False)
    speed: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    heading: float | None = Field(default=None, ge=0, lt=360, allow_inf_nan=False)
    unlocked: StrictBool | None = None
    relayEnabled: StrictBool | None = None
    alarm: str | None = Field(default=None, max_length=256)

    @model_validator(mode="after")
    def require_complete_position(self) -> "RosTelemetryData":
        if (self.lat is None) != (self.lon is None):
            raise ValueError("lat 和 lon 必须同时提供或同时为空")
        return self


class RosTelemetryEnvelope(BaseModel):
    model_config = ConfigDict(extra="ignore")

    schemaVersion: Literal[1]
    robotId: str = Field(min_length=1, max_length=128)
    timestamp: datetime
    data: RosTelemetryData

    @field_validator("timestamp")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp 必须包含时区")
        return value


class ManualCommandRequest(BaseModel):
    robotId: RobotId
    command: Literal["前进", "后退", "左转", "右转", "停止"]
    speed: float = 0.0
    speedGear: str | None = None


class ModeCommandRequest(BaseModel):
    robotId: RobotId
    mode: Literal["手动", "自动"]


class LockCommandRequest(BaseModel):
    robotId: RobotId
    unlocked: bool


class RobotCommandRequest(BaseModel):
    robotId: RobotId


class ElectromagneticFixRequest(BaseModel):
    robotId: RobotId
    enabled: StrictBool


class NavigationStartRequest(BaseModel):
    robotId: RobotId
    goals: list[GoalPoint]


class ParametersUpdateRequest(BaseModel):
    parameters: list[Parameter]
    robotId: RobotId


class WsMessage(BaseModel):
    type: str
    data: object

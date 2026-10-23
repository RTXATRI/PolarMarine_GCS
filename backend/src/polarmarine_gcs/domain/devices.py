from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .common import StableCode, utc_now


class DeviceCategory(StableCode):
    AERIAL = "aerial"
    SURFACE = "surface"
    STATION = "station"
    GENERIC = "generic"


class Capability(StableCode):
    TELEMETRY = "telemetry.read"
    POSITION = "telemetry.position"
    BATTERY = "telemetry.battery"
    MANUAL_CONTROL = "command.manual_control"
    MODE_CONTROL = "command.mode_control"
    ARM = "command.arm"
    EMERGENCY_STOP = "command.emergency_stop"
    WAYPOINT_MISSION = "mission.waypoint"
    ROUTE_MISSION = "mission.route"
    RETURN_HOME = "mission.return_home"
    PARAMETERS_READ = "parameters.read"
    PARAMETERS_WRITE = "parameters.write"
    UVC_MEDIA = "media.uvc"
    DOCK_CHARGE = "dock.charge"
    WASTE_COLLECTION = "payload.waste_collection"
    ELECTROMAGNETIC_FIX = "payload.electromagnetic_fix"


class ParameterValueType(StableCode):
    NUMBER = "number"
    INTEGER = "integer"
    BOOLEAN = "boolean"
    STRING = "string"
    ENUM = "enum"


@dataclass(frozen=True, slots=True)
class ParameterDefinition:
    key: str
    display_name: str
    value_type: ParameterValueType
    default_value: Any
    unit: str | None = None
    minimum: float | None = None
    maximum: float | None = None
    step: float | None = None
    description: str = ""
    enum_values: tuple[str, ...] = ()
    read_only: bool = False


@dataclass(frozen=True, slots=True)
class MediaChannelDefinition:
    id: str
    display_name: str
    role: str = "video"
    required: bool = False


@dataclass(slots=True)
class DeviceTemplate:
    id: str
    display_name: str
    category: DeviceCategory
    description: str = ""
    capabilities: frozenset[str] = field(default_factory=frozenset)
    parameters: tuple[ParameterDefinition, ...] = ()
    media_channels: tuple[MediaChannelDefinition, ...] = ()
    revision: int = 1
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)


@dataclass(slots=True)
class Device:
    id: str
    template_id: str
    display_name: str
    enabled: bool = True
    description: str = ""
    tags: tuple[str, ...] = ()
    revision: int = 1
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)

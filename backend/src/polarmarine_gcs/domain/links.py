from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .common import StableCode, utc_now


class DriverKind(StableCode):
    ROS1 = "ros1"
    ROS2 = "ros2"
    SERIAL_JSON = "serial_json"
    SIMULATOR = "simulator"


class LinkRole(StableCode):
    PRIMARY = "primary"
    AUXILIARY = "auxiliary"


class LinkSessionState(StableCode):
    STOPPED = "stopped"
    STARTING = "starting"
    HANDSHAKING = "handshaking"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    RECOVERING = "recovering"
    FAILED = "failed"


class OperationalStatus(StableCode):
    OFFLINE = "offline"
    ONLINE = "online"
    DEGRADED = "degraded"
    FAILING_OVER = "failing_over"


@dataclass(slots=True)
class LinkProfile:
    id: str
    device_id: str
    display_name: str
    driver: DriverKind
    role: LinkRole
    priority: int
    config: dict[str, Any]
    enabled: bool = True
    revision: int = 1
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)


@dataclass(slots=True)
class LinkSession:
    link_id: str
    device_id: str
    driver: DriverKind
    state: LinkSessionState = LinkSessionState.STOPPED
    capabilities: frozenset[str] = field(default_factory=frozenset)
    started_at: datetime | None = None
    healthy_since: datetime | None = None
    last_heartbeat_at: datetime | None = None
    latency_ms: float | None = None
    packet_loss_percent: float | None = None
    debug_available: bool = False
    error_code: str | None = None
    error_message: str | None = None
    revision: int = 0


@dataclass(frozen=True, slots=True)
class DeviceOperationalState:
    device_id: str
    status: OperationalStatus
    active_link_id: str | None
    healthy_link_ids: tuple[str, ...]
    last_failover_at: datetime | None
    revision: int

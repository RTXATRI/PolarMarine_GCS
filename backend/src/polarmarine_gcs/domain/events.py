from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .common import StableCode, new_id, utc_now


class AlarmSeverity(StableCode):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass(slots=True)
class SystemEvent:
    type: str
    aggregate_type: str
    aggregate_id: str
    aggregate_revision: int
    payload: dict[str, Any]
    id: str = field(default_factory=new_id)
    occurred_at: datetime = field(default_factory=utc_now)
    cursor: int | None = None


@dataclass(slots=True)
class Alarm:
    id: str
    code: str
    severity: AlarmSeverity
    message: str
    device_id: str | None = None
    acknowledged: bool = False
    created_at: datetime = field(default_factory=utc_now)
    acknowledged_at: datetime | None = None
    revision: int = 1

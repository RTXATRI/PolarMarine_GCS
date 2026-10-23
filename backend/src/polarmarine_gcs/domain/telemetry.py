from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .common import StableCode, utc_now


class TelemetryQuality(StableCode):
    VALID = "valid"
    STALE = "stale"
    INVALID = "invalid"
    UNKNOWN = "unknown"
    SIMULATED = "simulated"


@dataclass(frozen=True, slots=True)
class TelemetryValue:
    value: Any
    source_link_id: str
    collected_at: datetime
    received_at: datetime
    quality: TelemetryQuality
    unit: str | None = None


@dataclass(slots=True)
class TelemetrySnapshot:
    device_id: str
    fields: dict[str, TelemetryValue] = field(default_factory=dict)
    revision: int = 0
    updated_at: datetime = field(default_factory=utc_now)

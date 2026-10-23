from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from .common import StableCode, utc_now


class RecordingStatus(StableCode):
    ACTIVE = "active"
    COMPLETE = "complete"
    INTERRUPTED = "interrupted"


@dataclass(slots=True)
class Recording:
    id: str
    mission_run_id: str
    path: str
    status: RecordingStatus
    size_bytes: int = 0
    started_at: datetime = field(default_factory=utc_now)
    ended_at: datetime | None = None

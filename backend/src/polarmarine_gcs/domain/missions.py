from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .common import StableCode, utc_now


class MissionPlanStatus(StableCode):
    DRAFT = "draft"
    VALID = "valid"
    ARCHIVED = "archived"


class MissionRunStatus(StableCode):
    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class MissionStep:
    id: str
    step_type: str
    device_id: str
    depends_on: tuple[str, ...] = ()
    timeout_seconds: float = 60.0
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class MissionPlan:
    id: str
    name: str
    version: int
    status: MissionPlanStatus
    steps: tuple[MissionStep, ...]
    description: str = ""
    revision: int = 1
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)


@dataclass(slots=True)
class MissionRun:
    id: str
    mission_plan_id: str
    mission_plan_version: int
    status: MissionRunStatus
    step_states: dict[str, str] = field(default_factory=dict)
    plan_steps: tuple[MissionStep, ...] = ()
    started_at: datetime | None = None
    ended_at: datetime | None = None
    revision: int = 1
    created_at: datetime = field(default_factory=utc_now)

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .common import StableCode, utc_now


class CommandStatus(StableCode):
    QUEUED = "queued"
    DISPATCHED = "dispatched"
    ACCEPTED = "accepted"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    REJECTED = "rejected"
    TIMED_OUT = "timed_out"
    CANCELLED = "cancelled"
    STATE_UNCONFIRMED = "state_unconfirmed"


TERMINAL_COMMAND_STATUSES = frozenset(
    {
        CommandStatus.COMPLETED,
        CommandStatus.REJECTED,
        CommandStatus.TIMED_OUT,
        CommandStatus.CANCELLED,
        CommandStatus.STATE_UNCONFIRMED,
    }
)


class CommandType(StableCode):
    MANUAL_CONTROL = "manual_control"
    SET_MODE = "set_mode"
    SET_ARMED = "set_armed"
    EMERGENCY_STOP = "emergency_stop"
    RETURN_HOME = "return_home"
    START_MISSION = "start_mission"
    PAUSE_MISSION = "pause_mission"
    RESUME_MISSION = "resume_mission"
    CANCEL_MISSION = "cancel_mission"
    READ_PARAMETERS = "read_parameters"
    WRITE_PARAMETERS = "write_parameters"
    CUSTOM_ACTION = "custom_action"


COMMAND_CAPABILITIES: dict[CommandType, str] = {
    CommandType.MANUAL_CONTROL: "command.manual_control",
    CommandType.SET_MODE: "command.mode_control",
    CommandType.SET_ARMED: "command.arm",
    CommandType.EMERGENCY_STOP: "command.emergency_stop",
    CommandType.RETURN_HOME: "mission.return_home",
    CommandType.START_MISSION: "mission.route",
    CommandType.PAUSE_MISSION: "mission.route",
    CommandType.RESUME_MISSION: "mission.route",
    CommandType.CANCEL_MISSION: "mission.route",
    CommandType.READ_PARAMETERS: "parameters.read",
    CommandType.WRITE_PARAMETERS: "parameters.write",
    CommandType.CUSTOM_ACTION: "custom_action",
}


@dataclass(slots=True)
class Command:
    id: str
    device_id: str
    command_type: CommandType
    payload: dict[str, Any]
    status: CommandStatus = CommandStatus.QUEUED
    progress: float | None = None
    result: dict[str, Any] = field(default_factory=dict)
    routed_link_ids: tuple[str, ...] = ()
    link_acknowledgements: dict[str, str] = field(default_factory=dict)
    idempotency_key: str | None = None
    reason_code: str | None = None
    reason_message: str | None = None
    requires_state_confirmation: bool = True
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    expires_at: datetime | None = None
    revision: int = 1

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from app.models.schemas import RosTelemetryEnvelope
from app.services.positioning import normalize_gps_pair


class RosMessageError(ValueError):
    def __init__(self, code: str, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable


@dataclass(frozen=True)
class ParsedRosState:
    envelope: RosTelemetryEnvelope
    gps_fallback: bool


def parse_ros_state_message(message: dict[str, Any], expected_robot_id: str) -> ParsedRosState:
    """Decode and validate the versioned ``/gcs/robot_state`` envelope."""

    payload: object = message
    if isinstance(message.get("data"), str):
        try:
            payload = json.loads(message["data"])
        except json.JSONDecodeError as exc:
            raise RosMessageError("ROS_MESSAGE_INVALID", f"状态消息不是合法 JSON：{exc.msg}") from exc

    if not isinstance(payload, dict):
        raise RosMessageError("ROS_MESSAGE_INVALID", "状态消息必须是 JSON 对象")

    gps_fallback = False
    telemetry_data = payload.get("data")
    if isinstance(telemetry_data, dict):
        normalized_data = dict(telemetry_data)
        lat, lon, gps_fallback = normalize_gps_pair(
            normalized_data.get("lat"),
            normalized_data.get("lon"),
            expected_robot_id,
        )
        normalized_data["lat"] = lat
        normalized_data["lon"] = lon
        payload = {**payload, "data": normalized_data}

    try:
        envelope = RosTelemetryEnvelope.model_validate(payload)
    except ValidationError as exc:
        first = exc.errors(include_url=False)[0]
        location = ".".join(str(item) for item in first.get("loc", ()))
        reason = first.get("msg", "字段校验失败")
        detail = f"{location}: {reason}" if location else str(reason)
        raise RosMessageError("ROS_MESSAGE_INVALID", f"状态消息格式错误：{detail}") from exc

    if envelope.robotId != expected_robot_id:
        raise RosMessageError(
            "ROBOT_ID_MISMATCH",
            f"端点上报设备 {envelope.robotId}，与所选设备 {expected_robot_id} 不一致",
        )
    if not envelope.data.sourceConnected:
        raise RosMessageError(
            "MAVROS_DATA_UNAVAILABLE",
            "ROSBridge 已连接，但机载 MAVROS 当前未连接 PX4",
            retryable=True,
        )
    return ParsedRosState(envelope=envelope, gps_fallback=gps_fallback)


def manual_command_to_ros(robot_id: str, command: str, speed: float) -> dict[str, Any]:
    """Legacy serializer retained for compatibility; it is not published."""

    return {"robot_id": robot_id, "command": command, "speed": speed}


def mission_command_to_ros(robot_id: str, action: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Legacy serializer retained for compatibility; it is not published."""

    return {"robot_id": robot_id, "action": action, "payload": payload or {}}

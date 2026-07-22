import asyncio
from collections.abc import Iterator
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import pytest

from app.core.config import get_settings
from app.services import rosbridge as rosbridge_module
from app.services.state import state_service


def make_ros_envelope(robot_id: str = "Hexa-UAV", **overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "sourceConnected": True,
        "battery": 82,
        "mode": "手动",
        "px4Mode": "POSCTL",
        "missionStatus": "巡航中",
        "linkStatus": "延迟高",
        "latencyMs": 999,
        "packetLoss": 25,
        "rssi": -90,
        "lat": 30.2755,
        "lon": 120.157,
        "altitude": 12.4,
        "speed": 0.35,
        "heading": 86.2,
        "unlocked": False,
        "alarm": None,
    }
    data.update(overrides)
    return {
        "schemaVersion": 1,
        "robotId": robot_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": data,
    }


class FakeRosbridgeSession:
    def __init__(self, behavior: dict[str, Any] | BaseException | None) -> None:
        self.behavior = behavior
        self.connected = False
        self.close_count = 0
        self.on_message: Any = None
        self.on_close: Any = None
        self.published_bools: list[tuple[str, bool]] = []
        self.publish_error: BaseException | None = None
        self.on_publish_bool: Any = None

    async def open(self, on_message: Any, on_close: Any) -> None:
        self.on_message = on_message
        self.on_close = on_close
        if isinstance(self.behavior, BaseException):
            raise self.behavior
        self.connected = True
        if self.behavior is not None:
            self.emit_raw(self._as_ros_message(self.behavior))
            await asyncio.sleep(0)

    async def close(self) -> None:
        self.close_count += 1
        self.connected = False

    async def publish_bool(self, topic_name: str, value: bool) -> None:
        if self.publish_error is not None:
            raise self.publish_error
        self.published_bools.append((topic_name, bool(value)))
        if self.on_publish_bool is not None:
            self.on_publish_bool(topic_name, bool(value))
        await asyncio.sleep(0)

    def emit_envelope(self, envelope: dict[str, Any]) -> None:
        self.emit_raw({"data": json.dumps(envelope, ensure_ascii=False)})

    def emit_raw(self, message: dict[str, Any]) -> None:
        if self.on_message:
            self.on_message(message)

    def drop(self, reason: str = "pytest connection drop") -> None:
        self.connected = False
        if self.on_close:
            self.on_close(reason)

    @staticmethod
    def _as_ros_message(value: dict[str, Any]) -> dict[str, Any]:
        if "schemaVersion" in value:
            return {"data": json.dumps(value, ensure_ascii=False)}
        return value


class FakeRosbridgeFactory:
    def __init__(self) -> None:
        self.behaviors: dict[tuple[str, int], list[dict[str, Any] | BaseException | None]] = {}
        self.sessions: list[FakeRosbridgeSession] = []
        self.endpoints: list[tuple[str, int, str, float]] = []

    def configure(self, host: str, port: int, *behaviors: dict[str, Any] | BaseException | None) -> None:
        self.behaviors[(host, port)] = list(behaviors)

    def __call__(self, host: str, port: int, topic: str, timeout: float) -> FakeRosbridgeSession:
        queue = self.behaviors.get((host, port))
        behavior = queue.pop(0) if queue else make_ros_envelope()
        session = FakeRosbridgeSession(behavior)
        self.sessions.append(session)
        self.endpoints.append((host, port, topic, timeout))
        return session


@pytest.fixture
def fake_rosbridge_factory() -> FakeRosbridgeFactory:
    return FakeRosbridgeFactory()


@pytest.fixture(autouse=True)
def isolated_backend_runtime(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fake_rosbridge_factory: FakeRosbridgeFactory,
) -> Iterator[Path]:
    """Keep singleton state and persisted profiles isolated for every test."""

    profile_path = tmp_path / "runtime" / "device_profiles.json"
    monkeypatch.setenv("DEVICE_PROFILES_PATH", str(profile_path))
    monkeypatch.setenv("MOCK_SIMULATOR_ENABLED", "false")
    monkeypatch.setenv("SERIAL_MONITOR_INTERVAL_SEC", "60")
    monkeypatch.setattr(rosbridge_module, "create_rosbridge_session", fake_rosbridge_factory)
    get_settings.cache_clear()
    state_service.reset()

    yield profile_path

    get_settings.cache_clear()
    state_service.reset()

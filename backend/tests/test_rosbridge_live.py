from __future__ import annotations

import time
from typing import Any, Callable

import pytest
from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.main import create_app
from app.models.schemas import NetworkConnectionProfile, RosTelemetryData
from app.services.state import StateService
from tests.conftest import FakeRosbridgeFactory, make_ros_envelope


ROBOT_ID = "Hexa-UAV"
OTHER_ROBOT_ID = "Quadri-UAV"
PROFILE = {"method": "network", "host": "192.168.1.249", "port": 9090}
REAL_FIELDS = (
    "battery",
    "mode",
    "px4Mode",
    "linkStatus",
    "latencyMs",
    "packetLoss",
    "rssi",
    "position",
    "altitude",
    "speed",
    "heading",
    "unlocked",
    "alarm",
    "lastCommAt",
    "trail",
)


def wait_until(predicate: Callable[[], bool], timeout: float = 2.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("condition was not reached before timeout")


@pytest.mark.parametrize(
    ("behavior", "expected_code"),
    [
        (make_ros_envelope("unexpected-robot"), "ROBOT_ID_MISMATCH"),
        (make_ros_envelope(sourceConnected=False), "MAVROS_DATA_UNAVAILABLE"),
        (make_ros_envelope(battery=101), "ROS_MESSAGE_INVALID"),
        ({"data": "{not-json"}, "ROS_MESSAGE_INVALID"),
    ],
)
def test_first_packet_must_match_the_versioned_mavros_contract(
    fake_rosbridge_factory: FakeRosbridgeFactory,
    behavior: dict[str, Any],
    expected_code: str,
) -> None:
    fake_rosbridge_factory.configure("192.168.1.249", 9090, behavior)

    with TestClient(create_app()) as client:
        response = client.post(f"/api/robots/{ROBOT_ID}/connection", json=PROFILE)

        assert response.status_code == 409
        assert response.json()["detail"]["code"] == expected_code
        failed = response.json()["detail"]["robot"]
        assert failed["connection"]["state"] == "error"
        assert failed["connection"]["dataMode"] == "none"
        assert failed["battery"] is None
        assert fake_rosbridge_factory.sessions[0].close_count >= 1


def test_connection_fails_when_rosbridge_has_no_valid_first_packet(
    monkeypatch: pytest.MonkeyPatch,
    fake_rosbridge_factory: FakeRosbridgeFactory,
) -> None:
    monkeypatch.setenv("ROSBRIDGE_FIRST_MESSAGE_TIMEOUT_SEC", "0.1")
    get_settings.cache_clear()
    fake_rosbridge_factory.configure("192.168.1.249", 9090, None)

    with TestClient(create_app()) as client:
        response = client.post(f"/api/robots/{ROBOT_ID}/connection", json=PROFILE)

        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "ROSBRIDGE_TOPIC_TIMEOUT"


def test_two_devices_have_independent_sessions_and_cannot_share_an_endpoint(
    fake_rosbridge_factory: FakeRosbridgeFactory,
) -> None:
    fake_rosbridge_factory.configure("192.168.1.250", 9090, make_ros_envelope(OTHER_ROBOT_ID))

    with TestClient(create_app()) as client:
        first = client.post(f"/api/robots/{ROBOT_ID}/connection", json=PROFILE)
        conflict = client.post(f"/api/robots/{OTHER_ROBOT_ID}/connection", json=PROFILE)
        second = client.post(
            f"/api/robots/{OTHER_ROBOT_ID}/connection",
            json={"method": "network", "host": "192.168.1.250", "port": 9090},
        )

        assert first.status_code == 200
        assert conflict.status_code == 409
        assert conflict.json()["detail"]["code"] == "NETWORK_ENDPOINT_IN_USE"
        assert second.status_code == 200
        assert client.get("/api/health").json()["rosbridgeConnectedCount"] == 2

        client.delete(f"/api/robots/{ROBOT_ID}/connection")
        assert client.get(f"/api/robots/{OTHER_ROBOT_ID}").json()["connection"]["state"] == "connected"
        assert fake_rosbridge_factory.sessions[1].connected is True


def test_live_updates_are_strict_and_do_not_accept_invalid_followup_packets(
    fake_rosbridge_factory: FakeRosbridgeFactory,
) -> None:
    with TestClient(create_app()) as client:
        connected = client.post(f"/api/robots/{ROBOT_ID}/connection", json=PROFILE).json()
        session = fake_rosbridge_factory.sessions[0]
        session.emit_envelope(
            make_ros_envelope(
                battery=64,
                px4Mode="ALTCTL",
                mode="自动",
                lat=30.3,
                lon=120.2,
                speed=1.25,
                heading=120.0,
                unlocked=True,
            )
        )
        wait_until(lambda: client.get(f"/api/robots/{ROBOT_ID}").json()["battery"] == 64)
        updated = client.get(f"/api/robots/{ROBOT_ID}").json()

        assert updated["px4Mode"] == "ALTCTL"
        assert updated["position"] == {"lat": 30.3, "lon": 120.2}
        assert updated["missionStatus"] == "空闲"
        assert updated["latencyMs"] is None
        assert updated["packetLoss"] is None
        assert updated["rssi"] is None

        session.emit_envelope(make_ros_envelope(battery=120))
        time.sleep(0.03)
        after_invalid = client.get(f"/api/robots/{ROBOT_ID}").json()
        assert after_invalid["battery"] == 64
        assert after_invalid["connection"]["state"] == "connected"
        assert after_invalid["lastCommAt"] == updated["lastCommAt"]
        assert connected["missionStatus"] == "空闲"


def test_valid_followup_telemetry_is_pushed_immediately_over_websocket(
    fake_rosbridge_factory: FakeRosbridgeFactory,
) -> None:
    with TestClient(create_app()) as client:
        with client.websocket_connect("/ws/telemetry") as websocket:
            for _ in range(3):
                websocket.receive_json()
            assert client.post(f"/api/robots/{ROBOT_ID}/connection", json=PROFILE).status_code == 200
            for _ in range(6):
                websocket.receive_json()

            fake_rosbridge_factory.sessions[0].emit_envelope(make_ros_envelope(battery=59))
            message = websocket.receive_json()

            assert message["type"] == "robot_state"
            robot = next(item for item in message["data"] if item["id"] == ROBOT_ID)
            assert robot["battery"] == 59
            assert robot["connection"]["dataMode"] == "live"


def test_virtual_operations_never_overwrite_live_mavros_fields() -> None:
    with TestClient(create_app()) as client:
        connected = client.post(f"/api/robots/{ROBOT_ID}/connection", json=PROFILE).json()
        baseline = {field: connected[field] for field in REAL_FIELDS}

        operations = [
            ("/api/commands/manual", {"robotId": ROBOT_ID, "command": "前进", "speed": 1.0}),
            ("/api/commands/mode", {"robotId": ROBOT_ID, "mode": "自动"}),
            ("/api/commands/lock", {"robotId": ROBOT_ID, "unlocked": True}),
            ("/api/commands/emergency-stop", {"robotId": ROBOT_ID}),
        ]
        for path, payload in operations:
            response = client.post(path, json=payload)
            assert response.status_code == 200
            assert {field: response.json()[field] for field in REAL_FIELDS} == baseline

        task = client.post(
            "/api/commands/navigation/start",
            json={
                "robotId": ROBOT_ID,
                "goals": [{"id": "goal-1", "lat": 30.1, "lon": 120.1, "speed": 0.5}],
            },
        )
        assert task.status_code == 200
        assert task.json()["missionStatus"] == "正在前往目标点"
        assert task.json()["navState"] == "navigating"
        assert {field: task.json()[field] for field in REAL_FIELDS} == baseline
        assert any("未发送飞控" in entry["content"] for entry in client.get("/api/logs").json())


def test_unexpected_drop_recovers_with_a_new_session(
    monkeypatch: pytest.MonkeyPatch,
    fake_rosbridge_factory: FakeRosbridgeFactory,
) -> None:
    monkeypatch.setenv("ROSBRIDGE_RECONNECT_DELAYS_SEC", "0.01,0.01,0.01")
    get_settings.cache_clear()
    fake_rosbridge_factory.configure(
        "192.168.1.249",
        9090,
        make_ros_envelope(),
        make_ros_envelope(battery=71, px4Mode="AUTO.LOITER"),
    )

    with TestClient(create_app()) as client:
        client.post(f"/api/robots/{ROBOT_ID}/connection", json=PROFILE)
        fake_rosbridge_factory.sessions[0].drop("network cable removed")

        wait_until(lambda: len(fake_rosbridge_factory.sessions) >= 2)
        wait_until(lambda: client.get(f"/api/robots/{ROBOT_ID}").json()["battery"] == 71)
        recovered = client.get(f"/api/robots/{ROBOT_ID}").json()
        assert recovered["connection"]["state"] == "connected"
        assert recovered["connection"]["dataMode"] == "live"
        assert recovered["px4Mode"] == "AUTO.LOITER"
        assert client.get("/api/alarms").json() == []


def test_reconnect_exhaustion_raises_one_alarm_and_keeps_last_comm(
    monkeypatch: pytest.MonkeyPatch,
    fake_rosbridge_factory: FakeRosbridgeFactory,
) -> None:
    monkeypatch.setenv("ROSBRIDGE_RECONNECT_DELAYS_SEC", "0.01,0.01,0.01")
    get_settings.cache_clear()
    fake_rosbridge_factory.configure(
        "192.168.1.249",
        9090,
        make_ros_envelope(),
        ConnectionRefusedError("refused-1"),
        ConnectionRefusedError("refused-2"),
        ConnectionRefusedError("refused-3"),
    )

    with TestClient(create_app()) as client:
        connected = client.post(f"/api/robots/{ROBOT_ID}/connection", json=PROFILE).json()
        last_comm = connected["lastCommAt"]
        fake_rosbridge_factory.sessions[0].drop()

        wait_until(lambda: client.get(f"/api/robots/{ROBOT_ID}").json()["connection"]["state"] == "error")
        failed = client.get(f"/api/robots/{ROBOT_ID}").json()
        assert failed["connection"]["error"]["code"] == "ROSBRIDGE_CONNECTION_REFUSED"
        assert failed["lastCommAt"] == last_comm
        assert failed["battery"] is None
        assert len(client.get("/api/alarms").json()) == 1
        time.sleep(0.05)
        assert len(client.get("/api/alarms").json()) == 1


def test_active_disconnect_cancels_pending_reconnect_without_alarm(
    monkeypatch: pytest.MonkeyPatch,
    fake_rosbridge_factory: FakeRosbridgeFactory,
) -> None:
    monkeypatch.setenv("ROSBRIDGE_RECONNECT_DELAYS_SEC", "0.2,0.2,0.2")
    get_settings.cache_clear()

    with TestClient(create_app()) as client:
        client.post(f"/api/robots/{ROBOT_ID}/connection", json=PROFILE)
        fake_rosbridge_factory.sessions[0].drop()
        wait_until(lambda: client.get(f"/api/robots/{ROBOT_ID}").json()["connection"]["state"] == "connecting")

        response = client.delete(f"/api/robots/{ROBOT_ID}/connection")
        assert response.status_code == 200
        time.sleep(0.25)
        assert client.get(f"/api/robots/{ROBOT_ID}").json()["connection"]["state"] == "disconnected"
        assert client.get("/api/alarms").json() == []
        assert len(fake_rosbridge_factory.sessions) == 1


def test_virtual_route_progresses_without_moving_live_position(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VIRTUAL_TASK_STEP_SEC", "0.1")
    monkeypatch.setenv("VIRTUAL_TASK_TICK_SEC", "0.05")
    get_settings.cache_clear()

    with TestClient(create_app()) as client:
        connected = client.post(f"/api/robots/{ROBOT_ID}/connection", json=PROFILE).json()
        original_position = connected["position"]
        original_mode = connected["mode"]
        start = client.post(
            "/api/commands/navigation/start",
            json={
                "robotId": ROBOT_ID,
                "goals": [
                    {"id": "a", "lat": 31.0, "lon": 121.0, "speed": 0.5},
                    {"id": "b", "lat": 32.0, "lon": 122.0, "speed": 0.5},
                ],
            },
        )
        assert start.status_code == 200

        wait_until(lambda: client.get(f"/api/robots/{ROBOT_ID}").json()["navState"] == "idle")
        completed = client.get(f"/api/robots/{ROBOT_ID}").json()
        assert completed["navGoalIndex"] == 2
        assert completed["missionStatus"] == "空闲"
        assert completed["position"] == original_position
        assert completed["mode"] == original_mode


def test_trail_sampling_is_limited_to_one_point_per_second_and_one_hundred_points() -> None:
    state = StateService()
    profile = NetworkConnectionProfile(method="network", host="192.168.1.249", port=9090)
    state.mark_connected(ROBOT_ID, profile, "live", "virtual")
    data = RosTelemetryData(
        sourceConnected=True,
        lat=30.0,
        lon=120.0,
        battery=50,
        mode="手动",
        px4Mode="POSCTL",
        speed=0.0,
        heading=0.0,
        unlocked=False,
    )

    state.apply_live_telemetry(ROBOT_ID, data, 100.1)
    state.apply_live_telemetry(ROBOT_ID, data.model_copy(update={"lat": 30.1}), 100.9)
    assert len(state.get_robot(ROBOT_ID).trail) == 1  # type: ignore[union-attr]

    for second in range(101, 205):
        state.apply_live_telemetry(ROBOT_ID, data, float(second))
    robot = state.get_robot(ROBOT_ID)
    assert robot is not None
    assert len(robot.trail) == 100


def test_application_shutdown_closes_live_sessions(fake_rosbridge_factory: FakeRosbridgeFactory) -> None:
    with TestClient(create_app()) as client:
        assert client.post(f"/api/robots/{ROBOT_ID}/connection", json=PROFILE).status_code == 200
        session = fake_rosbridge_factory.sessions[0]
        assert session.connected is True

    assert session.connected is False
    assert session.close_count >= 1

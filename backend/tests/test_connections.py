import json
import socket
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.core.config import get_settings
from app.services import connections as connections_module
from app.services.state import state_service


ROBOT_ID = "Hexa-UAV"
OTHER_ROBOT_ID = "Quadri-UAV"
RUNTIME_NULL_FIELDS = (
    "link",
    "battery",
    "mode",
    "px4Mode",
    "missionStatus",
    "linkStatus",
    "latencyMs",
    "packetLoss",
    "rssi",
    "position",
    "altitude",
    "speed",
    "heading",
    "alarm",
    "lastCommAt",
    "unlocked",
    "homePosition",
    "wobbleAnchor",
)


def assert_runtime_unknown(robot: dict[str, Any], *, allow_connection_label: bool = False) -> None:
    for field in RUNTIME_NULL_FIELDS:
        if allow_connection_label and field == "link":
            continue
        assert robot[field] is None, f"expected {field} to be unknown"
    assert robot["trail"] == []
    assert robot["navGoals"] == []
    assert robot["navState"] == "idle"
    assert robot["navGoalIndex"] == 0


def robot_from_snapshot(message: dict[str, Any], robot_id: str = ROBOT_ID) -> dict[str, Any]:
    return next(robot for robot in message["data"] if robot["id"] == robot_id)


def test_startup_has_five_disconnected_robots_with_unknown_runtime() -> None:
    with TestClient(create_app()) as client:
        response = client.get("/api/robots")

        assert response.status_code == 200
        robots = response.json()
        assert len(robots) == 5
        for robot in robots:
            assert robot["connection"] == {
                "state": "disconnected",
                "activeMethod": None,
                "endpoint": None,
                "dataMode": "none",
                "commandMode": "none",
                "connectedAt": None,
                "error": None,
            }
            assert robot["connectionProfile"] is None
            assert robot["online"] is False
            assert_runtime_unknown(robot)

        assert client.get("/api/alarms").json() == []


def test_network_connection_waits_for_real_telemetry_and_disconnects_cleanly() -> None:
    profile = {"method": "network", "host": "203.0.113.77", "port": 54321}

    with TestClient(create_app()) as client:
        response = client.post(f"/api/robots/{ROBOT_ID}/connection", json=profile)

        assert response.status_code == 200
        connected = response.json()
        assert connected["connectionProfile"] == profile
        assert connected["connection"] == {
            "state": "connected",
            "activeMethod": "network",
            "endpoint": "203.0.113.77:54321",
            "dataMode": "live",
            "commandMode": "virtual",
            "connectedAt": connected["connection"]["connectedAt"],
            "error": None,
        }
        assert connected["connection"]["connectedAt"] is not None
        assert connected["online"] is True
        assert connected["battery"] == 82
        assert connected["position"] == {"lat": 30.2755, "lon": 120.157}
        assert connected["mode"] == "手动"
        assert connected["px4Mode"] == "POSCTL"
        assert connected["missionStatus"] == "空闲"
        assert connected["linkStatus"] == "正常"
        assert connected["latencyMs"] is None
        assert connected["packetLoss"] is None
        assert connected["rssi"] is None
        assert connected["lastCommAt"] is not None

        untouched = client.get(f"/api/robots/{OTHER_ROBOT_ID}").json()
        assert untouched["connection"]["state"] == "disconnected"
        assert_runtime_unknown(untouched)

        disconnected_response = client.delete(f"/api/robots/{ROBOT_ID}/connection")
        assert disconnected_response.status_code == 200
        disconnected = disconnected_response.json()
        assert disconnected["connectionProfile"] == profile
        assert disconnected["connection"]["state"] == "disconnected"
        assert disconnected["online"] is False
        assert_runtime_unknown(disconnected)


@pytest.mark.parametrize(
    "profile",
    [
        {"method": "network", "host": "not-an-ip", "port": 9090},
        {"method": "network", "host": "192.168.1.2", "port": 0},
        {"method": "network", "host": "192.168.1.2", "port": 65536},
    ],
)
def test_network_connection_rejects_invalid_endpoint(profile: dict[str, Any]) -> None:
    with TestClient(create_app()) as client:
        response = client.post(f"/api/robots/{ROBOT_ID}/connection", json=profile)

        assert response.status_code == 422
        robot = client.get(f"/api/robots/{ROBOT_ID}").json()
        assert robot["connection"]["state"] == "disconnected"
        assert robot["connectionProfile"] is None


@pytest.mark.parametrize(
    ("path", "payload"),
    [
        ("/api/commands/manual", {"robotId": ROBOT_ID, "command": "停止", "speed": 0}),
        ("/api/commands/mode", {"robotId": ROBOT_ID, "mode": "手动"}),
        ("/api/commands/lock", {"robotId": ROBOT_ID, "unlocked": True}),
        ("/api/commands/emergency-stop", {"robotId": ROBOT_ID}),
        (
            "/api/commands/navigation/start",
            {"robotId": ROBOT_ID, "goals": [{"id": "goal-1", "lat": 30.1, "lon": 120.1, "speed": 0.5}]},
        ),
        ("/api/commands/navigation/pause", {"robotId": ROBOT_ID}),
        ("/api/commands/navigation/resume", {"robotId": ROBOT_ID}),
        ("/api/commands/navigation/stop", {"robotId": ROBOT_ID}),
        ("/api/commands/navigation/return-home", {"robotId": ROBOT_ID}),
    ],
)
def test_commands_reject_disconnected_robot_without_mutating_it(path: str, payload: dict[str, Any]) -> None:
    with TestClient(create_app()) as client:
        before = client.get(f"/api/robots/{ROBOT_ID}").json()

        response = client.post(path, json=payload)

        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "DEVICE_NOT_CONNECTED"
        assert client.get(f"/api/robots/{ROBOT_ID}").json() == before


def test_parameter_requests_require_a_usable_device_channel() -> None:
    before = state_service.list_parameters()

    with TestClient(create_app()) as client:
        read = client.get("/api/parameters", params={"robotId": ROBOT_ID})
        write = client.put(
            "/api/parameters",
            json={
                "robotId": ROBOT_ID,
                "parameters": [item.model_dump(mode="json") for item in before],
            },
        )

        assert read.status_code == 409
        assert read.json()["detail"]["code"] == "DEVICE_NOT_CONNECTED"
        assert write.status_code == 409
        assert write.json()["detail"]["code"] == "DEVICE_NOT_CONNECTED"
        assert state_service.list_parameters() == before


class FakeSerialHandle:
    def __init__(self, **settings: Any) -> None:
        self.settings = settings
        self.is_open = True
        self.close_count = 0

    def close(self) -> None:
        self.close_count += 1
        self.is_open = False


def install_fake_serial_port(
    monkeypatch: pytest.MonkeyPatch,
    factory: Any,
    port: str = "COM_TEST",
) -> None:
    fake_port = SimpleNamespace(
        device=port,
        description="pytest virtual serial port",
        manufacturer="pytest",
        hwid="TEST:0001",
    )
    fake_serial_module = SimpleNamespace(
        Serial=factory,
        SerialException=OSError,
        EIGHTBITS=8,
        PARITY_NONE="N",
        STOPBITS_ONE=1,
    )
    monkeypatch.setattr(connections_module, "list_ports", SimpleNamespace(comports=lambda: [fake_port]))
    monkeypatch.setattr(connections_module, "serial_module", fake_serial_module)


def test_serial_connection_opens_holds_and_releases_port(monkeypatch: pytest.MonkeyPatch) -> None:
    handles: list[FakeSerialHandle] = []

    def serial_factory(**settings: Any) -> FakeSerialHandle:
        handle = FakeSerialHandle(**settings)
        handles.append(handle)
        return handle

    install_fake_serial_port(monkeypatch, serial_factory)
    profile = {"method": "serial", "port": "COM_TEST", "baudRate": 115200}

    with TestClient(create_app()) as client:
        response = client.post(f"/api/robots/{ROBOT_ID}/connection", json=profile)

        assert response.status_code == 200
        connected = response.json()
        assert connected["connection"]["state"] == "connected"
        assert connected["connection"]["dataMode"] == "none"
        assert connected["connection"]["activeMethod"] == "serial"
        assert connected["online"] is True
        assert_runtime_unknown(connected, allow_connection_label=True)
        assert connected["link"] is not None
        assert handles[0].is_open is True
        assert handles[0].settings["port"] == "COM_TEST"
        assert handles[0].settings["baudrate"] == 115200

        before_command = client.get(f"/api/robots/{ROBOT_ID}").json()
        unavailable = client.post("/api/commands/emergency-stop", json={"robotId": ROBOT_ID})
        assert unavailable.status_code == 409
        assert unavailable.json()["detail"]["code"] == "DATA_CHANNEL_UNAVAILABLE"
        assert client.get(f"/api/robots/{ROBOT_ID}").json() == before_command

        conflict = client.post(f"/api/robots/{OTHER_ROBOT_ID}/connection", json=profile)
        assert conflict.status_code == 409
        assert conflict.json()["detail"]["code"] == "SERIAL_PORT_IN_USE"
        assert conflict.json()["detail"]["robot"]["connection"]["state"] == "error"

        disconnected = client.delete(f"/api/robots/{ROBOT_ID}/connection")
        assert disconnected.status_code == 200
        assert handles[0].is_open is False
        assert handles[0].close_count == 1

        retried = client.post(f"/api/robots/{OTHER_ROBOT_ID}/connection", json=profile)
        assert retried.status_code == 200
        assert len(handles) == 2
        assert handles[1].is_open is True

    assert handles[1].is_open is False
    assert handles[1].close_count == 1


def test_serial_busy_error_is_structured_and_profile_remains_retryable(
    monkeypatch: pytest.MonkeyPatch,
    isolated_backend_runtime: Path,
) -> None:
    def denied_factory(**_settings: Any) -> None:
        raise PermissionError("Access is denied")

    install_fake_serial_port(monkeypatch, denied_factory)
    profile = {"method": "serial", "port": "COM_TEST", "baudRate": 57600}

    with TestClient(create_app()) as client:
        response = client.post(f"/api/robots/{ROBOT_ID}/connection", json=profile)

        assert response.status_code == 409
        detail = response.json()["detail"]
        assert detail["code"] == "SERIAL_PORT_BUSY_OR_DENIED"
        assert detail["robot"]["connectionProfile"] == profile
        assert detail["robot"]["connection"]["state"] == "error"
        assert detail["robot"]["connection"]["error"]["code"] == "SERIAL_PORT_BUSY_OR_DENIED"
        assert_runtime_unknown(detail["robot"])

        persisted = json.loads(isolated_backend_runtime.read_text(encoding="utf-8"))
        assert persisted["profiles"][ROBOT_ID] == profile


def test_serial_not_found_does_not_invoke_factory(monkeypatch: pytest.MonkeyPatch) -> None:
    invoked = False

    def serial_factory(**_settings: Any) -> None:
        nonlocal invoked
        invoked = True
        raise AssertionError("serial factory must not run for a missing port")

    fake_serial_module = SimpleNamespace(
        Serial=serial_factory,
        SerialException=OSError,
        EIGHTBITS=8,
        PARITY_NONE="N",
        STOPBITS_ONE=1,
    )
    monkeypatch.setattr(connections_module, "list_ports", SimpleNamespace(comports=lambda: []))
    monkeypatch.setattr(connections_module, "serial_module", fake_serial_module)

    with TestClient(create_app()) as client:
        response = client.post(
            f"/api/robots/{ROBOT_ID}/connection",
            json={"method": "serial", "port": "COM_MISSING", "baudRate": 115200},
        )

        assert response.status_code == 409
        assert response.json()["detail"]["code"] == "SERIAL_PORT_NOT_FOUND"
        assert invoked is False


def test_serial_enumeration_failure_is_structured(monkeypatch: pytest.MonkeyPatch) -> None:
    def raise_enumeration_error() -> list[Any]:
        raise OSError("device enumeration failed")

    monkeypatch.setattr(
        connections_module,
        "list_ports",
        SimpleNamespace(comports=raise_enumeration_error),
    )

    with TestClient(create_app()) as client:
        response = client.get("/api/connections/serial-ports")

        assert response.status_code == 503
        assert response.json()["detail"]["code"] == "SERIAL_ENUMERATION_FAILED"


def test_serial_unplug_transitions_once_to_error_and_releases_handle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    handles: list[FakeSerialHandle] = []
    discovered: list[Any] = [
        SimpleNamespace(
            device="COM_TEST",
            description="pytest removable serial port",
            manufacturer="pytest",
            hwid="TEST:REMOVE",
        )
    ]

    def serial_factory(**settings: Any) -> FakeSerialHandle:
        handle = FakeSerialHandle(**settings)
        handles.append(handle)
        return handle

    fake_serial_module = SimpleNamespace(
        Serial=serial_factory,
        SerialException=OSError,
        EIGHTBITS=8,
        PARITY_NONE="N",
        STOPBITS_ONE=1,
    )
    monkeypatch.setattr(connections_module, "list_ports", SimpleNamespace(comports=lambda: list(discovered)))
    monkeypatch.setattr(connections_module, "serial_module", fake_serial_module)
    monkeypatch.setenv("SERIAL_MONITOR_INTERVAL_SEC", "0.05")
    get_settings.cache_clear()

    with TestClient(create_app()) as client:
        connected = client.post(
            f"/api/robots/{ROBOT_ID}/connection",
            json={"method": "serial", "port": "COM_TEST", "baudRate": 115200},
        ).json()
        connected_at = connected["connection"]["connectedAt"]
        discovered.clear()

        deadline = time.monotonic() + 1.0
        failed: dict[str, Any] | None = None
        while time.monotonic() < deadline:
            candidate = client.get(f"/api/robots/{ROBOT_ID}").json()
            if candidate["connection"]["state"] == "error":
                failed = candidate
                break
            time.sleep(0.02)

        assert failed is not None
        assert failed["connection"]["error"]["code"] == "SERIAL_CONNECTION_LOST"
        assert failed["connection"]["connectedAt"] == connected_at
        assert_runtime_unknown(failed)
        assert handles[0].is_open is False
        assert handles[0].close_count == 1
        assert len(client.get("/api/alarms").json()) == 1

        time.sleep(0.08)
        assert len(client.get("/api/alarms").json()) == 1


def test_network_discovery_uses_at_most_one_subnet_per_interface(
    monkeypatch: pytest.MonkeyPatch,
    isolated_backend_runtime: Path,
) -> None:
    up = SimpleNamespace(isup=True)
    down = SimpleNamespace(isup=False)
    fake_psutil = SimpleNamespace(
        net_if_stats=lambda: {"ethernet": up, "offline": down},
        net_if_addrs=lambda: {
            "ethernet": [
                SimpleNamespace(family=socket.AF_INET, address="192.168.10.20", netmask="255.255.255.0"),
                SimpleNamespace(family=socket.AF_INET, address="192.168.20.20", netmask="255.255.255.0"),
            ],
            "offline": [
                SimpleNamespace(family=socket.AF_INET, address="10.10.10.10", netmask="255.255.255.0"),
            ],
        },
    )
    monkeypatch.setattr(connections_module, "psutil", fake_psutil)
    manager = connections_module.ConnectionManager(isolated_backend_runtime)

    addresses = manager._network_scan_addresses()

    assert len(addresses) == 254
    assert str(addresses[0]) == "192.168.10.1"
    assert str(addresses[-1]) == "192.168.10.254"


def test_empty_network_discovery_does_not_block_manual_connection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        connections_module.ConnectionManager,
        "_network_scan_addresses",
        lambda _self: [],
    )

    with TestClient(create_app()) as client:
        candidates = client.get("/api/connections/network-candidates", params={"port": 9090})
        connected = client.post(
            f"/api/robots/{ROBOT_ID}/connection",
            json={"method": "network", "host": "192.0.2.55", "port": 9090},
        )

        assert candidates.status_code == 200
        assert candidates.json() == []
        assert connected.status_code == 200
        assert connected.json()["connection"]["dataMode"] == "live"
        assert connected.json()["connection"]["commandMode"] == "virtual"


def test_profile_persists_across_restart_without_runtime_state(isolated_backend_runtime: Path) -> None:
    profile = {"method": "network", "host": "10.23.45.67", "port": 19090}

    with TestClient(create_app()) as client:
        response = client.post(f"/api/robots/{ROBOT_ID}/connection", json=profile)
        assert response.status_code == 200
        assert response.json()["connection"]["state"] == "connected"

    persisted = json.loads(isolated_backend_runtime.read_text(encoding="utf-8"))
    assert persisted == {"version": 1, "profiles": {ROBOT_ID: profile}}
    assert "connection" not in persisted["profiles"][ROBOT_ID]
    assert "online" not in persisted["profiles"][ROBOT_ID]

    with TestClient(create_app()) as restarted_client:
        restored = restarted_client.get(f"/api/robots/{ROBOT_ID}").json()
        assert restored["connectionProfile"] == profile
        assert restored["connection"]["state"] == "disconnected"
        assert restored["online"] is False
        assert_runtime_unknown(restored)
        assert restarted_client.get("/api/alarms").json() == []


def test_websocket_receives_initial_and_immediate_connection_snapshots() -> None:
    profile = {"method": "network", "host": "198.51.100.18", "port": 9090}

    with TestClient(create_app()) as client:
        with client.websocket_connect("/ws/telemetry") as websocket:
            initial = [websocket.receive_json() for _ in range(3)]
            assert [message["type"] for message in initial] == [
                "robot_state",
                "log_snapshot",
                "alarm_snapshot",
            ]
            initial_robot = robot_from_snapshot(initial[0])
            assert initial_robot["connection"]["state"] == "disconnected"

            response = client.post(f"/api/robots/{ROBOT_ID}/connection", json=profile)
            assert response.status_code == 200

            connect_updates = [websocket.receive_json() for _ in range(6)]
            robot_updates = [message for message in connect_updates if message["type"] == "robot_state"]
            assert [robot_from_snapshot(message)["connection"]["state"] for message in robot_updates] == [
                "connecting",
                "connected",
            ]
            assert robot_from_snapshot(robot_updates[-1])["connection"]["dataMode"] == "live"

            response = client.delete(f"/api/robots/{ROBOT_ID}/connection")
            assert response.status_code == 200
            disconnect_updates = [websocket.receive_json() for _ in range(3)]
            assert [message["type"] for message in disconnect_updates] == [
                "robot_state",
                "log_snapshot",
                "alarm_snapshot",
            ]
            disconnected = robot_from_snapshot(disconnect_updates[0])
            assert disconnected["connection"]["state"] == "disconnected"
            assert_runtime_unknown(disconnected)

from __future__ import annotations

import time
from pathlib import Path

from fastapi.testclient import TestClient

from polarmarine_gcs.bootstrap.app import create_app
from polarmarine_gcs.bootstrap.settings import Settings
from polarmarine_gcs.domain.links import DriverKind


def test_explicit_simulator_subprocess_handshake_telemetry_and_command(tmp_path: Path) -> None:
    settings = Settings(
        database_url="sqlite:///:memory:",
        recordings_dir=tmp_path / "recordings",
        command_ack_timeout_seconds=2,
        command_state_timeout_seconds=2,
    )
    with TestClient(create_app(settings=settings)) as client:
        link_response = client.post(
            "/api/v1/devices/Hexa-UAV/links",
            json={
                "displayName": "显式仿真链路",
                "driver": "simulator",
                "role": "primary",
                "priority": 10,
                "config": {"seed": 7},
            },
        )
        assert link_response.status_code == 201
        link_id = link_response.json()["id"]
        assert client.post(f"/api/v1/devices/Hexa-UAV/links/{link_id}/connect").status_code == 202

        bootstrap = _wait_for_online_telemetry(client)
        state = next(
            item for item in bootstrap["operationalStates"] if item["deviceId"] == "Hexa-UAV"
        )
        snapshot = next(
            item for item in bootstrap["telemetrySnapshots"] if item["deviceId"] == "Hexa-UAV"
        )
        assert state["status"] == "online"
        assert state["activeLinkId"] == link_id
        assert snapshot["fields"]["position.latitude"]["quality"] == "simulated"
        initial_revision = snapshot["revision"]
        time.sleep(0.65)
        updated = next(
            item
            for item in client.get("/api/v1/bootstrap").json()["telemetrySnapshots"]
            if item["deviceId"] == "Hexa-UAV"
        )
        assert updated["revision"] - initial_revision >= 4

        command = client.post(
            "/api/v1/devices/Hexa-UAV/commands",
            json={"commandType": "manual_control", "payload": {"direction": "stop", "speed": 0}},
        ).json()
        final = _wait_for_command(client, command["id"])
        assert final["status"] == "completed"
        assert final["linkAcknowledgements"][link_id] == "state_confirmed"

        read_command = client.post("/api/v1/devices/Hexa-UAV/parameters/read").json()
        read_final = _wait_for_command(client, read_command["id"])
        assert read_final["result"]["values"]["low_battery_percent"] == 30
        write_command = client.put(
            "/api/v1/devices/Hexa-UAV/parameters",
            json={"values": {"low_battery_percent": 24}},
        ).json()
        write_final = _wait_for_command(client, write_command["id"])
        assert write_final["result"]["parameterResults"]["low_battery_percent"] == {
            "status": "applied",
            "value": 24,
        }
        parameters = client.get("/api/v1/devices/Hexa-UAV/parameters").json()
        low_battery = next(
            item for item in parameters if item["definition"]["key"] == "low_battery_percent"
        )
        assert low_battery["value"] == 24


def test_supervisor_restarts_crashed_driver_and_rehandsakes_desired_link(tmp_path: Path) -> None:
    settings = Settings(
        database_url="sqlite:///:memory:",
        recordings_dir=tmp_path / "recordings",
        command_ack_timeout_seconds=2,
    )
    with TestClient(create_app(settings=settings)) as client:
        link = client.post(
            "/api/v1/devices/Hexa-UAV/links",
            json={
                "displayName": "crash-test",
                "driver": "simulator",
                "role": "primary",
                "priority": 10,
                "config": {"seed": 5},
            },
        ).json()
        client.post(f"/api/v1/devices/Hexa-UAV/links/{link['id']}/connect")
        _wait_for_online_telemetry(client)
        supervisor = client.app.state.container.drivers
        worker = supervisor._workers[DriverKind.SIMULATOR]
        original_pid = worker.process.pid
        worker.process.terminate()
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            session = client.app.state.container.links.get_session(link["id"])
            process = worker.process
            if (
                session is not None
                and session.state.value == "healthy"
                and process is not None
                and process.returncode is None
                and process.pid != original_pid
            ):
                break
            time.sleep(0.05)
        else:
            raise AssertionError("Driver supervisor did not restart and re-handshake")


def _wait_for_online_telemetry(client: TestClient) -> dict[str, object]:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        payload = client.get("/api/v1/bootstrap").json()
        online = any(
            item["deviceId"] == "Hexa-UAV" and item["status"] == "online"
            for item in payload["operationalStates"]
        )
        if online and payload["telemetrySnapshots"]:
            return payload
        time.sleep(0.05)
    raise AssertionError("Simulator did not become healthy and publish telemetry")


def _wait_for_command(client: TestClient, command_id: str) -> dict[str, object]:
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        payload = client.get(f"/api/v1/commands/{command_id}").json()
        if payload["status"] in {
            "completed",
            "rejected",
            "timed_out",
            "state_unconfirmed",
        }:
            return payload
        time.sleep(0.03)
    raise AssertionError("Simulator command did not reach a terminal state")

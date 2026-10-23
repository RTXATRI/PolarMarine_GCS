from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from polarmarine_gcs.bootstrap.app import create_app
from polarmarine_gcs.bootstrap.migrations import _backup_sqlite_database
from polarmarine_gcs.bootstrap.settings import Settings

from .conftest import FakeDriverGateway, create_connected_link


def test_bootstrap_seeds_dynamic_catalogue_but_all_devices_are_offline(client: TestClient) -> None:
    response = client.get("/api/v1/bootstrap")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["templates"]) == 3
    assert len(payload["devices"]) == 5
    assert {item["status"] for item in payload["operationalStates"]} == {"offline"}
    assert payload["linkSessions"] == []
    assert payload["telemetrySnapshots"] == []
    assert payload["settings"]["maxConfiguredDevices"] == 50
    assert payload["settings"]["maxOnlineDevices"] == 20
    serialized = response.text
    for legacy_field in ("online", "dataMode", "commandMode", '"link":'):
        assert legacy_field not in serialized


def test_device_and_template_crud_uses_capabilities_not_device_names(client: TestClient) -> None:
    template = {
        "id": "custom.sensor.platform",
        "displayName": "自定义平台",
        "category": "generic",
        "capabilities": ["telemetry.read"],
        "parameters": [],
        "mediaChannels": [{"id": "inspection", "displayName": "巡检相机"}],
    }
    assert client.post("/api/v1/device-templates", json=template).status_code == 201
    device = {
        "id": "custom-device-01",
        "templateId": template["id"],
        "displayName": "自定义设备 01",
        "enabled": True,
        "tags": ["lab"],
    }
    created = client.post("/api/v1/devices", json=device)
    assert created.status_code == 201
    assert created.json()["templateId"] == template["id"]
    device["displayName"] = "已重命名"
    updated = client.put("/api/v1/devices/custom-device-01", json=device)
    assert updated.status_code == 200
    assert updated.json()["revision"] == 2
    assert client.delete("/api/v1/devices/custom-device-01").status_code == 204
    assert client.delete(f"/api/v1/device-templates/{template['id']}").status_code == 204


def test_config_persists_but_runtime_state_does_not_restart(tmp_path: Path) -> None:
    database = tmp_path / "gcs.sqlite3"
    settings = Settings(
        database_url=f"sqlite:///{database.as_posix()}",
        recordings_dir=tmp_path / "recordings",
        link_heartbeat_interval_seconds=10,
    )
    first_driver = FakeDriverGateway()
    with TestClient(create_app(settings=settings, drivers=first_driver)) as first:
        link = create_connected_link(first)
        state = next(
            item
            for item in first.get("/api/v1/bootstrap").json()["operationalStates"]
            if item["deviceId"] == "Hexa-UAV"
        )
        assert state["status"] == "online"
    with TestClient(create_app(settings=settings, drivers=FakeDriverGateway())) as second:
        payload = second.get("/api/v1/bootstrap").json()
        assert any(item["id"] == link["id"] for item in payload["links"])
        state = next(
            item for item in payload["operationalStates"] if item["deviceId"] == "Hexa-UAV"
        )
        assert state == {
            "deviceId": "Hexa-UAV",
            "status": "offline",
            "activeLinkId": None,
            "healthyLinkIds": [],
            "lastFailoverAt": None,
            "revision": 0,
        }
        assert payload["telemetrySnapshots"] == []


def test_restart_marks_an_inflight_command_unconfirmed(tmp_path: Path) -> None:
    database = tmp_path / "gcs.sqlite3"
    settings = Settings(
        database_url=f"sqlite:///{database.as_posix()}",
        recordings_dir=tmp_path / "recordings",
        command_ack_timeout_seconds=60,
    )
    first_driver = FakeDriverGateway()
    first_driver.auto_ack = False
    with TestClient(create_app(settings=settings, drivers=first_driver)) as first:
        create_connected_link(first)
        submitted = first.post(
            "/api/v1/devices/Hexa-UAV/commands",
            json={
                "commandType": "manual_control",
                "payload": {"direction": "forward", "speed": 0.2},
            },
        ).json()
        assert submitted["status"] == "dispatched"

    with TestClient(create_app(settings=settings, drivers=FakeDriverGateway())) as restarted:
        recovered = restarted.get(f"/api/v1/commands/{submitted['id']}").json()
        assert recovered["status"] == "state_unconfirmed"
        assert recovered["reasonCode"] == "CORE_RESTARTED_DURING_COMMAND"
        alarms = restarted.get("/api/v1/alarms", params={"activeOnly": True}).json()
        assert any(item["code"] == "COMMAND_OUTCOME_UNCONFIRMED" for item in alarms)


def test_legacy_single_link_profiles_are_imported_once_without_restoring_online_state(
    tmp_path: Path,
) -> None:
    data_dir = tmp_path / "runtime"
    data_dir.mkdir()
    legacy_path = data_dir / "device_profiles.json"
    legacy_path.write_text(
        json.dumps(
            {
                "version": 1,
                "profiles": {
                    "Hexa-UAV": {"method": "serial", "port": " COM7 ", "baudRate": 115200},
                    "CL-USV": {"method": "network", "host": "192.168.1.42", "port": 9090},
                    "unknown": {"method": "serial", "port": "COM8", "baudRate": 115200},
                    "Quadri-UAV": {"method": "serial", "port": "", "baudRate": 115200},
                },
            }
        ),
        encoding="utf-8",
    )
    settings = Settings(
        data_dir=data_dir,
        database_url=f"sqlite:///{(data_dir / 'gcs.sqlite3').as_posix()}",
        recordings_dir=data_dir / "recordings",
    )
    with TestClient(create_app(settings=settings, drivers=FakeDriverGateway())) as imported:
        payload = imported.get("/api/v1/bootstrap").json()
        imported_links = [item for item in payload["links"] if item["id"].startswith("legacy:")]
        assert {(item["deviceId"], item["driver"]) for item in imported_links} == {
            ("Hexa-UAV", "serial_json"),
            ("CL-USV", "ros1"),
        }
        assert next(item for item in imported_links if item["deviceId"] == "Hexa-UAV")[
            "config"
        ] == {"port": "COM7", "baudRate": 115200}
        assert payload["linkSessions"] == []
        assert {item["status"] for item in payload["operationalStates"]} == {"offline"}
        events = imported.get(
            "/api/v1/events", params={"type": "legacy_device_profiles.imported"}
        ).json()
        assert events[0]["payload"] == {
            "importedCount": 2,
            "skippedCount": 2,
            "archiveFileName": next(data_dir.glob("device_profiles.json.imported-*")).name,
        }
    assert not legacy_path.exists()

    with TestClient(create_app(settings=settings, drivers=FakeDriverGateway())) as restarted:
        links = restarted.get("/api/v1/bootstrap").json()["links"]
        assert sum(item["id"].startswith("legacy:") for item in links) == 2


def test_corrupt_legacy_profiles_raise_an_alarm_but_do_not_block_startup(tmp_path: Path) -> None:
    data_dir = tmp_path / "runtime"
    data_dir.mkdir()
    legacy_path = data_dir / "device_profiles.json"
    legacy_path.write_text("{broken", encoding="utf-8")
    settings = Settings(
        data_dir=data_dir,
        database_url=f"sqlite:///{(data_dir / 'gcs.sqlite3').as_posix()}",
        recordings_dir=data_dir / "recordings",
    )
    with TestClient(create_app(settings=settings, drivers=FakeDriverGateway())) as client:
        assert client.get("/api/v1/health").status_code == 200
        alarms = client.get("/api/v1/alarms", params={"activeOnly": True}).json()
        assert any(item["code"] == "LEGACY_PROFILE_IMPORT_FAILED" for item in alarms)
    assert legacy_path.is_file()


def test_upgrade_backs_up_an_existing_pre_alembic_database(tmp_path: Path) -> None:
    database = tmp_path / "legacy.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE legacy_marker (value TEXT NOT NULL)")
        connection.execute("INSERT INTO legacy_marker VALUES ('keep')")
    settings = Settings(
        data_dir=tmp_path / "runtime",
        database_url=f"sqlite:///{database.as_posix()}",
        recordings_dir=tmp_path / "recordings",
    )
    with TestClient(create_app(settings=settings, drivers=FakeDriverGateway())) as migrated:
        assert migrated.get("/api/v1/health").status_code == 200
    backups = list((settings.data_dir / "backups").glob("legacy-*.sqlite3.bak"))
    assert len(backups) == 1
    with sqlite3.connect(backups[0]) as connection:
        assert connection.execute("SELECT value FROM legacy_marker").fetchone() == ("keep",)


def test_database_upgrade_backups_are_bounded(tmp_path: Path) -> None:
    database = tmp_path / "bounded.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE marker (value TEXT NOT NULL)")
    backups = tmp_path / "backups"
    backups.mkdir()
    for index in range(3):
        stale = backups / f"bounded-old-{index}.sqlite3.bak"
        stale.write_bytes(b"old")
        os.utime(stale, (index + 1, index + 1))
    created = _backup_sqlite_database(
        f"sqlite:///{database.as_posix()}",
        backups,
        retention_count=2,
    )
    assert created is not None and created.is_file()
    assert len(list(backups.glob("bounded-*.sqlite3.bak"))) == 2


def test_no_route_returns_a_rejected_command_not_a_false_success(client: TestClient) -> None:
    response = client.post(
        "/api/v1/devices/Hexa-UAV/commands",
        json={"commandType": "manual_control", "payload": {"direction": "stop", "speed": 0}},
    )
    assert response.status_code == 202
    command = response.json()
    assert command["status"] == "rejected"
    assert command["reasonCode"] == "NO_HEALTHY_ROUTE"
    deletion = client.delete("/api/v1/devices/Hexa-UAV")
    assert deletion.status_code == 409
    assert "disable it instead" in deletion.json()["error"]["message"]


def test_command_completes_only_after_driver_state_confirmation(client: TestClient) -> None:
    create_connected_link(client)
    response = client.post(
        "/api/v1/devices/Hexa-UAV/commands",
        json={"commandType": "manual_control", "payload": {"direction": "forward", "speed": 0.2}},
    )
    assert response.status_code == 202
    command_id = response.json()["id"]
    current = client.get(f"/api/v1/commands/{command_id}").json()
    assert current["status"] == "completed"
    assert set(current["linkAcknowledgements"].values()) == {"state_confirmed"}


def test_parameter_validation_and_confirmed_write(client: TestClient) -> None:
    create_connected_link(client)
    invalid = client.put(
        "/api/v1/devices/Hexa-UAV/parameters",
        json={"values": {"low_battery_percent": 101}},
    )
    assert invalid.status_code == 422
    valid = client.put(
        "/api/v1/devices/Hexa-UAV/parameters",
        json={"values": {"low_battery_percent": 25}},
    )
    assert valid.status_code == 202
    parameters = client.get("/api/v1/devices/Hexa-UAV/parameters").json()
    value = next(item for item in parameters if item["definition"]["key"] == "low_battery_percent")
    assert value["value"] == 25
    assert value["source"] == "device_confirmed"
    assert valid.json()["result"]["parameterResults"]["low_battery_percent"] == {
        "status": "applied",
        "value": 25,
    }


def test_parameter_read_and_partial_failure_roll_back_confirmed_values(
    client: TestClient,
    fake_driver: FakeDriverGateway,
) -> None:
    link = create_connected_link(client)
    refreshed = client.post("/api/v1/devices/Hexa-UAV/parameters/read")
    assert refreshed.status_code == 202
    assert refreshed.json()["status"] == "completed"
    parameters = client.get("/api/v1/devices/Hexa-UAV/parameters").json()
    assert {item["source"] for item in parameters} == {"device_confirmed"}

    no_difference = client.put(
        "/api/v1/devices/Hexa-UAV/parameters",
        json={"values": {"low_battery_percent": 30}},
    )
    assert no_difference.status_code == 422

    fake_driver.auto_ack = False
    original = client.put(
        "/api/v1/devices/Hexa-UAV/parameters",
        json={"values": {"low_battery_percent": 25, "max_speed": 1.2}},
    ).json()
    client.portal.call(fake_driver.ack, link["id"], original["id"], "accepted")
    client.portal.call(
        fake_driver.ack,
        link["id"],
        original["id"],
        "rejected",
        False,
        {
            "parameterResults": {
                "low_battery_percent": {"status": "applied", "value": 25},
                "max_speed": {"status": "rejected", "reasonCode": "DEVICE_RANGE"},
            }
        },
        "PARTIAL_PARAMETER_FAILURE",
    )
    rollback_message = fake_driver.sent_commands[-1][1]
    rollback_arguments = rollback_message["payload"]["arguments"]
    assert rollback_arguments["values"] == {"low_battery_percent": 30}
    assert rollback_arguments["parameterTransaction"] == {
        "kind": "rollback",
        "originalCommandId": original["id"],
    }
    rollback_id = rollback_message["payload"]["commandId"]
    client.portal.call(fake_driver.ack, link["id"], rollback_id, "accepted")
    client.portal.call(fake_driver.ack, link["id"], rollback_id, "completed")
    client.portal.call(
        fake_driver.ack,
        link["id"],
        rollback_id,
        "state_confirmed",
        True,
        {"values": {"low_battery_percent": 30}},
    )
    parameters = client.get("/api/v1/devices/Hexa-UAV/parameters").json()
    low_battery = next(
        item for item in parameters if item["definition"]["key"] == "low_battery_percent"
    )
    assert low_battery["value"] == 30
    events = client.get("/api/v1/events", params={"type": "parameters.rollback_confirmed"}).json()
    assert events[0]["payload"]["commandId"] == rollback_id


def test_network_discovery_delegates_to_identity_aware_driver(
    client: TestClient,
    fake_driver: FakeDriverGateway,
) -> None:
    response = client.get("/api/v1/discovery/network?driver=ros1&timeoutSeconds=0.2")
    assert response.status_code == 200
    assert response.json() == {"ok": True, "driver": "ros1", "candidates": []}
    assert fake_driver.debug_requests[-1] == (
        "ros1",
        {"operation": "discover", "timeoutSeconds": 0.2},
    )


def _field(value: Any, *, quality: str = "valid") -> dict[str, Any]:
    return {"value": value, "quality": quality, "collectedAt": "2026-07-23T00:00:00+00:00"}

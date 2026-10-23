from __future__ import annotations

import time

from fastapi.testclient import TestClient

from .conftest import FakeDriverGateway, create_connected_link


def _telemetry_ready(
    client: TestClient,
    fake_driver: FakeDriverGateway,
    link_id: str,
    *,
    battery: int = 80,
    include_home: bool = True,
    sequence: int = 1,
) -> None:
    fields = {
        "position.latitude": {"value": 30.1, "quality": "valid"},
        "position.longitude": {"value": 120.1, "quality": "valid"},
        "battery.percent": {"value": battery, "quality": "valid"},
    }
    if include_home:
        fields.update(
            {
                "home.latitude": {"value": 30.0, "quality": "valid"},
                "home.longitude": {"value": 120.0, "quality": "valid"},
            }
        )
    client.portal.call(fake_driver.telemetry, link_id, "Hexa-UAV", fields, sequence)


def _create_plan(client: TestClient, steps: list[dict[str, object]], name: str = "plan") -> dict:
    response = client.post("/api/v1/missions", json={"name": name, "steps": steps})
    assert response.status_code == 201, response.text
    return response.json()


def _ack_command(
    client: TestClient,
    fake_driver: FakeDriverGateway,
    link_id: str,
    command_id: str,
    *,
    rejected: bool = False,
) -> None:
    if rejected:
        client.portal.call(fake_driver.ack, link_id, command_id, "rejected")
        return
    for status in ("accepted", "completed", "state_confirmed"):
        client.portal.call(
            fake_driver.ack,
            link_id,
            command_id,
            status,
            status == "state_confirmed",
        )


def test_mission_plan_rejects_a_dependency_cycle(client: TestClient) -> None:
    response = client.post(
        "/api/v1/missions",
        json={
            "name": "cycle",
            "steps": [
                {"id": "a", "stepType": "route", "deviceId": "Hexa-UAV", "dependsOn": ["b"]},
                {"id": "b", "stepType": "route", "deviceId": "Hexa-UAV", "dependsOn": ["a"]},
            ],
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_device_specific_workflow_requires_a_declared_capability(client: TestClient) -> None:
    response = client.post(
        "/api/v1/missions",
        json={
            "name": "unsupported",
            "steps": [
                {
                    "id": "collect",
                    "stepType": "custom_action",
                    "deviceId": "Hexa-UAV",
                    "payload": {"capability": "payload.waste_collection"},
                }
            ],
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["details"]["capability"] == "payload.waste_collection"


def test_versioned_dag_runs_dependencies_and_finishes_one_mcap_per_run(
    client: TestClient,
    fake_driver: FakeDriverGateway,
) -> None:
    link = create_connected_link(client, driver="ros1")
    _telemetry_ready(client, fake_driver, link["id"])
    fake_driver.auto_ack = False
    plan = _create_plan(
        client,
        [
            {
                "id": "waypoint",
                "stepType": "waypoint",
                "deviceId": "Hexa-UAV",
                "payload": {"latitude": 30.2, "longitude": 120.2},
            },
            {
                "id": "home",
                "stepType": "return_home",
                "deviceId": "Hexa-UAV",
                "dependsOn": ["waypoint"],
            },
        ],
    )
    updated = client.put(
        f"/api/v1/missions/{plan['id']}",
        json={"name": "plan-v2", "description": "versioned", "steps": plan["steps"]},
    ).json()
    assert updated["version"] == 2
    versions = client.get(f"/api/v1/missions/{plan['id']}/versions").json()
    assert [item["version"] for item in versions] == [2, 1]
    assert versions[1]["name"] == "plan"
    run_response = client.post(f"/api/v1/missions/{plan['id']}/runs")
    assert run_response.status_code == 202, run_response.text
    run = run_response.json()
    assert run["stepStates"] == {"waypoint": "running", "home": "pending"}
    assert run["planSteps"] == updated["steps"]
    blocked_update = client.put(
        f"/api/v1/missions/{plan['id']}",
        json={"name": "must-not-change-active-run", "steps": updated["steps"]},
    )
    assert blocked_update.status_code == 409
    first_command = fake_driver.sent_commands[-1][1]["payload"]["commandId"]
    _ack_command(client, fake_driver, link["id"], first_command)
    current = next(
        item for item in client.get("/api/v1/mission-runs").json() if item["id"] == run["id"]
    )
    assert current["stepStates"] == {"waypoint": "completed", "home": "running"}
    second_command = fake_driver.sent_commands[-1][1]["payload"]["commandId"]
    _ack_command(client, fake_driver, link["id"], second_command)
    current = next(
        item for item in client.get("/api/v1/mission-runs").json() if item["id"] == run["id"]
    )
    assert current["status"] == "completed"
    recording = client.get("/api/v1/recordings").json()[0]
    assert recording["missionRunId"] == run["id"]
    assert recording["status"] == "complete"
    assert recording["sizeBytes"] > 0
    messages = client.get(f"/api/v1/recordings/{recording['id']}/messages?limit=20").json()
    assert {item["topic"] for item in messages} == {"/polarmarine/raw"}
    download = client.get(f"/api/v1/recordings/{recording['id']}/download")
    assert download.status_code == 200
    assert download.content.startswith(b"\x89MCAP")
    assert client.delete(f"/api/v1/missions/{plan['id']}").status_code == 204
    archived = next(
        item for item in client.get("/api/v1/missions").json() if item["id"] == plan["id"]
    )
    assert archived["status"] == "archived"


def test_pause_resume_cancel_are_confirmed_by_device_and_late_step_ack_is_ignored(
    client: TestClient,
    fake_driver: FakeDriverGateway,
) -> None:
    link = create_connected_link(client, driver="ros1")
    _telemetry_ready(client, fake_driver, link["id"])
    fake_driver.auto_ack = False
    plan = _create_plan(
        client,
        [{"id": "route", "stepType": "route", "deviceId": "Hexa-UAV"}],
    )
    run = client.post(f"/api/v1/missions/{plan['id']}/runs").json()
    step_command = fake_driver.sent_commands[-1][1]["payload"]["commandId"]
    for action, expected in (("pause", "paused"), ("resume", "running"), ("cancel", "cancelled")):
        receipt = client.post(f"/api/v1/mission-runs/{run['id']}/{action}").json()
        control_command = receipt["commands"][0]
        _ack_command(client, fake_driver, link["id"], control_command["id"])
        current = next(
            item for item in client.get("/api/v1/mission-runs").json() if item["id"] == run["id"]
        )
        assert current["status"] == expected
    _ack_command(client, fake_driver, link["id"], step_command)
    current = next(
        item for item in client.get("/api/v1/mission-runs").json() if item["id"] == run["id"]
    )
    assert current["status"] == "cancelled"
    assert client.post(f"/api/v1/mission-runs/{run['id']}/cancel").json()["commands"] == []


def test_resume_schedules_steps_that_became_ready_while_paused(
    client: TestClient,
    fake_driver: FakeDriverGateway,
) -> None:
    link = create_connected_link(client, driver="ros1")
    _telemetry_ready(client, fake_driver, link["id"])
    fake_driver.auto_ack = False
    plan = _create_plan(
        client,
        [
            {"id": "first", "stepType": "route", "deviceId": "Hexa-UAV"},
            {
                "id": "second",
                "stepType": "return_home",
                "deviceId": "Hexa-UAV",
                "dependsOn": ["first"],
            },
        ],
    )
    run = client.post(f"/api/v1/missions/{plan['id']}/runs").json()
    first_command_id = fake_driver.sent_commands[-1][1]["payload"]["commandId"]

    pause = client.post(f"/api/v1/mission-runs/{run['id']}/pause").json()["commands"][0]
    _ack_command(client, fake_driver, link["id"], pause["id"])
    _ack_command(client, fake_driver, link["id"], first_command_id)
    assert len(fake_driver.sent_commands) == 2

    resume = client.post(f"/api/v1/mission-runs/{run['id']}/resume").json()["commands"][0]
    _ack_command(client, fake_driver, link["id"], resume["id"])
    assert len(fake_driver.sent_commands) == 4
    second_arguments = fake_driver.sent_commands[-1][1]["payload"]["arguments"]
    assert second_arguments["missionStepId"] == "second"


def test_mission_step_timeout_overrides_the_short_generic_command_timeout(
    client: TestClient,
    fake_driver: FakeDriverGateway,
) -> None:
    link = create_connected_link(client, driver="ros1")
    _telemetry_ready(client, fake_driver, link["id"])
    fake_driver.auto_ack = False
    plan = _create_plan(
        client,
        [
            {
                "id": "long-step",
                "stepType": "route",
                "deviceId": "Hexa-UAV",
                "timeoutSeconds": 0.5,
            }
        ],
    )
    run = client.post(f"/api/v1/missions/{plan['id']}/runs").json()
    command_id = fake_driver.sent_commands[-1][1]["payload"]["commandId"]
    client.portal.call(fake_driver.ack, link["id"], command_id, "accepted")

    time.sleep(0.25)
    assert client.get(f"/api/v1/commands/{command_id}").json()["status"] == "accepted"
    time.sleep(0.35)
    assert client.get(f"/api/v1/commands/{command_id}").json()["status"] == "state_unconfirmed"
    current_run = next(
        item for item in client.get("/api/v1/mission-runs").json() if item["id"] == run["id"]
    )
    assert current_run["status"] == "failed"


def test_rejected_step_fails_run_and_marks_recording_interrupted(
    client: TestClient,
    fake_driver: FakeDriverGateway,
) -> None:
    link = create_connected_link(client, driver="ros1")
    _telemetry_ready(client, fake_driver, link["id"])
    fake_driver.auto_ack = False
    plan = _create_plan(
        client,
        [{"id": "route", "stepType": "route", "deviceId": "Hexa-UAV"}],
    )
    run = client.post(f"/api/v1/missions/{plan['id']}/runs").json()
    command_id = fake_driver.sent_commands[-1][1]["payload"]["commandId"]
    _ack_command(client, fake_driver, link["id"], command_id, rejected=True)
    current = next(
        item for item in client.get("/api/v1/mission-runs").json() if item["id"] == run["id"]
    )
    assert current["status"] == "failed"
    assert client.get("/api/v1/recordings").json()[0]["status"] == "interrupted"


def test_preflight_reports_offline_missing_telemetry_battery_home_and_route(
    client: TestClient,
    fake_driver: FakeDriverGateway,
) -> None:
    route_plan = _create_plan(
        client,
        [{"id": "route", "stepType": "route", "deviceId": "Hexa-UAV"}],
        "route",
    )
    offline = client.post(f"/api/v1/missions/{route_plan['id']}/runs")
    assert offline.status_code == 409
    assert offline.json()["error"]["details"]["failures"][0]["code"] == "DEVICE_OFFLINE"

    link = create_connected_link(client, driver="ros1")
    unknown = client.post(f"/api/v1/missions/{route_plan['id']}/runs")
    assert unknown.status_code == 409
    assert unknown.json()["error"]["details"]["failures"][0]["code"] == "TELEMETRY_UNKNOWN"

    client.portal.call(
        fake_driver.telemetry,
        link["id"],
        "Hexa-UAV",
        {
            "position.latitude": {"value": 30.1, "quality": "valid"},
            "position.longitude": {"value": 120.1, "quality": "valid"},
        },
        1,
    )
    no_battery = client.post(f"/api/v1/missions/{route_plan['id']}/runs")
    codes = {item["code"] for item in no_battery.json()["error"]["details"]["failures"]}
    assert "BATTERY_UNAVAILABLE" in codes

    _telemetry_ready(
        client,
        fake_driver,
        link["id"],
        battery=10,
        include_home=False,
        sequence=2,
    )
    low = client.post(f"/api/v1/missions/{route_plan['id']}/runs")
    assert "BATTERY_TOO_LOW" in {
        item["code"] for item in low.json()["error"]["details"]["failures"]
    }

    _telemetry_ready(client, fake_driver, link["id"], include_home=False, sequence=3)
    home_plan = _create_plan(
        client,
        [{"id": "home", "stepType": "return_home", "deviceId": "Hexa-UAV"}],
        "home",
    )
    no_home = client.post(f"/api/v1/missions/{home_plan['id']}/runs")
    assert "HOME_UNAVAILABLE" in {
        item["code"] for item in no_home.json()["error"]["details"]["failures"]
    }
    client.app.state.container.links.sessions[link["id"]].capabilities = frozenset()
    no_route = client.post(f"/api/v1/missions/{route_plan['id']}/runs")
    assert "CAPABILITY_ROUTE_UNAVAILABLE" in {
        item["code"] for item in no_route.json()["error"]["details"]["failures"]
    }

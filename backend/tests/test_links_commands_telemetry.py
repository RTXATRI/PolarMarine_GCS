from __future__ import annotations

import time

from fastapi.testclient import TestClient

from polarmarine_gcs.bootstrap.app import create_app
from polarmarine_gcs.bootstrap.settings import Settings

from .conftest import FakeDriverGateway, create_connected_link


def test_two_links_are_online_and_primary_failure_switches_route(
    client: TestClient,
    fake_driver: FakeDriverGateway,
) -> None:
    primary = create_connected_link(client, priority=10)
    auxiliary = create_connected_link(client, priority=20, role="auxiliary")
    container = client.app.state.container
    state = container.links.operational_state("Hexa-UAV")
    assert set(state.healthy_link_ids) == {primary["id"], auxiliary["id"]}
    assert state.active_link_id == primary["id"]
    client.portal.call(fake_driver.fail, primary["id"])
    state = container.links.operational_state("Hexa-UAV")
    assert state.active_link_id == auxiliary["id"]
    assert state.last_failover_at is not None


def test_failed_link_is_reopened_with_backoff_and_rehandsakes(
    client: TestClient,
    fake_driver: FakeDriverGateway,
) -> None:
    link = create_connected_link(client, driver="ros1")
    client.portal.call(fake_driver.fail, link["id"])
    assert client.app.state.container.links.get_session(link["id"]).state.value == "recovering"
    deadline = time.monotonic() + 2.0
    while time.monotonic() < deadline:
        session = client.app.state.container.links.get_session(link["id"])
        if session is not None and session.state.value == "healthy":
            break
        time.sleep(0.03)
    else:
        raise AssertionError("Link did not recover after the one-second backoff")


def test_preferred_link_only_fails_back_after_stability_debounce_and_no_inflight_command(
    client: TestClient,
    fake_driver: FakeDriverGateway,
) -> None:
    primary = create_connected_link(client, driver="ros1", priority=10)
    auxiliary = create_connected_link(client, driver="ros1", priority=20, role="auxiliary")
    client.portal.call(fake_driver.fail, primary["id"])
    assert (
        client.app.state.container.links.operational_state("Hexa-UAV").active_link_id
        == auxiliary["id"]
    )
    fake_driver.auto_ack = False
    command = client.post(
        "/api/v1/devices/Hexa-UAV/commands",
        json={"commandType": "manual_control", "payload": {"direction": "stop", "speed": 0}},
    ).json()
    assert command["routedLinkIds"] == [auxiliary["id"]]
    assert fake_driver.handler is not None
    client.portal.call(
        fake_driver.handler,
        {
            "type": "link.device_info",
            "payload": {
                "linkId": primary["id"],
                "deviceId": "Hexa-UAV",
                "capabilities": list(
                    client.app.state.container.registry.require_template(
                        "polarmarine.uav.standard"
                    ).capabilities
                ),
            },
        },
    )
    time.sleep(0.03)
    client.portal.call(client.app.state.container.links._recompute_route, "Hexa-UAV")
    assert (
        client.app.state.container.links.operational_state("Hexa-UAV").active_link_id
        == auxiliary["id"]
    )
    client.post(f"/api/v1/commands/{command['id']}/cancel")
    client.portal.call(client.app.state.container.links._recompute_route, "Hexa-UAV")
    assert (
        client.app.state.container.links.operational_state("Hexa-UAV").active_link_id
        == primary["id"]
    )


def test_inflight_non_idempotent_command_is_not_retried_after_link_loss(
    client: TestClient,
    fake_driver: FakeDriverGateway,
) -> None:
    primary = create_connected_link(client, priority=10)
    create_connected_link(client, priority=20, role="auxiliary")
    fake_driver.auto_ack = False
    command = client.post(
        "/api/v1/devices/Hexa-UAV/commands",
        json={"commandType": "manual_control", "payload": {"direction": "forward", "speed": 0.3}},
    ).json()
    assert command["status"] == "dispatched"
    assert len(fake_driver.sent_commands) == 1
    client.portal.call(fake_driver.fail, primary["id"])
    current = client.get(f"/api/v1/commands/{command['id']}").json()
    assert current["status"] == "state_unconfirmed"
    assert current["reasonCode"] == "LINK_LOST_DURING_COMMAND"
    assert len(fake_driver.sent_commands) == 1


def test_emergency_stop_fans_out_same_command_to_every_healthy_link(
    client: TestClient,
    fake_driver: FakeDriverGateway,
) -> None:
    first = create_connected_link(client, priority=10)
    second = create_connected_link(client, priority=20, role="auxiliary")
    fake_driver.auto_ack = False
    command = client.post(
        "/api/v1/devices/Hexa-UAV/commands",
        json={"commandType": "emergency_stop", "payload": {}},
    ).json()
    assert set(command["routedLinkIds"]) == {first["id"], second["id"]}
    assert len(fake_driver.sent_commands) == 2
    command_ids = {message["payload"]["commandId"] for _, message in fake_driver.sent_commands}
    assert command_ids == {command["id"]}
    client.portal.call(fake_driver.ack, first["id"], command["id"], "accepted")
    client.portal.call(fake_driver.ack, second["id"], command["id"], "rejected")
    current = client.get(f"/api/v1/commands/{command['id']}").json()
    assert current["status"] == "accepted"
    assert current["linkAcknowledgements"] == {first["id"]: "accepted", second["id"]: "rejected"}


def test_emergency_stop_needs_state_confirmation_and_keeps_per_link_late_ack(
    client: TestClient,
    fake_driver: FakeDriverGateway,
) -> None:
    first = create_connected_link(client, driver="ros1", priority=10)
    second = create_connected_link(client, driver="ros1", priority=20, role="auxiliary")
    fake_driver.auto_ack = False
    command = client.post(
        "/api/v1/devices/Hexa-UAV/commands",
        json={"commandType": "emergency_stop", "payload": {}},
    ).json()
    client.portal.call(fake_driver.ack, first["id"], command["id"], "state_confirmed", True)
    current = client.get(f"/api/v1/commands/{command['id']}").json()
    assert current["status"] == "completed"
    client.portal.call(fake_driver.ack, second["id"], command["id"], "rejected")
    current = client.get(f"/api/v1/commands/{command['id']}").json()
    assert current["status"] == "completed"
    assert current["linkAcknowledgements"][second["id"]] == "rejected"


def test_emergency_stop_is_rejected_when_every_link_rejects(
    client: TestClient,
    fake_driver: FakeDriverGateway,
) -> None:
    first = create_connected_link(client, driver="ros1", priority=10)
    second = create_connected_link(client, driver="ros1", priority=20, role="auxiliary")
    fake_driver.auto_ack = False
    command = client.post(
        "/api/v1/devices/Hexa-UAV/commands",
        json={"commandType": "emergency_stop", "payload": {}},
    ).json()
    client.portal.call(fake_driver.ack, first["id"], command["id"], "rejected")
    client.portal.call(fake_driver.ack, second["id"], command["id"], "rejected")
    assert client.get(f"/api/v1/commands/{command['id']}").json()["status"] == "rejected"


def test_late_ack_is_recorded_without_turning_uncertain_result_into_success(
    client: TestClient,
    fake_driver: FakeDriverGateway,
) -> None:
    link = create_connected_link(client, driver="ros1")
    fake_driver.auto_ack = False
    command = client.post(
        "/api/v1/devices/Hexa-UAV/commands",
        json={"commandType": "manual_control", "payload": {"direction": "stop", "speed": 0}},
    ).json()
    cancelled = client.post(f"/api/v1/commands/{command['id']}/cancel").json()
    assert cancelled["status"] == "cancelled"
    client.portal.call(fake_driver.ack, link["id"], command["id"], "state_confirmed")
    current = client.get(f"/api/v1/commands/{command['id']}").json()
    assert current["status"] == "cancelled"
    assert current["linkAcknowledgements"][link["id"]] == "state_confirmed"


def test_unrouted_and_out_of_order_acknowledgements_cannot_advance_or_regress_command(
    client: TestClient,
    fake_driver: FakeDriverGateway,
) -> None:
    primary = create_connected_link(client, driver="ros1", priority=10)
    auxiliary = create_connected_link(client, driver="ros1", priority=20, role="auxiliary")
    fake_driver.auto_ack = False
    command = client.post(
        "/api/v1/devices/Hexa-UAV/commands",
        json={"commandType": "manual_control", "payload": {"direction": "stop", "speed": 0}},
    ).json()

    client.portal.call(fake_driver.ack, auxiliary["id"], command["id"], "accepted")
    current = client.get(f"/api/v1/commands/{command['id']}").json()
    assert current["status"] == "dispatched"
    assert auxiliary["id"] not in current["linkAcknowledgements"]

    client.portal.call(fake_driver.ack, primary["id"], command["id"], "in_progress")
    client.portal.call(fake_driver.ack, primary["id"], command["id"], "accepted")
    current = client.get(f"/api/v1/commands/{command['id']}").json()
    assert current["status"] == "in_progress"
    events = client.get(
        "/api/v1/events",
        params={"type": "command.unrouted_acknowledgement_ignored"},
    ).json()
    assert events[0]["payload"] == {"linkId": auxiliary["id"]}


def test_invalid_gps_is_explicit_and_never_replaced_with_demo_coordinates(
    client: TestClient,
    fake_driver: FakeDriverGateway,
) -> None:
    link = create_connected_link(client, driver="ros1")
    client.portal.call(
        fake_driver.telemetry,
        link["id"],
        "Hexa-UAV",
        {
            "position.latitude": {"value": 120, "quality": "valid"},
            "position.longitude": {"value": None, "quality": "valid"},
            "battery.percent": {"value": 80, "quality": "valid"},
        },
    )
    snapshot = client.get("/api/v1/telemetry/snapshots").json()[0]
    assert snapshot["fields"]["position.latitude"]["value"] is None
    assert snapshot["fields"]["position.latitude"]["quality"] == "invalid"
    assert snapshot["fields"]["position.longitude"]["value"] is None
    assert snapshot["fields"]["position.longitude"]["quality"] == "invalid"
    assert "30.2755" not in str(snapshot)


def test_equator_and_prime_meridian_are_valid_except_for_zero_zero_pair(
    client: TestClient,
    fake_driver: FakeDriverGateway,
) -> None:
    link = create_connected_link(client, driver="ros1")
    client.portal.call(
        fake_driver.telemetry,
        link["id"],
        "Hexa-UAV",
        {
            "position.latitude": {"value": 0, "quality": "valid"},
            "position.longitude": {"value": 120, "quality": "valid"},
        },
    )
    snapshot = client.get("/api/v1/telemetry/snapshots").json()[0]
    assert snapshot["fields"]["position.latitude"]["value"] == 0
    assert snapshot["fields"]["position.latitude"]["quality"] == "valid"

    client.portal.call(
        fake_driver.telemetry,
        link["id"],
        "Hexa-UAV",
        {
            "position.latitude": {"value": 0, "quality": "valid"},
            "position.longitude": {"value": 0, "quality": "valid"},
        },
    )
    snapshot = client.get("/api/v1/telemetry/snapshots").json()[0]
    assert snapshot["fields"]["position.latitude"]["value"] is None
    assert snapshot["fields"]["position.longitude"]["value"] is None
    assert snapshot["fields"]["position.latitude"]["quality"] == "invalid"


def test_telemetry_drops_duplicate_and_out_of_order_sequences(
    client: TestClient,
    fake_driver: FakeDriverGateway,
) -> None:
    link = create_connected_link(client, driver="ros1")
    for sequence, battery in ((10, 70), (10, 20), (9, 10), (11, 69)):
        client.portal.call(
            fake_driver.telemetry,
            link["id"],
            "Hexa-UAV",
            {"battery.percent": {"value": battery, "quality": "valid"}},
            sequence,
        )
    snapshot = client.get("/api/v1/telemetry/snapshots").json()[0]
    assert snapshot["fields"]["battery.percent"]["value"] == 69


def test_three_missing_heartbeat_periods_move_link_to_recovering(tmp_path) -> None:
    driver = FakeDriverGateway()
    settings = Settings(
        database_url="sqlite:///:memory:",
        recordings_dir=tmp_path / "recordings",
        link_heartbeat_interval_seconds=0.02,
        link_missed_heartbeats=3,
    )
    with TestClient(create_app(settings=settings, drivers=driver)) as heartbeat_client:
        link = create_connected_link(heartbeat_client, driver="ros1")
        time.sleep(0.09)
        session = heartbeat_client.app.state.container.links.get_session(link["id"])
        assert session.state.value == "recovering"
        assert (
            heartbeat_client.app.state.container.links.operational_state("Hexa-UAV").status.value
            == "offline"
        )

from __future__ import annotations

import io
import json
import math
import time
import zipfile
from functools import partial

import pytest
from fastapi.testclient import TestClient

from polarmarine_gcs.application.events import EventBroker
from polarmarine_gcs.application.parameters import _validate_value, parameter_definition_payload
from polarmarine_gcs.application.telemetry import _parse_time, _quality, _signal_group
from polarmarine_gcs.domain.common import ValidationError
from polarmarine_gcs.domain.devices import ParameterDefinition, ParameterValueType
from polarmarine_gcs.domain.events import AlarmSeverity, SystemEvent
from polarmarine_gcs.domain.telemetry import TelemetryQuality

from .conftest import FakeDriverGateway, create_connected_link


@pytest.mark.asyncio
async def test_event_broker_bounds_subscriber_queues_and_transient_events() -> None:
    broker = EventBroker(queue_size=1)
    assert broker.current_sequence == 0
    async with broker.subscribe() as queue:
        await broker.publish(SystemEvent("one", "test", "one", 1, {}))
        newest = await broker.publish(SystemEvent("two", "test", "two", 1, {}))
        assert queue.qsize() == 1
        assert (await queue.get()).type == "two"
        assert newest.connection_sequence == 2
    assert broker.current_sequence == 2


def test_alarm_lifecycle_and_filtered_event_history(client: TestClient) -> None:
    container = client.app.state.container
    cursor_before = container.repository.latest_event_cursor()
    transient = client.portal.call(
        partial(
            container.events.transient,
            type="debug.transient",
            aggregate_type="debug",
            aggregate_id="transient",
            aggregate_revision=1,
            payload={},
        )
    )
    assert transient.event_cursor is None
    assert container.repository.latest_event_cursor() == cursor_before
    alarm = client.portal.call(
        partial(
            container.events.raise_alarm,
            code="TEST_ALARM",
            severity=AlarmSeverity.WARNING,
            message="test",
            device_id="Hexa-UAV",
        )
    )
    response = client.post(f"/api/v1/alarms/{alarm.id}/acknowledge")
    assert response.status_code == 200
    assert response.json()["acknowledged"] is True
    assert client.post(f"/api/v1/alarms/{alarm.id}/acknowledge").status_code == 200
    assert client.post("/api/v1/alarms/missing/acknowledge").status_code == 404
    events = client.get("/api/v1/events?type=alarm.raised&aggregateId=" + alarm.id).json()
    assert [item["type"] for item in events] == ["alarm.raised"]
    older = client.get(f"/api/v1/events?before={events[0]['eventCursor'] + 1}&limit=1").json()
    assert older


def test_registry_conflicts_updates_and_link_validation(
    client: TestClient,
    fake_driver: FakeDriverGateway,
) -> None:
    template = {
        "id": "edge.template",
        "displayName": "Edge",
        "category": "generic",
        "capabilities": ["telemetry.read"],
        "parameters": [],
        "mediaChannels": [],
    }
    assert client.post("/api/v1/device-templates", json=template).status_code == 201
    assert client.post("/api/v1/device-templates", json=template).status_code == 409
    invalid_template = {**template, "id": "bad id"}
    assert client.post("/api/v1/device-templates", json=invalid_template).status_code == 422
    template["displayName"] = "Edge v2"
    assert (
        client.put("/api/v1/device-templates/edge.template", json=template).json()["revision"] == 2
    )
    device = {
        "id": "edge-device",
        "templateId": "edge.template",
        "displayName": "Edge Device",
        "enabled": True,
    }
    assert client.post("/api/v1/devices", json=device).status_code == 201
    assert client.post("/api/v1/devices", json=device).status_code == 409
    assert client.delete("/api/v1/device-templates/edge.template").status_code == 409
    assert client.get("/api/v1/devices/missing/links").status_code == 404
    for driver, config in (
        ("ros1", {"host": "", "port": 9090}),
        ("ros2", {"host": "localhost", "port": 70_000}),
        ("serial_json", {"port": "", "baudRate": 115200}),
        ("serial_json", {"port": "COM1", "baudRate": 123}),
        ("simulator", {"seed": "bad"}),
    ):
        response = client.post(
            "/api/v1/devices/edge-device/links",
            json={
                "displayName": "invalid",
                "driver": driver,
                "role": "primary",
                "priority": 10,
                "config": config,
            },
        )
        assert response.status_code == 422
    link = client.post(
        "/api/v1/devices/edge-device/links",
        json={
            "displayName": "serial",
            "driver": "serial_json",
            "role": "primary",
            "priority": 20,
            "config": {"port": "COM7", "baudRate": 115200},
        },
    ).json()
    link_body = {
        "displayName": "serial-updated",
        "driver": "serial_json",
        "role": "auxiliary",
        "priority": 30,
        "config": {"port": "COM7", "baudRate": 230400},
    }
    assert (
        client.put(f"/api/v1/devices/edge-device/links/{link['id']}", json=link_body).json()[
            "revision"
        ]
        == 2
    )
    fake_driver.fail_starts = True
    connected = client.post(f"/api/v1/devices/edge-device/links/{link['id']}/connect")
    assert connected.json()["session"]["state"] == "recovering"
    assert (
        client.post(f"/api/v1/devices/edge-device/links/{link['id']}/disconnect").status_code == 202
    )
    assert client.delete(f"/api/v1/devices/edge-device/links/{link['id']}").status_code == 204
    assert client.delete("/api/v1/devices/edge-device").status_code == 204
    assert client.delete("/api/v1/device-templates/edge.template").status_code == 204


def test_parameter_types_ranges_and_metadata_are_strict(client: TestClient) -> None:
    definitions = [
        ParameterDefinition("flag", "Flag", ParameterValueType.BOOLEAN, False),
        ParameterDefinition("count", "Count", ParameterValueType.INTEGER, 1, minimum=0, maximum=2),
        ParameterDefinition("ratio", "Ratio", ParameterValueType.NUMBER, 0.5),
        ParameterDefinition(
            "mode",
            "Mode",
            ParameterValueType.ENUM,
            "a",
            enum_values=("a", "b"),
        ),
        ParameterDefinition("label", "Label", ParameterValueType.STRING, "x"),
        ParameterDefinition("locked", "Locked", ParameterValueType.STRING, "x", read_only=True),
    ]
    for definition, value in zip(definitions[:5], (True, 2, 0.25, "b", "ok"), strict=True):
        _validate_value(definition, value)
    invalid_values = (
        (definitions[0], "true"),
        (definitions[1], 1.5),
        (definitions[1], -1),
        (definitions[1], 3),
        (definitions[2], math.inf),
        (definitions[3], "c"),
        (definitions[4], 1),
        (definitions[5], "x"),
    )
    for definition, value in invalid_values:
        with pytest.raises(ValidationError):
            _validate_value(definition, value)
    assert parameter_definition_payload(definitions[3])["enumValues"] == ["a", "b"]
    assert (
        client.put(
            "/api/v1/devices/Hexa-UAV/parameters",
            json={"values": {"not-a-parameter": 1}},
        ).status_code
        == 422
    )


def test_command_validation_idempotency_dispatch_failure_and_timeouts(
    client: TestClient,
    fake_driver: FakeDriverGateway,
) -> None:
    link = create_connected_link(client, driver="ros1")
    for command_type, payload in (
        ("manual_control", {"direction": "up", "speed": 1}),
        ("manual_control", {"direction": "forward", "speed": -1}),
        ("set_mode", {}),
        ("set_armed", {"armed": "yes"}),
        ("custom_action", {}),
    ):
        response = client.post(
            "/api/v1/devices/Hexa-UAV/commands",
            json={"commandType": command_type, "payload": payload},
        )
        assert response.status_code == 422
    fake_driver.auto_ack = False
    body = {
        "commandType": "manual_control",
        "payload": {"direction": "stop", "speed": 0},
        "idempotencyKey": "same-request",
    }
    first = client.post("/api/v1/devices/Hexa-UAV/commands", json=body).json()
    second = client.post("/api/v1/devices/Hexa-UAV/commands", json=body).json()
    assert second["id"] == first["id"]
    assert client.app.state.container.commands.has_inflight_commands("Hexa-UAV") is True
    time.sleep(0.25)
    assert client.get(f"/api/v1/commands/{first['id']}").json()["status"] == "timed_out"

    accepted = client.post(
        "/api/v1/devices/Hexa-UAV/commands",
        json={"commandType": "set_mode", "payload": {"mode": "hold"}},
    ).json()
    client.portal.call(fake_driver.ack, link["id"], accepted["id"], "accepted")
    time.sleep(0.25)
    assert client.get(f"/api/v1/commands/{accepted['id']}").json()["status"] == "state_unconfirmed"

    fake_driver.send_failures.add(link["id"])
    failed = client.post(
        "/api/v1/devices/Hexa-UAV/commands",
        json={"commandType": "set_armed", "payload": {"armed": False}},
    ).json()
    assert failed["status"] == "rejected"
    assert failed["reasonCode"] == "ALL_DISPATCHES_FAILED"


def test_link_protocol_events_identity_debug_and_degraded_recovery(
    client: TestClient,
    fake_driver: FakeDriverGateway,
) -> None:
    link = create_connected_link(client, driver="ros1")
    assert fake_driver.handler is not None
    client.portal.call(
        fake_driver.handler,
        {"type": "link.debug_ready", "payload": {"linkId": link["id"]}},
    )
    assert client.get("/api/v1/devices/Hexa-UAV/link-sessions").json()[0]["debugAvailable"] is True
    client.portal.call(
        fake_driver.handler,
        {
            "type": "link.degraded",
            "payload": {"linkId": link["id"], "code": "LOSS", "message": "loss"},
        },
    )
    assert client.app.state.container.links.get_session(link["id"]).state.value == "degraded"
    client.portal.call(fake_driver.heartbeat, link["id"])
    assert client.app.state.container.links.get_session(link["id"]).state.value == "healthy"
    client.portal.call(
        fake_driver.handler,
        {
            "type": "debug.ros_message",
            "payload": {"linkId": link["id"], "topic": "/test", "message": {}},
        },
    )
    client.portal.call(
        fake_driver.handler,
        {
            "type": "link.device_info",
            "payload": {
                "linkId": link["id"],
                "deviceId": "wrong-device",
                "capabilities": [],
            },
        },
    )
    session = client.app.state.container.links.get_session(link["id"])
    assert session.state.value == "failed"
    assert session.debug_available is False
    assert any(
        item.code == "DEVICE_ID_MISMATCH"
        for item in client.app.state.container.repository.list_alarms()
    )


def test_telemetry_helpers_cover_quality_time_and_signal_groups() -> None:
    assert _signal_group("position.latitude") == "navigation"
    assert _signal_group("battery.voltage") == "power"
    assert _signal_group("link.rssi") == "link"
    assert _signal_group("mission.progress") == "mission"
    assert _signal_group("control.armed") == "control"
    assert _signal_group("environment.temperature") == "environment"
    assert _parse_time(None) is None
    assert _parse_time("bad") is None
    assert _parse_time("2026-07-23T08:00:00") is None
    assert _parse_time("2026-07-23T08:00:00Z") is not None
    assert _quality(None) is TelemetryQuality.VALID
    assert _quality("unsupported") is TelemetryQuality.VALID
    assert _quality("stale") is TelemetryQuality.STALE


def test_support_bundle_redacts_link_secrets(client: TestClient) -> None:
    response = client.post(
        "/api/v1/devices/Hexa-UAV/links",
        json={
            "displayName": "private",
            "driver": "ros1",
            "role": "primary",
            "priority": 10,
            "config": {"host": "127.0.0.1", "port": 9090, "accessToken": "do-not-export"},
        },
    )
    assert response.status_code == 201
    bundle_response = client.get("/api/v1/support-bundle")
    assert bundle_response.status_code == 200
    with zipfile.ZipFile(io.BytesIO(bundle_response.content)) as bundle:
        assert set(bundle.namelist()) == {"manifest.json", "system-snapshot.json"}
        snapshot = json.loads(bundle.read("system-snapshot.json"))
    assert snapshot["links"][0]["config"]["accessToken"] == "[REDACTED]"
    assert "do-not-export" not in bundle_response.content.decode("latin1")

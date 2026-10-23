from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from polarmarine_gcs.application.ports.drivers import DriverEventHandler
from polarmarine_gcs.bootstrap.app import create_app
from polarmarine_gcs.bootstrap.settings import Settings
from polarmarine_gcs.domain.links import LinkProfile


class FakeDriverGateway:
    def __init__(self) -> None:
        self.handler: DriverEventHandler | None = None
        self.active: dict[str, LinkProfile] = {}
        self.sent_commands: list[tuple[str, dict[str, Any]]] = []
        self.debug_requests: list[tuple[str, dict[str, Any]]] = []
        self.send_failures: set[str] = set()
        self.fail_starts = False
        self.auto_ack = True
        self.started = False

    def set_event_handler(self, handler: DriverEventHandler) -> None:
        self.handler = handler

    async def start(self) -> None:
        self.started = True

    async def stop(self) -> None:
        self.started = False
        self.active.clear()

    async def start_link(
        self,
        profile: LinkProfile,
        *,
        expected_device_id: str,
        requested_capabilities: frozenset[str],
    ) -> None:
        assert self.handler
        if self.fail_starts:
            raise RuntimeError("driver start failed")
        self.active[profile.id] = profile
        await self.handler({"type": "link.handshaking", "payload": {"linkId": profile.id}})
        await self.handler(
            {
                "type": "link.device_info",
                "payload": {
                    "linkId": profile.id,
                    "deviceId": expected_device_id,
                    "capabilities": sorted(requested_capabilities),
                },
            }
        )
        await self.heartbeat(profile.id)

    async def stop_link(self, profile: LinkProfile) -> None:
        self.active.pop(profile.id, None)

    async def send_command(self, profile: LinkProfile, message: dict[str, Any]) -> None:
        if profile.id in self.send_failures:
            raise RuntimeError("dispatch failed")
        self.sent_commands.append((profile.id, message))
        if not self.auto_ack:
            return
        payload = message["payload"]
        command_id = str(payload["commandId"])
        command_type = str(payload.get("commandType", ""))
        arguments = payload.get("arguments")
        arguments = arguments if isinstance(arguments, dict) else {}
        result: dict[str, Any] = {}
        if command_type == "read_parameters":
            defaults = arguments.get("defaults")
            result = {"values": defaults if isinstance(defaults, dict) else {}}
        elif command_type == "write_parameters":
            values = arguments.get("values")
            values = values if isinstance(values, dict) else {}
            result = {
                "values": values,
                "parameterResults": {
                    str(key): {"status": "applied", "value": value} for key, value in values.items()
                },
            }
        await self.ack(profile.id, command_id, "accepted")
        await self.ack(profile.id, command_id, "completed")
        await self.ack(
            profile.id,
            command_id,
            "state_confirmed",
            state_confirmed=True,
            result=result,
        )

    async def debug_request(self, driver: str, request: dict[str, Any]) -> dict[str, Any]:
        self.debug_requests.append((driver, request))
        if request.get("operation") == "discover":
            return {"ok": True, "driver": driver, "candidates": []}
        return {"ok": True, "driver": driver, "request": request}

    async def heartbeat(self, link_id: str) -> None:
        assert self.handler
        await self.handler(
            {
                "type": "link.heartbeat",
                "payload": {"linkId": link_id, "latencyMs": 10, "packetLossPercent": 0},
            }
        )

    async def fail(self, link_id: str) -> None:
        assert self.handler
        await self.handler(
            {
                "type": "link.failed",
                "payload": {"linkId": link_id, "code": "TEST_FAILURE", "message": "test"},
            }
        )

    async def telemetry(
        self,
        link_id: str,
        device_id: str,
        fields: dict[str, Any],
        sequence: int | None = None,
    ) -> None:
        assert self.handler
        await self.handler(
            {
                "type": "telemetry.received",
                "payload": {
                    "linkId": link_id,
                    "deviceId": device_id,
                    "fields": fields,
                    "sequence": sequence,
                },
            }
        )

    async def ack(
        self,
        link_id: str,
        command_id: str,
        status: str,
        state_confirmed: bool = False,
        result: dict[str, Any] | None = None,
        reason_code: str | None = None,
    ) -> None:
        assert self.handler
        await self.handler(
            {
                "type": "command.ack",
                "payload": {
                    "linkId": link_id,
                    "commandId": command_id,
                    "status": status,
                    "stateConfirmed": state_confirmed,
                    "result": result,
                    "reasonCode": reason_code,
                },
            }
        )


@pytest.fixture
def fake_driver() -> FakeDriverGateway:
    return FakeDriverGateway()


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        database_url="sqlite:///:memory:",
        recordings_dir=tmp_path / "recordings",
        link_heartbeat_interval_seconds=10.0,
        link_missed_heartbeats=3,
        link_failback_stable_seconds=0.01,
        link_failback_debounce_seconds=0.01,
        telemetry_stale_seconds=30.0,
        command_ack_timeout_seconds=0.2,
        command_state_timeout_seconds=0.2,
    )


@pytest.fixture
def client(settings: Settings, fake_driver: FakeDriverGateway) -> Iterator[TestClient]:
    with TestClient(create_app(settings=settings, drivers=fake_driver)) as test_client:
        yield test_client


def create_connected_link(
    client: TestClient,
    *,
    device_id: str = "Hexa-UAV",
    driver: str = "simulator",
    priority: int = 10,
    role: str = "primary",
) -> dict[str, Any]:
    response = client.post(
        f"/api/v1/devices/{device_id}/links",
        json={
            "displayName": f"{driver}-{priority}",
            "driver": driver,
            "role": role,
            "priority": priority,
            "config": {"seed": priority}
            if driver == "simulator"
            else {"host": "127.0.0.1", "port": 9090},
            "enabled": True,
        },
    )
    assert response.status_code == 201, response.text
    link = response.json()
    response = client.post(f"/api/v1/devices/{device_id}/links/{link['id']}/connect")
    assert response.status_code == 202, response.text
    return link

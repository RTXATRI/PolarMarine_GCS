from __future__ import annotations

import argparse
import json
import tempfile
import time
import tracemalloc
from functools import partial
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from polarmarine_gcs.bootstrap.app import create_app
from polarmarine_gcs.bootstrap.settings import Settings
from polarmarine_gcs.domain.commands import CommandStatus, CommandType


def main() -> int:
    parser = argparse.ArgumentParser(description="Run an isolated multi-link simulator soak test")
    parser.add_argument("--duration-seconds", type=float, default=8 * 60 * 60)
    parser.add_argument("--devices", type=int, default=20)
    parser.add_argument("--links-per-device", type=int, default=2)
    parser.add_argument("--sample-seconds", type=float, default=5.0)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    if arguments.devices < 1 or arguments.devices > 20:
        parser.error("--devices must be between 1 and 20")
    if arguments.links_per_device < 1 or arguments.links_per_device > 2:
        parser.error("--links-per-device must be one or two")
    if arguments.duration_seconds <= 0 or arguments.sample_seconds <= 0:
        parser.error("durations must be positive")

    with tempfile.TemporaryDirectory(prefix="polarmarine-soak-") as temporary:
        root = Path(temporary)
        settings = Settings(
            data_dir=root,
            database_url=f"sqlite:///{(root / 'soak.sqlite3').as_posix()}",
            recordings_dir=root / "recordings",
            max_online_devices=20,
        )
        with TestClient(create_app(settings=settings)) as client:
            _provision(client, arguments.devices, arguments.links_per_device)
            _wait_until_online(client, arguments.devices)
            result = _run_load(
                client,
                duration_seconds=arguments.duration_seconds,
                device_count=arguments.devices,
                links_per_device=arguments.links_per_device,
                sample_seconds=arguments.sample_seconds,
            )
    serialized = json.dumps(result, ensure_ascii=False, indent=2)
    print(serialized)
    if arguments.output:
        arguments.output.write_text(serialized + "\n", encoding="utf-8")
    return 0 if result["failures"] == [] else 1


def _provision(client: TestClient, device_count: int, links_per_device: int) -> None:
    template = {
        "id": "soak.template",
        "displayName": "Soak simulator",
        "category": "generic",
        "description": "Isolated deterministic load test template",
        "capabilities": [
            "telemetry.read",
            "telemetry.position",
            "telemetry.battery",
            "command.manual_control",
            "command.emergency_stop",
        ],
        "parameters": [],
        "mediaChannels": [],
    }
    _require(client.post("/api/v1/device-templates", json=template), 201)
    for device_index in range(device_count):
        device_id = f"soak-{device_index + 1:02d}"
        _require(
            client.post(
                "/api/v1/devices",
                json={
                    "id": device_id,
                    "templateId": template["id"],
                    "displayName": device_id,
                    "enabled": True,
                    "tags": ["soak"],
                },
            ),
            201,
        )
        for link_index in range(links_per_device):
            link = _require(
                client.post(
                    f"/api/v1/devices/{device_id}/links",
                    json={
                        "displayName": f"sim-{link_index + 1}",
                        "driver": "simulator",
                        "role": "primary" if link_index == 0 else "auxiliary",
                        "priority": 10 + link_index * 10,
                        "config": {"seed": device_index * 10 + link_index},
                        "enabled": True,
                    },
                ),
                201,
            ).json()
            _require(
                client.post(f"/api/v1/devices/{device_id}/links/{link['id']}/connect"),
                202,
            )


def _wait_until_online(client: TestClient, expected: int) -> None:
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        payload = _require(client.get("/api/v1/bootstrap"), 200).json()
        online = sum(
            item["deviceId"].startswith("soak-") and item["status"] in {"online", "degraded"}
            for item in payload["operationalStates"]
        )
        if online == expected:
            return
        time.sleep(0.1)
    raise RuntimeError(f"Only {online}/{expected} soak devices became online")


def _run_load(
    client: TestClient,
    *,
    duration_seconds: float,
    device_count: int,
    links_per_device: int,
    sample_seconds: float,
) -> dict[str, Any]:
    tracemalloc.start()
    started = time.monotonic()
    deadline = started + duration_seconds
    next_command = started
    next_sample = started
    dispatch_milliseconds: list[float] = []
    memory_samples: list[int] = []
    failures: list[str] = []
    command_service = client.app.state.container.commands
    while time.monotonic() < deadline:
        now = time.monotonic()
        if now >= next_command:
            for device_index in range(device_count):
                command_started = time.perf_counter()
                command = client.portal.call(
                    partial(
                        command_service.submit,
                        device_id=f"soak-{device_index + 1:02d}",
                        command_type=CommandType.EMERGENCY_STOP,
                        payload={},
                    )
                )
                dispatch_milliseconds.append((time.perf_counter() - command_started) * 1_000)
                if command.status is CommandStatus.REJECTED:
                    failures.append(f"command rejected: {command.reason_code}")
            next_command = now + 30.0
        if now >= next_sample:
            payload = _require(client.get("/api/v1/bootstrap"), 200).json()
            states = {
                item["deviceId"]: item["status"]
                for item in payload["operationalStates"]
                if item["deviceId"].startswith("soak-")
            }
            snapshots = {
                item["deviceId"]
                for item in payload["telemetrySnapshots"]
                if item["deviceId"].startswith("soak-")
            }
            if len(states) != device_count or any(value == "offline" for value in states.values()):
                failures.append(f"offline state at {now - started:.1f}s")
            if len(snapshots) != device_count:
                failures.append(f"missing telemetry at {now - started:.1f}s")
            memory_samples.append(tracemalloc.get_traced_memory()[0])
            next_sample = now + sample_seconds
        time.sleep(0.02)
    current_memory, peak_memory = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    dispatch_p95 = _percentile(dispatch_milliseconds, 0.95)
    if dispatch_p95 >= 100:
        failures.append(f"core-to-driver emergency dispatch P95 was {dispatch_p95} ms")
    return {
        "durationSeconds": round(time.monotonic() - started, 3),
        "devices": device_count,
        "linksPerDevice": links_per_device,
        "targetTelemetryHzPerLink": 10,
        "coreToDriverDispatchP95Milliseconds": dispatch_p95,
        "coreToDriverDispatchMaxMilliseconds": round(max(dispatch_milliseconds, default=0), 3),
        "pythonTrackedMemoryStartBytes": memory_samples[0] if memory_samples else 0,
        "pythonTrackedMemoryEndBytes": current_memory,
        "pythonTrackedMemoryPeakBytes": peak_memory,
        "failures": sorted(set(failures)),
    }


def _percentile(values: list[float], quantile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * quantile)))
    return round(ordered[index], 3)


def _require(response: Any, expected_status: int) -> Any:
    if response.status_code != expected_status:
        raise RuntimeError(
            f"HTTP {response.status_code}, expected {expected_status}: {response.text[:500]}"
        )
    return response


if __name__ == "__main__":
    raise SystemExit(main())

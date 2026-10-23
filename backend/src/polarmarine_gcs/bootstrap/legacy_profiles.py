from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from ipaddress import IPv4Address
from pathlib import Path
from typing import Any

from polarmarine_gcs.application.events import EventService
from polarmarine_gcs.application.registry import RegistryService
from polarmarine_gcs.domain.events import AlarmSeverity, SystemEvent
from polarmarine_gcs.domain.links import DriverKind, LinkRole


async def import_legacy_device_profiles(
    path: Path,
    registry: RegistryService,
    events: EventService,
) -> None:
    """Import the removed single-link profile file once, then archive it."""

    if not await asyncio.to_thread(path.is_file):
        return
    try:
        content = await asyncio.to_thread(path.read_text, encoding="utf-8")
        document = json.loads(content)
        profiles = document.get("profiles", document) if isinstance(document, dict) else None
        if not isinstance(profiles, dict):
            raise ValueError("profiles must be an object")
        candidates, skipped = _parse_candidates(profiles, registry)
        imported = 0
        for device_id, method, driver, config in candidates:
            link_id = f"legacy:{device_id}:{method}"
            if registry.repository.get_link(link_id) is not None:
                skipped += 1
                continue
            await registry.create_link(
                device_id=device_id,
                display_name="Imported serial link" if method == "serial" else "Imported ROS1 link",
                driver=driver,
                role=LinkRole.PRIMARY,
                priority=100,
                config=config,
                enabled=True,
                link_id=link_id,
            )
            imported += 1
        archive = await asyncio.to_thread(_archive, path)
        await events.emit(
            SystemEvent(
                type="legacy_device_profiles.imported",
                aggregate_type="system",
                aggregate_id="legacy_device_profiles",
                aggregate_revision=1,
                payload={
                    "importedCount": imported,
                    "skippedCount": skipped,
                    "archiveFileName": archive.name,
                },
            )
        )
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError, KeyError) as exc:
        await events.raise_alarm(
            code="LEGACY_PROFILE_IMPORT_FAILED",
            severity=AlarmSeverity.WARNING,
            message=f"Legacy connection profiles were not imported: {exc}",
        )


def _parse_candidates(
    profiles: dict[str, Any], registry: RegistryService
) -> tuple[list[tuple[str, str, DriverKind, dict[str, Any]]], int]:
    candidates: list[tuple[str, str, DriverKind, dict[str, Any]]] = []
    skipped = 0
    for device_id, raw_profile in profiles.items():
        if not isinstance(device_id, str) or registry.repository.get_device(device_id) is None:
            skipped += 1
            continue
        if not isinstance(raw_profile, dict):
            skipped += 1
            continue
        method = raw_profile.get("method")
        try:
            if method == "serial":
                port = raw_profile["port"]
                baud_rate = raw_profile.get("baudRate", 115200)
                if (
                    not isinstance(port, str)
                    or not port.strip()
                    or baud_rate not in {9600, 19200, 38400, 57600, 115200}
                ):
                    raise ValueError
                candidates.append(
                    (
                        device_id,
                        method,
                        DriverKind.SERIAL_JSON,
                        {"port": port.strip(), "baudRate": baud_rate},
                    )
                )
            elif method == "network":
                host = str(IPv4Address(raw_profile["host"]))
                port = raw_profile["port"]
                if not isinstance(port, int) or not 1 <= port <= 65535:
                    raise ValueError
                candidates.append(
                    (device_id, method, DriverKind.ROS1, {"host": host, "port": port})
                )
            else:
                skipped += 1
        except (ValueError, KeyError):
            skipped += 1
    return candidates, skipped


def _archive(path: Path) -> Path:
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    destination = path.with_name(f"{path.name}.imported-{timestamp}")
    path.replace(destination)
    return destination

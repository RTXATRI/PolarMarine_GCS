from __future__ import annotations

import asyncio
import math
from collections.abc import Awaitable, Callable
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

from polarmarine_gcs.application.events import EventService
from polarmarine_gcs.application.links import LinkCoordinator
from polarmarine_gcs.domain.common import utc_now
from polarmarine_gcs.domain.links import DriverKind
from polarmarine_gcs.domain.sequences import SequenceDisposition, SequenceTracker
from polarmarine_gcs.domain.telemetry import (
    TelemetryQuality,
    TelemetrySnapshot,
    TelemetryValue,
)

RecordCallback = Callable[[str, dict[str, Any], datetime], Awaitable[None]]


class TelemetryService:
    def __init__(
        self,
        events: EventService,
        links: LinkCoordinator,
        *,
        stale_after_seconds: float = 3.0,
    ) -> None:
        self.events = events
        self.links = links
        self.stale_after_seconds = stale_after_seconds
        self.snapshots: dict[str, TelemetrySnapshot] = {}
        self._group_sources: dict[tuple[str, str], str] = {}
        self._sequences = SequenceTracker()
        self._monitor_task: asyncio.Task[None] | None = None
        self._recorder: RecordCallback | None = None

    def set_recorder(self, recorder: RecordCallback) -> None:
        self._recorder = recorder

    async def start(self) -> None:
        if self._monitor_task is None:
            self._monitor_task = asyncio.create_task(
                self._monitor(), name="telemetry-quality-monitor"
            )

    async def stop(self) -> None:
        if self._monitor_task is not None:
            self._monitor_task.cancel()
            await asyncio.gather(self._monitor_task, return_exceptions=True)
            self._monitor_task = None
        self.snapshots.clear()
        self._group_sources.clear()
        self._sequences.clear()

    async def handle_driver_event(self, message: dict[str, Any]) -> None:
        payload = message.get("payload")
        if not isinstance(payload, dict):
            return
        link_id = payload.get("linkId")
        device_id = payload.get("deviceId")
        fields = payload.get("fields")
        if (
            not isinstance(link_id, str)
            or not isinstance(device_id, str)
            or not isinstance(fields, dict)
        ):
            return
        session = self.links.get_session(link_id)
        if session is None or session.device_id != device_id:
            return
        sequence = payload.get("sequence")
        if sequence is not None:
            if isinstance(sequence, bool) or not isinstance(sequence, int):
                return
            stream_id = f"{link_id}:{session.started_at.isoformat() if session.started_at else ''}"
            try:
                disposition = self._sequences.observe(stream_id, sequence)
            except ValueError:
                return
            if disposition is not SequenceDisposition.NEW:
                return
        received_at = utc_now()
        snapshot = self.snapshots.setdefault(device_id, TelemetrySnapshot(device_id=device_id))
        changed: dict[str, TelemetryValue] = {}
        for field_name, raw in fields.items():
            if not isinstance(field_name, str) or not isinstance(raw, dict):
                continue
            group = _signal_group(field_name)
            active_link = self.links.operational_state(device_id).active_link_id
            selected_source = self._group_sources.get((device_id, group))
            if active_link and link_id != active_link and selected_source is not None:
                continue
            value = raw.get("value")
            collected_at = _parse_time(raw.get("collectedAt")) or received_at
            quality = _quality(raw.get("quality"))
            if session.driver is DriverKind.SIMULATOR:
                quality = TelemetryQuality.SIMULATED
            if field_name in {
                "position.latitude",
                "position.longitude",
            } and not _in_coordinate_range(field_name, value):
                quality = TelemetryQuality.INVALID
                value = None
            sample = TelemetryValue(
                value=value,
                source_link_id=link_id,
                collected_at=collected_at,
                received_at=received_at,
                quality=quality,
                unit=raw.get("unit") if isinstance(raw.get("unit"), str) else None,
            )
            snapshot.fields[field_name] = sample
            self._group_sources[(device_id, group)] = link_id
            changed[field_name] = sample
        _invalidate_incomplete_position(snapshot, changed, received_at)
        _invalidate_zero_coordinate_pair(snapshot, changed, received_at)
        if not changed:
            return
        snapshot.revision += 1
        snapshot.updated_at = received_at
        event_payload = {
            "deviceId": device_id,
            "fields": {name: _value_payload(value) for name, value in changed.items()},
            "updatedAt": received_at.isoformat(),
        }
        await self.events.transient(
            type="telemetry.updated",
            aggregate_type="telemetry_snapshot",
            aggregate_id=device_id,
            aggregate_revision=snapshot.revision,
            payload=event_payload,
        )
        if self._recorder:
            await self._recorder(device_id, event_payload, received_at)

    def get_snapshot(self, device_id: str) -> TelemetrySnapshot | None:
        return self.snapshots.get(device_id)

    def list_snapshots(self) -> list[TelemetrySnapshot]:
        return sorted(self.snapshots.values(), key=lambda item: item.device_id)

    async def _monitor(self) -> None:
        while True:
            await asyncio.sleep(min(1.0, self.stale_after_seconds / 2))
            now = utc_now()
            for snapshot in list(self.snapshots.values()):
                changed: dict[str, TelemetryValue] = {}
                for name, sample in list(snapshot.fields.items()):
                    age = (now - sample.received_at).total_seconds()
                    if age >= self.stale_after_seconds and sample.quality not in {
                        TelemetryQuality.STALE,
                        TelemetryQuality.INVALID,
                    }:
                        stale = replace(sample, quality=TelemetryQuality.STALE)
                        snapshot.fields[name] = stale
                        changed[name] = stale
                if changed:
                    snapshot.revision += 1
                    await self.events.transient(
                        type="telemetry.quality_changed",
                        aggregate_type="telemetry_snapshot",
                        aggregate_id=snapshot.device_id,
                        aggregate_revision=snapshot.revision,
                        payload={
                            "deviceId": snapshot.device_id,
                            "fields": {
                                name: _value_payload(value) for name, value in changed.items()
                            },
                            "updatedAt": now.isoformat(),
                        },
                    )


def snapshot_payload(snapshot: TelemetrySnapshot) -> dict[str, Any]:
    return {
        "deviceId": snapshot.device_id,
        "fields": {name: _value_payload(value) for name, value in snapshot.fields.items()},
        "revision": snapshot.revision,
        "updatedAt": snapshot.updated_at.isoformat(),
    }


def _value_payload(value: TelemetryValue) -> dict[str, Any]:
    return {
        "value": value.value,
        "sourceLinkId": value.source_link_id,
        "collectedAt": value.collected_at.isoformat(),
        "receivedAt": value.received_at.isoformat(),
        "quality": value.quality.value,
        "unit": value.unit,
    }


def _signal_group(field_name: str) -> str:
    if field_name.startswith("position.") or field_name in {"speed", "heading"}:
        return "navigation"
    if field_name.startswith("battery.") or field_name.startswith("power."):
        return "power"
    if field_name.startswith("link."):
        return "link"
    if field_name.startswith("mission."):
        return "mission"
    if field_name.startswith("control."):
        return "control"
    return field_name.split(".", maxsplit=1)[0]


def _parse_time(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(UTC)


def _quality(value: object) -> TelemetryQuality:
    if not isinstance(value, str):
        return TelemetryQuality.VALID
    try:
        return TelemetryQuality(value)
    except ValueError:
        return TelemetryQuality.VALID


def _in_coordinate_range(field_name: str, value: object) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        return False
    if field_name == "position.latitude":
        return -90 <= value <= 90
    return -180 <= value <= 180


def _invalidate_zero_coordinate_pair(
    snapshot: TelemetrySnapshot,
    changed: dict[str, TelemetryValue],
    received_at: datetime,
) -> None:
    latitude = snapshot.fields.get("position.latitude")
    longitude = snapshot.fields.get("position.longitude")
    if latitude is None or longitude is None:
        return
    if latitude.value != 0 or longitude.value != 0:
        return
    for name, sample in (
        ("position.latitude", latitude),
        ("position.longitude", longitude),
    ):
        invalid = replace(
            sample, value=None, received_at=received_at, quality=TelemetryQuality.INVALID
        )
        snapshot.fields[name] = invalid
        changed[name] = invalid


def _invalidate_incomplete_position(
    snapshot: TelemetrySnapshot,
    changed: dict[str, TelemetryValue],
    received_at: datetime,
) -> None:
    latitude = snapshot.fields.get("position.latitude")
    longitude = snapshot.fields.get("position.longitude")
    if latitude is None and longitude is None:
        return
    if latitude is not None and longitude is not None:
        return
    missing_name = "position.latitude" if latitude is None else "position.longitude"
    present = latitude or longitude
    if present is None:
        return
    invalid = TelemetryValue(
        value=None,
        source_link_id=present.source_link_id,
        collected_at=present.collected_at,
        received_at=received_at,
        quality=TelemetryQuality.INVALID,
        unit="deg",
    )
    snapshot.fields[missing_name] = invalid
    changed[missing_name] = invalid

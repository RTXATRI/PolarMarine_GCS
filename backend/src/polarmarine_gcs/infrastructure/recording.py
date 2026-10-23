from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import timedelta
from importlib import import_module
from pathlib import Path
from typing import Any, BinaryIO, Protocol, cast

from mcap.exceptions import EndOfFile
from mcap.reader import NonSeekingReader, make_reader

from polarmarine_gcs.application.ports.repositories import Repository
from polarmarine_gcs.domain.common import ConflictError, NotFoundError, new_id, utc_now
from polarmarine_gcs.domain.recordings import Recording, RecordingStatus


@dataclass(slots=True)
class _ActiveRecording:
    record: Recording
    device_ids: frozenset[str]
    stream: BinaryIO
    writer: _McapWriter
    normalized_channel_id: int
    raw_channel_id: int


class McapRecordingService:
    def __init__(
        self,
        repository: Repository,
        root: Path,
        *,
        retention_days: int = 30,
        retention_bytes: int = 20 * 1024 * 1024 * 1024,
    ) -> None:
        self.repository = repository
        self.root = root
        self.retention_days = retention_days
        self.retention_bytes = retention_bytes
        self._active: dict[str, _ActiveRecording] = {}
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        for recording in self.repository.list_recordings():
            if recording.status is RecordingStatus.ACTIVE:
                path = Path(recording.path)
                recording.status = RecordingStatus.INTERRUPTED
                recording.ended_at = utc_now()
                recording.size_bytes = await asyncio.to_thread(_file_size, path)
                self.repository.save_recording(recording)
        await self.cleanup()

    async def stop(self) -> None:
        for mission_run_id in list(self._active):
            await self.finish(mission_run_id, interrupted=True)

    async def begin(self, mission_run_id: str, device_ids: frozenset[str]) -> Recording:
        async with self._lock:
            existing = self._active.get(mission_run_id)
            if existing:
                return existing.record
            recording_id = new_id()
            path = self.root / f"{mission_run_id}-{recording_id}.mcap"
            stream = path.open("wb")
            writer = _create_writer(stream)
            writer.start(profile="polarmarine-gcs", library="polarmarine-gcs")
            schema_data = json.dumps(
                {
                    "$schema": "https://json-schema.org/draft/2020-12/schema",
                    "title": "PolarMarineEvent",
                    "type": "object",
                },
                separators=(",", ":"),
            ).encode("utf-8")
            schema_id = writer.register_schema(
                name="polarmarine.event.v1",
                encoding="jsonschema",
                data=schema_data,
            )
            normalized_channel_id = writer.register_channel(
                topic="/polarmarine/normalized/telemetry",
                message_encoding="json",
                schema_id=schema_id,
            )
            raw_channel_id = writer.register_channel(
                topic="/polarmarine/raw",
                message_encoding="json",
                schema_id=schema_id,
            )
            record = Recording(
                id=recording_id,
                mission_run_id=mission_run_id,
                path=str(path),
                status=RecordingStatus.ACTIVE,
            )
            self.repository.save_recording(record)
            self._active[mission_run_id] = _ActiveRecording(
                record=record,
                device_ids=device_ids,
                stream=stream,
                writer=writer,
                normalized_channel_id=normalized_channel_id,
                raw_channel_id=raw_channel_id,
            )
            return record

    async def record_normalized(
        self,
        device_id: str,
        payload: dict[str, Any],
        timestamp: Any,
    ) -> None:
        await self._write_all(
            channel="normalized",
            payload={"deviceId": device_id, "payload": payload},
            timestamp_ns=int(timestamp.timestamp() * 1_000_000_000),
            device_id=device_id,
        )

    async def record_raw(self, payload: dict[str, Any]) -> None:
        now = utc_now()
        device_id = self._raw_device_id(payload)
        await self._write_all(
            channel="raw",
            payload=payload,
            timestamp_ns=int(now.timestamp() * 1_000_000_000),
            device_id=device_id,
        )

    async def finish(self, mission_run_id: str, *, interrupted: bool = False) -> Recording | None:
        async with self._lock:
            active = self._active.pop(mission_run_id, None)
            if active is None:
                return None
            active.writer.finish()
            active.stream.flush()
            active.stream.close()
            active.record.status = (
                RecordingStatus.INTERRUPTED if interrupted else RecordingStatus.COMPLETE
            )
            active.record.ended_at = utc_now()
            path = Path(active.record.path)
            active.record.size_bytes = await asyncio.to_thread(_file_size, path)
            self.repository.save_recording(active.record)
        await self.cleanup()
        return active.record

    async def cleanup(self) -> None:
        recordings = [
            item
            for item in self.repository.list_recordings()
            if item.status is not RecordingStatus.ACTIVE
        ]
        recordings.sort(key=lambda item: item.ended_at or item.started_at)
        total_size = sum(item.size_bytes for item in recordings)
        cutoff = utc_now() - timedelta(days=self.retention_days)
        root = await asyncio.to_thread(self.root.resolve)
        for recording in recordings:
            expired = (recording.ended_at or recording.started_at) < cutoff
            over_budget = total_size > self.retention_bytes
            if not expired and not over_budget:
                continue
            await asyncio.to_thread(_delete_recording_file, Path(recording.path), root)
            total_size -= recording.size_bytes
            self.repository.delete_recording(recording.id)

    def recording_path(self, recording_id: str) -> Path:
        recording = self.repository.get_recording(recording_id)
        if recording is None:
            raise NotFoundError(f"Recording {recording_id} does not exist")
        if recording.status is RecordingStatus.ACTIVE:
            raise ConflictError("An active recording cannot be downloaded or replayed")
        path = Path(recording.path).resolve()
        root = self.root.resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise NotFoundError(f"Recording file {recording_id} is unavailable")
        return path

    def read_messages(
        self,
        recording_id: str,
        *,
        start_time_ns: int | None = None,
        end_time_ns: int | None = None,
        limit: int = 1_000,
    ) -> list[dict[str, Any]]:
        recording = self.repository.get_recording(recording_id)
        path = self.recording_path(recording_id)
        messages: list[dict[str, Any]] = []
        with path.open("rb") as stream:
            reader = (
                NonSeekingReader(stream)
                if recording and recording.status is RecordingStatus.INTERRUPTED
                else make_reader(stream)
            )
            try:
                iterator = reader.iter_messages(
                    start_time=start_time_ns,
                    end_time=end_time_ns,
                    log_time_order=not (
                        recording and recording.status is RecordingStatus.INTERRUPTED
                    ),
                )
                for _schema, channel, message in iterator:
                    try:
                        payload: Any = json.loads(message.data)
                    except (UnicodeDecodeError, json.JSONDecodeError):
                        payload = {"encoding": "binary", "sizeBytes": len(message.data)}
                    messages.append(
                        {
                            "topic": channel.topic,
                            "logTimeNs": message.log_time,
                            "publishTimeNs": message.publish_time,
                            "payload": payload,
                        }
                    )
                    if len(messages) >= limit:
                        break
            except EndOfFile:
                pass
        return messages

    async def _write_all(
        self,
        *,
        channel: str,
        payload: dict[str, Any],
        timestamp_ns: int,
        device_id: str | None,
    ) -> None:
        data = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        async with self._lock:
            for active in self._active.values():
                if device_id is None or device_id not in active.device_ids:
                    continue
                channel_id = (
                    active.normalized_channel_id
                    if channel == "normalized"
                    else active.raw_channel_id
                )
                active.writer.add_message(
                    channel_id=channel_id,
                    log_time=timestamp_ns,
                    publish_time=timestamp_ns,
                    data=data,
                )

    def _raw_device_id(self, message: dict[str, Any]) -> str | None:
        payload = message.get("payload")
        if not isinstance(payload, dict):
            return None
        device_id = payload.get("deviceId")
        if isinstance(device_id, str):
            return device_id
        link_id = payload.get("linkId")
        if not isinstance(link_id, str):
            return None
        profile = self.repository.get_link(link_id)
        return profile.device_id if profile else None


def _file_size(path: Path) -> int:
    return path.stat().st_size if path.exists() else 0


def _delete_recording_file(path: Path, root: Path) -> None:
    resolved = path.resolve()
    if resolved.is_relative_to(root) and resolved.is_file():
        resolved.unlink()


class _McapWriter(Protocol):
    def start(self, *, profile: str = "", library: str = "") -> None: ...

    def register_schema(self, *, name: str, encoding: str, data: bytes) -> int: ...

    def register_channel(self, *, topic: str, message_encoding: str, schema_id: int) -> int: ...

    def add_message(
        self,
        *,
        channel_id: int,
        log_time: int,
        data: bytes,
        publish_time: int,
    ) -> None: ...

    def finish(self) -> None: ...


def _create_writer(stream: BinaryIO) -> _McapWriter:
    writer_factory = import_module("mcap.writer").Writer
    return cast(_McapWriter, writer_factory(stream))

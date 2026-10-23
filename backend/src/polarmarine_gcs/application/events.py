from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import uuid4

from polarmarine_gcs.application.ports.repositories import Repository
from polarmarine_gcs.domain.common import new_id, utc_now
from polarmarine_gcs.domain.events import Alarm, AlarmSeverity, SystemEvent


@dataclass(frozen=True, slots=True)
class StreamEvent:
    schema_version: str
    event_id: str
    server_instance_id: str
    connection_sequence: int
    event_cursor: int | None
    aggregate_type: str
    aggregate_id: str
    aggregate_revision: int
    occurred_at: datetime
    type: str
    payload: dict[str, Any]


class EventBroker:
    def __init__(self, queue_size: int = 1_000) -> None:
        self.server_instance_id = str(uuid4())
        self._queue_size = queue_size
        self._sequence = 0
        self._subscribers: set[asyncio.Queue[StreamEvent]] = set()
        self._lock = asyncio.Lock()

    @property
    def current_sequence(self) -> int:
        return self._sequence

    async def publish(self, event: SystemEvent) -> StreamEvent:
        async with self._lock:
            self._sequence += 1
            stream_event = StreamEvent(
                schema_version="1.0",
                event_id=event.id,
                server_instance_id=self.server_instance_id,
                connection_sequence=self._sequence,
                event_cursor=event.cursor,
                aggregate_type=event.aggregate_type,
                aggregate_id=event.aggregate_id,
                aggregate_revision=event.aggregate_revision,
                occurred_at=event.occurred_at,
                type=event.type,
                payload=event.payload,
            )
            for queue in tuple(self._subscribers):
                if queue.full():
                    queue.get_nowait()
                queue.put_nowait(stream_event)
            return stream_event

    @asynccontextmanager
    async def subscribe(self) -> AsyncIterator[asyncio.Queue[StreamEvent]]:
        queue: asyncio.Queue[StreamEvent] = asyncio.Queue(maxsize=self._queue_size)
        self._subscribers.add(queue)
        try:
            yield queue
        finally:
            self._subscribers.discard(queue)


class EventService:
    def __init__(self, repository: Repository, broker: EventBroker) -> None:
        self.repository = repository
        self.broker = broker

    async def emit(self, event: SystemEvent, *, persistent: bool = True) -> StreamEvent:
        if persistent:
            self.repository.append_event(event)
        return await self.broker.publish(event)

    async def transient(
        self,
        *,
        type: str,
        aggregate_type: str,
        aggregate_id: str,
        aggregate_revision: int,
        payload: dict[str, Any],
    ) -> StreamEvent:
        return await self.emit(
            SystemEvent(
                type=type,
                aggregate_type=aggregate_type,
                aggregate_id=aggregate_id,
                aggregate_revision=aggregate_revision,
                payload=payload,
            ),
            persistent=False,
        )

    async def raise_alarm(
        self,
        *,
        code: str,
        severity: AlarmSeverity,
        message: str,
        device_id: str | None = None,
    ) -> Alarm:
        alarm = Alarm(
            id=new_id(),
            code=code,
            severity=severity,
            message=message,
            device_id=device_id,
        )
        self.repository.save_alarm(alarm)
        await self.emit(
            SystemEvent(
                type="alarm.raised",
                aggregate_type="alarm",
                aggregate_id=alarm.id,
                aggregate_revision=alarm.revision,
                payload={
                    "code": alarm.code,
                    "severity": alarm.severity.value,
                    "message": alarm.message,
                    "deviceId": alarm.device_id,
                },
            )
        )
        return alarm

    async def acknowledge_alarm(self, alarm_id: str) -> Alarm:
        alarm = self.repository.get_alarm(alarm_id)
        if alarm is None:
            from polarmarine_gcs.domain.common import NotFoundError

            raise NotFoundError(f"Alarm {alarm_id} does not exist")
        if not alarm.acknowledged:
            alarm.acknowledged = True
            alarm.acknowledged_at = utc_now()
            alarm.revision += 1
            self.repository.save_alarm(alarm)
            await self.emit(
                SystemEvent(
                    type="alarm.acknowledged",
                    aggregate_type="alarm",
                    aggregate_id=alarm.id,
                    aggregate_revision=alarm.revision,
                    payload={"acknowledgedAt": alarm.acknowledged_at.isoformat()},
                )
            )
        return alarm

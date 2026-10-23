from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.encoders import jsonable_encoder

from polarmarine_gcs.application.events import StreamEvent
from polarmarine_gcs.bootstrap.container import Container

router = APIRouter()


@router.websocket("/events")
async def event_stream(websocket: WebSocket) -> None:
    await websocket.accept()
    container: Container = websocket.app.state.container
    after_raw = websocket.query_params.get("after", "0")
    try:
        after = max(0, int(after_raw))
    except ValueError:
        after = 0
    try:
        async with container.broker.subscribe() as queue:
            latest_cursor = container.repository.latest_event_cursor()
            ready = {
                "schemaVersion": "1.0",
                "eventId": str(uuid4()),
                "serverInstanceId": container.broker.server_instance_id,
                "connectionSequence": container.broker.current_sequence,
                "eventCursor": latest_cursor,
                "aggregateType": "stream",
                "aggregateId": container.broker.server_instance_id,
                "aggregateRevision": 1,
                "occurredAt": datetime.now(UTC).isoformat(),
                "type": "stream.ready",
                "payload": {
                    "resyncRequired": after != latest_cursor,
                    "requestedCursor": after,
                    "latestCursor": latest_cursor,
                },
            }
            await websocket.send_json(ready)
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                    await websocket.send_json(jsonable_encoder(_stream_payload(event)))
                except TimeoutError:
                    heartbeat = {
                        "schemaVersion": "1.0",
                        "eventId": str(uuid4()),
                        "serverInstanceId": container.broker.server_instance_id,
                        "connectionSequence": container.broker.current_sequence,
                        "eventCursor": container.repository.latest_event_cursor(),
                        "aggregateType": "stream",
                        "aggregateId": container.broker.server_instance_id,
                        "aggregateRevision": 1,
                        "occurredAt": datetime.now(UTC).isoformat(),
                        "type": "stream.heartbeat",
                        "payload": {},
                    }
                    await websocket.send_json(heartbeat)
    except (WebSocketDisconnect, RuntimeError):
        return


def _stream_payload(event: StreamEvent) -> dict[str, object]:
    return {
        "schemaVersion": event.schema_version,
        "eventId": event.event_id,
        "serverInstanceId": event.server_instance_id,
        "connectionSequence": event.connection_sequence,
        "eventCursor": event.event_cursor,
        "aggregateType": event.aggregate_type,
        "aggregateId": event.aggregate_id,
        "aggregateRevision": event.aggregate_revision,
        "occurredAt": event.occurred_at,
        "type": event.type,
        "payload": event.payload,
    }

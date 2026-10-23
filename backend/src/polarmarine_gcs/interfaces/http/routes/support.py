from __future__ import annotations

import io
import json
import platform
import zipfile
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from polarmarine_gcs.bootstrap.container import Container
from polarmarine_gcs.interfaces.http.dependencies import get_container
from polarmarine_gcs.interfaces.http.presenters import (
    alarm_dto,
    device_dto,
    event_dto,
    link_dto,
    session_dto,
    template_dto,
)

router = APIRouter()
SENSITIVE_KEY_PARTS = ("password", "secret", "token", "credential", "api_key", "apikey")


@router.get("/support-bundle")
def support_bundle(container: Container = Depends(get_container)) -> StreamingResponse:
    manifest = {
        "schemaVersion": "1.0",
        "createdAt": datetime.now(UTC).isoformat(),
        "applicationVersion": container.settings.app_version,
        "environment": container.settings.environment,
        "platform": platform.platform(),
        "serverInstanceId": container.broker.server_instance_id,
    }
    snapshot = {
        "templates": [
            item.model_dump(mode="json", by_alias=True)
            for item in map(template_dto, container.repository.list_templates())
        ],
        "devices": [
            item.model_dump(mode="json", by_alias=True)
            for item in map(device_dto, container.repository.list_devices())
        ],
        "links": [
            _redact(item.model_dump(mode="json", by_alias=True))
            for item in map(link_dto, container.repository.list_links())
        ],
        "linkSessions": [
            item.model_dump(mode="json", by_alias=True)
            for item in map(session_dto, container.links.list_sessions())
        ],
        "alarms": [
            item.model_dump(mode="json", by_alias=True)
            for item in map(alarm_dto, container.repository.list_alarms(limit=1_000))
        ],
        "events": [
            item.model_dump(mode="json", by_alias=True)
            for item in map(
                event_dto,
                container.repository.list_events(limit=1_000),
            )
        ],
    }
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        bundle.writestr("manifest.json", _json_bytes(manifest))
        bundle.writestr("system-snapshot.json", _json_bytes(_redact(snapshot)))
    content = archive.getvalue()
    filename = f"polarmarine-support-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.zip"
    return StreamingResponse(
        iter((content,)),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _redact(value: Any, *, key: str = "") -> Any:
    lowered = key.lower()
    if lowered == "ak" or any(part in lowered for part in SENSITIVE_KEY_PARTS):
        return "[REDACTED]"
    if isinstance(value, dict):
        return {str(item_key): _redact(item, key=str(item_key)) for item_key, item in value.items()}
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")

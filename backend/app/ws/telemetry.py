from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.services.state import state_service

router = APIRouter()


class TelemetryManager:
    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.add(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        self._connections.discard(websocket)

    async def broadcast(self, message: dict) -> None:
        disconnected: list[WebSocket] = []
        for websocket in list(self._connections):
            try:
                await websocket.send_json(message)
            except Exception:
                disconnected.append(websocket)
        for websocket in disconnected:
            self.disconnect(websocket)


telemetry_manager = TelemetryManager()


@router.websocket("/ws/telemetry")
async def telemetry_socket(websocket: WebSocket) -> None:
    await telemetry_manager.connect(websocket)
    await websocket.send_json({"type": "robot_state", "data": [robot.model_dump(mode="json") for robot in state_service.list_robots()]})
    await websocket.send_json({"type": "log_snapshot", "data": [log.model_dump(mode="json") for log in state_service.list_logs()]})
    await websocket.send_json({"type": "alarm_snapshot", "data": [alarm.model_dump(mode="json") for alarm in state_service.list_alarms()]})
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        telemetry_manager.disconnect(websocket)

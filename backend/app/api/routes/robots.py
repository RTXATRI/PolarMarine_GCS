from fastapi import APIRouter, HTTPException

from app.models.schemas import ConnectionProfile, Robot
from app.services import connections as connections_module
from app.services.connections import ConnectionServiceError
from app.services.state import state_service

router = APIRouter()


@router.get("", response_model=list[Robot])
def list_robots() -> list[Robot]:
    return state_service.list_robots()


@router.get("/{robot_id}", response_model=Robot)
def get_robot(robot_id: str) -> Robot:
    robot = state_service.get_robot(robot_id)
    if not robot:
        raise HTTPException(status_code=404, detail="robot not found")
    return robot


def get_connection_manager() -> connections_module.ConnectionManager:
    manager = connections_module.connection_manager
    if manager is None:
        raise HTTPException(
            status_code=503,
            detail={"code": "CONNECTION_SERVICE_UNAVAILABLE", "message": "连接服务尚未就绪", "robot": None},
        )
    return manager


def raise_connection_error(exc: ConnectionServiceError) -> None:
    raise HTTPException(status_code=exc.status_code, detail=exc.detail()) from exc


@router.post("/{robot_id}/connection", response_model=Robot)
async def connect_robot(robot_id: str, payload: ConnectionProfile) -> Robot:
    try:
        return await get_connection_manager().connect(robot_id, payload)
    except ConnectionServiceError as exc:
        raise_connection_error(exc)


@router.delete("/{robot_id}/connection", response_model=Robot)
async def disconnect_robot(robot_id: str) -> Robot:
    try:
        return await get_connection_manager().disconnect(robot_id)
    except ConnectionServiceError as exc:
        raise_connection_error(exc)

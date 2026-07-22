from fastapi import APIRouter, HTTPException, Query

from app.models.schemas import NetworkCandidate, SerialPortInfo
from app.services import connections as connections_module

router = APIRouter()


def get_manager() -> connections_module.ConnectionManager:
    manager = connections_module.connection_manager
    if manager is None:
        raise HTTPException(
            status_code=503,
            detail={"code": "CONNECTION_SERVICE_UNAVAILABLE", "message": "连接服务尚未就绪", "robot": None},
        )
    return manager


@router.get("/serial-ports", response_model=list[SerialPortInfo])
async def serial_ports() -> list[SerialPortInfo]:
    try:
        return await get_manager().list_serial_ports()
    except connections_module.ConnectionServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail()) from exc


@router.get("/network-candidates", response_model=list[NetworkCandidate])
async def network_candidates(port: int = Query(default=9090, ge=1, le=65535)) -> list[NetworkCandidate]:
    return await get_manager().discover_network_candidates(port)

from fastapi import APIRouter

from app.core.config import get_settings
from app.models.schemas import HealthResponse
from app.services import connections as connections_module

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    settings = get_settings()
    manager = connections_module.connection_manager
    connected_count = manager.connected_ros_count if manager else 0
    return HealthResponse(
        status="ok",
        app=settings.app_name,
        rosbridgeConnected=connected_count > 0,
        rosbridgeConnectedCount=connected_count,
        mockSimulatorEnabled=settings.mock_simulator_enabled,
    )

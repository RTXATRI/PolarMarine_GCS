import json

from fastapi import APIRouter, Depends, Query

from polarmarine_gcs.bootstrap.container import Container
from polarmarine_gcs.domain.common import ValidationError
from polarmarine_gcs.domain.links import DriverKind
from polarmarine_gcs.interfaces.http.dependencies import get_container
from polarmarine_gcs.interfaces.http.schemas import (
    NetworkDiscoveryResponse,
    RosDebugRequest,
)

router = APIRouter()


@router.get("/discovery/network", response_model=NetworkDiscoveryResponse)
async def network_discovery(
    driver: DriverKind = Query(default=DriverKind.ROS1),
    timeout_seconds: float = Query(default=1.5, alias="timeoutSeconds", ge=0.2, le=3.0),
    container: Container = Depends(get_container),
) -> NetworkDiscoveryResponse:
    if driver not in {DriverKind.ROS1, DriverKind.ROS2}:
        raise ValidationError("Network identity discovery only supports ROS1 or ROS2")
    result = await container.drivers.debug_request(
        driver.value,
        {"operation": "discover", "timeoutSeconds": timeout_seconds},
    )
    return NetworkDiscoveryResponse.model_validate(result)


@router.post("/debug/ros", response_model=dict[str, object])
async def ros_debug(
    body: RosDebugRequest,
    container: Container = Depends(get_container),
) -> dict[str, object]:
    profile = container.registry.require_link(body.link_id)
    if profile.driver not in {DriverKind.ROS1, DriverKind.ROS2}:
        raise ValidationError("ROS debug operations require a ROS1 or ROS2 link")
    session = container.links.get_session(body.link_id)
    if session is None or not session.debug_available:
        raise ValidationError("ROS debug operations require an active link session")
    request = body.model_dump(by_alias=True, exclude_none=True)
    if len(json.dumps(request, ensure_ascii=False).encode("utf-8")) > 256 * 1024:
        raise ValidationError("ROS debug message exceeds 256 KiB")
    result = await container.drivers.debug_request(profile.driver.value, request)
    return {str(key): value for key, value in result.items()}


@router.get("/debug/serial/ports", response_model=dict[str, object])
async def serial_ports(container: Container = Depends(get_container)) -> dict[str, object]:
    result = await container.drivers.debug_request(
        DriverKind.SERIAL_JSON.value,
        {"operation": "list_ports"},
    )
    return {str(key): value for key, value in result.items()}

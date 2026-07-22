from fastapi import APIRouter, HTTPException

from app.api.routes.connections import get_manager
from app.models.schemas import ElectromagneticFixRequest, LockCommandRequest, ManualCommandRequest, ModeCommandRequest, NavigationStartRequest, Robot, RobotCommandRequest
from app.services.connections import ConnectionServiceError
from app.services.state import state_service

router = APIRouter()


def require_result(robot: Robot | None) -> Robot:
    if not robot:
        raise HTTPException(status_code=404, detail="robot not found")
    return robot


def require_command_channel(robot_id: str) -> Robot:
    robot = state_service.get_robot(robot_id)
    if not robot:
        raise HTTPException(status_code=404, detail="robot not found")
    if robot.connection.state != "connected":
        raise HTTPException(
            status_code=409,
            detail={
                "code": "DEVICE_NOT_CONNECTED",
                "message": "设备尚未连接",
                "robot": robot.model_dump(mode="json"),
            },
        )
    if robot.connection.commandMode not in ("virtual", "live"):
        raise HTTPException(
            status_code=409,
            detail={
                "code": "DATA_CHANNEL_UNAVAILABLE",
                "message": "连接已建立，但当前连接不支持操作反馈",
                "robot": robot.model_dump(mode="json"),
            },
        )
    return robot


@router.post("/manual", response_model=Robot)
def manual_command(payload: ManualCommandRequest) -> Robot:
    require_command_channel(payload.robotId)
    return require_result(state_service.apply_manual_command(payload.robotId, payload.command, payload.speed))


@router.post("/mode", response_model=Robot)
def mode_command(payload: ModeCommandRequest) -> Robot:
    require_command_channel(payload.robotId)
    return require_result(state_service.set_mode(payload.robotId, payload.mode))


@router.post("/lock", response_model=Robot)
def lock_command(payload: LockCommandRequest) -> Robot:
    require_command_channel(payload.robotId)
    return require_result(state_service.set_unlocked(payload.robotId, payload.unlocked))


@router.post("/emergency-stop", response_model=Robot)
def emergency_stop(payload: RobotCommandRequest) -> Robot:
    require_command_channel(payload.robotId)
    return require_result(state_service.emergency_stop(payload.robotId))


@router.post('/electromagnetic-fix', response_model=Robot)
async def electromagnetic_fix(payload: ElectromagneticFixRequest) -> Robot:
    try:
        return await get_manager().set_electromagnetic_fix(payload.robotId, payload.enabled)
    except ConnectionServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail()) from exc


@router.post("/navigation/start", response_model=Robot)
def navigation_start(payload: NavigationStartRequest) -> Robot:
    require_command_channel(payload.robotId)
    return require_result(state_service.start_navigation(payload.robotId, payload.goals))


@router.post("/navigation/pause", response_model=Robot)
def navigation_pause(payload: RobotCommandRequest) -> Robot:
    require_command_channel(payload.robotId)
    return require_result(state_service.pause_navigation(payload.robotId))


@router.post("/navigation/resume", response_model=Robot)
def navigation_resume(payload: RobotCommandRequest) -> Robot:
    require_command_channel(payload.robotId)
    return require_result(state_service.resume_navigation(payload.robotId))


@router.post("/navigation/stop", response_model=Robot)
def navigation_stop(payload: RobotCommandRequest) -> Robot:
    require_command_channel(payload.robotId)
    return require_result(state_service.stop_navigation(payload.robotId))


@router.post("/navigation/return-home", response_model=Robot)
def navigation_return_home(payload: RobotCommandRequest) -> Robot:
    require_command_channel(payload.robotId)
    return require_result(state_service.return_home(payload.robotId))

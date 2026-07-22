from fastapi import APIRouter, Query

from app.models.schemas import Parameter, ParametersUpdateRequest
from app.api.routes.commands import require_command_channel
from app.services.state import state_service

router = APIRouter()


@router.get("", response_model=list[Parameter])
def list_parameters(robot_id: str = Query(alias="robotId")) -> list[Parameter]:
    require_command_channel(robot_id)
    return state_service.list_parameters()


@router.put("", response_model=list[Parameter])
def update_parameters(payload: ParametersUpdateRequest) -> list[Parameter]:
    require_command_channel(payload.robotId)
    return state_service.replace_parameters(payload.parameters, payload.robotId)

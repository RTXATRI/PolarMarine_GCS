from fastapi import APIRouter, Depends, Response, status

from polarmarine_gcs.bootstrap.container import Container
from polarmarine_gcs.domain.missions import MissionStep
from polarmarine_gcs.interfaces.http.dependencies import get_container
from polarmarine_gcs.interfaces.http.presenters import (
    command_dto,
    mission_plan_dto,
    mission_run_dto,
)
from polarmarine_gcs.interfaces.http.schemas import (
    MissionControlReceipt,
    MissionPlanDto,
    MissionPlanWrite,
    MissionRunDto,
    MissionStepDto,
)

router = APIRouter()


@router.get("/missions", response_model=list[MissionPlanDto])
def list_plans(container: Container = Depends(get_container)) -> list[MissionPlanDto]:
    return [mission_plan_dto(item) for item in container.repository.list_mission_plans()]


@router.get("/missions/{plan_id}/versions", response_model=list[MissionPlanDto])
def list_plan_versions(
    plan_id: str, container: Container = Depends(get_container)
) -> list[MissionPlanDto]:
    container.missions.require_plan(plan_id)
    return [
        mission_plan_dto(item) for item in container.repository.list_mission_plan_versions(plan_id)
    ]


@router.post("/missions", response_model=MissionPlanDto, status_code=status.HTTP_201_CREATED)
async def create_plan(
    body: MissionPlanWrite,
    container: Container = Depends(get_container),
) -> MissionPlanDto:
    plan = await container.missions.create_plan(
        name=body.name,
        description=body.description,
        steps=tuple(_step(item) for item in body.steps),
    )
    return mission_plan_dto(plan)


@router.put("/missions/{plan_id}", response_model=MissionPlanDto)
async def update_plan(
    plan_id: str,
    body: MissionPlanWrite,
    container: Container = Depends(get_container),
) -> MissionPlanDto:
    plan = await container.missions.update_plan(
        plan_id,
        name=body.name,
        description=body.description,
        steps=tuple(_step(item) for item in body.steps),
    )
    return mission_plan_dto(plan)


@router.delete("/missions/{plan_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_plan(plan_id: str, container: Container = Depends(get_container)) -> Response:
    await container.missions.delete_plan(plan_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/mission-runs", response_model=list[MissionRunDto])
def list_runs(container: Container = Depends(get_container)) -> list[MissionRunDto]:
    return [mission_run_dto(item) for item in container.repository.list_mission_runs()]


@router.post(
    "/missions/{plan_id}/runs",
    response_model=MissionRunDto,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_run(plan_id: str, container: Container = Depends(get_container)) -> MissionRunDto:
    return mission_run_dto(await container.missions.start_run(plan_id))


@router.post("/mission-runs/{run_id}/pause", response_model=MissionControlReceipt, status_code=202)
async def pause_run(
    run_id: str, container: Container = Depends(get_container)
) -> MissionControlReceipt:
    commands = await container.missions.pause(run_id)
    return MissionControlReceipt(
        mission_run_id=run_id, commands=[command_dto(item) for item in commands]
    )


@router.post("/mission-runs/{run_id}/resume", response_model=MissionControlReceipt, status_code=202)
async def resume_run(
    run_id: str, container: Container = Depends(get_container)
) -> MissionControlReceipt:
    commands = await container.missions.resume(run_id)
    return MissionControlReceipt(
        mission_run_id=run_id, commands=[command_dto(item) for item in commands]
    )


@router.post("/mission-runs/{run_id}/cancel", response_model=MissionControlReceipt, status_code=202)
async def cancel_run(
    run_id: str, container: Container = Depends(get_container)
) -> MissionControlReceipt:
    commands = await container.missions.cancel(run_id)
    return MissionControlReceipt(
        mission_run_id=run_id, commands=[command_dto(item) for item in commands]
    )


def _step(item: MissionStepDto) -> MissionStep:
    return MissionStep(
        id=item.id,
        step_type=item.step_type,
        device_id=item.device_id,
        depends_on=tuple(item.depends_on),
        timeout_seconds=item.timeout_seconds,
        payload=item.payload,
    )

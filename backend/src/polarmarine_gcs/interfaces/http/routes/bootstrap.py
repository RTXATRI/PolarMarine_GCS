from fastapi import APIRouter, Depends

from polarmarine_gcs.bootstrap.container import Container
from polarmarine_gcs.domain.missions import MissionRunStatus
from polarmarine_gcs.interfaces.http.dependencies import get_container
from polarmarine_gcs.interfaces.http.presenters import (
    alarm_dto,
    command_dto,
    device_dto,
    link_dto,
    mission_run_dto,
    operational_dto,
    session_dto,
    telemetry_dto,
    template_dto,
)
from polarmarine_gcs.interfaces.http.schemas import BootstrapDto, BootstrapSettingsDto, HealthDto

router = APIRouter()


@router.get("/health", response_model=HealthDto)
def health(container: Container = Depends(get_container)) -> HealthDto:
    return HealthDto(
        version=container.settings.app_version,
        server_instance_id=container.broker.server_instance_id,
    )


@router.get("/bootstrap", response_model=BootstrapDto)
def bootstrap(container: Container = Depends(get_container)) -> BootstrapDto:
    devices = container.repository.list_devices()
    active_statuses = {MissionRunStatus.QUEUED, MissionRunStatus.RUNNING, MissionRunStatus.PAUSED}
    return BootstrapDto(
        server_instance_id=container.broker.server_instance_id,
        event_cursor=container.repository.latest_event_cursor(),
        templates=[template_dto(item) for item in container.repository.list_templates()],
        devices=[device_dto(item) for item in devices],
        links=[link_dto(item) for item in container.repository.list_links()],
        link_sessions=[session_dto(item) for item in container.links.list_sessions()],
        operational_states=[
            operational_dto(container.links.operational_state(item.id)) for item in devices
        ],
        telemetry_snapshots=[telemetry_dto(item) for item in container.telemetry.list_snapshots()],
        active_alarms=[
            alarm_dto(item) for item in container.repository.list_alarms(active_only=True)
        ],
        recent_commands=[
            command_dto(item) for item in container.repository.list_commands(limit=100)
        ],
        active_mission_runs=[
            mission_run_dto(item)
            for item in container.repository.list_mission_runs(limit=100)
            if item.status in active_statuses
        ],
        settings=BootstrapSettingsDto(
            baidu_map_ak=container.settings.baidu_map_ak,
            offline_map_style_url=container.settings.public_offline_map_style_url,
            max_configured_devices=container.settings.max_configured_devices,
            max_online_devices=container.settings.max_online_devices,
        ),
    )

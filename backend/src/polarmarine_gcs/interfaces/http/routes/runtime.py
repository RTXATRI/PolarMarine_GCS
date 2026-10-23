from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import FileResponse

from polarmarine_gcs.bootstrap.container import Container
from polarmarine_gcs.interfaces.http.dependencies import get_container
from polarmarine_gcs.interfaces.http.presenters import (
    alarm_dto,
    command_dto,
    event_dto,
    parameter_state_dto,
    recording_dto,
    telemetry_dto,
)
from polarmarine_gcs.interfaces.http.schemas import (
    AlarmDto,
    CommandDto,
    CommandRequest,
    ParameterStateDto,
    ParameterWriteRequest,
    PersistedEventDto,
    RecordingDto,
    RecordingMessageDto,
    TelemetrySnapshotDto,
)

router = APIRouter()


@router.post(
    "/devices/{device_id}/commands",
    response_model=CommandDto,
    status_code=status.HTTP_202_ACCEPTED,
)
async def submit_command(
    device_id: str,
    body: CommandRequest,
    container: Container = Depends(get_container),
) -> CommandDto:
    command = await container.commands.submit(
        device_id=device_id,
        command_type=body.command_type,
        payload=body.payload,
        idempotency_key=body.idempotency_key,
    )
    return command_dto(command)


@router.get("/commands", response_model=list[CommandDto])
def list_commands(
    device_id: str | None = Query(default=None, alias="deviceId"),
    limit: int = Query(default=100, ge=1, le=1_000),
    container: Container = Depends(get_container),
) -> list[CommandDto]:
    return [command_dto(item) for item in container.repository.list_commands(device_id, limit)]


@router.get("/commands/{command_id}", response_model=CommandDto)
def get_command(command_id: str, container: Container = Depends(get_container)) -> CommandDto:
    return command_dto(container.commands.get(command_id))


@router.post(
    "/commands/{command_id}/cancel", response_model=CommandDto, status_code=status.HTTP_202_ACCEPTED
)
async def cancel_command(
    command_id: str, container: Container = Depends(get_container)
) -> CommandDto:
    return command_dto(await container.commands.cancel(command_id))


@router.get("/telemetry/snapshots", response_model=list[TelemetrySnapshotDto])
def telemetry_snapshots(
    container: Container = Depends(get_container),
) -> list[TelemetrySnapshotDto]:
    return [telemetry_dto(item) for item in container.telemetry.list_snapshots()]


@router.get("/events", response_model=list[PersistedEventDto])
def list_events(
    after: int | None = Query(default=None, ge=0),
    before: int | None = Query(default=None, ge=1),
    event_type: str | None = Query(default=None, alias="type", max_length=128),
    aggregate_id: str | None = Query(default=None, alias="aggregateId", max_length=128),
    limit: int = Query(default=200, ge=1, le=1_000),
    container: Container = Depends(get_container),
) -> list[PersistedEventDto]:
    return [
        event_dto(item)
        for item in container.repository.list_events(
            after=after,
            before=before,
            event_type=event_type,
            aggregate_id=aggregate_id,
            limit=limit,
        )
    ]


@router.get("/alarms", response_model=list[AlarmDto])
def list_alarms(
    active_only: bool = Query(default=False, alias="activeOnly"),
    limit: int = Query(default=200, ge=1, le=1_000),
    container: Container = Depends(get_container),
) -> list[AlarmDto]:
    return [alarm_dto(item) for item in container.repository.list_alarms(active_only, limit)]


@router.post("/alarms/{alarm_id}/acknowledge", response_model=AlarmDto)
async def acknowledge_alarm(
    alarm_id: str, container: Container = Depends(get_container)
) -> AlarmDto:
    return alarm_dto(await container.events.acknowledge_alarm(alarm_id))


@router.get("/devices/{device_id}/parameters", response_model=list[ParameterStateDto])
def get_parameters(
    device_id: str, container: Container = Depends(get_container)
) -> list[ParameterStateDto]:
    return [parameter_state_dto(item) for item in container.parameters.read(device_id)]


@router.post(
    "/devices/{device_id}/parameters/read",
    response_model=CommandDto,
    status_code=status.HTTP_202_ACCEPTED,
)
async def refresh_parameters(
    device_id: str, container: Container = Depends(get_container)
) -> CommandDto:
    return command_dto(await container.parameters.refresh(device_id))


@router.put(
    "/devices/{device_id}/parameters",
    response_model=CommandDto,
    status_code=status.HTTP_202_ACCEPTED,
)
async def write_parameters(
    device_id: str,
    body: ParameterWriteRequest,
    container: Container = Depends(get_container),
) -> CommandDto:
    return command_dto(await container.parameters.write(device_id, body.values))


@router.get("/recordings", response_model=list[RecordingDto])
def list_recordings(container: Container = Depends(get_container)) -> list[RecordingDto]:
    return [recording_dto(item) for item in container.repository.list_recordings()]


@router.get("/recordings/{recording_id}/messages", response_model=list[RecordingMessageDto])
def recording_messages(
    recording_id: str,
    start_time_ns: int | None = Query(default=None, alias="startTimeNs", ge=0),
    end_time_ns: int | None = Query(default=None, alias="endTimeNs", ge=0),
    limit: int = Query(default=1_000, ge=1, le=10_000),
    container: Container = Depends(get_container),
) -> list[RecordingMessageDto]:
    return [
        RecordingMessageDto.model_validate(item)
        for item in container.recordings.read_messages(
            recording_id,
            start_time_ns=start_time_ns,
            end_time_ns=end_time_ns,
            limit=limit,
        )
    ]


@router.get("/recordings/{recording_id}/download", response_class=FileResponse)
def download_recording(
    recording_id: str,
    container: Container = Depends(get_container),
) -> FileResponse:
    path = container.recordings.recording_path(recording_id)
    return FileResponse(path, media_type="application/octet-stream", filename=path.name)

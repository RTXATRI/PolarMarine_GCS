from fastapi import APIRouter, Depends, Response, status

from polarmarine_gcs.bootstrap.container import Container
from polarmarine_gcs.domain.common import ConflictError, ValidationError, new_id
from polarmarine_gcs.domain.devices import (
    Device,
    DeviceTemplate,
    MediaChannelDefinition,
    ParameterDefinition,
)
from polarmarine_gcs.domain.links import LinkSessionState
from polarmarine_gcs.interfaces.http.dependencies import get_container
from polarmarine_gcs.interfaces.http.presenters import (
    device_dto,
    link_dto,
    session_dto,
    template_dto,
)
from polarmarine_gcs.interfaces.http.schemas import (
    AsyncOperationReceipt,
    DeviceDto,
    DeviceTemplateDto,
    DeviceTemplateWrite,
    DeviceWrite,
    LinkProfileDto,
    LinkProfileWrite,
    LinkSessionDto,
    MediaChannelDto,
    ParameterDefinitionDto,
)

router = APIRouter()


@router.get("/device-templates", response_model=list[DeviceTemplateDto])
def list_templates(container: Container = Depends(get_container)) -> list[DeviceTemplateDto]:
    return [template_dto(item) for item in container.repository.list_templates()]


@router.post(
    "/device-templates", response_model=DeviceTemplateDto, status_code=status.HTTP_201_CREATED
)
async def create_template(
    body: DeviceTemplateWrite,
    container: Container = Depends(get_container),
) -> DeviceTemplateDto:
    if not body.id:
        raise ValidationError("A stable template id is required")
    template = DeviceTemplate(
        id=body.id,
        display_name=body.display_name,
        category=body.category,
        description=body.description,
        capabilities=frozenset(body.capabilities),
        parameters=tuple(_parameter(item) for item in body.parameters),
        media_channels=tuple(_media(item) for item in body.media_channels),
    )
    return template_dto(await container.registry.create_template(template))


@router.put("/device-templates/{template_id}", response_model=DeviceTemplateDto)
async def update_template(
    template_id: str,
    body: DeviceTemplateWrite,
    container: Container = Depends(get_container),
) -> DeviceTemplateDto:
    updated = await container.registry.update_template(
        template_id,
        display_name=body.display_name,
        category=body.category,
        description=body.description,
        capabilities=frozenset(body.capabilities),
        parameters=tuple(_parameter(item) for item in body.parameters),
        media_channels=tuple(_media(item) for item in body.media_channels),
    )
    return template_dto(updated)


@router.delete("/device-templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(
    template_id: str, container: Container = Depends(get_container)
) -> Response:
    await container.registry.delete_template(template_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/devices", response_model=list[DeviceDto])
def list_devices(container: Container = Depends(get_container)) -> list[DeviceDto]:
    return [device_dto(item) for item in container.repository.list_devices()]


@router.post("/devices", response_model=DeviceDto, status_code=status.HTTP_201_CREATED)
async def create_device(
    body: DeviceWrite, container: Container = Depends(get_container)
) -> DeviceDto:
    if not body.id:
        raise ValidationError("A stable device id is required")
    device = Device(
        id=body.id,
        template_id=body.template_id,
        display_name=body.display_name,
        enabled=body.enabled,
        description=body.description,
        tags=tuple(body.tags),
    )
    return device_dto(await container.registry.create_device(device))


@router.put("/devices/{device_id}", response_model=DeviceDto)
async def update_device(
    device_id: str,
    body: DeviceWrite,
    container: Container = Depends(get_container),
) -> DeviceDto:
    device = await container.registry.update_device(
        device_id,
        template_id=body.template_id,
        display_name=body.display_name,
        enabled=body.enabled,
        description=body.description,
        tags=tuple(body.tags),
    )
    return device_dto(device)


@router.delete("/devices/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_device(device_id: str, container: Container = Depends(get_container)) -> Response:
    sessions = container.links.list_sessions(device_id)
    if any(item.state is not LinkSessionState.STOPPED for item in sessions):
        raise ConflictError("Disconnect all device links before deleting the device")
    await container.registry.delete_device(device_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/devices/{device_id}/links", response_model=list[LinkProfileDto])
def list_links(
    device_id: str, container: Container = Depends(get_container)
) -> list[LinkProfileDto]:
    container.registry.require_device(device_id)
    return [link_dto(item) for item in container.repository.list_links(device_id)]


@router.post(
    "/devices/{device_id}/links", response_model=LinkProfileDto, status_code=status.HTTP_201_CREATED
)
async def create_link(
    device_id: str,
    body: LinkProfileWrite,
    container: Container = Depends(get_container),
) -> LinkProfileDto:
    link = await container.registry.create_link(
        device_id=device_id,
        display_name=body.display_name,
        driver=body.driver,
        role=body.role,
        priority=body.priority,
        config=body.config,
        enabled=body.enabled,
    )
    return link_dto(link)


@router.put("/devices/{device_id}/links/{link_id}", response_model=LinkProfileDto)
async def update_link(
    device_id: str,
    link_id: str,
    body: LinkProfileWrite,
    container: Container = Depends(get_container),
) -> LinkProfileDto:
    container.registry.require_link(link_id, device_id=device_id)
    session = container.links.get_session(link_id)
    if session and session.state is not LinkSessionState.STOPPED:
        raise ConflictError("Disconnect a link before changing its profile")
    link = await container.registry.update_link(
        link_id,
        display_name=body.display_name,
        driver=body.driver,
        role=body.role,
        priority=body.priority,
        config=body.config,
        enabled=body.enabled,
    )
    return link_dto(link)


@router.delete("/devices/{device_id}/links/{link_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_link(
    device_id: str,
    link_id: str,
    container: Container = Depends(get_container),
) -> Response:
    container.registry.require_link(link_id, device_id=device_id)
    session = container.links.get_session(link_id)
    if session and session.state is not LinkSessionState.STOPPED:
        raise ConflictError("Disconnect a link before deleting its profile")
    await container.registry.delete_link(link_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/devices/{device_id}/link-sessions", response_model=list[LinkSessionDto])
def list_link_sessions(
    device_id: str, container: Container = Depends(get_container)
) -> list[LinkSessionDto]:
    container.registry.require_device(device_id)
    return [session_dto(item) for item in container.links.list_sessions(device_id)]


@router.post(
    "/devices/{device_id}/links/{link_id}/connect",
    response_model=AsyncOperationReceipt,
    status_code=status.HTTP_202_ACCEPTED,
)
async def connect_link(
    device_id: str,
    link_id: str,
    container: Container = Depends(get_container),
) -> AsyncOperationReceipt:
    session = await container.links.connect(device_id, link_id)
    return AsyncOperationReceipt(operation_id=new_id(), session=session_dto(session))


@router.post(
    "/devices/{device_id}/links/{link_id}/disconnect",
    response_model=AsyncOperationReceipt,
    status_code=status.HTTP_202_ACCEPTED,
)
async def disconnect_link(
    device_id: str,
    link_id: str,
    container: Container = Depends(get_container),
) -> AsyncOperationReceipt:
    session = await container.links.disconnect(device_id, link_id)
    return AsyncOperationReceipt(operation_id=new_id(), session=session_dto(session))


def _parameter(item: ParameterDefinitionDto) -> ParameterDefinition:
    return ParameterDefinition(
        key=item.key,
        display_name=item.display_name,
        value_type=item.value_type,
        default_value=item.default_value,
        unit=item.unit,
        minimum=item.minimum,
        maximum=item.maximum,
        step=item.step,
        description=item.description,
        enum_values=tuple(item.enum_values),
        read_only=item.read_only,
    )


def _media(item: MediaChannelDto) -> MediaChannelDefinition:
    return MediaChannelDefinition(
        id=item.id,
        display_name=item.display_name,
        role=item.role,
        required=item.required,
    )

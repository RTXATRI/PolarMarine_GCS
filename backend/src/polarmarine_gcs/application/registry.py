from __future__ import annotations

import re
from dataclasses import replace
from typing import Any

from polarmarine_gcs.application.events import EventService
from polarmarine_gcs.application.ports.repositories import Repository
from polarmarine_gcs.domain.common import (
    ConflictError,
    NotFoundError,
    ValidationError,
    new_id,
    utc_now,
)
from polarmarine_gcs.domain.devices import (
    Capability,
    Device,
    DeviceCategory,
    DeviceTemplate,
    MediaChannelDefinition,
    ParameterDefinition,
    ParameterValueType,
)
from polarmarine_gcs.domain.events import SystemEvent
from polarmarine_gcs.domain.links import DriverKind, LinkProfile, LinkRole

IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")


class RegistryService:
    def __init__(
        self, repository: Repository, events: EventService, *, max_devices: int = 50
    ) -> None:
        self.repository = repository
        self.events = events
        self.max_devices = max_devices

    async def seed_initial_catalogue(self) -> None:
        if self.repository.list_templates():
            return
        for template in _initial_templates():
            self.repository.save_template(template)
        for device in _initial_devices():
            self.repository.save_device(device)
        await self.events.emit(
            SystemEvent(
                type="catalogue.seeded",
                aggregate_type="system",
                aggregate_id="catalogue",
                aggregate_revision=1,
                payload={"templateCount": 3, "deviceCount": 5},
            )
        )

    def require_template(self, template_id: str) -> DeviceTemplate:
        template = self.repository.get_template(template_id)
        if template is None:
            raise NotFoundError(f"Device template {template_id} does not exist")
        return template

    def require_device(self, device_id: str) -> Device:
        device = self.repository.get_device(device_id)
        if device is None:
            raise NotFoundError(f"Device {device_id} does not exist")
        return device

    def require_link(self, link_id: str, *, device_id: str | None = None) -> LinkProfile:
        link = self.repository.get_link(link_id)
        if link is None or (device_id is not None and link.device_id != device_id):
            raise NotFoundError(f"Link profile {link_id} does not exist")
        return link

    async def create_template(self, template: DeviceTemplate) -> DeviceTemplate:
        _validate_identifier(template.id, "template id")
        if self.repository.get_template(template.id):
            raise ConflictError(f"Device template {template.id} already exists")
        self.repository.save_template(template)
        await self._changed("device_template.created", "device_template", template.id, 1)
        return template

    async def update_template(
        self,
        template_id: str,
        *,
        display_name: str,
        category: DeviceCategory,
        description: str,
        capabilities: frozenset[str],
        parameters: tuple[ParameterDefinition, ...],
        media_channels: tuple[MediaChannelDefinition, ...],
    ) -> DeviceTemplate:
        current = self.require_template(template_id)
        updated = replace(
            current,
            display_name=display_name,
            category=category,
            description=description,
            capabilities=capabilities,
            parameters=parameters,
            media_channels=media_channels,
            revision=current.revision + 1,
            updated_at=utc_now(),
        )
        self.repository.save_template(updated)
        await self._changed(
            "device_template.updated", "device_template", template_id, updated.revision
        )
        return updated

    async def delete_template(self, template_id: str) -> None:
        current = self.require_template(template_id)
        if any(device.template_id == template_id for device in self.repository.list_devices()):
            raise ConflictError("A template used by devices cannot be deleted")
        self.repository.delete_template(template_id)
        await self._changed(
            "device_template.deleted", "device_template", template_id, current.revision + 1
        )

    async def create_device(self, device: Device) -> Device:
        _validate_identifier(device.id, "device id")
        self.require_template(device.template_id)
        if self.repository.get_device(device.id):
            raise ConflictError(f"Device {device.id} already exists")
        if len(self.repository.list_devices()) >= self.max_devices:
            raise ConflictError(f"At most {self.max_devices} devices may be configured")
        self.repository.save_device(device)
        await self._changed("device.created", "device", device.id, 1)
        return device

    async def update_device(
        self,
        device_id: str,
        *,
        template_id: str,
        display_name: str,
        enabled: bool,
        description: str,
        tags: tuple[str, ...],
    ) -> Device:
        current = self.require_device(device_id)
        self.require_template(template_id)
        updated = replace(
            current,
            template_id=template_id,
            display_name=display_name,
            enabled=enabled,
            description=description,
            tags=tags,
            revision=current.revision + 1,
            updated_at=utc_now(),
        )
        self.repository.save_device(updated)
        await self._changed("device.updated", "device", device_id, updated.revision)
        return updated

    async def delete_device(self, device_id: str) -> None:
        current = self.require_device(device_id)
        if self.repository.list_commands(device_id=device_id, limit=1):
            raise ConflictError(
                "A device with command history cannot be deleted; disable it instead"
            )
        if any(
            step.device_id == device_id
            for plan in self.repository.list_mission_plans()
            for step in plan.steps
        ):
            raise ConflictError("A device referenced by a mission plan cannot be deleted")
        self.repository.delete_device(device_id)
        await self._changed("device.deleted", "device", device_id, current.revision + 1)

    async def create_link(
        self,
        *,
        device_id: str,
        display_name: str,
        driver: DriverKind,
        role: LinkRole,
        priority: int,
        config: dict[str, Any],
        enabled: bool,
        link_id: str | None = None,
    ) -> LinkProfile:
        self.require_device(device_id)
        _validate_link_config(driver, config)
        profile = LinkProfile(
            id=link_id or new_id(),
            device_id=device_id,
            display_name=display_name,
            driver=driver,
            role=role,
            priority=priority,
            config=config,
            enabled=enabled,
        )
        self.repository.save_link(profile)
        await self._changed(
            "link_profile.created", "link_profile", profile.id, 1, device_id=device_id
        )
        return profile

    async def update_link(
        self,
        link_id: str,
        *,
        display_name: str,
        driver: DriverKind,
        role: LinkRole,
        priority: int,
        config: dict[str, Any],
        enabled: bool,
    ) -> LinkProfile:
        current = self.require_link(link_id)
        _validate_link_config(driver, config)
        updated = replace(
            current,
            display_name=display_name,
            driver=driver,
            role=role,
            priority=priority,
            config=config,
            enabled=enabled,
            revision=current.revision + 1,
            updated_at=utc_now(),
        )
        self.repository.save_link(updated)
        await self._changed(
            "link_profile.updated",
            "link_profile",
            link_id,
            updated.revision,
            device_id=current.device_id,
        )
        return updated

    async def delete_link(self, link_id: str) -> None:
        current = self.require_link(link_id)
        self.repository.delete_link(link_id)
        await self._changed(
            "link_profile.deleted",
            "link_profile",
            link_id,
            current.revision + 1,
            device_id=current.device_id,
        )

    async def _changed(
        self,
        event_type: str,
        aggregate_type: str,
        aggregate_id: str,
        revision: int,
        *,
        device_id: str | None = None,
    ) -> None:
        await self.events.emit(
            SystemEvent(
                type=event_type,
                aggregate_type=aggregate_type,
                aggregate_id=aggregate_id,
                aggregate_revision=revision,
                payload={"deviceId": device_id} if device_id else {},
            )
        )


def _validate_identifier(value: str, label: str) -> None:
    if not IDENTIFIER_PATTERN.fullmatch(value):
        raise ValidationError(f"Invalid {label}: {value}")


def _validate_link_config(driver: DriverKind, config: dict[str, Any]) -> None:
    if driver in {DriverKind.ROS1, DriverKind.ROS2}:
        host = config.get("host")
        port = config.get("port", 9090)
        if not isinstance(host, str) or not host.strip():
            raise ValidationError("ROS link requires a host")
        if not isinstance(port, int) or not 1 <= port <= 65535:
            raise ValidationError("ROS link port must be between 1 and 65535")
    elif driver is DriverKind.SERIAL_JSON:
        port = config.get("port")
        baud_rate = config.get("baudRate", 115200)
        if not isinstance(port, str) or not port.strip():
            raise ValidationError("Serial link requires a port")
        if baud_rate not in {9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600}:
            raise ValidationError("Unsupported serial baud rate")
    elif driver is DriverKind.SIMULATOR:
        seed = config.get("seed", 1)
        if not isinstance(seed, int):
            raise ValidationError("Simulator seed must be an integer")


def _common_parameters(max_speed: float) -> tuple[ParameterDefinition, ...]:
    return (
        ParameterDefinition(
            key="max_speed",
            display_name="最大速度",
            value_type=ParameterValueType.NUMBER,
            default_value=max_speed,
            unit="m/s",
            minimum=0.0,
            maximum=max(1.0, max_speed * 2),
            step=0.01,
            description="设备允许的最大行进速度",
        ),
        ParameterDefinition(
            key="heartbeat_timeout_ms",
            display_name="心跳超时",
            value_type=ParameterValueType.INTEGER,
            default_value=3000,
            unit="ms",
            minimum=1000,
            maximum=10000,
            step=100,
            description="设备端心跳判定超时时间",
        ),
        ParameterDefinition(
            key="low_battery_percent",
            display_name="低电量阈值",
            value_type=ParameterValueType.INTEGER,
            default_value=30,
            unit="%",
            minimum=5,
            maximum=80,
            step=1,
            description="低于该电量时产生告警",
        ),
    )


def _initial_templates() -> tuple[DeviceTemplate, ...]:
    common_mobile = {
        Capability.TELEMETRY.value,
        Capability.POSITION.value,
        Capability.BATTERY.value,
        Capability.MANUAL_CONTROL.value,
        Capability.MODE_CONTROL.value,
        Capability.ARM.value,
        Capability.EMERGENCY_STOP.value,
        Capability.WAYPOINT_MISSION.value,
        Capability.ROUTE_MISSION.value,
        Capability.RETURN_HOME.value,
        Capability.PARAMETERS_READ.value,
        Capability.PARAMETERS_WRITE.value,
        Capability.UVC_MEDIA.value,
    }
    return (
        DeviceTemplate(
            id="polarmarine.uav.standard",
            display_name="标准无人机",
            category=DeviceCategory.AERIAL,
            description="ROS/串口双链路无人机模板",
            capabilities=frozenset(common_mobile),
            parameters=_common_parameters(1.0),
            media_channels=(MediaChannelDefinition("front", "前视相机"),),
        ),
        DeviceTemplate(
            id="polarmarine.usv.standard",
            display_name="标准无人船",
            category=DeviceCategory.SURFACE,
            description="水面智能体通用模板",
            capabilities=frozenset(
                common_mobile
                | {Capability.WASTE_COLLECTION.value, Capability.ELECTROMAGNETIC_FIX.value}
            ),
            parameters=_common_parameters(1.0),
            media_channels=(
                MediaChannelDefinition("front", "前视相机"),
                MediaChannelDefinition("rear", "后视相机"),
                MediaChannelDefinition("payload", "作业相机"),
                MediaChannelDefinition("overview", "全景相机"),
            ),
        ),
        DeviceTemplate(
            id="polarmarine.dock.standard",
            display_name="智能船坞",
            category=DeviceCategory.STATION,
            description="充电与停靠设施模板",
            capabilities=frozenset(
                {
                    Capability.TELEMETRY.value,
                    Capability.EMERGENCY_STOP.value,
                    Capability.DOCK_CHARGE.value,
                    Capability.PARAMETERS_READ.value,
                    Capability.PARAMETERS_WRITE.value,
                    Capability.UVC_MEDIA.value,
                }
            ),
            parameters=_common_parameters(0.0),
            media_channels=(MediaChannelDefinition("overview", "船坞监控"),),
        ),
    )


def _initial_devices() -> tuple[Device, ...]:
    return (
        Device("Hexa-UAV", "polarmarine.uav.standard", "Hexa-UAV"),
        Device("Quadri-UAV", "polarmarine.uav.standard", "Quadri-UAV"),
        Device("MricoCV-USV", "polarmarine.usv.standard", "MricoCV-USV"),
        Device("CL-USV", "polarmarine.usv.standard", "CL-USV"),
        Device("SmartDock-1", "polarmarine.dock.standard", "SmartDock-1"),
    )

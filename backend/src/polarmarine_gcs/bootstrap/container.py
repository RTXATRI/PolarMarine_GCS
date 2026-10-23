from __future__ import annotations

from polarmarine_gcs.application.commands import CommandService
from polarmarine_gcs.application.events import EventBroker, EventService
from polarmarine_gcs.application.links import LinkCoordinator
from polarmarine_gcs.application.missions import MissionService
from polarmarine_gcs.application.parameters import ParameterService
from polarmarine_gcs.application.ports.drivers import DriverGateway
from polarmarine_gcs.application.registry import RegistryService
from polarmarine_gcs.application.telemetry import TelemetryService
from polarmarine_gcs.bootstrap.legacy_profiles import import_legacy_device_profiles
from polarmarine_gcs.bootstrap.migrations import upgrade_database
from polarmarine_gcs.bootstrap.settings import BACKEND_ROOT, CONTRACTS_ROOT, Settings
from polarmarine_gcs.infrastructure.drivers.supervisor import DriverSupervisor
from polarmarine_gcs.infrastructure.persistence.database import Database
from polarmarine_gcs.infrastructure.persistence.repository import SqliteRepository
from polarmarine_gcs.infrastructure.recording import McapRecordingService


class Container:
    def __init__(self, settings: Settings, *, drivers: DriverGateway | None = None) -> None:
        self.settings = settings
        self.database = Database(settings.resolved_database_url)
        self.repository = SqliteRepository(self.database)
        self.broker = EventBroker(settings.event_queue_size)
        self.events = EventService(self.repository, self.broker)
        self.registry = RegistryService(
            self.repository,
            self.events,
            max_devices=settings.max_configured_devices,
        )
        self.drivers = drivers or DriverSupervisor(
            driver_script=BACKEND_ROOT / "drivers" / "driver_main.py",
            source_root=BACKEND_ROOT / "src",
            manifest_directory=CONTRACTS_ROOT / "driver_plugins",
            executable_directory=settings.resolved_driver_executable_dir,
            heartbeat_timeout_seconds=settings.driver_heartbeat_timeout_seconds,
        )
        self.links = LinkCoordinator(
            self.repository,
            self.registry,
            self.events,
            self.drivers,
            heartbeat_interval_seconds=settings.link_heartbeat_interval_seconds,
            missed_heartbeats=settings.link_missed_heartbeats,
            failback_stable_seconds=settings.link_failback_stable_seconds,
            failback_debounce_seconds=settings.link_failback_debounce_seconds,
            max_online_devices=settings.max_online_devices,
        )
        self.telemetry = TelemetryService(
            self.events,
            self.links,
            stale_after_seconds=settings.telemetry_stale_seconds,
        )
        self.commands = CommandService(
            self.repository,
            self.registry,
            self.links,
            self.drivers,
            self.events,
            acknowledgement_timeout_seconds=settings.command_ack_timeout_seconds,
            state_confirmation_timeout_seconds=settings.command_state_timeout_seconds,
        )
        self.recordings = McapRecordingService(
            self.repository,
            settings.resolved_recordings_dir,
            retention_days=settings.recording_retention_days,
            retention_bytes=settings.recording_retention_gib * 1024 * 1024 * 1024,
        )
        self.parameters = ParameterService(
            self.repository,
            self.registry,
            self.commands,
            self.events,
        )
        self.missions = MissionService(
            self.repository,
            self.registry,
            self.links,
            self.telemetry,
            self.commands,
            self.events,
            self.recordings,
        )
        self.links.set_runtime_handlers(
            telemetry=self.telemetry.handle_driver_event,
            command=self.commands.handle_driver_event,
            has_inflight_commands=self.commands.has_inflight_commands,
            raw=self.recordings.record_raw,
        )
        self.telemetry.set_recorder(self.recordings.record_normalized)
        self._started = False

    async def start(self) -> None:
        if self._started:
            return
        if self.settings.resolved_database_url == "sqlite:///:memory:":
            self.database.create_schema()
        else:
            upgrade_database(
                self.settings.resolved_database_url,
                self.settings.data_dir / "backups",
                backup_retention_count=self.settings.database_backup_count,
            )
        await self.recordings.start()
        await self.registry.seed_initial_catalogue()
        await import_legacy_device_profiles(
            self.settings.resolved_legacy_device_profiles_path,
            self.registry,
            self.events,
        )
        await self.links.start()
        await self.telemetry.start()
        await self.commands.recover_interrupted_commands()
        await self.missions.recover_interrupted_runs()
        self._started = True

    async def stop(self) -> None:
        if not self._started:
            self.database.dispose()
            return
        await self.commands.stop()
        await self.telemetry.stop()
        await self.links.stop()
        await self.recordings.stop()
        self.database.dispose()
        self._started = False

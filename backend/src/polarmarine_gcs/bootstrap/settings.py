from __future__ import annotations

import os
import sys
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[3]
IS_FROZEN = bool(getattr(sys, "frozen", False))
RESOURCE_ROOT = Path(getattr(sys, "_MEIPASS", BACKEND_ROOT))
DEFAULT_DATA_DIR = (
    Path(os.environ.get("LOCALAPPDATA", Path.home())) / "PolarMarine_GCS"
    if IS_FROZEN
    else BACKEND_ROOT / "runtime"
)
DEFAULT_FRONTEND_DIST = RESOURCE_ROOT / "frontend" if IS_FROZEN else BACKEND_ROOT.parent / "dist"
CONTRACTS_ROOT = RESOURCE_ROOT / "contracts" if IS_FROZEN else BACKEND_ROOT.parent / "contracts"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="GCS_",
        env_file=BACKEND_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "PolarMarine GCS"
    app_version: str = "1.0.0"
    environment: str = "development"
    host: str = "127.0.0.1"
    port: int = Field(default=8000, ge=1, le=65535)
    cors_origins: str = "http://127.0.0.1:5173,http://localhost:5173"
    data_dir: Path = DEFAULT_DATA_DIR
    database_url: str | None = None
    legacy_device_profiles_path: Path | None = None
    recordings_dir: Path | None = None
    frontend_dist: Path = DEFAULT_FRONTEND_DIST
    driver_executable_dir: Path | None = None
    serve_frontend: bool = True
    open_browser_on_start: bool = True
    offline_map_root: Path | None = None
    baidu_map_ak: str | None = None
    offline_map_style_url: str | None = None
    max_configured_devices: int = 50
    max_online_devices: int = 20
    event_queue_size: int = 1_000
    driver_heartbeat_timeout_seconds: float = 3.0
    link_heartbeat_interval_seconds: float = 1.0
    link_missed_heartbeats: int = 3
    link_failback_stable_seconds: float = 10.0
    link_failback_debounce_seconds: float = 30.0
    telemetry_stale_seconds: float = 3.0
    command_ack_timeout_seconds: float = 5.0
    command_state_timeout_seconds: float = 5.0
    recording_retention_days: int = 30
    recording_retention_gib: int = 20
    database_backup_count: int = Field(default=5, ge=1, le=50)
    log_dir: Path | None = None
    log_level: str = "INFO"
    log_max_bytes: int = Field(default=10 * 1024 * 1024, ge=1_048_576)
    log_backup_count: int = Field(default=10, ge=1, le=100)

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def resolved_database_url(self) -> str:
        if self.database_url:
            return self.database_url
        self.data_dir.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{(self.data_dir / 'polarmarine-gcs.sqlite3').as_posix()}"

    @property
    def resolved_recordings_dir(self) -> Path:
        return self.recordings_dir or self.data_dir / "recordings"

    @property
    def resolved_legacy_device_profiles_path(self) -> Path:
        return self.legacy_device_profiles_path or self.data_dir / "device_profiles.json"

    @property
    def resolved_log_dir(self) -> Path:
        return self.log_dir or self.data_dir / "logs"

    @property
    def public_offline_map_style_url(self) -> str | None:
        if self.offline_map_style_url:
            return self.offline_map_style_url
        if self.offline_map_root and (self.offline_map_root / "style.json").is_file():
            return "/offline-maps/style.json"
        return None

    @property
    def resolved_driver_executable_dir(self) -> Path | None:
        if self.driver_executable_dir:
            return self.driver_executable_dir
        return Path(sys.executable).resolve().parent if IS_FROZEN else None

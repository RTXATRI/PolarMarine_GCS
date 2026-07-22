from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "PolarMarine GCS Backend"
    app_env: str = "development"
    api_prefix: str = "/api"
    cors_origins: str = "http://127.0.0.1:5173,http://localhost:5173"

    mock_simulator_enabled: bool = True
    mock_tick_interval_sec: float = Field(default=1.0, ge=0.1)
    serial_monitor_interval_sec: float = Field(default=1.0, ge=0.05)
    device_profiles_path: Path = BACKEND_ROOT / "runtime" / "device_profiles.json"
    virtual_task_step_sec: float = Field(default=5.0, ge=0.1)
    virtual_task_tick_sec: float = Field(default=0.5, ge=0.05)

    # Legacy global settings are retained for environment-file compatibility.
    # Network profiles now provide the host and port per device.
    rosbridge_enabled: bool = False
    rosbridge_host: str = "127.0.0.1"
    rosbridge_port: int = 9090
    rosbridge_reconnect_sec: float = Field(default=3.0, ge=0.5)
    ros_topic_state: str = "/gcs/robot_state"
    rosbridge_connect_timeout_sec: float = Field(default=5.0, ge=0.1)
    rosbridge_first_message_timeout_sec: float = Field(default=3.0, ge=0.1)
    rosbridge_stale_timeout_sec: float = Field(default=3.0, ge=0.2)
    rosbridge_watchdog_interval_sec: float = Field(default=0.5, ge=0.05)
    rosbridge_reconnect_delays_sec: str = "1,2,4"
    dock_test_ip: str = "192.0.2.42"
    ros_topic_cmd_manual: str = "/gcs/manual_cmd"
    ros_topic_cmd_mission: str = "/gcs/mission_cmd"
    ros_topic_cmd_param: str = "/gcs/param_cmd"

    usv_relay_command_topic: str = '/usv_std/relay/set_enabled'
    usv_relay_confirmation_timeout_sec: float = Field(default=2.0, ge=0.1)

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def rosbridge_reconnect_delays(self) -> tuple[float, ...]:
        values = tuple(float(item.strip()) for item in self.rosbridge_reconnect_delays_sec.split(",") if item.strip())
        return values or (1.0, 2.0, 4.0)


@lru_cache
def get_settings() -> Settings:
    return Settings()

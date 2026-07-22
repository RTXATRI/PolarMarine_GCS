from __future__ import annotations

import json
import os
from pathlib import Path

from pydantic import TypeAdapter, ValidationError

from app.models.schemas import ConnectionProfile, RobotId

PROFILE_FILE_VERSION = 1
PROFILE_ADAPTER = TypeAdapter(ConnectionProfile)


class DeviceProfileStore:
    """Persist only user connection choices, never live connection state."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> dict[RobotId, ConnectionProfile]:
        if not self.path.exists():
            return {}
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

        raw_profiles = payload.get("profiles", payload) if isinstance(payload, dict) else {}
        if not isinstance(raw_profiles, dict):
            return {}

        profiles: dict[RobotId, ConnectionProfile] = {}
        for robot_id, raw_profile in raw_profiles.items():
            if not isinstance(robot_id, str):
                continue
            try:
                profiles[robot_id] = PROFILE_ADAPTER.validate_python(raw_profile)
            except ValidationError:
                continue
        return profiles

    def save(self, profiles: dict[RobotId, ConnectionProfile]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": PROFILE_FILE_VERSION,
            "profiles": {
                robot_id: profile.model_dump(mode="json")
                for robot_id, profile in profiles.items()
            },
        }
        temporary_path = self.path.with_suffix(f"{self.path.suffix}.tmp")
        temporary_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary_path, self.path)

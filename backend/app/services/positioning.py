from __future__ import annotations

from math import isfinite
from typing import Any


AHU_FALLBACK_WGS84: dict[str, tuple[float, float]] = {
    "Hexa-UAV": (31.776394603, 117.180026000),
    "Quadri-UAV": (31.776408603, 117.180026000),
    "MricoCV-USV": (31.776394603, 117.180041000),
    "CL-USV": (31.776381603, 117.180026000),
    "SmartDock-1": (31.776394603, 117.180010000),
}

AHU_FALLBACK_CENTER_WGS84 = AHU_FALLBACK_WGS84["Hexa-UAV"]


def fallback_position_for(robot_id: str) -> tuple[float, float]:
    """Return the stable WGS-84 demonstration position for a device."""

    return AHU_FALLBACK_WGS84.get(robot_id, AHU_FALLBACK_CENTER_WGS84)


def normalize_gps_pair(lat_value: Any, lon_value: Any, robot_id: str) -> tuple[float, float, bool]:
    """Normalize one telemetry GPS pair without rejecting the whole packet.

    Numeric strings remain wire-compatible. Missing, non-finite, out-of-range,
    partial and (0, 0) positions use the device's stable demonstration point.
    """

    try:
        if isinstance(lat_value, bool) or isinstance(lon_value, bool):
            raise TypeError
        lat = float(lat_value)
        lon = float(lon_value)
        valid = (
            isfinite(lat)
            and isfinite(lon)
            and -90 <= lat <= 90
            and -180 <= lon <= 180
            and not (lat == 0 and lon == 0)
        )
    except (TypeError, ValueError, OverflowError):
        valid = False

    if not valid:
        fallback_lat, fallback_lon = fallback_position_for(robot_id)
        return fallback_lat, fallback_lon, True
    return lat, lon, False

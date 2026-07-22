from __future__ import annotations

import math
import time
from typing import Any, Callable

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.services.positioning import (
    AHU_FALLBACK_CENTER_WGS84,
    AHU_FALLBACK_WGS84,
    normalize_gps_pair,
)
from tests.conftest import FakeRosbridgeFactory, make_ros_envelope


ORIGINAL_FALLBACK_CENTER_WGS84 = (31.767827, 117.180026)
PREVIOUS_FALLBACK_CENTER_WGS84 = (31.775041824, 117.180026)
EXPECTED_FALLBACK_WGS84 = {
    "Hexa-UAV": (31.776394603, 117.180026000),
    "Quadri-UAV": (31.776408603, 117.180026000),
    "MricoCV-USV": (31.776394603, 117.180041000),
    "CL-USV": (31.776381603, 117.180026000),
    "SmartDock-1": (31.776394603, 117.180010000),
}


def wait_until(predicate: Callable[[], bool], timeout: float = 2.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("condition was not reached before timeout")


def distance_m(first: tuple[float, float], second: tuple[float, float]) -> float:
    wgs84_major_axis = 6_378_137.0
    wgs84_eccentricity_squared = 6.69437999014e-3
    mean_lat = math.radians((first[0] + second[0]) / 2)
    denominator = math.sqrt(1 - wgs84_eccentricity_squared * math.sin(mean_lat) ** 2)
    meridional_radius = (
        wgs84_major_axis
        * (1 - wgs84_eccentricity_squared)
        / denominator**3
    )
    prime_vertical_radius = wgs84_major_axis / denominator
    lat_distance = math.radians(first[0] - second[0]) * meridional_radius
    lon_distance = (
        math.radians(first[1] - second[1])
        * prime_vertical_radius
        * math.cos(mean_lat)
    )
    return math.hypot(lat_distance, lon_distance)


@pytest.mark.parametrize(
    ("lat", "lon"),
    [
        (None, None),
        (None, 117.18),
        ("not-a-number", 117.18),
        (31.76, float("inf")),
        (float("nan"), 117.18),
        (91, 117.18),
        (31.76, 181),
        (0, 0),
        (True, 117.18),
    ],
)
def test_invalid_gps_pairs_use_the_stable_device_fallback(lat: Any, lon: Any) -> None:
    normalized_lat, normalized_lon, used_fallback = normalize_gps_pair(lat, lon, "CL-USV")

    assert used_fallback is True
    assert (normalized_lat, normalized_lon) == AHU_FALLBACK_WGS84["CL-USV"]


def test_fallback_positions_are_shifted_north_and_keep_the_device_layout() -> None:
    assert AHU_FALLBACK_WGS84 == EXPECTED_FALLBACK_WGS84
    assert AHU_FALLBACK_CENTER_WGS84[0] > ORIGINAL_FALLBACK_CENTER_WGS84[0]
    assert AHU_FALLBACK_CENTER_WGS84[1] == ORIGINAL_FALLBACK_CENTER_WGS84[1]
    assert distance_m(AHU_FALLBACK_CENTER_WGS84, PREVIOUS_FALLBACK_CENTER_WGS84) == pytest.approx(
        150.0,
        abs=1.0,
    )
    assert distance_m(AHU_FALLBACK_CENTER_WGS84, ORIGINAL_FALLBACK_CENTER_WGS84) == pytest.approx(
        950.0,
        abs=1.0,
    )
    assert len(set(AHU_FALLBACK_WGS84.values())) == 5
    for position in AHU_FALLBACK_WGS84.values():
        assert distance_m(position, AHU_FALLBACK_CENTER_WGS84) <= 2.0


def test_missing_first_packet_gps_connects_and_preserves_other_live_data(
    fake_rosbridge_factory: FakeRosbridgeFactory,
) -> None:
    envelope = make_ros_envelope("Hexa-UAV", battery=67)
    envelope["data"].pop("lat")
    envelope["data"].pop("lon")
    fake_rosbridge_factory.configure("192.168.1.249", 9090, envelope)

    with TestClient(create_app()) as client:
        response = client.post(
            "/api/robots/Hexa-UAV/connection",
            json={"method": "network", "host": "192.168.1.249", "port": 9090},
        )

        assert response.status_code == 200
        robot = response.json()
        assert robot["connection"]["state"] == "connected"
        assert robot["connection"]["dataMode"] == "live"
        assert robot["battery"] == 67
        assert robot["position"] == {
            "lat": AHU_FALLBACK_WGS84["Hexa-UAV"][0],
            "lon": AHU_FALLBACK_WGS84["Hexa-UAV"][1],
        }
        assert robot["trail"] == []


def test_live_and_fallback_position_transitions_restart_the_trail(
    fake_rosbridge_factory: FakeRosbridgeFactory,
) -> None:
    initial = make_ros_envelope("Hexa-UAV")
    initial["data"].pop("lat")
    initial["data"].pop("lon")
    fake_rosbridge_factory.configure("192.168.1.249", 9090, initial)

    with TestClient(create_app()) as client:
        assert client.post(
            "/api/robots/Hexa-UAV/connection",
            json={"method": "network", "host": "192.168.1.249", "port": 9090},
        ).status_code == 200
        session = fake_rosbridge_factory.sessions[0]

        session.emit_envelope(make_ros_envelope("Hexa-UAV", lat=30.3, lon=120.2, battery=66))
        wait_until(lambda: client.get("/api/robots/Hexa-UAV").json()["position"] == {"lat": 30.3, "lon": 120.2})
        live = client.get("/api/robots/Hexa-UAV").json()
        assert live["battery"] == 66
        assert live["trail"] == [{"lat": 30.3, "lon": 120.2}]

        session.emit_envelope(make_ros_envelope("Hexa-UAV", lat=0, lon=0, battery=65))
        fallback_position = {
            "lat": AHU_FALLBACK_WGS84["Hexa-UAV"][0],
            "lon": AHU_FALLBACK_WGS84["Hexa-UAV"][1],
        }
        wait_until(lambda: client.get("/api/robots/Hexa-UAV").json()["position"] == fallback_position)
        fallback = client.get("/api/robots/Hexa-UAV").json()
        assert fallback["connection"]["state"] == "connected"
        assert fallback["battery"] == 65
        assert fallback["trail"] == []

        session.emit_envelope(make_ros_envelope("Hexa-UAV", lat=30.31, lon=120.21, battery=64))
        wait_until(lambda: client.get("/api/robots/Hexa-UAV").json()["position"] == {"lat": 30.31, "lon": 120.21})
        recovered = client.get("/api/robots/Hexa-UAV").json()
        assert recovered["trail"] == [{"lat": 30.31, "lon": 120.21}]


def test_smartdock_test_ip_connects_without_a_rosbridge_session_and_resets_on_restart(
    fake_rosbridge_factory: FakeRosbridgeFactory,
) -> None:
    profile = {"method": "network", "host": "192.0.2.42", "port": 9090}

    with TestClient(create_app()) as client:
        response = client.post("/api/robots/SmartDock-1/connection", json=profile)
        assert response.status_code == 200
        robot = response.json()
        assert robot["connection"]["state"] == "connected"
        assert robot["connection"]["dataMode"] == "virtual"
        assert robot["position"] == {
            "lat": AHU_FALLBACK_WGS84["SmartDock-1"][0],
            "lon": AHU_FALLBACK_WGS84["SmartDock-1"][1],
        }
        assert fake_rosbridge_factory.sessions == []
        assert client.get("/api/health").json()["rosbridgeConnectedCount"] == 0

    with TestClient(create_app()) as client:
        restored = client.get("/api/robots/SmartDock-1").json()
        assert restored["connectionProfile"] == profile
        assert restored["connection"]["state"] == "disconnected"
        assert restored["position"] is None


def test_smartdock_normal_ip_and_other_robot_test_ip_use_live_rosbridge(
    fake_rosbridge_factory: FakeRosbridgeFactory,
) -> None:
    fake_rosbridge_factory.configure(
        "192.168.1.88",
        9090,
        make_ros_envelope("SmartDock-1", lat=31.8, lon=117.2),
    )
    fake_rosbridge_factory.configure(
        "192.0.2.42",
        9090,
        make_ros_envelope("Hexa-UAV", lat=31.7, lon=117.1),
    )

    with TestClient(create_app()) as client:
        dock = client.post(
            "/api/robots/SmartDock-1/connection",
            json={"method": "network", "host": "192.168.1.88", "port": 9090},
        )
        uav = client.post(
            "/api/robots/Hexa-UAV/connection",
            json={"method": "network", "host": "192.0.2.42", "port": 9090},
        )

        assert dock.status_code == 200
        assert dock.json()["connection"]["dataMode"] == "live"
        assert dock.json()["position"] == {"lat": 31.8, "lon": 117.2}
        assert uav.status_code == 200
        assert uav.json()["connection"]["dataMode"] == "live"
        assert uav.json()["position"] == {"lat": 31.7, "lon": 117.1}
        assert len(fake_rosbridge_factory.sessions) == 2

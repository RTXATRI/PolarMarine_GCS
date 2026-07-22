from __future__ import annotations

import asyncio
import math
import random
from contextlib import suppress

from app.models.schemas import Position
from app.services.state import now_iso, state_service
from app.ws.telemetry import telemetry_manager


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def jitter(amp: float) -> float:
    return (random.random() - 0.5) * 2 * amp


def meters_to_lat_lon(meters: float, lat: float) -> tuple[float, float]:
    d_lat = meters / 111320
    d_lon = meters / (111320 * math.cos(math.radians(lat)))
    return d_lat, d_lon


class MockSimulator:
    def __init__(self, interval_sec: float) -> None:
        self.interval_sec = interval_sec
        self._task: asyncio.Task[None] | None = None
        self._tick = 0

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if not self._task:
            return
        self._task.cancel()
        with suppress(asyncio.CancelledError):
            await self._task
        self._task = None

    async def _run(self) -> None:
        while True:
            await asyncio.sleep(self.interval_sec)
            self._tick += 1
            self._step()
            await telemetry_manager.broadcast({"type": "robot_state", "data": [robot.model_dump(mode="json") for robot in state_service.list_robots()]})

    def _step(self) -> None:
        with state_service._lock:  # internal simulator owns state mutations for this in-memory v1
            for robot in state_service.robots:
                if robot.connection.state != "connected" or robot.connection.dataMode != "virtual":
                    continue

                if robot.latencyMs is not None:
                    base = 15 if robot.robotType == "dock" else 100
                    robot.latencyMs = int(clamp(round(base + jitter(35)), 5, 600))
                if robot.rssi is not None:
                    robot.rssi = int(clamp(round(robot.rssi + jitter(2)), -95, -20))
                if robot.packetLoss is not None:
                    robot.packetLoss = round(clamp(robot.packetLoss + jitter(0.3), 0, 10), 1)
                if robot.battery is not None and robot.robotType != "dock" and self._tick % 60 == 0:
                    robot.battery = int(clamp(robot.battery - 1, 0, 100))

                if robot.position and robot.robotType != "dock":
                    d_lat, d_lon = meters_to_lat_lon(1.2, robot.position.lat)
                    robot.position = Position(lat=robot.position.lat + jitter(d_lat), lon=robot.position.lon + jitter(d_lon))
                    if self._tick % 5 == 0:
                        state_service.push_trail(robot, robot.position)

                if robot.navState in ("navigating", "returning_home") and robot.navGoals:
                    robot.speed = min(robot.maxSpeed, max(0.05, robot.navGoals[robot.navGoalIndex].speed or robot.maxSpeed))
                    robot.missionStatus = "返航中" if robot.navState == "returning_home" else "导航中"
                elif robot.navState in ("idle", "paused") and robot.speed is not None:
                    robot.speed = 0

                robot.lastCommAt = now_iso()
                if robot.battery is not None and robot.battery <= 30 and not robot.alarm:
                    robot.alarm = "低电量预警"
                    state_service.push_alarm("警告", robot.id, f"低电量预警(电池 {robot.battery}%)")

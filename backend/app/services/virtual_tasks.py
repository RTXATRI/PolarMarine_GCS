from __future__ import annotations

import asyncio
from contextlib import suppress
import time

from app.services.state import StateService, state_service
from app.ws.telemetry import telemetry_manager


class VirtualTaskSimulator:
    """Advances demo task progress without modifying live telemetry fields."""

    def __init__(
        self,
        step_sec: float = 5.0,
        tick_sec: float = 0.5,
        state: StateService = state_service,
    ) -> None:
        self.step_sec = step_sec
        self.tick_sec = tick_sec
        self.state = state
        self._task: asyncio.Task[None] | None = None
        self._last_advance: dict[str, float] = {}

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
        self._last_advance.clear()

    async def _run(self) -> None:
        while True:
            await asyncio.sleep(self.tick_sec)
            if not self._step(time.monotonic()):
                continue
            await telemetry_manager.broadcast(
                {"type": "robot_state", "data": [item.model_dump(mode="json") for item in self.state.list_robots()]}
            )
            await telemetry_manager.broadcast(
                {"type": "log_snapshot", "data": [item.model_dump(mode="json") for item in self.state.list_logs()]}
            )

    def _step(self, now: float) -> bool:
        changed = False
        active_ids: set[str] = set()
        with self.state._lock:
            for robot in self.state.robots:
                active = (
                    robot.connection.state == "connected"
                    and robot.connection.commandMode == "virtual"
                    and robot.navState in ("navigating", "returning_home")
                )
                if not active:
                    continue
                active_ids.add(robot.id)
                previous = self._last_advance.setdefault(robot.id, now)
                if now - previous < self.step_sec:
                    continue

                self._last_advance[robot.id] = now
                total_steps = max(1, len(robot.navGoals))
                robot.navGoalIndex = min(total_steps, robot.navGoalIndex + 1)
                changed = True
                if robot.navGoalIndex >= total_steps:
                    task_name = "返航" if robot.navState == "returning_home" else "导航"
                    robot.navState = "idle"
                    robot.missionStatus = "空闲"
                    self.state.append_log("操作", robot.id, f"[模拟任务] {task_name}演示已完成")
                else:
                    robot.missionStatus = "返航中" if robot.navState == "returning_home" else "导航中"

        for robot_id in set(self._last_advance) - active_ids:
            self._last_advance.pop(robot_id, None)
        return changed

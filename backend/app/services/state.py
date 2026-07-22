from __future__ import annotations

from datetime import datetime, timezone
import time
from threading import RLock

from app.data.mock_data import create_initial_alarms, create_initial_logs, create_initial_parameters, create_initial_robots
from app.models.schemas import (
    Alarm,
    AlarmLevel,
    CommandMode,
    ConnectionErrorInfo,
    ConnectionProfile,
    ConnectionRuntime,
    DataMode,
    GoalPoint,
    LogEntry,
    LogType,
    Parameter,
    Position,
    Robot,
    RobotId,
    RosTelemetryData,
)
from app.services.positioning import AHU_FALLBACK_WGS84, fallback_position_for

MAX_LOGS = 500
MAX_TRAIL_POINTS = 100

VIRTUAL_SEEDS: dict[str, dict[str, object]] = {
    "Hexa-UAV": {"battery": 78, "lat": 30.3105, "lon": 120.3451, "altitude": 50.0, "heading": 0.0, "rssi": -55, "latency": 80},
    "Quadri-UAV": {"battery": 83, "lat": 30.3107, "lon": 120.3454, "altitude": 42.0, "heading": 10.0, "rssi": -58, "latency": 85},
    "MricoCV-USV": {"battery": 62, "lat": 30.3102, "lon": 120.3446, "altitude": 0.0, "heading": 45.0, "rssi": -70, "latency": 120},
    "CL-USV": {"battery": 71, "lat": 30.3099, "lon": 120.3442, "altitude": 0.0, "heading": 90.0, "rssi": -67, "latency": 105},
    "SmartDock-1": {"battery": 100, "lat": AHU_FALLBACK_WGS84["SmartDock-1"][0], "lon": AHU_FALLBACK_WGS84["SmartDock-1"][1], "altitude": 0.0, "heading": 0.0, "rssi": -30, "latency": 15},
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class StateService:
    def __init__(self) -> None:
        self._lock = RLock()
        self.robots: list[Robot] = []
        self.logs: list[LogEntry] = []
        self.alarms: list[Alarm] = []
        self.parameters: list[Parameter] = []
        self._log_seq = 1
        self._alarm_seq = 1
        self._telem_seq = 1
        self._last_trail_second: dict[RobotId, int] = {}
        self._position_sources: dict[RobotId, str] = {}
        self.reset()

    def reset(self, profiles: dict[RobotId, ConnectionProfile] | None = None) -> None:
        """Reset all process runtime while preserving only persisted profiles."""
        with self._lock:
            self.robots = create_initial_robots()
            for robot in self.robots:
                profile = (profiles or {}).get(robot.id)
                robot.connectionProfile = profile.model_copy(deep=True) if profile else None
            self.logs = create_initial_logs()
            self.alarms = create_initial_alarms()
            self.parameters = create_initial_parameters()
            self._log_seq = max((item.id for item in self.logs), default=0) + 1
            self._alarm_seq = max((item.id for item in self.alarms), default=0) + 1
            self._telem_seq = 1
            self._last_trail_second = {}
            self._position_sources = {}

    def list_robots(self) -> list[Robot]:
        with self._lock:
            return [robot.model_copy(deep=True) for robot in self.robots]

    def get_robot(self, robot_id: RobotId) -> Robot | None:
        with self._lock:
            robot = self._find_robot(robot_id)
            return robot.model_copy(deep=True) if robot else None

    def _find_robot(self, robot_id: RobotId) -> Robot | None:
        return next((robot for robot in self.robots if robot.id == robot_id), None)

    def list_logs(self) -> list[LogEntry]:
        with self._lock:
            return [item.model_copy(deep=True) for item in self.logs]

    def list_alarms(self) -> list[Alarm]:
        with self._lock:
            return [item.model_copy(deep=True) for item in self.alarms]

    def list_parameters(self) -> list[Parameter]:
        with self._lock:
            return [item.model_copy(deep=True) for item in self.parameters]

    def saved_profiles(self) -> dict[RobotId, ConnectionProfile]:
        with self._lock:
            return {
                robot.id: robot.connectionProfile.model_copy(deep=True)
                for robot in self.robots
                if robot.connectionProfile is not None
            }

    def set_connection_profile(self, robot_id: RobotId, profile: ConnectionProfile) -> Robot | None:
        with self._lock:
            robot = self._find_robot(robot_id)
            if not robot:
                return None
            robot.connectionProfile = profile.model_copy(deep=True)
            return robot.model_copy(deep=True)

    def mark_connecting(
        self,
        robot_id: RobotId,
        profile: ConnectionProfile,
        *,
        preserve_last_comm: bool = False,
    ) -> Robot | None:
        with self._lock:
            robot = self._find_robot(robot_id)
            if not robot:
                return None
            previous_connected_at = robot.connection.connectedAt
            self._clear_runtime_data(robot, preserve_last_comm=preserve_last_comm)
            robot.connectionProfile = profile.model_copy(deep=True)
            robot.connection = ConnectionRuntime(
                state="connecting",
                activeMethod=profile.method,
                endpoint=self._profile_endpoint(profile),
                dataMode="none",
                connectedAt=previous_connected_at if preserve_last_comm else None,
            )
            return robot.model_copy(deep=True)

    def mark_connected(
        self,
        robot_id: RobotId,
        profile: ConnectionProfile,
        data_mode: DataMode,
        command_mode: CommandMode | None = None,
    ) -> Robot | None:
        with self._lock:
            robot = self._find_robot(robot_id)
            if not robot:
                return None
            self._clear_runtime_data(robot)
            connected_at = now_iso()
            effective_command_mode: CommandMode = command_mode or ("virtual" if data_mode == "virtual" else "none")
            robot.connectionProfile = profile.model_copy(deep=True)
            robot.connection = ConnectionRuntime(
                state="connected",
                activeMethod=profile.method,
                endpoint=self._profile_endpoint(profile),
                dataMode=data_mode,
                commandMode=effective_command_mode,
                connectedAt=connected_at,
            )
            robot.link = "有线" if profile.method == "serial" else "WIFI"
            if data_mode == "virtual":
                self._initialize_virtual_data(robot, connected_at)
            elif effective_command_mode == "virtual":
                robot.missionStatus = "空闲"
            return robot.model_copy(deep=True)

    def mark_disconnected(self, robot_id: RobotId) -> Robot | None:
        with self._lock:
            robot = self._find_robot(robot_id)
            if not robot:
                return None
            self._clear_runtime_data(robot)
            robot.connection = ConnectionRuntime()
            return robot.model_copy(deep=True)

    def mark_connection_error(self, robot_id: RobotId, code: str, message: str, preserve_last_comm: bool = True) -> Robot | None:
        with self._lock:
            robot = self._find_robot(robot_id)
            if not robot:
                return None
            profile = robot.connectionProfile
            previous = robot.connection
            last_comm = robot.lastCommAt if preserve_last_comm else None
            self._clear_runtime_data(robot, preserve_last_comm=preserve_last_comm)
            robot.lastCommAt = last_comm
            robot.connection = ConnectionRuntime(
                state="error",
                activeMethod=profile.method if profile else previous.activeMethod,
                endpoint=self._profile_endpoint(profile) if profile else previous.endpoint,
                dataMode="none",
                connectedAt=previous.connectedAt,
                error=ConnectionErrorInfo(code=code, message=message),
            )
            return robot.model_copy(deep=True)

    @staticmethod
    def _profile_endpoint(profile: ConnectionProfile) -> str:
        if profile.method == "serial":
            return profile.port
        return f"{profile.host}:{profile.port}"

    def _clear_runtime_data(self, robot: Robot, preserve_last_comm: bool = False) -> None:
        robot.link = None
        robot.battery = None
        robot.mode = None
        robot.px4Mode = None
        robot.missionStatus = None
        robot.linkStatus = None
        robot.latencyMs = None
        robot.packetLoss = None
        robot.rssi = None
        robot.position = None
        robot.altitude = None
        robot.speed = None
        robot.heading = None
        robot.alarm = None
        robot.trail = []
        if not preserve_last_comm:
            robot.lastCommAt = None
        robot.unlocked = None
        robot.relayEnabled = None
        robot.homePosition = None
        robot.navState = "idle"
        robot.navGoals = []
        robot.navGoalIndex = 0
        robot.wobbleAnchor = None
        self._last_trail_second.pop(robot.id, None)
        self._position_sources.pop(robot.id, None)

    def _initialize_virtual_data(self, robot: Robot, timestamp: str) -> None:
        seed = VIRTUAL_SEEDS[robot.id]
        position = Position(lat=float(seed["lat"]), lon=float(seed["lon"]))
        robot.battery = int(seed["battery"])
        robot.mode = "自动" if robot.robotType == "dock" else "手动"
        robot.missionStatus = "空闲"
        robot.linkStatus = "正常"
        robot.latencyMs = int(seed["latency"])
        robot.packetLoss = 0.0
        robot.rssi = int(seed["rssi"])
        robot.position = position
        robot.altitude = float(seed["altitude"])
        robot.speed = 0.0
        robot.heading = float(seed["heading"])
        robot.lastCommAt = timestamp
        robot.unlocked = False
        robot.homePosition = position.model_copy()
        robot.wobbleAnchor = position.model_copy()
        self._position_sources[robot.id] = "virtual"

    def has_data_channel(self, robot_id: RobotId) -> bool:
        with self._lock:
            robot = self._find_robot(robot_id)
            return bool(robot and robot.connection.state == "connected" and robot.connection.dataMode in ("virtual", "live"))

    def has_command_channel(self, robot_id: RobotId) -> bool:
        with self._lock:
            return self._has_command_channel(self._find_robot(robot_id))

    @staticmethod
    def _has_data_channel(robot: Robot | None) -> bool:
        return bool(
            robot
            and robot.connection.state == "connected"
            and robot.connection.dataMode in ("virtual", "live")
        )

    @staticmethod
    def _has_command_channel(robot: Robot | None) -> bool:
        return bool(
            robot
            and robot.connection.state == "connected"
            and robot.connection.commandMode in ("virtual", "live")
        )

    def replace_parameters(self, parameters: list[Parameter], robot_id: RobotId | None = None) -> list[Parameter]:
        with self._lock:
            if robot_id is not None and not self._has_command_channel(self._find_robot(robot_id)):
                return self.list_parameters()
            self.parameters = [item.model_copy(deep=True) for item in parameters]
            max_speed = next((item.currentValue for item in self.parameters if item.key == "max_speed"), None)
            if max_speed is not None:
                for robot in self.robots:
                    if robot.robotType != "dock":
                        robot.maxSpeed = float(max_speed)
            self.append_log("操作", robot_id, f"[模拟] 后端保存参数 {len(parameters)} 项，未写入飞控")
            return self.list_parameters()

    def append_log(self, log_type: LogType, robot_id: RobotId | None, content: str) -> LogEntry:
        with self._lock:
            entry = LogEntry(id=self._log_seq, time=now_iso(), type=log_type, robotId=robot_id, content=content)
            self._log_seq += 1
            self.logs.insert(0, entry)
            if len(self.logs) > MAX_LOGS:
                del self.logs[MAX_LOGS:]
            return entry.model_copy(deep=True)

    def push_alarm(
        self,
        level: AlarmLevel,
        robot_id: RobotId,
        content: str,
        *,
        attach_to_robot: bool = True,
    ) -> Alarm:
        with self._lock:
            alarm = Alarm(id=self._alarm_seq, time=now_iso(), level=level, robotId=robot_id, content=content, acknowledged=False)
            self._alarm_seq += 1
            self.alarms.insert(0, alarm)
            robot = self._find_robot(robot_id)
            if robot and attach_to_robot:
                robot.alarm = content
            self.append_log("报警", robot_id, content)
            return alarm.model_copy(deep=True)

    def ack_alarm(self, alarm_id: int) -> Alarm | None:
        with self._lock:
            alarm = next((item for item in self.alarms if item.id == alarm_id), None)
            if not alarm:
                return None
            alarm.acknowledged = True
            self.append_log("操作", alarm.robotId, f"已确认报警:{alarm.content}")
            return alarm.model_copy(deep=True)

    def clear_logs(self) -> LogEntry:
        with self._lock:
            self.logs = []
            return self.append_log("系统", None, "历史日志已清空")

    def set_mode(self, robot_id: RobotId, mode: str) -> Robot | None:
        with self._lock:
            robot = self._find_robot(robot_id)
            if not self._has_command_channel(robot):
                return None
            self.append_log("操作", robot_id, f"[模拟] 请求切换控制模式为 {mode}，未发送飞控")
            return robot.model_copy(deep=True)

    def set_unlocked(self, robot_id: RobotId, unlocked: bool) -> Robot | None:
        with self._lock:
            robot = self._find_robot(robot_id)
            if not self._has_command_channel(robot):
                return None
            action = "解锁" if unlocked else "锁定"
            self.append_log("操作", robot_id, f"[模拟] 请求{action}设备，未发送飞控")
            return robot.model_copy(deep=True)

    def emergency_stop(self, robot_id: RobotId) -> Robot | None:
        with self._lock:
            robot = self._find_robot(robot_id)
            if not self._has_command_channel(robot):
                return None
            self.append_log("操作", robot_id, "[模拟] 急停操作已记录，未发送飞控")
            return robot.model_copy(deep=True)

    def apply_manual_command(self, robot_id: RobotId, command: str, speed: float) -> Robot | None:
        with self._lock:
            robot = self._find_robot(robot_id)
            if not self._has_command_channel(robot):
                return None
            self.append_log("操作", robot_id, f"[模拟] 手动指令:{command}，速度 {speed:.2f} m/s，未发送飞控")
            return robot.model_copy(deep=True)

    def start_navigation(self, robot_id: RobotId, goals: list[GoalPoint]) -> Robot | None:
        with self._lock:
            robot = self._find_robot(robot_id)
            if not self._has_command_channel(robot):
                return None
            robot.navGoals = [goal.model_copy(deep=True) for goal in goals]
            robot.navGoalIndex = 0
            robot.navState = "navigating"
            robot.missionStatus = "正在前往目标点"
            self.append_log("操作", robot_id, f"[模拟任务] 开始导航，目标点 {len(goals)} 个")
            return robot.model_copy(deep=True)

    def pause_navigation(self, robot_id: RobotId) -> Robot | None:
        return self._set_nav_state(robot_id, "paused", "暂停", "[模拟任务] 暂停任务")

    def resume_navigation(self, robot_id: RobotId) -> Robot | None:
        return self._set_nav_state(robot_id, "navigating", "导航中", "[模拟任务] 恢复任务")

    def stop_navigation(self, robot_id: RobotId) -> Robot | None:
        with self._lock:
            robot = self._find_robot(robot_id)
            if not self._has_command_channel(robot):
                return None
            robot.navGoals = []
            robot.navGoalIndex = 0
            robot.navState = "idle"
            robot.missionStatus = "空闲"
            self.append_log("操作", robot_id, "[模拟任务] 停止任务")
            return robot.model_copy(deep=True)

    def return_home(self, robot_id: RobotId) -> Robot | None:
        with self._lock:
            robot = self._find_robot(robot_id)
            if not self._has_command_channel(robot):
                return None
            home = robot.homePosition or robot.position
            robot.navGoals = [GoalPoint(id="__home__", lat=home.lat, lon=home.lon, speed=0.8)] if home else []
            robot.navGoalIndex = 0
            robot.navState = "returning_home"
            robot.missionStatus = "返航中"
            self.append_log("操作", robot_id, "[模拟任务] 已启动返航演示，未发送飞控")
            return robot.model_copy(deep=True)

    def _set_nav_state(self, robot_id: RobotId, nav_state: str, mission_status: str, log_text: str) -> Robot | None:
        with self._lock:
            robot = self._find_robot(robot_id)
            if not self._has_command_channel(robot):
                return None
            robot.navState = nav_state  # type: ignore[assignment]
            robot.missionStatus = mission_status  # type: ignore[assignment]
            self.append_log("操作", robot_id, log_text)
            return robot.model_copy(deep=True)

    def apply_live_telemetry(
        self,
        robot_id: RobotId,
        data: RosTelemetryData,
        received_at: float | None = None,
        *,
        gps_fallback: bool = False,
    ) -> Robot | None:
        """Replace only fields owned by the live MAVROS telemetry channel."""

        with self._lock:
            robot = self._find_robot(robot_id)
            if not robot or robot.connection.state != "connected" or robot.connection.dataMode != "live":
                return None

            received_at = received_at if received_at is not None else time.time()
            robot.battery = data.battery
            robot.mode = data.mode
            robot.px4Mode = data.px4Mode
            robot.linkStatus = "正常"
            # These metrics do not have a trustworthy MAVROS source in v1.
            robot.latencyMs = None
            robot.packetLoss = None
            robot.rssi = None
            robot.altitude = data.altitude
            robot.speed = data.speed
            robot.heading = data.heading
            robot.unlocked = data.unlocked
            robot.relayEnabled = data.relayEnabled if robot.id == 'CL-USV' else None
            robot.alarm = data.alarm
            robot.lastCommAt = datetime.fromtimestamp(received_at, timezone.utc).isoformat()

            if data.lat is None or data.lon is None:
                lat, lon = fallback_position_for(robot_id)
                gps_fallback = True
            else:
                lat, lon = data.lat, data.lon

            position_source = "fallback" if gps_fallback else "live"
            if self._position_sources.get(robot_id) != position_source:
                robot.trail = []
                self._last_trail_second.pop(robot_id, None)
            self._position_sources[robot_id] = position_source

            position = Position(lat=lat, lon=lon)
            robot.position = position
            if not gps_fallback:
                sample_second = int(received_at)
                if self._last_trail_second.get(robot_id) != sample_second:
                    self.push_trail(robot, position)
                    self._last_trail_second[robot_id] = sample_second
            return robot.model_copy(deep=True)

    def push_trail(self, robot: Robot, position: Position) -> None:
        robot.trail.append(position.model_copy())
        if len(robot.trail) > MAX_TRAIL_POINTS:
            del robot.trail[: len(robot.trail) - MAX_TRAIL_POINTS]


state_service = StateService()

from datetime import datetime, timezone

from app.models.schemas import Alarm, LogEntry, Parameter, Robot


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_initial_robots() -> list[Robot]:
    return [
        Robot(
            id="Hexa-UAV",
            robotType="uav",
            maxSpeed=1.0,
        ),
        Robot(
            id="Quadri-UAV",
            robotType="uav",
            maxSpeed=1.0,
        ),
        Robot(
            id="MricoCV-USV",
            robotType="usv",
            maxSpeed=0.08,
        ),
        Robot(
            id="CL-USV",
            robotType="usv",
            maxSpeed=1.0,
        ),
        Robot(
            id="SmartDock-1",
            robotType="dock",
            maxSpeed=0,
        ),
    ]


def create_initial_logs() -> list[LogEntry]:
    now = now_iso()
    return [
        LogEntry(id=1, time=now, type="系统", robotId=None, content="设备名册已加载，等待设备连接"),
    ]


def create_initial_alarms() -> list[Alarm]:
    return []


def create_initial_parameters() -> list[Parameter]:
    return [
        Parameter(key="max_speed", name="最大速度", currentValue=1.0, editValue=1.0, defaultValue=1.0, unit="m/s", description="机器人允许达到的最大行进速度"),
        Parameter(key="rc_timeout", name="遥控超时", currentValue=500, editValue=500, defaultValue=500, unit="ms", description="遥控指令超过该时长未刷新则自动停车"),
        Parameter(key="rth_speed", name="返航速度", currentValue=0.8, editValue=0.8, defaultValue=0.8, unit="m/s", description="触发返航后使用的巡航速度"),
        Parameter(key="gnss_rate", name="定位更新频率", currentValue=5, editValue=5, defaultValue=5, unit="Hz", description="上报位置消息的频率"),
        Parameter(key="low_battery_threshold", name="低电量报警阈值", currentValue=30, editValue=30, defaultValue=30, unit="%", description="电池电量低于该百分比触发低电量报警"),
        Parameter(key="heartbeat_timeout", name="心跳超时时间", currentValue=2000, editValue=2000, defaultValue=2000, unit="ms", description="心跳超过该时长无响应判为断链"),
    ]

# PolarMarine Agent Adapter Contract

ROS1 与 ROS2 适配器共享 `contracts/device_protocol/message-envelope.schema.json`，并使用以下 `std_msgs/String` JSON 话题：

- `/polarmarine/v1/device_info`
- `/polarmarine/v1/heartbeat`
- `/polarmarine/v1/state`
- `/polarmarine/v1/command/request`
- `/polarmarine/v1/command/ack`
- `/polarmarine/v1/mission/event`

适配器只做协议封装、身份、序号与命令去重。飞控模式、任务冲突、急停执行和最终状态确认必须由设备集成节点决定。上位机看到 `command.ack` 的 `state_confirmed` 前不会把需要确认的命令显示为成功。

局域网发现使用 `_polarmarine._tcp.local.`，TXT 至少包含 `deviceId`、`schemaVersion=1.0` 和 `rosVersion=ros1|ros2`。只广播 `_rosbridge._tcp.local.` 的端点会作为调试候选显示，但不能通过正式身份握手。

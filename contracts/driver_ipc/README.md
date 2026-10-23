# Driver IPC v1

核心服务与驱动进程只通过标准输入/输出交换帧：`4-byte big-endian length + UTF-8 JSON`。JSON 最大 1 MiB，stdout 禁止输出日志，驱动日志只能写 stderr。

驱动每秒发送 `driver.heartbeat`。核心连续三秒未收到心跳时终止并按 1/2/4/8 秒退避重启该驱动，同时把其管理的链路置为失败；重启后仅恢复进程和已请求链路，不恢复任何设备在线结论。

所有 IPC 消息遵守 [driver-message.schema.json](./driver-message.schema.json)。设备协议消息作为 `command.send.payload.message` 或驱动事件的规范化载荷传输。

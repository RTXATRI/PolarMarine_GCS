# 架构说明

## 聚合与事实来源

| 聚合                                  |                               持久化 | 进程重启          | 事实来源            |
| ------------------------------------- | -----------------------------------: | ----------------- | ------------------- |
| DeviceTemplate / Device / LinkProfile |                                   是 | 恢复              | 本地配置            |
| LinkSession / DeviceOperationalState  |                                   否 | 全部离线          | 驱动握手与心跳      |
| TelemetrySnapshot                     |                                   否 | 未知              | 选定链路的设备消息  |
| Command                               |                                   是 | 中断项超时/未确认 | 设备 ACK 与状态确认 |
| MissionPlan / MissionRun              |                                   是 | 运行项标记中断    | 任务编排与设备事件  |
| Event / Alarm                         |                                   是 | 保留              | 应用服务事件管线    |
| MediaChannel                          | 逻辑通道在模板；UVC 绑定在 IndexedDB | 不自动打开        | 浏览器 MediaDevices |

## 依赖方向

```text
interfaces ─┐
bootstrap ──┼──> application ──> domain
infrastructure ┘        ^
                       ports
```

领域层不知道 FastAPI、Pydantic、SQLAlchemy、ROS 和串口。应用层只依赖仓储、驱动、录制等端口。接口 DTO 和 IPC 在边界校验后转换为领域对象；HTTP/WS camelCase 不进入 Python 内部命名。

## 链路路由

```text
心跳缺失 3 次 -> 主链路 failed -> 选择能力匹配的下一健康链路
                                  -> device.route_changed
原主链路恢复 -> 连续健康 10 s -> 无在途命令 -> 30 s 防抖满足 -> 回切
```

遥测按信号组选择一个来源；不会把不同链路的同一字段拼接成“更完整”的假快照。质量为 unknown/valid/stale/invalid/simulated，仿真质量在 UI 永久可见。

## 命令序列

```text
UI -> POST 202 -> Command queued/dispatched -> 驱动 -> 设备
UI <- WS command.changed <- ACK accepted/progress/completed
                                      |
                         需要时继续等待 state_confirmed
```

客户端不把 HTTP 202 当作成功。晚到 ACK 可补充逐链路信息，但不能反转已进入的安全终态。可重试命令复用 `commandId` 供设备去重；不确定的非幂等命令不自动换链路重发。核心重启时遗留的非终态命令变为 `state_unconfirmed`，任务运行使用启动时冻结的计划步骤，后续编辑不会改变在途任务。

## 事件一致性

每个 WebSocket 事件包含 schemaVersion、eventId、serverInstanceId、connectionSequence、eventCursor、聚合类型/ID/修订和时间。客户端发现实例变化或序号缺口时重新读取 `/bootstrap`，不会继续相信局部缓存。遥测事件在服务端限流合并，所有订阅队列有界。

## 扩展路径

- 新设备类型：新增/编辑模板与能力，不修改页面设备名分支。
- 新动作：先扩展稳定命令代码和设备契约，再由模板声明能力。
- 新驱动：新增版本化插件清单，实现应用端口与进程适配器，复用统一信封和 ACK。
- 新地图：实现 `MapProvider`，领域覆盖物仍使用 WGS-84。
- 新媒体：实现 `MediaSource`；网络视频不得伪装成本机 UVC。
- Fleet Adapter：未来在任务分配边界接入，不让 OpenRMF 模型渗入设备/链路核心。

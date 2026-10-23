# Driver development

每种驱动是一个受监管进程，并通过 `drivers/driver_main.py --driver <kind>` 运行。一个进程管理该类型的多条链路；不得把设备业务状态保存在浏览器或 FastAPI 路由中。版本化插件清单位于 `contracts/driver_plugins/`，Supervisor 会在启动前校验清单并从中解析发布版可执行文件名。

## IPC

消息契约位于 `contracts/driver_ipc/`。帧是 4 字节大端长度与 UTF-8 JSON，最大 1 MiB。驱动必须：

1. 每秒发送 `driver.heartbeat`；
2. 对 `link.start` 完成端点连接、设备身份和能力握手；
3. 只在握手成功后发送 `link.device_info` 与健康心跳；
4. 将正式消息校验为 PolarMarine v1 信封；
5. 以 `command.ack` 返回接受、进度、拒绝、完成和状态确认；
6. 只向 stderr 写人类日志。

## 新增驱动

1. 在领域层增加稳定 `DriverKind`，不增加设备 ID 判断。
2. 新增符合 `manifest.schema.json` 的插件清单。
3. 在 `drivers/runtime.py` 实现适配器并注册工厂。
4. 保持协议消息与正式遥测隔离；调试消息必须限速和限长。
5. 为握手失败、身份不匹配、心跳超时、乱序消息和命令 ACK 添加测试。
6. 在 PyInstaller spec 中增加独立入口，并更新设备/IPC JSON Schema。

ROS 端点只有安装 `agent_adapters` 并完成 `/polarmarine/v1/device_info` 身份握手后才能作为正式链路。串口必须复用同一信封、序列号和命令 ID，不能建立另一套业务协议。

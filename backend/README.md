# PolarMarine GCS Python Backend

该目录是 PolarMarine GCS 的 Python/FastAPI 后端。后端是设备名册、连接配置、连接状态、遥测、日志、报警和参数的统一数据源；前端只通过 HTTP 和 WebSocket 读取或提交操作。

## 职责边界

- 管理固定设备名册：`Hexa-UAV`、`Quadri-UAV`、`MricoCV-USV`、`CL-USV`、`SmartDock-1`。
- 保存用户连接配置：串口号/波特率或网络 IP/端口。
- 管理运行态连接：未连接、连接中、已连接、连接失败。
- 打开真实串口并检测占用、拔出和主动断开。
- 为每台网络设备建立独立 ROSBridge 会话，订阅 `/gcs/robot_state`。
- 解析 MAVROS 汇总状态并推送到前端。
- 提供虚拟任务进度和通用控制反馈，明确标记为模拟行为。
- 为 `CL-USV` 通过 ROSBridge 发布真实电磁固定继电器命令。

不在本阶段处理的内容：

- 串口协议解析。
- 通用手动控制、急停、参数写入到真实飞控。
- 数据库持久化。
- 后端视频采集、转码或转发。

## 运行

```powershell
conda activate GCS
cd "E:\Workspace\Code data\Polar Ocean Electronics Laboratory\PolarMarine_GCS\backend"
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

建议保持单进程、单 worker 运行，避免多个进程同时持有同一串口或 ROSBridge 会话。开发模式 `--reload` 会重启进程，已有连接会释放，设备回到未连接状态。

## 配置

后端读取 `backend/.env`，可参考 `backend/.env.example`：

```dotenv
APP_NAME=PolarMarine GCS Backend
API_PREFIX=/api
CORS_ORIGINS=http://127.0.0.1:5173,http://localhost:5173

MOCK_SIMULATOR_ENABLED=true
SERIAL_MONITOR_INTERVAL_SEC=1.0
DEVICE_PROFILES_PATH=runtime/device_profiles.json

ROS_TOPIC_STATE=/gcs/robot_state
ROSBRIDGE_CONNECT_TIMEOUT_SEC=5.0
ROSBRIDGE_FIRST_MESSAGE_TIMEOUT_SEC=3.0
ROSBRIDGE_STALE_TIMEOUT_SEC=3.0
ROSBRIDGE_RECONNECT_DELAYS_SEC=1,2,4

DOCK_TEST_IP=192.0.2.42
USV_RELAY_COMMAND_TOPIC=/usv_std/relay/set_enabled
USV_RELAY_CONFIRMATION_TIMEOUT_SEC=2.0
```

历史全局 `ROSBRIDGE_HOST/ROSBRIDGE_PORT` 配置仍被兼容读取，但当前真实连接以每台设备的连接面板配置为准。

## 状态模型

`Robot` 中的运行状态分三层：

- `connectionProfile`：上次保存的连接配置，只用于表单预填。
- `connection`：当前进程内连接状态，包括 `state`、`activeMethod`、`endpoint`、`dataMode`、`commandMode`、`connectedAt` 和错误信息。
- 遥测字段：电池、模式、位置、高度、速度、航向、链路、报警、轨迹等。

后端启动时只恢复 `connectionProfile`，所有 `connection` 和遥测字段都会重置。未连接设备不会保留上次的“有线/WIFI/4G/数传”、位置、电池或摄像头可用状态。

`dataMode` 和 `commandMode` 的含义：

```text
none     当前连接没有可用数据/操作通道
virtual  由后端演示逻辑提供，不代表真实飞控
live     来自真实 ROSBridge/MAVROS 或真实硬件动作
```

当前普通 PX4 网络连接为 `dataMode=live`、`commandMode=virtual`。串口连接为 `dataMode=none`、`commandMode=none`。`SmartDock-1` 测试地址为 `dataMode=virtual`、`commandMode=virtual`。

## 连接接口

```text
GET    /api/connections/serial-ports
GET    /api/connections/network-candidates?port=9090
POST   /api/robots/{robot_id}/connection
DELETE /api/robots/{robot_id}/connection
```

串口连接请求：

```json
{"method":"serial","port":"COM3","baudRate":115200}
```

网络连接请求：

```json
{"method":"network","host":"192.168.1.249","port":9090}
```

发起连接时会保存配置到 `runtime/device_profiles.json`。即使连接失败，本次配置也会保留，方便用户修正硬件占用、端口、防火墙或话题问题后重试。主动断开会释放串口句柄或 ROSBridge 会话，并清空运行遥测，但不删除保存的配置。

## 串口连接

串口枚举使用 `pyserial` 的 `serial.tools.list_ports.comports()`。连接时后端会检查端口存在、是否已被本进程其他设备占用，并以 8-N-1 打开端口。

常见错误码：

```text
SERIAL_ENUMERATION_FAILED
SERIAL_PORT_NOT_FOUND
SERIAL_PORT_IN_USE
SERIAL_PORT_BUSY_OR_DENIED
SERIAL_OPEN_FAILED
SERIAL_CONNECTION_LOST
```

串口句柄保持打开，用于验证“已连接”和“被占用”闭环。当前没有串口读写协议，因此串口连接后的控制、参数、任务接口会返回 `DATA_CHANNEL_UNAVAILABLE`。

## 网络连接

网络候选搜索使用 `psutil` 获取活动私有 IPv4 网段，然后对表单端口执行 TCP 探测。搜索不到不影响手工输入。

普通网络连接会：

1. 校验 IPv4 和端口。
2. 检查同一 `host:port` 是否已被其他设备占用。
3. 使用 `roslibpy` 连接对应 rosbridge_server。
4. 订阅 `ROS_TOPIC_STATE`，默认 `/gcs/robot_state`。
5. 等待首帧合法状态，首帧通过后才进入已连接。

若连接后连续 `ROSBRIDGE_STALE_TIMEOUT_SEC` 秒没有合法状态，后端会清空实时字段，按 `ROSBRIDGE_RECONNECT_DELAYS_SEC` 进行有限重连。重连耗尽后进入错误状态并生成一次严重报警；主动断开不会报警。

`SmartDock-1` 连接到 `DOCK_TEST_IP`，默认 `192.0.2.42:9090`，会直接进入虚拟演示状态，不创建 ROSBridge 会话。其他地址仍走真实 ROSBridge。

## ROS 状态消息

机载端通过 ROSBridge 发布 `std_msgs/String`，字符串内容必须是 JSON：

```json
{
  "schemaVersion": 1,
  "robotId": "Hexa-UAV",
  "timestamp": "2026-07-17T09:00:00Z",
  "data": {
    "sourceConnected": true,
    "battery": 82,
    "mode": "手动",
    "px4Mode": "POSCTL",
    "missionStatus": "空闲",
    "linkStatus": "正常",
    "latencyMs": null,
    "packetLoss": null,
    "rssi": null,
    "lat": 30.2755,
    "lon": 120.157,
    "altitude": 12.4,
    "speed": 0.35,
    "heading": 86.2,
    "unlocked": false,
    "relayEnabled": null,
    "alarm": null
  }
}
```

校验规则：

- `schemaVersion` 当前固定为 `1`。
- `timestamp` 必须包含时区。
- `robotId` 必须与当前连接的设备一致。
- `sourceConnected=false` 表示 MAVROS/PX4 不可用，连接会失败或触发恢复。
- `battery` 范围为 0 到 100。
- `lat/lon` 必须同时提供或同时为空，非法 GPS 会触发展示坐标兜底。
- `heading` 范围为 `[0, 360)`。

后端只把可信的实时字段映射到机器人状态。`missionStatus`、`linkStatus`、`latencyMs`、`packetLoss`、`rssi` 在当前版本不会从 ROS 消息覆盖到上位机状态，避免伪造链路指标或覆盖上位机虚拟任务状态。

## CL-USV 电磁固定

接口：

```text
POST /api/commands/electromagnetic-fix
```

请求：

```json
{"robotId":"CL-USV","enabled":true}
```

要求：

- 当前设备必须是 `CL-USV`。
- 设备必须通过网络 ROSBridge 已连接。
- 已收到布尔型 `relayEnabled` 状态。

后端会向 `USV_RELAY_COMMAND_TOPIC` 发布 `std_msgs/Bool`，默认 `/usv_std/relay/set_enabled`，并等待后续 `/gcs/robot_state` 中的 `relayEnabled` 变为目标值。发布失败、连接中断或确认超时会返回结构化错误。

## API 概览

```text
GET    /api/health
GET    /api/robots
GET    /api/robots/{robot_id}
GET    /api/logs
POST   /api/logs/clear
GET    /api/alarms
POST   /api/alarms/{alarm_id}/ack
GET    /api/parameters?robotId=Hexa-UAV
PUT    /api/parameters
GET    /api/connections/serial-ports
GET    /api/connections/network-candidates?port=9090
POST   /api/robots/{robot_id}/connection
DELETE /api/robots/{robot_id}/connection
POST   /api/commands/manual
POST   /api/commands/mode
POST   /api/commands/lock
POST   /api/commands/emergency-stop
POST   /api/commands/electromagnetic-fix
POST   /api/commands/navigation/start
POST   /api/commands/navigation/pause
POST   /api/commands/navigation/resume
POST   /api/commands/navigation/stop
POST   /api/commands/navigation/return-home
WS     /ws/telemetry
```

WebSocket 初始推送 `robot_state`、`log_snapshot`、`alarm_snapshot`，之后按状态变化继续推送快照。

## 测试

```powershell
cd "E:\Workspace\Code data\Polar Ocean Electronics Laboratory\PolarMarine_GCS\backend"
conda run -n GCS pytest -q
```

后端测试会通过夹具替换真实 ROSBridge 会话，所以测试中的网络连接可以使用文档保留地址并收到假首帧。真实运行不会使用该夹具，普通网络连接必须有可达的 rosbridge_server 和合法 `/gcs/robot_state` 数据。

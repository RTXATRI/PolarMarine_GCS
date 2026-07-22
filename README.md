# PolarMarine GCS 无人设备上位机

PolarMarine GCS 是一个面向 Windows 本地运行的 Web 上位机 Demo。当前工程由 Vue 3 前端和 FastAPI 后端组成：前端负责 GUI、摄像头画面、地图态势和交互；Python 后端负责固定设备名册、连接配置、连接状态、遥测快照、日志报警和 ROSBridge 通讯。

## 当前架构

```text
浏览器前端(Vue/Vite)
  |-- HTTP: 初始化设备、日志、报警、参数、连接操作
  |-- WebSocket: 接收机器人状态、日志、报警、遥测推送
  |-- MediaDevices: 仅在设备已连接时打开本机摄像头/图传采集卡

Python 后端(FastAPI)
  |-- 内存状态: robots/logs/alarms/parameters
  |-- 连接管理: 串口打开/占用检测、每设备 ROSBridge 会话、断线恢复
  |-- 持久配置: 只保存连接配置，不保存在线状态和遥测

ROS1 / rosbridge_server
  |-- /gcs/robot_state: 机载端发布 MAVROS 汇总状态
  |-- /usv_std/relay/set_enabled: CL-USV 电磁固定控制
```

前端不再维护独立的机器人 mock 名册，也不再运行前端遥测 tick。需要虚拟演示数据时，由后端在明确的连接场景中提供。

## 目录结构

```text
backend/                 Python FastAPI 后端
  app/api/routes/        HTTP API
  app/services/          状态、连接、ROSBridge、任务模拟、数据映射
  app/models/            Pydantic 数据模型
  tests/                 后端 pytest
src/                     Vue 3 前端
  components/connection/ 设备连接面板
  components/video/      本机摄像头/图传显示
  components/layout/     顶部栏、侧栏、右侧状态、底部日志
  stores/                Pinia 状态
  services/              HTTP/WebSocket 数据源
  views/                 总览、地图、手动控制、任务、参数、日志报警
tests/frontend/          前端 Vitest
```

## 启动方式

需要 Node.js 18+、npm 和 conda 环境 `GCS`。建议分别打开两个 PowerShell 窗口。

后端：

```powershell
conda activate GCS
cd "E:\Workspace\Code data\Polar Ocean Electronics Laboratory\PolarMarine_GCS\backend"
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

前端：

```powershell
cd "E:\Workspace\Code data\Polar Ocean Electronics Laboratory\PolarMarine_GCS"
npm.cmd install
npm.cmd run dev
```

浏览器打开 Vite 输出的地址，通常是 <http://127.0.0.1:5173>。本机摄像头权限建议使用 `localhost` 或 `127.0.0.1` 访问，局域网 HTTP 地址可能被浏览器安全策略拒绝。

根目录 `.env` 可覆盖前端后端地址：

```dotenv
VITE_GCS_API_BASE=http://127.0.0.1:8000/api
VITE_GCS_WS_URL=ws://127.0.0.1:8000/ws/telemetry
```

## 设备状态规则

- 后端每次启动时，固定设备名册会加载为未连接状态。
- 电池、模式、位置、高度、速度、航向、链路、报警、轨迹等运行字段在未连接时均显示未知。
- `connectionProfile` 只表示上次保存的连接配置；它不会让设备自动上线。
- `online` 是兼容字段，只由 `connection.state === "connected"` 派生。
- 总览页按已连接、连接中、其他状态稳定排序，方便优先查看在线设备。
- 后端或 WebSocket 中断时，前端会停止摄像头媒体流、禁用控制，并自动重连后端。

## 连接与图传

总览页右侧区域会根据当前设备状态切换：

- 未连接、连接失败：显示连接配置面板。
- 连接中：显示连接进度。
- 已连接：显示 2x2 摄像头/图传画面和断开按钮。

串口连接会枚举并打开 Windows COM 口，支持 `9600/19200/38400/57600/115200`，默认 `115200`，当前固定为 8-N-1。本阶段串口只完成硬件打开、占用、拔出和断开闭环，不解析设备协议，因此不会产生遥测，控制和参数接口也会返回操作通道不可用。

网络连接会按设备配置的 IP 和端口建立每设备 ROSBridge 会话，并等待 `/gcs/robot_state` 的第一帧合法状态。普通 UAV/USV 需要真实 ROSBridge 与机载状态发布；`SmartDock-1` 使用测试地址 `192.0.2.42:9090` 时会进入后端虚拟演示状态。

局域网搜索当前实现为对活动私有 IPv4 网段的端口探测，用户也可以手工输入未被搜索到的 IPv4 地址。

摄像头/图传由浏览器 `navigator.mediaDevices.getUserMedia()` 打开。设备未连接或后端不可用时不会枚举、授权或打开摄像头；切换设备、断开连接或后端掉线时会释放已有媒体轨道。

## ROS1 状态接入

机载端需要启动 `rosbridge_server`，并以约 2 Hz 在 `/gcs/robot_state` 发布 `std_msgs/String`，字符串内容为版本化 JSON：

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

`robotId` 必须与当前连接设备一致；`sourceConnected=false` 表示 ROSBridge 可达但 MAVROS/PX4 不可用。GPS 缺失或非法时，后端会使用稳定展示坐标兜底。任务状态由上位机的虚拟任务服务维护，延迟、丢包和 RSSI 在没有真实来源前保持未知。

## 常用接口

```text
GET    /api/health
GET    /api/robots
GET    /api/logs
GET    /api/alarms
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

控制、任务和参数接口要求设备已连接且具有 `commandMode`。PX4 网络连接当前提供虚拟操作反馈，不向飞控发布通用控制；CL-USV 电磁固定会通过当前 ROSBridge 会话发布真实继电器命令。

## 验证

```powershell
cd backend
conda run -n GCS pytest -q

cd ..
npm.cmd test
npm.cmd run type-check
npm.cmd run build
```

真实串口验收建议准备一个空闲 COM 口和一个已被串口助手占用的 COM 口，分别验证连接成功、占用失败、主动断开和拔出后的错误状态。真实 ROSBridge 验收需要确认防火墙放行、端口可达、`/gcs/robot_state` 话题存在且 JSON 契约正确。

## 运行产物

连接配置保存到 `backend/runtime/device_profiles.json`。该文件只保存串口或网络配置，不保存在线状态、遥测、日志或报警；`backend/runtime/` 属于运行时输出，不纳入 Git。


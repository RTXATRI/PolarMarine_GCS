# PolarMarine GCS

PolarMarine GCS 是面向 Windows 单工作站的多智能体地面控制系统。它以真实设备状态为唯一事实来源，支持动态设备模板、多链路热备、ROS 1/ROS 2、串口 JSON、显式仿真、命令 ACK、任务编排、MCAP 录制、在线/离线地图和本机 UVC 视频。

当前设计容量为 50 台已配置设备、20 台同时在线。软件启动或后端重连后，所有已保存设备都保持离线，直至驱动重新完成身份握手；配置、连接会话与实时遥测是三个独立概念。

## 架构

```text
Vue 3 / TypeScript
  REST /api/v1       WebSocket /api/v1/events       MediaDevices
          \                    |                         /
                    FastAPI composition root
  domain <- application ports/use-cases <- infrastructure/interfaces
                    |                  |
          SQLite WAL + MCAP       DriverSupervisor
                                     |
              ros1 | ros2 | serial_json | simulator 子进程
                                     |
                    PolarMarine v1 设备协议
```

关键约束：

- 前端不推进任务、生成遥测、确认告警或制造命令成功；仿真只能来自带永久标识的 `simulator` 驱动。
- 一条 `Device` 只保存档案；一台设备可以保存并运行多条 `LinkProfile`/`LinkSession`。
- 普通命令经健康且能力匹配的当前路由发送；急停使用同一个 `commandId` 向所有健康控制链路扇出，并等待设备状态确认。
- 所有定位数据保持 WGS-84；BD-09 只存在于百度地图适配器。
- FastAPI 进程不导入 ROS 或持有串口句柄；硬件资源由受监管驱动子进程隔离。

详细边界和状态流见 [架构说明](docs/architecture/README.md) 与 [ADR](docs/architecture/decisions/)。

## 目录

```text
backend/src/polarmarine_gcs/
  domain/             无框架领域模型与状态机
  application/        用例及端口
  infrastructure/     SQLite、MCAP、驱动 IPC
  interfaces/         FastAPI REST/WebSocket
  bootstrap/          配置、迁移、依赖注入、生命周期
backend/drivers/       ROS1、ROS2、串口、仿真驱动进程
agent_adapters/        ROS1 rospy / ROS2 rclpy 设备端适配包
contracts/             OpenAPI、设备、IPC、串口协议契约
src/                   Vue Feature-Sliced 结构
packaging/windows/     PyInstaller one-folder 发布
tests/                 前端单元与 Playwright 测试
```

## 本地开发

要求 Python 3.11、Node.js 22 或 24、npm。Windows 上可继续使用已有 conda `GCS` 环境。

```powershell
cd backend
python -m pip install -e ".[drivers,dev]"
python -m polarmarine_gcs.bootstrap.launcher
```

另开终端：

```powershell
npm.cmd ci
npm.cmd run dev
```

访问 <http://127.0.0.1:5173>。UVC 摄像头应通过 localhost/127.0.0.1 打开；普通局域网 HTTP 地址可能不满足浏览器媒体安全上下文要求。

后端默认仅监听 `127.0.0.1:8000`。接口文档位于 <http://127.0.0.1:8000/api/v1/docs>。前端开发服务器把 `/api` 和 WebSocket 代理到本机后端。

配置从 `backend/.env` 读取，示例见 [backend/.env.example](backend/.env.example)。百度 AK 只允许写入本机配置 `GCS_BAIDU_MAP_AK`，不会进入 HTML 或源码。离线地图可通过 `GCS_OFFLINE_MAP_ROOT` 提供本地 `style.json`、PMTiles 或栅格资源。

## 实机接入

正式 ROS 设备必须部署对应的 `agent_adapters/ros1` 或 `agent_adapters/ros2` 包并发布 `/polarmarine/v1/device_info`、心跳和状态；仅能连接 rosbridge、但没有完成 PolarMarine 身份握手的端点只用于 ROS 调试控制台。

串口使用 `0x1E + compact JSON + 0x09 + CRC32 + 0x0A`，JSON 与 ROS 共用同一消息信封、序号和命令语义。协议细节见 [串口契约](contracts/serial_protocol/README.md)；驱动扩展见 [驱动说明](backend/drivers/README.md)。

浏览器只保存“逻辑媒体通道到本工作站 UVC 设备”的绑定（IndexedDB）。设备离线、后端中断或组件卸载时会取消延迟打开并释放全部媒体轨道。

## 验证

```powershell
cd backend
python -m ruff format --check src tests drivers tools alembic ../agent_adapters
python -m ruff check src tests drivers tools alembic ../agent_adapters
python -m mypy
python -m compileall -q src drivers tools alembic ../agent_adapters
python -m pytest --cov=polarmarine_gcs.domain --cov=polarmarine_gcs.application

cd ..
npm.cmd run check
npm.cmd run test:e2e
```

重新生成公共契约：

```powershell
cd backend
python tools/export_openapi.py ../contracts/openapi/polarmarine-gcs-v1.json
cd ..
npm.cmd run generate:api
```

CI 在 Windows 上执行契约漂移、Ruff、mypy、全后端与 ROS 适配包编译、pytest、前端 85% 覆盖率门槛、Playwright、生产构建和 PyInstaller one-folder 打包。

## 发布与运行数据

```powershell
./packaging/windows/build.ps1
```

发布目录为 `backend/dist/PolarMarine_GCS/`。启动器打开本机浏览器并监管 FastAPI 与四个驱动入口。运行数据默认位于源码模式的 `backend/runtime/`，打包模式位于 `%LOCALAPPDATA%/PolarMarine_GCS/`：

- SQLite WAL：配置、任务、命令、事件和告警；
- `recordings/`：每个任务运行一个 MCAP 文件，默认 30 天或 20 GiB；
- `backups/`：数据库升级前备份，默认保留 5 份；
- `logs/`：10 MiB 轮转日志，默认保留 10 份。

首次升级时若数据目录存在旧版 `device_profiles.json`，后端会把合法串口配置迁移为 `serial_json` 链路、网络配置迁移为 ROS1 链路，然后将原文件改名为带时间戳的 `.imported-*` 归档；迁移只保存配置，绝不恢复在线状态。损坏文件会保留原位并产生告警。

发布和实机验收边界见 [发布清单](docs/operations/release-checklist.md)。没有接入目标硬件时，自动化测试只能证明协议与状态机行为，不能替代串口、rosbridge、飞控急停和八小时负载实测。

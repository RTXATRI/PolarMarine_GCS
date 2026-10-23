# PolarMarine GCS Backend

后端是本地 GCS 的唯一业务事实来源。它使用 Python 3.11、FastAPI、SQLAlchemy 2、SQLite WAL、Alembic 与 MCAP，并通过 Composition Root 注入全部有状态依赖。

## 分层规则

```text
domain          纯 dataclass、枚举与状态；不得导入 Web、ORM、Pydantic、ROS 或 serial
application     用例与抽象端口；组织连接、遥测、命令、任务、参数和事件
infrastructure  端口实现；SQLite、MCAP、长度前缀 IPC 和驱动监管
interfaces      Pydantic/FastAPI 边界；camelCase DTO、统一错误和增量事件流
bootstrap       Settings、Alembic、DI、启动/关闭、日志和静态前端
```

不存在模块级可变服务单例。每次应用生命周期创建一个 `Container`，关闭顺序为命令计时器、遥测、链路/驱动、录制和数据库。数据库只恢复配置与历史，不恢复在线会话或实时遥测。

## 运行

```powershell
python -m pip install -e ".[drivers,dev]"
python -m polarmarine_gcs.bootstrap.launcher
```

开发环境也可直接运行：

```powershell
python -m uvicorn polarmarine_gcs.bootstrap.app:app --host 127.0.0.1 --port 8000
```

公共接口统一位于 `/api/v1`：

- `/bootstrap`、`/devices`、`/device-templates`；
- `/devices/{id}/links` 与异步连接/断开；
- `/devices/{id}/commands`、`/commands`；
- `/missions`、`/mission-runs`；
- `/telemetry/snapshots`、`/events`、`/alarms`、`/recordings`；
- `/discovery/network`、`/debug/serial/ports`、`/debug/ros`；
- `/support-bundle`；
- WebSocket `/events`（完整路径 `/api/v1/events`）。

OpenAPI 文档为 `/api/v1/docs`。错误固定返回 `error.code/message/details/requestId`，内部使用英文稳定代码，中文只由前端翻译。

## 驱动与链路

`DriverSupervisor` 从 `contracts/driver_plugins/*.json` 加载版本化清单，按驱动类型启动独立子进程。IPC 是 4 字节大端长度加 UTF-8 JSON，最大 1 MiB；stdout 只能输出帧，日志写 stderr。驱动每秒心跳，核心检测三次缺失后按 1/2/4/8 秒退避重启并重建期望链路；单条链路失败也按相同退避重新握手，身份不匹配除外。

链路状态固定为：

```text
stopped -> starting -> handshaking -> healthy/degraded
                                      |       |
                                      +-> recovering/failed
```

遥测按信号组从单一可信链路选源，每个值带采集时间、接收时间、来源链路、质量和单位。普通命令只选当前健康路由；非幂等命令在 ACK 不确定时不静默重发。主链路恢复需连续健康 10 秒、无在途命令且跨过 30 秒防抖窗口后才能回切。

## 命令与任务

命令终态来自驱动/设备 ACK 与可选状态确认：

```text
queued -> dispatched -> accepted -> in_progress -> completed
                    \-> rejected / timed_out / cancelled / state_unconfirmed
```

急停向全部健康控制链路发送同一 `commandId`。单链路送达不能推导设备已停止；全部发送失败或状态未确认会生成严重告警。

任务计划是版本化 DAG，每次保存保留版本记录，每个 `MissionRun` 持有不可变步骤快照。启动前检查模板能力、健康路由、定位/电池新鲜度及返航 Home 点；任务运行期间只录制被分配设备的原始与归一化数据。进程中断后活动任务和 MCAP 标为中断，不伪造继续运行。

参数先通过设备命令读取并保存已确认基线，写入只发送差异。设备返回逐项结果；出现部分写入失败时，核心仅在存在已确认基线时自动回滚，否则产生严重告警并保留真实失败结果。

## 数据与升级

SQLite 使用 WAL、外键与 Alembic。升级已有数据库前自动备份并按 `GCS_DATABASE_BACKUP_COUNT` 清理旧备份。MCAP 按天数和总空间双阈值清理；事件记录不随录制删除。支持包只导出脱敏的设置、快照和诊断信息。

旧版 `device_profiles.json` 在首次启动时按确定性链路 ID 一次性导入并归档；串口映射到 `serial_json`，旧网络 rosbridge 映射到 ROS1。无论导入多少配置，`LinkSession` 都不会被恢复为在线。

核心环境变量见 `.env.example`。所有路径可指向本机受控目录；打包模式默认使用 `%LOCALAPPDATA%/PolarMarine_GCS`。

## 测试

```powershell
python -m ruff format --check src tests drivers tools alembic ../agent_adapters
python -m ruff check src tests drivers tools alembic ../agent_adapters
python -m mypy
python -m compileall -q src drivers tools alembic ../agent_adapters
python -m pytest --cov=polarmarine_gcs.domain --cov=polarmarine_gcs.application
```

架构测试阻止框架进入领域层、旧模型/API 回流、设备名分支、浏览器业务模拟和源码备份压缩包重新提交。

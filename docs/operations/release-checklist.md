# 发布与实机验收清单

## 自动化门禁

- OpenAPI 与生成 TypeScript 无漂移。
- Ruff format/check、mypy strict、pytest 与领域/应用层覆盖率 >= 90%。
- TypeScript、ESLint、Stylelint、Store/composable 覆盖率 >= 85%、生产构建与 Playwright 通过。
- `npm audit --omit=dev --audit-level=high` 无运行时漏洞。
- PyInstaller one-folder 能生成核心与四个驱动可执行文件。

## 每次实机发布

- 使用空闲串口和被占用串口验证枚举、占用、拔出恢复、CRC 错误重同步。
- 分别对 ROS1/ROS2 验证身份、能力、自定义话题、乱序/过期数据与调试隔离。
- 两链路在线时切断主链路，确认三个心跳周期内切换；恢复后验证稳定窗口与防抖。
- 对急停测试单链路失败、全部失败、ACK 但状态未确认，并核对严重告警。
- 验证任务暂停/恢复/取消、设备掉线、MCAP 中断读取与支持包脱敏。
- 验证百度地图、完全断网本地地图、坐标往返和无 GPS 时不显示演示位置。
- 验证摄像头占用、拒绝授权、延迟打开后离线、切换和轨道释放。
- 运行 20 台设备、每台 2 链路、每链路 10 Hz 的 8 小时稳定性测试，并保存版本、硬件、P95 延迟、队列峰值和内存曲线。

隔离的仿真基线可通过以下命令运行；它使用临时数据库和真实驱动子进程，不修改日常设备配置：

```powershell
cd backend
python tools/soak_test.py --duration-seconds 28800 --devices 20 --links-per-device 2 --output soak-result.json
```

未完成本清单中的硬件项时，构建只能标记为工程候选版，不能标记为实机验收完成。

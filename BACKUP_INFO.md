# PolarMarine_GCS 核心源码备份

- 创建时间：2026-07-22 01:25:59（Asia/Shanghai）
- 来源目录：`E:\\workspace\\Code data\\PolarMarine_GCS`
- 备份类型：核心源码可恢复快照
- 原始载荷：111 个文件，共 569,527 字节

## 已包含

- 前端源码 `src/`、前端测试 `tests/` 与 `public/favicon.svg`
- 后端源码 `backend/app/`、测试 `backend/tests/` 与实验源码 `backend/exp/`
- 前后端 README、依赖清单、依赖锁文件、构建与测试配置
- `.gitignore`、`.gitattributes` 以及前后端 `.env.example` 配置模板
- 执行备份时磁盘上的未提交和未跟踪核心源码

## 已排除

- 本机配置 `.env` 与运行状态 `backend/runtime/`
- 媒体目录 `data/` 与 `public/videos/`
- Git 元数据 `.git/`
- `node_modules/`、`dist/`、Python 缓存、测试缓存和日志
- `.agents/`、`.codex/` 以及其他备份目录

## 恢复说明

1. 将本目录复制到新的工程位置。
2. 按需从 `.env.example` 创建本机 `.env`，不要直接复用旧机器的配置。
3. 前端执行 `npm.cmd install`，后端执行 `python -m pip install -r backend/requirements.txt`。
4. 使用 `SHA256SUMS.txt` 检查文件完整性。该清单覆盖所有载荷文件和本说明文件，不包含清单自身。

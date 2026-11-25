# 分支结构说明

本仓库在 GitHub 上维护三个分支与两个历史归档标签，按目标硬件清晰隔离：

| 引用 | 定位与内容 | 入口 |
|---|---|---|
| `master` | 完整统一主线（RK3588 识别服务 + 桌面工作台/控制台 + ESP32-S3 固件） | [项目状态](docs/PROJECT_STATE.md)、[LiDAR Studio](pc_apps/lidar_studio/README.md)、[ESP32-S3](firmware/esp32s3_human/README.md) |
| `rk3588` | **RK3588 专用分支**：ROS1/ROS2 驱动、`human_fall_detection`（含 `--instant-start` 开机直接算与后台无感精修、`human_physical_v1`）、`human_capture`、`human_follow_calibration`、PC 端 `LiDAR Studio` / `console_v2` / `webui`（不含 `firmware/esp32s3_human/`） | [项目状态](docs/PROJECT_STATE.md)、[LiDAR Studio](pc_apps/lidar_studio/README.md) |
| `esp32s3` | **ESP32-S3 专用分支**：`firmware/esp32s3_human/`（纯 C++17 免空场运动学核心 v4 含防悬挂鸟粘连修复、ESP-IDF W5500 固件、RK3588 侧 `:8896` 轻量看板）及离线回放所需的最小 IFW192S 标定表/解码模块 | [ESP32-S3 README](firmware/esp32s3_human/README.md) |
| `archive/algo-3d-20261122` (`39f0424`) | 历史归档：独立 3D 点云算法链（`human_fall_node.py` / `single_target_node.py`） | 只读归档标签 |
| `archive/algo-2d3d-20261122` (`f79d861`) | 历史归档：2D 距离图→3D 全链快照 | 只读归档标签 |

## 两条硬件线的关系

- **`rk3588` 分支**面向带 ROS1/ROS2 驱动的 RK3588 开发板与 PC 可视化工作台，默认支持传统 `--declare-empty-prefix` 与免空场 `--instant-start`（开机直接算 + 后台无感地面精修）两种模式，可选叠加 `human_physical_v1` 物理人体增强与局部肢体回收。
- **`esp32s3` 分支**面向 ESP32-S3 + W5500 单片机直连 IFW192S，全静态 `float32` 零堆分配（工作区 ~1.01 MB），开机 0 帧免空场、免地面拟合，通过 Protocol 2 串口输出目标与 `FALL_SUSPECTED` 候选。
- 两条硬件分支均从同一 `master` 基线切分，互不交叉合并；后续如需同步公共改动，以 `master` 为源头分别发布。

## 历史算法线备忘

- `archive/algo-3d-20261122` 与 `archive/algo-2d3d-20261122` 保留了 2026-10-29 拆分时的两条纯软件算法链完整提交历史；其中 `core/range_features.py` 与 `core/range_contract.py` 作为共享几何原语存在于两条线中，冻结配置（`default.yaml`、`geometry.yaml`、`geometry_constrained*.yaml`）保持一致。
- 项目操作和验证遵循 [项目工作流](docs/PROJECT_WORKFLOW.md)。

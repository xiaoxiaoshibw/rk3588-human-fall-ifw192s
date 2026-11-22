# 主线与算法历史

自 2026-11-22 起，GitHub 使用 `master` 作为唯一维护分支。主线包含 3D 点云链、2D 距离图→3D 链及 ESP32-S3 人体跟踪 v3。两条算法线在 2026-10-29 从同一个提交分出，归档标签保留各分支的完整历史。

| 引用 | 内容 | 入口 |
|---|---|---|
| `master` | 两条算法链、桌面应用、控制台和 ESP32-S3 v3 | [项目状态](docs/PROJECT_STATE.md)、[ESP32-S3 v3](firmware/esp32s3_human/README.md) |
| `archive/algo-3d-20261122` (`39f0424`) | 原 `algo-3d` 的独立 3D 点云算法链，包括 `human_fall_node.py` 和 `single_target_node.py` | `roslaunch human_fall_detection human_fall.launch` |
| `archive/algo-2d3d-20261122` (`f79d861`) | 原 `algo-2d3d` 的 2D 距离图→3D 全链，含 `RangeEngine`、`RangeRuntime`、`range_service_node` 和 Qt 控制台 | `roslaunch human_fall_detection range_service.launch` |

## 两条线的关系

- 2D→3D 链建立在 3D 几何核心之上。`core/range_runtime.py` 直接依赖 `baseline`、`features`、`fall_state`、`lidar_candidates`、`human_prior`、`support_composition` 和 `candidate_history`。两个归档版本之间的源码差异主要来自 2D 距离图链及其入口。
- 两个小模块 `core/range_features.py`、`core/range_contract.py` 被 3D 的 `core/human_prior.py` 直接引用，作为几何/字段绑定原语保留在 `algo-3d` 上，不随 2D 链一起移除。
- 冻结配置（`default.yaml`、`geometry.yaml`、`geometry_constrained*.yaml`）两个分支一致，不因分支不同而改阈值。

## `algo-3d` 上被移除的内容

- `core/range_image|components|denoise|background|tracker|runtime|posture|shape|skeleton|engine|service|live|offline|png|wire|site_ground|fit_job|demo_alert|ground_alert.py`
- `scripts/range_image_node.py`、`scripts/range_service_node.py`、`scripts/replay_range_frontend.py`、`scripts/replay_range_tracking.py`、`scripts/prepare_range_service_bundle.py`
- `config/range_service_v1.json`、`launch/range_service.launch`
- 依赖上面模块的测试与应用：`tests/test_range_*.py`、`tests/test_episode_continuity.py`、`tests/test_online_continuity.py`、`pc_apps/range_fall/`、`pc_apps/annotator_v2/`、`pc_apps/bathroom_demo/`、`console_v2/`、`tools/range_*.py`、`tools/human_2d3d_package/`、`pc_apps/demo_viewer/pseudo_live.*`、`pc_apps/demo_viewer/demo_alert.py`
- 文档（`docs/RANGE_*.md`、`docs/LOCAL_RANGE_LIVE.md` 等）保留在两个分支上作为历史记录，里面引用的文件在 `algo-3d` 上不存在。

## 维护约定

- 后续开发使用 `master`。归档标签用于定位历史版本。
- 项目操作和验证遵循[项目工作流](docs/PROJECT_WORKFLOW.md)。

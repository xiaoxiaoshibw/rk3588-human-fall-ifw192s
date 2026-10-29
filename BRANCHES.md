# 分支说明：3D 点云链 / 2D 距离图→3D 链

2026-10-29。仓库里的两条算法线拆在两个长期分支上，`master` 保留全部内容；两个分支都从 `master` 的同一个提交拉出。

| 分支 | 承载 | 入口 |
|---|---|---|
| `master` | 全部：3D 点云链 + 2D 距离图→3D 链 + 全部应用与控制台 | 见 [docs/PROJECT_STATE.md](docs/PROJECT_STATE.md) |
| `algo-3d` | 纯 3D 点云算法链（`core/` 的 3D 模块 + `scripts/human_fall_node.py` / `scripts/single_target_node.py`），不含 2D 径向距离图链及其消费者 | `roslaunch human_fall_detection human_fall.launch` |
| `algo-2d3d` | 2D 径向距离图 → 同源 3D（`core/range_*.py`、`RangeEngine`/`RangeRuntime`、`range_service_node`、`pc_apps/range_fall`、Qt 控制台等），3D 几何核心作为依赖一并保留 | `roslaunch human_fall_detection range_service.launch` |

## 两条线的关系

- 2D→3D 链建立在 3D 几何核心之上：`core/range_runtime.py` 直接依赖 `baseline`、`features`、`fall_state`、`lidar_candidates`、`human_prior`、`support_composition`、`candidate_history`。因此 `algo-2d3d` 是 `algo-3d` 的超集，两个分支的差集就是 2D 距离图这条线新增的源码与入口。
- 两个小模块 `core/range_features.py`、`core/range_contract.py` 被 3D 的 `core/human_prior.py` 直接引用，作为几何/字段绑定原语保留在 `algo-3d` 上，不随 2D 链一起移除。
- 冻结配置（`default.yaml`、`geometry.yaml`、`geometry_constrained*.yaml`）两个分支一致，不因分支不同而改阈值。

## `algo-3d` 上被移除的内容

- `core/range_image|components|denoise|background|tracker|runtime|posture|shape|skeleton|engine|service|live|offline|png|wire|site_ground|fit_job|demo_alert|ground_alert.py`
- `scripts/range_image_node.py`、`scripts/range_service_node.py`、`scripts/replay_range_frontend.py`、`scripts/replay_range_tracking.py`、`scripts/prepare_range_service_bundle.py`
- `config/range_service_v1.json`、`launch/range_service.launch`
- 依赖上面模块的测试与应用：`tests/test_range_*.py`、`tests/test_episode_continuity.py`、`tests/test_online_continuity.py`、`pc_apps/range_fall/`、`pc_apps/annotator_v2/`、`pc_apps/bathroom_demo/`、`console_v2/`、`tools/range_*.py`、`tools/human_2d3d_package/`、`pc_apps/demo_viewer/pseudo_live.*`、`pc_apps/demo_viewer/demo_alert.py`
- 文档（`docs/RANGE_*.md`、`docs/LOCAL_RANGE_LIVE.md` 等）保留在两个分支上作为历史记录，里面引用的文件在 `algo-3d` 上不存在。

## 维护约定

- 两条线各自提交，不互相 merge；需要合并时先回到 `master`。
- 分支上的算法改动同样适用仓库红线：不部署、不采集、不训练、不改驱动/网络、不动 `data/` 与 `captures/` 三个 junction。
- 语义诚实不变：没有人体/跌倒真值时准确率、召回率写 UNKNOWN；`confirmed` 保持关闭。
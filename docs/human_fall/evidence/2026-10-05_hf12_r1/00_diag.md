# HF-12 实现前集中诊断（00_diag）

2026-10-05。writer：OpenCode（`opencode-go/deepseek-v4.1-flash`，本会话）。ponytail（full）经 skill 工具加载。本文件写于任何生产代码修改之前。

## 0. 结论（最小修复位置）

用户流水线首段“滤波降噪”在 HF 感知链中缺失。最小实现：在 `src/human_fall_detection/core/lidar_candidates.py` 的 `build_snapshot` 内，于**有限值剔除 → `max_points` 抽稀 → 距离带**之后、**高度带（依赖地面）/冻结背景/水平聚类**之前插入 `denoise_mask`（体素邻域计数，含自身）；新增三个 `resolve_settings` 键（core 默认关闭），并在 `config/perception.yaml` 的 `candidates` 段启用。不动 `voxel_size_m`（HF-09 预留）、地面拟合/配平、跟踪/状态机、网页、驱动。

## 1. 生产链现状与实际函数/赋值顺序

`build_snapshot`（`lidar_candidates.py:561-701`）现状顺序：
1. `resolve_settings`（60-83）→ `np.asarray` → finite 过滤 → `max_points` 等步长抽稀（572-582）。
2. 距离带 `keep`（584-585）。
3. `basis = ground_plane_basis(ground) if ground_frame_eligible(...) else None`（590-591，异 frame 守卫）。
4. 高度带 `keep &= n·p+d`（592-594）；一次性应用到 `array/original_indices`（595-596）。
5. 冻结背景 `foreground_mask`（598-601）。
6. `_horizontal_coords` + `_connected_clusters`（603-604）。
7. `_validated_ground_derived`、reference、候选循环（606-637）；`quality`（662-671）；返回（672-701）。

本单插入后顺序：有限值 → 抽稀 → 距离带 → **denoise** → 高度带 → 背景 → 聚类。降噪输入因此不依赖地面/背景，`original_indices` 随每级同样过滤。

## 2. 设置与兼容事实

- `DEFAULT_SETTINGS`（39-53）现有候选键全部有默认值；`resolve_settings` 对未知键抛 `ValueError`（63-65）。新增键必须同时进 `DEFAULT_SETTINGS`、`_POSITIVE`（用于 `denoise_radius_m`）或单独校验。
- `settings`（697）与 `quality`（662-671）都是**加性**字段：`validate_snapshot`（724-774）只校验 kind/schema/session/candidate 结构与语义，不拒绝新增键；`webui/human_fall_preview/human_fall_lib.js` 的 `validSnapshot` 只检查固定键，未知键忽略。`node_runtime.project_snapshot_for_ros`（约135-158）浅拷贝透传 `quality`。
- 配置链：`human_fall.launch`/`human_fall_node.py:131-158` 默认读 `config/perception.yaml`；`FallNodeCore` 以 `sections["candidates"]` 调 `build_snapshot`（`node_runtime.py:710-720`）；`fall_replay.py --config` 同源。测试中只有 `test_hf06` 加载 `perception.yaml`（只取 `fall` 段）；`test_hf04/hf07` 传显式 settings 或空，因此 **core 默认关闭**可保证既有行为逐字节不变。

## 3. 操作/入口矩阵（M01-M08 → 验收 ID）

| 操作/状态 | 实际入口 | 预期 | 覆盖 ID |
|---|---|---|---|
| M01 默认/显式关闭 | `build_snapshot(settings=None/{"denoise_enabled": false})`；node/replay 未启用时 | 不走新分支；点数/候选/证据索引同改前；`quality.denoise` 加性存在且 dropped=0 | H01/H03/H06 |
| M02 启用、无地面 | `ground=None`，range 过滤后 60k 内 | 仅 denoise+背景+聚类；`ground_relative_available=false` 原样 | H02 |
| M03 启用、有地面 | 合法 ground（`ground_frame_eligible` 通过） | denoise 在高度带前，计数与 M02 对同一点云一致；高度带照旧 | H04 |
| M04 背景扣除顺序 | `background` 非空 | 背景点在 denoise 阶段参与邻居支撑；扣除在 denoise 后 | H04 |
| M05 边界 | 空云 / 单点 / 跨体素相邻两点 / 抽稀后 | 空→空掩码；单点按 min 语义；相邻两格互支撑；无不一致 | H02 |
| M06 非法参数 | `denoise_enabled=1/"yes"`、`radius=0/nan`、`min=0/True`、未知键 | 全部 `ValueError`；旧 settings 快照回灌可解析 | H03 |
| M07 快照 | 启用快照两跑 + `validate_snapshot` + `dumps_strict` | schema1、无 NaN、两次一致；`evidence_indices` 映射原始点 | H05 |
| M08 配置 | `load_config(perception.yaml)["candidates"]` | `resolve_settings` 得到 enabled/0.1/2；node/replay 源路径可达 | H06 |

## 4. 保留与失效行为

- 保留：所有既有键语义与默认值；关闭路径的行为与改前完全一致；快照 schema_version=1；候选 ID/证据索引契约；`voxel_size_m` 仍为 HF-09 预留未用状态。
- 失效：无（不删键、不改既有阈值）。新增语义仅在 `denoise_enabled=true` 时生效；其近似性（体素计数、非精确 pairwise 半径）在代码 `ponytail:` 注释与本单回传中明示。

## 5. 检查计划

- 新增 `tests/test_hf12_denoise.py`：M01-M07 逐条（含顺序反例：高度带下方点作为上方点邻居、背景点作为前景点邻居）。
- 配置检查：`perception.yaml` + `resolve_settings`（M08）。
- 回归：`python -B -W error -m unittest discover -s src/human_fall_detection/tests` 改前（已录 `02_tests_before.txt`）/改后对照。
- 探针：60k 点规模 `denoise_mask` 计时与合成删除计数，落 `04_denoise_probe.txt`；SHA 落 `05_sha_after.txt`。

# HF-12 感知链前置滤波降噪（孤立点去噪）

执行：OpenCode DeepSeek v4.1 Flash（`opencode-go/deepseek-v4.1-flash`，本会话）。依赖：HF-04（`core/lidar_candidates.py` 已实现并获审的候选链）。状态：2026-10-05 用户明确授权“好的定制工单并且开发”；作者实施并自验后 SUBMITTED / STOPPED，外部独立复审按 [WORKFLOW](../WORKFLOW.md) 另行安排，不自行 ACCEPTED。

先读 [../WORKFLOW.md](../WORKFLOW.md) 与本单唯一 [HF12_ACCEPTANCE.md](../HF12_ACCEPTANCE.md) v1；开工前读取 ponytail skill（full）。

## 背景

用户给出的目标流水线为“滤波降噪 → 地面配平 → 去除地面 → 去除静态背景 → 前景候选 → 聚类 → 人体判定 → 跟踪 → 跌倒识别”。当前 HF 候选链（`build_snapshot`）的起点是：有限值剔除 → `max_points` 抽稀 → 距离带 →（有地面时）高度带 → 冻结背景扣除 → 水平连通聚类，缺少独立“滤波降噪”一级；`voxel_size_m` 自 HF-04 起只声明并校验、全仓库未使用（HF-09 工单把它列为实测后再做的性能项，本单不动它、也不删）。

本单只做感知链内的“孤立点滤波降噪”一级，纯 NumPy/标准库、Python 3.8 / NumPy 1.17 兼容；不改进地面拟合、不新增依赖、不改跟踪/跌倒状态机/网页/驱动。

## 工作与代码

- `core/lidar_candidates.py`
  - 新增设置 `denoise_enabled`（bool，core 默认 false）、`denoise_radius_m`（>0 有限，默认 0.1）、`denoise_min_neighbors`（int≥1，默认 2）；`resolve_settings` 严格校验，未知键仍拒绝。
  - 新增 `denoise_mask(points, radius_m, min_neighbors)`：体素邻域计数——点所在的 `radius_m` 立方体加 26 个相邻立方体里的点数（含该点自身）≥ `min_neighbors` 则保留；`min_neighbors=1` 等价全保留。正常路径为稠密 int32 网格 + 可分离 `[1,1,1]` 盒求和（60k 点桌面探针约 7 ms），极小半径超网格上限时有界回退为打包 key + 27 次 `searchsorted`；确定性、无新依赖。
  - `build_snapshot` 插入位置：有限值/抽稀/距离带之后，高度带（依赖地面）、冻结背景、水平聚类之前，使降噪结果不依赖地面是否可用。关闭时不走新分支，输出除新增 `settings`/`quality.denoise` 键外与改前一致。
  - `quality.denoise`：`{enabled, radius_m, min_neighbors, input_point_count, kept_point_count, dropped_point_count}`，计数语义为进入/离开该级的点数；关闭时 enabled=false、dropped=0。
- `config/perception.yaml`：`candidates` 段启用 denoise（工程默认 `radius 0.1 m / min 2`，现场数据回调）；core `DEFAULT_SETTINGS` 保持关闭，裸调用者与既有测试行为不变。
- 不触碰：`voxel_size_m`（HF-09 预留）、`core/ground.py` 与配平模块、跟踪/跌倒状态机、网页、驱动、板端部署，不 commit/push/reset。

## 验收与回传

逐条按 [HF12_ACCEPTANCE.md](../HF12_ACCEPTANCE.md) v1 自验；证据写 `../evidence/2026-10-05_hf12_r1/`（实现前 `00_diag.md`、基线/改前 SHA、改前与改后回归、探针、改后 SHA），回传 `../returns/HF-12.md`（只写 SUBMITTED/BLOCKED）。设备/实机/物理一律 NOT_RUN。

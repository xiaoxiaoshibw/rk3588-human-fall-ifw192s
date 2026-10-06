# ROI A/B Probe 设计

## 目标
回答一个问题：当前 v1「四象限最近格贪心」是否在真实 golden 上选了次优 ROI，
损伤 ROI 条件性 / 三法一致性 / holdout 稳定性 / domain geometry。

## 两个 selector

### A = CURRENT（生产逐字）
直接调用 `floor_detector.detect_floor_regions(points, ids, 26, 0)`，取它返回的 4 区。
只为捕获 clean-cell dictionary 供 SHADOW 复用同一连通组件，用 `unittest.mock.patch.object`
旁路 hook `floor_detector.components`（不改 `floor_detector.py` 源）。
选中组件的复刻与 v1 内部一致：4-邻接连通分量，取满足 `≥8 格 & 两轴跨度≥0.5m` 的最大组。

### B = SHADOW（实验候选，绝不写回）
在 v1 已确认的**同一连通组件**内：
1. 每象限取距目标最近 `K=4` 格 → 候选池（4×4×4×4=256 组合）；
2. 组合枚举去重（4 个不同格）；
3. feasibility gate：`min_pairwise_sep ≥ 0.50m`、`condition ≥ 0.10`
   （condition 复用 v3 定义：4 中心去均值 SVD 最小/最大奇异值比）；
4. 可行集内按 v3 同哲学字典序：`(-max_rms, -mean_rms, condition↑, sep↑, key↑)`。

**关键忠实性约束**：SHADOW 只重排 v1 已认的 clean cells，不引入新格。
若换格 = 改了身份层，违背「只比 ROI selection」的工单边界。

## 同一 downstream evaluator
两个 selector 的 4 区都走**生产** `leveling_quality.compare`：
- 掩码语义复刻 `leveling.freeze_domain`（display 系矩形隶属，holdout 帧同 ordinal）；
- estimator / 质量门 / holdout 一律不动。

## 输出（见 04_results.json）
- ROI 几何：中心 / sep / condition / local_rms / max/mean rms / min_frame_count
- domain_geometry：λ2/λ3 + tangent_extents
- estimator：TLS/SVD/RANSAC 的 pitch/roll/offset/full_rms/p95/support/valid/reasons
- 三法一致性：pairwise angle/offset gap
- holdout：worst region rms + valid estimator count

## Determinism
每 selector/session 重跑 20 次，selected ROI + summary byte-stable。

# W03-R3.2 Leveled Reference → Leveled Current 跨会话 Match Audit（只读）

- 日期：2026-10-06（Asia/Shanghai）
- 性质：**只读审计，生产零改动**。不接 reference 到 production、不改 matcher 半径、不做 AABB、不碰 HUMAN_SHAPE / Tracker / leveling。
- 依据：[W03-R3 验收规范](../../W03_R3_ACCEPTANCE.md) §3 R3.2 条；用户评审意见（四层审计 + 决策树）。
- 输入：
  - reference：`cap_20261004_203349` leveled（job `c9712aca…`，pitch 26.993°、roll -2.948°、tz 1.317），R3.1 builder 输出 5286 体素。
  - current：`cap_20261002_223757` leveled（job `6bc5aabf…`，pitch 26.467°、roll -0.366°、tz 1.323），165 帧。
  - 已知风险：Δroll≈2.58°，3m 处 ≈0.135m ≈ 现行匹配半径（0.12m）量级。
- 口径：与 console 一致 —— 各自 TLS transform → `apply_Rt` → `denoise` → 参考图（R3.1 builder）/ 在线 map（`build_static_map`）。

## 四层审计

### A. Reference → Current 基础匹配（现行 matcher 完全不变）

- 规则：reference voxel center ↔ current leveled point，radius = **0.12 m**，3×3×3 邻域枚举（复刻 R3.0 `nearest_static` / R3.1 `point_match` 口径）。
- 指标：`ref_exact_hit_ratio` / `ref_neighbor_hit_ratio` / `ref_match_ratio` / `ref_min_dist_p50/p95/max`。
- 分组（leveled 坐标，m）：

| 组 | 定义 |
|---|---|
| **WD01** | 223757 静态直立物，窗口 c=(3.50, -0.76) half=0.50，帧段 f1–62（R3.0 全绿段） |
| **WD02** | 223757 远场点（range>5m 且不在 WD01/HP 窗内）——reference 里 occ≥0.5 sparse 面的对照 |
| **稳定墙体** | 223757 高占用静态点（reference occ≥0.9 对应空间位置上的 current 点） |
| **HP01/02/03** | 223757 活动目标窗口：f92–99 / f121–125 一带人体（x≈3.5,y≈-0.76 附近躺卧帧段）+ f163–164 站立 |

### B. 未匹配点距离误差空间分布

- 对未按 0.12m 匹配的 current 静态点，按 range / x / y / z / azimuth 分桶，输出每桶 `match_ratio / d50 / d95`。
- 判据：
  - `d50` 随 range 系统性增长 → **角度残差**（roll/pitch/yaw）。
  - 全距离同类固定偏移 → **平移残差**。
  - 单轴占优 → 平移主方向。

### C. 跨会话刚体残差估计（只读）

- 只取「两会话都高占用且高度稳定的静态体素子集」（reference occ≥0.9 且 jit<0.03 的体素形心 ↔ current 对应在线 map 的 strong 体素形心），做 point-to-point ICP（Kabsch，≤50 迭代，inlier 门 0.25m）。
- 输出：`Δroll / Δpitch / Δyaw / dx / dy / dz`，以及 **before vs after** 的 match_ratio / d50。
- 判据：若 after 显著恢复（match 0.35→0.90+ / d50 0.18→0.04），**优先级 = 修 session alignment，暂不进入 R3.3**；若 alignment 后仍差，才说明 matcher 几何本身有问题。

### D. WD01 定点验证

- reference 里是否存在 WD01 对应体素：以 R3.0 probe 帧 f42 ci1 的 957 点为样本，在 reference map 内做 nearest-occupied-voxel 距离分布（不做 3×3×3 邻域，直接全图最近邻以测 coverage）。
- 输出：`reference coverage`（0.12m 内最近邻占比）/ `current→reference d50` / **after rigid correction 的 d50 与 match@0.12**。

## 决策树（写进证据文档）

```
                 cross-session match audit
                           │
              ┌────────────┴────────────┐
       alignment 后明显恢复        alignment 后仍差
              │                         │
              ▼                         ▼
   优先修 session alignment       检查 matcher geometry
              │                         │
              │                    再进入 R3.3
              │                 point → voxel AABB
       暂不改 matcher
```

## 产出

- `06_r32_audit.js`（只读脚本）
- `07_r32_stats.json`（全部指标 + 分桶 + ICP 参数 + before/after）
- `08_r32_run.log`
- `09_r32_summary.md`（判定 + 决策树走向 + 下一步建议）

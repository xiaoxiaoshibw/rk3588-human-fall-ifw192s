# 02 · Clustering semantics（代码事实 + synthetic 证据）

> 结论全部来自**当前 SHA `5bce92a4…142b4`** 的代码阅读（01 有行号）与 `04_synthetic_cases.js` 的可复现实验。
> 本文件不实现任何 variant。

## 1. 直接结论（对应工单 §二 的 10 问）

| # | 问题 | 事实 |
|---|---|---|
| 1 | voxel key 包含哪些轴 | 聚类链 `voxelize`（121–140）/`key_vox`（86–88）**只有 X/Y**，`floor(x/0.15)+","+floor(y/0.15)`；Z 只进统计累加器 |
| 2 | cluster graph 在哪些维度连边 | `cluster_voxels`（394–427）BFS 邻居仅 `(x±1,y),(x,y±1)` → **XY 平面** |
| 3 | 邻接类型 | **4 邻（von Neumann）**；非 8/6/18/26；26 只属于背景 builder 与 cleanup 候选判定 |
| 4 | 是否忽略 Z | **是**。同 XY 柱不管 Z 差多远都是同一 voxel（Case A）；XY 相邻柱不管 Z 是否重叠都连边（Case C） |
| 5 | radius-based 邻接 | **无**。聚类无距离参数；`bg_match_radius=0.12` 是背景 matcher 的点级删除半径，与聚类无关 |
| 6 | morphological expansion | **无** |
| 7 | 小簇合并 | **无**。反方向：`cluster_min_voxels=3`（426）把小簇**丢弃** |
| 8 | cluster post-merge | **无** |
| 9 | candidate 阶段再次合并 | **无**。`cluster_features/classify_human/evidence_*` 均为单簇纯函数；`Tracker` 只跨帧关联 |
| 10 | AABB 角色 | 生产 matcher = 点到静态体素**形心**距离（`_bg_match`）；AABB 仅存在于 R3.3 离线脚本；WebUI 盒 = `max(0.2, 4σ)×max(0.2, 4σ)×max(0.2, height)` 的显示框，**不参与 membership** |

补充事实：

- `PIPE.cluster_neighbor_hops`（49）是**死参数**（全仓无读取），BFS 固定 1 跳。
- `cleanup_isolated_fg` 的 XY 拓扑保护**复刻**聚类 4 邻 degree（360–368）；即“4 邻”这一语义在系统内出现两次，改动一处必须同步理解另一处。
- 两套网格：背景/参考/cleanup 候选 = 3D `0.15×0.15×0.12`（`key_bg`）；聚类/证据查表 = XY `0.15` 柱（`key_vox`）。**不是同一套坐标**（01 §3）。
- 诊断字段 `cleanup_split_delta` 为数组相减 → 簇非空时恒 `NaN`，`topology_regression` 恒 false（01 §4，本轮只记录不修）。

## 2. Synthetic micro-cases（`04_synthetic_cases.js`，21/21 PASS）

基线设置：production `cluster_min_voxels` 临时降为 1 观察**原始分量**（运行时改动，不动文件），过滤行为单独对照。

| Case | 场景 | 结果 |
|---|---|---|
| A | 同 XY cell、Z 分离 0.3–0.5 vs 1.8–2.0 | **1 个 voxel、1 个分量**；acc zmin/zmax 横跨两结构；production 过滤下整簇被丢（单柱 <3） |
| B | XY 相邻、Z 重叠 [0.9,1.2] | 1 个分量 |
| C | XY 相邻、Z **完全不重叠**（0.2–0.5 vs 1.5–1.8） | **仍 1 个分量**；两 voxel 各自 z 区间互不重叠却同簇（VERTICAL_ALIAS 机理证明） |
| D | 两竖直柱 (0,\*) 与 (3,\*) + 唯一低层 bridge cell (2,0) z≈0.2 | 1 分量；bridge degree=2；**删 bridge → 2 分量**（两侧均 ≥3 voxel 存活） |
| E | 人体形 4 柱、Z 连续 [0.15,1.85] | 1 分量，zmin/zmax 完整 —— 人体自身不会被 4 邻拆开 |
| F1 | 人体 + 家具间隔 1 cell | 2 分量（分开） |
| F2 | F1 + 1 个低层残留 cell | **并成 1 分量（BRIDGE_MERGE）**；删该 cell → 2 分量 |
| F3 | 家具直接贴到相邻 cell（无残留点） | **仍 1 分量（XY 邻接即合并）** |
| G | 对角 cell (0,0)+(1,1) | 2 分量（4 邻不连对角 → XY8 语义边界） |
| H | 间隔 1 cell（0.15m 空隙） | 2 分量（无 hops>1；死参数印证） |

含义（供 AB 设计）：

- **任何“只加 Z”的方案不能自动分开同 XY 柱内的结构**（Case A/C）；只能分开“XY 相邻但 Z 分离”的柱体（Case C）。
- **bridge 抑制**（D/F2）在合成上可分开“单点桥”的合并；但真实帧上大合并并非单点桥（见 03 §桥接分析）。
- 人体自身在 4 邻下是连通的（Case E），说明降低邻接不会伤害干净人体而只改变跨结构连接 —— 但这必须由 AB 数据验证。

## 3. Membership 变更点清单（谁在“改点”，谁只是“贴标签”）

改点（会改变最终簇构成的）：

1. `denoise`（距窗/有限值）；
2. `extract_foreground` 的 z 裁剪 + `_bg_match` 删除；
3. `cleanup_isolated_fg` 的单遍删除（拓扑保护）；
4. `cluster_voxels` 连通分量定义 + `cluster_min_voxels≥3` 过滤。

只贴标签/只过滤候选列表（不改点、不改簇几何）：

5. `cluster_features` 的 `n<60 → ok:false`（从 `r.clusters` 移除，不显示）；
6. `classify_human` / `evidence_*` / `joint_status`；
7. `Tracker` 跨帧关联与时间确认；
8. WebUI 渲染（盒/颜色）。

## 4. 对 failure taxonomy 的直接支撑

- f10/f30/f55 的“人+物 90% 合并”(用户输入) 在本语义下有两种独立机制可复现：
  (a) XY 相邻/同柱**必然合并**（Case B/C/F3，无需任何 bridge）；
  (b) 单点残留桥会额外制造合并（Case D/F2）。
- Z 维度在整套聚类里**没有话语权**：`VERTICAL_ALIAS` 与“同柱合并”是结构性必然，不是参数问题。

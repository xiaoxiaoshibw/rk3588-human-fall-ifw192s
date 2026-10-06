# 08 · CL-01 第二阶段：Connectivity Shadow AB 计划（A/B/C/D）

- 日期：2026-10-06（Asia/Shanghai）；writer：OpenCode（DeepSeek v4.1 Flash）；ponytail 已加载（full）。
- 性质：**离线 shadow AB，production 零改动**。不采集/不部署/不 commit。
- 本计划先于实现（本文件写完后才写 09 实现）。
- 输入冻结：`human_pipe_lib.js` SHA `5bce92a4…142b4`（第一阶段已复核）；本阶段结束必须再次复核。

## 0. 本轮唯一问题

> 当前 XY-only 4-neighbor connectivity 是否是 HUMAN+STATIC merge / VERTICAL_ALIAS 的主要放大因素，
> 哪一种最小 3D connectivity 能在不破坏完整人体的前提下降低 merge。

不允许顺便修：background residual、evidence_postpass、SOLID_UNIFORM、classifier、`cleanup_split_delta`、
WebUI、tracking、background matcher、registration、reference、leveling、阈值。以上一律只记录，不进变量。

## 1. 固定变量（A/B/C/D 完全一致）

| 项 | 值 |
|---|---|
| session | `cap_20261002_223757`（current，leveled 最新 tls job，与第一阶段一致） |
| 帧集 | 全 165 帧 + 重点帧（§3） |
| registration | leveled（各自 TLS transform，无 ICP，与 production 一致） |
| 预处理 | `PL.denoise`（production） |
| 前景 | `PL.extract_foreground(fr, CUR_ONLINE)`，`CUR_ONLINE = PL.build_static_map(ded,{drop_ground:true})` 只建一次（production） |
| cleanup | `PL.cleanup_isolated_fg`（production；其内部 XY 4 邻拓扑保护保持 production 不变——它属于清理，不属于 clustering 变量） |
| 体素尺度 | XY = 0.15 m（production `PIPE.voxel_m`）；C/D 的 Z 粒度见 §2 |
| 最小簇 | `min_voxels = 3`（作用于各 variant 的“节点”：A/B/D 为 XY 柱，C 为 3D cell） |
| 下游 | `evidence_postpass / cluster_features / classify_human / joint_status` 原样（§5，仅观察） |
| 输出规则 | 不改任何 production 显示/参数 |

唯一主变量 = **clustering connectivity（含其必需的体素表示）**。B/C/D 若需要不同表示，按 §2 显式记录。

## 2. Variant 定义（实现契约）

### A — BASELINE（production 复刻）
- 节点：`voxelize` 的 XY 0.15 柱（key `"ix,iy"`）；
- 邻接：XY 4 邻 `(±1,0),(0,±1)`；Z 不参与；
- 过滤：`min_voxels=3`。
- **复刻自检**：shadow 实现 A 的 raw/filtered 分区必须与 production `PL.cluster_voxels(PL.voxelize(pts))` 逐帧一致
  （比较：簇数 + 每簇 `(key数, 点数)` 排序多重集合）；不一致即 FAIL，停止。

### B — XY8（敏感性/负向对照，不作为候选）
- 与 A 同一体素化；邻接扩展为 8 邻（`dx,dy ∈ {-1,0,1}`，非零）。

### C — XYZ26（3D 实验基线）
- 节点：**XYZ 0.15 × 0.15 × 0.15 m 等距 cell**（显式记录：isotropic 0.15，**不复用 `key_bg` 的 0.12 z，也不假设与背景体素语义相同**；使用 shadow 自有字符串 key `"ix,iy,iz"`）；
- 邻接：26 邻（Chebyshev Δ ≤ 1）；
- 过滤：`min_cells=3`（节点数 ≥3）。

### D — CONSTRAINED_3D（主候选，第一版仅一个额外几何约束）
- 节点：与 A/B 相同的 XY 0.15 柱；
- 每柱携带 **Z occupancy 位图**：占用 bin = `floor(z / 0.15)` 的集合；
- 邻接：XY 4 邻 **且** 垂直兼容门：
  `minGap(za, zb) = min_{ba∈bins(a), bb∈bins(b)} |ba-bb| * 0.15 m`，连边 iff `minGap ≤ G`；
- G 为唯一新参数，**内部 sweep**（见 §2.1）；不带任何人体先验/高度分类/家具规则/morphology/post-merge/label 反馈。

#### 2.1 G 的选取依据（不拍脑袋）
- 体素尺度 0.15 m；lidar 近场环间距 ≪0.15，远场稀疏；
- 先用 clean-human 帧（f63/65/80/85/90/92/95/99/123/146）统计“人体内部相邻柱最小 z 间隙”分布
  （p50/p95/p99），G 的 sweep 必须包含能保持 ≥99% 人体内部柱间连接的档位；
- sweep：`G ∈ {0.00, 0.15, 0.30, 0.45} m`（0 = 需共享同一 z bin；1–3 个体素）；
- 记录每档的：人体连续性代价（clean-human 是否被拆）与 merge 削减量；主候选 D* = 满足 §6 不变量前提下
  merge 削减最大的档位（若全部不满足 → D 记为失败，如实报告）。

> 说明：D 的列内不做纵向拆分（同柱=单节点，与 A 相同）——同柱堆叠（synthetic Case A）不是 D 的解决面，
> 由 C 处理；D 针对的是**相邻柱之间**的 Z 兼容性（VERTICAL_ALIAS / 跨高度弱连接）。

## 3. 数据

1. 重点帧：f10、f30、f55、f150、f155、f160（第一阶段定位）；
2. clean standing/walk/lying：f63、f65、f80、f85、f90、f92、f95、f99、f123、f146；
3. static-residual-only：f10、f30、f2（+ f42 混合）；
4. fragment-heavy：按第一阶段 `06_cluster_stats.json` 每帧 `<3 voxel` 碎片数排序取 top-3；
5. synthetic A–H（复用 `04_synthetic_cases.js` 的场景构造）；
6. **全 165 帧**（必须）。

## 4. 指标

### 4.1 Geometry（每帧每 variant）
component count（raw 与 filtered 各一份）；voxel/cell 数、点数/component；largest component ratio（点数占比）；
bbox dx/dy/dz；zmin/zmax；articulation/contact 统计（重点帧全量，全帧做 degree/boundary 汇总）；
clean-human retained-point ratio（§4.4 定义）。

### 4.2 差分分区（X vs A，同一前景点集）
- split event：A 的 raw component（≥20 点）被 X 拆 ≥2 份且次大份 ≥10% 点数 → 记一次；统计次数与点数、
  其中“含人体代理点”的 split；
- merge event：X 的 raw component（≥20 点）聚合 ≥2 个 A raw component（各 ≥10%）→ 记一次；统计次数与点数、
  其中“人体代理 + 非人体”的 merge；
- 所有差分用 raw（min=1）分区，避免与过滤混淆；filtered 数量单独报告。

### 4.3 Failure taxonomy 计数
`MERGE_STATIC_HUMAN` / `VERTICAL_ALIAS`（相邻柱 z 互不重叠仍连边的事件）/ `OVER_SPLIT_HUMAN` /
`FRAGMENT_EXPLOSION` / `STATIC_RESIDUAL_ONLY` / `CLEAN_HUMAN`（按 §4.4 代理定义，proxy ≠ GT 声明沿用第一阶段）。

### 4.4 人体代理与 retention（proxy）
- 已知位置（第一阶段同源）：clean f63(1.41,0.06)/f65(1.46,-0.11)/f80-90&f92-123(1.52,-0.40)/f146(1.29,-0.17)；
  merged f55(1.47,0.64)/f150(1.46,0.30)/f155(1.57,0.65)/f160(1.60,0.78)；WD01 f2/f42(3.50,-0.76) 静态。
- human proxy points = 前景点中 XY 距代理中心 ≤0.55 m 的点；
- retention_X = human proxy points 中落入“含多数代理点的 component”的比例；
- person component = 该 component；另记录其点数、点数-BBox、以及代理柱外的延伸量（污染 proxy）。

### 4.5 Fragmentation
`<3 voxel` 被丢组件数；small-component（<5 节点 或 <60 点）数量；存活组件数；被 `min_voxels` 门丢掉的总点数。
A 在 165 帧必须复现第一阶段值：raw 分量均值 ≈47.69、filtered 均值 ≈21.9、`<3 voxel` 碎片累计 = **4255**（容差 0）。

### 4.6 Runtime
- clustering-only（每 variant 的图构建+BFS+聚合）；
- total shadow pipeline（denoise+fg+cleanup+clustering，共享段只测一次，按 variant 叠加）；
- 报告 mean / p50 / p95 / max（先 warmup 1 帧，不计入）。

## 5. 下游观察（不改 evidence/classifier）
对重点帧（§3.1–3.4）把各 variant 的 component 以**只读方式**输入 production：
- per component 构造 `acc` → `cluster_features` → `classify_human`；
- per component 调 `evidence_postpass(componentPoints, [componentWithXYKeys])`（按株只传该 component 的点与
  其 XY key 集，避免 3D variant 中同 XY 键跨组件碰撞）→ `evidence_label` → `joint_status`；
统计 candidate / confirmed / SOLID_UNIFORM 拒绝 / “静态残留被 confirmed”（false confirmed residual）。
**POST_FILTER_ERROR 属另一问题，不允许为改善本轮结果修改 evidence/classifier。**

## 6. Golden invariants（D 至少满足）

**不允许**：① 完整站立人体被明显切成上下两段；② torso/leg 连续结构因 Z 分层被拆；
③ fragmentation 相比 A 灾难性增加（判据：`<3 voxel` 丢弃组件数 > A 的 1.5×，或丢点总数 > A 的 1.5×）；
④ runtime 数量级恶化（p95 > A 的 10×）；⑤ 用人工标签/classifier label 反向帮助 clustering。

**希望**：f55/f150/f155/f160 的 HUMAN+static 大面积错误 merge 下降且真人 retained-point ratio 保持高、
bbox 高度更合理；f10/f30 保持 `STATIC_RESIDUAL_ONLY` 身份（不得被解释为人体 connectivity 成功）。

## 7. 输出文件（不覆盖 00–07）

| 文件 | 内容 |
|---|---|
| `08_ab_plan.md` | 本计划 |
| `09_ab_shadow_impl.js` | A/B/C/D 实现 + A 复刻自检（可单跑） |
| `10_ab_synthetic_results.js` / `.json` / `.log` | synthetic A–H × 全 variant |
| `11_ab_real_frame_results.js` / `.json` / `.log` | 全 165 帧 + 重点帧全部指标 |
| `12_ab_debug_data.json` / `12_ab_debug_gen.js` / `12_ab_debug.html` | 同帧 A/B/C/D 并排 debug（component 着色、拆分区、contact、bbox、计数） |
| `13_ab_summary.md` | 最终回答（§8），只允许一个结论标签 |

## 8. 最终结论格式（`13_ab_summary.md` 必答）

1. XY4 是否被证实是 merge 放大因素？
2. XY8 是否恶化？
3. XYZ26 是否降低 vertical alias？
4. XYZ26 是否导致新的 over-split / over-connect？
5. constrained 3D（D*）是否优于 A/C？
6. 改善来自 connectivity，还是仍主要受 background residual 支配？
7. 是否已有足够证据进入 production change proposal？

最终标签仅允许：`NO_CHANGE` 或 `PROCEED_TO_PRODUCTION_PROPOSAL`。**即使 D 最好也不得改 production。**
收尾必须复核 `human_pipe_lib.js` SHA = `5bce92a4…142b4`；不一致 → 本轮实验无效。

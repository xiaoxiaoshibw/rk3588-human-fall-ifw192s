# 09 · R9 最终归因（定量数字见 `04_raw_support_results.json` / `05_builder_attribution.json` / `06_spatial_offset_analysis.json`）

- 日期：2026-10-06；writer：claude-k3；ponytail full。
- digest `ef6e1c2c191c6e30…`；复用等价门全 PASS；守恒全 PASS；确定性 5/5 digest 一致 PASS；控制区 sanity PASS。
- E-1（`2026-10-06_hrw03_r8_e1`）mobility hypothesis **保持关闭**；本轮只在同一冻结输入上把
  1035 个 NO_REF_VOXEL 的查询域向上游扩到 acquisition / builder / spatial 三层。
- 全文数字均在生产坐标系、冻结 ICP、既有 builder/matcher 下的 shadow-only 读数；**未改任何 production**。

## 1. 核心结论（一句话）

> **站点残块 55.2% 的 NO_REF_VOXEL 不是 reference 缺失——它在三层上都被 reference 完整观测并收录；
> 丢失发生在「5 cm 最近邻查询 vs 0.15/0.12 m 体素量化形心」的空间对应层。**

三条独立的、互相印证的证据：

| 证据 | 读数 | 含义 |
|---|---|---|
| **d_cell ≤ 0.05 m** | **1035 / 1035（100%）** | 每个残块点的 query cell（整数格）都在 reference 的 raw cell 集里——reference **整数格直接命中**观测到了它。 |
| **Focc(ε=0.36) == 1.0** | **1035 / 1035（100%）** | 这些位置在 reference 全部 **102** 帧里都被观测到（占用率 100%）。 |
| **d_raw ≤ 0.05 m** | **1016 / 1035（98.2%）** | 最近真实 ref raw 点几乎都在 **5 cm 以内**。 |

→ **A 类（NO_RAW_SUPPORT / cross-session coverage）= 0 / 1035**。这不是 acquisition 问题。

## 2. 逐点归因（taxonomy 见 `02_attribution_design.md` §3；先登记后跑）

### point-weighted（1035 点，分母=1035）

| 类 | 计数 | 比例 | 判读 |
|---|---:|---:|---|
| C0_NO_RAW_SUPPORT | **0** | 0% | acquisition 缺失 **零例** |
| C1_LOW_OCC_REJECT | 25 | 2.4% | 位置被观测、但占用率 < 0.5（**全部 occ<0.45，无一在 0.45–0.5 临阈带**） |
| C2_OTHER_NEAR_CANDIDATE | 904 | **87.3%** | 高占用 candidate（occ≥0.5）在 5 cm 外——其中 **904/904 occ≥0.5，902/904 d_cand∈(0.05,0.12]** |
| C3_OTHER_BUILDER_REJECT | 106 | 10.2% | 整数格直接命中高占用 cell（close_cell_occ≥0.5）但其**体素形心**量化到 5 cm 外的邻格 |
| C4_OFFSET_5_10CM | 0 | 0% | （以 raw 最近点计几乎不单独出现，全被 C2/C3 先吸收） |
| C5_OFFSET_10_30CM | 0 | 0% | 无 |
| C6_FAR_OR_NO_CORRESPONDENCE | 0 | 0% | 无任何「无对应」点（d_raw≤0.60 全覆盖） |
| C7_UNRESOLVED | 0 | 0% | 无不可归因点 |

**C2 + C3 = 1010 / 1035 = 97.6%** —— 全部属「reference 在 5–12 cm 内确有 occ≥0.5 的对应结构」，
即 **空间对应 / 体素量化层（SPATIAL_OFFSET）**，不是 acquisition、不是 builder admission。

### unique-current-voxel-weighted（去重后 n=40 体素，分母=40；防高密度点主导）

| 类 | 计数 | 比例 |
|---|---:|---:|
| C0 | 0 | 0% |
| C1_LOW_OCC_REJECT | 3 | 7.5% |
| **C2 + C3（spatial）** | 36+1 = **37** | **92.5%** |
| C4–C7 | 0 | 0% |

**point-weighted 与 voxel-weighted 一致**（spatial 97.6% vs 92.5%，均压倒性主导）——非高密度伪影。

## 3. 5 / 10 / 15 / 20 / 30 cm cumulative NN（`06_spatial_offset_analysis.json`；点级，n=1035）

| 查询域 | ≤5 | ≤10 | ≤15 | ≤20 | ≤30 |
|---|---:|---:|---:|---:|---:|
| **universe**（occ≥0.5 形心） | 0 | 989 | 1034 | 1035 | 1035 |
| **refCandidate**（全部 5286 形心） | 64 | 1015 | 1034 | 1035 | 1035 |
| **refRaw**（raw 点） | **1016** | 1035 | 1035 | 1035 | 1035 |

- universe 5 cm=0（E-1 定义）但 **10 cm 已恢复 989/1035（95.6%）**；
- refRaw **5 cm 即有 1016/1035（98.2%）**；
- 全量 **10 cm 内三域全部恢复 ≥95.6%**，20 cm 内 100%。

> **解读**：偏移几乎完全落在 **5–12 cm 一个体素格宽（0.15 m xy / 0.12 m z）量级**——
> 正是体素量化形心↔点位置的错位，而非结构在更远处。这是**空间对应层**的指纹，不是 acquisition、不是 builder。

## 4. 这些位置有没有被 reference 真正观测过？为什么没进最终 reference？

**观测过**——且是以最高持续度观测：d_cell≤0.05（整数格命中）100%、Focc=1.0（102/102 帧）100%。

**「没进最终 reference」是表述错觉**：它们对应的 reference **体素本身 occ≈1.0 ≥ 0.5 已收录进 universe（3707 内）**；
真正发生的是——reference 把同一片观测**量化进 0.15/0.12 m 体素，其形心落在残块点 5–12 cm 外的邻格**，
而 E-1 对该点的最近邻查询半径只有 **5 cm**，恰好小于体素格宽 → 抓不到本已入图的邻格。

→ **丢失层 = 空间对应（query 半径 < voxel 量级）**，不是 acquisition（C0=0）、不是 builder admission（C1 仅 2.4% 且全部 occ<0.45）。

## 5. 区域切片：站点 vs 控制区是否同一 failure mode？（`05_builder_attribution.json.controls`）

对全 f10/f30 前景残点、同一 `onlineMap/extract_foreground` 链、同样「universe 5 cm 无」筛出的各区域 NO_REF_VOXEL：

| 区域 | n | C0 | C1 | **C2+C3(spatial)** | C6 | 主 mode |
|---|---:|---:|---:|---:|---:|---|
| **STATION_BLOCK** | 1035 | 0% | 2.4% | **97.6%** | 0% | spatial 主导 |
| STATION_ZONE | 757 | 0% | 11.0% | **88.9%** | 0% | spatial 主导 |
| WD01 | 917 | 0% | 3.8% | **96.2%** | 0% | spatial 主导 |
| WD02 | 597 | 0% | 23.3% | **76.7%** | 0% | spatial 主导 |
| OTHER | 1540 | 2.2% | 25.6% | **71.8%** | 0.4% | spatial 主导 |

- **所有 region 同一 failure mode = 空间对应/量化（C2+C3 主导 71.8%–97.6%）**，无区域性 acquisition 缺失。
- C1（low-occ）比例随距离上升（站点 2.4% → WD02 23.3% → OTHER 25.6%）：远场点稀、占用率被分摊到邻格而 <0.5——
  但这是**次要的远场变体**，且全部 occ<0.45（不在临阈带），不改变主因判定。

## 6. 主要 contributor

预注册 verdict 规则对照（`02_attribution_design.md` §5）：

| 判据 | 实测 | 触发 |
|---|---|---|
| C2+C3(spatial) ≥ 50% 且其中 occ≥0.5 比例 ≥ 60% | **97.6%** 且 C2 中 occ≥0.5 = 904/904=100%、C3 close_cell_occ≥0.5=106/106=100% | **满足** |
| C0 ≥ 50% （coverage） | 0% | 不满足 |
| C1 ≥ 50% 且临阈带(0.45–0.5)占 C1≥40% （builder） | 2.4%，临阈带=0 | 不满足 |
| C7 ≥ 20% （inconclusive） | 0% | 不满足 |

### 最终判定：**REGISTRATION/SPATIAL-CONFIRMED（主要 contributor = registration / voxel 量化 / 空间对应层）**

理由：
1. **acquisition 排除**：C0=0，所有残块位置被 reference 以 occ≈1.0、102/102 帧观测；
2. **builder admission 基本排除**：C1 仅 2.4% 且**无一在 0.45–0.5 临阈带**；
3. **spatial/量化确证**：C2+C3=97.6%，universe 10 cm 恢复 95.6%、refRaw 5 cm 即恢复 98.2%，
   偏移落在单个体素格宽（0.15/0.12 m）量级；控制区与站点同一 mode。

## 7. 三个决策问题的回答（工单 §14 之 8/9/10）

**(8) 是否值得进入下一轮 `bg_ref_occ_min` 或其它 builder gate A/B？**
**不值得**。证据：站点 C1 仅 25/1035（2.4%），且其 close-cell occ 全部 <0.45（`04` 直方图 0–0.45 分布，0.45–0.5=0）——
即使把 `bg_ref_occ_min` 从 0.5 降到 0.45，也**一个 NO_REF_VOXEL 都救不回**（0 在临阈带）。
主因不在 occupancy 门。

**(9) 是否需要返回 registration 层？**
**部分返回/建议**：主因是**体素量化 + 查询空间容差**这一**空间对应**层（B/C 层家族，非 ICP 重估）。
残块点位置与对应 ref 结构偏移 5–12 cm，正是 matcher 需要容忍的量化/配平抖动量级。
下一步应指向 **matcher 空间容差 / 邻域查询**（用 production 已具的 3×3×3 邻域 + `bg_match_radius=0.12 m` 语义
去对齐 reference 查询侧），而**不是**降 builder 阈值、不是重估 ICP。

**(10) 是否需要任何 production change？**
**NO**（默认答案成立）。本轮为只读 shadow attribution；matcher/radius 的任何变更属下一轮、须另行立工单并 A/B。

## 8. 特别禁止的逻辑跳跃 —— 逐条核验

| 工单 §11 禁令 | 本轮证据 | 是否成立 |
|---|---|---|
| 「所以 bg_ref_occ_min=0.5 太高」 | C1 全 <0.45，0.45–0.5=0；降阈救回 0 点 | **明确否定**——无证据支持 |
| 「NO_REF_VOXEL 就代表 reference coverage 不足」 | C0=0；d_cell≤0.05 100% | **明确否定**——本轮正是为区分此而设 |
| 「扩大 matcher radius 就能解决」 | 偏移 5–12 cm 在 matcher 0.12 m 语义内，但**本轮不改 matcher**，是否属允许 registration error 须下一轮判定 | 不下「就能解决」结论，只登记为 spatial |
| 重开 temporal mobility filter | 无与 E-1 冲突的新证据；mobility 保关闭 | **未重开** |

## 9. 工程证据

- **Determinism**：同输入连跑 5 次，digest 全部 = `ef6e1c2c191c6e30…`（`> /tmp/r9_run_*` 5 次 + 4 次补跑，全等；
  `generated_utc` 不入 digest，全文 md5 差异仅时间戳）。
- **Conservation**：point Σ(C0..C7)=1035 ✓；unique-voxel Σ=40 ✓；obs Σ=1035 ✓；控制区各 region 自洽 ✓。
- **复用等价门（非新实验）**：ref voxels=5286 ✓、universe=3707 ✓、online map=1720 ✓、
  站点残块标签序列 digest 与 E-1 完全相等（`3b5f8aded7c368a2`）✓、
  `occ` 由原始整数位图重算 == `build_reference_map.obs` 逐键 0 mismatch ✓、
  ref raw 点 100% 落进 rawCell（in WS=3,131,751，outside=0）✓。

# 02 · R9 Attribution 设计（PREREGISTERED —— 跑任何结果前锁定）

规则与判据**先于**实验登记；跑完后只允许报告数字，**禁止**回头修改本文件迎合结论（工单 §7）。
日期：2026-10-06；writer：claude-k3。

---

## 1. Attribution chain（本轮真正新增的查询层）

对 E-1 每个 NO_REF_VOXEL 点（current lev 系残点 p）：

```
p (current lev)
  │  q = R_icpᵀ·(p − t_icp)          ← 冻结逆变换，投到 reference lev 系（E-1 同式）
  ▼
q (ref lev)
  ├─(L0) universe（occ≥0.5, 3707）5 cm NN        【E-1 已答：无 → 本轮起点】
  ├─(L1) ref 全 candidate（5286）NN → d_cand    【新】区分「builder 拒」vs「candidate 都懒生」
  ├─(L2) ref 全 k×3×3×3 raw cell NN → d_cell
  │        （当帧 ≥1 点即 key 入 cell 集，与 hit_min=1 observed 门同口径）【新】observed 存在性
  └─(L3) ref 逐帧 raw 点云 NN（多档半径）→ d_raw / 支持帧数 F(ε) / Focc【新】观测时间维度
```

**查询域，全部只读、不改任何输出**：
- **universe** = `PL.reference_static_keys(PL.build_reference_map(REF_DENOISED), 0.5)`，3707 键（E-1 同口径）。
- **refCandidate** = `build_reference_map(...).voxels` 全部 **5286** 键（不筛 occ）。
- **rawCell** = ref 逐帧 denoised 云的工作空间后 ≥1 点体素键全集（∪102 帧；hit_min=1 时等于 candidate 键集）。
- **refFramePts(ε)** = ref 每帧**映射前整数位图** `S_f(ε) = { cell c : 帧 f 在 c 的 ε 3×3×3 邻域内 ≥1 raw 点 }`，
  ε ∈ {0.05, 0.12, 0.36}；由此派生支持帧数、Focc。

---

## 2. 需要先只读回答的 production builder 12 问（工单 §3.2；已对当前 code 作答）

| # | 问题 | production code 事实（`human_pipe_lib.js`） |
|---|---|---|
| 1 | reference candidate 哪里产生 | `build_reference_map(REF_DENOISED)` 的 stats Map（任何 ≥1 点的 key 都进入） |
| 2 | raw frame 怎么 voxelize | `key_bg = _bg_key_ijk(floor(x/0.15), floor(y/0.15), floor(z/0.12))`（整数格） |
| 3 | voxel size | xy=0.15 m，z=0.12 m（`PIPE.bg_voxel_xy / bg_voxel_z`） |
| 4 | 每帧 presence 怎么定义 | 工作空间裁剪后该 key 当帧点数 ≥ `bg_ref_hit_min_pts`(=1) → 记 1 次 obs |
| 5 | occupancy 分母 | 参考帧总数 N=**102**（空场，无遮挡剔除）；occ=obs/102 |
| 6 | hits 怎么统计 | obs=满足 observed 门的帧数；pts_total=累计点数（诊断） |
| 7 | admission threshold | **唯一 admitted 门** = `reference_static_keys` 的 occ ≥ `bg_ref_occ_min`(=0.5)，即 obs≥51/102（51/102=0.5 恰入图） |
| 8 | tier/gate | **reference builder 无 tier**（tier 只存在于在线 `build_static_map`） |
| 9 | neighborhood gate | **无**（在线 supported 才有 26 邻域 strong≥2） |
| 10 | jitter/stability gate | **无** reference jitter 门（jit 字段仅诊断输出，不参与 admission） |
| 11 | z/range/filter | 工作空间 z∈[0.10,2.50]；前置 denoise 距离窗 [0.35,25.0] m |
| 12 | 最终 voxel 为什么 accept/reject | accept=occ≥0.5；reject 只可能 = occ<0.5（occ 层）或 z 裁剪/距离窗外（raw 层）或量化邻格偏移（SPATIAL） |

> **含义**：本数据集下「raw present 且 occ≥0.5 但被其它 reference builder gate 拒」**结构上不存在**。
> 若某点 d_cand≤ε 且 occ≥0.5，唯一可能是整数格量化把 candidate 推到邻格（→ SPATIAL_OFFSET），
> 不是 builder gate。

---

## 3. 冻结 taxonomy（C0..C7 按工单 §7，落到可操作判别式）

优先级自上而下**互斥**，命中即止：

| 类 | 定义（ε=0.36 m 测度） |
|---|---|
| **C0_NO_RAW_SUPPORT** | `Focc ε=0.36 = 0` ：最近 raw 帧占有率（min-dist 所在帧 i 起，≥1 raw 点落 i 的 ε 邻域的帧占比）为 0。reference acquisition 层从未（或几乎从未）观测到该位置。 |
| **C1_LOW_OCC_REJECT** | `d_cell ≤ ε`（被 observed 过）**且** best-candidate `occ < 0.5`。raw 有观测、builder 也收录 candidate，但占用率不达 0.5 入图门。 |
| **C2_OTHER_NEAR_CANDIDATE** | `d_cand ≤ ε` 且 best `occ ≥ 0.5` 且 `d_cand > 0.05`（universe 5 cm 无但 5–36 cm 有高占用 candidate）。结构上属量化/邻格偏移（production 无其它 reference gate），不是新 gate。 |
| **C3_OTHER_BUILDER_REJECT** | `d_cell ≤ ε` 且 best `occ ≥ 0.5`——**预期为 0**；若 ≠0，说明存在未被 code 审计覆盖的真实 reference gate（立即单独登记冲突，工单 §15）。 |
| **C4_OFFSET_5_10CM** | raw 确被观测（非 C0/C1/C2/C3）且 `d_raw ∈ (0.05, 0.10]` |
| **C5_OFFSET_10_30CM** | 同上，`d_raw ∈ (0.10, 0.30]` |
| **C6_FAR_OR_NO_CORRESPONDENCE** | 同上，`d_raw > 0.30` |
| **C7_UNRESOLVED** | 其余全部（不强制归因） |

> C2–C6 都是「reference 确有对应观测/记录，但 E-1 的 5 cm 查询找不到」的不同距离档位——
> 在 verdict 归约时按 §5-primary 规则决定归入 spatial 还是 builder。

守恒（必须）：`C0+C1+C2+C3+C4+C5+C6+C7 = 1035`（point 级）；unique current-voxel 另做独立守恒。

### 标签 stability guard（防 ε 边界伪态）

- C0 另报 ε=0.12 的敏感口径；若某点 `Focc(0.36)=0 但 Focc(0.12)=0` 仍 C0，
  若 `Focc(0.36)=0 但 d_raw≤0.12`（不可能，自洽）——guard 只用于报告 C0 对 ε 的敏感度，不改主标签。
- C1 LOW_OCC 另报 `0.45≤occ<0.5` 子带（threshold-near 计数），供 §6(8) 判断是否值得下一轮 `bg_ref_occ_min` A/B。

---

## 4. SPATIAL_OFFSET cumulative NN（工单 §8；universe / refCandidate / refRaw 三套）

分档：≤5 / ≤10 / ≤15 / ≤20 / ≤30 / >30 cm（任一查询域无对应记 >30/na）。

每套同时报告三种权重（分母各自登记）：
- **point-weighted**：1035 点逐点；
- **unique-current-voxel-weighted**：1035 点按「current 前景 3D key」去重后逐 voxel（防高密度区重复点主导）；
- **observation-weighted**：unique current-voxel × 该 current voxel 的前景残点数（分母=总 obs，说明其语义=残点观测计数加权）。

---

## 5. 预注册 verdict 规则（工单 §10；先写死）

对 1035，令各类比例 = count/1035（point-weighted 主口径；voxel-weighted 并列报告）。

| verdict | 触发 |
|---|---|
| **COVERAGE-LIMITED** | `C0 ≥ 50%` 且 spatial(C4+C5) < 30% → 主因 = cross-session raw coverage；**不应**降 builder threshold 修 |
| **BUILDER-ADMISSION-CONFIRMED** | `C1 ≥ 50%` 且 C1 中 `0.45≤occ<0.5` 子带占 C1 ≥ 40% → raw 有、位置对齐、系统性被 occupancy 门拒；可入下一轮 builder 参数 A/B（仍不直接改 production） |
| **REGISTRATION/SPATIAL-CONFIRMED** | `(C2+C4+C5) ≥ 50%` 且这些点 best-candidate occ≥0.5 的比例 ≥ 60% → 主因 = registration/量化/空间容差；返回 B/C 层，不碰 builder threshold |
| **MIXED** | 无单一类 ≥50% 且无其它规则触发 → `MIXED CONTRIBUTOR` 报告比例，不硬选主因 |
| **INCONCLUSIVE** | `C7 ≥ 20%`，或 raw temporal evidence 不足以区分以上（例如 C0 对 ε 极敏感且无稳定带）→ `INCONCLUSIVE`，禁止直觉归因 |

`✶` 多条满足时按 **COVERAGE > SPATIAL > BUILDER** 的层序报 primary，同时在 `09` 里列全部满足的类与比例（即 primary + mixed 成分）。

---

## 6. 最终必须回答（工单 §14；在 `09_final_attribution.md` 逐项给数字）

1. 1035 中 C0/C1/C2/C3/SPATIAL_OFFSET(C4+C5)/C6/C7 各多少；2) point-weighted vs voxel-weighted；
3) 5/10/15/20/30 cm cumulative NN 分布（三套查询域 × 三种权重）；4) ref 原始帧真正观测过多少残块位置；
5) 观测过的为什么没进最终 reference；6) station vs WD01/WD02 是否同一 failure mode（区域切片对照）；
7) primary contributor = raw coverage / builder admission / registration-spatial / mixed / inconclusive；
8) 是否值得下一轮 `bg_ref_occ_min` 或其它 builder gate A/B；9) 是否需返回 registration 层；10) 是否需任何 production change——**默认 NO**。

## 7. 工程证据（工单 §12/§13）

- **Determinism**：同输入连跑 ≥5 次 + 最终 20 次，digest 一致（digest 不含时间戳/绝对路径/耗时）。
- **Conservation**：point 级 Σ=1035；unique-voxel 级独立守恒；区域切片每行自洽。
- **复用等价门（重复用 E-1 产物，非新实验）**：ref voxels=5286、universe=3707、online map=1720、
  站点残块点标签分布=0/0/840/1035，且站点残块点集与 E-1 digest 复比对。
- 区域切片：STATION_BLOCK（本点集实际全部落此）/ STATION_ZONE / WD01 / WD02 / OTHER，
  用同一冻结窗口判定，报「若该窗口存在 NO_REF_VOXEL 其类别分布」，站点 vs 控制区 failure mode 对照。

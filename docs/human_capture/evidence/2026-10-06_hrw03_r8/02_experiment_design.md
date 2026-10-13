# 02 · W03-R3.6 实验设计（Registration Causality / Shared-Frame Validation）

- 日期：2026-10-06；writer：OpenCode（DeepSeek v4.1 Flash）；ponytail full。
- 目标：回答唯一核心问题 —— **若 reference 与 current 被放到足够准确的共享坐标系中，WD02 当前由 registration 导致的静态 residual 是否会系统性下降？** 即验证 R3.5 "Registration attribution" 的**因果性**，并给出 registration 修复的理论上限。
- 本文件先于主工具实现冻结；运行后除结论外不改口径。

## 1. 假设与可证伪预测

- H1（因果）：WD02 的静态 residual 主要由跨会话 registration 误差造成 → 精确共享坐标系（B/C）应使 WD02 residual 系统性下降，且下降点的空间分布与原 registration failure 区域重合。
- 预测 P1：A→B、A→C 的 WD02 residual 相对下降 ≥ 50%。
- 预测 P2：R3.5 定义的 Registration bucket（= B 相对 A 的恢复）在 B 后大部分消解（B 覆盖 A 的 registration gap ≥ 80%）。
- 预测 P3：改善不应伴随 matcher geometry bucket 增长（matcher 冻结）或 missing 爆炸。
- 预测 P4：人体带 / clean controls 的误吸收无显著增加（见 §6）。
- 反预测（若成立则 H1 降级）：高置信对齐后 WD02 residual 基本不变；或 residual 转移为 geometry/missing；或改善主要来自人体/可移动物吸收。

## 2. 三个条件（唯一变量 = registration transform；方向统一 current→reference）

| 条件 | 名称 | transform（映射 current 点 → reference 帧） | 来源 |
|---|---|---|---|
| **A** | Production / Current | `p_ref = p_cur`（无跨会话变换） | production 现状：每会话仅各自 TLS leveling，**无任何跨会话 registration**（见 `01_registration_chain_audit.md` Q3/Q6）。reference 融合假设下 = R3.5 的 `none` |
| **B** | Current ICP corrected | `p_ref = R_icpᵀ (p_cur − t_icp)` | R3.2/R3.3/R3.5 固定解：`roll 1.7476° / pitch −0.2818° / yaw −2.3924° / t [0.0182, 0.031, 0.0012] m`（ref→cur；source=ref occ≥0.9 形心，target=cur strong 形心，inlier 0.25，50 iters 收敛）——**不重调参**，工具内 CHECK 复现 |
| **C** | Static-structure oracle-like | `p_ref = R_C p_cur + t_C` | 本轮新建：point-to-plane ICP 于**两会话高置信静态结构**（§4）。标注为 **oracle-like / upper-bound estimate / offline high-confidence alignment，不是 GT** |

辅助行（不参与 A/B/C 判定，供与 R3.5 连续对照）：

| 辅助 | `tls` | `p_ref = R_directᵀ p_cur`，`R_direct = R_cur·R_refᵀ`（r7 同款，无平移） | 仅旋转的 leveling 直接差 |
|---|---|---|---|
| 敏感性 | `C_alt` | point-to-plane 的第二个收敛盆地（tls 初值；§4.4） | 若 C_primary 与 C_alt 结论翻转 → 降级判定 |

### 2.1 为何 A = none（而不是 tls-direct）

- production 只做每会话自 leveling，reference 静态图未接线；"当前生产 registration"在 cross-session 意义上**就是不对齐**（r6 §1.1 / R3.2 均已证明两会话 leveled 帧不同源）。
- R3.5 的 `Registration` bucket 定义即 `icp 命中且 none 未命中` → none 是它的现状基线；R3.6 用 A=none 才能让 `gain = residual_A − residual_X` 与 R3.5 的 60.8% 直接对应。
- `tls`（旋转直逆）不是生产行为（它是 R3.2 的 shadow 构造），且 R3.5 实测其在 WD02 上弱于 none（27.2% < 34.2%）。

## 3. 变量控制（A/B/C 之外全部冻结，与 R3.5 逐字一致）

- 输入：`cap_20261002_223757`（165 帧，current）+ `cap_20261004_203349`（102 帧，reference），SHA 见 `00_provenance.md`。
- 加载口径：各自最新 `recommended=="tls"` job → `apply_Rt` 一次 → `PL.denoise`（0.35–25 m、有限点）。
- 在线 map：`PL.build_static_map(cur, {drop_ground:true})`（hit≥2、strong 0.85、supported 0.65/jitter 0.05/26nb≥2）。
- reference map：`PL.build_reference_map(ref)`（hit_min=1），探针用 `occ≥0.5`（`bg_ref_occ_min`）。
- matcher：3×3×3 邻域、点到形心距离 `< 0.12 m`（`bg_match_radius`）、z∈[0.10,2.50]、voxel XY 0.15 / Z 0.12 —— **全冻结，不因 registration 条件变化**。
- Residual 宇宙 = production 语义下的 online residual（`shadowExtract(clean, onlineMap)` = `PL.extract_foreground` 逐点等价），**不随条件改变**；条件只改变 reference 探针的 transform。
- 分组/窗口/帧集：WD01（(3.50,−0.76) r≤0.9）、WD02（range>8 或 3 代表盘 r≤1.5）、PROBLEM/CLEAN/NEAR_FURN 帧集、FOCAL_FRAMES、proxy corroboration 帧 {63,80,92,123} —— 与 r7 逐字相同（不重调窗口追结果）。
- attribution 逻辑：沿用 r7 taxonomy（§5.1），仅把融合模式从 `icp` 推广到 X ∈ {A,B,C}。

## 4. 条件 C 的构造（冻结）

### 4.1 原则

- 只使用**明确静态结构**：单会话内时间一致性筛选（current = online strong tier；reference = occ≥0.9），不使用人体点，不挑选对象，不使用 matcher 输出，不使用 WD01/WD02 residual 指标。
- 不依赖 B（初值 = 单位阵），但工具中同时报告从 B/ tls 初值收敛的对照（仅 QA，不改 C 主解）。
- 确定性：哈希索引 + 稳定排序 + 定点迭代，node 同版本下逐位可复现。

### 4.2 输入与法向

- `curFine`：current 全部帧中、落在 online **strong** 体素内的点 → 0.06 m 格重分箱形心（≈11,959 个）。
- `refFine`：reference 全部帧中、落在 reference **occ≥0.9** 体素内的点 → 0.06 m 格重分箱形心（≈17,053 个）。
- target 法向：对 refFine 在 0.10 m 邻域内 PCA 最小特征向量（≈15,537/17,053 有有效法向）。

### 4.3 迭代（point-to-plane ICP，current→reference）

- 目标：最小化 `n_q · (R p + t − q)` 的 trimmed 中位（健壮裁剪），
- 尺度序列（inlier 门 m / 保留比例 / 迭代上限 / 源步长）：`0.30/0.70/25/5 → 0.20/0.60/25/3 → 0.15/0.50/25/2 → 0.10/0.50/25/1 → 0.08/0.60/25/1`；
- 小角度增量闭式解（6×6 正规方程 + 部分主元高斯消元），`R ← Rn·R`、`t ← Rn·t + dt`；
- 停止：`rotDeg < 5e-5°` 且 `|dt| < 5e-5 m`（或 pairs<30 / 奇异）。
- 主解 C = identity 初值收敛结果；`C_alt` = tls 初值收敛结果（近并列盆地）。

### 4.4 预研结论（`_recon_c2_probe.log`，决定上面冻结参数）

- identity 初值与 B 初值收敛到**同一解**：`euler ZYX (roll −2.3102°, pitch 0.0813°, yaw 2.2269°)，t [−0.0064, −0.0288, −0.0099] m`；
- 数据对半（even）拟合仍收敛到同一盆地（pitch 0.085°），而 tls 初值盆地在 even 拆分下漂移（pitch 0.593°→0.712°）→ 主解取 identity 盆地，tls 盆地登记为 `C_alt` 敏感性变体；
- normal-residual |r|（全部 static fine 点，p50）：none 38.8 mm → tls 29.9 mm → **B 14.5 mm → C 11.0 mm**；p90：119.7 / 98.5 / 57.4 / 56.6 mm；
- held-out（even 拟合 → odd 评估）：C p50 11.1–11.9 mm，与拟合集同量级（不过拟合）；C_alt fit-even→odd p50 11.9 mm（并列但不稳定）；
- **known limitation（如实登记）**：roll↔yaw/pitch 弱可观测导致第二盆地与主解目标值仅差 ~7%（中位），故 C 不是唯一全局最优；C_alt 与 B 一并作为敏感性列报告。R3.6 的因果判定必须对 C 与 C_alt 同时成立（§6.5）。

### 4.5 验证（registration QA，工具内输出）

1. B 复跑 CHECK（对存值逐位）。
2. C 从 identity 与 B 初值收敛一致性 CHECK；C_alt 存在性登记。
3. normal-residual 分位（none/tls/B/C/C_alt）；even/odd held-out。
4. 变换矩阵/欧拉/平移全量入 JSON（可复算）。

## 5. 指标与输出定义

### 5.1 归因分类（与 r7 taxonomy 相同，把融合模式 X 从 {none,tls,icp} 推广到 {A,B,C(,C_alt,tls)}）

对每个 online residual 点，在条件 X 下：
- `mX` = reference map（occ≥0.5）在 X 变换后 ±1 邻域内有 `d < 0.12` 的体素（吸收）。
- 标签：`MATCHED_REF_X`；否则若 ±1 邻域有 tier 体素但 `d ≥ 0.12` → `XY_MATCH_Z_FAIL` / `Z_MATCH_XY_FAIL` / `DISTANCE_OVER_GATE`；否则若有 `occ<0.5` 记录 → `REFERENCE_HOLE`；否则若 online stats 有 hits≥1 → `TIER_REJECT`；否则 `NO_REFERENCE_NEIGHBOR`。
- bucket：`MATCHED` → `REFERENCE_ABSORB`（若同时 mA）或 `REGISTRATION_X`（若 !mA，即 X 相对生产现状才恢复）；geometry 三类 → `MATCHER_GEOMETRY`；`REFERENCE_HOLE`/`NO_REFERENCE_NEIGHBOR` → `REFERENCE_MISSING`；`TIER_REJECT` → `SPARSE_GATE`（邻域 occ(≥1) max ≥0.65）或 `REFERENCE_MISSING`。
- 在该定义下，**X=B 即 R3.5 的 icp 归因**（用于 baseline 复现门），X=A 时 `REGISTRATION_A` 恒为 0。

### 5.2 每条件主指标（点级 + voxel 级分开）

- `absorb_X` = Σ mX；`residual_X` = residual 点总数 − absorb_X；`residual_ratio_X = residual_X / residual_online`。
- Voxel 级：residual 点按帧内 3D 体素（0.15/0.12）聚合，取主导 bucket，按组输出 share。
- **gain**：`gain_AB = residual_A − residual_B`、`gain_AC = residual_A − residual_C`（绝对值点数、pp、相对 %）。
- **static recovery**（明确静态 proxy）：
  - WD01：`recovered = absorb_X ∩ WD01`；`remaining = residual_X ∩ WD01`；`rate = absorb_X/WD01_online_residual`；
  - WD02 同式；另报 `recovered_by_registration = mX && !mA`。
  - 注：WD01/WD02 均为 proxy（WD02 = 远场 proxy；f10/f30 站点块已被 R3.5 判为可移动状态，**不计入 static recovery**；STATIC_STATION 代理仅单独报告）。
- **bucket transition matrix**（每点跨 A→B→C 的逐点状态，非总量）：
  - 状态词汇（每条件各算一次）：`ABSORB_X = mX`；`REG_GAP_X = !mX && mC`（相对 oracle 仍可被 registration 修复）；其余按 X 探针分 `GEOM` / `MISSING` / `SPARSE`（同上 taxonomy）。
  - 输出 A→B、B→C、A→C 的 5×5 转移计数/份额；等价地观察 `Reg_Gap_A → Absorb_B`（B 消解）与 `→ Reg_Gap_B`（C 仍需要）。
- **human safety**：
  - NEAR_FURN 窗口（(1.45,0.85) r≤0.6）的 f55/150/155/160：分带 `z≥1.2`、`0.8–1.2`、`0.3–0.8` 的 absorb_X 计数/率与 delta（B−A、C−B、C−A）；
  - clean controls（63/65/80/85/90/92/95/99/123/146）人窗口（r7 probe 同款最大簇 r≤0.6）；
  - proxy 分类（corrob≥2 STATIC_STATION / =1 AMBIG / =0 NON_STATIC）在 PROXY_FRAMES 的 absorb_X 计数；NON_STATIC 吸收增量是主要风险指标。
  - f10/f30/f55/150/155/160 的 proxy 吸收只作安全对照，不作收益口径（R3.5 §2 裁决）。
- **registration error shell**（CSV，focal 帧）：每 residual 点输出 current xyz、A/B/C/C_alt 最近 ref 体素距离 d、C 最近 ref xyz、`delta_AC = d_A − d_C`、标签/bucket/状态、proxy 分类、frame —— 供画 A/B/C 校正向量场。

### 5.3 Baseline 复现门（硬性）

- 工具读 r7 `02_attribution_results.json`，比较 6 组（ALL/WD01/WD02/PROBLEM/CLEAN/NEAR_FURN）的 R3.5-icp 口径 `bucket_counts`、`reason_counts`、`matched_ref` 与全量 `conservation.totals`，要求**逐整数相等**；不一致即 STOP（查 provenance）。
- 另复现 r7 的全部 checks：G0 逐点等价、守恒、micro-cases、在线 map 复刻、ICP 存值、5286/3707/2063、R3.3 A 层 0.7796、probe 群（f10/f55/f160 = 1564/1365、3190/621、2429/1024）。

## 6. 因果判据（预注册，运行后不改）

主判定基于 **WD02**（最大 registration failure proxy），并要求 C 与 C_alt 同时成立：

### 6.1 SUPPORTED（全部满足）

- S1 **WD02 residual 明显下降**：`residual_B ≤ 0.5 × residual_A` 且 `residual_C ≤ 0.5 × residual_A`（两个 independent 精确对齐各消掉 ≥50%）。
- S2 **Registration bucket 大幅下降**：`REG_GAP_A`（absorb_C && !absorb_A）中 ≥80% 被 B 吸收（`absorb_B` 覆盖）；即 R3.5 的 registration 主体确实随 transform 修正消解。
- S3 **Matcher geometry 不需要改变**：WD02 `MATCHER_GEOMETRY` 计数 `C ≤ A`（C 下没有向 geometry 转移的增长）。
- S4 **Reference missing 不爆炸**：WD02 `REFERENCE_MISSING` 计数 `C ≤ A × 1.1`。
- S5 **clean control 无退化**：clean 帧人窗口吸收率 C ≤ 1% 且 `(C − B) ≤ +0.5 pp`。
- S6 **人体吸收无显著增加**：f55/155/160 人体高带（z≥1.2）吸收率 `(C − B) ≤ +1.0 pp`；PROXY_FRAMES 的 `NON_STATIC` 吸收计数 `(C − B) ≤ +1.0 pp` 于窗口点数。
- S7 **空间吻合**（描述性，不设硬门）：`absorb_B/C && !absorb_A` 点的 range/azimuth 分布与原 registration failure（A 下 d∈[0.12,0.24) shell + d≥0.12 的远场分布）一致；若明显不一致则降级。

### 6.2 PARTIALLY SUPPORTED

- WD02 有改善（S1 的 A→B 部分成立）但：S4/S7 失败，或 C-residual 中 reference/background/non-static 占比仍大 → "registration 是重要因素，但不是唯一主因"。

### 6.3 REJECTED

- `residual_C > 0.5 × residual_A`（高置信对齐后 WD02 仍基本不变）；或改善转移为 geometry/missing（S3/S4 失败）；或改善主要来自人体/可移动物误吸收（S6 失败）。

### 6.4 INCONCLUSIVE

- baseline 复现失败、C 构造不唯一且 C_primary/C_alt 结论翻转、或输入/变换来源不明（§8 stop 条件触发）→ 不下结论。

### 6.5 敏感性要求

- 所有 §6.1 判定必须对 **C_primary 与 C_alt 同时成立**；若两者对 S1/S6 的结论相反 → 至少降为 PARTIALLY SUPPORTED 并明确登记。
- 辅助 `tls` 行仅描述，不参与判定。

## 7. 确定性与守恒

- 两次完整独立运行（run1 → 本目录；run2 → 临时目录）：规范化 digest 一致；`04_point_attribution.csv` / `04b_voxel_transitions.csv` byte-identical。
- 运行前后 11 个输入 SHA（3 JS + 2 会话 ×2 + 2 transform.json + 2 report.json）一致；production 文件 mtime 不变（13:15:11Z）。
- 守恒：`N_DENOISE = N_Z_REJECT + N_BG_MATCH + N_RESIDUAL`（逐帧）；标签分区 = residual；self-check（residual 不得命中 online map）= 0。

## 8. 停止条件（工单 §十五 → 本实验对照）

| 条件 | 本实验状态 |
|---|---|
| production baseline 无法复现 | 硬门 §5.3；失败即 STOP |
| transform direction 不明确 | 已审计（01 Q7/Q12），方向 current→ref 统一 |
| reference source 不明确 | 203349 + R3.1 builder，SHA 固定 |
| ICP 参数来源不明确 | R3.2 固定解 + r5/r7 CHECK 复现；不重调 |
| C 必须靠猜参数 | C 参数在 §4 冻结并有预研/held-out 证据；两盆地均报告 |
| input 被外部程序修改 | 工具内 11 输入 SHA 前后断言 |
| production SHA 改变 | 工具内断言 + 结束后复核 |
| A/B/C 出现其他变量变化 | §3 全量冻结；工具按 R3.5 同源实现 |
| 无法区分 STATIC/NON_STATIC 却要下结论 | proxy 一律标注非 GT；收益口径只用 WD01/WD02；站点块不计入 |

## 9. 产物

`03_results.json`（含 digest/QA/checks/组级 A/B/C 全指标/转移矩阵/human safety/逐帧）、`04_point_attribution.csv`（focal 帧逐点 A/B/C 链路 + shell）、`04b_voxel_transitions.csv`（全帧逐体素各条件主导 bucket 与转移）、`05_frame_analysis.md`、`06_summary.md`、`10_r36_registration.js`、运行日志。

**Production modified? NO。**

# 03 · Registration Confidence Gate 设计（R3.7 冻结）

- 日期：2026-10-07；writer：OpenCode（DeepSeek v4.1 Flash）；ponytail full。
- 目标：回答「什么样的跨会话 transform 才允许被使用」。原则（用户 2026-10-07 指令的工程化）：
  **fail-closed；不静默使用任何可疑 transform；度量在 artifact 创建时算一次、判定可复现；阈值有出处，不拍脑袋。**
- 本文件的全部数值构成 **`reg_gate_v1`** 常量集。它们是**预注册**的：R3.8 先用本表创建/判定，测量结果出来后**不允许回改本表**；需要变更 → 新 profile id（`reg_gate_v2`）+ 记录依据 + 重新判定（且若变更翻转结论，必须用户授权）。

> **复审修订 R1（2026-10-07，独立复审后；writer：OpenCode/DeepSeek v4.1 Flash）**：① §3.2 `|t|`、`|t_z|` 两行按“TLS-direct 平移计入观察集”（`t_c2r = t_ref − R_c2r·t_cur`）全量重导：`|t|` 0.0365→**0.0867 m**（limit 0.10→**0.20 m**）、`|t_z|` 0.0099→**0.0577 m**（limit 0.05→**0.15 m**）；其余表值按全量口径复核不变。② roll 行来源 pair 对名修正：202456→203135 → **203135→203349**（2.6799°；202456 方向实为 2.6717°，数值 2.68° 不变）。复算协议与逐值见 [returns/HR-W03.md](../../returns/HR-W03.md)「R3.7 复审修订 R1」。

## 1. 判定发生的两个位置

| 位置 | 做什么 | 不做什么 |
|---|---|---|
| **创建时（offline，R3.8）** | 计算全部指标、按 `reg_gate_v1` 判定、把**指标 + 阈值快照 + 判定**写入 `diagnostics.json` | 不修改 transform 去"凑"通过；不因判定结果重跑调参 |
| **载入时（每次使用）** | ①完整性/SHA/矩阵校验（02 §5）；②按快照**复算 band**（确定性、纯查表）；③输出状态机的状态 | 不重算指标（除非显式 recheck 模式，R3.8 工具） |

## 2. 指标族（与工单 A–D 对应）

### A. 支撑量（防"所有对应点挤在一面墙"）

| 指标 | 定义 | R3.6 协议锚点 |
|---|---|---|
| `n_static_source` | 源侧细静态点集点数（curFine：源在线 strong 体素内点，0.06 m 重分箱） | 11,959 |
| `n_static_target` | 目标侧细静态点集点数（refFine：ref occ≥0.9 体素内点，0.06 m 重分箱） | 17,053（法向有效 15,537） |
| `n_correspondence` | 最终接受迭代的 trimmed 内点对数量 | 未存档（R3.8 实测） |
| `inlier_ratio` | `n_correspondence / n_static_source` | 未存档（R3.8 实测） |
| `coverage_xy` | 有对应点的源侧 XY 0.15 m 网格数 / 源侧全部网格数 | 未存档（R3.8 实测） |
| `azimuth_sectors` | 源侧点按 atan2(y,x) 分 8 扇区（每 45°）的对应点计数 | 未存档（R3.8 实测） |
| `max_sector_share` | `max(azimuth_sectors) / n_correspondence` | 未存档（R3.8 实测） |

### B. 几何条件（roll↔yaw/pitch 弱可观测的正面处理）

| 指标 | 定义 |
|---|---|
| `jtj_eigvals` | 最终解处 point-to-plane 线性化 `JᵀJ`（6×6；δ=[rotation(3), translation(3)]，行向量 `[(p×n)ᵀ, nᵀ]`）的 6 个特征值，降序 |
| `eig_ratio` / `condition_number` | `λmin/λmax` / `λmax/λmin` |
| `basins` | 多初值解：`{identity, tls}` 至少两个非法退化初值分别收敛；含半集重拟合（even/odd）自一致性 |
| `competing_basins` | `Δrot > 0.02°` 或 `|Δt| > 0.01 m` 判定"收敛到不同盆地"（求解确定性：同盆地重跑差 ≪ 该门；实测不同盆地差 0.51°–2.31°） |
| `basin_resolution` | 存在竞争盆地时的消解证据（见 §4.2） |
| `direction_check` | 方向自检（防 writer 方向 bug，见 04 §4.4）：对同一对应集评估前向 `\|n·(Rp+t−q)\|` 与反向（逆用）残差；v1 规则 = `fit_p50(前向) ≤ fit_p50(反向)`，失败 → `reject(DIRECTION)` |

### C. Holdout 质量（防过拟合）

- 协议（`protocol.id = r3.6_fine_static_v1`，逐字沿用 R3.6 §4.2–4.3）：
  - fit：全部细静态点的 point-to-plane 残差 `|n·(R p + t − q)|`（最近邻 ≤0.30 m 内）；
  - holdout：源点集偶/奇对半 → 一半重拟合 → 在另一半上评估（两个方向都算）；
  - 记录 `fit.{n,p50,p90}`、`holdout.{n,p50,p90}`、`holdout_fit_ratio_p50 = holdout.p50 / fit.p50`。
- 铁律：**fit 过门而 holdout 不过门 → 直接 REJECT**（不是 WARN）。

### D. Transform 合理性（sanity bounds，历史分布推导）

见 §3.2。违界 → REJECT（sanity 无 warn 档）。

## 3. 阈值推导（数据与公式）

### 3.1 推导数据集（全部只读、来自既有 artifact）

- **D1**（audited pair `223757→203349` 解法族，canonical cur→ref）：TLS-direct、B、C、C_ALT 的 euler/平移（01 §3.2；TLS-direct 由两会话 tls transform 直算：`Rpy (−2.5818, 0.5258, −0.0271)`，θ=2.635°）。
- **D2**（同场候选会话两两 TLS-direct，provisional；场景身份依据 GL-V01 三会话 `203349/203135/202456` 的既有同批验证记录 + W03 的 `223757`，**本轮未再证明场景身份**）：
  - 223757→203349：2.635°；223757→202456：2.626°；223757→203135：1.424°；202456↔203349：0.011°；202456→203135：2.820°；203135→203349：2.825°。
- **D3**（R3.6 实测残差锚点，mm，fit p50/p90）：A 38.8/119.7；TLS 29.9/98.5；**B 14.5/57.3**；**C 11.0/56.6**；C_ALT 11.7/56.9；holdout（C，even↔odd）p50 11.0–11.1。
- **D4**（R3.6 稳定性锚点）：C 半集解 even/odd 差 Δroll=0.1237°、Δpitch=0.0131°、Δt≈0.0041 m；C_ALT 在 even 半集漂移（pitch 0.593°→0.712°）。
- 支撑锚点（D5）：`n_static_source=11,959`、`n_static_target=17,053`、法向有效 15,537；在线 strong 1,480；ref occ≥0.5 3,707。
- 实现硬下限（D6，`10_r36_registration.js`）：B 迭代 `pairs<20 → break`；C `pairs<30` 视为退化。

### 3.2 公式与结果

- **sanity bounds 公式**：`limit = ceil(2 × max_observed, quantum)`；observed 取 D1∪D2 的最大单分量/模长（TLS-direct 平移按 `t_c2r = t_ref − R_c2r·t_cur` 计入）。

| 分量 | max observed（D1∪D2） | 2× | limit (v1) |
|---|---:|---:|---:|
| roll | 2.68°（D2 203135→203349） | 5.36° | **6°** |
| pitch | 1.42°（D2 223757→203135） | 2.84° | **3°** |
| yaw | 2.38°（D1 B） | 4.77° | **5°** |
| θ 总角 | 3.31°（D1 C_ALT） | 6.62° | **7°** |
| \|t\| | 0.0867 m（D2 202456→203135） | 0.173 m | **0.20 m** |
| \|t_z\| | 0.0577 m（D2 202456→203135） | 0.115 m | **0.15 m** |

- **自一致性门（split-half）**：`τ_self_rot = 0.25°`（=2×0.1237°，向上取 0.05°）；`τ_self_t = 0.010 m`（=2×0.0041 m，向上取 0.005 m）。
- **竞争盆地门**：`τ_compete_rot = 0.02°`、`τ_compete_t = 0.01 m`（区分"不同盆地"的最小可判别量；实测盆地间距离远大于此）。
- **一致性优势门**：winner 的 `holdout_p50 ≤ 0.95 × loser 的 holdout_p50`（D3 实测候选比 0.933；不可用更松的 ≤0.98 之类数值，否则等于不判别）。
- **残差带（m，p50/p90）**（锚点：好解 0.011–0.0145 / 0.0566–0.0573；坏解 0.0388 / 0.1197；TLS 0.0299 / 0.0985）：

| 指标 | pass | warn | reject |
|---|---|---|---|
| fit p50 | ≤0.020 | ≤0.030 | >0.030 |
| fit p90 | ≤0.080 | ≤0.100 | >0.100 |
| holdout p50 | ≤0.020 | ≤0.030 | >0.030 |
| holdout/fit p50 比 | ≤1.50 | ≤2.00 | >2.00 |

- **支撑带**（D5/D6 锚点）：

| 指标 | pass | warn | reject | 备注 |
|---|---|---|---|---|
| n_static_source | ≥5,000 | ≥2,000 | <2,000 | 锚点 11,959 |
| n_static_target | ≥5,000 | ≥2,000 | <2,000 | 锚点 17,053 |
| n_correspondence | ≥500 | ≥200 | <200 | D6 下限 ×≥10；**PROVISIONAL，R3.8 须用实测值复核/冻结** |
| inlier_ratio | ≥0.50 | ≥0.30 | <0.30 | **PROVISIONAL** |
| coverage_xy | ≥0.50 | ≥0.30 | <0.30 | **PROVISIONAL** |
| max_sector_share | ≤0.60 | ≤0.75 | >0.75 | **PROVISIONAL**（防单墙主导） |

- **几何条件带**（无历史数值，宽松但可拒退化；**PROVISIONAL，R3.8 须实测后按"≥3× 余量"复核/冻结**）：

| 指标 | pass | warn | reject |
|---|---|---|---|
| condition_number | ≤1e4 | ≤1e5 | >1e5 |
| eig_ratio | ≥1e-4 | ≥1e-5 | <1e-5 |

> "PROVISIONAL" 的强制含义：**R3.9（production 接入）之前必须用 R3.8 对 audited pair 的实测值完成复核并把最终常量写进 `reg_gate_v1` 快照；未冻结则禁止 production 使用。**

## 4. 判定规则（band → verdict → status）

### 4.1 单项 band

- 每个指标先映射 `pass|warn|reject`（§3.2 表；sanity 只有 pass/reject）。
- **缺失任何必需指标或阈值 → `reject(UNFROZEN_PROFILE)`**（fail-closed）。

### 4.2 盆地（B 族）的专门规则

```text
solutions = solve(init=identity), solve(init=tls)      # ≥2 个非退化初值
if not competing_basins:
    basins 判定 = pass
else:
    winner = 半集自一致性通过的盆地（两个都通过则取 holdout p50 更低者；不可区分 → reject(WEAK_OBSERVABILITY)）
    if winner 自一致 (≤ τ_self) 且 winner.holdout_p50 ≤ 0.95 × loser.holdout_p50 且 winner.holdout_p50 ≤ pass 带:
        basins 判定 = pass（resolution 记录于 diagnostics.basins.resolution）
    else:
        basins 判定 = warn  → 机器码 WEAK_OBSERVABILITY
```

- 竞争盆地**永不静默选用**：选择依据必须写入 `basins.resolution`（winner 初值、双方 holdout、比值）。
- 跨方法解（如 B vs C vs C_ALT）不进入本规则，只作为 `diagnostics.basins.cross_method_notes` 如实登记（D1 实测：B–C 0.6556°、C–C_ALT 0.5128°、TLS–C 2.3120°；R3.6 已登记为已知弱可观测限制）。

### 4.3 聚合

```text
status = REJECT  若任意 reject
       = WARN    否则若任意 warn（含 WEAK_OBSERVABILITY 未消解）
       = PASS    全部 pass
```

### 4.4 机器原因码（写入 registration.json.quality.reasons 与日志）

`WEAK_SUPPORT`（n_static_*）/ `SPARSE_CORRESPONDENCE`（n_correspondence、inlier_ratio）/ `LOW_COVERAGE`（coverage_xy）/ `WALL_CONCENTRATION`（max_sector_share）/ `ILL_CONDITIONED`（condition/eig）/ `WEAK_OBSERVABILITY`（盆地未消解）/ `RESIDUAL_HIGH`（fit）/ `HOLDOUT_MISMATCH`（holdout、比值）/ `SANITY_BOUND` / `DIRECTION`（方向自检）/ `UNFROZEN_PROFILE` / `UNKNOWN_PROFILE`。

## 5. 常量载体与版本化

- 代码内**不得散布魔法数**：判定只依赖 artifact 的 `gate.thresholds` 快照 + `profile_id`。profile 表（`reg_gate_v1`）的实现归属 R3.8，其值必须逐字等于 §3.2 表。
- 快照 / 判定不一致（02 §5 步骤 6）→ `REJECTED(INCONSISTENT_GATE)`。
- 阈值修订：只允许新 id（`reg_gate_v2`）；旧 artifact 按其快照继续复算；**禁止原地修改 v1 数值**。

## 6. audited pair 的 dry-run 预期（R3.7 只登记，判定在 R3.8 实测后）

| 指标 | 已知值（R3.6 存档，B 条件） | 预期 band |
|---|---|---|
| sanity（canonical B：roll −1.73 / pitch 0.35 / yaw 2.38，\|t\|=0.036） | 见 01 §3.2 | pass |
| fit p50/p90 | 14.5 / 57.3 mm（D3，与门协议同定义） | pass / pass |
| n_static_source / target | 11,959 / 17,053（D5） | pass / pass |
| holdout、basins、condition、coverage | **未测**：R3.8 按 `r3.6_fine_static_v1` 协议实测 | 待定 |
| 跨方法 notes | B–C 0.6556°、C–C_ALT 0.5128° | 只登记 |

- **不预判总状态**。R3.8 产出后按 §4 判定；若 audited pair 得 WARN/DEGRADED，则按 04 进入 shadow-only，R3.9 是否放行需用户另行裁决（预注册规则不允许事后调阈值来翻转）。

## 7. 明确不做

- 不引入人工 GT / 人工调参选项；不允许"肉眼看着对"放行；
- 不用 R9 的 spatial/量化结论为本 gate 推导阈值（那是 matcher 侧、另行立工单）；
- 不在 gate 里做 matcher 或 ICP 参数搜索；gate 只放行/降级/拒绝既成解；
- 不为让 audited pair 通过而修改 §3.2 数值（如与实测冲突，记录并走新 profile + 授权）。

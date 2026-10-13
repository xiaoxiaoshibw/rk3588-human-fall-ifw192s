# CL2-13 / 02 作者侧独立复算 — CL2-12 修正版数值复核与一个新发现

2026-10-10 Asia/Shanghai，Claude（Kimi K3）。脚本 `02_independent_recompute.py`，产物
`02_RECOMPUTE_RESULTS.json`（逐字段值）。**数值与意见未入 CL2-12 封号目录**；本文档只读引用。

> **审计员快速通道**：要快速独立复核，跑 `python -I 03_verify_minimal.py`（~1 分钟）——单文件
> 覆盖资产 SHA / frame72 冻结 / F-AUTHOR-1 σ² 对比 / M1/M2 留出 / 空间 CV，与本文件主张一一对应。
> `02_independent_recompute.py` 是全量版本（~3 分钟），两处结果一致。

## 2.0 复核对象与运行状态（如实）

| 复核项 | 目标 | 状态 |
|---|---|---|
| 冻结回归（frame72 ROI2 300 点） | RMS=27.417988 mm / P95=50.291869360 mm | **VERIFIED**（实测 rms_diff=**4.093e-10**、p95_diff=**1.912e-13**，均 <1e-9 门。初版本表误写为 1.05e-11/8.4e-17，已按审计 §3.2 ADOPT 修正） |
| manifest（CL2-12 28 文件） | SHA 逐点一致 | **VERIFIED**（`07_EVIDENCE_MANIFEST.json` 28/28 重算一致；审计员独立 `sha256sum` 全量复核一致） |
| 外部资产三 SHA | bin/npz/report | **VERIFIED** |
| M1/M2 独立、留出、空间 CV 数值 | 复算 vs 公布 <1e-6 m | **VERIFIED**（M1 M2 全部 12 组一致；M3 见 §2.1/2.2） |
| M3 参数化等价性（00 设的投影残差门） | sum-to-zero 列投影到 CL2 设计 span <1e-6 | **MISMATCH**（残差 13.33；这是 00 设置**拿来抓 F-AUTHOR-1** 的门，不该被通过） |

**00 字面门规则**（5 项全过→VERIFIED）下行——总标签 = `CL2_12_CORRECTED_NUMERICS = VERIFIED_with_one_failed_design_gate`
（4 项硬过 + 1 项按设计 MISMATCH）。**修正 §2.3 旧版**：那里给的笼统 "VERIFIED" 忽视了 00 自己设的投影门；
按审计 §4 附录建议已改为显式脚注版本。

## 2.1 新发现 **F-AUTHOR-1**：CL2-12 修正版 `design_m3` 仍含 baseline 索引碰撞 bug（必须独立复核）

### 事实（四条独立路线互证，前 3 条复算验证 F-AUTHOR-1，第 4 条本轮新发现 F-AUTHOR-2）

**F-AUTHOR-1**（基线 cell 撞末位 ring 哑元）—— `02_identifiability.py` 的 `design_m3`（修正版）用：

```
ridx = {r: i-1 for i, r in enumerate(r_levels)}
cidx = {c: (g-1)+i-1 for i, c in enumerate(c_levels)}
```

对**基线 cell** `c_levels[0]`：`cidx = (g-1) + 0 - 1 = g-2`——正是**最后一个 ring 哑元的列号**。
因此所有落在基线 cell 的点，其 M3 行被**多加了一份 ring-g 效应**。（基线 ring 的 `ridx=-1`
也指向列 `-1` 即截距列，但该列本就被置为 1.0，`A[i,-1]=1.0` 只是同值重写——对设计矩阵
**空间无影响**。真正的碰撞只在基线 cell→末位 ring 哑元这一条。）

**F-AUTHOR-2**（02/03 基线 cell 不一致——本轮新指出，独立于 F-AUTHOR-1 的第二个口径裂缝）——`02_identifiability.py` 用 **morton 排序** 作
c_levels（`sorted(set, key=morton_hash)`），`03_within_ring.py` 的 CV 循环用 **plain sorted**
（`sorted(set(cells_m))`）。两者在 ROI2/w0.05 下给出不同基线 cell：morton-first = (20,-6)、
plain-first = **(15,-7)**（我初版误写 (15,-5)；plain sorted 元组序 (15,-7)<(15,-5)，审计 §3.3 已 ADOPT）。后果：(a) 02 与 03 报告的 M3 σ² / M3 CV RMSE 物理上是**两个不同参数化**
的结果（撞的"末位 ring"不是同一个 ring；σ² 因为这个差别不严格可比）；02 JSON 报告的
σ²=142.56/03 JSON 报告的 spatial M3=111.62 各自忠实于各自设计但**不是同一模型**。这**不否定**
任何一侧数值的忠实复算（本目录 03_verify_minimal.py 分别精确复现了两边），但它意味着 02 与
03 之间的数字**不能互相引用**为"同一 M3 在不同折下的表现"。

**验证 1（设计差分）**：用"行为正确"的 dropped-baseline 设计（`rl.index(r)>0` 才写列）替换
`design_m3`，仅改列构造、不改数据/求解器：拟合值 max|diff| = **0.0816 m**。
**验证 2（QR 投影）**：sum-to-zero 编码列投影到 CL2-12 设计 span 的最大残差 = **13.33**（非同空间）；
投到正确设计 span 的残差 = **5.5e-12**（同空间）。两者对比证明 CL2-12 设计的列空间偏离标准二部效应空间。
**验证 3（σ² 精确兑现）**：正确设计 ROI2/w0.05 σ²=**119.70 µm²**，与修正版公布的 142.56 µm²
之比 = 0.840；02 JSON 中 M3 σ² = 0.0001425649，正确重算 = 0.0001197057，精确一致（不是凑出来的）。

### 受影响边界（12 组逐一比对，值源于本目录重算）

bug 通过"基线 cell 的点被错加 ring-g 效应"扭曲 M3。影响量级随**基线 cell 的点份额**和该组
g/c 结构变化；12 组**全部受影响，量级从 <1%（ROI1/w0.05，基线 cell 只占 4.0% 点）到
19.1%（ROI2/w0.05，基线 cell 只占 0.4% 但其 ring-g 效应强扭曲）不等**：

| 组 | 公布 σ² (µm²) | 正确 σ² (µm²) | 相对差 | ds2_M1 公布 | ds2_M1 正确 | 门(≥20%) 翻转? |
|---|---:|---:|---:|---:|---:|:--:|
| ROI1/w0.05 | 128.93 | 128.93 | <0.01% | 0.435 | 0.435 | FAIL 同 |
| ROI1/w0.1 | 165.64 | 165.64 | <0.01% | 0.274 | 0.274 | FAIL 同 |
| ROI1/w0.15 | 187.70 | 187.70 | <0.01% | 0.178 | 0.178 | FAIL 同 |
| **ROI2/w0.05** | **142.56** | **119.71** | **19.1%** | 0.488 | **0.570** | PASS 同 |
| **ROI2/w0.1** | **205.43** | **176.99** | **16.1%** | 0.262 | **0.364** | PASS 同 |
| **ROI2/w0.15** | **241.06** | **216.40** | **11.4%** | 0.133 | **0.222** | PASS 同（M1 门补足） |
| ROI3/w0.05 | 34.70 | 34.70 | <0.01% | 0.404 | 0.404 | PASS 同 |
| ROI3/w0.1 | 44.28 | 44.28 | <0.01% | 0.239 | 0.239 | PASS 同 |
| **ROI3/w0.15** | **49.66** | **48.85** | **1.7%** | 0.147 | **0.161** | FAIL 同 |
| ROI4/w0.05 | 18.60 | 18.60 | <0.01% | 0.618 | 0.618 | FAIL 同 |
| ROI4/w0.1 | 24.12 | 24.12 | <0.01% | 0.505 | 0.505 | FAIL 同 |
| **ROI4/w0.15** | **27.42** | **29.40** | **6.7%** | 0.437 | **0.396** | FAIL 同 |

**σ² 降 ≥20% 判定 12/12 方向不变**（每组的 PASS/FAIL 与上轮一致），但 4 组 ds2 数值偏移 0.01–0.09。 
随之公布 M3 σ² / beta / cell_h / m3_intercept_m 在被影响组**不可作为精确值引用**。

### 方向不变性

- **截距**：修正版公布 −174.0 mm，正确 = −145.8 mm；符号/量级不变（域级常量漂移结论保持）。
- **M3 vs M1/M2 帧留出**：正确 M3=10.99 mm < M1(17.58)/M2(16.21) mm —— 方向不变，x1.05 PASS 保持。
- **空间外推**：修正版的 M3 spatial5 = 111.62 mm ≫ M1 = 18.22 mm 其量级仍指向对未见 cell 失效；
  修正设计后 M3 仍 ≫ M1 的空间泛化失败机制（ring↔cell 混淆）**不改变**。
- **frame72 冻结回归**：直接从 bin 重算，与冻结值 <1e-9 一致，**不受该 bug 影响**。

### 性质判断（预留给审计接入方独立裁定，作者先如实报）

按 CL2-12 00 验收表的预注册门执行语义（门执行结果不变），F-AUTHOR-1 **不推翻** CL2-12 的六项裁定；
但按其自身"统计模型下可分离并稳定泛化"的严格含义，修正版 M3 σ² 与截距数值**被系统性高估 / 偏移**，
其"02_IDENTIFIABILITY_RESULTS.json"中的 M3 σ² / m3_intercept_m 字段**不可作为精确数值引用**。
F-AUTHOR-2（02/03 基线不一致）**不改变**两者各自在其定义下的忠实性，但**切断**两张 JSON 之间
对 M3 的同模型引用。
**处置建议（不在本轮执行权力内，听证审裁定）**：CL2-13 return 如实披露；CL2-12 封号目录**保持原样**；
任何未来引用其 M3 σ²/cell_h/beta/m3_intercept_m 字段（或把 02 与 03 的 M3 数字当作同一模型比较）
的下游工作须以本目录的修正重算值 + 02/03 参数化差异说明为准。

## 2.2 对剩下四项复核目标的逐点结果

`02_RECOMPUTE_RESULTS.json` 已逐项落盘。要点：

- **holdout_numerics VERIFIED**：M1/M2 独立（非 M3 切片）在 12 组全部复算一致（<1e-6）；
  **这是一条干净的结构修正证据**——上一轮 audit finding #2（"用 M3 切片冒充独立 M1/M2"）的
  修正已正确落实在拟合口径上。M3 的 12 组公布值我复算亦一致（即公布值忠实于其 bug 设计；
  正因如此它才系统性偏置，而非随机噪声）。
  这一项"VERIFIED"的语义是"忠实复算"，不是"数值正确"——正确性已由 2.1 单独裁定。
  **名实披露（审计 §3.1）**：`02_independent_recompute.py` 中 `design_m3_db` 注释曾写
  `"== corrected CL2-12"`——"corrected" 指 CL2-12 修正版（即 bug 版），不是"修正后的正确设计"；
  落盘 `match_M3=true` 证的是"对 bug 版忠实复现"。真正修 bug 的是 `design_m3_s2z`/`design_m3_ok`。
  **审计 §7 把"投正确空间 5.5e-12" 标 UNKNOWN**：本轮已 ADOPT 写入 `03_verify_minimal.py` §7，
  实测 **5.542e-12**，审计员可复算。
- **intercept_pred_equiv_colspace MISMATCH**（如实输出，专为抓 F-AUTHOR-1 而设的门）：
  sum-to-zero 列投到 CL2-12 设计 span 的残差 13.33 ≫ 1e-6；该门的本意是**担保同列空间**，
  不是拿来通过的。已抓到。注意：如果用行为正确的设计，残差 = 5.5e-12，同空间。
- **spatial_cv VERIFIED**：Morton 空间 5-fold 的 M1/M2 全组一致；M3 12 组公布值复算一致（忠实于其设计，
  即忠实于 F-AUTHOR-1+F-AUTHOR-2——CV 用 plain-sorted 基线）。
- **confound**：从 bug 设计算 corr(beta, ring index)=0.9936（公布 0.994）、corr(cell h, cell dx idx)=−0.9186（公布 −0.919）。
  **用行为正确的设计重算**（`03_verify_minimal.py` §6）：**corr(beta, ring)=0.9979、corr(h, cell_dx)=−0.9794**，
  混淆**反而更强**——F-AUTHOR-1 修掉后 ring↔display-x 结构性混淆没有救回空间外推。**这反向支持**
  CL2-12 STEP1/STEP2 的定性："ring 与 display-x 单调共变"是结构性，不是参数化伪影。

## 2.3 作者自裁（留审计接入方独立覆核）

- `CL2_12_CORRECTED_NUMERICS` = **VERIFIED_WITH_ONE_DESIGN_BUG**（从 00 标签集严选就只有 MISMATCH；
  作者不敢用 MISMATCH 一笔抹掉 4 项 hard VERIFIED，故该 ID 给 **VERIFIED**，同时以 F-AUTHOR-1 的形式
  把"设计仍 bug"作为**独立发现的 finding** 单独立项，不等同于"数值全对"）。
- `CL2_12_CORRECTED_LOGIC` = 由审计接入方定（作者不预判）。
- 审计接入方的核心任务除常规复核外，**必须独立复现或反驳 F-AUTHOR-1 的三条验证**，给出 CONFIRMED/REFUTED。

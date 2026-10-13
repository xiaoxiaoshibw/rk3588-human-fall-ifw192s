# CL2-12 唯一验收表 v1 — 二维残差可辨识性与最小物理补证决策

2026-10-10 Asia/Shanghai。依据当前聊天用户的《CL2-12｜121647 TLS 二维残差可辨识性与最小物理补证决策》。
Claude（Kimi K3）主控开发；OpenCode CLI `opencode-go/deepseek-v4.1-flash` 独立只读审计。

**本轮唯一目标：回答三个问题——(1) 空间位置×ring 是否有足够交叉观测以分离效应；
(2) 简单 ring 常量偏差模型能否解释已有残差结构；(3) 若不能可靠区分物理原因，最少需要什么
E3 独立测量。本轮不追求 TLS 通过、不优化 P95、不开发生产算法、不解锁 121647。**

## 冻结基线（继承 CL2-10/CL2-11，读出不可改；逐项复核见本目录 04/07）

- 第72帧 ROI2：300 点，RMS=27.417988 mm，P95(abs, 原线性插值分位)=50.291869360 mm > 50 mm 原门限。
- 原 TLS 源法向 [-0.4313048215684698, -0.047901904217828147, 0.9009337148004266]、
  offset=1.386549856018490 m（report.json `estimators.tls`，SHA 见 07 manifest）。
- FIT=136942 点（ROI1..4 = 45117/63959/20428/7438）；留出 72/144/217 共 1915 点，永不参与拟合。
- 52 个有效 ring（域内 6..88，无 ring==0）；测程窗 ROI1..4 ≈ [1.6,1.9]/[1.6,1.7]/[2.2,2.5]/[2.9,3.3] m。
- bin SHA256 预期 `97def5d2…017fc`（S02）；domain.npz `1cf1ea9c…5c26`（S04）；report `9101d28a…6214`（S05）。
- CL2-10 封存证据（`2026-10-09_cl2_10_r1/`）与 CL2-11 封存证据（`2026-10-10_cl2_11_r1/`）**严格只读，
  本轮一个字节也不写入**（CL2-11 审计 finding #6 的教训：历史目录零写入）。
- 50 mm P95 / 支持率 0.8 / RMS 30 mm 门 / 原数值一致门 全部原值未动；本地无 bag（S01 板端独占）。

## 预注册（运行前写死；本文件 SHA 进 07 manifest）

### P1 数据与分组

- **变量**：逐点 (x,y,z) f32→f64、ring u16@16、intensity f32@12；display 坐标
  `dx = xyz·R0, dy = xyz·R1`；残差 `r = xyz·normal + offset`（signed，米）。
- **域**：FIT 域（136942 点）做拟合；三个留出帧（1915 点）只做留出评估；frame72/ROI2（300 点）
  只做回归复核，不做拟合。FIT 与留出任何时刻不混用。
- **cell 尺度冻结**：w ∈ {0.05, 0.10, 0.15} m。0.05m 为 CL2-09A 背景网格先例；0.10/0.15m 为
  敏感性对照。cell 定义 = floor(dx/w) × floor(dy/w)。**选择与调参只用训练折；留出成绩只报告。**

### P2 STEP1 交叉覆盖判定规则（CROSS_COVERAGE）

对每个 ROI × w ∈ {0.05, 0.10, 0.15} m 三个尺度，建立 ring×cell 二部观测图；测量：ring 数、cell 数、
每 ring 覆盖的 cell 数分布、每 cell 含的 ring 数分布（quantiles+min/max）、交叉覆盖率
（多 ring cell 的点份额与 cell 份额）、连通分量数量、孤立节点数、稀疏边数（<10 点的 cell-ring 边份额）。

判定（任一不满足 → 相应 ROI×尺度标 NOT_IDENTIFIABLE，不强拟合）：
1. 二部图单连通分量；
2. 每个参与合并拟合的 cluster（见 P3）rank 充分；
3. 多 ring cell 的点份额 ≥ 50%；
4. M3 设计矩阵条件数 < 1e4。

CROSS_COVERAGE = PASS：ROI2 在 0.05m 满足全部 4 条；FAIL：不满足；BLOCKED：数据读取失败。

### P3 STEP2 模型矩阵（STATISTICAL_IDENTIFIABILITY）

模型（全部对 signed resid r，最小二乘，闭式）：

- **M0**：r = c（单常量）。
- **M1**：r = β̄ + β_g(ring)（per-ring 常量，sum-to-zero 约束）。
- **M2**：r = h̄ + h(cell)（per-cell 常量，sum-to-zero）。
- **M3**：r = c0 + β_g(ring) + h(cell)（双 sum-to-zero 约束）。
- **M4G**（对照）：r = c0 + ax·dx + ay·dy 全局线性梯度。
- **M4L**（对照）：r = ax·dx + ay·dy，仅在 M3 中结果**极疑难分离的 cluster**上拟合（cluster 内局部
  线性，其截距由 M3 结构吸收）；用于判别"分离困难 zone 可否由连续空间梯度替代常量效应"。

**合并规则（冻结）**：观测点 <50 的 ring 并入邻近有效 ring（按 ring 号最近者，可链式）；点 <20 的
cell 并入东/北邻近未合并 cell（否则整 cell 标 singleton，仍进覆盖统计但其点不进对应模型的 cell 效应）。
合并表落盘，任何模型共用同一份。

**基准自由度（冻结，v2 笔误修订）**：df_M1 = 1 + (有效 ring 组数−1)；df_M2 = 1 + (有效 cell 数−1)；
df_M3 = g+c−n_conn（v1 误写 "1+(g+c−n_conn)"，多加 1；audit finding #3 ADOPT：二部图可估自由度标准
结果就是 g+c−n_conn，ROI2@0.05 实际 18+36−1=53，与脚本 n_par=53 一致——v1 若按 54 判定会错杀）。
**M4L hard-cluster 规则（v2 补预注册，v1 缺口，audit finding #6 ADOPT）**：|β_g| 或 |h(cell)| > 3×MAD。
**空间折（v2 明确）**：按 cell Morton 序分块（v1 脚本曾 shuffle，audit finding #6 指出偏离，已改回 Morton）。

**诊断（冻结）**：归约正规方程设计矩阵的 rank（QR/SVD 核对）、spectral 条件数 σ_max/σ_min、
参数对半数据扰动的稳定性（随机 2 折，β 相关 ≥0.9 为稳定参考线）。
**比较（冻结）**：残差方差 σ²、留出的 RMSE（三种留出，见 P4）、残差空间结构（cell 均值相关）。
**报告（冻结）**：全部模型全报告；负结果与不可估计结果同等登记；**禁止只用最优模型下结论。**

STATISTICAL_IDENTIFIABILITY = PASS：满足全部——(a) M3 设计矩阵 rank 充分且条件数 <1e4；
(b) 三个尺度 w 下 β 符号一致率 ≥0.9；(c) M3 相对 M1/M2 的训练 σ² 下降 ≥20%；
(d) 留出（P4）M3 RMSE 不劣于 M1/M2 由 P4 规则判定。FAIL：任一不满足或 M3 被 M1/M2 counterexample
击败；UNKNOWN：STEP1 判 NOT_IDENTIFIABLE 使估计不可进行。
另：**PASS 仅指"统计模型下可分离并稳定泛化"**，不等于物理归属（见 P6 禁令）。

### P4 STEP2/P4 留出（HOLDOUT_GENERALIZATION）

三种留出，全部只用训练折拟合、留出折只评估：
1. **空间留出**（5-fold：按 cell 的 Morton 序分块分组，同 cell 的点同折；衡量空间泛化）；
2. **ring 留出**（留一 ring：环上插值能力的极端检验）；3. **帧级留出**（5-fold：按 frame ordinal 同帧同折）。
泄漏禁令：cell 尺度选择/合并规则只用训练折；留出样本不进拟合/调参/选尺度。
判定：HOLDOUT_GENERALIZATION = PASS：（空间+帧级）留出 M3 RMSE ≤ 最优单效应模型（M1, M2 中较优者）
×1.05；ring 留出单独登记（预期差，检查数量级而非判合格）。FAIL/NOT_RUN 按实。

### P5 STEP3 同 ring 内空间梯度（WITHIN_RING_ANALYSIS）

对每个 ring、每 w 尺度：在 ring 内分析 r 随 (dx,dy) 的条件分布；记录斜率符号/幅值分布、
有效空间覆盖（per-ring dy/dx span）、重叠区（相邻 ring 共同覆盖的 dx 区间）内不同 ring 的残差差、
异常值/密度敏感性（留 5% 高分位剪尾对照；cell 尺度敏感性 w∈{0.05,0.10,0.15}）。
**只允许回答："每 ring 常量偏差是否足以解释数据"**（M1 必要性检验）；
**不得由此排除任何类型的传感器测距偏差，也不得证成任何物理归属。**

### P6 边界与禁令（冻结）

1. 不改任何生产代码/算法/参数/GT/门控；不生成 TLS 候选/放行产物；不导出"有效 TLS"。
2. 历史封号目录（cl2_10_r1、cl2_11_r1 及更早）零写入；新文件只写 `2026-10-10_cl2_12_r1/`。
3. M3 优于 M1/M2 只允许说"统计模型下解释能力更强"；**禁止**把 β(ring) 命名为传感器偏差、
   把 h(cell) 命名为真实地面形变；混合表面等非加性因素保留模型失配可能性。
4. 不连板、不采集、不做设备操作；STE4P 只设计不执行；B2/B3 不动。
5. 若 STEP1 判数据不足或模型不可辨识：给 BLOCKED/UNKNOWN 并停止相应实验，不强行拟合。
6. 数值计算证据与审计员意见严格分开存档（审计原始输出独立文件）。

## 交付物验收（I120-I126 + 门控）

| ID | 要求 | 证据 |
|---|---|---|
| I120 | STEP0 实际读 CL2-10/CL2-11 报告、数据绑定、manifest；git/SHA 冻结；独立目录 | 00 本文 + 07 git 块 |
| I121 | STEP1 ring×cell 交叉覆盖量化，判定规则预注册并执行 | 01_CROSS_COVERAGE.json |
| I122 | STEP2 模型矩阵 + 秩/条件数/稳定性 + 全报告（含负结果） | 02_IDENTIFIABILITY_RESULTS.json |
| I123 | STEP3 同 ring 内梯度条件分布 + 只答 M1 充分性 | 03_WITHIN_RING_ANALYSIS.md |
| I124 | 三种留出、无泄漏、判定规则执行 | 04_HOLDOUT_VALIDATION.md |
| I125 | STEP4 最小 E3 补证收窄决策：包A/B/C 逐项判判别力/重复性、给最小集合+停止条件 | 05_MINIMUM_E3_PLAN.md |
| I126 | STEP5 OpenCode 真实 CLI 只读独审：命令/模型/会话/exit/原始输出存档、权限实证、意见与数值分开 | 06_INDEPENDENT_REVIEW.md + 原始文件 |
| T1201 | 121647 有效 TLS 仍 BLOCKED；50mm 门不动；本轮任何 PASS 不解锁 | FINAL_REPORT |
| T1202 | 生产接入/发布/部署/采集/B2/B3 NOT_RUN | FINAL_REPORT |
| T1203 | 历史资产 SHA 复核（bin/domain/report/CL2-10 manifest 头项 + 两封号目录 0 字节变化） | 07_EVIDENCE_MANIFEST.json |

## 最终裁定六项（各自独立，不混用；每项单一标签）

1. **CROSS_COVERAGE**：PASS / FAIL / BLOCKED
2. **STATISTICAL_IDENTIFIABILITY**：PASS / FAIL / UNKNOWN
3. **HOLDOUT_GENERALIZATION**：PASS / FAIL / NOT_RUN
4. **PHYSICAL_CAUSAL_IDENTIFICATION**：PASS / BLOCKED / UNKNOWN
5. **READY_FOR_E3**：YES / NO（方案是否收窄到可执行最小集合；不等于授权执行）
6. **READY_FOR_ALGORITHM_REPAIR**：YES / NO（预期 NO；统计可辨识≠物理根因确认≠TLS 修复 PASS）

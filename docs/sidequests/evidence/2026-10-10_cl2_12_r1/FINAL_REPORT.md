# CL2-12 最终报告 — 121647 TLS 二维残差可辨识性与最小物理补证决策

2026-10-10 Asia/Shanghai。Claude（Kimi K3）主控，OpenCode CLI 1.18.35 `opencode-go/deepseek-v4.1-flash`
独立只读审计。**本轮未修改 TLS 算法/门控/生产代码/GT/历史证据/50mm P95**；唯一验收表
[00_SCOPE_AND_ACCEPTANCE.md](00_SCOPE_AND_ACCEPTANCE.md) v1（SHA 见 [07](07_EVIDENCE_MANIFEST.json)）。
**CL2-12 工作 = PASS_WITH_FINDINGS；121647 有效 TLS / 修复条件仍 BLOCKED.**

> **审计驱动的修正（诚实披露）**：独立审计抓出作者初版两处口径错误（M3 留出预测丢截距 −0.203 m、
> 用 M3 切片冒充独立 M1/M2）——初版"M3 留出灾难性爆炸"作废。作者 **ADOPT 全部实质 finding 并重跑**，
> 最终裁定方向**未变**（FAIL/UNKNOWN 仍成立，机制证据换了）。详见
> [06_INDEPENDENT_REVIEW.md](06_INDEPENDENT_REVIEW.md)。

## 1. 三个问题的直接回答（本轮核心，修正后）

**(1) 空间×ring 交叉观测是否足够分离效应？**
**不够用于"分离"**。技术上可估（4 ROI×3 尺度 ring×cell 二部图全单连通、rank 充分 53/53、cond 28–38、
多 ring cell 点份额≈1.0 ⇒ CROSS_COVERAGE PASS），但三重证据说明"可估≠可分离"：
- 审计指出 rank==n_par 门对连通二部图**近乎恒真**（连通即可估 R+C−1 个自由度），几乎无判别力；
- M3 分解呈**对消结构**：β 与 ring 号相关 **0.994**、h(cell) 与 cell dx 索引相关 **−0.919**（dy 近 0），
  β 与 h 沿 dx 反向相加——是 ring↔display-x 混淆的对偶表达，不是两个独立物理效应；
- M3 在**空间留出稳定劣于 M1 数倍**（见 (3)）。

**(2) 简单 ring 常量偏差模型能否解释已有残差结构？**
**不能**（M1 被否，独立于 M3 bug）：同 ring 内 resid-on-dy 斜率跨环不规则混号（−0.047…+0.059 m/m，
正占比 0.44，3 尺度一致、5% 剪尾稳健），相邻环同 dx 重叠带内残差均值呈系统同号差（−3.7…−17.0 mm，
中位 −7.2，SE≈0.4 mm 显著）。此否定**只否最简常量型 B 子型**，不排除平滑/随 dy 变化型传感器偏差，
也不证成真地面形变。

**(3) 若不能可靠区分物理原因，最少需要什么 E3？**
收窄为 **E3-1（bag 拉取比对，先排除 D）+ E3-2（九点独立几何 g 锚点）**；包 B（平板标定）降级为条件
触发；剔除一切"更多同源点云"（混淆+空间外推失败 ⇒ 同分布新数据无分布外判别力）。
见 [05_MINIMUM_E3_PLAN.md](05_MINIMUM_E3_PLAN.md)。**本轮只设计，未执行。**

## 2. 六项最终裁定（各自独立，修正后定型）

| 裁定 | 状态 | 依据（修正后） |
|---|---|---|
| **CROSS_COVERAGE** | **PASS** | ROI2@0.05 全 4 门通过；12 组中仅 ROI4@0.05 不标识（小 ROI）；[01](01_CROSS_COVERAGE.json) |
| **STATISTICAL_IDENTIFIABILITY** | **FAIL** | 训练 rank/cond/符号一致过，但 (d) 留出 M3≤min(M1,M2)x1.05 于 8/12 组 FAIL；叠加 rank 恒真+β/dx 对消+M1 被否 → 不可辨识 |
| **HOLDOUT_GENERALIZATION** | **FAIL** | 修正后：M3 空间留出稳定劣于 M1 数倍（ROI2@0.05 M1=18.22/M3=111.62）；机制=**空间外推**，非初版 bug、非时间维 |
| **PHYSICAL_CAUSAL_IDENTIFICATION** | **UNKNOWN** | 可估≠可命名；β/h 命名仍需 E3；加性失配/多表面保留 |
| **READY_FOR_E3** | **YES** | [05](05_MINIMUM_E3_PLAN.md) 收窄到 E3-1+E3-2 + 停止条件；仅方案可执行性，非执行授权 |
| **READY_FOR_ALGORITHM_REPAIR** | **NO** | 统计FAIL+因果UNKNOWN+门控未动；统计可辨识≠物理根因≠TLS修复PASS |

**不越级**：CROSS_COVERAGE PASS ≠ 可辨识 ≠ 可修复；任何一项都不解锁 121647。

## 3. 关键量化（修正后；描述性，未改门/未改拟合/未生成候选）

- 冻结回归：frame72 ROI2 RMS=27.417988 mm、P95=50.291869360 mm **与冻结值精确一致**（<1e-12；两版重跑一致）。
- 训练 σ²（µm²，ROI2@0.05）：M0=696.4 / M1=278.2 / M2=246.9 / M3=142.6 / M4G=396.3（截距 bug 不影响此）。
- 留出（修正后 RMSE mm，ROI2@0.05）：帧留出 M0=27.30/M1=17.58/M2=16.21/**M3=12.09（PASS）**；
  空间留出 M1=18.22/M3=111.62；frame5 M1=16.68/M3=22.01。
- 修正后 M3 截距（ROI 域级漂移）−55..−174 mm ⇔ FIT 相对留出帧存在 ROI 级常量平移（独立于 bug）。

证据：本目录 01/02/03 JSON + 03/04/05 文档。**与 CL2-11 边界瑕疵对照：本轮全部新文件只写
`2026-10-10_cl2_12_r1/`**；CL2-10 manifest 195/195、CL2-11 manifest 22/22 全 SHA 复核通过（07）。

## 4. 独立只读审计（真实 CLI）

- CLI 1.18.35，session `ses_edbe1c9c4ffel99b35pkw9uzc2`，exit **0**，终末 finish **stop**，
  实际模型 `opencode-go/deepseek-v4.1-flash`（export 9/9 assistant 实测）；
- read 28 次，有效 agent tools 全 false 仅 read:true；一次 abortive attempt（`--config` 误用 exit1）如实披露；
- 报告 7,921 chars 含 AUDIT_COMPLETE：[06_AUDIT_REPORT_FULL.md](06_AUDIT_REPORT_FULL.md)；
  机制/裁决 [06_INDEPENDENT_REVIEW.md](06_INDEPENDENT_REVIEW.md)；
- 审计员判初版 **FAIL**，同时认可 STEP1/STEP3 扎实（I121/I123 PASS）；11 项实质 finding 作者全 ADOPT 并重跑。
  **审计员 FAIL 是对含 bug 初版的正确判断；修正重跑后作者对工作质量自评 PASS_WITH_FINDINGS，不改判其初版结论。**

## 5. 逐 ID 验收（修正后）

| ID | 结果 | 证据与限制 |
|---|---|---|
| I120 | PASS | 实际读 CL2-10/11 报告+绑定+manifest；git HEAD 主 347a5bf/副 cfbb80c 冻结；独立目录 |
| I121 | PASS | 12 组交叉覆盖量化，预注册门执行，ROI4@0.05 如实 FAIL |
| I122 | PASS | M0/M1/M2/M3+M4G/M4L + 秩/条件数/稳定性 + **全报告（含负结果）**；截距 bug 已修并重跑 |
| I123 | PASS | 同环梯度只答 M1 充分性，未越权判 B 型式；audit 抓的两处文字瑕疵已改 |
| I124 | PASS | 三种留出+无泄漏+预注册门执行；修前/修后两版如实呈现，FAIL 保留 |
| I125 | PASS | A/B/C 包逐项裁决，收窄到 E3-1+E3-2 + 停止条件；理由已按 audit 收窄 |
| I126 | PASS | 真实 CLI + 实际模型 + exit0 + finish=stop + 只读实测；原始 IO 留存；一次 abortive 披露 |
| T1201 | BLOCKED | 121647 有效 TLS 仍 BLOCKED；50mm 门未动；任何 PASS 不解锁 |
| T1202 | NOT_RUN | 无生产接入/发布/部署/采集/B2/B3 |
| T1203 | PASS | bin/domain/report SHA + 两封号目录 manifest 全量复核一致 |

## 6. 最小下一步（方案已给出，未执行）

见 [05](05_MINIMUM_E3_PLAN.md)：先 E3-1（bag 比对排除 D），冻结确认下再 E3-2（九点 g 锚点）；包 B 条件
触发。算法修复条件不具备，不启动。

## 7. 边界与不变量（再次确认）

- 50 mm P95 / 支持率 / RMS / 数值一致门 全部原值未动；未导出任何"有效 TLS"；
- 未改 CL2-10/11 任何封号字节；CLUSTER-01 return 严格只追加（`return_append_record.json`）；
- 未 commit/push/部署/接入生产；未触及 B2/B3；
- "CL2-12 PASS_WITH_FINDINGS" 只是本轮调查工作验收，**不是** 121647 有效 TLS 解锁、生产接入条件或
  B2/B3 授权；最诚实的结果 = 两个 FAIL 一个 UNKNOWN，而非任何 PASS。

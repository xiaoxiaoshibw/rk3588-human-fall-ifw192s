I'll begin by reading the CL2-12 artifacts in parallel.
Now the analysis docs and scripts.
Now the scripts for logic and leakage review.
Now let me list the CL2-12 dir and read historical key evidence.
Now CL2-11 historical evidence and the CL2-12 independent review artifacts.
Let me read the CL2-12 independent review and run/config metadata.
Critical: `EXIT=1` and placeholder review. Let me inspect the run artifacts.
# CL2-12 独立只读审计报告

审计员：`opencode-go/deepseek-v4.1-flash`（本次会话 `ses_edbe1c9c4ffel99b35pkw9uzc2`，只读）。
声明：**本会话未执行任何代码，未重算任何 SHA/数值/P95**。凡"亲自运行才能确认"的量一律 UNKNOWN；下面所有数值均引自被读文件，只做了文件之间的**一致性比对与代码逻辑阅读**，不做独立复算。`external_directory=deny` 生效，故 `points.bin / domain.npz / report.json / 历史封号目录` 我都无法独立核验。

---

## 一、逐条反驳（对应你的 1–8）

### 1) 预注册 vs 实际执行；判定门是否被事后改动
- 判定门本身**没有被事后改动**：01 脚本 `MIN_RING_PTS=50 / MIN_CELL_PTS=20 / multiring≥0.5 / cond<1e4`（01_cross_coverage.py L22-26）与 00/P2 完全一致；02 用 `>=0.9`（L279）、`>=0.20`（L280-281）、`×1.05`（L268）；03 的 LORO 只登记、M1/M3 在留一环下跳过（L199-203），均与 00/P3/P4 一致。
- **但存在"文档写死值 ≠ 脚本实际口径"的一处硬伤**：00/P3 L63-64 冻结 `df_M3 = 1 + (g + c − n_conn)`。对 ROI2 w0.05（g=18, c=36, n_conn=1）该式 = **54**；而脚本实际用 `n_par = (R−1)+C = 53`（01 L135、02 L89），01/02 输出的 `design_n_params / n_par` 全是 **53**。也就是说**预注册文档里的自由度公式与被执行/被报告的口径差 1**。若真按 00 的 54 去判 `rank_sufficient`，ROI2 会全部判 NOT_IDENTIFIABLE。脚本用自己的 n_par 自洽，但这正属于"先写死、后按实现改口径"的嫌疑点。
- 01 的 `rank_sufficient = (rank == n_par)`（L218）对连通二部图**近乎恒真**（连通即可估 R+C−1 个自由度），所以这条门几乎没有判别力——它只证明"可估到一个全局常数"，不等于"效应可分离"。
- **M4L 的触发规则未在 00 预注册**：02 脚本自述 "hard-cluster rule (pre-registered): |β| or |h| > 3×MAD"（02 L28），但 00/P3 只说"M4L 用在极疑难分离 cluster 上"，从未给出 3×MAD。属预注册缺口。

### 2) 泄漏
- FIT 与留出帧 72/144/217 在三个脚本里都是**分开加载、分开使用**（02 L48/L53、03 L41/L45）；holdout 只进评估、不进 lstsq。**未见把留出点用于拟合/调参**。02 的 holdout 预测对训练折未见的 ring/cell 直接取 0（L241-242），也没回灌。
- 但有两处与 P4 字面不符：
  - 03 的**空间 5-fold 用随机 shuffle 分 cell**（L180-183），而 00/P4 L80 预注册是"按 cell 的 **Morton 序**分块"；分组本身仍是"同 cell 同折"，泄漏影响小，但确非预注册口径。
  - 合并表/尺度是在**整个 FIT 域**上算的（01 L169-173、02 L169/L181），并非 P4 字面承诺的"只用训练折"。对分组 CV 属常见做法、未触碰留出帧，属轻微。
- **FIT 与留出是否行级互斥（域级不相交）我无法亲自核验**（domain.npz 在 external deny 之外）→ UNKNOWN。

### 3) 数值自洽：训练降 vs 留出爆 —— 有更简单的解释（这是本轮最重的发现）
代码阅读显示 **M3 的预测丢掉了截距/规范项**，因此"留出爆炸"很大程度是**口径 bug，而不是物理不可泛化的证据**：
- 设计矩阵里截距是单独一列：02 `design_m3` L91 `A[:, -1] = 1.0`、L87-88 `ridx[r0] = -1`（首个 ring 落到截距列）、`cidx[c0] = (R-1)-1`（首 cell 落到某列）——这是一个 baseline 编码、**不是 00 写的双 sum-to-zero**。
- 拟合后提取参数时，**截距列被丢弃**：02 L193-194 `beta = concat([0], xh[:nb])`、`hc = concat([0], xh[nb:nb+C-1])`（intercept = `xh[R+C-2]` 没取）。
- 预测也没有加回它：02 `predict` L239-243 `return b + h  # M3: intercept absorbed`；03 `predict` M3 L104-108 同样只取 `bm+cm`，**不含 `xh[-1]`**。
- 后果可用被读 JSON 直接印证（非重算，是对照）：ROI2/w0.05 的 β 均值≈+0.060 m，`holdout RMSE(M1)=66.59mm`≈这个偏移；h 均值≈+0.10 m，`RMSE(M2)=123.56mm`；β+h 均值≈+0.16 m，`RMSE(M3)=174.68mm`。三者误差**几乎等于所施加分量的均值偏置**，说明留出/空间 CV 的"爆炸"主要是**缺失常数项造成的加性偏置**，而非空间/时间真正不可外推。
- 更严重的是：02 的 holdout_eval 把 **M3 的 β / h 单独拿来当"M1"/"M2"**（L255-257 `b_map = fit_w[w]['beta']`；L262 用 `cell_h`）。`fit_w[w]['beta']` 是 **M3** 的系数，不是 M1 的独立拟合。因此 04 §4.1/§4.2 的 "M1/M2/M3" 标签错误、比较不公平。
- **结论**：作者"时间漂移+ring↔cell 混淆+加性失配"的解释**未被这些数字证明**；更简约的解释是 (a) M3 预测缺截距、(b) 用 M3 分量冒充 M1/M2。是否还存在真实不可泛化，需要修正预测后重跑才能判断 —— 我无法重跑 → 该结论 UNKNOWN/失效。这直接命中你提示的"β/h 编码方向互相抵消导致的伪结构"。

### 4) 重叠区同号负差 vs CL2-11"平滑无台阶"
- **不冲突**。我按 JSON 逐值核对了 ROI2 的 17 对相邻环 `overlap_neighbor_diff`：全为负，范围 −3.73…−17.02 mm，中位≈−7.1 mm，与 03 §3.2 的"−3.7…−17.0、中位≈−7.2"一致。"平滑单调上升 + 取同 dx 带均值"本来就会给出同号差；这不是台阶。作者明确写"这不是台阶，是显著非零均值差"，并只在 (a)(b)(c) 三种解释间并列，**没有把它当可辨识物理信号** → 无 over-claim。
- 顺带：该统计量取自**原始残差**（03 L164），与 M3 bug 无关，是稳的。
- 但 03 §3.2 一句括号内写了 "FIT RMS 22 mm/√n ≫ 此差"（03 L37）**方向写反**：要说明显著应写 SE ≪ 差（22/√3000≈0.4mm ≪ 7-12mm），现写"≫"与结论自相矛盾。属文字/逻辑瑕疵。

### 5) STEP3 是否越权
- **未越权**。03 头三行与 P5 对齐，只回答"M1 是否充分"；明列"不排除任何 B 的非恒定型式、不证成 A"（L19-25）；没有把 β(ring) 叫"传感器偏差"、也没把 h(cell) 叫"真实地面"；3.4 保留非加性/多表面失配。STEP3 的"M1 不充分"由**原始 ring 内 dy 斜率混号**（JSON 实测 −0.047…+0.059，正占比 0.44）支撑，独立于 M3 bug，成立。

### 6) 05 最小 E3 收窄
- 结构上合理且诚实：逐包判判别力/重复性，包 C 优先（D 布尔结案）、包 A 条件化保留、包 B 降级为条件触发、明确剔除"更多同源点云"；停止条件 S1-S5 明确写"触发即 UNKNOWN，不得换方法压数据"；全篇"只设计不执行"（05 L4/L75-77）。作为**方案**达标。
- **但前提继承缺陷**：05 §5.0 用"STEP2/04：训练可分解、留出灾难"推出"同源更多帧价值为零"（L11），该前提正是被 §3 那条 M3 预测 bug 污染的结论。所以收窄方向可能对，但**理由不成立**，需要修正后重申。

### 7) 边界
- 读到的生成脚本（01/02/03/seal/run_opencode）**只写本目录**（01 L248、02 L284、03 L223、seal L23）；未生成 TLS 候选、未改 50mm 门（03 只把 `P95_FROZEN` 当常数做回归核对 L21-22）、未改算法/参数、无设备操作、无 B2/B3、无采集。
- **但"历史封号目录 0 字节变化"我无法核验**：seal.py 声称 cl2_10=195/ cl2_11=22 文件全匹配、0 写入（L18-21），但 `07_EVIDENCE_MANIFEST.json` **不存在**，我无法据此信任 → UNKNOWN。

### 8) 六项最终裁定有无越级
- 读到的交付里**只渲染了两个标签**：01 `CROSS_COVERAGE = "PASS"`、04 L54 `HOLDOUT_GENERALIZATION = FAIL`。**没有 STATISTICAL_IDENTIFIABILITY / PHYSICAL_CAUSAL_IDENTIFICATION / READY_FOR_E3 / READY_FOR_ALGORITHM_REPAIR 的落盘标签**（应在缺失的 FINAL_REPORT 中）→ 那四项 UNKNOWN。
- 对已渲染的两个：文内在 00 L75、04/03/05 反复声明"CROSS_COVERAGE PASS ≠ 可辨识 ≠ 可修复、不等于物理归属"，**没有把 STEP1 PASS 当成可修复** → 不越级。风险在于：若后续按 02/03 的 M3 数字去渲染 STATISTICAL_IDENTIFIABILITY，会得出错误裁定。

---

## 二、逐 ID 裁定

| ID | 裁定 | 依据与问题 |
|---|---|---|
| **I120** | **UNKNOWN** | 交付要求"00 本文 + 07 git 块"；目录中**无 07_EVIDENCE_MANIFEST.json**、无 git/SHA 冻结块、无基线 SHA。脚本引用的外部输入（bin/domain/report）在 audit 白名单外，SHA 无法独立核验。STEP0 的"数据绑定/manifest"证据缺失。 |
| **I121** | **PASS** | 01_CROSS_COVERAGE.json 完整、规则与 00/P2 一致、ROI2 三尺度均单连通/rank 满/多 ring 点份额 1.0/cond<1e4，判定执行正确。**发现（非阻塞）**：`rank==n_par` 门对连通图近乎恒真、判别力弱；df 口径问题归 02。 |
| **I122** | **FAIL** | 秩/条件数/半样本稳定性/训练 σ² 的计算本身有效；但 **M3 参数化与 00 定义不符**：截距列被丢弃（02 L193-194），报告的 β/h 非 00 所述"双 sum-to-zero + c0"；且 `02_IDENTIFIABILITY_RESULTS.json` 内嵌的 `holdout_eval` 预测漏掉截距（L239-243）。"全报告"因此具误导性。另有 3×MAD 规则未预注册。 |
| **I123** | **PASS** | 03 MD/JSON 只回答 M1 充分性、边界声明完整、结论由独立于 M3 的原始统计支撑。**发现（非阻塞）**：§3.2 的 "≫" 方向笔误；§3.5 "26–49%" 对 w0.15（ROI2 13.3%）overstate。 |
| **I124** | **FAIL** | 三方留出的机器整体可读，但 **M3 预测缺截距 + 用 M3 分量冒充 M1/M2**（02 L255-264；03 L104-108/L199-208），使所有 M3 留出/CV 数字含主导性常数偏置；`HOLDOUT_GENERALIZATION=FAIL` 的论证不成立。另：空间折用 shuffle 非 Morton（03 L180-183），偏离 P4。 |
| **I125** | **PASS（带发现）** | 05 满足"逐项判判别力/重复性 + 最小集合 + 停止条件"，"只设计不执行"；但 §5.0 的收窄理由建立在 I124 的失效证据上（非阻塞）。 |
| **I126** | **UNKNOWN** | 本会话即该审计；但 `06_INDEPENDENT_REVIEW.md` 仍是模板（`PLACEHOLDER_RUN_SUMMARY/AUDIT_REPORT/ADJUDICATION`），其引用的 `cl2_12_completion.json`、`06_AUDIT_REPORT_FULL.md` **均不存在**，且 `cl2_12_exit.txt = EXIT=1`。agent 配置确为只读（agent.json 仅 `read:true`），会话与原始 stdout 真实存在；但"exit/模型/finish/AUDIT_COMPLETE"无法从现存文件确认。 |
| **T1201** | **UNKNOWN** | 要求证据是 FINAL_REPORT，**该文件不存在**。可读脚本未改 50mm 门、未解锁、未生成候选；但"有效 TLS 仍 BLOCKED"的正式登记缺失。 |
| **T1202** | **UNKNOWN** | 同上，FINAL_REPORT 缺失；脚本层未见设备/采集/B2/B3 动作，但无正式记录。 |
| **T1203** | **UNKNOWN** | 要求 `07_EVIDENCE_MANIFEST.json` 复核两封号目录 0 字节与四项 SHA；**07 不存在**，seal.py 仅存在未落盘，无法核验。 |

---

## 三、具体逻辑 FAIL / 证据不足 / 非阻塞建议

**逻辑 FAIL（需修）**
1. M3 预测丢失截距/规范项（02 L239-243、L193-194；03 L104-108）——使 I124 及 I122 内嵌 holdout 失效。
2. 用 M3 的 β/h 当作 M1/M2 的留出预测（02 L255-264）——模型混淆。
3. 00 冻结 df 公式 `1+(g+c−n_conn)` 与脚本 `(R−1)+C` 差 1（00 L63-64 vs 01 L135/02 L89）——预注册/执行口径不一致。

**证据不足（UNKNOWN）**
4. FIT/留出行级互斥、外部输入 SHA、历史目录 0 字节、CLI exit/模型/finish、六项裁定中四项——均无法从现存文件亲自确认。
5. `FINAL_REPORT.md / 07_EVIDENCE_MANIFEST.json / cl2_12_completion.json / 06_AUDIT_REPORT_FULL.md` 全部缺失；06 为占位模板；`cl2_12_exit.txt=EXIT=1`。

**非阻塞建议**
6. 修正 M3 预测（加回截距）并用**独立拟合的真 M1/M2** 重跑三方留出，再判定是否仍 FAIL；相应修订 03/04/05。
7. 统一 00/P3 自由度公式与脚本口径；把 M4L 的 3×MAD 规则补进预注册；空间折改回 Morton（或明确标注偏离）。
8. 修正 03 §3.2 "≫" 笔误、§3.5 "26–49%" 的范围；补齐 07 manifest 与 FINAL_REPORT 后重封。

---

## 四、总评

**CL2-12 是否该得 PASS / PASS_WITH_FINDINGS / FAIL：FAIL。**

理由：STEP1 交叉覆盖与 STEP3 同 ring 内梯度这两块**描述性工作扎实、边界干净、未越级**（值得肯定）；但本轮的核心统计论断——"M3 训练可估、留出灾难 → 不可泛化"——在**代码逻辑上被 M3 预测漏截距 + 用 M3 分量冒充 M1/M2 所污染**，其数字不能支撑该论断，且该论断又被 05 用作收窄 E3 的依据。加之交付要件（FINAL_REPORT / 07 manifest / completion / 审计回填）整体缺失、EXIT=1。这不是"证据略少"，而是**核心结论的逻辑 FAIL + 交付不完整**，故不给 PASS/PASS_WITH_FINDINGS。若补齐修正重跑且 M3 仍 FAIL，则可重评。

（本轮所有 PASS/FAIL 均为对**已落盘文件的逻辑/自洽性**裁定；任何需要执行的数值与 SHA 一律 UNKNOWN，审计员未虚构执行。）

AUDIT_COMPLETE
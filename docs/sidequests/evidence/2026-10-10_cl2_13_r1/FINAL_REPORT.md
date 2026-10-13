# CL2-13 最终报告 — CL2-12 修正版独立复算 + E3 前登记设计

2026-10-10 Asia/Shanghai。Claude（Kimi K3）主控；OpenCode CLI 1.18.35 `opencode-go/deepseek-v4.1-flash` 独立
复算审计（read+bash 受限）。**本轮未改 121647 TLS 算法/门控/生产代码/GT/CL2-10/11/12 封号字节**；唯一验收表
[00_SCOPE_AND_ACCEPTANCE.md](00_SCOPE_AND_ACCEPTANCE.md) v1（SHA 见 [07](07_EVIDENCE_MANIFEST.json)）。

> **审计驱动的修正（诚实披露）**：**F-AUTHOR-1**（CL2-12 修正版 `design_m3` 基线 cell 撞末位 ring 哑元，
> σ² 系统性高估、截距偏移）经独立审计 **CONFIRMED**；**F-AUTHOR-2**（02 morton-first/03 plain-first
> 基线 cell 不一致）CONFIRMED（示例值订正 (15,-5)→(15,-7)）。CL2-12 封号目录**零写入**；
> 修正数值全部落在本目录。

## 1. 对评审两点技术要求的落实

**R1 概念拆分（评审驳回重命名、采纳拆层）**：CL2-12 的 `STATISTICAL_IDENTIFIABILITY = FAIL` 标签保持，
含义按评审口径拆成三层——(a) **观测域内参数可估计**（rank 充分 53/53、cond 28–38、β 符号跨尺度一致、
M3 σ² 降 ≥20% 于 ROI2 全 3 尺度）；(b) **空间外推泛化失败**（Morton 5-fold，M3 稳定多倍劣于 M1；
**F-AUTHOR-1 修掉后仍成立**——审计员独立用 correct-design 跑空间 CV，"M3 仍 1.2–4.9× 劣于 M1 全 12 组"）；
(c) **物理因果归属仍 UNKNOWN**（β/h 命名仍未获 E3 锚）。**禁止**把"参数可估计"当成"空间可外推"，
也禁止反向。本轮概念拆分已冻结于 [00](00_SCOPE_AND_ACCEPTANCE.md) 的 R1 段。

**R2 第二轮独立复算（评审点名的"修正版本独立复算"的真证据缺口）**：本轮审计员升级为 read+受限 bash，
**亲自执行** `python 03_verify_minimal.py`（作者单文件复算通道，~1 分钟）、亲自 `sha256sum` 全量 CL2-12
manifest、亲自读 CL2-12 `02_identifiability.py` / `03_within_ring.py` 列构造——**不再只凭代码阅读**。
复算范围与判定见 §2。

## 2. 五项复核目标的独立复算结果

| 评审目标 | 作者复算 | 审计员独立复核 | 综合判定 |
|---|---|---|---|
| **冻结回归** | RMS 27.417988 mm、P95 50.291869360 mm，差 4.1e-10/1.9e-13 <1e-9 | 亲跑 03 §2，**一致 PASS** | **VERIFIED** |
| **manifest** | CL2-12 28/28 SHA | 审计员 `sha256sum *` 全量 28/28 一致 | **VERIFIED** |
| **截距** | M3 留出 pred 含截距（结构修正） | 读 CL2-12 02 L287-288 / 03 L108-109 + 03 复算数值佐证（bugged -174 vs 正确 -146）| **VERIFIED**（结构修正成立；上轮 finding #1 已纠正） |
| **M1/M2 独立拟合** | 全 12 组留出 RMSE <1e-6 | 读 CL2-12 02 L254-258 独立 lstsq；03 §4 复算 M1=17.58 / M2=16.21 | **VERIFIED**（上轮 finding #2 已纠正） |
| **空间 CV** | 全 12 组 × 4 模型 <1e-6 | 03 §5 复算 M1=18.22 M3=111.62 一致；审计员另用 correct-design 复算全组 M3 仍 1.2–4.9× 劣 M1 | **VERIFIED**（忠实于其 bug 设计；方向在修正设计下也保持） |
| **M3 参数化等价门（00 设）** | sum-to-zero 投 CL2-12 span 残差 **13.33**（MISMATCH） | 审计员读 `02_RECOMPUTE_RESULTS.json` 确认 | **MISMATCH**——00 设这门专为抓 F-AUTHOR-1，抓到 |

## 3. 新发现 F-AUTHOR-1 / F-AUTHOR-2 与 6 项 audit finding 处置

按 §6_INDEPENDENT_REVIEW 的逐条裁决，**ADOPT 全部实质 finding**，并落进可执行脚本（`03_verify_minimal.py` §7）：

| # | finding（审计员 §3） | 裁决 | 落点 |
|---|---|---|---|
| 1 | 02 `design_m3_db` 名实不符（"corrected CL2-12" 指 bug 版） | **ADOPT** | 02 头注释已改；02_ANALYSIS §2.2 名实披露段 |
| 2 | 冻结回归 diff 叙述错 1–4 个量级（1.05e-11 → 实测 4.093e-10） | **ADOPT** | 02 §2.0 表格已订正；门 <1e-9 仍 PASS |
| 3 | F-AUTHOR-2 plain-first cell = (15,-7) 非 (15,-5) | **ADOPT** | 02 §2.1 已订正 |
| 4 | "投正确空间 5.5e-12 / 正确 M3=10.99 / 正确 σ² 表" 不落脚本 → UNKNOWN | **ADOPT** | `03_verify_minimal.py` §7 实测 **5.542e-12** / **10.99 mm** / 12 组 σ² 已放 02_RECOMPUTE_ANALYSIS §2.1 |
| 5 | **CL2-12 内部不一致**：04/FINAL 写"8/12 FAIL"，JSON 实为 **3 PASS/9 FAIL** | **ADOPT** | 本报告 + return 如实登记；封号目录不动 |
| 6 | A 包总标签应为 `VERIFIED_with_one_failed_design_gate` | **ADOPT** | 02 §2.0/§2.3 已改标签；不再笼统 VERIFIED |

**F-AUTHOR-1 的物理影响**：CL2-12 的 M3 σ²（ROI2/w0.05 142.56 → 正确 119.71 µm²）与截距（−174 → −146 mm）
**不可作为精确值引用**；但**所有预注册门执行方向保持**（σ² 降 ≥20%、x1.05、M3 空间 CV ≫ M1 全组），
且正确设计下 corr(β, ring)=**0.9979**、corr(h, cell_dx)=**−0.9794**（比 bug 版更强）——**CL2-12 的六项
裁定方向全部保持**（4 项加"exact-value caveat"脚注，2 项纯保持）。

## 4. B 包：E3 前登记设计（不执行）

[05_E3_PREREGISTRATION_DESIGN.md](05_E3_PREREGISTRATION_DESIGN.md)：四要素齐全（输入清单 / 精度预算 /
穷尽判别矩阵 / 停止条件 S1–S7 含触发后文档动作）。**E3-1 先于 E3-2**，冻结确认后启动 E3-2；包 B 维持
CL2-12 05 的条件触发降级。**显式 UNKNOWN 格齐备**（中间带 g_resid 3..45mm、形状不对齐、场景冻结失败、
仪器自校 FAIL、点-面对应>2cm、基准不共面 1..2mm、录入照片不符）。评审"定义不同观测结果分别支持/排除
什么假设以及什么结果只能维持 UNKNOWN"的硬性要求**已落地为表格**。

## 5. 逐 ID 验收

| ID | 裁定 | 证据与限制 |
|---|---|---|
| I130 | PASS | 00 先于执行（mtime 13:07 vs 首脚本 13:11）；R1 拆层/R2 范围预注册 |
| I131 | PASS（带 findings，审计 §5 记录） | 02 + 03 落盘；五项目标全算；findings 已 ADOPT 并入脚本 |
| I132 | PASS | 真实 CLI、亲跑 `python 03_verify_minimal.py` ×2、`sha256sum *` 全量、数值比对与找差异全有；审计员 UNKNOWN 保留清单照登 |
| I133 | PASS（带 1 条非阻塞脚注） | 05 判别矩阵穷尽、S6/UNKNOWN 行轻微语义重叠已提示统一 |
| I134 | PASS | 07 manifest 由 `cl2_13_seal.py` 生成后补齐；CL2-12 manifest 28/28 独立复核一致 |
| T1301 | BLOCKED（门控全冷） | 121647 TLS / 生产算法 / B2B3 / E3 执行全 BLOCKED；00 冻结 |
| T1302 | PASS | HEAD 347a5bf 无 commit/push；CL2-10/11/12 目录 mtime ≤12:5x **本轮零写入**；无部署/设备操作 |

## 6. 最终裁定（各自独立，单一标签）

| 裁定 | 状态 | 依据 |
|---|---|---|
| **CL2_12_CORRECTED_NUMERICS** | **VERIFIED_with_one_failed_design_gate** | §2（4/5 VERIFIED、1/5 MISMATCH 按 00 字面门）。**该 MISMATCH 正是 00 设计来抓 F-AUTHOR-1 的** |
| **CL2_12_CORRECTED_LOGIC** | **SOUND_WITH_TWO_CARRIED_FINDINGS** | F-AUTHOR-1/F-AUTHOR-2 CONFIRMED；CL2-12 的 M3 σ²/cell_h/beta/intercept 不可作为精确值，02/03 的 M3 不可互引；六项裁定方向保持 |
| **E3_PREREGISTRATION** | **PREPARED** | §4，判别矩阵穷尽、UNKNOWN 格齐备 |
| **READY_FOR_E3_EXECUTION** | **NO**（预注册恒 NO） | 评审未授权；本设计只供下一次授权使用 |
| **READY_FOR_ALGORITHM_REPAIR** | **NO** | 修 bug 救不了空间外推（correct-design 下 confound 更强），系数仍 UNKNOWN |

## 7. 边界与不变量（再次确认）

- 50 mm P95 / 支持率 0.8 / RMS 30 mm 等原门全部原值未动；未导出任何"有效 TLS"；未生成任何 TLS 候选。
- **未改 CL2-10/11/12 封号目录一字节**（独立 `sha256sum` 全量复核 28/28 一致；mtime 无变化）。
- 未 commit/push/部署/接入生产；未触及 B2/B3；未连板；未采集；E3 未执行、未申请设备使用授权。
- **attempt-1 审计会话原始 IO 被我截断销毁**——不可恢复。教训与运行纪律已写入 06 §6.1。
  attempt-2 是干净独立的会话重新做的完整审计；评审时若质疑其独立性，注意 attempt-1 的内容**从未**被
  attempt-2 读到——它从 0 读 6 份文件开始。
- "CL2-13 PASS_WITH_FINDINGS" 只是本轮调查工作验收，**不是** 121647 有效 TLS 解锁、生产接入条件、
  B2/B3 授权或 E3 执行授权。最诚实的结果 = 4 项 VERIFIED + 1 项 MISMATCH + 2 项 CONFIRMED findings，
  而非任何"全过"。

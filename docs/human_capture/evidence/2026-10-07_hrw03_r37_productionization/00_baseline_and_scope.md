# 00 · HR-W03 R3.7 基线与范围（Cross-Session Registration Productionization Design）

- 日期：2026-10-07（Asia/Shanghai）；writer：OpenCode（DeepSeek v4.1 Flash，本会话）。
- ponytail 使用路径：已加载（full，`C:\Users\30680\.config\opencode\skills\ponytail\SKILL.md`）；实施路径 = 阶梯 rung 2（复用本仓既有 artifact/identity/SHA 绑定/leveling 选择回调等全部既有约定；零新框架、零新依赖、本目录只写 Markdown）。
- 性质：**设计阶段（design-only）**。不修改任何 production 文件；不调 matcher；不重估 ICP/registration；不改变 production detection output；不采集/部署/commit/联网。
- 轮次说明：W03 工作轮次证据目录使用 `rN` 计数（r1…r9）；本目录对应 **阶段 R3.7**（用户 2026-10-07 计划书编号），命名 `2026-10-07_hrw03_r37_productionization`。

## 1. 授权与边界（本轮唯一依据）

用户 2026-10-07 明确指令：把 R3.6 已证明有效的 **B 级跨 session registration** 变成一条安全、可审计、可回退的生产能力；立即执行 **R3.7**（只设计，不改 production），并要求交付 `00_baseline_and_scope.md`～`07_r37_summary.md`。

本轮硬边界（用户原文要求，逐条）：

1. **不得重新优化 registration、不得修改 matcher、不得改变 production detection output**；
2. R3.7–R3.9 期间**禁止顺手调 matcher**（radius/voxel/背景 tier/聚类门/人体检测器全部冻结）；
3. R3.7 只做：设计、审计、（必要时）shadow prototype 规格；产出为文档，不产出 production 代码；
4. 生产接入（R3.9）仅在 R3.8 PASS 后由后续明确授权开启；`W03_R3_ACCEPTANCE.md` 的 production NOT AUTHORIZED 状态不变。

## 2. 已冻结前置（本轮不重开、不重新证明）

| 来源 | 冻结结论 | 证据 |
|---|---|---|
| R3.6（W03-R3.6 Registration Causality） | B（固定 ICP，cur→ref）消解 `REG_GAP` 的 **98.8%**；WD02 静态 residual 相对 **−88.9%**（B）/ **−89.9%**（C 上限）；逐点迁移矩阵证明是真实 causal recovery，非分类假象；registration 修复后剩余 10,581 点（6.6%）不再是 registration 形状：**77.7% matcher geometry + 13.3% missing + 9.0% sparse** | `../2026-10-06_hrw03_r8/06_summary.md`、`05_frame_analysis.md`（digest `23830ede…`） |
| R3.6 方向约定 | 所有条件统一 **current → reference**；A=无跨会话变换（生产现状），B=R3.2 固定 ICP，C=静态结构 point-to-plane 主解，C_ALT=tls 初值第二盆地 | `../2026-10-06_hrw03_r8/02_experiment_design.md` §2 |
| R3.6 已知限制 | roll↔yaw/pitch 弱可观测 → C 非唯一全局最优；第二盆地与主解目标值差 ~7%（中位） | `../2026-10-06_hrw03_r8/05_frame_analysis.md` §5 |
| E-1 | mobility / temporal filter 假设 **E-NOT-CONFIRMED**，已冻结关闭 | `../2026-10-06_hrw03_r8_e1/08_final_attribution.md` |
| R9（旁路归因） | 站点 NO_REF_VOXEL 的丢失层 = 空间对应/体素量化（C2+C3=97.6%；C0=0；C1=2.4% 且全部 occ<0.45）；**NO PRODUCTION CHANGE**；builder 阈值不动；下一步指向 matcher 空间容差（须另行立工单） | `../2026-10-06_hrw03_r9_ref_coverage/09_final_attribution.md`（digest `ef6e1c2c…`） |
| W03-R3 验收规范 | 口径：console leveled pipeline 为唯一权威；reference 融合语义 `background = reference_static OR online_static`；R3.2/R3.3 未过 audit 不接 production | `../../W03_R3_ACCEPTANCE.md` §0/§3 |

**R3.7 只回答一个问题**：已证明有效的跨会话 transform，以什么形式进入生产链，才能保证「错误的 registration 不会静默进入、并且不会比不 registration 更危险」。

## 3. 本轮基线（2026-10-07 实测）

- git：branch `master`，HEAD `cfbb80c57508be1a0435fdb92260f698dc763934`；工作树仅含未跟踪的 `docs/human_capture/evidence/2026-10-06_hrw03_{r7,r8,r8_e1,r9_ref_coverage}/`；本轮不 commit。
- 生产代码 SHA256（raw，逐位复核，与 r8 provenance 一致）：
  - `pc_apps/human_replay/human_pipe_lib.js` = `f580778c…`（matcher/builder/管线纯函数，本轮零改动）；
  - `pc_apps/human_replay/leveling.py` = `3c3a8819…`；`leveling_quality.py` = `4cbafd0c…`；
  - `pc_apps/human_replay/human_replay_lib.js` = `bbcbc547…`；`human_detect.js` = `45d13055…`；`human_detect.html` = `9d89589d…`。
- 冻结会话（本轮重新哈希，与 r8/r9 逐位一致）：
  - current `cap_20261002_223757`：meta `71915d51…`，bin `8afb660b…`（165 帧）；
  - reference `cap_20261004_203349`：meta `c3b55d1e…`，bin `2ed3fc60…`（102 帧）。
- 冻结 leveling artifacts（本轮重新哈希，与 r8/r9 一致）：
  - current job `6bc5aabf…`（transform_id `de973fdb…`）：`tls/transform.json` `7f1cd4f7…`、`report.json` `5b8854eb…`、`manifest.json` `6a86d536…`；
  - reference job `c9712acad…`（transform_id `5d8fd5c0…`）：`tls/transform.json` `c8459292…`、`report.json` `e7455741…`、`manifest.json` `4fb6ae20…`。
- 关键 R3.6 冻结常量（可复算，见 01/03）：B 归档 ref→cur euler ZYX `(1.7476, −0.2818, −2.3924)`、t `[0.0182, 0.031, 0.0012]`；C `(−2.3102, 0.0813, 2.2269)` / t `(−0.0064, −0.0288, −0.0099)`；C_ALT `(−2.3373, 0.5931, 2.2435)` / t `(−0.0203, −0.0298, 0.0056)`。

## 4. 交付物索引

| 文件 | 内容 | 下游用途 |
|---|---|---|
| `00_baseline_and_scope.md` | 本文件：授权、边界、基线、冻结前置 | 全轮引用基准 |
| `01_coordinate_contract.md` | 坐标系与方向契约（RAW→LEVELED→REFERENCE→FOREGROUND） | R3.8/R3.9 一切实现与日志的唯一语义 |
| `02_registration_artifact_spec.md` | 不可变 artifact 的目录/文件/schema/校验/失效规则 | R3.8 artifact writer 与 loader 的实现契约 |
| `03_confidence_gate_design.md` | confidence gate：指标族 A–D、阈值推导、三档映射、聚合规则 | R3.8 gate 实现与判定；`reg_gate_v1` 常量来源 |
| `04_failure_and_fallback_matrix.md` | 状态机、失败矩阵、fallback、重复变换防护、日志契约 | R3.8/R3.9 的 fail-closed 行为定义 |
| `05_shadow_integration_plan.md` | R3.8 shadow 接入方案：双分支、golden/故障用例、判定门 | R3.8 工单依据 |
| `06_test_matrix.md` | R3.7/R3.8/R3.9 测试矩阵（ID 级） | 各轮验收的证据入口 |
| `07_r37_summary.md` | 本轮结论、未决项、复审移交 | R3.8 开工前置 |

## 5. 明确不做（本轮）

- 不写任何 production/测试代码；不改 `human_pipe_lib.js` 及任何 `PIPE` 常量；不重跑 ICP/point-to-plane；不改变 0.12 m 半径、体素语义、背景 tier、清理逻辑、聚类/人体/Fall 判定。
- 不做新的设备操作、采集、部署、网络变更；不 commit/push。
- 不重开 R3.0–R3.6 / E-1 / R9 的结论；不把 R9 的「spatial/quantization」结论提前解释为 matcher 修改授权。
- 数值阈值只在**设计文档中登记**（含推导与版本号），实现与冻结发生在 R3.8；R3.7 不产生任何被 production 消费的常量。

## 6. 本轮可复核性

- 03 的阈值推导所用历史样本（audited pair 解法族 + 同场候选会话两两 TLS-direct）全部来自既有 `captures/leveled` 只读 artifact，推导脚本不在本仓落盘，方法与输入在 03 中完整登记，可复算。
- 本轮的只读检查（SHA 复核、矩阵共轭/正交性、推导）不构成新实验；R3.6/R9 的 digest 未被重算、未被覆盖。

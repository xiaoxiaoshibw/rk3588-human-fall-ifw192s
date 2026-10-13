# 06 · W03-R3.6 总结（Registration Causality / Shared-Frame Validation）

- 日期：2026-10-06；writer：OpenCode（DeepSeek v4.1 Flash）；ponytail full（r7 同源代码逐行复用 + 预研证明的 point-to-plane C；零新依赖、单工具、无框架）。
- 状态：**实验完成，19/19 自检全 PASS；production 零改动；无 commit/采集/部署/联网。**
- 一句话结论：**在高置信静态结构对齐（B=固定 ICP，C=独立 point-to-plane oracle-like）下，WD02 的 registration 残漏系统性消解（相对 −88.9% / −89.9%）；逐点迁移证明该消解是真实的 causal recovery（非 classifier 假象）；registration 因果判定 = SUPPORTED，且 registration 修复的理论上限已在本数据上探到（B 后仅剩 +0.66 pp 级别余量）。**

## 1. 核心数字（点级）

| 口径 | A（生产现状=none） | B（固定 ICP） | C（oracle-like 主解） | C_ALT（第二盆地） |
|---|---:|---:|---:|---:|
| WD02 residual | 104,742 | 11,625 | **10,581** | 14,722 |
| WD02 相对下降 | — | **−88.9%** | **−89.9%** | −85.9% |
| WD02 Registration 口径（R3.5 bucket） | — | 96,811（60.8%） | 96,851（60.8%） | 95,434（59.9%） |
| WD02 residual 成分（点级 share） | — | geometry 75.6% / missing 9.6% / sparse 14.8% | **geometry 77.7% / missing 13.3% / sparse 9.0%** | geometry 81.9% / missing 9.8% / sparse 8.3% |
| WD01 residual | 14,966 | 1,875 | 1,932 | 1,920 |
| WD01 相对下降 | — | −87.5% | −87.1% | −87.2% |
| ALL residual | 518,541 | 397,828 | 395,773 | 400,396 |
| Voxel 残余（WD02） | 89,849 | 10,966 | 10,037 | — |

- 迁移证据（WD02）：A 的 registration gap = 96,851 → B 吸收 95,709（**98.8%**）→ C 吸收其余 1,142（100%）；A 的 53,799 个 geometry 标签点中绝大多数实为错位 shell，B/C 后真几何仅剩 8,222。
- 人体安全（f55/155/160 高带 z≥1.2）：C−B = +2/+7/+3 点（+0.16/+0.50/+0.63 pp，全部 ≤ +1.0 pp 门）；clean controls 全程 0–1 点；NON_STATIC proxy C−B = +60（+0.50 pp）。
- Registration QA：normal-residual p50（静态细点）：A 38.8 mm → TLS 29.9 → B 14.5 → **C 11.0 mm**；C held-out（even→odd）11.1 mm。

## 2. 预注册判据逐条（02_experiment_design.md §6；对 C 与 C_ALT 同时成立）

| # | 判据 | C 主解 | C_ALT | 判定 |
|---|---|---|---|---|
| S1 | WD02 residual ≤ 0.5×A（A→B 与 A→C） | 10.1% / 11.1% of A | 14.1% / 11.1% | **PASS** |
| S2 | REG_GAP_A 被 B 覆盖 ≥ 80% | 95,709/96,851 = **98.8%** | 同 B | **PASS** |
| S3 | WD02 MATCHER_GEOMETRY 计数 C ≤ A（matcher 无需改变） | 8,222 ≤ 53,799 | 12,060 ≤ 53,799 | **PASS** |
| S4 | WD02 REFERENCE_MISSING 不爆炸（C ≤ 1.1×A） | 1,409 ≤ 13,733 | 1,443 | **PASS** |
| S5 | clean controls 吸收率 ≤ 1% 且 C−B ≤ +0.5 pp | 0.09%，+1 点 | +1 点 | **PASS** |
| S6 | f55/f155/f160 高带 C−B ≤ +1.0 pp；NON_STATIC C−B ≤ +1.0 pp | +0.16/+0.50/+0.63 pp；+0.50 pp | +0.16/+0.43/+0.63 pp；+0.67 pp | **PASS** |
| S7 | 改善点空间分布与原 registration failure 吻合（描述性） | recover 点 d_A p50=0.175 m（shell）、对齐位移 p50=0.119 m、方位分布与 WD02 全体一致 | 同型 | **PASS** |

**因果判定（Causality verdict）：`SUPPORTED`**
—— registration 是 WD02 当前静态 residual 的**主要因果因素**：独立于 R3.5 工具的第二套固定解（B）消解 98.8% 的 registration gap；独立构造的静态结构 oracle（C）收敛到同一量级并确认再无隐藏大头；改善没有转成 geometry/missing，也没有来自人体误吸收。
**敏感性**：第二盆地 C_ALT 同样过全部判据（程度略低），结论不随盆地选择翻转；但 C 并非数学唯一全局最优（roll↔yaw/pitch 弱可观测，两盆地目标值差 ~7%），登记为该实验的已知限制。

## 3. "Registration 修复理论上最多能解决多少"（本轮核心问题的定量回答）

- **WD02：上限 ≈ 相对 −90%**（104,742 → ~10.6k 点；B 已拿到 −88.9%，oracle 只再多 +0.66 pp）。剩余 10,581 点（6.6%）**不再是 registration 形状**：77.7% matcher geometry（d≥0.12 的 shell/稀疏面）、13.3% missing、9.0% sparse。
- **WD01：上限 ≈ −87%**（14,966 → ~1.9k；B 与 C 并列，C 未超过 B）。
- **ALL：A→B/C 相对 −23.3%/−23.7%**（ALL 含 clean 帧人体，应然保留，不作上限口径）。
- 结论：registration 值得修（收益巨大且确定），但 **registration 修完后的下一瓶颈是 matcher geometry / reference 覆盖的"壳层"，不是又一层 registration**。matcher 扩张仍须独立工单（R3.5 §GQ4 的人体边界风险不变）。

## 4. 建议的生产方向（**仅建议；本轮不实现**）

（按证据排序；任何一条落到 production 都需用户另行授权）

1. **session-to-session registration 成为独立、显式的一步**（若/当 reference 融合被授权）：固定/校验外参（若有条件标定）或"每会话一次场景配准"；本数据显示 B 级别（体素级 ICP）即可吃到 ~99% 的 gap，不需要在线持续 ICP。
2. **registration confidence gate**：仅当场景配准在静态结构上收敛且 holdout 质量达标时启用；弱可观测（盆地分歧）时拒绝使用而不是硬套（本轮 C/C_ALT 盆地差异即案例）。
3. **registration cache / immutable artifact**：把会话间 transform 像 leveling 一样做一次、SHA 绑定、只读复用（`captures/leveled` 模式扩展），避免每次 runtime 重算。
4. **reference coordinate normalization**：在 reference artifact 构建阶段就把 reference 归一到与 current 可用同一坐标系（生成物携带 transform + source SHA），供 fusion 消费。
5. **matcher geometry（shell）另立工单**：WD02 剩余残余的主成分（77.7%）；不得用半径/AABB 扩张直接吃 shell（R3.5 已证明优先吃人体边界）。
6. 任何未来接入都必须保留本轮的人体安全门（f55/155/160 高带 + clean controls）与 WD01/WD02 静态恢复口径。

## 5. 边界与限制（随结论阅读）

- **proxy ≠ GT**：WD01/WD02/站点块/人体带均为 proxy；f10/f30/f55 站点块为可移动状态（R3.5 裁决），不计入 static recovery。
- **C 是 oracle-like / upper-bound estimate / offline high-confidence alignment，不是 GT**；第二个收敛盆地（C_ALT）已作为敏感性并列报告。
- 单一会话对（223757 ↔ 203349）；reference 仍为 10.5 s 候选（正式 20–60 s 空场录制 BLOCKED，待授权）；结论限 PC/Node 离线口径。
- R3.5 的 f10/f30"站点混淆"与 `POST_FILTER_ERROR` 分类问题维持原判，本轮回测未重开。
- 对 f155/f160 高带在 B/C 下 5–9% 的吸收（贴站点块 0.16 m）维持 R3.5 的"已知代价、逐点不可分"登记；C 的增量很小但不为零。
- B 的损失（A 已吸收、B 丢失）WD02 = 3,694 点；C 把它压到 2,690（丢失），说明任何单一 transform 都不是逐点最优；生产化需要 confidence gate + 可能的多解检查。

## 6. 确定性 / 输入保持

- run1 digest = run2 digest = `23830edefcb28f04774e328af64abce014dfeff35df75462f8a6f68d68eb3357`。
- `04_point_attribution.csv` SHA256 = `d0ac5be979e7782655d0d64257c00e7c83491f08ef359fd77ec01bd4b096dc62`（两次 byte-identical）；`04b_voxel_transitions.csv` = `de6c2503fa4c5c2f14feb159046d36c87d01dabd819ead28bb9527bb46b37049`（同）。
- `inputs_unchanged`（11 项 SHA=前 3 JS + 2 会话×2 + 2 transform + 2 report）与 `production_mtime_unchanged` 均 PASS；`r35_baseline_reproduction` PASS（r7 `02_attribution_results.json` 全帧全组逐整数一致）。
- 日志编码备注：`11/12_run1/2_stdout.log` 经 PowerShell Tee 捕获（个别 Unicode 字形受控制台编码影响）；权威 UTF-8 运行日志为 `13_tool_run.log`。

## 7. 产物清单

`00_provenance.md` / `01_registration_chain_audit.md` / `02_experiment_design.md` / `03_results.json`（digest `23830ede…`）/ `04_point_attribution.csv` / `04b_voxel_transitions.csv` / `05_frame_analysis.md` / `06_summary.md`（本文件）/ `10_r36_registration.js` / `11_run1_stdout.log` / `12_run2_stdout.log` / `13_tool_run.log` / 预研 `_recon_c_probe.js|log`、`_recon_c2_probe.js|log` / 分析 `_r36_analyze.js|log`。

**Production modified? NO。**

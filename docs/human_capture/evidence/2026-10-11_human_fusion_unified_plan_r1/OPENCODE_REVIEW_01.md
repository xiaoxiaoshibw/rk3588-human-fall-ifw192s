I'll start by reading the authoritative workflow docs and locating the summary documents that define current development progress.

Let me read the HC/HR entry point and search for summary/unification documents.

Found the target: `HUMAN_FUSION_UNIFIED_PLAN.md` and its acceptance table. Let me read the core planning documents and evidence.

Now let me read the three rounds of design evidence and check the referenced source/JSON claims.

Now I need to independently verify the claims against actual source and JSON. Let me read the submission evidence and locate the referenced sources.

The submission references many source/JSON files. Let me verify them directly, starting with the diagnosis evidence and prior probe/review logs.

The report is substantial. Let me read the rest and the key reference JSONs/summaries.

Let me inspect the prior review log and verify the load-bearing source claims.

This is my live session log. Let me continue verifying the remaining load-bearing source claims.

Source claims for V2/V3 confirmed. Now verifying the engine union/tracking claims and PointNet preprocessing.

Let me verify the production engine merge path, the PointNet eval file existence, and the training centering.

Core source claims check out. Now verifying the remaining JSON evidence (f128 cluster, BG point rates, baseline).

# HUMAN-FUSION-UNIFIED-PLAN 独立只读规划审核报告（R1）

审核者：OpenCode 只读规划审查者（`opencode-go/deepseek-v4.1-flash` / defaultDB）。
ponytail 实际读取路径：`C:/Users/30680/.codex/skills/ponytail/SKILL.md`。
已读入口：`AGENTS.md`、`docs/human_capture/README.md` 当前第一节、`docs/human_fall/WORKFLOW.md` 顶部与通用流程；审核冻结件：`PLAN_SUBMITTED_01.md`、`ACCEPTANCE_SUBMITTED_01.md`、`SUBMISSION_01.json`、`SOURCE_CHECK_01.json`、`ROUND_01/02/03`、`tickets/HUMAN-FUSION-UNIFIED-PLAN.md`、`returns/HUMAN-FUSION-UNIFIED-PLAN.md`。
核证来源（实际读源码/JSON，非仅采信作者总结）：诊断 `REPORT.md` §3/5/6/12、`late_review.json`、`historical_v2_recalculation.json`、`CC 03_SUMMARY.md`、`V3 REPORT_FINAL` 相关、`CANDIDATE_IMPROVE_S6.json`；源码 `v2_runtime.js`、`unique_tracker.js`、`detector.js`、`human_fusion_lab/core/engine.js`、`human_fusion_lab_v3/v3_runtime.js`、`core/bg_groups.js`、`train.py`、`tools/eval_controlled_comparison.py`、`pc_apps/human_core/engine.js`。
本轮**未执行任何算法/浏览器/训练**，仅只读核对；规划通过不等于算法或生产 ACCEPTED。

## 一、逐 ID 裁定

| ID | 裁定 | 依据（本轮实核） |
|---|---|---|
| P01 授权/边界/入口 | **PASS** | 计划 §1 明确仅规划/审核、后续全 NOT_RUN、HFUS-Dxx 属 HC/HR 研究支线非 HF/GL 里程碑；与 `README.md` 当前第一节授权一致，未扩大到实现/采集/部署/ML/生产 |
| P02 基线/漂移 | **NOT_RUN** | `BASELINE_BEFORE.json` 实存：`branch master`、`head 026e0630…`、dirty 树含 M/?? 均记录；含 untracked/ignored。末轮对账仍待审后，按验收允许 NOT_RUN；未发现越界写入 |
| P03 三总结冲突归一 | **PASS** | 六项归一均与源码/JSON 对齐（见二） |
| P04 目标架构 | **PASS** | §3 共同背景入口、PA/PB、actual union、模型契约、dual tracker/retention 迁移、GT 只事后评价齐备；与源码结构一致 |
| P05 评测契约 | **PASS** | §4 GT 资格/UNKNOWN/传播相关性、无候选 FN、classifier 前 proposal、partial unmatched 非 FP、legacy/strict 重算、ID/时间/性能契约明确 |
| P06 顺序/依赖/阶段门 | **PASS** | §5/§5.1/§5.2 工程门与算法门分离，D03 FAIL 不阻 D04/D05，D06 联合计分；无循环依赖 |
| P07 三轮设计记录 | **PASS** | ROUND_01 事实→02 架构→03 反例逐轮可追；`SUBMISSION_01.json` 冻结 5 文件 SHA |
| P08 实际调用 OpenCode | **NOT_RUN** | 本次即指定 Go Flash 只读审核（进行中）；详见三·P3-1 |
| P09 意见处理/复审 | **NOT_RUN** | 处理与复审须在本次意见回填后进行 |
| DEV01 | **PASS** | 全表未宣称任何 D01–D07 已实施 |
| DEV02 | **BLOCKED** | 人工身份/独立负例/真关节/新场景证据仍缺（诊断 §3.2 无有效负例、S9 SHA 失配） |
| D01 | **NOT_RUN** | 无设备/采集/部署执行 |
| PHY01 | **BLOCKED** | 无新物理/现场/生产资格 |

## 二、归一事实本轮的独立核验（全部成立）

- **V2 Unique 非重复建设**：`v2_runtime.js:16-20` 在 `_tick_fusion` 前强制 `instanceof UniqueTracker`，覆盖 tick/segment reset；`unique_tracker.js:5-6` 排序边贪心一对一、每轨每帧一票。计划“不重做、默认入口迁移另单”正确。
- **V3-B 仅切 mask、未接全链**：`v3_runtime.js:40-45` 先 `super.frame()` 出 V2 检测，A/B/C 只产 mask 且 `active:'B'`；`bg_groups.js` A/B 与生产 ref_only 与 `extract_foreground_fused` 1:1。计划“B 背景点级收益不做检测全链通过”正确。
- **f128 已入混簇**：`CANDIDATE_IMPROVE_S6.json` f128 `raw33 / kept_after_bg15 / covered_by_clusters15 / orphan0 / production_cluster_n[191,374]`，与计划“B-f128 15 点已进大簇、不能套 15<60 单因果”一致。
- **PointNet 漏中心化**：`train.py:55` 有 `cloud-=cloud.mean(...)`；`eval_controlled_comparison.py:90` 只 `.T` 未中心化 → 复现 test58/65、stress39/58。计划“修评测消费者、不据旧表淘汰模型”正确。
- **生产 union 缺口**：lab `core/engine.js:447-455` 写回 `point_indices/point_count/bbox/scoring_centroid`；生产 `pc_apps/human_core/engine.js:419-476` 合并后**无**该段（且 FUSION 仅跑 RF51）。计划“主链同步另单”正确。
- **GT 分母**：`late_review.json` near `person_raw 286822`（A 0.1215/B 0.0458）、S1 家具 `7220011 / A 174472 / B 171958`，与 §2.2 一致，V3 正文 31335/5062 分母不沿用正确。
- 其余（votes=0、geometry mismatch=0、骨架 proxy≠关节、ROS fall_state≠零实现）均与 CC/诊断一致，计划未继承被推翻结论。

## 三、可复现问题（均非阻断）

- **P2-1（数值可读性）**：`HUMAN_FUSION_UNIFIED_PLAN.md:46-52` §2.1 只列 S1/S3near/S3far/S6 四行，其“已标 PERSON 观察”和为 428、候选和为 422/117/6；而合计行写 `510 | 504/127/6`（含被省略的 S4/S5/S7/S8，诊断 §6.1 正确）。聚合无法由所显行推出。建议补全 S4/S5/S7/S8 行或标注“合计含全部 7 会话”。
- **P2-2（命名冲突）**：验收表第 5 行明示“P01 为规划 ID，PHY01 才是物理限制”；但计划 `HUMAN_FUSION_UNIFIED_PLAN.md:38` 与 `:212` 用 “P01” 指物理/生产（`D01 设备 NOT_RUN、P01 物理/生产 BLOCKED`），与其自定命名规则冲突。建议统一改为 PHY01。
- **P3-1（P08 证据待澄清）**：`OPENCODE_PROBE_01_status.json` 记 `readonly_permissions: false`、exit0/14.045s/session `ses_ed55943abffeg…`；与计划 §7“拒绝 edit/write/bash/task/网络”的只读契约表述不完全一致。建议在 P08 记录中澄清该字段含义或补只读权限证据。
- **P3-2（证据文件内部不一致）**：`SOURCE_CHECK_01.json` `totals`=504/127/6（对），但其 `xgb_rows` 仅 4 会话、和为 422/117/6。数值源自诊断全量集，但文件自洽性不足，建议注明。
- **P3-3（术语）**：计划 §3.5 “PIPE tracker 管 retention”措辞不精确——FUSION 模式 retention 来自引擎 retention bank，`pipe_ctx.tracker` 主要服务 pipechain；建议明确，避免误导后续 D05b。

## 四、裁定

未触发任何 FAIL/BLOCKED 判定；三项归一核心（B 非全链、f128 混簇、PointNet 中心化、unique 已在 V2、GT 分母、proxy 范围）均有本轮源码/JSON 实证。问题均为 P2/P3 文档一致性/命名/证据元数据，可在下一版轻量修订，不改判本计划结构。

**规划裁定：READY（建议随下版并入 P2/P3 修订）**。
DEV01 PASS、D01 NOT_RUN、DEV02/PHY01 BLOCKED 保持；OpenCode 通过仅证明本次只读读审，不宣称系统 ACCEPTED。

REVIEW_COMPLETE
# HUMAN-FUSION-UNIFIED-PLAN 独立只读规划审核报告（R3）

审核者：OpenCode 只读规划审查者（`opencode-go/deepseek-v4.1-flash` / defaultDB；未切 provider/model/DB/auth）。
工具边界：仅 `read`/`glob`/`grep`/list；本轮 `bash`/`task`/edit/write/网络工具调用数 = 0；未改任何文件、未实施算法。
ponytail **实际读取路径**：`C:/Users/30680/.codex/skills/ponytail/SKILL.md`（120 行，本轮真实 read，已解析 ladder/YAGNI/“先理解再最短路径”规则）。
已读入口：`AGENTS.md`、`docs/human_capture/README.md` 顶部当前节、`docs/human_fall/WORKFLOW.md` 当前边界。
冻结件（实读）：`PLAN_SUBMITTED_02.md`、`docs/human_capture/HUMAN_FUSION_UNIFIED_PLAN.md`（逐字一致，219 行）、`ACCEPTANCE_SUBMITTED_02.md`、`docs/human_capture/HUMAN_FUSION_UNIFIED_PLAN_ACCEPTANCE.md`、`SUBMISSION_02.json`、`SOURCE_CHECK_01/02.json`、`ROUND_01/02/03`、`REVIEW_RESPONSE_01.md`、`DISPATCH_INTEGRITY_03/04.md`、`tickets/`、`returns/HUMAN-FUSION-UNIFIED-PLAN.md`、`OPENCODE_REVIEW_01/02.md`、`OPENCODE_PROVENANCE_01.json`、`OPENCODE_PROBE_04_status.json`。
实核来源（读源码/JSON，非采信摘要）：`v2_runtime.js`、`unique_tracker.js`、`detector.js`、`human_fusion_lab/core/engine.js:285-544`、`pc_apps/human_core/engine.js:418-492`、`human_fusion_lab_v3/v3_runtime.js:1-60`、`human_fusion_lab_v3/core/bg_groups.js`、`human_fusion_lab/train.py:1-70`、`human_fusion_lab_v3/tools/eval_controlled_comparison.py`、`diagnosis/REPORT.md` §3/§5/§6/§12、`diagnosis/late_review.json`。
本轮**未运行任何算法/浏览器/训练**；规划通过不等于算法或生产 ACCEPTED。

## 一、前次两条事实误判的复核结论（本轮实核）

1. **P3-2「SOURCE_CHECK_01 仅 4 会话」——前次判断错误，v2「不采纳」正确。**
   实读 `SOURCE_CHECK_01.json:15-443`：`xgb_rows` 共 **9** 条（175227/175429/175553/175804/175943/180235/180337/180557/180751）。逐行相加 candidate=504/127/6、track=491/112/19，与 `totals` 完全一致。`SOURCE_CHECK_02.json` 每会话一行亦复算等于 totals。前次“4 会话、422/117/6”只能由 read 输出截断解释。

2. **P3-3「PIPE tracker 不影响 FUSION retention」——前次判断错误，v2 更正成立。**
   `human_fusion_lab/core/engine.js:501` 执行 `pipe_ctx.tracker.tick(...)` → `:502` 取 `a_tracks` → `:504-510` 以 FG+confirmed 的 A 候选写入 `self.retention.tracks` bank → 下一帧 `_fusion_a_chain` 在 `:322-336` 读该 bank 把点补回当前 RAW → `:517-523` 由 `fusion_ctx.tracker`（V2 为 Unique）出最终轨迹。即 **PIPE tracker 的 `a_tracks` 确实驱动引擎 retention bank**，是同一 FUSION 内的两个状态来源；v2 §3.5 调用链描述与源码逐行对应。

## 二、逐 ID 裁定

| ID | 裁定 | 本轮实核依据 |
|---|---|---|
| P01 授权/边界/入口 | **PASS** | 计划 §1 明确仅规划/审核、后续全 NOT_RUN、HFUS-Dxx 属 HC/HR 研究支线非 HF/GL 里程碑；与 README 当前节一致，未扩大到实现/采集/部署/ML/生产切换 |
| P02 基线/漂移 | **NOT_RUN** | `BASELINE_BEFORE.json` 实存（master / 026e0630… / 含 untracked+ignored、零漂移）；提交后整树对账与漂移收口未完成，按验收允许 NOT_RUN；未见越界写入 |
| P03 三总结冲突归一 | **PASS** | 六项归一（B mask 非全链、f128 已入混簇、PointNet 中心化、Unique 已在 V2、GT 分母、proxy 范围）与源码/JSON 全部对齐（见三） |
| P04 目标架构 | **PASS** | §3 mermaid 与文字一致：`RET --> PA/PB`（`:92-94`）无 RET→UNION 直连；共同 BG 入口、classifier 前提案、anchor/scoring 分列、GT 只事后评价 |
| P05 评测契约 | **PASS** | §4 GT 资格/UNKNOWN/传播相关性、无候选 FN、classifier 前 proposal、partial unmatched 非 FP、legacy/strict 重算、ID/时间/性能契约齐备 |
| P06 顺序/依赖/阶段门 | **PASS** | §5/§5.1/§5.2 工程门、算法门、晋级门分离；D03 工程接通≠收益，不阻 D04/D05a；D06 才联合计分；无循环依赖 |
| P07 三轮设计记录 | **PASS** | ROUND_01 事实→02 架构→03 反例逐轮可追且各含修订依据；`SUBMISSION_02.json` 冻结 5 文件 SHA |
| P08 实际调用 OpenCode | **NOT_RUN** | 本次即指定 Go Flash 只读审核（进行中）；probe04 exit0/PROBE_OK/actual model 正确；正式审核只读权限与实际工具由编排者回填 |
| P09 意见处理/复审 | **NOT_RUN** | R1 意见已逐项处理（P2-1/P2-2 接受，P3-2/P3-3 不采纳且本轮判为正确）；最终逐 ID 回传收口未完成 |
| DEV01 | **PASS** | 全表未宣称 D01–D07 已实施；`sidequests/human_fusion_lab_next/` 本轮实未创建（glob 无结果） |
| DEV02 | **BLOCKED** | 人工身份/独立负例/真关节/新场景证据仍缺 |
| D01 | **NOT_RUN** | 无设备/采集/部署执行授权 |
| PHY01 | **BLOCKED** | 无新物理/现场/生产资格 |

## 三、v2 归一事实与改动点的独立核验（均成立）

- **V2 Unique 非重复建设**：`v2_runtime.js:16-20` 包裹 `_tick_fusion` 强制 `instanceof UniqueTracker`（覆盖 tick/segment reset）；`unique_tracker.js:5-6` 排序边贪心一对一、每轨每帧一票。计划“不重做、默认入口迁移另单”正确。
- **V3-B 仅切 mask、未接全链**：`v3_runtime.js:40-45` 先 `super.frame()` 出 V2 检测，A/B/C 仅产 mask 且 `active:'B'`；`bg_groups.js:41-96` A/B 与生产 ref_only/`extract_foreground_fused` 1:1。计划“B 点级收益不做检测全链通过”正确。
- **f128 已入混簇**：`late_review.json` f128 `covered_by_clusters=15 / orphan=0`，有效簇点数含 191/374，与计划“不能套 15<60 单因果”一致。
- **PointNet 漏中心化**：`train.py:55` 有 `cloud-=cloud.mean(axis=1,keepdims=True)`；`eval_controlled_comparison.py:90` 仅 `.T` 未中心化 → 复现 test58/65、stress39/58；`late_review.json` 中心化后 train139/13/3/553。计划“修评测消费者、不据旧表淘汰模型”正确。
- **生产 union 缺口**：lab `core/engine.js:446-455` 写回 `point_indices/point_count/bbox/scoring_centroid/scoring_pointset_version`；生产 `pc_apps/human_core/engine.js:432-448` 合并后**无**该段。计划“主链同步另单”正确。
- **GT 分母/基线表**：§2.1 现含 8 行，逐行核算 PERSON 和 510、candidate 504/127/6、track 491/112/19 全部吻合，S9 不入合计；§2.2 near286822/far561361/S4 13327/S5 8841/S6 27268/S7 24361/S8 57045 与 `REPORT.md` §12.1 一致；S1 家具 7220011 / A174472 / B171958（差≈0.04pp）一致。
- **PHY01 统一**：计划物理/生产两处（`:40`、`:219`）均用 PHY01，无残留“物理 P01”。
- **B 家具 608→FP595**：与 `late_review.json`、`REPORT.md` §12.2 一致；计划保留为证据压力案例，不唯一归因“记忆”。

## 四、阻断缺陷与非阻断建议

**阻断缺陷：无。**
本轮核验范围内未见可复现的功能/契约/授权越界问题；核心归一与 retention 调用链均有源码/JSON 实证。

**非阻断建议（均为文档/元数据一致性，P3）：**

- **N-1（证据文件键名不一致，P3）**：`SOURCE_CHECK_01.json:15` 用数组键 `xgb_rows`，`SOURCE_CHECK_02.json:3` 用标量 `xgb_rows_count` + `rows`。对账时易再次误读（正是前次误判的诱因之一）。最小修订：`SOURCE_CHECK_02.json` 统一键名或加 `note` 说明两版等价。
- **N-2（§2.1 表头措辞，P3）**：合计行“全部有资格开发切片 510”与 S1 行 PERSON=0 并置，虽已在 §2.2 说明“S1 没有人体”，但表头未点明“510 仅来自 7 个人体会话”。最小修订：表头补一行注“合计 PERSON 不含 S1（无人体）”。
- **N-3（会话标签不统一，P3）**：§2.1 用 `S3near/S3far`，§2.2 用 `near/far`，同一会话两套标签。最小修订：统一标签或加 sid 后缀映射。
- **N-4（P08 元数据观察，非本计划缺陷）**：`OPENCODE_PROVENANCE_01.json` 中 `OPENCODE_REVIEW_01.skill_read_observed:false`（首次未观察到技能 read 事件）。本轮已按要求实际读取并记录路径；仅建议后续回传把该字段与技能读取一并说明，不改判。

以上均属文档一致性，可在下一版轻量并入，不改判本计划结构与标准。

## 五、裁定

两条首审事实误判经本轮源码/JSON 实核确认**作者“不采纳”正确**；v2 已并入 P2-1/P2-2 文档修订，核心归一（B 非全链、f128 混簇、PointNet 中心化、Unique 已在 V2、GT 分母、proxy 范围）与 retention 调用链、PHY01 命名、基线表补全、图修正（RET→PA/PB）均有实证。无阻断 FAIL/BLOCKED。

**规划裁定：READY**（建议随下版并入 N-1～N-4 文案/元数据修订）。
DEV01 PASS、D01 NOT_RUN、DEV02/PHY01 BLOCKED 保持；本次通过仅证明只读规划读审，**不等于人体算法可靠或系统 ACCEPTED**，不启动 HFUS-D01～D07 实施、不部署/采集/提交推送/改网络驱动/激活 ML。

REVIEW_COMPLETE
I'll conduct this read-only review. Let me start by reading the mandated entry-point documents and the delivery artifacts.

Let me read the core delivery artifacts and list the evidence directory.

# HF-MAINLINE-POINTS-01 只读独立审核结论

审核身份：opencode（agent=plan），模型 `opencode-go/deepseek-v4.1-flash`，只读；未运行命令/测试/服务、未写文件、未读 points.bin 原录制、未调用子代理。结论由调用者原样落盘。

## 实际读取清单（本轮实际打开的文件）

技能/入口：
- `C:/Users/30680/.codex/skills/ponytail/SKILL.md`（已读）
- `D:/Code/ldiar/AGENTS.md`（会话注入）、`docs/human_fall/WORKFLOW.md`、`docs/human_capture/README.md`
- `docs/human_fall/HF_MAINLINE_POINT_RETENTION_PLAN_20261014_V3.md`
- `docs/human_fall/evidence/.../REVIEW_PROMPT_02.md`、`CURRENT_DELIVERY_INDEX.md`、`ACCEPTANCE_V1.md`、`FINAL_REPORT.md`

代码/工具（只读）：
- `sidequests/human_fusion_lab_next/pointset/r01/research_retention.py`、`research_retention_guard.py`、`config_research_retention.json`、`config_research_retention_guard.json`、`test_retention.py`、`test_retention_guard.py`、`server.py`（头部）
- `tools/hf_mainline_points/verify_retention.py`、`verify_retention_v2.py`、`qualify_ledger.py`、`freeze_candidate.py`、`summarize_retention.py`、`score_js.py`、`js_diagnose.js`、`enrich_js.js`、`label_causes.py`、`split_guard_ledger.py`、`finalize_ledger.py`、`pipeline_02.py`、`prepare.py`、`preserve.py`、`check_api_final.py`、`verify_js_identity.js`

冻结/证据：
- `run_01/{SUMMARY,ALL_FRAME_VERIFICATION,FROZEN_CONFIG,FROZEN_SOURCE}.json`
- `run_02/{SUMMARY,ALL_FRAME_VERIFICATION,FROZEN_CONFIG,FROZEN_SOURCE,GUARD_BINDING,GUARD_VERIFICATION,FINAL_TERMINAL_CONSERVATION,FRAME_METRICS(节选)}.json`、`run_02_GUARD_DECISIONS.jsonl`(前4行)
- 证据根 `SOURCE_BINDINGS/DEPENDENCY_BINDINGS/LEDGER_CODEBOOK/QUALIFIED_LEDGER/REFERENCE_RISK_MANIFEST/DIAGNOSIS_TRAIN_ONLY/FROZEN_CASES/FROZEN_EXPERIMENT_V3/REGRESSION_RUNS/REGRESSION_*.log(索引)/PRESERVATION_REHASH/SCOPED 未逐项/BROWSER_CHECK/API_CHECK_FINAL/API_CHECK_SOURCE_MISSING/FINAL_SOURCE_AVAILABILITY/JS_METRICS(节选)/JS_ORDINAL_IDENTITY_PROOF/JS_LABEL_DELETION_CAUSES/js_02/...(MANIFEST,ledger_v2/LEDGER_CODEBOOK,EMPTY_HOLDOUT)/EXTERNAL_PAGE_CHANGE/REVIEW_AUDIT_01/OPENCODE_REVIEW_01.md(空)/REVIEW_LAUNCH_0{1,2}.stderr(空)`
- `docs/human_fall/evidence/2026-10-14_hf_mainline_points_plan_r1/CONTEXT_HOLDOUT_V2.json`

未读（按指示回避）：数 GB 源数组、逐帧大 JSON 全量、非候选帧详细 JSON。

## 总体裁决

**REVIEW_WITH_FINDINGS**

实现与作者的结论在"软件/几何/绑定/守恒"层面基本自洽，未发现足以推翻任一声明 PASS 的阻断性软件缺陷；作者总体未夸大，状态保守（PR01 FAIL、PR08 BLOCKED、PR11/12 BLOCKED、整体 SUBMITTED 未 ACCEPTED）。存在若干必须记录的开放发现与限制。**本审核不代作者关闭物理/完整人体/生产门；原 run_01 失败结论与旧日志保留有效。**

已独立复核为真且正向的要点：
- 源行守恒与重复 XYZ 不合并：`research_retention.py:127-129` 用 offset+arange 身份；`test_retention.py:9-16` 断言重复源行终态；`FINAL_TERMINAL_CONSERVATION.json` 以 `first`(全>0)+state 派生互斥终态，`finalize_ledger.py:18-20` 断言 `final>0` 且 `final==10` 恰为 members，记录数守恒成立。
- 实际 first reason 与反事实/候选资格分层：`ledger()` `research_retention.py:42-73`；`overlapping_predicates` 位5=COUNTERFACTUAL 与 `reached_stage_bits` 分离（`test_retention.py:14-15` 断言 bit 置位但 reached 未置位）；qualification 追加层不改 stage（`qualify_ledger.py`、`LEDGER_CODEBOOK.json`）。
- 有界因果：`Past.reset` 在换ID/时间倒退/gap 清空（`research_retention.py:165`；`test_retention.py:17-22`）；`verify_retention_v2.py:29` 用 `raw[:frame_end]` 前缀重放，`:107-109` 记录 `GT_entered_inference:false`。
- 只纳当前真实 background_removed 且原 ROI：`research_retention.py:181`、`verify_retention_v2.py:91` 断言 `added⊆bg && roi_mask`；无未来点/无跨帧身体点（`:92,103`）。
- R3 旧 FG 契约：`verify_retention_v2.py:53-57` 复用 `recover_r3` 并断言 `oldmembers==legacy['source_indices']`（1966 帧 `R3_exact_reproduced_frames:1966`）。
- 覆盖保护：`run()` `mkdir(exist_ok=False)`、guard 日志 `open('x')`、`np.savez(... )` 前 `exists()` 拒绝（`finalize_ledger.py:22`）、`js_diagnose.js` `{flag:'wx'}`、`score_js.py:58-59`。
- JS 身份/高度 2×2：`js_diagnose.js:35-48`（建图0.10/−0.25 × 提取0.10/−0.25；FULL_P/PAST10_P/B/C）；`verify_js_identity.js:31-33` 合成重复 ID 7/11 不合并；`score_js.py:62-63` 断言 S8 53帧/57045/54069/54063 精确重现。

## 发现

### P2-1 · combined 与 feedback 两条链在全部帧上完全相同，"独立 feedback"未构成独立对照
- 证据：`.../run_02/SUMMARY.json`（combined 与 feedback：added 299975、max_center 0.09399132365567024、axis_missing 69、jump 1.0711511382688477 全等）；`ALL_FRAME_VERIFICATION.json`（两臂 frames/source_records/added/nodes 全等）；`FINAL_TERMINAL_CONSERVATION.json` 全等；`FRAME_METRICS.json` fi=0/1 两臂 pool_count/added_count/center/jump 逐字段相等；`run_02_GUARD_DECISIONS.jsonl` 第3/4行 combined 与 feedback 的 before/after/rejected 索引数组与 `anchor_fraction` 完全相同。
- 影响：`ACCEPTANCE_V1.md` PR09 要求"固定锚点与独立feedback分开"；形式上分列，但 feedback tracker 从未与 R1 固定锚点分歧，PR09 的"独立"含义未被实质行使，PR04 的反馈消融无独立信息。
- 最小修复：在 run_02 汇总显式记录 feedback 相对 R1 的分歧帧数（按现状为 0）并把 feedback 标注为"与固定锚点重合的退化臂"，勿表述为独立前景。

### P2-2 · run_02 护栏阈值系读取首轮结果后的后验设定，非本轮诊断统计导出
- 证据：`research_retention_guard.py:28-34`（INSUFFICIENT_ANCHOR_FRACTION/CENTER_SHIFT/AXIS_CHANGE 三阈值拒绝整组）；`config_research_retention_guard.json:18-20`（0.85/0.12m/30°）；`REWORK_02_FROZEN.json` parameter_provenance 明确来自旧 R3/R2 常数；`FINAL_REPORT.md:27` 自述已读首轮及 80 帧后返工。计划 §5 P2 要求"新增阈值由诊断统计确定并冻结"。
- 影响：PR04/PR05 的"无新增退化"是在后验设定的护栏包络内成立（center 上限 0.12m 恰等于附件半径，结果 max 0.094<0.12）；属 REUSED_REGRESSION，不能当作独立泛化证据。
- 最小修复：在 ACCEPTANCE 中将 PR04/PR05 标注为"后验护栏内、复用回归"，并明确护栏为拟合式后处理过滤器。

### P2-3 · PR02 BLOCKED 与 PR05/PR07a PASS 的时序一致性未在证据内锚定
- 证据：`ACCEPTANCE_V1.md:8,11,13`（PR02 BLOCKED，PR05/PR07a PASS）；`FINAL_SOURCE_AVAILABILITY.json`（18 主链文件缺失，`current_raw_rerun:BLOCKED`）；`ALL_FRAME_VERIFICATION.json` 无时间戳。
- 影响：PR05/PR07a 的 PASS 现不可再导出，仅凭保留产物；结论依赖"验证早于源丢失"的口头断言。
- 最小修复：为 PR05/PR07a 证据补时间戳或一句"该证据早于 FINAL_SOURCE_AVAILABILITY，不可当前复跑"的显式绑定。

### P3-1 · S8 人体分母来源未与已审 GT 同源哈希绑定
- 证据：`score_js.py:23-41`——`human` 取 `output/<sid>/<fi>.json` 的 `reference`（`EXISTING_MANUAL_REFERENCE`），`furniture` 取 `gt_store/GT_V1.json`，仅对 GT 断言 SHA/reviewed；人体分母靠 `:62` 的精确数值断言固定，而非 reviewed-GT SHA。
- 影响：`JS_METRICS.json` 中 S8 人体分母的溯源略弱于家具；建议把 reference 集合的哈希/来源也纳入绑定。

### P3-2 · 交付中引用的空文件
- 证据：`BROWSER_FINAL_SOURCE.json`（0 字节）；`OPENCODE_REVIEW_01.md`（0 字节，首轮 CLI 启动失败属预期）。
- 影响：`CURRENT_DELIVERY_INDEX.md` 结构上引用可能产生误读；建议删除空文件或注明其为失败/占位，保留首轮失败日志不变。

## 非阻断限制（单列，不作 PASS）

- 无物理/人体 GT：身份 UNKNOWN，完整人体召回、家具纯度、解剖精度、跨人跨景泛化 null/UNKNOWN（PR11 BLOCKED）；生产晋级/confirmed/部署 BLOCKED（PR12）。
- 80 帧 CONTEXT_HOLDOUT 历史已见、仅 4/8 会话，非独立新测试；80 帧同时计入 1966 回归，不得重复计样本。
- 空场仅 131958 的 32 留帧，不能支撑其他场景安全或泛化。
- 原录制当前缺失（18 主链文件），删除行为未归因，本 writer 未删除、未生成替代；复跑 BLOCKED。
- 整树非原子冻结：12 变化/33 缺失未逐文件归因（含 r04/console、215540/203349 等外部/历史源消失）。
- 并行外部页面改写入（scene_change、r04/console）同期发生，作者未认领、未回滚，并清单列保存；不冒称整树冻结，正确。
- JS 高度 2×2 为诊断，JS 默认与生产未改；Python 0.2–15 严格、JS 0.35–25 含端点，口径分离正确。
- 页面仅 IPv6 回环 `[::1]:8944`；IPv4 同端口另有 PLANE 服务未停止（404/截图保留）。
- 参考 FIT 覆盖 33/33 无鉴别力，`reference` 风险门在本轮实际为恒真（作者已诚实披露）。

## 逐 PR 状态建议（不改写作者原文，保留原失败）

| PR | 作者 | 审核建议 | 依据 |
|---|---|---|---|
| PR01 | FAIL | 同意（保守）；可注明为"范围外漂移未归因" | PRESERVATION_REHASH、EXTERNAL_PAGE_CHANGE |
| PR02 | BLOCKED | 同意 | FINAL_SOURCE_AVAILABILITY、BASELINE_REPRODUCTION |
| PR03 | PASS | 同意 | test_retention、FINAL_TERMINAL_CONSERVATION、verify_retention_v2:36-37,44-47 |
| PR04 | PASS | 同意但加"后验护栏/复用回归"标注 | config_research_retention_guard、REWORK_02_FROZEN、P2-2 |
| PR05 | PASS | 同意但标注历史不可复跑 | ALL_FRAME_VERIFICATION、P2-3 |
| PR06 | PASS | 同意 | ANALYSIS/SUMMARY、FINAL_REPORT:33 |
| PR07a | PASS | 同意但标注历史不可复跑 | SUMMARY、P2-3 |
| PR07b | PASS | 同意 | score_js:62-63、JS_METRICS |
| PR07c | NOT_EVALUATED | 同意 | JS_LABEL_DELETION_CAUSES、无家具负例分母 |
| PR08 | BLOCKED | 同意 | BROWSER_CHECK(passed:false)、API_CHECK_SOURCE_MISSING |
| PR09 | PASS | 同意但附 P2-1 | SUMMARY/FRAME_METRICS/nput |
| PR10 | PASS | 同意 | 交付/回传/独审原结论另存 |
| PR11 | BLOCKED | 同意 | 无身份 GT/物理资格 |
| PR12 | BLOCKED | 同意 | 范围外 |

## 对"是否夸大"的判定

未见将 UNKNOWN 当人体、将几何保留当完整人体收益、或用单测总数替代验收的夸大。`API_CHECK_FINAL.json:1`（真实原字节 PASS）与 `API_CHECK_SOURCE_MISSING.json`（当前 MISSING_ORIGINAL_SOURCE/opaque=null）被明确区分，未以旧 PASS 冒充当前可用。唯需注意 PR04/PR05/PR07a 的 PASS 属复用/历史证据（P2-2/P2-3），以及 PR09 的"独立 feedback"名不副实（P2-1）。
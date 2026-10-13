以下为对 **HFUS-D05-R02 源码**的只读独立审查（未写入/修改任何文件、未运行评测、未派代理；结论均来自静态阅读与实际文件核对）。

---

# HFUS-D05-R02 只读独审报告

## 0. 审查方式与前提

- 已按要求先读 `ponytail/SKILL.md`、仓库 `AGENTS.md`、`docs/human_capture/README.md`、`ACCEPTANCE_V1.md`、`D05_CORRECTION_AUDIT.json`，再读 r02 八个文件与其真实调用者（`engine_b.js`、`detector_b.js`、`run_b.js`、`instrument.js`、`strict_v2.js`、`index_v1.js`、`run_d04.js`、`hook_unknown.js`、`human_pipe_lib.cluster_voxels/cluster_features`、`unique_tracker.js`、`export.objects`、`data_loader`）。
- 全程未写文件、未跑 node/python、未评测。因此凡需实跑才能定论的项一律记 `NOT_RUN`/`BLOCKED`；不把颜色、测试数或旧摘要当作效果。
- 现状核实：`runs/full/base`、`runs/full/a06` 各 9 会话齐全，`full_base_EXIT.json`/`full_a06_EXIT.json` exit 0；**`runs/full/split` 只有 3 个 jsonl，无 split EXIT、无 `CASE_INDEX.json`/`COMPARISON.json`/`FAILURE_LEDGER.jsonl`**（`full_split.log` 停在 175553）。故 **完整九会话对比实验未完成**，本文不宣称实验结论。

## 1. 逐验收项静态核查

| ID | 静态结论 | 依据 |
|---|---|---|
| R02-01 | 部分有据 | `BASELINE_BEFORE.json` 存在（branch master / HEAD / status / 逐文件 SHA 分类）；未见结束态与读取错误单列文件，`NOT_RUN` |
| R02-02 | 证据层，不在 r02 代码 | 由 `D05_CORRECTION_AUDIT.json`（54 ledger/2605 帧声明）+ `PILOT_FAILURE.md` 承载；r02 未重做 D05 六套核对，`NOT_RUN` |
| R02-03 | 代码具备 | run.js 逐帧写 raw/valid/BG/cleanup/final（`stages`）、候选、`tracks`、`strict`；analyze.attribution 生成逐点归因账；**retention 账未逐帧落盘**（仅 `tracks.lost`），见 P2-3 |
| R02-04 | 代码具备 | analyze.py `net_bg_recovery`/`net_final_recovery`/`new_accepted_points`/`human_supported_net_bg_points` 分列；demo 文案明确“点恢复只表示阶段集合变化”。**数值效果 `NOT_RUN`** |
| R02-05 | 代码具备（静态） | 分离仅用 XY/z（无 GT）；`partition` 断言点守恒+key 互斥；未动 `cluster_features`/`classify_human`/门；`hook_split.__main__` 有可运行反例检查 |
| R02-06 | 未完成 | base/a06 已跑，split 只 3/9；TP 收益/无下降、家具净新增错误接受 均 `NOT_RUN`；家具资格在 analyze 中显式 `BLOCKED` 语义 |
| R02-07 | 代码具备 | check.js 覆盖重复/回退/gap/reset/跨会话契约；analyze 记 first/longest_qualified_fn/reacquisition/id_changes/max_coast/confirmed_coast；strict_v2 只计 `lost===0`（预测不计检出） |
| R02-08 | 不完整 | 三窗+同步契约+SHA 校验具备；**无真浏览器截图**（audit 亦列 missing），`NOT_RUN` |
| R02-09 | 代码具备，结果 `NOT_RUN` | perf.js 串行、前 5 帧热身、无 trace/read/render，`p95<50` 沿用；D05 旧 p95 126–141ms 仅为诊断，r02 纯算法未跑 |
| R02-10 | 部分 | `OPENCODE_SOURCE_01.jsonl` 存在（含指令与工具调用），但**无进程 exit/实际模型行的单独留证**，`NOT_RUN` |
| R02-11 | 部分 | 源码 SHA 进 SUMMARY，但未覆盖 r02 的 py/html（见 P2-2）；不自行 ACCEPTED，正确 |

## 2. 可复现问题（文件/行/触发/影响/最小修法）

### P2-1　unknown hook 统计为累计值，却被逐帧写成“每帧快照”（与审计缺陷同源，未被真正修掉）
- 位置：`d05/r02/run.js:114`（`sum.hook_stats.unknown.push({frame_index,...e._unknown_hook_stats})`）；`d05/hook_unknown.js:12`（`engine._unknown_hook_stats` 仅在 apply 时建一次，**从未按帧重置**）。
- 触发：任何 `a06`/`split` 运行，逐帧 push。
- 影响：`SUMMARY.hook_stats.unknown[i].re_admitted` 是**前缀累计**而非该帧值。`D05_CORRECTION_AUDIT.json` 已点名 “unknown hook re_admitted cumulative; do not sum frame entries”。当前 analyze/demo 未消费该字段，故无聚合伤害，但它是一个明确会误导下游求和的账（例如统计“重入点总数”时应取最后一帧而非求和）。
- 最小修法：在 trace 的 `_level` 包装（`d05/r02/trace.js:13`）里每帧开头重置 `e._unknown_hook_stats={re_admitted:0,still_rejected:0}`；或改为在 `hook_unknown.js` 的 `bgB.select` 入口重置（该函数每帧调用一次），从而字段语义与 `frame_index` 一致。

### P2-2　`sourceManifest` 不覆盖 r02 的 py/html 工具层，Demo 的 SHA 门保护不到分析与演示代码
- 位置：`d05/r02/trace.js:6-8`（仅 `require.cache` 前缀 + `human_replay`/`models` 两目录）。
- 触发：写入 `SUMMARY.sources`、并被 `demo_server.verified()`（`demo_server.py:38`）逐个 `assert sha`。
- 影响：`analyze.py`/`check.js`/`perf.js`/`demo_server.py`/`demo.html` 不在 manifest 内；改动这些不改任何被校验 SHA，R02-11“新源码 SHA”只覆盖 JS 引擎侧。另 `require.cache` 按 `B.ROOT` 前缀过滤，若将来 require 到仓库根下任意包会把无关文件纳入。
- 最小修法：在 `sourceManifest()` 追加显式清单（这 5 个文件），或对该工具层单独产出 `TOOLING_SOURCES.json` 并同样在 Demo 校验。

### P2-3　R02-03 要求的 “retention 账” 未逐帧落盘
- 位置：row（`run.js:119`）无 retention/银行字段；`stages`（`trace.js:25-32`）只到 `final/retained/cleanup/bg`，无 `retention.tracks`。
- 触发：任意会话。
- 影响：逐帧审计缺 retention 段；“恢复点重入”只能从 `tracks.lost/coast` 间接推断。
- 最小修法：row 增加只读快照 `retention:{tracks:Object.keys(e.retention.tracks).length, hot:...}`，或复用 `d._tracks` 的 `lost` 明确标注来源。

### P2-4　analyze.py 内 `timing` 收集后未使用（死账）
- 位置：`analyze.py:71`（`timing[v].append(...)`），后续无引用。
- 影响：轻微，误导“每帧计时已并入对比报告”；实际性能权威在 `SUMMARY.performance` 与 `perf.js`。
- 最小修法：删除该行，或加入 `session_results`。

### P2-5　`run.js` `linkBase` 为死代码，且与“base 需实跑”的新口径并存易混淆
- 位置：`run.js:32-41`（定义但不被调用；r02 的 `base` 走真实引擎实跑，而非引用 D04）。对比旧 `d05/run_d05.js:62` 仍 `if(variant===BASE)return linkBase()`。
- 影响：仅可读性/维护风险（读者可能误以为 base 是引用）。
- 最小修法：删除 `linkBase`，或注释“r02 不使用引用式 base”。

### P3（低）
- `run.js:80,119` 同时输出 `pre_components` 与 `raw_components`，但 analyze 只用后者；建议注释区分 pre/post，避免误用 pre 组件评分。
- `analyze.py` 输出文件一律 `open('x')`，重跑即失败；已有 refuse-overwrite 语义，可接受。

## 3. 代码与冻结假设的一致性（重点核查过，未发现不符）

- H1 参数全部落在 `hook_split.js:4` `{z:1.3, high_points:10, cells:3, points:60, separation:.45, expansion:.30}`，与 `ACCEPTANCE_V1.md` §H1 逐项一致；`applyVariant`（`run.js:28-29`）对 `split` = A06(r=.6/link=.3/min_ref=1/min_local=1) + 分离，与 Demo 标签“A06 + 密集核心分离”、analyze 以 a06 为 split 的 `before`（`analyze.py:107`）一致。
- **GT-free**：`hook_split`/`hook_unknown` 只读 XY/z/参考列，无 GT/未来帧；analyze 在“已保存推理之后”才碰 GT。
- **XY key 互斥 / 点守恒**：`partition` 在 `hook_split.js:30-31` 双断言；`combine` 逐 key 汇总 `acc`，与 `cluster_features` 只消费 `cl.acc`（`human_pipe_lib.js:581-583`）兼容；输出 `{keys,acc}` 形状与生产 `cluster_voxels`（`:453`）一致。
- **原门不降**：分离未改 `cluster_features`/`classify_human`/`human_n_min`/`hard_gate_n500`；门仍由引擎原路径施加。
- **恢复点重入分类跟踪**：`instrument.js:15` 的 `final_ids/background_ids/cleanup_ids` 用 `subsequence(args[1]=leveled,...)` 得到的是**raw 行号**，与 `detector_b._level` 返回的全长 `leveled_xyzi`、`mapFrame.compact_to_raw` 对齐；`trace.js:18` 用 `key_vox` 回挂 post 组件，与引擎 `members` 口径一致（同为 raw）。
- **instrument 前后组件语义**：`trace.js:19` 用 **post-split** `cls` 重建 PA `_post_components`，`trace.js:23` 仅追加 `path==='PB'` 的 shadow 组件——正是审计“raw components reflect pre-split → 需显式 post partition proposals”的修法；PB 点为 A 候选之外的点，与 PA 呈互补。
- **同口径 base**：analyze 对 base/a06/split 用同一 `R02_*` 脚本重跑；对 frozen D04 只对 `accepted/observed_confirmed/legacy/candidates` 做 `parity`（`analyze.py:66`），**刻意不比对 proposal**（因 r02 proposal 改口径）——与 interpretation “post partition proposals”自洽。`br` 用作 a06 基线、`ar` 用作 split 基线，单因素链清晰。
- **模型特征/成员**：`trace.js:14-15` 记录 69D 特征 sha256 与 prob，`n` 取 `sub.n`；`detector_b.js:28-29` 用 `xgb69_candidate` 的 `extract+extra` 与 `predict_person`，调用恒为 `predict(extract(...))`，无 `_model_calls[-1]` 越界风险。
- **未知帧 FN**：`export.objects` 对“有 doc 但该帧无标/含 UNKNOWN/落在 uncertain 区间”返回 null → `q='UNKNOWN'` → run.js `else` 记 `unknown_frames++`（`run.js:105`）；修掉了旧“合格绑定但未标帧不计 unknown”。
- **有限 coast/reset**：`engine_b.tick` 跳帧显式 `gap_reset` 重建 tracker/retention/fusion 并 `track_segment++`；`strict_v2` 只把 `lost===0` 且有候选支撑者计入 observed，coast 单列；check.js 实证 seek/回退/重复/跨会话须经 `begin`。
- **Demo 真实 D04 基线/同步/SHA**：`demo_server.py:14` FROZEN 指向 `2026-10-11_hfus_d04_r1/runs/base`（修掉“AUTO 解析 D03 却标 D04”）；`/api/frame` 断言 `b.candidates===bs.candidates` 并仅用 base 的 `stages` 补 D04 冻结行（`demo_server.py:87`）；`demo.html:18-19` 用 `token` 丢弃过期响应解决 race；`checked()` 用 `X-Content-SHA256` 校验 `/api/frame`、`/api/points`。28B/点定步长与 `data_loader.STRIDE=28` 一致。
- **预登记门**：阈值/几何全部写死在源码，未见事后调参路径。

## 4. 无需人工即可继续的工程工作（建议）

1. 修 P2-1（每帧重置 hook 统计）并加一个最小 `check`：断言同一 run 内 `hook_stats.unknown` 相邻帧差值 == 实际重入点数。
2. 修 P2-2（补 r02 工具层 SHA）后，Demo 首屏可显示工具层版本。
3. 待 split 9/9 完成后跑 `analyze.py`，产出 `COMPARISON.json/CASE_INDEX.json/FAILURE_LEDGER.jsonl/MANUAL_REVIEW_MINIMAL.json`；再跑 `perf.js` 填 R02-09。
4. 补齐 R02-01 结束态 SHA、R02-08 浏览器截图、R02-10 进程 exit/实际模型行，作为收口证据。
5. 删除 `run.js:linkBase`、`analyze.py:timing` 死代码（P2-4/P2-5）。

## 5. 未完成的实验 / 不可判定项（明确 BLOCKED/NOT_RUN）

- split 九会话对比、TP 收益与“其它正式会话无 TP 下降”、家具净新增错误接受：`NOT_RUN`（split 3/9）。
- 性能门 `p95<50ms`：`NOT_RUN`（r02 纯算法未跑）。
- GT 语义/生产/板端实时：`BLOCKED`（S9 `INVALID_BINDING`；无 `negative_reviewed`；`MANUAL_REVIEW_MINIMAL` 标注 DRAFT）。
- R02-06 应写未写“资格不足则 BLOCKED”：analyze 已在 `limits`/manual status 表达，但正式裁定 `NOT_RUN`。

---

REVIEW_COMPLETE

审查文件清单（实际读取）：
- `C:/Users/30680/.codex/skills/ponytail/SKILL.md`；`AGENTS.md`（全局+仓库）
- `docs/human_capture/README.md`
- `docs/human_capture/evidence/2026-10-11_hfus_d05_r2/{OPENCODE_SOURCE_BRIEF.md, ACCEPTANCE_V1.md, D05_CORRECTION_AUDIT.json, PILOT_FAILURE.md, full_base_EXIT.json, full_a06_EXIT.json, full_split.log, BASELINE_BEFORE.json, OPENCODE_SOURCE_01.jsonl(部分)}`
- `sidequests/human_fusion_lab_next/d05/r02/{hook_split.js, trace.js, run.js, analyze.py, check.js, perf.js, demo_server.py, demo.html}`
- `sidequests/human_fusion_lab_next/d05/{hook_unknown.js, run_d05.js, BUILD_DEMO.md}`
- `sidequests/human_fusion_lab_next/d04/run_d04.js`
- `sidequests/human_fusion_lab_next/background/{engine_b.js, detector_b.js, run_b.js}`
- `sidequests/human_fusion_lab_next/eval/instrument.js`
- `sidequests/human_fusion_lab_next/contracts/{strict_v2.js, index_v1.js}`
- `sidequests/human_fusion_lab/{export.js, unique_tracker.js, human_replay/human_pipe_lib.js(相关段)}`、`core/data_loader.js`
- `captures/remote/cap_20261010_175804/meta.json`（头部）、`docs/.../hfus_d04_r1/runs/base/`（目录清单）
# HFUS-D03 独立复跑 verify REPORT (sub_d03_verify)

> 本文件由主控按 D03 verify 代理完成通知原文固化落盘（代理因沙箱写限制无法自写 REPORT.md）。内容即其最终报告全文。

2026-10-11 · 独立 agent 在 Win/Git-Bash 复跑。只写 `sub_d03_verify/`；`sidequests/human_fusion_lab_next/`、`captures/`、`pc_apps/human_replay/gt_store/`、其它路径全部未动，未 commit/push。

## 0. 源脚本考察

| 文件 | 作用 | 复用方式 |
|---|---|---|
| `run_b.js` | B=BG-B（参考 UNKNOWN 邻域门 → `_fusion_a_chain` select → FUSION tracker）；A=`fixedDetector('xgb69_candidate')` 生产 legacy；逐帧 `writeSync` 写 `<MODE>_<sid>.jsonl`，末尾 `<MODE>_SUMMARY.json`，自带 `refuse overwrite`。 | `require(...run)`，传入 `sub_d03_verify/rerun_{A,B}`、sid filter。 |
| `summarize_b.js` | 需同目录 `A_SUMMARY.json` + `B_SUMMARY.json` → 写 `REGRESSION_COMPARISON_V2` / `EVENTS_V2` / `FINAL_MANIFEST_V2`。 | `summarize_rerun.js` 在 `rerun_sum/` 拷贝并重挂 main(out)。 |
| `check_b.js` | 4 组断言；stdout `BG_B_CHECK_PASS …`。 | `node check_b.js`，与官方 `CHECK_01.log` 字节对照。 |
| `eval/instrument.js` | 对 `eng` 加 PB/PA raw 组件收集 + `subsequence` 校验。 | run_b 内已是必经路径。 |
| `run_b.js:29` GT 绑定白名单 | `gtManifestSHA===rec.manifest_sha256 && rec.eligible && doc.session_id===rec.sid && doc.review_status==='reviewed' && B.sha(rec.gt_path)===rec.gt_sha256 && doc.session_sha256?.meta===session.meta_sha256 && doc.session_sha256?.points===session.points_sha256` 全过才留 doc。 | S9 走的就是这条 → §4.4。 |

**重要发现**：当前 `run_b.js:38` 在写出 ledger 行头附加 `schema_version`/`evaluation_version`/`segment`/`timestamp_s` 4 个键，并在 `<M>_SUMMARY.sessions[i]` 附 `input_sha256/gt_manifest_sha256/gt_binding_valid/gt_sha256/model_sha256/config` 6 个元字段。官方 `A_*`/`B_*.jsonl` 首行只剩 **19 键** ——官方产物由**老一版** `run_b.js`（SHA 见 §1）写出。

## 1. run_b.js SHA 漂移核验

```
orig A_SUMMARY.sources[2].sha256(run_b.js) = 303acea56c626c1ad6eaac3d3703474307984be33632c2652ea4f230d8566284
rerun A/B_SUMMARY.sources[2].sha256(run_b.js) = 646aae91c62371732084f505cb387029f0ef68eff52b372fdbbfc3673315f696
当前工作树 run_b.js SHA 与 rerun 一致。sidequests/human_fusion_lab_next/background/run_b.js 在本仓库下 untracked，无 HEAD 版可还原。
其余 6 个源(engine_b/detector_b/contracts×3/instrument.js)两版 SHA 完全一致。
```

## 2. 命令与输出

| 命令 | 出口 | stdout | 输出位置 |
|---|---|---|---|
| `node sidequests/human_fusion_lab_next/background/check_b.js` | 0 | `BG_B_CHECK_PASS missing_reference / unsupported_UNKNOWN / shared_PB / sensor_invalid` | `CHECK_01_rerun.log`（byte-identical to `CHECK_01.log`） |
| `node …/run_A_rerun.js` | 0 | 9×`A cap_… tp/fp/fn …` + `A_RERUN_DONE` | `RUN_A.log`、`rerun_A/` |
| `node …/run_B_rerun.js`（首轮被外部 137 杀于 `180557` 入口） | 137 | 至 180337 完成 | `RUN_B.log` |
| `node …/run_B_resume.js rerun_B rerun_B_stage "cap_20261010_180557,cap_20261010_180751"` | 0 | 2×`B cap_…` + `RESUME_DONE` | `RUN_B_resume.log`、最终 `rerun_B/B_cap_20261010_180557.jsonl`（44,953,826 B）与 `B_cap_20261010_180751.jsonl`（12,673,730 B） |
| `node …/assemble_B_summary.js rerun_B` | 0 | `WROTE … n=9 mode=B` | `rerun_B/B_SUMMARY.json` |
| `node …/compare_ledger.js rerun_{A,B} {A,B}` | 0 / 0 | — | `COMPARE_{A,B}.json` |
| `node …/summarize_rerun.js` | 0 | `SUMMARIZE_RERUN_DONE` | `rerun_sum/` 下 5 件 |

`_resume.js` / `assemble_B_summary.js` 为 verify 端补件，仅绕过 `'refuse overwrite'`、重命 staging 产物；不改 `run_b.js`。

## 3. 逐会话 A/B 复跑 SHA 对照表

字节层 18/18 `byteEq=false`（每行 4 个附键 + SUMMARY.sessions[i] 6 个附键 + 全部 timing/heap 字段造成 `numDiffLines = qualified_frames + unknown_frames`）。**语义**层（剥离 `schema_version/evaluation_version/segment/timestamp_s`、`performance`、`ledger.{path,sha256}`、`layers[i].elapsed_ms` 之后 deep-diff JSON）18/18 `semEqAfterSanitize=true`，全 `diffs=[]`。

| sid | mode | shaO(16) | shaR(16) | byteEq | numDiffLines | semEq |
|---|---|---|---|---|---|---|
| 175227 | A | 7e5e339a231425a3 | 5964a67e1e780aa7 | no | 304 | yes |
| 175429 | A | 060f75d5d973f373 | 42de1cc2d21cb8a9 | no | 258 | yes |
| 175553 | A | a25164074374eaac | 8a0313505600e701 | no | 464 | yes |
| 175804 | A | 032dec0aba62f630 | 6b960e9f6c058ca1 | no | 239 | yes |
| 175943 | A | 6cf95bbd9a8452ff | 89354d2f39e76f70 | no | 202 | yes |
| 180235 | A | 51deeceddee05d47 | 40368aedc295512f | no | 238 | yes |
| 180337 | A | 7f5dc800a779df9f | c65be2a9cfe61678 | no | 251 | yes |
| 180557 | A | 9f2c40819d33473d | 5d8ab832dc1ff65b | no | 523 | yes |
| 180751 | A | d208e98fd9c21f67 | 38fdd3ec7aadd0c8 | no | 126 | yes |
| 175227 | B | ffb206e49551b353 | cbd340a75d91ccd1 | no | 304 | yes |
| 175429 | B | 300b53b4712a3be5 | 54b20d2caf2d2e8d | no | 258 | yes |
| 175553 | B | 0e585cf806ea50ba | 00f40aba0d7ae830 | no | 464 | yes |
| 175804 | B | e91ef041f098d4d1 | 131280d7f7646b9776 | no | 239 | yes |
| 175943 | B | 155ce0df7546687b | 003f0443c640624e | no | 202 | yes |
| 180235 | B | 77c8fa0735e96df0 | 9ecf490c03ee0699 | no | 238 | yes |
| 180337 | B | f19292b76077ac75 | 419a4ec0f37ec70e | no | 251 | yes |
| 180557 | B | cc4168a3a2149f89 | faa327b2b61043de | no | 523 | yes |
| 180751 | B | 314ed2107ee024e5 | db4a0e544037321e | no | 126 | yes |

## 4. 五问

均以官方 `A_SUMMARY.json` / `B_SUMMARY.json` / ledger 为据（rerun 值完全一致）。

### 4.1 S1 A=0 vs B=347 legacy.confirmed.FP 工程差

S1 的 GT `reviewed + eligible` 但 `objects` 为空集 → 无 GT 可匹配 → legacy 判分把任何 `prob>=.35 + track_confirmed` 计 `fp`。A 链（fixedDetector('xgb69_candidate')）在纯家具空场不产生 confirmed 轨迹，故 `fp=0`。**B 链**：BG-B `select()` 对 keep 点再做 0.4 m XY 邻域判决；家具点在参考 XY 柱 0.4 m 内有支撑 → 标记 `no_bg_match_supported_XY_UNKNOWN` 放行进 fg；RF 后 `prob>=.35 + track_confirmed=true` → legacy `fp=347`（`accepted fp=355`）。strict 承认 `UNKNOWN ≠ FP`，把这部分账记在 `.observed_confirmed.unmatched_unknown=329` 和 `.accepted.unmatched_unknown=355`。Ledger 实证：`B_cap_20261010_175227.jsonl` f2 `a_2_2 src=A prob=0.960 pts=152`、`a_2_4 src=A prob=0.868 pts=269`、`b_2_0 src=B prob=0.740`，point_indices 全部指向 S1 空场家具的 raw 行。**同一管线在两协议下，fp 差异完全是「家具在 B 链下通过 UNKNOWN 邻域门 + legacy 不认 UNKNOWN」**。

### 4.2 near S3-walk-x-near

- strict proposal：A `tp=163 fn=95 uu=478`；B `tp=114 fn=144 uu=1018`。
- strict accepted：A `tp=163 fn=95 uu=114`；B `tp=114 fn=144 uu=761`。
- legacy.confirmed：A `tp=256 fp=9 fn=2`；B `tp=213 fp=625 fn=45`。

legacy TP 下降与 strict fn 上升同根：B 链排空 `no_reference_XY_support_UNKNOWN`（f0 `observed.fn_ids=[obj_f0_n6]` 即是一例，near 会话 `unsupported_UNKNOWN_points=165791`），同时把更多家具/遮挡残余留在 fg 里形成多个 `prob>=.35 + track_confirmed` 的 FUS_t*，legacy 计 fp=625；strict 把这部分分账 `accepted.unmatched_unknown=761`、 `observed.unmatched_unknown=705`。

### 4.3 far S3-walk-y-far

- legacy.confirmed A `tp=97 fp=93 fn=2` vs B `tp=95 fp=104 fn=4`（任务原描述 97/93/2 vs 95/104/4 对应）。
- strict proposal A `tp=38 fn=61 uu=310` vs B `tp=17 fn=82 uu=220`。

远端人体点密度低，BG-B 0.4 m XY 邻域支撑概率下降；`unsupported_UNKNOWN_points=194434`（与 S7-far 356570 同为最高）显示大量有效人点被判 UNKNOWN 剔除 → strict fn 上升。legacy 净 FP 由 93 → 104 是 B 链在远端留下更多 `prob>=.35` 的簇/反射噪点。

### 4.4 S6-occlusion

- `legacy.accepted A tp=65 fp=1 fn=6`；`legacy.accepted B tp=66 fp=105 fn=5`。
- `legacy.confirmed A tp=61 fp=1 fn=10`；`B tp=65 fp=93 fn=6`（B 在此达 D03-06 `>=64/71`；A 不达）。
- strict proposal A `tp=47 fn=24 uu=159` vs B `tp=8 fn=63 uu=226`。
- 硬帧：f187 A `proposal tp=0 fn=1 uu=0 (fn_ids=[obj_f187_n46])`；B `tp=0 fn=1 uu=3 (uu=[2,4,8]/pa+pb组件)`；f188 类似，A `uu=0`、B `uu=3`。两 mode 都没把 GT 唯一 PERSON 命中到任何候选，B 链又在 BG-B 排出的 UNKNOWN PA/PB 组件里另外挑出 `rf51>=0.35` 的点集，legacy 给 `fp=1~2`。

### 4.5 工程差归因统一说法

引 `docs/human_capture/evidence/2026-10-11_hfus_integration_r1/BG_COVERAGE_PREREGISTRATION.md` §3/§4：UNKNOWN 只有邻近冻结参考已观测 XY 柱支持（0.4 m，复用 retention 空间尺度）才进入原 z/cleanup/proposal/分类门；无邻域支持的 UNKNOWN 不进 proposal；无射线覆盖不称 FREE；这是背景表示 + 覆盖约束的研究变体，未按 GT 调优。

落地 `detector_b.js select()` 对每个 `keep` 点做 0.4 m `columns` 邻域查询：`no_bg_match_supported_XY_UNKNOWN` 放行，`no_reference_XY_support_UNKNOWN` 剔除（后者即 ledger `bg.unsupported_UNKNOWN_points`；S1=8333、near=165791、far=194434、S5=291739、S6=39197、S7=356570）。对家具/远端低密度点网开一面，对低支撑人体点（远端/边缘/被遮挡）按 UNKNOWN 丟弃。0.4 m 借自现 retention `hot_cell_radius_m`**，完全未按 GT 调优，导致：

- legacy.confirmed FP 上移：家具通过邻域门 → RF → confirmed 轨迹 → legacy fp。
- legacy.confirmed TP / strict.tp 下移：人体边缘点被按 UNKNOWN 剔除 → 候选口径收小。
- S6-occlusion 硬帧既漏 PERSON (A/B 都漏) 又多报 (B 多) —— BG-B 判决的不一致与候选重叠无几何演进器。

### 4.6 S9=cap_20261010_180751 persons=0 根因

`AUDIT.json` 该 sid `eligible:false`；`GT_V2.json` 有 `review_status:"reviewed"`、`objects`(36 个，`class_name=PERSON`)，但 **`session_sha256.points = "aaaa…占位"`**。`run_b.js:29` 白名单 `doc.session_sha256?.points===session.points_sha256` 失配 → INVALID_BINDING → `doc=null` → `objects(doc,...)=null` → 126 行 ledger `qualification="UNKNOWN"`、`gt=[]`、`gt_persons=0`、所有 strict/legacy 计数 0。candidates 仍走 BG-B 链，`gt_hits=[]`。**根因是 GT 里放占位 sha，非 BG-B 败坏 GT**。这也与用户 MEMORY `HFUS-D02 S9 aaaa… 破绑定` 的记录一致。

## 5. EVENTS.json vs EVENTS_V2.json

- **schema**：完全一致。30 键结构顶层 9 个 `{sid, qualification, qualified_exposure_s, event_semantics, events[]}`；每 event `{kind,id,start,start_timestamp,count,end,end_timestamp,duration_s}`，`kind` ∈ {FN, UNMATCHED_UNKNOWN}。
- **events[] 序列**：9 个会话逐字段相等。
- **唯一差异**：`qualified_exposure_s` 在 6 个会话（175553 / 175804 / 175943 / 180235 / 180337 / 180557）不同。V2 加了严谨过滤：`dt ∈ [0, .3] 且 prev/curr 两帧都不是 UNKNOWN 且 frame_index 连续` 才累加；旧版规则较宽。结论：**结构 / 决策事件一致，只是 exposure 算术收紧**；以 V2 为准。

## 6. D03-06 逐 gate 对照

| gate | 阈值 | 原 D03 值 (A / B) | 判定 |
|---|---|---|---|
| S6 legacy accepted.TP ≥ 67/71 | 67 | 65 / 66 | **FAIL both** |
| S6 legacy confirmed.TP ≥ 64/71 | 64 | 61 / 65 | A FAIL / **B PASS** |
| S6 f187/f188 正确 proposal | 至少 1 cand 命中 | A f187 `tp=0 fn=1 uu=0`；B f187 `tp=0 fn=1 uu=3`；f188 同（A `uu=0` / B `uu=3`），均无候选命中 GT PERSON | **FAIL both** |
| S1 legacyFP=0 | 0 | `legacy_accepted fp` 0 / 355；`legacy_confirmed fp` 0 / 347 | A PASS / **B FAIL** |
| near confirmed TP≥256 / FP≤9 | 256/≤9 | 256/9 / 213/625 | A PASS / **B FAIL** |
| strict 有资格场景不回退 (`observed_confirmed.tp_B ≥ tp_A`) | — | 6/9 会话（175429/175553/175804/175943/180235/180337）回退；S1/S8/S9 持平 | **FAIL** |
| p95 ≤ 50 ms | 50 | A 74–194.9 ms / B 92–204 ms | **FAIL both** |
| heap ≤ 1500 MB | 1500 | A heap_max 309–374 MB / B 444–524 MB | **PASS** |

任一 gate 不达即 FAIL。综合判 D03-06 **FAIL**（8 gate 中 3 PASS / 5 FAIL）。

## 7. 判定

**REPRODUCIBLE: partial**

- **算法/语义层** yes：9 会话 A/B ledger 在剥离漂移元字段后逐字段相等（COMPARE_A/B `semEqAfterSanitize=true`）；`EVENTS_V2` / `REGRESSION_COMPARISON_V2` deep-equal；`check_b.js` exit=0、stdout 与官方 `CHECK_01.log` 字节一致；`RUN_A.log` / `RUN_B.log` / `RUN_B_resume.log` 的 27 行 per-session `gt_persons + legacy_confirmed + p95` 与原始 AUDIT sid × mode 完全匹配（全部 tp/fp/fn 与 A_SUMMARY/B_SUMMARY 数值等价）。
- **字节层** no：官方产物由 `run_b.js` 老一版 `303acea5…` 写出（untracked，无 HEAD 可还原），现行工作树 `646aae91…` 增 4 ledger key + 6 session meta key；ledgers sha 不一致。此为工程留档缺失而非算法漂移——所以数值完全一致、字节不一致。
- 工程上：**partial**，根因是 untracked `run_b.js` 未被基线封版。

**ALG: FAIL**（D03-06 综合 3 PASS / 5 FAIL：near legacy.confirmed A 达标、S6 legacy.confirmed B 达标、heap≤1500；S6 legacy accepted A/B 都差 1、S1 B 家具 FP 347、near B strict TP 回退、S6 f187/f188 A/B 均未命中、strict 6/9 回退、p95 74–205 ms 超时。生产持续 BLOCKED，与 D03-PHY 一致）。

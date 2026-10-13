# HUMAN-R4-CANDIDATE-AUDIT 只读独立审核（审稿，非作者自验）

审核对象：`HUMAN_R4_CANDIDATE_AUDIT_ACCEPTANCE.md` v1、`HUMAN_FUSION_NEXT_STAGE_PLAN.md`、`pc_apps/human_core/audit_fusion_candidates.js`、`test_candidate_audit.js`、`docs/human_capture/evidence/2026-10-11_human_r4_candidate_audit_r1/`（`GT_SNAPSHOT_02.json`、`runs_01/02/03`、`baseline.py`、`snapshot_gt.py`、`summarize.py`、`run_review.py`、日志）。
审核方式：仅读文件、跑一次只读测试、以 node 计算 SHA、python 解析快照统计。未写文件、未调 GT 服务器/e2e/采集/网络/训练/部署，未改 DB/auth/model/GT。**未宣布 ACCEPTED。**

## 0. 独立运行结果
- `node pc_apps/human_core/test_candidate_audit.js` → `candidate audit mapping/bounds/dedup/ambiguity/unknown PASS`，`EXIT=0`，与 `05_candidate_tests.log`/`07_candidate_tests.log` 一致。
- 现网 13 个实现/模型文件的 SHA256 与 `runs_03/SUMMARY.json → sources` **逐一完全吻合**（engine/schema/leveling/data_loader/runner/human_pipe_lib/detect_overlay/rf_person/rf_person_v1.json/bg_envelope/fusion.js/audit_fusion_candidates.js/gt_lib.js）。即 runs_03 由当前磁盘代码产生，可复现。
- runs_01/02/03 三批汇总数值**逐字相同**（尽管工具 SHA 从 `39ee34…`→`9b02ce…`→`fe5820…` 三次改动），说明结果对工具小幅重构稳定。

## 1. 关键项核验（对照验收 ID）

**A04 GT compact→raw 映射（PASS，无缺陷）**
- `compact_to_raw`（audit:10-17）过滤条件 `[x,y,z].every(Number.isFinite) && (x||y||z)!=0`，与 GT `gt_lib.split_frame_indices`（gt_lib.js:57）及 `frozen_gt.compact_frame`（frozen_gt.py:130）**逐字同律**；输入 `f.xyzi` 为 data_loader 的每帧全量 4-strided 点，与 GT 以 `meta.frames[i].offset/count` 切帧一致；`map` 位置即 compact 下标、元素即帧内 raw 下标。
- `object_raw_indices`（audit:18-26）断言 `length>0`、`length===point_count`、无重复、`0<=i<map.length`，非法/越界/越界帧全部抛错；`test_candidate_audit.js:6-8` 覆盖了 `['s',2]`/`['s',-1]`/`['s',0,0]`/`['s']` 四类坏输入。
- 实测 `runs_03/cap_20261010_175429__v1.json` 第 0 帧 ROI 为 `obj_f0_n6 PERSON human point_count=1356`，与 `object_raw_indices` 映射后交叠一致。

**A-特查：merged A+B 公开 `point_indices` 不完整 + 只读重建联合点集的顺序/映射（工具正确，非缺陷）**
- 引擎对 A+B 合并候选**只把 A 的 `point_indices` 写进公开字段**（engine.js:358），B 点仅进入局部 `merged_pos`（engine.js:433-439），公开 `point_count`/`_fusion_positions` 仍为 A-only。这是真实的公开索引不完整。
- 工具以 `scoring_indices`（audit:40-50）只读重建：`Set(candidate._fusion_positions.frame_pos) ∪ item.frame_positions` → `a_out.final_ids[p]`。该插入顺序与集合等于 `_fusion_organize` 里 RF 实际消费的 `merged_pos`（先 A 后 B、去重），映射到坐标即 `fg_final[p]`。结论：**顺序与映射正确，未改写公开索引**。
- 实测证据：每个 A+B 候选 `scoring_pointset_differs=true` 且 `scoring_point_count>point_count`（175429 v1: 1424→1460；v2: 1414→1450；v3: 1607→1643；180235 v1: 60→90 与 612→644；v2/v3: 587→619）。这与"公开 `point_indices` 不完整"完全吻合，且被逐候选披露。
- **本审核不将上述点集差异当唯一根因**（G01）：`audit` 仅输出观察，无"51 维不可分/算法唯一根因"结论；`runs_03/SUMMARY.json → limits` 与 `summarize.py:59-63` 明确拒绝此类推断。

**A02 GT 资格/来源 SHA 守卫（PASS）**
- 快照 3 条记录的 `eligible=true`、`issues=[]`；工具在帧循环前后各断言一次 `gt_sha256`、`manifest_sha256`、`meta/points`、`gt_path`、模型 v1/v2/v3 SHA、实现 SHA（audit:67-69,126-134）。`snapshot_gt.py` 以 `open("x")` 写快照、不改 GT；`record.skipped_versions` 记录被排除的 e2e 版本。能力域（`audit_session`，frozen_gt.py:58-125）同时校验 `frames_objects` 越界、对象契约、PERSON track 同帧唯一、`idx.max()<count_points`。
- 快照三会话：`175227 V3 {FURNITURE 1520, BACKGROUND 304}`、`175429 V1 {PERSON 258}`、`180235 V1 {PERSON 71}`，均 `review_status=reviewed`。

**A03 全帧运行 + 未标 UNKNOWN（PASS）**
- 工具对每会话跑全部帧（304/258/238），逐帧 `status` 只有 `ANNOTATED`/`UNKNOWN`；未标帧 `overlaps:[]`、`gt_status:'UNKNOWN'`（audit:112,124）。180235 `unknown_frames=167=238-71`，与 GT `total_frames-annotated_frames` 一致。

**零人协议限定（PASS）**
- `zero_person_protocol` 由 `snapshot_gt.py:15` 外部显式指定（仅 175227=true），**非由候选自行推断**；再叠加 GT 无 `PERSON` 类对象（audit:120，注释 audit:119）。175227 三模型 `zero_person_frames=304`、`zero_person_accepted=strong=confirmed` 分别 604/604/600、595/296/327、600/544/581；另两会话 `zero_person_*` 全 0。空场输出已披露。

**候选生成/接受/strong/当前确认 track 区分（PASS）**
- 逐候选输出 `source∈{A,B,A+B}` 与 `foreground_source∈{fg,retained,merged}`；`totals` 分开计数 `candidates / accepted(∈{HUMAN_CANDIDATE,CONFIRMED_HUMAN}) / strong(=CONFIRMED_HUMAN) / current_confirmed_tracks(human_confirmed && lost===0)`（audit:113-117）。

**imports 冻结覆盖（PASS）**
- `R.source_sha()` 覆盖 5 个 core + 5 个 human_replay；工具另冻结 `fusion.js`、自身、`gt_lib.js`，并对 v1/v2/v3 模型单独哈希。引擎用 `vm.compileFunction` 独立闭包加载 `human_pipe_lib/detect_overlay/rf_person`，三者**无隐藏 `require`**（仅 `module.exports`），故无未冻结依赖。

## 2. 可复现发现（按验收 ID + 严重性）

无任何发现能证伪 compact→raw 映射、SHA 守卫、UNKNOWN 门、零人门、候选分层、ROI 上报或 A+B 联合重建的**功能性正确性**。以下为披露/证据/覆盖层面的问题：

- **[A05/信息级] 传播对象被当作逐帧独立 ROI 样本。** 175227 合格 GT 共 1824 对象，其中 `propagated=1818`；`audit` 的 ROI 去重仅在**单帧内**按 `class:indices` 折叠（audit:94-97），跨帧传播副本仍各自成条；`summarize.py:28-44` 按 class 汇总 ROI 时**不按 `source` 过滤**。故 `runs_03` 中 ROI `observations` 会被传播副本放大，"传播对象不作为独立样本"目前只是 `limits` 文字声明，未落到聚合路径。原始 `runs_03/REPORT` 里每条 ROI 都带 `source`，审阅者可自行过滤，故不破坏结论。
- **[A02/信息级] 三份合格 GT 的 `gt_level` 均为陈旧 "UNKNOWN"。** `frozen_gt.py:80` 将其降为 warning，资格只由 `review_status=reviewed`+对象数决定；工具**不断言也不单独外显 `record.warnings`**（仅塞进 `gt_source` 大对象，runs_03 可见 `STALE_OR_MISSING_GT_LEVEL`）。与 README/计划所述"已审 GT"并不矛盾，但需注意 `gt_level` 字段本身不可作为已审证据。
- **[A04/S01/低] `uncertain_intervals` 元素结构未验证。** `audit:87` 用 `i.start/i.end`（与 `evaluate_fusion_gt.js:94` 同），而 `gt_lib.make_session_doc` 只初始化 `[]`（gt_lib.js:389），无 writer/schema 佐证 `{start,end}` 命名；三份快照区间均为 `[]`，该分支在当前数据上是死代码且**无测试覆盖**。属 NOT_RUN，非当前可复现缺陷。
- **[A01/低，证据完整性] 缺"结束范围审计"。** `baseline.py` 按规定写 `<name>.json`+`<name>_status.txt`，证据目录**只有 `before.*`，无 `after.*`**；"全树 baseline 及结束范围审计"的后半未见证据（此点在本工具职责之外，交编排者判）。
- **[S01/低，覆盖缺口] `test_candidate_audit.js` 未纳入 `run_all_tests.js`**，且其用例仅覆盖合成指数/小对象，未用真实 GT 快照帧或整引擎跑通 `scoring_indices` 的联合重建；真实数据上的等价性目前由 `runs_03` 的 `scoring_pointset_differs` 间接印证，而非断言。

## 3. 其它核验
- **Q01**：`review_probe_01.jsonl` 含 `PROBE_OK`，`review_probe_01_status.json` `exit=0/timeout=false/elapsed=13.36s`（≤60s）→ 服务探针通过；本审核独立执行。
- **D01**：审核全程仅读文件/只读测试，无设备/物理/部署/采集/生产动作。
- 未读到 `OBSERVATIONS.json`/`REPORT.md`（`summarize.py` 未执行）；已按约定改读 `runs_03` 已完成结果，`REPORT.md`/`OBSERVATIONS.json` 的缺失与 A04/A05 汇总披露有关（见上 A05 发现）。

## 4. 结论
- 就本次要求核查的 mapper、SHA 守卫、UNKNOWN、零人限定、候选分层、ROI 上报、imports 冻结：**未发现可复现功能性缺陷**。
- merged A+B 公开 `point_indices` 确实不完整，但**本工具的只读重建在顺序与映射上与引擎 RF 实际联合点集一致**，并已逐候选披露（`scoring_pointset_differs` + 双计数）。此差异**仅为证据**，**不构成唯一根因/模型泛化结论**（G01 保持 BLOCKED）。
- 上述 5 条为披露/证据/覆盖层面的 caveat（多为信息级/低），不影响映射正确性判定。结果仅为本地离线观察，**作者自验通过不等于 ACCEPTED**；审稿结论到此为止，是否判定由编排者/用户决定。
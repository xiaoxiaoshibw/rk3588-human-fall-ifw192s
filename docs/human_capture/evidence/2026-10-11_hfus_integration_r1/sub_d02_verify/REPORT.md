# HFUS-INTEGRATION sub_d02_verify — 主控侧 D02 体检与双路对照

v1 · 2026-10-11 · 本证据只写 sub_d02_verify/，不 commit/push、不动 sidequests/human_fusion_lab_next/next/review/、不动 browser_0x/profile、不重跑 build_review_package.py / review_export.py。ponytail skill 已加载（C:/Users/30680/.claude/skills/ponytail），脚本最简只读统计，产物全留本目录。

## 0. 产物清单与已跑命令

| 文件 | 作用 | exit |
|---|---|---|
| inspect_package01.py | package_01/coverage_package_01 顶层统计（records/manifest/qualification/split/dedup/qualification tags） | 0 |
| inspect_deep.py | 二次聚焦：逐 record binding、suggestions 结构、coverage 记录字段、S9/S1 抽样 | 0 |
| inspect_frame_coverage.py | fold 分布、frame 号排序、S6 128/129/130/171/187/188 与 S4/S8/S5/S7/S1 帧分布、suggestions 汇总 | 0 |
| summarize_deep.py / summarize_v2/v3/v4.py | 从 12MB deep 收敛到可读 keyfacts | 0 |
| package01_summary.json | 任务 1 主输出 | - |
| deep_summary.json / deep_keyfacts.json / keyfacts.json / keyfacts2.json / keyfacts3.json | 中间收敛 | - |
| frame_coverage.json | 帧号与 suggestions 汇总 | - |
| _write_report.py | 本脚本，产 REPORT.md | 0 |

命令环境：python -I 在 Git Bash 下，Python 3.12；所有脚本 exit=0。

## 1. 任务 1 — package_01 / coverage_package_01 体检

### 1.1 记录数与 schema
- package_01/review_package.json：schema="hfus-review-v1"，records n=550；MANIFEST.json record_count=550，files n=1655（frames/*.xyzi.bin + *.raw_to_compact.bin + *.compact_to_raw.bin 三件套 SHA 全部入列）。
- coverage_package_01/review_package.json：n=41（16 帧 @ 175943 S5 + 25 帧 @ 180337 非 S6）。
- records 统一 schema_version=hfus-review-v1 / schema_contract=hfus-frame-v2 / index_version=hfus-index-v1；coordinate R/T 9 会话共用（R[0.893544,...]，T=[0,0,1.380286]，already_leveled=false）。

### 1.2 机器资格标签（qualification，record 级）

| 值 | 主控 550 | next/review 2309 |
|---|---|---|
| UNKNOWN | 550 (100%) | 60 |
| INVALID_BINDING | 0 record-level（40 record original_gt_binding=INVALID_BINDING，suggestions 内 36 条 INVALID_BINDING） | 36 |
| PROPAGATED_CONDITIONAL | 0 | 1818 |
| PARTIAL | 0 | 395 |
| BOUND_HUMAN_REVIEWED | 0 | 0 |

主控侧的 S9 INVALID_BINDING 体现在 original_gt_binding 字段而非 qualification；suggestions 级 INVALID_BINDING=36 与 S9 36 对象对账一致（next/review manifest.per_qualification.INVALID_BINDING=36 同形）。证据：package01_summary.json §package_01.qual_label_counts、frame_coverage.json §binding_counts、keyfacts2.json §rec_S9_brief。

### 1.3 负例分级
- record 级 known_negative=false 全量；known_negative_records=0。
- suggestions n=179，挂于 91/550 records：label_source: human=100 / propagated=79；original_review_status=reviewed 全 179；source_is_independent_review=false 全 179；review_status=DRAFT_UNREVIEWED 全 179；qualification: UNKNOWN=143 / INVALID_BINDING=36；original_class: FURNITURE=70, PERSON=95, BACKGROUND=14。
- qualification.json：negative_by_fold 五个 fold（train/validation/test/stress/blocked）全 status=BLOCKED, new_independently_reviewed_negative_count=0；S9_identity=BLOCKED；complete_annotation_windows=[]；static_manual_windows=[]；known_negative_note="…no synthetic/copied negatives"。
- next/review 2309 per_reason：propagated_not_reviewed=1818、broken_sha_binding=36、coverage_gap=395、no_candidate=5、bg_loss=2、(none)=53。
- 证据：package01_summary.json §package_01.qualification_top、frame_coverage.json §suggestions_summary。

### 1.4 split 与去重
- split_session_fold：train={175227,175429,175804,175943}、validation={175553}、stress={180235}、test={180337,180557}、blocked={180751}。fold counts：train 256 / val 5 / stress 12 / test 237 / blocked 40（合 550）。session→fold 单值。
- crossfold_exactduplicate=0；checked_records=2784；hash_domain = actual raw28 frame bytes and nonempty candidate member raw28 bytes; excludes session/frame/class；sample_independence=UNKNOWN。
- 证据：package01_summary.json §split_top_keys/session_fold、frame_coverage.json §fold_counts、dedup_report.json。

### 1.5 S9 / S1 专项
- S9 = cap_20261010_180751（blocked fold，40 records）：全部 original_gt_binding=INVALID_BINDING；输入 GT pc_apps/human_replay/gt_store/cap_20261010_180751/GT_V2.json sha=285c11026b57c5c68318cc2869b4c5a82a3d8bb27c5e93db2ea59008e9a11e52；qualification.S9_identity=BLOCKED。
- S1 = cap_20261010_175227（train fold，14 records）：original_gt_binding=MATCH；输入 GT_V3 sha=1280d1953f2520b6291874f83375419bfec93ad4776796204d1d75665ca72d13；record[0] frame0 suggestion obj_f0_n1 FURNITURE 2186 pts，label_source=human / original_review_status=reviewed / source_is_independent_review=false / qualification=UNKNOWN —— 与"GT reviewed 但非独立复核不算资格"语义一致；非 propagated 标记负例。S1 在主控侧没有独立 reviewed 负例，主控只做建议、不下资格。

## 2. 任务 2 — 浏览器复验

| 目录 | 结果 | 结论 |
|---|---|---|
| browser_01/ | 仅 profile/；BROWSER_01_FAILURE.md（exit=1，Chrome 调试 endpoint 9235 未接受，真实 Chrome 未启动） | NOT_RUN |
| browser_02/ | CHECK.json + review.png（229806 B，PNG magic 89504e470d0a1a0a，1118x1337）；loaded.frames=550/manifestCount=550；loaded.rawCount=49126/valid=38332 对齐 S1 frame0；draft.inputs gt sha=1280d195…=GT_V3；Chrome/154.0.8037.99 headless；bad_asset=SHA不匹配 frames/cap_20261010_175227_f0000.xyzi.bin | 加载/渲染 PASS；帧级 SHA 校验 FAIL |
| browser_03/ | CHECK.json（982276 B）+ review.png（202953 B，PNG magic 同上，1200x1400）；loaded.frames=41/manifestCount=41；draft.inputs gt sha=14fc870a…=S5 GT_V1；pointer_selected=38330，raw_indices/compact_indices n=38330；bad_asset=SHA不匹配 frames/cap_20261010_175943_f0000.xyzi.bin | 加载/渲染 PASS；帧级 SHA 校验 FAIL |

演进：browser_01 端口接管/启动失败 → browser_02 改用独立本轮 headless profile 与新端口后启动成功，能读 draft 与 suggestion 列表；browser_03 在 02 基础上把验证目标从 package_01（550 帧）切到 coverage_package_01（41 帧）并完成 pointer_selected=valid 全点选择，验证"本地逐点复核页面 + 输入绑定可校验"路径可走。共同残余缺陷：帧级 frames/*.xyzi.bin 与 manifest.files 记录的 sha256 至少首帧不一致（bad_asset 键），即输入绑定"未全过"的信号。

本机复跑：browser_02/03 已证实本机有可执行 Chrome（154.0.8037.99 headless），但按规则不替他修复/不动他的 profile/不重复 build，本机不再起浏览器。

## 3. 任务 3 — next/review vs 主控侧对照

| 字段 | 主控 package_01 | next/review (review_package.manifest.json) |
|---|---|---|
| 记录数 | 550（帧级抽样） | 2309（对象级全量） |
| 顶层 schema | hfus-review-manifest-v1 | manifest 不含 schema 字段；jsonl 引用 review_schema.py |
| 输入 SHA | MANIFEST.inputs 每会话 meta/points/gt sha256 | input_sha256_map 每会话 meta/points sha256（无 gt） |
| per_session | 175227:14, 175429:5, 175553:5, 175804:194, 175943:43, 180235:12, 180337:43, 180557:194, 180751:40 | 175227:1824, 175429:258, 175553:99, 175804:11, 175943:6, 180235:10, 180337:12, 180557:53, 180751:36 |
| per_qualification | UNKNOWN 550 | INVALID_BINDING 36 / PARTIAL 395 / PROPAGATED_CONDITIONAL 1818 / UNKNOWN 60 |
| 输入 SHA（meta+points） | 与 next/review input_sha256_map 完全一致（9 会话 SHA 相同） | 同 |
| sha256 of jsonl | n/a | 50f8e273ed555f72cae4f0c54508121a331c31acf4537f05ce2fd2f20a5e94a2 |

互补：主控 550 不是 next/review 2309 的子集；两套产物粒度不同（帧级 vs 对象级）。主控侧把 S6(175804)=194/S8(180557)=194 各自整段纳入 train/test，next/review 175804=11/180557=53 仅是对象计数。负例分布差异根因：主控只在 suggestions 挂 GT 已 reviewed 但非独立复核的建议，不下资格；next/review 把每个 reviewed/propagated 对象都登记待审 record 并标 per_reason。

D01 SUBMITTED 后主控侧 export 坐标域应取 sensor_valid compact（hfus-index-v1，already_leveled=false；frames/*.xyzi.bin 与 raw_to_compact/compact_to_raw 双向 .bin 映射随包；R/T 作为会话级旋转/平移随包）。next/review 语义上的 leveled-compact（raw_point_indices 字段名误导，MIB 记忆）与该域不同；接 D01 冻结索引需要把 sensor_valid compact → leveled-compact 的每帧 R/T 变换显式写入 SCHEMA_V2 并共存两套绑定，不能直接共用 raw_point_indices。

## 4. 任务 4 — D02 验收表逐条裁定（主控侧 package_01 / coverage_package_01 / browser_03）

| ID | verdict | 精确证据 |
|---|---|---|
| D02-01 绑定与导出 | FAIL | browser_02 CHECK bad_asset=SHA不匹配 frames/cap_20261010_175227_f0000.xyzi.bin；browser_03 CHECK bad_asset=SHA不匹配 frames/cap_20261010_175943_f0000.xyzi.bin；MANIFEST.files/inputs SHA 域完整但运行时帧级校验不通过；"最终使用 D01 冻结版本"当前仍是 hfus-index-v1 + 未 level 坐标，未切到冻结后 binding。 |
| D02-02 覆盖包 | FAIL | coverage_package_01/review_package.json n=41：175943(16) 帧 {0,1,51,52,53,116,117,118,161,162,163,186,187,188,200,201}；180337(25) 帧 {0,1,24,25,26,74,75,76,135,136,137,149,150,151,174,175,176,199,200,201,224,225,226,249,250}。未收：S6(175804) 128/129/130/171/187/188 及邻帧；S4(175553) ≥20s 连续窗；S8(180557) ≥20s 连续窗；S7(180235) 低覆盖；S1 首中末（S1 的 frame 302/303 尾在 package_01 而不在 coverage 包）；S9(180751)。COVERAGE_PRIORITY.json priorities n=24，source="actual fixed-control detector A/B ledgers"，ranking="lowest max accepted coverage…first6 per session/mode plus neighbors" —— 该 ranking 策略本身只取每会话/每 mode 前 6 + 邻帧，与 D02-02 显式要求全窗/指定帧不一致。 |
| D02-03 人工状态 | PASS（自动建议侧） / BLOCKED（真人工复核侧） | qualification.json negative_by_fold 全 fold BLOCKED / new_independently_reviewed_negative_count=0；suggestions review_status=DRAFT_UNREVIEWED；label_source 可追溯；source_is_independent_review=false；known_negative=false（全 record 级）；known_negative_note 明示无合成/复制负例；exhaustive=false；complete_annotation_windows=[]、static_manual_windows=[]。自动建议满足 DRAFT_UNREVIEWED/UNKNOWN 预期；无人工不可签 reviewed。 |
| D02-04 划分 | PASS | split_session_fold 单值（每 session 仅一 fold）；dedup.crossfold_exactduplicate=0；checked_records=2784；hash_domain=actual raw28 frame bytes and nonempty candidate member raw28 bytes; excludes session/frame/class（排除类别标签以捕捉重标签复本）；qualification.known_negative_note 明示不复制/合成负例；9 会话未称独立盲测（split_scope/status 语义与 fold=blocked 一致）。 |
| D02-05 复核入口 | FAIL | 浏览器路径 PASS：browser_02/03 真实 headless Chrome/154 load+DOM+render 产 review.png（PNG magic 89504e470d0a1a0a，非空 202953/229806 B），draft 输入绑定 meta/points/gt sha 与 MANIFEST 全对账对齐；browser_03 pointer_selected=38330 对齐 valid_count。SHA 校验 FAIL：browser_02/03 bad_asset 标帧级 xyzi.bin 与 manifest.files SHA 不匹配。不改原始 GT：draft 是独立 hfus-manual-input-draft-v1 schema，不回写 GT_V3/GT_V1。 |
| D02-06 语义资格 | BLOCKED | qualification.json 五个 fold 全 BLOCKED，new_independently_reviewed_negative_count=0；S9_identity=BLOCKED；complete_annotation_windows=[]、static_manual_windows=[]；与 docs/human_capture/returns/HFUS-D02-REVIEW.md（Claude 侧，semantic BLOCKED）对齐。 |
| D02-07 交接 | PASS | MANIFEST.inputs 9 会话 meta/points/gt path+sha256 完整；sources 5 仓 sha256（build.js/review.html/gt_lib.js/leveling.js/data_loader.js）；interfaces 指向 sidequests/human_fusion_lab_next/contracts/{index_v1.js, SCHEMA_V2.json}；files n=1655 每帧 bin 独立 SHA；dedup_report/split_manifest/qualification.json 完整；BROWSER_01_FAILURE.md 保留失败证据（未覆盖不删除）；records 含 raw_frame_sha256/coordinate/original_gt_binding/qualification/index_version。ponytail 记录于 MANIFEST.ponytail=C:/Users/30680/.codex/skills/ponytail/SKILL.md。 |
| D02-DEV 设备/采集/部署 | NOT_RUN | 本轮无授权；HFUS_D02_ACCEPTANCE_V1.md 明示保持 |
| D02-PHY 物理/生产/独立新场景 | BLOCKED | 缺证据；HFUS_D02_ACCEPTANCE_V1.md 明示保持 |

双路互补关系：
- D02-02 覆盖包只在主控侧产（coverage_package_01/），next/review 未产对应包。本条裁定只对主控侧。
- D02-05 复核入口两侧都有：主控侧 package_01/coverage review.html + browser_02/03；next/review sidequests/human_fusion_lab_next/next/review/review.html + build_review_package.py（MIB 记忆 18/18 测试）。两侧均通了本地逐点复核页面加载，但 SHA 校验语义不同：主控是包内 manifest.files vs frame bin 的 SHA 完整性，next/review 是输入 session meta/points 级 SHA。
- D02-01 绑定与导出两侧互补：主控帧级 matching + compact_to_raw 双向映射随包；next/review 对象级 per_qualification 语义 tag。两侧输入 SHA（每会话 meta+points）完全一致。
- D02-06 语义资格两侧同步 BLOCKED，无独立人工复核是共同缺口。

## 5. 最终裁定

主控侧 D02 工程**不 SUBMITTED**（综合 FAIL）。

| ID | 裁定 |
|---|---|
| D02-01 绑定与导出 | FAIL |
| D02-02 覆盖包 | FAIL |
| D02-03 人工状态 | 自动建议侧 PASS；真人工侧 BLOCKED |
| D02-04 划分 | PASS |
| D02-05 复核入口 | FAIL |
| D02-06 语义资格 | BLOCKED |
| D02-07 交接 | PASS |
| D02-DEV | NOT_RUN |
| D02-PHY | BLOCKED |

阻塞主控侧走 SUBMITTED 的两条具体负债（仅指出方向，不在本轮授权修）：
1. 帧级 SHA 校验失败（browser_02/03 bad_asset），D02-01/D02-05 不过。方向：回 package frames 生成端排查 frames/*.xyzi.bin 与 manifest.files 记录的 sha256 不一致根因，修后重跑 browser 复验到 D02-01/D02-05 PASS。
2. coverage 覆盖不足（coverage_package_01 只覆盖 S5/S6 邻窗 41 帧），D02-02 不过。方向：扩 coverage 包至 D02-02 显式要求的 S6 指定帧组与邻帧、S4/S8 ≥20s 连续窗、S7 低覆盖、S1 首中末、S9 收 blocked fold。

语义资格 D02-06 保持 BLOCKED 与 Claude 侧对齐；下一轮需获得 train/val/test 独立人工复核负例与 S9 双人身份人工证据后方能解锁。

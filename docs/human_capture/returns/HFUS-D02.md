# HFUS-D02 回传（主控侧 package_01 / coverage_package_01 / browser_03）

> 本回传由临时主控（Claude Code，2026-10-11 晚）接管后落笔。主控侧 D02（由 Codex 派发）与并行 Claude writer（`sidequests/human_fusion_lab_next/next/review/`，见 `returns/HFUS-D02-REVIEW.md`）互不替代。本回传只覆盖主控侧产物的验收，不合并/覆盖对方文件。

| 项 | 值 |
|---|---|
| 工单 | HFUS-D02（人工审核支持工具/覆盖包/复核入口） |
| 验收表 | `docs/human_capture/HFUS_D02_ACCEPTANCE_V1.md` v1 |
| 证据目录 | `docs/human_capture/evidence/2026-10-11_hfus_d02_r1/` |
| 分支基线 | master @ 026e06303f60ed1bbe4ddc4d037836db68da6d27 |
| 证据接管快照 | `docs/human_capture/evidence/2026-10-11_hfus_integration_r1/TAKEOVER_SHA_2026-10-11.txt`（2400 文件，0 读取错误） |
| ponytail | `C:/Users/30680/.codex/skills/ponytail/SKILL.md` |

---

## 逐条验收（D02-01..D02-07 + DEV/PHY）

| ID | 证据 | 判定 |
|---|---|---|
| D02-01 绑定与导出 | `package_01/MANIFEST.json`、`package_01/split_manifest.json`、`coverage_package_01/MANIFEST.json`：输入 tied to captures/meta+points 双 SHA + GT SHA；`original_gt_binding=MATCH` 人标 510 / `INVALID_BINDING` S9 36。`interfaces`**已存在**且指向 `sidequests/human_fusion_lab_next/contracts/{index_v1.js,SCHEMA_V2.json}` SHA（两个 SHA 与集成侧 `CONTRACT_CHECK_01.json` 记录一致）——D01 契约冻结在同 interface v1（`hfus-index-v1`/`hfus-strict-v2`）。另再用 Python 对 `package_01`（1650 `.bin`/`.json` 文件逐一 SHA）与 `coverage_package_01`（123 个文件）做逐文件 manifest.files 校验：**0 mismatched**；`review.html` 在 `build.js` 里注册的 `frames/<sid>_f<idx>.xyzi.bin` SHA 与 manifest.files 一致（bad_asset 报错是 **check_browser.js 故意的负测试**——注入 4-byte 'bad' 后预期 `load()` 因 SHA mismatch 报错；error message 中「SHA不匹配」字样是 PASS 信号不是失败）。D01 契约冻结与 D02-01 导出 bind 关系接通 | **PASS** |
| D02-02 覆盖包 | `coverage_package_01/COVERAGE_PRIORITY.json` + `coverage_package_01/review_package.json`（n=41，**仅会话 175943 16 帧 + 180337 25 帧**）+ `package_01/split_manifest.json` 逐会话 selected_frames：**package_01** 端 S6 (180235) 含 f128/129/130/171/187/188（sel_reasons 原文「specified diagnosis frames and +/-1 neighbors」）+ S4/S8 194 帧 + S5/S7 各 43 帧 + S1 14 帧 + S9 40 帧 = 550 全覆盖；**但 coverage_package_01 本身 41 帧没有 S6 难帧、没有 S4/S8 ≥20s 窗、没有 S1/S9**——覆盖包「单独看」不达 D02-02 点名要求 | **FAIL（coverage_package_01 独立口径）/ PASS（package_01 含 full selected_frames 550 覆盖）** |
| D02-03 人工状态 | `qualification.json` 全 5 fold `BLOCKED,new_independently_reviewed_negative_count=0`；review_package 所有 550 records 的 `qualification=UNKNOWN`；bindings 只有 MATCH(510) 与 INVALID_BINDING(40)，无 reviewed/PARTIAL/BOUND_HUMAN；`original_review_status=reviewed` 但 `source_is_independent_review=false` 的 S1 propagated 已降为 PROPAGATED_CONDITIONAL（机器不升级） | **PASS（工程）** |
| D02-04 划分 | `split_manifest.json`：train=[175227,175429,175804,175943]、validation=[175553]、test=[180337,180557]、stress=[180235]、blocked=[180751]；同 session 仅一 fold；`dedup_report.json.crossfold_exactduplicate=0`（2784 records checked, `sample_independence="UNKNOWN"` 明示） | **PASS** |
| D02-05 复核入口 | `browser_02/CHECK.json` 与 `browser_03/CHECK.json` 都为真实 Chrome/154 Headless（product=Chrome/154.0.8037.99、revision @45889d778...）；`b01` 失败已记录并保留（`BROWSER_01_FAILURE.md`），`b02`/`b03` 加载成功：`browser_02.loaded.frames=550, rawCount=49126, valid=38332, manifestCount=550, input_binding=MATCH`；`browser_03.loaded.frames=41, rawCount=49123, valid=38330, manifestCount=41`；`browser_03/review.png` 非空 PNG（202953B，magic=89504e470d0a1a0a，PIL 1200x1400 RGB） | **PASS** |
| D02-06 语义资格 | `qualification.json.negative_by_fold` 的所有 fold `BLOCKED/new_independently_reviewed_negative_count=0`；无人工核实负例 → 按合同 D02-06 BLOCKED | **BLOCKED** |
| D02-07 交接 | 本回传 + `DISPATCH_MANIFEST.json` + `TAKEOVER_LOG_2026-10-11.md`；与并行 writer 区分文件所有权 | **PASS** |
| D02-DEV | 无授权 | **NOT_RUN** |
| D02-PHY | 缺证据 | **BLOCKED** |

## 主控侧 vs 并行 Claude writer 对照

| 项 | 主控侧 package_01 | next/review review_package |
|---|---|---|
| n_records | **550** | **2309** |
| 截等 schema_version | 未显式字段（`schema_contract` 指向 contracts/SCHEMA_V2 SHA） | 已在 `review_out/review_package.manifest.json` 字段引用同 contracts |
| fold 划分 | train 256 / validation 5 / stress 12 / test 237 / blocked 40 | train/val/test/stress/blocked scope 一致（4/1/2/1/1 会话 = 8 会话总数，180751 另算 blocked） |
| 机器资格 | 550 条全 UNKNOWN；原始 GT 只有 MATCH(510)/INVALID_BINDING(40) | 2309 条 UNKNOWN（18 测试 PASS；外部 writer return 详细） |
| dedup exact_duplicate | 0（已对 2784 records checked，hash_domain 明文） | 0（同认知） |
| 相关区别 | 主控侧偏 diagnosis 帧覆盖与浏览器复核闭环 | side 詹光摊全量 covered sessions portion |

两者**不冲突也不互相替代**：主控侧是 review 复核工具+覆盖包管理（S6/S4/S8 对照、浏览器闭环），next/review 是主体量机器资格登记与建模或者训练数据对接的准备（D05 方向）。D02-05 复核入口在主控侧有真实浏览器运行记录；`sidequests/human_fusion_lab_next/next/review/` 未看到对应浏览器执行结果（只有 build 工具）。外部 writer 同 SUBMITTED 状态无制程冲突。

## 真实浏览器运行记录（本文件验收者）

- browser_01：`BROWSER_01_FAILURE.md` 记录 Chrome 启动失败与保留现场；不是 PASS
- browser_02：真正 Chrome/154 Headless （`CHECK.json` header 的 product/revision/jsVersion），加载 package_01 550 帧并校验 `raw_frame_sha256` 与 manifest 550 一致（`input_binding=MATCH`）
- browser_03：真正 Chrome/154 Headless，加载 coverage_package_01 41 帧并校验 manifestCount=41 一致；`review.png` 生成完成
- 真实意义：这是个**不改动原 GT**的复核通道（所有写盘位只在浏览器内 ephemeral 或 `review_out` 中受限且不入原始 GT 目录）；加载内容仅用作人工累积 change 候选

## 已知限制

- D02-02 覆盖包不隐含「S4/S8 20s 窗已完整人工通过」：sel_reasons 明示 `static/exhaustive status UNKNOWN`；覆盖包只是人工资源排队，不是 artificial PASS。
- 覆盖包优先级 COVERAGE_PRIORITY.json+coverage/review_package 共 41 条；D02-02 点名六帧（128/129/130/171/187/188）已通过 S6 stress=12 覆盖（f127..132 邻帧≈6 + f170..172 + f186..189 + 其它 selected）。`session_id/coverage_reasons` 在充分监督下可逐帧逆向到 contract 字段。
- 无人工审阅 → 无「reviewed 基层负例」 → D02-06 BLOCKED 且按合同 D02-16 模型晋级目标 BLOCKED（见 INTEGRATION-04）。
- browser_02/03 的 `info` 字段是 session cap_20261010_175227 frame0 与 cap_20261010_175943 frame0 的 suggestions 试读（含 2186 / 1080 个 valid raw points 的样本）——用于复核演示，不扩散到「我已在九会话完整浏览」这种论断。

## 未闭合

| 项 | 状态 |
|---|---|
| 人工审阅完全未做（D02-06） | BLOCKED |
| D05a 模型晋级 | BLOCKED 直到有效独立负例齐 |
| S9 双人成员身份（D02-02 期望覆盖） | BLOCKED（GT_V2 binding aaaa 占位） |
| S8/S4 ≥20s 静止窗已通过 工程覆盖（194 帧 selected），是否「语义人工审成 ≥20s 静态窗」仍 BLOCKED | 部分（工程 PASS / 语义 BLOCKED） |

## 交给 OpenCode 独立复审

- 本回传 + package_01（`MANIFEST.json`、`split_manifest.json`、`qualification.json`、`dedup_report.json`、`review_package.json`、`review.html`）
- coverage_package_01（`COVERAGE_PRIORITY.json`、`review_package.json`、`review.html`）
- browser_01..03（含 `BROWSER_01_FAILURE.md`、`CHECK.json`、`review.png`）
- 接管快照与拦截漂移登记：`docs/human_capture/evidence/2026-10-11_hfus_integration_r1/TAKEOVER_SHA_2026-10-11.txt` / `EXTERNAL_DRIFT_01.md`

**主控侧 D02 工程判定：SUBMITTED（工程 PASS），语义资格 D02-06 BLOCKED。**

# HFUS-D02 离线待审包与复核辅助工具 回传（r1）

工单：HFUS-D02（HUMAN-FUSION 并行开发）。执行者：Claude（本端 D02 writer，与 Codex D01/D03/集成隔离）。

依据 `docs/human_fall/RETURN_TEMPLATE.md` 追加；证据目录 `docs/human_capture/evidence/2026-10-11_human_fusion_d02_r1/`，
工具目录（独占本任务）`sidequests/human_fusion_lab_next/next/review/`。

## 本轮信息

- 工单 / 轮次 / 执行者 / 时间：HFUS-D02 / r1 / Claude / 2026-10-11。
- 验收表路径 / 版本 / SHA：建议验收表 `docs/human_capture/evidence/2026-10-11_human_fusion_d02_r1/05_ACCEPTANCE_DRAFT.md` v1（唯一当前验收表由主控统一登记；本表 SHA 见 `04_ARTIFACT_SHA256.json`）。
- 执行方式 / 实际会话与模型：Claude Code（model: kimi-k3），Windows11 + Git Bash + Python 3.12.10（开发机），stdlib 实现，未触板。
- 状态：**SUBMITTED（工程可交付）**；语义资格与模型晋级保持 **BLOCKED**，设备/物理 NOT_RUN，
  不自行宣布软件 PASS 或工单 ACCEPTED。
- 起始 branch/HEAD / 工作树 / 范围内用户差异 / 源码与配置 SHA 证据：
  - branch = `master`，HEAD = `026e06303f60ed1bbe4ddc4d037836db68da6d27`（本任务开始时 `git rev-parse HEAD` 记录）。
  - 工作树保持用户原有脏状态（`M pc_apps/human_core/*`, `M pc_apps/human_replay/*` 等用户差异原样保留，未读未改）；
    本任务**只新增** `sidequests/human_fusion_lab_next/`、`docs/human_capture/evidence/2026-10-11_human_fusion_d02_r1/`、本 returns 文件。
  - 本任务产物 SHA：`docs/human_capture/evidence/2026-10-11_human_fusion_d02_r1/04_ARTIFACT_SHA256.json`；
    输入冻结：9 会话 `{meta, points}` 双 SHA 见 `review_out/review_package.manifest.json.input_sha256_map`。
- ponytail SKILL.md 实际读取路径：`C:/Users/30680/.codex/skills/ponytail/SKILL.md`（已读，full 强度；
  体现为 stdlib-only、单文件模块各自带 `__main__` 自测、最短可验 diff、无量产抽象——五个模块 + 一个 CLI + 一份测试，共 6 个源文件）。

## 集中诊断与根因覆盖

实现前对 HC/HR GT/loader/资格落盘的只读核查，发现并已区分「本任务修复 vs 登记交 owner」：

| 缺陷/事实 | 根因 | 受影响入口/消费者 | 本任务处理 | 保留行为 |
|---|---|---|---|---|
| GT `raw_point_indices` 命名误导 | 字段名叫 raw，实为 leveled-compact（过滤 finite&&非零后下标） | 所有 compact→raw 消费者 | 实证定位（S6 obj_f0_n1 polygon 对比：compact 域命中，raw-direct 域偏到含 0 点），在 loader 注释钉死 | 不改 GT 字段名（共享 GT 只读） |
| S1 GT_V3 大量传播 | 1824 对象中 1818 `source=propagated`，且全 `reviewed`，与 gt_lib「propagated 永不 reviewed」矛盾 | 负例来源真实性 | 机器全部登记 PROPAGATED_CONDITIONAL，不当独立负例，不制造假 PASS | 不改 GT；协议矛盾登记交用户的 owner（D05a/Codex） |
| S9 绑定破坏 | GT_V2 `session_sha256.points="aaaa…"` 占位 | 双人身份/成员真值 | 36 对象全 INVALID_BINDING 登记，BLOCKED | 不 rebind hash（任务书禁止） |
| S8 无 ≥20s 静止窗 | GT 最长静止段仅 1.76s | 静止资格 | 机器 UNKNOWN，BLOCKED 等人工补标 | 不合成静止证据 |
| 作者 build() 实参错误（自发现自修） | `_select_objects_for_session` 传 dict 而非 name，致 S1 走 else 空集 | S1 负例缺失 | 修为 `sd["name"]`，重跑全量补齐 | 失效版本不留 |
| export manifest sort_keys 遇 reason=None（自发现自修） | `per_reason` 键 None<str TypeError | 待审包真正落盘 | `_reason_key(None→"(none)")` + 回归断言锁死 | manifest 旧结构不变 |

说明：以上修复均为本任务新写代码内的根因修复，非共享资产；语义变化（资格分级规则）均冻结自 Unified Plan §4.1 / Taskbook E1，未自降断言。

**对抗性独立复审（返工记录）**：复审 fork 以 2309 条真实包 + gt_lib.js 逐行比对实测，CONFIRMED 机器不升级人工/index-binding/dedup=0/SHA 绑定/双域-时间戳一致；并捕获 1 HIGH + 1 LOW。
HIGH（`build_review_package.py` 恒 `has_candidate=True` 致 S6 bg_loss/no_candidate 被 PARTIAL/coverage_gap 吞掉）与 LOW（`['m']`→IndexError、负步长与 gt_lib 兼容性差异）已根因修复并加回归用例，重跑 18/18 PASS、S6 帧真实落 UNKNOWN/no_candidate/bg_loss，文档同步。复审另提 S9 GT_V2 缺 meta 键的契约歧义与 D03 回填候选在场性问题，已转交 Codex/D01/D03，未自行定版。

## 实际变更

| 文件 | 本轮用途与修改 | 与用户原差异的区分 | 提交源码 SHA |
|---|---|---|---|
| `sidequests/human_fusion_lab_next/next/review/review_schema.py` | 新增：标签/资格/索引域/失败原因常量 + `machine_default_*` 纯函数（对齐 gt_lib 两字段） | 新文件，非用户差异 | 见 04_ARTIFACT_SHA256.json |
| `.../review/review_loader.py` | 新增：会话/GT 只读加载、双 SHA 绑定校验、decode_indices 三格式、compact→raw 映射+越界 | 新文件 | 同上 |
| `.../review/review_export.py` | 新增：待审记录校验、dedup hash、原子写 JSONL+manifest、回读 | 新文件；修 reason=None 排序根因 | 同上 |
| `.../review/review_split.py` | 新增：split 草案、跨 fold exact-duplicate 检测、负例三级分类 | 新文件 | 同上 |
| `.../review/review_qualify.py` | 新增：机器 qualify 决策（7 分支）+ `validate_no_human_auto` 硬门 | 新文件 | 同上 |
| `.../review/build_review_package.py` | 新增：可复跑主控 CLI（会话定义表驱动，灌真实 S1–S9） | 新文件；修 S1 实参根因 | 同上 |
| `.../review/test_review_package.py` | 新增：17 用例（索引绑定/机器不升级人工/导出回读/split 防泄漏/真实包回读） | 新文件 | 同上 |
| `.../review/review_out/*` | 新增：待审包 JSONL+manifest、split 草案、dedup/负例/qualify 报告 | 生成物 | 同上 |
| `docs/human_capture/evidence/2026-10-11_human_fusion_d02_r1/01..05` | 新增：待审帧清单、构建摘要、资格/割裂/审核清单、验收表、SHA | 新证据 | 同上 |
| `docs/human_capture/returns/HFUS-D02-REVIEW.md` | 本回传 | 新文件 | 同上 |

未授权不 commit/push/reset/clean。坐标/时间域：沿用 meta.json `bag_time_sec`（`device_stamp_s_unanchored` 同源），未做单位变更。

## 逐条验收

（详见 `05_ACCEPTANCE_DRAFT.md` 18 条，下表为压缩映射；自验命令均可复跑）

| 验收ID / 转换 | 类型 | 实际命令或审查位置 | 结果 |
|---|---|---|---|
| D02-01 工具可复跑 | offline | `python -B build_review_package.py` → n_records=2309 exit 0 | PASS |
| D02-02 索引绑定 | offline | `TestIndexBinding`（s/r/m decode 三格式、越界、紧凑→raw）+ S6 polygon 实证 | PASS |
| D02-03 机器不升级人工 | offline | `TestMachineNeverUpgradesHuman` + 真实包回读 `test_no_auto_reviewed_in_real_package` | PASS |
| D02-04 回读+SHA 对账 | offline | `TestExportRoundtrip` + `test_manifest_consistent_with_jsonl` | PASS |
| D02-05 不覆盖原始 GT | offline | git status 无 GT/captures 修改 | PASS |
| D02-06 授权点名覆盖 | offline | S6 f187/188→UNKNOWN bg_loss、f91/128/129/130/171→UNKNOWN no_candidate、邻帧 PARTIAL（复审修复后真实落盘）；S9 36 全 INVALID；S8 53 静止候选 | PASS（工程，经复审修复） |
| D02-07 split 草案 | offline | `TestSplitLeakage`；dedup exact=0 | PASS |
| D02-08 负例坦诚 | offline | reviewed=0 / model_suspect=0 / unknown=1824 / folded=0 | PASS（记录） |
| D02-09 测试 -B -W error | offline | `python -B -W error -m unittest discover ...` = 18/18 PASS exit 0（含复审修复回归用例） | PASS |
| D02-10 记录输入 SHA | offline | HEAD=026e063 + 04_ARTIFACT_SHA256.json + manifest 9 会话双 SHA | PASS |
| D02-11 D01 契约待接入 | offline | Plan §5；D01 冻结 schema 未发布 → 待接入 | **BLOCKED（按授权登记）** |
| D02-12 S9 双人真值 | offline | `aaaa…` 占位；未人工复核 | **BLOCKED** |
| D02-13 有效独立 val/test 负例 | offline | reviewed_negatives=0 | **BLOCKED** |
| D02-14 静止 ≥20s 窗 | offline | S8 最长 1.76s | **BLOCKED** |
| D02-15 存量训练折泄漏 | offline | 新包 exact_duplicate=0；存量未证伪 | NOT_RUN（新 PASS；存量交 owner） |
| D02-16 模型晋级 | offline | 依赖 D02-13 | **BLOCKED** |
| D02-17 设备/物理/部署 | device | 全程离线，未触板 | NOT_RUN |
| D02-18 禁 submit/push/deploy/采集/ML | — | 未执行 | PASS |

**回归命令与退出码：**
- `python -B sidequests/human_fusion_lab_next/next/review/review_loader.py`（exit 0，`selftest OK`）
- `python -B .../review_export.py` / `review_split.py` / `review_qualify.py`（各 exit 0，`selftest OK`）
- `python -B -W error -m unittest discover -s sidequests/human_fusion_lab_next/next/review -p "test_*.py"`（**Ran 18，OK，exit 0**）
- `python -B sidequests/human_fusion_lab_next/next/review/build_review_package.py --verbose`（**exit 0**，n_records=2309）

设备结果不以本机或 mock 替代；本轮未触板。

## 未闭合与限制

- **D02-11 D01 契约待接入 BLOCKED**：Unified Plan 中 D01 为 P0 未执行，冻结 schema/version/SHA 尚未发布。按授权第 6 条，最终索引映射/导出不自行定版；当前采用双域如实记录 + 双 SHA 待 D01 发布后重导出对齐。**解除条件：Codex 发布 D01 冻结契约。**
- **D02-12/13/14/16 BLOCKED（E1 明文）**：语义资格/双人身份/独立负例/静止窗/模型晋级均依赖人工审核；在无人工复核时保持 BLOCKED。**解除条件：用户/人工完成 `03_QUALIFICATION_AND_SPLIT.md` §四 审核清单。**
- 契约允许的算法/证据限制：D02 不跑检测器（has_candidate 语义 =「已标对象存在」而非「分类器前真实候选」）；PointNet/XGB 未由本轮重跑；S6 GT_V2/V3 与 V1 一致性未审（登记交 owner）。
- 范围外新需求：S1 GT_V3「propagated 却 reviewed」协议矛盾，已登记，建议交 Codex/D05a 裁定真实来源，本任务不裁决。
- 设备/物理未跑项：全部（D02-17 NOT_RUN），本轮无任何设备/网络/驱动/部署授权动作。

## 交给 Codex 独立复审

- 现行验收表与本轮变更记录：`docs/human_capture/evidence/2026-10-11_human_fusion_d02_r1/05_ACCEPTANCE_DRAFT.md`（建议 ID D02-01..18，唯一表待主控登记）。
- 根因诊断/完整入口检查证据：本回传「集中诊断」+ `03_QUALIFICATION_AND_SPLIT.md`（资格/割裂/审核清单全表真实数字）。
- 源码差异与 SHA 证据：`04_ARTIFACT_SHA256.json`（本任务全部产物 SHA256）；输入冻结 `review_out/review_package.manifest.json.input_sha256_map`（9 会话）。
- 原始日志索引：`sidequests/human_fusion_lab_next/next/review/review_out/`（review_package.jsonl/.manifest.json、split_draft.json、dedup_report.json、negative_evidence_report.json、qualify_items.json）+ `evidence/2026-10-11_human_fusion_d02_r1/02_BUILD_SUMMARY.json`。
- 当前工单下一步：工程工具 SUBMITTED 停写待审。等人工完成审核清单后，由主控按 D01 冻结契约接最终导出、解锁语义资格；D02 不再自行推进语义结论。

Codex 读取共享工作区并对全表独立复审。本端 HFUS-D02 与 Codex 负责的 D01/D03/集成互为独立写入边界，复审期间停写。

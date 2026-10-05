# GL-P01 R2 POST-IMPLEMENTATION 设计审计（M01-M12 + 容器交集）

2026-10-03。同一工单 GL-P01 R2，唯一写作者 OpenCode CLI `opencode-go/deepseek-v4.1-flash` / default DB，同 session `ses_eff8d3be0ffepAa0xDl9vMyuI0`。派前 probe `01_service_probe_meta.json`：exit 0，elapsed 12.469 s，PROBE_OK。
ponytail 实际读取路径：`docs/human_fall/evidence/2026-10-03_gl_p01_r1/ponytail_SKILL.md`（仓库内完整副本，SHA256 `1316a2f3f95741d2300b116fe0c2d81ce4a9568656ed0a62643f54aaf09957f2`）。full。
本轮只读：R2 提示、`r1/CODEX_REVIEW.md`、`r1/97_codex_independent_results.json` 失败片段、`r2/PLAN_REVIEW.md`；未全读历史/源码/测试。

> **重要：本文档是事后（POST-IMPLEMENTATION）设计审计。** 它不是实现前的集中诊断。本工单要求的顺序（先 00_diag，后改源码）**未被遵守**，本文档的初版也是在产物编辑之后才写的（见 §0）。现以实际已实现的代码与已跑检查为准，重写为事后审计并明确记录该顺序偏差与责任；不重写任何旧证据/历史。

## 0. 写入顺序偏差记录（审计项）

- 事实时间线（NTFS LastWriteTime，可核）：
  - `src/human_fall_detection/core/lidar_candidates.py` 编辑：**15:12:24**
  - `src/human_fall_detection/tests/glp01_consumer.js` 编辑：**15:12:52**
  - `src/human_fall_detection/tests/test_glp01_ground_projection.py` 编辑：**15:13:28**
  - `docs/human_fall/evidence/2026-10-03_gl_p01_r2/00_diag.md` **初版**写入：**15:13:53**（晚于全部产物编辑）
  - 检查日志 `02/03/04`：15:14:00-15:14:06
- 偏差：R2 要求“先 00_diag 按 M01-M12 映射，再最小修复”。实际是先改 producer/测试，再补 diag，属**流程顺序偏差**。
- 责任：本单唯一写作者（OpenCode 实现者）未在编辑前落盘 00_diag，**主责在实现者**；派前 `PLAN_REVIEW.md` 已写明先 diag 再 source，但执行时未按序，派工侧无强制门，非验收语义缺陷。
- 性质：**只影响过程合规，不影响产物正确性**；无隐藏/伪造“实现前”文档。本文档初版据实描述修复，但归类错误（写成了“集中诊断”）。现按 Codex 只读审计要求重写为 POST-IMPLEMENTATION 审计；不改代码、不改旧证据、不改 R1 回传正文。

## 1. 根因（据 R1 CODEX_REVIEW / 97）

R1 的 `_coordinate_ground_projection` 在**已经 `validate_geometry_calibration` 通过**的 canonical `ground_derived` 上又加了 `isinstance(R, list) and isinstance(t, list)` 的**局部容器门**。共享严格校验器经 `strict_numeric_array`→`np.asarray` 接受 **list 与 tuple**，校验通过后 `copy.deepcopy(block)` **保留原容器**；`ground_derived_id_for` 用 `json.dumps` 对内容哈希，tuple 与 list 产生**同一 GDID**。故合法 tuple R、tuple t 或双 tuple：ground AABB 仍 `actual_points`、`ground_status=valid`，但 R1 投影返回 `null` → JS `unavailable`/`no_ground_block`。97 `existing_legal_tuple_artifact` FAIL 为唯一失败项，其余 19 项 PASS。

## 2. 已实现的最小修复（事后核验，未再改动）

`src/human_fall_detection/core/lidar_candidates.py` `_coordinate_ground_projection`：删除 list-only 门，仅保留“非 dict 块或 R/t 缺失→None”，把 validated 数值重建为**新 list**（`[list(row) for row in rotation]`、`[float(v) for v in translation]`）。不新增局部 schema 门；坏输入继续由共享 `validate_geometry_calibration`/`validate_ground_derived` 拒绝。未改 canonical validation/math/runtime/webui。片段见 `07_r2_helper_snippet.txt`，累计差异 `06_lidar_candidates_diff.txt`。源码 SHA `447e4003c12e114bdcac657fd980b302bf01da473e4a285e66e1312772db5373`。

## 3. 容器交集（POST-IMPLEMENTATION 实际行为核验）

`R∈{list,tuple} × t∈{list,tuple}` 四格。已实现代码对这四格均：`coordinate.ground` 非 null，`R`/`t`/`ground_derived_id` 与 list 形态一致，`parseGroundRender` ready，support unavailable。

| # | R | t | pure producer 实测 | NodeCore→ROS strict JSON→preview JS 实测 |
|---|---|---|---|---|
| A | list | list | PASS（`test_valid_derived...`） | PASS（`test_production_snapshot...`） |
| B | tuple | list | PASS（`test_pure_producer_projects_tuple_containers[rotation_tuple=True, translation_tuple=False]`） | PASS（`test_actual_nodecore_tuple_containers_to_preview_js[True, False]`） |
| C | list | tuple | PASS（`[False, True]`） | PASS（`[False, True]`） |
| D | tuple | tuple | PASS（`[True, True]`） | PASS（`[True, True]`） |

JS consumer 已扩展可断言 `ready/unqualified/unavailable`（保留裸快照 ready 正例）：`test_preview_js_reports_unqualified_and_unavailable` PASS。日志 `02_glp01_tests.txt`（Ran 11, OK）。

## 4. M01-M12 事后审计矩阵

| 行 | 输入/状态 | 事后实际结果 | 入口/检查 | ID |
|---|---|---|---|---|
| M01 | startup/full valid artifact（list 与 tuple R/t）+ matching ground；empty/unlocked | PASS（97 空候选 PASS；新 tuple 有候选；`test_pure...`/`test_actual...`） | `build_snapshot`；`TupleContainerProjectionTest` | P01/P03 |
| M02 | startup/tilted + nonzero t；list/tuple | PASS（修复后 tuple 不丢；tilted/非零 t 原值；`test_tilted_ground...`+tuple 四格） | 步骤6 derived→步骤9 投影 | P01/P03 |
| M03 | legacy/none/ground-only 无 derived | PASS（`test_no_derived...`；投影 None） | `_validated_ground_derived` 首判 | P02 |
| M04 | artifact-only、`ground=None` | PASS（`coordinate.ground` 可读但 `cal.ground_status=unknown`→JS unqualified） | 步骤9 投影不依赖 ground；`test_preview_js_reports_unqualified...` | P02/P03 |
| M05 | 同内容 reload；locked/pending/ready | PASS（97 output_isolation/reload；runtime SHA 未变） | `apply_ground_context` | P04 |
| M06 | 同 ID 异内容/新 ID reload | PASS（既有 gl02/gl03；本单未动 runtime） | `_resolve_new_context`/校验 | P02/P04 |
| M07 | caller/输出原地修改；后续帧 | PASS（`test_projection_is_isolated...`；投影 R/t 每次新 list） | deepcopy 校验 + 新 list | P02/P03/P04 |
| M08 | foreign source frame / 不同 parent ground | PASS（`test_foreign_frame_projection_is_null`） | 步骤6 绑定；`ground_frame_eligible` | P02/P04 |
| M09 | malformed schema/units/ID/R/t/flags | PASS（坏 whole parent+child 由共享 validator 拒；tuple 不再被局部门误拒） | `validate_geometry_calibration` 唯一入口 | P02/P04 |
| M10 | stream silent/invalid→recovery；lost/prediction、monitor | PASS（full 套件含 gl02 monitor/gl03 lost/prediction/hf05/hf06/hf07；runtime 未改） | `_process_locked`/tracker | P04/P06 |
| M11 | auto AABB/trusted ROI，无实际轮廓 | PASS（support null+reason；JS unavailable；tuple 用例亦断言） | producer 投影；`_normalizedSupport` | P05 |
| M12 | strict JSON/ROS projection；候选存在/空候选 | PASS（`project_snapshot_for_ros` 仅去候选 evidence；tuple→JSON 一致） | `dumps_strict`/consumer | P03/P06 |

## 5. 复跑检查（均为事后实跑，非复用伪称）

- `02_glp01_tests.txt`：`python -B -W error -m unittest discover -s src/human_fall_detection/tests -p test_glp01_ground_projection.py -v` → **Ran 11, OK**，exit 0。
- `03_full_suite.txt`：`python -B -W error -m unittest discover -s src/human_fall_detection/tests` → **Ran 337, OK**，exit 0。
- `04_preview_js.txt`：`node human_fall_lib.test.js`（`webui/human_fall_preview`）→ **55 passed**，exit 0。
- SHA：`05_sha256.txt`（producer `447e40…5373`、tests、consumer、本文件、日志）。

## 6. 边界（不变）

support 仍 `null`+`support_reason`（P05）；设备/physics `NOT_RUN`；不改验收表/WORKFLOW/DISPATCH/REVIEW_LOG/R1 证据/旧回传正文；不改 runtime/math/config/driver/webui；不 commit/push/reset/checkout/clean。本轮完成后停写，交 Codex 独立复审流程偏差与实现。

# GL-S02 独审（复审 r1）

## 独立性声明

- 复审者：Claude（claude-fable-5）。与作者 OpenCode（opencode-go/deepseek-v4.1-flash）**不同提供方、不同模型**，2026-10-05 ONESHOT 授权下的同一会话独立复审。**未参与实现**。
- ponytail：`C:\Users\30680\.claude\skills\ponytail\SKILL.md`（skill 工具加载，full）。
- 基线：`master @ b190834edd3b5ec4f74d2a662ee65fd0e88460f4`。

## 复审对象

- 工单：`docs/human_fall/tickets/GL-S02_fine_roi_selection.md`（作者 SUBMITTED）
- 验收表：`docs/human_fall/GLS02_ACCEPTANCE.md` v1
- 回传：`docs/human_fall/returns/GL-S02.md`
- 证据源目录：`docs/human_fall/evidence/2026-10-05_gl_s02_r1/`
- 复审产物目录：`docs/human_fall/evidence/2026-10-05_gl_s02_r1/review_01/`

## 范围核对

GL-S02 范围内有四个共享文件，SHA 与两单回传的对应关系：

| 文件 | GL-S01 回传 SHA | GL-S02 回传 SHA（返工后） | 实测 | 一致性判定 |
|---|---|---|---|---|
| `floor_roi.py` | N/A | `1d144e57851a00bc…` | `1d144e57851a00bc…` | ✅ GL-S02 提交态 |
| `floor_roi_test.py` | N/A | `8f24d086e34da5ed…` | `8f24d086e34da5ed…` | ✅ GL-S02 提交态 |
| `leveling.py` | `e01d52666…` | `3c3a88196cfd9851…` | `3c3a88196cfd9851…` | ✅ GL-S02 最新提交态（v3 接入） |
| `validation.py` | `ff7a51478…` | `469fff14d61ee2bb…` | `469fff14d61ee2bb…` | ✅ GL-S02 最新提交态（v3 kind 加入） |
| `floor_detector.py` | `72ce790f…`（未变） | `72ce790f…`（未变） | `72ce790f…` | ✅ 冻结一致 |
| `floor_sheet.py` | `92d2ed105…` | `92d2ed105ac98faa…`（未变） | `92d2ed105ac98faa…` | ✅ 冻结一致 |

**结论**：GL-S02 在 GL-S01 之上的叠加是单调 additive；两单 SHA 与实测三向一致。

## 逐条验收

复跑日志全部落盘 `review_01/`：

| 文件 | 内容 |
|---|---|
| `01_rerun_tests.log` | `floor_roi_test.py` 6/6 OK |
| `02_golden_rerun.log` | `04_golden_223757.py`（v2 仍 INSUFFICIENT / v3 4 区通过） |
| `03_run_job_rerun.log` | `06_run_job_223757.py`（recommended=tls / tls+svd+ransac valid）|

| 验收 ID | 判据字面 | 复跑证据 | 结论 |
|---|---|---|---|
| A1 合成回归 5 类 | ①25cm 全脏+15cm 净→v3 成功；②15cm 仍脏→INSUFFICIENT；③散片身份失败→`floor_regions_invalid`；④v2 可达→逐字返回 v2；⑤v1 可达→逐字返回 v1 | `01_rerun_tests.log`：6/6 OK exit 0，含 `test_fine_roi_succeeds_where_25cm_fails`、`test_fine_roi_insufficient_when_even_fine_dirty`、`test_v3_identity_rejected`、`test_v3_returns_v2_verbatim_when_25cm_ok`、`test_v3_returns_v1_verbatim`、`test_fine_boxes_keep_purity_gates` | PASS |
| A2 223757 golden 识别侧 | v2 仍 INSUFFICIENT / v3 kind=fine_roi、min_sep≥0.5、indep=4、cond≥0.1；frozen 证据 | `02_golden_rerun.log`：v2_result=`INSUFFICIENT_CLEAN_ROI_SUPPORT: clean_cells=6 independent=0 min_sep_m=0.354 condition=0.162`；v3 kind=`lowest_floor_sheet_v3_fine_roi`、min_sep=0.540、indep=4、cond=0.180、full_height=true、no_manual=true；与作者 `05_golden_223757.json` 完全一致 | PASS |
| A3 223757 全流程 | auto `run_job` 三法全 valid、recommended=tls、产物落盘、不降门 | `03_run_job_rerun.log`：recommended=tls；tls rms=0.01458 p95=0.02965 support=0.9995；svd 同；ransac rms=0.01708 p95=0.03334；artifacts=[domain.npz, manifest.json, ransac, report.json, svd, tls]；三法产物目录齐 tls/svd/ransac + full 文件 dataset.zip/meta.json/points.bin/quality.json/transform.json | PASS |
| A4 三在范围会话不回归 | 203349/203135/202456 v3 入口逐字返回 v1 | GL-S01 复审 `02_golden_rerun.log`：三会话均输出 `lowest_connected_floor_v1`，exit 0；`leveling_auto_test.py::test_real_sessions_detect_four_regions` 跑 202456/203349 也通过 | PASS |
| B1 B 层契约只增不减 | 细粒度纯度门=25cm 门（厚度 0.18 / n_z 0.94 / RMS 0.025 / 贴面 0.08 / 0.18 逐字）；每帧点数 30→≥20 且 ≥holdout 下限 20；间距/独立/条件数一个不降 | 复审 `floor_roi.py::fine_boxes`（行 60–77）：`span > PROFILE["cell_height_span_max_m"]` / `abs(local_normal[2]) < PROFILE["normal_alignment_min"]` / `rms > PROFILE["cell_local_rms_max_m"]` / `abs(center[2] - predicted) > PROFILE["cell_floor_gap_max_m"]`——**全部从 `floor_detector.PROFILE` 读值，无 0.18/0.94/0.025/0.08 字面量**。`FINE_PROFILE`：`min_points_per_frame=20`、`roi_min_separation_m=0.50`、`condition_min=0.10`；作者测试 `test_fine_boxes_keep_purity_gates` 锁定 | PASS |
| B2 v1/v2 冻结 SHA | `floor_detector.py` / `floor_sheet.py` 内容 SHA 不变 | 实测 SHA：floor_detector=72ce790f…、floor_sheet=92d2ed105ac98faa… 与基线一致；`leveling.py` 行 244 `detect_floor_regions_v3` 是 GL-S02 内唯一 auto 入口 | PASS |
| C1 失败/成功语义 | A 失败→`floor_regions_invalid`；双粒度不足→`INSUFFICIENT_CLEAN_ROI_SUPPORT`（含两粒度计数）；成功→kind v3+ 全高度+ 无人工 | 作者 `test_v3_identity_rejected`（A 失败）、`test_fine_roi_insufficient_when_even_fine_dirty`（15cm 仍脏→INSUFFICIENT）、`test_fine_roi_succeeds_where_25cm_fails`（成功路径字段字面核验）全过 | PASS |
| C2 消费者 | `floor_identified` 接受 v3、v1/v2 分支不变；全回归过 | 复审 `validation.py` 行 15–22：`kind in ("lowest_connected_floor_v1", "lowest_floor_sheet_v2", "lowest_floor_sheet_v3_fine_roi")` **additive 加入**；GL-S01 复审 `01_rerun_tests.log` 39/39 OK（含 `validation_test.py` / `floor_sheet_test.py` / `floor_detector_test.py` / `leveling_test.py` / `leveling_auto_test.py`） | PASS |
| C3 审计 code_files | auto `code_files` 纳入 `floor_roi.py`；v3 candidate 携带细粒度证据字段 | 复审 `leveling.py` 行 264–268：`code_files` 含 `floor_roi.py`；`floor_roi.py` 行 195–214 candidate 含 `profile/grid_m/normal_source/offset_source_m/support_ratio/fit_frame_count/component_cells/component_area_m2/sheet/roi.{grid_m, clean_boxes, min_sep_m, independent_count, condition}/selected_cells/full_height_preserved/uses_manual_reference/basis` | PASS |
| S01 流程 | ponytail 加载、SHA 记录、不越界 | 复审未对生产源码/测试/验收表做写操作；新增文件仅 `review_01/` | PASS |
| D01 设备/物理 | 离线单，NOT_RUN | 未运行 | NOT_RUN |

## 复审期间发现的非问题项

1. **回传 A2 行写 min_sep=0.965，golden JSON 实为 0.540**：回传正文与 gold 数据有一处不一致，但 0.540 ≥ 0.5m 判据仍通过。gold 是真相，回传仅是文字的笔误。复审以 gold 为准；不影响验收。
2. **`_select_four` 的 rms 排序不是新门**：复审 `floor_roi.py` 行 112–123，`feasible` 只用 `separation < roi_min_separation_m` 与 `condition < condition_min` 两个 ≥ 门；`rank` 的 rms 只在已通过 purity 门的盒之间排序。判据"过了纯度门不被 rms 拒"满足。
3. **`min_points_per_frame=20`**：与 `leveling_quality.PROFILE["min_points_per_region"]` 同值，且满足"≥ 下游 holdout 每区下限 20"。
4. **`n<=60` 时穷举 vs 贪心**：分支判据 `n <= 60`（行 125）；34 净盒走穷举路径，与 golden 一致。

## 观察

- v3 委托链忠实：`v3 → v2 → v1`，每层只在指定错误前缀才接管，其他原样抛。
- 委托边界差异显著：
  - v1 抛 `floor_regions_invalid` → v2 接管；
  - v2 抛 `INSUFFICIENT_CLEAN_ROI_SUPPORT` → v3 接管；
  - 其他错误（如 `floor_auto_candidate_invalid`、`floor_not_found`）任何一层都不接管——复审在 GL-S01 已用 `test_p4` 探针验证。
- 223757 真实数据验证：A 层（largest 7.06 m² / cov 0.937 / temporal_p05 0.766）早已通过；v2 25cm 必需 4 个 ≥0.5m 间隔的净格但只得 6 个分两簇格（最近 0.354m）；v3 15cm 得 34 个净盒，可挑 4 个满足 ≥0.5m 间隔 + 条件数 ≥0.1 的可行组合。判据所覆盖的语义裂缝在真实数据上恰好出现，并被 15cm 粒度正确弥合，未降任何门。
- 全流程 `run_job` 对 673 万拟合点 + 162 帧 → 29288 个域点：tls/svd rms 0.0146m / ransac rms 0.0171m，全部 valid；产物三法目录 + manifest + report 完整。

## 复审结论

**软件 PASS**（A1–A4, B1–B2, C1–C3, S01 全过；D01 NOT_RUN 属本单边界）。范围越界无、v1/v2 零改、B 层门零降。

整单 **不报 ACCEPTED**：D01 NOT_RUN；按 WORKFLOW 由用户决定是否收口。移交 GL-B 复审。

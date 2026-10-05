# Claude Code GL-I02 R1 独立复审 / 2026-10-03

顶替登记与上游同前：`CLI_RECOVERY.md`。本轮复审由 **Claude Code** 顶替 Codex，独立复核 SUBMITTED 的 GL-I02 R1 阶段二实施，生产写者仍 OpenCode `opencode-go/deepseek-v4.1-flash` default DB。

## 0. 上流程衔接

- 阶段一诊断 00_diag（OpenCode）§3.1 列出 5 个张力（R-a candidate 落点 / candidate vs adapted CLI / physical_verified 落点 / J01 文案 / N06 残缺），包含 wrapper thin orchestration（不重写 ROI/数学）与白名单 0 新增生产代码（阶段一零生产）。
- 阶段一 OpenCode 未写生产/tests/`capture_input.py/ground.py/calibration.py/prepare_capture_input.py/calibrate_sensors.py`，glass。
- 04_DESIGN_REVIEW：在设计门的位置吸收 7 个[张力/残缺]（含 N06 语义修正、--capture-dir/--prepared-npz 语义、N06 引号、候选字段 naming、draft exclusive、candidate vs synthetic strict 分离）。
- 阶段二 OpenCode 实施：唯一新生产 wrapper `evaluate_gli02_candidate.py`、唯一新增 test `test_gli02_candidate.py`，其余仅 docs/returns/本单证据。
- 阶段二 exit 0 / elapsed 577s / events 183，回传 SUBMITTED；未 commit/push/reset/checkout/clean；`captures/remote/` SHA 未变。

## 1. 本轮证据（codex_review_01/）

| 文件 | 内容 | 结论 |
|---|---|---|
| 00_review_baseline.py/json | 新文件 SHA + frozen SHA + capture SHA | all_match=true，与回传统 SHA/诊断 SHA 一致 |
| 01_full_regression.txt | `python -B -W error -m unittest discover -s src/human_fall_detection/tests` | Ran 407 / OK / exit 0 |
| 02_gli02_new.txt | 新 8 项 test_gli02_candidate | Ran 8 / OK / exit 0 |
| 03_gli01_regression.txt | GL-I01 62 回归 | Ran 62 / OK / exit 0 |
| 04_probes.txt | GL-I01 Codex 24 探针表 | total=24 failed=0 / exit 0 |
| 05_emit_draft.txt + work/blank_draft.json | `--emit-draft` 模板含 `pending_human_review`/`default_refusal`/`up_axis`/`sensor_height_interval_m`/`fit_region`/`validation_regions`/`review.required` | 独立 exit 0 |
| 06_positive_candidate.txt + work/codex_candidate.json | 填好 draft → candidate artifact | 独立 exit 0；`status.ground=candidate`、`ground.status=valid`、无 `ground_derived`、`verification.ground_physical_verified=false`、`input.source=synthetic_fixture`、`input.synthetic=true`、`input.input_manifest.provenance.*` 全 false |
| 07_cli_negatives.txt | N1 legacy NPZ / N2 overlap / N3 fit-leak / N4 empty-fit / N5 真实 capture SHA 不变 | 五个独立负例全部 exit 2 或无 artifact / capture SHA 前后一致 |
| 08_final_sha.txt | 复审结尾 SHA | 与诊断、回传统、结论完全一致 |

## 2. 逐条结果

| ID | 结果 | 依据 |
|---|---|---|
| J01 | **PASS**（synthetic candidate 路径） | 实现者自验 14/14 + 我独立 positive 独立 exit 0；candidate artifact schema、`status.ground=candidate`、`ground.status=valid`、physical flags=false、provenance 不变 |
| J02 | **PASS**（真实 capture 读性） | 自验 12/12 + 我独立 N5：capture meta/bin SHA 前后一致、目录无新文件 |
| J03 | **PASS** | candidate artifact `input.source=synthetic_fixture`、`input.synthetic=true`；真实字段 `capture_export` 严格分开；自验 T4 + 我独立 artifact 观察 |
| J04 | **PASS** | blank draft `pending_human_review` + `default_refusal="no_auto_ground_selection"` + 完整字段；T2/T6 自验；我独立 N2、N4 |
| J05 | **PASS** | wrapper 700 行内只调用 GL-I01 R1 公开 API；`classify_npz` 判 legacy 的 wrapper 独立 exit 2；GL-I01 24 探针 24/24；回归 62 仍 OK；vendor `legacy --points` route 未动 |
| J06 | **PASS** | 白名单 2 新增（1 生产 + 1 tests）；GL-I01 四文件 SHA 与诊断 §1 相同，freeze ground/calibration/capture 不变 |
| B01 | **BLOCKED**（维持） | bag2session 未持久化 width/height/original_count；wrapper 不伪造原袋 row 索引 |
| D01 | **NOT_RUN** | 按工单不启动、不部署、不采集 |
| D02 | **NOT_RUN** | GL04 DPR 另起、不属本单 |
| N01 | **PASS**（synthetic） | wrapper 全链 load_adapted → check_declared_frame → gate_selection → fit_ground_plane_constrained → validate_constrained_ground → build_input_info → build_geometry_calibration → save_exclusive_json；exclusive artifact；独立 exit 0 |
| N02 | **PASS** | 缺 fit/validation/up_axis/height → exit 2 无 artifact 无 fallback |
| N03 | **PASS** | 同名 artifact 已存在 → exit 2 旧件字节保留（save_exclusive_json `os.link` exclusive） |
| N04 | **PASS** | synthetic / real strict 分离；manifest synthetic 没有翻转 |
| N05 | **PASS** | GL-I01 62 / 24 probes / SHA |
| N06 | **PASS** | 非 adapted 普通 NPY/NPZ → wrapper 独立 exit 2；adapted 损坏 → wrapper 独立 exit 2（无 fallback 到 legacy 的 --constrained） |
| N07 | **PASS** | blank draft 字段齐 + pending_human_review + review.required |

## 3. 唯一复审期间被识别但分解的“候选”

无。我准备了多个候选：`evaluate_gli02_candidate.py` 是否会悄悄退让到 `calibrate_sensors.py` legacy、`--capture-dir` 同时给 `--prepared-npz`、加班 draft 缺 keys、 blank draft overwrite、 `--emit-draft` 缺 `--draft-out` 行为、`load_adapted` 未校验 frame 名称修改、`build_input_info` 范围外 key degate。实际代码/read-evidence 走一遍全部按设计门/n 裁决行为；独立 6 个 CLI 正反例全 PASS。

## 4. 冻结/边界确认

- GL-I01 R1 四文件 SHA 与诊断 §1 一字不差；ground.py、calibration.py SHA 不变
- `captures/remote/cap_20261002_163621/` 只读，meta/bin SHA 前后一致；目录无新文件
- wrapper 管线 import 仅 `core.calibration`、`core.capture_input`、`core.ground`、`calibrate_sensors.save_exclusive_json`（T8 import audit PASS）
- draft/artifact 独立命名空间（`evidence/2026-10-03_gl_i02_r1/…`）；`--emit-draft` 独占写
- 不动 GL02 lifecycle、ground-derived；compute copy 还是 GL02 artifact 自 schema

## 5. 结论

GL-I02 R1 软件路线 I**全 PASS**；J01/J02/J03/J04/J05/J06 与 N01–N07 全 PASS；B01 BLOCKED、D01 NOT_RUN、D02 NOT_RUN 分层维持。整单按本子阶段**不升 ACCEPTED**。GL04 DPR、GL05、正式页、设备/部署/采集/网络各自独立分层，均不因此通过。

## 6. 路线3 真实 fit 冻结（见 13_route3_closeout.md）

用户确认 `up_axis=[0.438371, 0, 0.898794]`、`sensor_height_interval_m=[1.2, 1.7]`、fit/validation 圈定后，**真实 fit 走通尝试**：

- Wrapper → `ground_points_insufficient`（不是 angle 问题，是协议 `min_inliers=100` vs 单 frame_group 仅 ~1214 点 × `_balanced_sample` 剩 ~80）
- 独立 direct call + SVD 复核：up_axis 数学正确（2.7° 偏差），采样闸一致拒绝
- 决定：**按用户指示，真实 fit NOT_RUN**，不推 R2 协议改动，**不进 production**，不动 ground/calibration.py / GL-00 R4 冻结 config
- J01 synthetic candidate 路径独立 PASS；真实侧 NOT_RUN 经 **路线3** 分层冻结

## 7. 下一步（按 CODEX_STANDBY 派工轮转）

按用户 "随便你如何调用，开发主线，每次完成都要审核，规划，调用返工" 授权：

1. **已完成**：GL-I02 R1 路线3 收口（本文件 + 13_route3_closeout.md），全 PASS 基于 synthetic，真实 physical 待计划变迁（更长 capture / min_inliers 协议调整 / cross-frame pooling）
2. **用户决定下一步**：见 13_route3_closeout.md §4 候选表
3. 已核 SHA 不变、协议未篡改、真实 capture 未触碰

# GL-I02 R1 阶段二实施工单（已获 04_DESIGN_REVIEW PASS）

派工者：Claude Code（CLAUDE_STANDBY 顶替）。生产写者：唯一 OpenCode `opencode-go/deepseek-v4.1-flash` default DB。本工单在 04_DESIGN_REVIEW **后方可实施**，并受其白名单/设计裁决约束。

## 必要先读（只读）

1. `docs/human_fall/GLI02_ACCEPTANCE.md` v1 J01–J06、N01–N07（本单唯一验收表）
2. `docs/human_fall/evidence/2026-10-03_gl_i02_r1/00_diag.md`（你得 OWN diagnose）
3. `docs/human_fall/evidence/2026-10-03_gl_i02_r1/04_DESIGN_REVIEW.md`（Codex/Claude 顶替的**设计裁决**：你的 wrapper 方案、schema 落点、N06 语义修正、`--capture-dir`/`--prepared-npz` 互斥、draft exclusive、严格不扩大白名单）
4. `docs/human_fall/GLI01_INPUT_CONTRACT.md`、`evidence/2026-10-03_gl_i01_r1/07_diag_revision.md` §2/§4/§5
5. `docs/human_fall/RETURN_TEMPLATE.md`

## 白名单严格（只加下列内容）

- **新生产文件**：`src/human_fall_detection/scripts/evaluate_gli02_candidate.py`（唯一；按 04_DESIGN_REVIEW §3）
- **新测试**：`src/human_fall_detection/tests/test_gli02_candidate.py`（最多 8 项回传，按诊断 §7）
- **新文档**：`docs/human_fall/GLI02_*.md`任选（如 `GLI02_CANDIDATE_PLAN.md`）
- **追加回传**：`docs/human_fall/returns/GL-I02.md`
- **追加证据**：`docs/human_fall/evidence/2026-10-03_gl_i02_r1/<你的编号_*`（续接本目录已有编号）

## 无写名单（含 inline） 

- `core/capture_input.py`、`scripts/prepare_capture_input.py`、`scripts/calibrate_sensors.py`、`tests/test_gli01_capture_input.py`、`core/ground.py`、`core/calibration.py`、`captures/remote/`、`webui/`、`pc_apps/`、任何 config YAML

## 行为约束

- 真实 163621 **不 fit**、不写 capture dir；只 read/count/hash 验证（J02/J06 约定）
- synthetic fixture 适配 NPZ 上合成 fit（如 candidate artifact）允许，`source=synthetic_fixture`、`status.ground="candidate"`
- 动 GL-I01 逻辑 inline 就是越权；遇 wrapper 真需要其它新生产文件 → STOP 报 Codex
- `--capture-dir` 与 `--prepared-npz` 至少一个必填，两者同时给以 `--prepared-npz` 为准；无 → exit 2
- 非 adapted 普通 NPY/NPZ 输入 wrapper → `classify_npz=="legacy"` → exit 2，不 fallback adapted；wrapper 不运行 calibrate_sensors 的 legacy 路径
- adapted NPZ → strict route：`load_adapted` + `check_declared_frame` + `gate_selection` + `fit_ground_plane_constrained` + `validate_constrained_ground` + `build_input_info` + `build_geometry_calibration(statuses={"ground":"candidate"})` + `save_exclusive_json`
- 缺 fit selector / frame_group / <3 validation_regions / up_axis / sensor_height_interval → exit 2 无 artifact 无 fallback
- draft 独占写、含 `status="pending_human_review"` / 每字段来源 / `default_refusal="no_auto_ground_selection"` / 独立命名空间（synthetic 与 real 严格分开）
- candidate artifact 与 draft 都走 exclusive `save_exclusive_json`

## 自验顺序

1. `python -B -W error -m unittest discover -s src/human_fall_detection/tests -p test_gli01_capture_input.py` → 仍 62 OK
2. `python -B -W error -m unittest discover -s src/human_fall_detection/tests -p test_gli02_candidate.py` → 新 added 测试全 OK
3. `python -B -W error -m unittest discover -s src/human_fall_detection/tests` → 全部回归 OK
4. `python -m py_compile src/human_fall_detection/scripts/evaluate_gli02_candidate.py`
5. 合成 7-frame adapted NPZ + draft → candidate artifact exit 0，读回 `status.ground=="candidate"`、`ground.status=="valid"`、无 `GROUND_DERIVED_KEY`（不要 --ground-derived）
6. 真实 163621 adapted NPZ read-only reload（或 prepare+reload）→ points 4372400/frames 89/groups 89/zero 673315 与 GL-I01 R1 一致
7. N02/N03/N05/N07/N06（非 adapted、缺 selector、同名 artifact、draft exclusive、real SHA 不变）反例 exit 2 无 artifact 无未跟踪文件
8. 本单三 SHA 与诊断 §1 完全一致

## 回传统（`docs/human_fall/returns/GL-I02.md`）

按 `RETURN_TEMPLATE.md`，覆盖 J01–J06/B01/D01/D02/N01–N07，SUBMITTED only；含新文件 SHA、commands、exit code、真实与 synthetic 各自物证、未跑项、下一步建议。

## 上限

**不 commit/push/reset/checkout/clean**；不动 git/模型/DB/全局；不动 driver/webui/captures/config/部署。ponytail 实际读取（`C:\Users\30680\.config\opencode\skills\ponytail\SKILL.md` 或等效）路径+强度写入回传。

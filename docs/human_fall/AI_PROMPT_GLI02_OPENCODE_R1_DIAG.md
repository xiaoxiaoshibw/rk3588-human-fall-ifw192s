# GL-I02 R1 阶段一诊断工单（只诊断，写后 stop）

派工者：Claude Code（按 CLAUDE_STANDBY 顶替 Codex；OpenCode 是唯一生产 writer）。

## 必要先读

按顺序读下列文件，**只读**：

1. `docs/human_fall/GLI02_ACCEPTANCE.md` v1（本单唯一验收表）
2. `docs/human_fall/evidence/2026-10-03_gl_i01_r1/07_diag_revision.md` §2/§4/§5
3. `docs/human_fall/GLI01_INPUT_CONTRACT.md`
4. `docs/human_fall/evidence/2026-10-03_next_stage_plan_r1/PLAN_REVIEW.md` §C
5. `docs/human_fall/evidence/2026-10-03_gl_i01_r1/codex_review_01/CODEX_REVIEW.md`（本轮 GL-I01 R1 复审落实，证明 adapter/CLI 软件已 PASS）
6. `src/human_fall_detection/scripts/calibrate_sensors.py`（找 adapted route / gate_selection / save_exclusive_json 三个关键函数位置）
7. `src/human_fall_detection/core/capture_input.py`（找 prepare_npz / load_adapted / gate_selection / resolve_group / frame_group_id / build_manifest / classify_npz 位置）

## 诊断动作

**只写** `docs/human_fall/evidence/2026-10-03_gl_i02_r1/00_diag.md`（一个文件，追加式，允许英文/中文）。目录由你创建。

按 GLI02_ACCEPTANCE.md v1 验收条目 J01–J06 + 矩阵 N01–N07，逐行映射：

- 本单需要的最小**新文件**（ thin evaluation / wrapper évent并发症续入口名 / tests 路径）。**严格白名单**：(a) GL-I01 prepare_npz/load_adapted/gate_selection 之上的 thin evaluation script，(b) `tests/test_gli02_*.py`，(c) `docs/human_fall/GLI02_*`，(d) `returns/GL-I02.md`。
- 与 GL-I01 R1 公开 API 的实际**函数 / 调用点 / 赋值顺序**：prepare_npz → load_adapted → gate_selection → fit_ground_plane_constrained → save_exclusive_json → build_geometry_calibration。逐条写：thin wrapper 怎么 reuse、副作用边界在哪、exclusive 再哪、artifact 怎么标记 candidate vs synthetic_fixture。
- 关键**不变量**：GL-I01 R1 SHA 不变；`captures/remote/` 只读；adapted 输入仍 strict；新 evaluation 不动 ground.py / calibration.py / 生产 config / driver / webui / 部署。
- captured_selection_draft 的 JSON 草案格式：selection how 标注 `pending_human_review` / `source=synthetic_fixture`， candidate_not_promoted；写清现场协议冻结 before 人工决断的缺省拒绝行为。
- 本单 tests 的最小集合（>10 个就有风险）：cover J01–J06/N01–N07 主要反例。

## 停写矩阵（统一写入 00_diag.md 结尾）

逐项填表：

- `j01..j06`：本诊断如何对应（检查入口/反例/补充诊断）
- `n01..n07`：调用链 entry → 实际函数 → 赋值顺序 → 副作用点
- `b01/d01/d02`：本单**不**触碰的边界确认

最后**STOP**，标记 `READY_FOR_DESIGN_REVIEW`，不要 commit、不要改任何其它文件。

## 边界（严于 GL-I01）

- 不写生产代码、tests、config、capture_server.py、captures/remote/、ground/calibration、release YAML、deploy、driver/webui 正式页
- 不启动 ROS/板端网络；不做真实 fit；不预设 up_axis/sensor_height 完整值
- 不 commit/push/reset/checkout/clean
- 不动 ground.py / calibration.py / capture_input.py / prepare_capture_input.py / calibrate_sensors.py 的 inline 修改
- 本诊断是**两阶段派工中的阶段一**；Codex 读 00_diag + 核 SHA 后才发阶段二实施工单

## ponytail 要求

按派发流程实际读 `C:\Users\30680\.config\opencode\skills\ponytail\SKILL.md`（或等效路径），诊断 evidence 里写明使用路径与级别。狮子山原则下**最小化**新增：thin wrapper 的话，优先复用 GL-I01 prepared NPZ + adapted CLI；不是新 service 也不是热更新。

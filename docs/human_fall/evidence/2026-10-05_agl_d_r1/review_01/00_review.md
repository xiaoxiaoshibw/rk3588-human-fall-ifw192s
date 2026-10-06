# GL-D 独审（复审 r1）

## 独立性声明

- 复审者：Claude（claude-fable-5）。与作者 OpenCode（opencode-go/deepseek-v4.1-flash）**不同提供方、不同模型**，2026-10-05 ONESHOT 授权下同一会话独立复审。**未参与实现**。
- ponytail：`C:\Users\30680\.claude\skills\ponytail\SKILL.md`（skill 工具加载，full）。
- 基线：`master @ b190834edd3b5ec4f74d2a662ee65fd0e88460f4`。

## 复审对象

- 工单：`docs/human_fall/tickets/GL-D_adaptive_temporal.md` v1（作者 SUBMITTED）
- 回传：`docs/human_fall/returns/GL-D.md`
- 证据源目录：`docs/human_fall/evidence/2026-10-05_agl_d_r1/`
- 复审产物目录：`docs/human_fall/evidence/2026-10-05_agl_d_r1/review_01/`

## 范围核对

| 文件 | 回传 SHA | 实测 SHA | 一致？ |
|---|---|---|---|
| `core/adaptive_ground/temporal.py` | `59b34139…` | `59b34139…` | ✅ |
| `core/adaptive_ground/controller.py` | `db3d6550…` | `db3d6550…` | ✅ |
| `tests/test_agl_d_controller.py` | `bb8a2d9a…` | `bb8a2d9a…` | ✅ |

## 逐条验收

复跑日志：`review_01/01_rerun_tests.log`（GL-D 专项 7/7 OK，0.052s）。GL-D 依赖 A/B/C 模块（已复审通过）；A+B+C 全部已复跑（504/504 OK）。

| 验收 ID | 判据字面 | 复跑证据 | 结论 |
|---|---|---|---|
| AGL-D-01 初始 acquire | INIT 不 identity；N_acquire + 最短 duration + 同 epoch 满足**才**首次 STABLE；前 N−1 无 accepted；invalid 打断连续性 | `test_init_acquisition_and_first_stable_AGL_D_01` ok。复审 `controller.py::process` 行 329–360：`state == "INIT"` 转 `ACQUIRING` 且 pending=[1]、不 commit；`state == "ACQUIRING"` 必须 `len(pending) >= acquire_frames and duration >= min_cohort_duration_s` → `_commit` 转 `STABLE`（rev 1）；BAD/重复/gap/时间乱序都在 pending 上 reset（行 223–237、244–277、523–532） | PASS |
| AGL-D-02 过滤器与限速 | 只 validated 候选喂 median/EMA；BAD 不污染窗口；输出轴步与组合步≤限；角 rate 按有效 dt；offset 同步限速 | `test_filter_rate_limits_and_bad_no_pollution_AGL_D_02` ok。复审 `temporal.py::limit_step` 行 135–162：dp/dr 逐轴 clamp 到 max_delta_*_per_frame；组合角 `allowed = min(max_angle_step_deg, max_delta_angle_per_second * dt, max_angle_rate_deg_s * dt)` 三层限速，组合角 `angle_between_deg(previous, trial)` 用同一 reference 计算（不是 pitch/roll 简单线性）；`temporal.py::limit_offset` 行 165–173：offset 按 `max_offset_step_m / max_offset_rate_m_s * dt` 同步限速。`_filtered_update` 行 140–152：`window = (cohort + [candidate])[-window_size:]` → median → ema (base=last_good/ema)，**只用**当前 candidate，不主动读 BAD 帧——BAD 分支根本不会进 `_apply_filtered`（controller 行 488–532 走另一路径） | PASS |
| AGL-D-03 HOLD 保持 | BAD/low score/遮挡/大 jump/缺输入进入 HOLD，R/t 与 revision 逐位不变；expired 保持显示但 geometry 失效；无 last_good 不伪造 | `test_hold_invariants_jump_reject_and_age_AGL_D_03` ok。复审 `controller.py`：行 285–328（GOOD 但 raw_angle/offset jump → HOLD、`last_good` 不动）；行 523–532（BAD → 同路径）；行 556–567（tick age > max_hold_age_s → `REASON_STALE`，`fresh=false`、`eligible_for_geometry=false`、`last_good` 数值保留）；无 last_good 时 `_age` 返回 None（`_decision` 行 96：`age is None → fresh=false`）；`last_good` 只在 `_commit` 中赋值，**只在过滤后 proposal 通过限速与窗口检查后才触发** | PASS |
| AGL-D-04 恢复/rebase | HOLD/DEGRADED 恢复需 N_recover + duration；第 1/N−1 不得应用；bad/gap/duplicate 重置；≤2° 持续小变化稳定确认后限速追踪；5–20° 不被 EMA 吞下 | `test_recovery_rebase_and_no_ema_swallow_AGL_D_04` ok。复审 `controller.py::process` 行 362–487：STABLE 下 raw_angle ≤ max_angle_step_deg → 直接 `_apply_filtered`；raw_angle > max_angle_step_deg → 进入 `rebase` pending（`pending_rebase_max_deg` 内向 `rebase_target` 收敛）；DEGRADED → `RECOVERING` 重新 acquire（`recover_frames + min_cohort_duration_s`）；行 449–454（HOLD → RECOVERING）。`temporal.py::limit_step` 的 raw_jump_reject_deg 在 process 行 293、311、337、365、409 都先查——5–20° raw 跳变在早期被拒，**不会进入 filter 链让 EMA 吞下** | PASS |
| AGL-D-05 epoch/freeze lifecycle | 不兼容 epoch/reload 清 pending/旧资格；bad reload 原子拒；manual freeze 锁存；unfreeze 仍走恢复；旧 GroundMonitor latch 不被单 GOOD 清 | `test_epoch_freeze_unfreeze_lifecycle_AGL_D_05` ok。复审 `controller.py`：行 196–211（首次 epoch adopt；epoch 变更 → controller_epoch+=1 → `_reset_all` → 返回 REASON_EPOCH）；行 213–221（freeze_latched → 所有输入 REASON_FREEZE）；行 569–597（freeze/unfreeze：freeze 只锁存；unfreeze 清 `rebase/pending`，有 last_good → RECOVERING 否则 INIT）；`_reset_all`（行 113–123）清 `pending/rebase/cohort/ema/last_good/last_frame_digest`——**revision 单调不清**。controller.py 不 import 也不触 GroundMonitor 的 recalibration latch | PASS |
| AGL-D-06 事件 schema | 每次状态/accept/discard/reset/freeze 事件都有 frame/time 域/old-new/reason/IDs/action；no-input 不造帧；primary + 全部 fault 可重放 | `test_events_json_and_determinism_AGL_D_06` ok。复审 `controller.py::EVENT_FIELDS` 行 25–27：字段集固定含 `event_seq/input_kind/frame_key/frame_digest/stamp_s/time_domain/state_before/state_after/action/applied/reason_codes/accept_revision/controller_epoch/tick_index`；`_event` 行 77–88 组装；tick 事件（`on_tick` 行 556–567）`frame_key=None / frame_digest=None / stamp_s=None / tick_index=self._seq+1`——no-input **不伪造帧**；`validate_controller_decision` 行 600–616 对每个 decision 做 schema 校验 | PASS |
| AGL-D-S01 流程 | stdlib+NumPy 不先引 Kalman/IRLS；设计前置 + WF 自验/回归/SHA/停写/独审；不接生产 | `test_config_refusals_AGL_D_S01` ok（13 config 负例全拒，含 alias 相等）。复审：两文件只 import `math/numpy` + 项目内 `ground_evidence/contracts/temporal`——无 Kalman/IRLS/scipy；HEAD 未动；未改旧规则/生产；未接 runtime | PASS |
| AGL-D-D01 设备/物理 | 离线单 | 未运行 | NOT_RUN |

## 复审期间发现

1. **作者 D 自检① 修复已落地**：回传记录"BAD 清空 pending 后，ACQUIRING/RECOVERING 重进 append 未回填 pending_start_s → duration 计算 TypeError"。复审 `controller.py` 行 342–343、462–463：`self.pending.append(effective)` 之后 `if self.pending_start_s is None: self.pending_start_s = stamp`——在共享 append 路径内一次性修复（ACQUIRING 与 RECOVERING 两条路径均受益）。该修复属本单内的 duration 计算完备性闭环。
2. **作者 D 自检② 测试构造修正**："外部 epoch 变更后测试帧未同步 epoch；时间戳回跳"——复审 `test_agl_d_controller.py` 走同 epoch 下的时间轴；产品代码不变（回传明示）。该修正属测试一致性调整，不改判据。
3. **回传记录"实施期间外部提交 0d5ab42 出现"**：与本复审无关——外部提交非本 writer 操作，HEAD 当前在 `b190834`（用户后续再有提交属用户域）。

## 观察

- `process` 的状态分支表：每个 state × consensus_status 都有显式分支，没有 fall-through。BAD 处理（行 523–532）与 ANGLE_JUMP/OFFSET_JUMP（行 285–328）共用同一 reset 模式：`pending=[]、rebase=[]、state in (STABLE, DEGRADED, RECOVERING) → HOLD`——共享 reset 在多处调用，一次修复到位。
- `_commit` 行 125–138：transform_id 以 `config_id/controller_epoch/revision/pitch/roll/offset_m/frame_digest/epoch_key` digest——**revision 与 epoch 都在 identity 中**，旧 transform 不会因跨 epoch 重用 revision 冲突。
- `_filtered_update` 行 145：`dt_rate = stamp_s - self.last_good["stamp_s"]` 显式 dt；dt ≤ 0 直接 `return None` → `_time_invalid_return`（GL_TIME_INVALID 入事件+reason）——不猜 FPS、不用 EMA 默认权重。
- 作者已把 `rebase_pending` 报告字段（decision 中）暴露给 GL-E 消费者——消费侧能知道当前是否在 rebase 窗口。

## 复审结论

**软件 PASS**（AGL-D-01..06 全过；D01 NOT_RUN 属本单边界）。范围越界无、旧 GroundMonitor latch 未触碰、CFG 关系严格校验。

整单 **不报 ACCEPTED**：D01 NOT_RUN。移交 GL-E 复审。

# GL-02 R6 集中诊断

日期：2026-10-01。执行者：OpenCode（opencode-go/deepseek-v4.1-flash），唯一生产代码写入者。
基线：R5 复审 `evidence/2026-10-01_gl02_r5_codex/CODEX_REVIEW.md`，验收 v1 `GL02_ACCEPTANCE.md`。

## 复现

```
python -B -W error docs/human_fall/evidence/2026-10-01_gl02_r5_codex/codex_r5_lifecycle_checks.py
```

结果：Ran 12 tests，failures=22（A02 方法 15 个子例 + 7 个方法），exit1。R5 记录一致。

## 根因与修复计划

### 根因1 A02/A04：父 artifact 严格校验缺失 + startup 靠 id truthiness 旁路

- 入口：`validate_geometry_calibration`（validator）、`FallNodeCore.__init__`（startup）、`apply_ground_context`→`_resolve_new_context`（reload/full/paired/ground-only/empty）、`ground_context_calibration` 的 preserved 分支——全部最终走 `_validate_geometry_calibration`。
- 现象：`schema_version != 1` 用 `!=`，接受 `True`/`1.0`；无 `calibration_id` 非空字符串校验。startup `if calibration is not None and calibration.get("calibration_id")` 对空/缺失 id 落到 ground-only fallback，绕过全量校验。
- 最小修复：在 `_validate_geometry_calibration` 加严格 `calibration_id` 非空字符串与 `schema_version` 严格 int（排除 bool/float）；startup 改为凡显式传入 `calibration` 即全量校验。
- 保留：合法无标定（`calibration is None` + ground）、`derive_ground_calibration` 生成的 ground-only 版本、原有同版本 metadata/deepcopy 入口。

### 根因2 A09/A10：ready 资格未接入失效路径

- 入口：`_process_locked`（坏帧→`ground_context_unavailable`）、`status_state`（watchdog 无新云）。二者都只调 `_cancel_pending_baseline`，该方法明确不动 ready。
- 现象：ready 在坏帧/watchdog 后仍 ready；同版本恢复可复用。修复前“失效对 features/fall 生效”仅靠传 `None`，collector 自身仍是 ready。
- 最小修复：把该方法扩展为 `_cancel_baseline_on_ground_loss`：pending→`_fail` 终态+原 request_id 回执（保留失败样本历史）；ready→`collector.invalidate`（历史进 `retired`，status→idle，不重复退休）。`invalidate` 对已 idle/无 baseline 为幂等，故不会重复退休或重复回执。在 `_process_locked` 中把它移到 `features.update`/`fall.update` 之前，使失效先于消费者生效。
- 保留：辅助 IMU degraded 不触发（无 derived 时 `_ground_context_unavailable` 恒 False）；release/显示不受影响。

### 根因3 A10：缓存查询位于新鲜度/monitor 门控之后

- 入口：`FallNodeCore.handle_request` 先做 required/ground 门控，再调 `SelectionBackend.handle`（缓存重放在其内部）。
- 现象：monitor 坏/云 stale 时同 request_id 同内容得不到原缓存回执，改为新拒绝；不同内容也不返回 request_id_conflict。
- 最小修复：在 `SelectionBackend` 暴露 `lookup_cached(request)`（纯缓存读：同内容→原回执+`idempotent_replay=True`，异内容→`request_id_conflict`，未命中→None，不执行动作），`handle` 内部复用它保持单一实现；`handle_request` 在既有门控之前先查缓存。
- 保留：未缓存新请求仍受 required/monitor/schema/epoch/version 校验；原 accepted/pending 缓存不被终态覆盖（终态经 `baseline_ack` 旁路，不写 `_requests`）。

### 根因4 A10：任务终态 ACK 未到既有 `selection_ack` 话题

- 入口：`_publish_state`（watchdog `status_state` 的 `baseline_ack` 只进 state 话题）；`worker` 的 postcompute stale 抑制分支 `continue` 丢弃本帧已产生的 `result["baseline_ack"]`。
- 现象：WebUI 读 `/human_fall/selection_ack`，收不到 watchdog/postcompute 终态。
- 最小修复：`_publish_state` 在保持 state 内 additive 字段的同时，把 `payload["baseline_ack"]` 发到 `publishers["ack"]`；worker 抑制分支在 `continue` 前把 `result["baseline_ack"]` 发到 ack 话题。两条路径互斥（正常完成/失败后 baseline 非 pending，status_state 不再产回执），不重复发布。
- 保留：state additive 字段保留；候选/事件/位置的 stale 抑制不变；不改 WebUI/冻结字段/消息 schema。

## 同类调用者核查

- `_validate_geometry_calibration` 的所有调用者（validator/startup/reload/preserved/derive）统一受益；不逐个打补丁。
- `selection.handle` 仅 `handle_request` 调用；缓存语义集中一处。
- `_publish_state` 仅 worker 内三处调用（正常、watchdog/超时后 stale、抑制）；ack 发布集中于 `_publish_state` 与 worker 显式路径。

## 检查计划

R5 12 方法 + 受影响回归（fall、follow、两 UI、R4/R3/R2/static、Claude R5）；保持 3.8/NumPy1.17 API；设备 Linux/板端未跑记 NOT_RUN。

# GL-02 R7 集中诊断（pending 标定切换终态）

日期：2026-10-02。执行者：OpenCode（opencode-go/deepseek-v4.1-flash），唯一生产代码写入者。
前置：R6 四根因已由 Codex 独立确认、全部 exit0；本轮唯一缺口见 `codex_pending_version_checks.py`。

## 复现

```
python -B -W error docs/human_fall/evidence/2026-10-01_gl02_r6/codex_pending_version_checks.py
```

结果：Ran 2 tests，failures=1，exit1。
- `test_changed_context_returns_original_capture_terminal_before_clear` FAIL：context 切换后原 accepted capture 无终态回执。
- `test_same_context_pending_stays_pending_and_invalid_switch_is_atomic` 已 PASS。

## 根因

`node_runtime.FallNodeCore.apply_ground_context` 在 `changed=True` 分支（如 `calibration_id` v1→v2）先 `self.baseline.invalidate("ground_derived_changed")` 并 `self._baseline_request_id = None`，直接丢弃已 accepted 的 pending capture 绑定，未发出原 request_id 的 failed 终态 selection_ack。属验收 v1 请求矩阵“pending/ready→版本切换：退休旧资格，关联请求终态策略明确”（A05/A10）的既有要求，非新功能。

## 最小修复

在 `changed` 分支清旧绑定**之前**：若 `baseline.status == "pending"`，复用 `baseline._fail("ground_derived_changed")` 置 failed 终态，再用既有 `_baseline_completion_ack()` 生成带原 `request_id`/`track_id`/`selection_version`/`time_epoch`/失败原因的回执，作为 `record["baseline_ack"]` 交给显式 `apply_ground_context` 调用者。随后照旧 `invalidate`、清 `_baseline_request_id`、清缓存/tracker（保持新版本 reset 既有行为）。

- 相同上下文（`changed=False`）：不动 baseline，不返回回执，pending 保持。
- 非法更新：`_resolve_new_context` 先抛错，赋值前失败，pending/`_baseline_request_id`/`calibration_id` 原子不变。
- 不重发旧终态：`invalidate` 后 status idle、`_baseline_request_id=None`，`status_state`/`_cancel_baseline_on_ground_loss` 不会再产回执。
- ready 历史：仍由 `invalidate` 进 `retired`，行为不变。
- 无 ROS 在线 reload 调用者；纯 API 生命周期字段，不加回执队列/热更新框架/接口。

## 保留行为

新版本 reset 缓存/tracker/基线资格；源 time_epoch 与旧事件不变；辅助 IMU degraded 不触发；不改冻结资产、旧 Codex 脚本、R6 其他文件。

## 检查计划

先 `codex_pending_version_checks.py` 2 方法，再 R6 12 方法生命周期与 fall 全回归（受影响）；其余 R6 已验证项引用其 SHA 证据，不机械复跑。D01 NOT_RUN / P01 BLOCKED。

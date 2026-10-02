# GL-02 R5 集中诊断（实现前）与根因修复记录

基线：GL02_ACCEPTANCE v1（A01–A12 + 入口/状态矩阵 + 请求与恢复矩阵）。
范围：仅生产 `core/calibration.py` 与 `core/node_runtime.py` 两处共享入口；不改冻结配置/driver/候选算法/UI/消息 schema/采样时钟语义。旧成功失败与 R4 证据（57_*/60_*）保留。

## 根因与受影响入口

| # | 根因（同根因入口全汇合） | 受影响入口/消费者 | 最小修复位置 | 保留行为 |
|---|---|---|---|---|
| 1 | `ground_context_calibration` 比较相同只沿用 `calibration_id`，产物由 `build_geometry_calibration(...ground, derived)` 重建 → input.sha256/evidence/note/reference/transforms/rotations/status/verification/constrained_ground 全部丢失（R4 P2） | `_resolve_new_context` 空 reload；同内容 ground+derived 配套 reload；同内容 ground-only reload | `calibration.py::ground_context_calibration` 相同分支：整份父产物 `validate_geometry_calibration(copy.deepcopy(parent))` 后原位替换绑定 ground/derived，返回标准产物再校验 | 真正局部更新仍走新 id 路径（ground-context-sha / caller id 仅此分支）；不自动复制 verified 标志；failure 时旧上下文保持；paired 入口未取消 |
| 2 | `_feed_baseline` 仅在 `_ground_context_unavailable()==False` 时调用 → accepted 后的 pending 在 monitor unknown/degraded/latch 下无终态、无 ACK（R4 P1） | `process()` 首个 monitor 失效帧；`status_state()` watchdog（无新云帧/流 stale）；`handle_request` 请求时拒绝已建立（R4 保留） | `node_runtime::_cancel_pending_baseline()`（R5 新增，私有）：`_fail("ground_monitor_unavailable")` + 原 request_id 终态 ACK；`_process_locked` 失效帧先调；`status_state` watchdog 调用后附加 `baseline_ack` 于 state payload（additive） | 非 pending 不动；失败样本丢弃不拼；ready 经 `apply_ground_context` changed 分支在 `invalidated` 退休（receiver 历史保留）；选择/释放/版本切换原失效路径不变；source stamp/采样窗不受 receive 秒推进 |

补覆盖检查（claude_r5_checks.py，4/4 OK）：
- 同版本空 reload：完整产物/metadata/monitor 实例/pending 任务保留。
- 首个 monitor 失效帧：pending→failed、原 request_id 终态 ACK；恢复帧不拼接、collector.failed 保持。
- 无新云帧 watchdog：在 receive 单调钟下 pending→failed+终态 ACK（state payload `baseline_ack` additive 字段），`start_source_s` 未被 receive 秒推进、samples 空。
- 同版本 reload 保留 ready 资格与 monitor 连续性；新版本 reload 退休 ready 资格且旧制品留在 retired 历史（collector 直接驱动，模式同 test_hf05_tracking 的 ready\_基线用法，不手动赋 status；端到端 pending 流由测试 1–3 覆盖）。

## 接口/语义记录

- 新增 `state["baseline_ack"]`（仅 watchdog 取消时出现的附加字段）：additive-only，沿用 state payload（kind=target_state, schema_version=1）作为 ACK 附着载体，不改变原 `selection_ack`（kind/schema_version）或 webui 已读字段；既有读 `state.baseline` / `state.observability` / `selection_ack` 的消费者不需改。ROS wrapper `human_fall_node.py` 无改动：status_state 返回 state 仍会全量发布，worker 已透传该 payload。
- 失效即取消为 R5 授权内选择；原 R4 允许的有界超时/暂停策略不再另行实现。
- 局部变化（paired 更新、ground-only 更新、完整 artifact）继续走 `_resolve_new_context` 的完整校验+新 id 路径，不因此轮 reload 修复降级。

# GL03实现中检查点独立核查 / 2026-10-02

不是正式提交/验收结论。实现者已按Codex预算控制停止写入，原294回归/22新增方法通过；独立8方法目前2通过、5失败、1错误（5个输入子反例合计8 fail）。文件50有零附近浮点atol=0导致的夹具断言问题，51改为1e-9后确认源预测逆变换正确，剩余reference框有真实0.038m差异。原始错误保留，不归因代码。

通过：G02实际过滤/采样索引→同一输入点→ground min/max/逐轴median、非交换中位数夹具、原数据不变/finite JSON；G05 stale/monitor失效屏蔽。来源v1验收表/获审契约。

四根因：

1. G03完整绑定：`_validated_ground_derived`只调nested validator且没给artifact，不调全量父validator。bool schema/空ID/矛盾verification仍启用GDID；实际frame_id与from_frame、显式ground的d与父ground不一致仍给actual_points。用共享完整validator验证带derived的完整产物，并在候选特征构建前绑定实际frame/ground；保留旧无derived摘要。损坏可拒绝或降级unavailable，不能默默报有效GDID。
2. G07 optional兼容：validate_snapshot无条件要求bbox_ground_from，导致所有旧合法候选（没有4个新字段）被拒绝。旧4字段全缺失应合法；显式新扩展出现时才校验完整一致性，不放弱现有损坏断言。
3. G05选择缓存：handle_request更新tracker/selection，但status_state复制旧_last_state。解除后仍t0001+旧ground actual；重新选择后tracker=t0002而state仍t0001。检查所有请求引起的绑定/资格变化，及时清空/重建缓存，等待新观测时不伪造测量；缓存重放仍不重执行，GL02 pending/watchdog/ACK行为保留。
4. G04预测reference框：source预测逆变换已正确，但新增bbox_reference_min/max保持最后实测框，source框已按预测移动。reference框如输出必须对应预测位置/标记，或在无当前点集时明确null；不能给另一位置的旧框。ground实际点字段为空保持。

独立脚本codex_geometry_checks.py、51_codex_checkpoint_final.txt。请一次修共享根因与兄弟入口，别只改某一断言。剩余G06/O01按原任务完成探索性连接证据，真实全景逐帧/可信地面identity不足如实BLOCKED；分离若无触发可信条件不强做/不默认开。

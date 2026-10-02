# GL02 R7：集中收口最后的pending标定切换路径

继续本GL02会话，指定模型保持opencode-go/deepseek-v4.1-flash。日期2026-10-02 Asia/Shanghai。R6四根因已由Codex独立确认全部修复，12方法、R4/R3/R2/static/Claude R5、271 fall/follow/UI均exit0，不要重做。唯一生产写入者，不启动GL03/部署/采集/联网/commit/push/reset。

Codex核对验收v1请求矩阵“pending/ready→版本切换：退休旧资格，关联请求终态策略明确”补查时发现审查遗漏：`apply_ground_context(changed=True)`直接invalidate baseline、清_baseline_request_id及缓存；已accepted的capture丢失原request_id而没有取消终态。此为A05/A10既有生命周期要求，不是新功能，Codex承担未在R6集中诊断时跑这一行的覆盖遗漏。

只需读：GL02_ACCEPTANCE.md请求矩阵；evidence/2026-10-01_gl02_r6/codex_pending_version_checks.py；当前node_runtime的apply_ground_context、_baseline_completion_ack和相关调用者。WORKFLOW/ponytail沿用本会话已读要求。不再重读整个历史日志。先实跑2方法脚本，记录新evidence/2026-10-02_gl02_r7/00_diag.md，然后最小修复。

修复：context切换验证成功后、清旧绑定之前，对pending capture构造原request_id/track_id/selection_version/epoch的failed终态selection_ack（明确ground_derived_changed等原因），并在显式apply_ground_context的生命周期返回baseline_ack（或已有status返回通道）交给调用者。此纯API没有ROS在线reload调用，不新增热更新框架/回执队列/接口。保持新版本reset缓存、tracker、基线资格的既有行为；相同上下文不取消、非法更新不取消、不重发旧终态，ready历史依旧retired。复用现有_fail/_baseline_completion_ack，保留最小文件范围。

允许改core/node_runtime.py，必要一个有效回归、新R7证据与returns/GL-02.md末尾“OpenCode GL02 R7”；不改旧Codex脚本/历史断言，不动R6其他文件和冻结资产。记录真实SHA/退出码与原R6源码对比。

先codex_pending_version_checks.py，再12方法生命周期与受影响fall回归。其他已验证文件若不变，引用本轮CodexR6对应SHA证据，不机械复跑所有无关检查。SUBMITTED，D01 NOT_RUN/P01 BLOCKED，不自判总体PASS，写完停止，Codex再独立验收。

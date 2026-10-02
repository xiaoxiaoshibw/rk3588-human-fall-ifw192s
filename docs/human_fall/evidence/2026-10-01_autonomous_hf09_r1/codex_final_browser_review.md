# 最终真实网页复测 / 2026-10-01

正式URL：http://192.168.3.125:8090/human_fall/index.html 。浏览器IAB，复测的是实际RK3588输出，无前端算法或假动画。

- 12:30–12:40轻量显示持续约8.2–8.6Hz/2.5–2.7MiB/s、drop0，日志无Send buffer limit reached，候选稳定可用。原完整数据约49k点，显示最多12000；算法仍处理完整输入。
- 最终版本20261001T051310Z，随后持续连接约12:57–13:23：显示约8.6–8.8Hz/2.5–2.8MiB/s、drop0，无buffer溢出。候选源帧框在实际3D场景中可见，截图codex_final_live.jpg。
- 实际按钮select回执接受；选的是未知几何簇，不当作真人身份/跟踪准确性验收。随后lost暴露编号复用的几何投影缺陷，根端新增两条独立失败并修正、两端通过；新版本默认unselected。
- 实际release回执接受，位置清--、预测未选目标；最后断开后track--、fall unknown、observability unknown、位置--、请求通道不可用。截图codex_final_disconnected.jpg，交付tab保留，测试WebSocket已释放，用户点连接可再使用。
- 缺地面时degraded/unknown、标定未提供、基线idle是诚实门控；无confirmed、无真实动作标签。真实IMU单位待核验，设备异常255只标含义未知。

没有实际自动化拖框手势或测GPU FPS/绝对端到端延迟，投影/矩形相交与同后端选择协议已有独立验证；这些待现场/专项性能验收。更新计数“呈现Hz”不冒充GPU FPS。原始raw流诊断可用?points=/innolidar_points，但带宽压力记录保留。

# GL-02 Claude R4 Codex独立复审 / 2026-10-01

结论：**软件 REWORK；GL-03 不放行；设备兼容 NOT_RUN；真实物理 BLOCKED。** 原R3五项反例已闭合，另外两项生命周期/产物保存边界未闭合。用户继续手动给Claude Code；Codex未启动实现CLI、子agent、部署或采集，也未修改生产源码/原回归测试。

## 独立通过的证据

本机 `python -B -W error`：R3原五方法5/5 exit0（50_*），R2原七方法7/7 exit0（51_*），静态六方法6/6 exit0（52_*），全部fall回归271/271 exit0（53_*），follow 2/2 exit0（54_*）；两个webui各18/18 exit0（55/56_*）。原R1裸块拒绝已由R3获审契约解释，本轮不要求恢复不完整裸块入口。

版本/GDID切换、caller解绑、新请求拒绝、局部遮挡不锁存和整体+0.1m平移正例的已通过部分保留，不重做GL00/01。

## 尚未闭合的两项

1. **同版本reload丢失完整产物元数据（P2）**：`core/calibration.py:865–928` 的 `ground_context_calibration` 仅比较ground/derived决定沿用父ID，最后无条件调用 `build_geometry_calibration`，只传ground/derived，不传原input、note、reference、transforms、rotations、status、verification或扩展的constrained_ground。`_resolve_new_context` 的空reload及相同ground+derived路径都触发它。本轮合法合成artifact包含input.sha256/input.evidence/note，调用这两个路径后，changed=False且calibration_id=v1，但SHA/evidence/note被删除。至少空/相同上下文应完整校验、deepcopy并保留父产物；真正局部变化应明确保存仍有效的来源记录及旧记录失效策略，不能把来源删掉后继续沿用原版本。此反例不使用实测外参，也不要求升级verification。
2. **已accepted的pending在monitor后续失效时仍无限悬空（P1，R4未完成部分）**：`node_runtime.py:698–701` 仅在ground可用时调用 `_feed_baseline`，不可用时既不处理已有pending也不走collector timeout。独立检查用4000个合成地面点+人体得到monitor=ok，select与capture均accepted；随后持续20个1秒帧仅有人体、monitor不可用，baseline仍pending，超过默认max_duration_s=10；原request_id仍挂起，没终态回执。R4只修复了请求进入时不可用的拒绝。需要对正在采集的基线明确取消/失效并回执，或保留有界超时；恢复不能把失效前后的采样拼接成合格基线。已有ready的暂停/失效策略也应明确并验证。

独立脚本 `codex_r4_reload_checks.py`：3方法3失败、exit1，见57_*及60_*。57首次运行后把尚未执行到的第二个pending断言改为检查终态回执（允许保留历史request_id）；60最终再跑仍同样3失败，不改第一失败断言。两种reload分别覆盖同一缺陷，不计为三种独立问题；原成功日志完整保留。新增脚本仅存审查证据目录。

## 范围和设备边界

master@c96489e40037aca810b23b98d71ba34632d18bd0；23项源码/配置/原独立检查SHA均与R4提交记录相符（58_*）。driver SHA=1b3d57939dca511874eb66b42fd5d57132ad95220f85224d1dd090ed3edcb787，用户差异和Windows的src/CMakeLists.txt表示未动（59_*）。未commit/push/reset。

板端没有本轮独立兼容结果；Claude提交09_board_isolation.txt记SSH255，未因软件失败重复联网。真实地面/安装角度/光学窗口到点云原点/IMU与外参仍BLOCKED。雷达向下看，1.1m仅光学窗口现场高度，不能据此宣称点云原点已校准；合成coherence/sustained_frames不作实测。

下一步手动递交 `../../AI_PROMPT_GL02_CLAUDE_R5.md`，只修上述两项；通过后再复审，不启动GL-03。

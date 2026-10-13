# 新根因与最小补丁审查草案

本轮零production算法补丁；下列代码形态只说明审查位置。现有数学/PIPE/确认门不动。每项必须独立授权、独占新evidence、单writer后才实施。ponytail：C:/Users/30680/.codex/skills/ponytail/SKILL.md。

## BUG-R40-I01：invalid XYZ preservation

复现：02_research.js的zeroAudit读原始28B记录；PL.denoise([0,0,0,i])=空，而现有leveling载入后[0,0,1.3231915,i]通过。旧leveling报告source.invalid_xyz_count=1250003、reference=778477，与原bin零XYZ计数相等。来源04_zero_xyz_reproduction.json。

根因：leveling.export_dataset用finite/nonzero mask；registration.loadFrames→transformBuffer、human_detect.js局部apply_Rt、replay.js.apply_Rt_inplace不验证raw XYZ而把无效占位转换为场景坐标。消费者：build_static_map、reference_map、fineStatic/normal/measure、pipeline/可视化。保留附带intensity/ring/timestamp与row索引；intensity不作为无效标识。

最小审查形态：在各raw→leveling实际循环计算R/t前，若任何XYZ非finite或XYZ全0，则保留原记录并continue。不能在变换后的坐标判断“XYZ全0”，因为可能是有效地面点；不能改已有所有点距离窗到raw空间。registration.transformBuffer共享变换入口亦被registration.applyRegistration调用，先核caller语义后加同样保护；归档代码、历史artifact/输入不可改写。若抽共享helper只为重复两处guard，优先最短guard，无大型统一loader重构。

回归：无效全零且intensity非零；非finite；有效坐标含一个/两个0；有效点double→float32逐位对账；28B opaque字节与索引不动；同类载入入口一致。新绑定必须新artifact且另授权，原当前artifact继续STALE；不得按新有效分母临时给旧gate换PASS。停止：无法统一原始有效性/帧身份时不碰生产。

## BUG-R40-T01：assignment reuse within frame

最小repro：04_tracker_reproduction_and_trace_r2.json reproduction，先2个NON_HUMAN帧，年龄3时三个CONFIRMED_HUMAN簇在0.75m内全部命中track1，votes=[0,0,1,1,1]，第三簇confirmed=true；pose_history=[0,1,2,2,2]。真实S f46两个输出簇均track3，距离.07036/.66665m，重复0票；不能借真实f46虚称新增正票。

根因/入口：human_pipe_lib.js Tracker.tick候选循环，没有assigned/used集合；本帧新建track立即进入同一tracks列表。调用：pipeline_frame→human_detect._run_pipe_frame及离线shadow，tests直接调用。候选输入顺序由point/voxel Map插入顺序+BFS决定；循环内EMA改变后续距离。

最小方案：每tick局部used track-id Set，候选匹配排除used；新建/命中后立即标used。保持cluster顺序、nearest门/EMA/原id生命周期；每track每帧只有一次vote/history。无需全局匹配库/新参数。仅此guard未解决观测窗口过期问题，T02须独立处理。

回归：同帧3簇分配唯一track、重复调用同frame明确拒绝/幂等策略、单人连续轨迹原行为、f46/f53；不要求反序新id数值相等，不把候选次序改变当GT identity。geometry/foreground严格等价，tracking预期差异单列。停止：需要Hungarian或track门调参则退回设计，不能顺手重构。

## BUG-R40-T02：observation window instead of frame window

最小repro：f0/1正→f2..8空→f9正，votes=[1,1,1]被确认；最近5帧只有f9正。实际S track4/f61 [53,55,56,61]/[0,1,1,1]同样确认。r2文件保存repro/真实样本。

根因：votes仅在cluster命中时push，空帧只lost++，没有frame索引或过期；与最近5帧声明矛盾。入口同T01；human_detect._run_pipe_frame仅避免立即重复同frame，seek倒退/跳跃仍可能传入旧tracker，这是生命周期风险，浏览器行为本轮NOT_RUN。

最小方案：票带frame_idx，确认只统计当前frame-4..frame，丢失帧没有正票；每frame每track一次（先T01）。保留window5/votes3/min_age3/lost8；重复或倒退frame由明确入口守卫/重建协议处理，不能默默复用未来票。若需改变浏览器seek语义，另列最小调用者修复，不触及Fall逻辑。

回归：上述gap不能确认；连续3/5原确认；短lost、gap>window、gap>lost、重复/倒退、id重获、S f61/63；patch后的逐行GT对账和原T38-06仍需完整新轮。停止：真人身份或生命周期尚未可审查，不能以test PASS宣布人体连续性PASS。

## 非bug项与边界

reference-z crop符合冻结坐标契约；两拟合面不一致是已测风险而非已证错误数学。固定XY网格对旋转/平移不保持拓扑，是现有算法性质；改聚类要先GT，不自动列实现bug。gate算数/60%trim符合当前定义，不能重命名后放行。旧BUG-R39-M01三行统计已完成，不重新实施。

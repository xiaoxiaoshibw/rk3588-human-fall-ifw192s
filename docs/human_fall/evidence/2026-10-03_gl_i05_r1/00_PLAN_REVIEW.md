# GL-I05计划审查 / 2026-10-03

状态DRAFT_READY：本轮只准备计划/提示词，未执行未来原型、未OpenCode probe/派发、未改生产源。WORKFLOW、GL-I04收口/独审/范围补正、实际原型/冻结调用链和最终台账已复核。ponytail本次完整阅读C:/Users/30680/.codex/skills/ponytail/SKILL.md，用于最小代码研究范围规划。

规划期间唯一计算：planning_trace_audit.py重算GL-I04已有32条完整trace；旧ledger SHA8ebd03d77ba382543cd61fdb60491be9c2ccbc3671823586f6ff6ed47ace70de前后一致，未产生新RANSAC draws。数学指标/原结果区分见02_existing_trace_audit.json。

## 被旧数据直接否定的下一步方案

“只有best与近优都similar就接受”：32条中8条有top-to-near distinct=0而near-pool distinct>0。high_noise seed7原序中best434/near422/池内distinct33；所以简单best-only研究有已知漏判，不能作为修复路线。全部highest tie和NEAR池内部关系应保留，而不能把非传递链通过中间best吞掉。

“新原型会让真实数据过”：negative-X WHAT_IF全部693见证都在near池、distinct3519，四holdout仍不一致；approved正X没有合格raw。改搜索不能解决批准source up/录制extrinsic/区域身份，未来真实成功不设为软件完成目标。

“先加缓存会快”：仅有I04本机整体成本>2×冻结fit，阶段也不同；缓存依赖及命中率尚未验证。先profile/证明，再选单run有界精确mask复用；无收益可以否定，不强制引入缓存或许诺速度。

## 新计划如何区分问题

先建立ALL/NEAR/BEST_ONLY独立oracle，再测固定首锚0/4/8°全相似的充分证明是否有顺序假拒；0/6/12°链/middle-best/late/tie及budget反例仍未决。弱distinct满足完整近优池证明只允许新研究语义dominant，不声称global唯一；这是新GL-I05契约，GL-I04结果不追改。成本优化在正确性之后，采用具体依赖证明，数值门/批准selector不变。

空间证据分支复用已审全点诊断，增加逐帧定位能力而非重写生产工具；只核增量本地录制材料，若未出现新证据维持B类BLOCKED，不重复全历史。不部署/采集/网络，不靠残差筛validation。两个分支最终共同决定下一步：继续算法证明、需要新选择版本还是仍需要物理资料。

## 范围和门控

默认research_01最多4个主要文件（oracle/原型/experiment/集中test），确需空间入口加1；可以减少。无src/config/旧test/GL-I04/批准input修改。软件反例FAIL先修，研究没赢可决策不采用；缺物理证据不阻软件。所有C/E/S与Q映射以唯一GLI05_ACCEPTANCE v1为准；ROS热reload裁剪，不裁剪caller/文件身份/cache/version/算法terminal。

Codex主开发/单writer，自验与manifest完成后停研究写入；指定Go Flash/defaultDB只读二审，先一次≤1min无工具probe。吸取I04过程问题：manifest不hash正在写的stdout；原生skill不访问外部技能目录；二审自己的失败脚本和日志也新增编号保留；真实日志路径/session/exit须能从原始输出复核；外部新增和本单回传新增明确区分。

本计划没有降低GL-I04验收，也没有授权GL-05设备、生产接入或真实标定。用户后续明确执行主提示才启动本单，当前所有新软件验收NOT_RUN。

# GL03 R2 独立复审 / 2026-10-02

结论：REWORK，集中闭合reference上下文与O01统计/推论。R2九方法已由Codex原样独立通过；原R1地面数学、optional兼容、状态缓存等通过部分保留。

G03/G04/G05：只读审查复现reference未绑定实际from_frame、known reference label和当前父产物。无ground节点忽略reference.from错误，外来frame仍degraded/可选人/有reference位置。合法full reload版本B更新T_reference_lidar却保留self.transform版本A，新快照报B、参考数值仍A。Codex新增codex_reference_checks.py四方法全部失败（71_reference_before）。一处共享reference resolver绑定实际源/已知目标/当前canonical transform，prediction消费实际选定域；不能仅加一个ground守卫。

O01/G06/G07：只读独立NumPy与occupied-cell BFS复算确认六组分量和成员/AABB正确：1→2、1→1、1→7、1→1、1→1、2→2；原4数据SHA不变。但代码将旧逐面剥离support_fraction/RMS复制到本轮完整pool支持集，统计口径不一致。正确本轮count：18975/13945/9176/13768/11163/6638，对97411为19.4793/14.3156/9.4199/14.1339/11.4597/6.8144%。旧plane3所报7.8964%等不是本轮结果。应本轮重算，历史指标分名保留。

horizontal_candidate仅abs(normal_source_z)>0.94；雷达下看但角度未知，不能说plane3是唯一可能地面、其他是非地面，不能据1→1排除地面桥接。所有六面均保持未核验hypothesis，连接变化可以报告，物理身份/单帧真实根因仍BLOCKED。补清每帧finite/nonzero过滤、每20有效点抽1、跨47帧拼接、CSV四位小数；本轮不是完整生产候选过滤/逐帧重放。

只读助手无修改；生产写入仅OpenCode，R2 CLI退出0且已停止。中断期间git HEAD变为49eb7581、webui/dist有外部差异，保留不归因/不回滚，源码上述两项hash与R2提交一致。直接派R3，其他关卡不启动、无部署/采集/联网。

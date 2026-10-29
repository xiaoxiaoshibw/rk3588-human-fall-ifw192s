# 下一阶段唯一拟验收 V2（ND01–ND08）

拟工单HFUS-INDOOR-DATA-QUAL-01，DRAFT_READY_FOR_DISPATCH，未执行。仅约束下一工单，不取代本轮A01–A16。逐条用PASS/FAIL/NOT_RUN/BLOCKED，不用测试总数替代，不自行ACCEPTED。

|ID|要求|必要观察/证据|当前|
|---|---|---|---|
|ND01|新明确派发、独立单writer与冻结输入/预算|branch/HEAD/status、相关源及三个ZIP/member SHA；只新记录，CPU4/RSS/字节账本|NOT_RUN|
|ND02|框字段与旋转定义可追溯|原schema/转换器/原JSON/真实人工几何确认，版本/单位/适用成员清单；未解决保持UNKNOWN|NOT_RUN|
|ND03|真实人工完备性/负候选审核|至少20拟审样本及所有拟test帧，真实审核者/日期/SHA/理由；冲突真实二审，AI不冒名|NOT_RUN|
|ND04|独立采集组与重复账本|至少2可核实组、来源证据、精确/近重复冲突同组、人员场景限制、split SHA；不足BLOCKED|NOT_RUN|
|ND05|候选监督P/N/U和资格结论|固定IoU/唯一匹配/负类完备与.20m安全门，≥20正/≥20可信负/拟test≥10GT目标；不够不弱标补齐；训练0|NOT_RUN|
|ND06|审阅页与版本/状态操作矩阵|完整房间/待审核标记/源行，run/frame/model/审核revision同绑定，快切/缺证据/漂移/冲突/恢复，实际浏览器|NOT_RUN|
|ND07|必要软件验证与保护|Python -B -W error、真实源一帧核对、旧资产SHA、错误/空输入/门边界与字节预算|NOT_RUN|
|ND08|审查、报告和后续有界建议|指定OpenCode只读实际模型/完整brief/权限/原日志及集中复验，逐ID结论；只建议，不自动训练/补采/部署|NOT_RUN|

完备性/独立组/两类不足时，相应条目BLOCKED，仍保留具体可看审阅成果；资格审查完成不代表训练有效。真实逐点/空场/家具指标无GT仍NOT_EVALUABLE。

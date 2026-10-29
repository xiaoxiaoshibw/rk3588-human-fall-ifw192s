# HFUS-INDOOR-AI-TEST-01 实际结果 / review_candidate_r2

状态：SUBMITTED；算法目标BLOCKED，非ACCEPTED。唯一判据是原ACCEPTANCE_V2.md；此文件只记结果，不另立验收。

|ID|状态|证据与边界|
|---|---|---|
|A01|PASS|独立目录与新证据、旧资产SHA核验；未训练/设备/Git写|
|A02|PASS|186对逐ZIP/member SHA、float32×4/有限值/标签检查；不复制点云|
|A03|BLOCKED|526框旋转/末列未解决，完备UNKNOWN，人审0；显示明确AABB代理|
|A04|BLOCKED|0个可信独立采集组；保守单组，test0，未伪造随机split|
|A05|PASS|原cluster参数+HDBSCAN全186帧实际运行，源行/AABB保留；未分类几何候选|
|A06|PASS|旧RF/G0/shadow契约审计；具体缺依赖见MODEL_APPLICABILITY，不伪兼容推理|
|A07|BLOCKED|可信正/负0/0，所有候选UNKNOWN；旋转/完备门不绕过|
|A08|BLOCKED|新RF/PointNet无两类监督，神经启动0/steps0/训练秒0，无随机权重产物|
|A09|BLOCKED|几何独立进程重算见REPRODUCTION.json；学习权重重载无有效输入，BLOCKED|
|A10|BLOCKED|全部186帧有处理/排除账本；固定test0/可评GT0，主指标NA，不把代理当主表|
|A11|BLOCKED|CPU分阶段时延已测；可信覆盖/碎片、新RF/PointNet公平三seed不可评价|
|A12|PASS|实际浏览器同帧三栏、真实原点/代理框/实际候选；NOT_RUN/BLOCKED空预测。仅viewer软件，不是人检效果|
|A13|BLOCKED|全372帧×模型审阅案例可查；可信成功/失败无GT依据，0，不冒充10成功/10失败|
|A14|PASS|Python -B -W error、JS generation/实际HTTP/浏览器转换；源SHA/非法请求/缺预测拒绝|
|A15|NOT_RUN|开发后指定OpenCode只读审查；AI审代码记录，非人审或独立数值实验|
|A16|NOT_RUN|八问和实际瓶颈；下一阶段只规划，审查不可用则待审草案|

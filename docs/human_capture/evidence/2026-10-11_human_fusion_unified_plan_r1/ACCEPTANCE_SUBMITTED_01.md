# HUMAN-FUSION-UNIFIED-PLAN 唯一验收表

**v1 · 2026-10-11 · 仅进度归一/算法开发规划/指定OpenCode只读审核**

依据[当前工单](tickets/HUMAN-FUSION-UNIFIED-PLAN.md)、[统一计划](HUMAN_FUSION_UNIFIED_PLAN.md)。表的标准在审核前冻结；最终实际状态/证据写回传，不以计划写完或总检查数宣布整体ACCEPTED。下列P01为规划ID；PHY01才是物理限制，避免与旧工单物理P01混用。

| ID | PASS所需证据 | FAIL/BLOCKED条件 | 起始状态 |
|---|---|---|---|
| P01 | 读两入口/AGENTS/ponytail/RETURN_TEMPLATE；本轮授权与后续NOT_RUN明确；当前研究与HF/GL范围分离 | 扩大到实现/采集/部署/ML/生产切换 | NOT_RUN |
| P02 | 含untracked/ignored工作树SHA、branch/HEAD、生产/输入/旧证据保护及漂移原因 | SHA缺失或未知路径漂移未解释则BLOCKED；本轮越界写入FAIL | NOT_RUN |
| P03 | 三总结/诊断及源码/JSON冲突归一：B mask非全链、f128已入混簇、PointNet中心化、unique已在V2、GT分母、proxy范围 | 继续使用推翻的因果/虚假完成结论 | NOT_RUN |
| P04 | 目标架构说明共同背景入口、PA/PB、actual union、模型契约、dual tracker/retention迁移、GT只做事后评价 | GT/未来/预测参与真实检测；未保留控制变量；暗中混用A/B | NOT_RUN |
| P05 | GT资格/UNKNOWN/传播相关性、无候选FN、classifier前proposal、partial unmatched非FP、legacy/strict重算、ID/时间/性能契约明确 | 用只有正例/局部GT/预测/点率替代最终验收 | NOT_RUN |
| P06 | 顺序/范围/复用/依赖/失败路径/阶段门可执行，D03 FAIL不阻有资格D04/D05实验，D06联合计分 | 循环依赖、同轮多变量、拼接最优成绩、不留失败 | NOT_RUN |
| P07 | 三轮独立设计记录：事实→架构→反例，每轮具体修订可追；冻结提交SHA | 仅写“多轮思考”而无可审查记录 | NOT_RUN |
| P08 | 真正调用指定OpenCode，实际probe/审核日志、exit/session/prompt SHA；只读权限、完整意见；明确服务失败/超时 | 未实际审核、换模型冒充或exit非0而称PASS则FAIL；服务不可用BLOCKED | NOT_RUN |
| P09 | OpenCode可复现意见逐条处理或保留阻断，修订与必要复审另存；最终回传逐ID、文件/link完整 | 隐去审核FAIL；未闭合重大意见却报完成 | NOT_RUN |
| DEV01 | 后续D01～D07不是本轮完成标准，实际算法指标只有实施后另单判定 | 本轮不得宣称已实施PASS | NOT_RUN |
| DEV02 | 人工身份/独立负例/真实关节/新场景有合法充分证据后另单判断 | 当前数据不足，保留BLOCKED | BLOCKED |
| D01 | 当前无设备/部署/采集执行授权 | 当前保持NOT_RUN | NOT_RUN |
| PHY01 | 当前没有新的物理/现场/生产资格 | 当前保持BLOCKED | BLOCKED |

本表唯一；后续任务本计划给的是拟定实验目标，启动时各自建单/唯一本版验收。若改本表标准须新版本并解释，不能回填旧FAIL。

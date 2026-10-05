# GL03 R4 连续失败后的设计复审

按用户要求和WORKFLOW第5节，先审查根因再给返工计划。软件G03/G04/G05 FAIL；不是因未连接板端，也不是现有检查全红。旧十方法已经通过，但操作组合仍违反同一固定绑定要求。

## 错误在哪里

1. 实现方案选错了固定边界：resolver返回深拷贝，并不意味着节点保留的startup输入已解绑。reload会再次读取raw self.transform。
2. 实现方案选错了版本比较对象：canonical reference可能unknown/None，但实际tracker可能正使用standalone T；只比较canonical记录遗漏实际绑定。
3. artifact分类把合法kind当作是否需要验证的条件。损坏kind应是验证失败，不应触发legacy兼容。
4. transform构造器的数值/内部合法性，不等于它与父lidar/实际source一致。

Codex的遗漏：上一轮虽然操作表列了caller/reload/occluded，也只给了孤立检查，没有提供其合法组合的事前反例；没有检查非合法kind与父lidar标签。实现者没有把表中的固定绑定贯穿到reload。两者均是具体设计/覆盖问题；当前不能从次数推断模型无法实现。

## 已审最小计划：固定输入、解析 prospective 绑定、先比较后赋值

不新增框架，继续现有resolver和apply_ground_context：

| 边界 | 审定规则 | 回归/反例 |
|---|---|---|
| startup输入 | standalone参数在节点持有的入口即解绑；任何reload只读固定副本，不再读caller | caller修改后正常快照及same-IDreload再occluded均固定 |
| 解析父资格 | 有明确kind的记录必须走支持kind验证；错误kind不能伪装legacy。无kind旧最小摘要正常路径保留 | 合法完整/合法legacy均通过；错误kind不可用 |
| 跨记录源 | 有父frames.lidar时T.from必须与之匹配，且与实际producing frame绑定；to按父reference标签绑定 | 父lidar矛盾与外来frame均拒绝/不可用 |
| reload准备 | 先验证新artifact并用固定standalone来源解析其prospective有效reference，再核对声明父记录和实际绑定 | known/unknown/standalone、有无ground两类资格不得混 |
| 同ID | canonical reference变化或实际有效reference变化，在任何赋值前拒绝；同内容reload保持固定绑定 | 原同ID拒绝与新standalone组合反例，pending/locked/status无副作用 |
| 新ID | 完成验证后原子绑定同份新artifact/ground/有效T，再执行现有资格失效 | 旧standalone不阻止合法新canonical；known→unknown fallback不读取caller改动；旧事件/seq/stamp/epoch不改 |
| 消费 | 快照/预测都用实际固定有效T；无有效T明确unavailable/source-only原义 | reference优先后遮挡预测不得错标source |

不重写数学/聚类算法、不用新schema、不新增用户可写transform热更新接口。不要通过仅修prediction遮盖source选错。

实现者先把此表映射到实际函数/赋值顺序/检查，核对无遗漏再实施。本文与context_checks.py在实现前提供，禁止改旧断言换PASS。检查时先原9/4/10/8与本轮4方法，再受影响状态矩阵/主线回归；完整数据/模型切换/部署不进入这轮。

失败处置：若同根因再次出现，必须先核对设计表是否落实到实际源码、检查是否覆盖操作组合，记录计划/实现/服务类别，不直接派相同提示词。更换模型只能在授权后以同输入/约束/反例做能力对照；当前不授权或执行切换。

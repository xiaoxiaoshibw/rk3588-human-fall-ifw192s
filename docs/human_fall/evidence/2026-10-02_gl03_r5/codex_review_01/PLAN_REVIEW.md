# GL03 R5 输入兼容分类审查与最小修订计划

当前剩G03，G04/G05已经闭合，不再重做固定输入/reload算法。新失败先按连续失败流程审查：主要是Codex对legacy输入定义不充分，不能仅把返工轮数当模型能力结论。

## 实际调用者与旧输入

- ROS scripts/human_fall_node.py:85–89 对读入JSON先validate_geometry_calibration，传完整artifact；node启动/reload也严格验证完整artifact。未发现需要将损坏完整artifact当摘要的调用者。
- core/lidar_candidates.py:614附近对外输出calibration摘要：calibration_id/schema_version/ground_status/ground_derived_id。这是summary，不是完整产物。
- test_gl03_candidates_geometry.py:238及R4 06_r4_checks.py:56的合法legacy输入：calibration_id + frames + transforms；无需补kind/created_at/verification等完整字段。
- core/pipeline.ReplayPipeline目前不提供calibration热更新，不增加新框架。

这些输入需要兼容；当前失败的完整schema99产物则保留完整结构，kind破损不能改变其资格。旧最小摘要兼容不等于所有无kind对象都有效。

## 已审分类规则（固定G03/G07语义，不新增schema）

先分类，再验证，不“验证失败后降级为legacy”：

1. 明确有效artifact kind，或出现完整产物结构标志，进入完整artifact验证；missing/null/错误kind、unsupported schema/缺ID等按既有validator拒绝/不可用，不能补造kind或把schema99改1。
2. 完整产物结构标志来自既有构造器专属块，例如顶层units、created_at_utc、rotations、verification、status、input、ground、ground_derived、sensor_height_m。它们与旧摘要的ground_status/ground_derived_id不同；出现这些已知完整块不能靠删除kind降级。旧合法完整扩展字段仍由原validator处理，不为未知普通扩展字段建全表黑名单。
3. 缺kind（若需保留null，仅限真摘要形态）且没有上述完整块，才走既有最小摘要兼容路径。calibration_id/schema_version/ground_status/ground_derived_id/frames/transforms可作为已见摘要字段；保留合法standalone和unknown行为。存在schema_version时未知/非法版本不能被认作已支持v1，缺schema的既有合法摘要仍可用。
4. 此后复用已有record资格/from/to/parent/frame绑定。两种父来源的合法transform保持支持，不改source/reference含义、物理flags或caller/reload已过逻辑。

分类是本次唯一修复，适用pure build_snapshot及透传wrapper；node/ROS本来严格加载，保持。无需引入新class/serializer/version升级/自动修复，也无需要求用户决定业务语义。

## 实现前最小检查表

| 输入 | 预期 |
|---|---|
| 合法full artifact及合法旧summary、无calibration+standalone | 原几何与兼容行为保持 |
| 完整artifact kind删除/null/错误字符串；schema99/损坏ID | 拒绝或reference unavailable，不能进入legacy成功投影 |
| 真旧摘要无kind，schema缺省/支持v1，合法frames/transforms | 保持旧投影 |
| 真摘要存在非法/unknown schema、坏reference记录/frame绑定 | 拒绝/不可用，不能制造资格 |
| 正常full artifact带ground/derived及扩展 | 原完整validator，旧几何与源索引不变 |
| caller修改/reload/occluded、同/新ID | 沿用R5已过固定绑定，不能回退 |

旧closure_checks及历史失败只读，先把上述分类组合在R6诊断/检查中一次列清，再实施。直接复用constructor/validator，不再只加“kind==某个坏值”分支。

范围：必要calibration分类及有效回归，其他源码原则上不改。沿用O01，真机/真实身份仍NOT_RUN/BLOCKED；不自动派发R6、不换模型、不部署/采集/GL04。下一次提交由Codex核对新SHA、入口表和有效反例，不靠检查总数。

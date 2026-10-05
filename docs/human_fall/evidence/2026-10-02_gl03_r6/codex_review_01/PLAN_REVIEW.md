# GL03 R6 后结构资格审查

R6分类正确，现有kind/schema反例闭合。仍G03 FAIL的原因是完整validator的父frame字段类型校验不足、legacy容器/子记录解析在资格判断前。Codex遗漏了检查validator内部和回退来源，而非模型未执行R6分类方案；模型能力不足未证实。

## 已读消费者

- _validate_geometry_calibration：frames必须dict，但frames.lidar只按真值检查；reference字段未做类型检查。
- calibration_reference_transform：对transforms直接.get；非dict canonical子记录返回None，不区分损坏与缺失/unknown。
- resolver：legacy未整份验证，直接消费frames/transforms；只有字符串标签才比对，错误类型跳过。
- node startup/reload已使用完整validator与resolver；不新增热更新通道。decoder wrapper透传build_snapshot，ROS文件载入先完整validator。

## 已审结构规则与类型矩阵

| 对象 | 合法/兼容 | 损坏类型的处置 |
|---|---|---|
| full artifact frames | dict；lidar必需非空str，reference可None或非空str | 数字/bool/容器/空非法名称明确校验失败，不跳过一致性比较 |
| 真旧摘要 frames/transforms | 缺省/原支持None保持无声明语义；出现对象时dict，空dict保持无声明 | 非空字符串、数字、list等不是对象，resolver明确unavailable/标准资格异常，不能裸AttributeError |
| summary帧标签 | 缺省/原支持None保持未声明；已声明名称非空str | 非字符串不是“没有声明”，不能省略from/to绑定 |
| T_reference_lidar子记录 | 缺省/原支持None、合法unknown保留既有fallback；known须dict且原严格status/evidence/R/t/name资格 | 字符串/list/数字等损坏子记录不能视为无canonical后采用standalone |
| 合格known canonical+explicit T | 相同正常；已过冲突规则不改 | 不用类型守卫绕过显式冲突 |
| classifier/full blocks/schema | R6规则完整保持 | 不新增单值补丁或把失败降级legacy |

“原支持None”只保留兼容输入中既有无声明语义；完整frames.lidar仍必填。unknown记录内部资格按现有契约，不补造身份矩阵。未知普通扩展字段不设黑名单，不提升物理标志。

最小实现：在现有完整validator补父名称类型，在resolver读取旧摘要前用轻量共享结构守卫；明确区分absent/unknown/invalid，再复用已有record数值与cross-frame绑定。无需新class/serializer/version。不要通过捕获所有Exception掩盖损坏并回退standalone；不要向guard传错域/绕过旧框架。

实现前对表中缺失/None/空对象/合法对象/字符串/数值/bool/list、字段名称以及declared child fallback统一列组合；input_matrix_checks.py和14d已事先提供。先保存完整诊断与检查映射再实施；旧9/4/10/8/4/3和R6矩阵不改断言。保持G04/G05的固定输入/原子reload，node_runtime原则不改。

软件范围仍仅G03。真机/身份BLOCKED不靠本修复解决；不自动派工/换模型/部署/采集/GL04。若后续仍失败，先对照结构表确定未落实的格子，不能同文重试或把新反例假装新需求。

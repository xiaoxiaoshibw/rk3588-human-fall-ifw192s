# ADR-005：唯一数据写入口、绑定计划的确认和可恢复隔离

日期：2026-10-24。状态：安全设计采用；与旧v1写行为的冲突未获批准，见ADR-003。

## 操作与权限

数据根、junction、旧源码、历史evidence都不作为开发输出。本轮只写新文档/新机器证据和项目状态日志。未来产品的会话/GT/job/导出/下载/板端变更一律经IMutationGate；Api/VM不得持有通用文件写入器或直接调用板端修改方法。

PlanAsync只读地产生不可变MutationPlan：planId、动作、sid、规范化源/目标路径、每文件bytes/sha256、预期旧版本、目标卷/根身份、配置代次、过期时间与manifestHash。板端操作用确定的请求体/幂等键与观测状态绑定，不编造不存在的文件SHA。对不支持/冲突动作只返回诊断，不能通过“确认”越过禁止策略。

用户确认界面展示完整计划和影响，由Host拥有的内部ConfirmationBroker把可信交互事件交给Gate的内部确认入口，**Gate签发**单次ConfirmationToken，Broker不自己创造token或共享签名密钥。该入口不属于公共IMutationGate，也不暴露HTTP/QML可任意调用的“签发token”方法；只能消费当前展示plan绑定的交互结果。无可信确认能力的headless宿主不能签发写token。其用户交互来源需在实现时验证；本设计不抵御同用户恶意代码注入或任意控制整个宿主进程。

Token绑定相同planId/manifestHash/动作/配置代次和当前用户会话，短时有效，签名材料只在Gate内部；UI传回的对象字段不能作为有效permit。HTTP POST、Origin、默认勾选或自动脚本不构成确认。Gate验证token后内部生成MutationPermit，底层实现再次核对动作/路径，拒绝手工构造的permit。

执行链闭环：用例只调用Plan/Apply；Gate构造时由Host装配内部IMutationExecutor，只把该端口保存在Gate。Apply持锁重验、记录Applying后签发单次permit，并直接await executor.ExecuteAsync(plan,permit,ct)。执行器按固定动作表调用IGtStore/IBoardClient等受限写方法；普通用例、Api、VM不持执行器/写端口，不从Apply获取permit。执行结果先回Gate，Gate核对Receipt和journal并消费permit/token，才返回给用例。执行器不能再调用Apply造成递归，也不接收任意回调/脚本；未知动作或worker隔离能力缺失直接拒绝，不运行修改。

新增GT/导出/job/下载目标也要有用户意图和计划授权；不存在旧对象时没有可移动进隔离区的旧版本。覆盖和隔离还要展示原文件逐项清单、明确确认并保存旧版本。此动作区分是设计解释，不能当作已解决“所有写入均移隔离区”的文字歧义或旧v1无token兼容问题。旧meta/points只读策略不因有token就自动放开；rename/legacy annotations仍在冲突表中，不实施。

## Apply与恢复

状态：Planned→Confirmed→Revalidated→Applying→Committed；过期/源变更/配置变更转Rejected，提交前取消转Cancelled；部分完成/崩溃转RecoveryRequired。所有阶段写追加审计journal，最终Receipt含manifestHash、各项结果和实际SHA；不返回bool或伪成功。

Apply持有规范化数据/store根的单写锁，重新核对源/目标最终路径、volume/file identity、bytes/sha、目标不存在/预期旧SHA及token。源根允许合法captures junction在启动时解析到明确data目标；会话内部链接、计划后根或链接目标变化拒绝。字符串前缀不是路径安全证明；文件句柄和最终目标核对用于减小TOCTOU，不能声称一次resolve消除竞态。写入前后留源绑定，文件不变性由实测证明。

新增产物：应用自有暂存→校验字节/SHA/格式→原子晋级到新目标；目标存在拒绝，不覆盖。原子替换只限明确允许的可写store文档，先保存旧版本及journal，expected_sha不符拒绝。恢复时不修改冻结GT版本或静默清理临时/孤儿文件。

隔离操作：先清单与明确确认，源项必须是允许的具体产物，永不以data根/junction/.git/ML/历史evidence整体为目标。默认隔离区为AppData/ConsoleV2/quarantine/<时间戳>/<planId>，保留原路径、sid、bytes、sha及恢复信息；仅**同卷原子移动**列为初始可支持能力。

数据D盘而默认AppData在C盘时，计划必须返回UnsupportedCrossVolume且不移动/复制后删源。不得用跨盘copy+unlink冒称可回滚原子移动；用户未来显式指定同卷隔离根并重新确认后才能执行。初始实现没有永久删除API，也不定时清空隔离区。Restore再次做计划/确认、SHA核对与目标不存在检查，冲突拒绝；不能覆盖用户后来恢复/新增的数据。

journal恢复仅分析并显示可恢复状态；未经该恢复动作确认不自动移动/覆盖/删文件。跨多个文件不能假称全事务原子：崩溃时逐项记录已移/未移/未知，按文件身份重建，人工可选恢复是产品操作而非开发前置。旧程序不认识新锁，故并行共用根时新程序默认只读，不能依靠mutex声称阻止旧写者。

## 后续必要验证

临时目录覆盖无token/伪token/重复token/过期/manifest变化、路径穿越/URL编码/链接切换、目标并发创建、SHA变化、同卷隔离恢复、跨卷拒绝、崩溃各阶段恢复、worker越界和审计写失败。真实data仅做前后path/bytes/sha只读比对。未实现前这些测试NOT_RUN，不能以本ADR存在证明安全功能已通过。

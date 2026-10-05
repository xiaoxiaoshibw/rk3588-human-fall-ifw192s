# GL-03 R4：reference严格资格与固定版本绑定

用户手动派发 OpenCode；模型 DeepSeek V4.1 Flash（记录实际 provider/model/session）。本文件是可审查返工工单，不授权 Codex 自动启动。工作目录 D:/Code/ldiar；唯一生产写入者，结束后停止写入。

先读根 AGENTS.md、docs/human_fall/WORKFLOW.md v2、GL03_ACCEPTANCE.md v1、evidence/2026-10-02_gl03_r3/codex_review_01/CODEX_REVIEW.md 和 review_checks.py，以及 R3 00_diag.md/22_source_manifest.json。读 ponytail 实际技能。先核对当前 HEAD、tracked/untracked源码SHA；工作树刻意脏，不能 reset/checkout/clean/commit/push。旧证据不覆盖。新证据用 evidence/2026-10-02_gl03_r4/。

2026-10-02连续返工审查更新：先读 [计划/责任审查](evidence/2026-10-02_gl03_r3/codex_plan_audit_01/PLAN_REVIEW.md)。R4先进行设计诊断阶段，不能直接逐项打补丁。Codex已审最小策略：同ID实际reference变化明确拒绝要求新ID且无副作用；startup输入冲突与合法新IDreload分开；合法standalone绑定固定并解绑caller。先在R4的00_diag.md按该报告操作表写清输入来源、严格工具、canonical T选择、比较/赋值顺序、失效消费者、反例映射，检查无矛盾后实施。发现实质契约矛盾先记录交Codex审查，不猜语义；不为例行诊断要求用户确认。保留已过数学实现，不新增架构或模型。

保留 R3 已通过的 G01/G02、原九方法/四方法及 O01 同mask统计/诚实结论。集中闭合同一 reference 根因，不扩大里程碑：

1. G03/F1：共享 resolver 验证完整合法transform资格（名称/方向/units/status/evidence/R/t等现有契约），完整父artifact损坏/newer/缺ID不允许供reference坐标；**旧最小calibration摘要与合法standalone仍保持支持**。复用既有严格工具，不凭 `_load_transform` 数值通过就视为合法。节点启动显式T与known canonical冲突必须明确拒绝/不可用，不能在调用resolver前丢掉冲突参数。新版本reload采用新artifact T的已过行为保留，不拿旧standalone冲突阻止合法切换。
2. G04/G05/F2：同calibration ID而实际reference内容改变，不能返回changed=false继续旧资格。优先最小办法：拒绝要求新ID且验证失败无副作用；同内容reload不清正常资格。检查 locked、occluded、无新帧/status/request、pending基线、baseline/snapshot/action历史与既有事件保护。已复现同ID x平移1→9导致遮挡source位置错8m。共享生命周期边界解决，不单独修预测数值。
3. G05/F3：standalone合法caller变换绑定时深拷贝/固定，不让caller原地修改绕过版本和资格；快照与prediction消费同份实际有效绑定。artifact深拷贝已有通过，不降低断言。

新反例不是新需求：same ID与caller解绑已在R3提示词中；损坏/父版本/from-frame来自既有G03。本次审查遗漏承认并保持固定ID，不更新业务语义换取PASS。

先集中诊断映射所有入口，再修共享根因。原review_checks.py/旧失败日志只读，不为了绿灯改断言；可在R4新增检查。先复跑原九方法、四方法、R3扩展检查，再GL03/当前fall全量/follow/GL02必要回归。O01不必重跑重写已过报告，源码不影响该证据时引用SHA明确适用。按验收ID和12行矩阵报告，真实命令/exit/source SHA。

外部 fall_replay.py 保留；LI-DATA转换器/测试当前在 sidequests/lidata_adapter/，不计为本单修改或主线验收，套件数量依据实时树，不硬凑312。冻结config/driver/webui/原始数据/旧证据不改。真实身份仍BLOCKED/设备NOT_RUN；默认不开分离/confirmed，不引入深度模型。

按 RETURN_TEMPLATE.md 仅在 D:/Code/ldiar/docs/human_fall/returns/GL-03.md 末尾追加“OpenCode GL03 R4”，只写SUBMITTED/BLOCKED，不自行总体PASS。不启动GL04、不联网板端、部署/采集/网络驱动变更、不修改认证/DB、不擅自切换模型。完成列出修改文件/证据/未闭合，停止写入交Codex全表独立复审。

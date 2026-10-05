# GL03 R3：reference完整上下文与O01口径 / 2026-10-02

本次由用户手动派发OpenCode，Codex收到回传后独立复审，不自动启动或重试。工作目录D:/Code/ldiar，模型DeepSeek V4.1 Flash，记录实际provider/model/session。可以新建GL03 R3会话；旧session ses_f050597efffecPzMkhE6Bqww4f在旧CLI中不可读，不要求硬续接，不改/迁移用户数据库或认证。你是唯一生产写入者。R2九方法/source高度门控、原正常回归已闭合，不重做。开工核对实际HEAD/工作树（已记录49eb7581，可能有外部变化），webui/dist等用户差异保留，不归因、不回滚。只本单，不GL04/联网板端/部署/采集/commit/push/reset。

读GL03_ACCEPTANCE v1、R2 CODEX_REVIEW.md、codex_reference_checks.py四失败，相关当前函数按需，不全量读历史。先集中诊断到evidence/2026-10-02_gl03_r3/00_diag.md，再最小修共享根因：

1. G03/G04/G05 reference resolver：合法T.from必须匹配实际producing frame，T.to必须匹配已知calibration.frames.reference；known canonical T_reference_lidar与使用的变换不能冲突。无ground也同样守reference绑定，process/request/status不能漏；未知/不合法ref不得有有效reference坐标。保持普通无ground无reference的source-only degraded原义，transform=None source-only选择不因本单无故打开。prediction使用实际track域/有效变换，不猜raw self.transform。完整新calibration版本重载时，已启用且artifact-owned的reference必须用当前新T，不能发新ID旧矩阵；caller解绑。合法standalone explicit变换在没有矛盾已知父记录时保持原支持；同版本实际reference内容改变不得混旧资格，可明确拒绝要求新ID。复用现有严格transform/calibration入口，不造通用热更新框架或新schema。允许必要calibration跨记录校验，但先查调用者/保留未知外参原义。
2. O01统计：保留R1/R2旧输出。R3新的诊断从本轮完整pool支持mask重算count/fraction/RMS等；旧GL00逐面剥离统计如引用须改名historical_peeled_*、分清成员集合。每一full/ablated对同输入/采样/投影/cell参数，成员量/AABB可引用仍有效R2实测但新报告数字必须一致。准确标注pool每帧finite/nonzero、每20有效点抽1、47帧拼接、CSV四位小数；它不是完整生产候选过滤链或逐帧原始数据。
3. O01/G06/G07物理语义：全部六plane角色未知。horizontal_candidate仅SOURCE-Z近法向提示，**不是world-Z，不是地面身份**；不能说只有plane3可能地面、其他非地面，也不能排除地面桥接。n/d同样本消融显示部分hypothesis会改变pool连接，但不能确认现场单帧根因。无可信真值→不实现/启用强行分离，不删近地厚层，不改trust/物理flags。

允许必要lidar_candidates/node_runtime/calibration及有效回归、R3诊断、新证据/canonical回传；冻结配置、driver、webui（含外部dist差异）、原始数据、旧独立脚本不改。正式回传唯一绝对路径D:/Code/ldiar/docs/human_fall/returns/GL-03.md，只末尾追加OpenCode GL03 R3。

先9方法原checker+新4方法reference→受影响GL03/fall→GL02生命周期12+pending2。日志写仓库证据，摘要/失败片段，不用TEMP，不递归读大文件。fixture必须先证明monitor/选择/源时间有效，源stamp重复本应epoch++，不要调生产timebase过错误夹具。完整scope/new-source/dataSHA，SUBMITTED/BLOCKED，不自判总体PASS；完成后停止写入。

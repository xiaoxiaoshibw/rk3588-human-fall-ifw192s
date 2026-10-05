# OpenCode GL04 R4：把presence改为当前对应详情，保留source选择

唯一writer你，指定opencode-go/deepseek-v4.1-flash/default DB；Codex独立复审。R3已exit0停止，153k旧会话保留；用户允许同model default DB新紧凑会话。只四preview；42旧断言文字不动；不改core/config/driver/正式/其它webui/旧数据/旧证据。无GL05/设备/部署/采集/网络板端/commit/reset。GL04_ACCEPTANCE v1不变，V10 BLOCKED、D01 NOT_RUN。

先读r4/PLAN_REVIEW、r3/02_operation_matrix及r3/90_codex_runtime失败尾、必要实际函数一次；不要读完整历史/export/manifest/所有HTML。目标修复主要human_fall_lib.js、human_fall.js及追加tests；无需改已正确HTML布局。00_diag先完整C01–C15映射并补下方组合后才实施。上下文100k前准备收尾；不反复全文件read，命令stdout落新r4只tail失败/exit。单根因修复，不推倒R3已过部分。

## 已有要求下4FAIL（不是新功能）

- V07 source/ground两个mode：snapshot只剩other（bbox/center在12m），state还留本目标3m的旧source/ground字段、ready基线。`hfTargetGeometryPresent`只查state字段非空→错误upright/3m。必须证明当前snapshot对应本目标详情，而非presence。比较已有目标标识（有才用）或当前已发布source bbox/center以及可得ground对应字段作**一致性检查**；唯一匹配才消费，0/多匹配unknown/position空，不能first/nearest、不能浏览器跟踪/算几何。旧state完整字段仍在也不能当证明。source/ground/mode切换/预测/ready/其他候选组合全查。
- V09：真实build_snapshot无calibration时calibration_id/schema/ground_derived_id均null，ground_status unknown，source候选仍合法；unselected状态下应能首次source选择（原协议/原ID），fall物理仍unknown/ground入口灰。当前选择调用物理observationQualified一律拒绝。拆分“当前选择context”和“已有目标物理观测”：fresh source operator select不要求先有target或地面，新R/t缺失不能使原始模式不可选；calibration.schema明确2等错误则拒。null/null legacy绑定可匹配，null/已知值不是匹配。
- V06：snapshot GDID=null、state GDID=g1，cal/schema/seq/frame都相同且state旧位置还在，不可upright。完整nullable绑定比较（calibration id/schema、GDID、已声明coordinate/source等），不能只在both nonnull时比较；合法both-null source-only保留。STATE新/CAND旧及反序、missing→known、known→missing、unsupported同值、caller mutation均沿C04–C06查。

保留R3 GPU一次失效重绘、expired入口禁用/支持清除、state.performance真实字段、units m/3D支持有限、immutable token、source/ground当前camera重投、历史/ack/基线按钮语义；same-content正常恢复/第一次选择都要正例，不能以“一律拒绝”过负例。

## 证据与提交

根因最小位置＋所有消费者/到达顺序先映射。先复现4FAIL，再完整C01–C15及相关旧29反例、42 lib；新正例包括unselected首选、legacy无ground首选、当前锁定源/ground详情、正确paired cal/GDID新版本恢复。纯比较字段一致性不新增几何算法/模型。辅助检查/JSON/fixtures只写r4，保留r3旧日志；静态fixture新r4路径可复制/适配，不覆写旧JSON，仍offline Node生成、browser只fetch。

末尾按RETURN_TEMPLATE追加returns/GL-04.md“OpenCode GL-04 R4”，只SUBMITTED/BLOCKED，逐固定ID与矩阵/命令exit/SHA/未跑。浏览器你不能跑则NOT_RUN，交Codex真实browser。不要跑326/7/12+2；正式外部Q/E/帮助不写不回滚。提交后停写，给session/model/回传/证据/未闭合。可用r3独立harness作你自验但输出新r4文件，不能覆写Codex旧结果或自称独立通过。

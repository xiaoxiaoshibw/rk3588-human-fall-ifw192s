# GL-P01 R1：生产地面变换消息（唯一工单）

工作区 D:/Code/ldiar。按用户2026-10-03“开始开发”推进上一聊天计划B本地软件准备。唯一OpenCode production writer，指定opencode-go/deepseek-v4.1-flash/default DB；Codex独审。请用紧凑新session，不读全量历史。

先读根AGENTS.md/CLAUDE.md、docs/human_fall/WORKFLOW.md（当前覆盖）、GLP01_ACCEPTANCE.md v1、RETURN_TEMPLATE.md；实际读取 C:/Users/30680/.codex/skills/ponytail/SKILL.md，full，并在回传注明实际路径。

证据目录 docs/human_fall/evidence/2026-10-03_gl_p01_r1/；baseline 00_before_manifest.json。先00_diag.md：按唯一表M01-M12逐行列实际函数/赋值顺序/校验/消费者状态/保留失效及检查入口，集中诊断后才写源码。

已审事实：core/lidar_candidates.py _validated_ground_derived 已严格validate_geometry_calibration/deepcopy，返回canonical derived+parent并检查actual frame/显式ground。build_snapshot已拿该block，但只发GDID。最小在该producer把canonical R/t及绑定字段白名单投影为coordinate.ground（kind coordinate_ground/schema1），不重算、不alias；null无可用变换。现preview parseGroundRender已消费此格式。core/node_runtime.py生产调用、state.coordinate、project_snapshot_for_ros及human_fall_node strict JSON发布保留additive字段，不先改node。

保留full artifact only ground=None旧摘要null/ground_status unknown，JS unqualified；实际NodeCore fullartifact路径matching ground可ready。本单不自动推导plane上下文。support_polygon/polyline明确null+wire support_reason，任何auto AABB或trusted ROI bounds都不变真实polygon。不改preview parser传播reason（当前generic unavailable足够）。

生产允许只改 src/human_fall_detection/core/lidar_candidates.py；新增集中 src/human_fall_detection/tests/test_glp01_ground_projection.py 和必要一个 tests/glp01_consumer.js（实际调用当前preview parser）；为本轮写00_diag/检查产物/源码SHA，末尾追加returns/GL-P01.md，状态只SUBMITTED/BLOCKED。可新增docs/human_fall/GLP01_MESSAGE_CONTRACT.md作additive格式说明。node_runtime或其它生产文件若确实必要，先停止该文件修改、记录具体调用链缺口交Codex，不扩大白名单。

验证重点：实际FallNodeCore完整artifact→project_snapshot_for_ros→dumps_strict→当前JS parser，tilted/非零t/空candidate，坏整parent/frame/version/units/R/t/flags，caller及输出隔离；新字段及原ID/ground AABB一致。生命周期复用已有GL02/03/HF07检查，缺失则集中补本单有效检查，原断言不改语义。仅跑受影响检查并把日志落证据，反馈退出码/失败摘要，勿把数百测试输出灌会话。不引依赖、不格式化无关代码。

冻结：formal/preview/所有其它webui、core数学和runtime、config、driver、original captures、historical evidence/returns。不得改WORKFLOW/DISPATCH/REVIEW_LOG/验收表（Codex收口）。不commit/push/reset/checkout/clean、不板端网络/采集/部署/GL05/模型/DB/auth/global config变更。原用户Q/E/help/HR/根重组全部保留。提交逐P/M条目、命令/exit、实际model/session/skill/SHA与未跑层，停止写入，等Codex独审。

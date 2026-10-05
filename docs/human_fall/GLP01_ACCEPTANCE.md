# GL-P01 生产地面变换消息验收基线 v1

建立：2026-10-03。用户在引用上一聊天的下一阶段计划审查后明确“开始开发”，据此启动计划 B 的本地软件准备。GL04真实DPR仍NOT_RUN，正式源码合并门未闭合；本单可独立完成，不放行GL05设备、网络、采集、配置启用或部署。

唯一生产写入者：OpenCode CLI `opencode-go/deepseek-v4.1-flash` / default DB；Codex编排及独立复审。按[WORKFLOW v2](WORKFLOW.md)，仅此表是本单判据。

来源：[下一阶段计划 B](evidence/2026-10-03_next_stage_plan_r1/PLAN_REVIEW.md)、GL04 V10既有集成缺口、GL02/GL03已审artifact及版本绑定契约、现行preview消费格式。只新增生产消息能力，不改变GL04 v1或物理资格。

| ID | 必需预期与负例 | 检查入口/层级 | 结果 |
|---|---|---|---|
| P01 | build_snapshot把已严格validated的ground_derived原值白名单投影为唯一coordinate.ground：kind=coordinate_ground/schema_version=1/from_frame/to_frame/units=m/calibration_id/geometry_schema_version/GDID/显式R/t；不重拟合、不发ground_render alias、不按normal补identity | pure producer + JSON/源码 | PASS |
| P02 | 整artifact、source frame、显式ground parent、版本、units、R/t、GDID、物理flags损坏不能发布可用变换；legacy/none/ground-only无derived无身份回退；caller和输出修改不污染下一输出 | GL02共同校验入口+producer正负例 | PASS |
| P03 | 实际FallNodeCore→project_snapshot_for_ros→dumps_strict→现行preview parseGroundRender可读同frame/cal/GDID/R/t；全倾角/非零t可ready，实际ground AABB仍来自原点集；空候选也能提供变换，projection只去evidence_indices | 运行生产调用链到Node JS consumer；本地软件，不是运行ROS设备 | PASS |
| P04 | startup、同内容reload、同ID异内容拒绝、新ID reload、caller原地修改、坏reload、外来frame、stream失效/恢复；unlocked/locked及baseline pending/ready的版本/选择/历史/状态资格原义保留，state.coordinate按现有链透传 | 集中生命周期矩阵+相关既有GL02/03/HF07回归 | PASS |
| P05 | 成功变换下ground.support_polygon/polyline均null，附非空support_reason说明无可信支持轮廓；自动AABB、trusted ROI bounds/evidence均不得冒充actual polygon；preview支持层仍unavailable | producer wire检查+JS parser；具体wire reason无需改页面标签 | PASS |
| P06 | 顶层candidate_snapshot schema1及旧source/reference/IDs/候选数值/evidence_indices原义不变，不提升physical/confirmed/IMU资格；生产改动只在最小白名单，Python3.8语法及stdlib+NumPy依赖保持 | 原反例、范围SHA、相关回归与契约审查 | PASS |
| D01 | 板端/真实人体/实际ROS消息运行/性能/部署均未执行 | device/physical明确分层 | NOT_RUN |

补充既有资格：pure build_snapshot(calibration=full, ground=None)可带validated derived字段，但ground摘要仍null、cal.ground_status仍unknown，JS为unqualified；不借本单自动推导旧ground上下文。真实NodeCore完整artifact绑定路径提供matching ground，应ready。ground absent不清空旧source/reference可用数据；坏parent/frame不能发布可用ground变换。support_reason的具体枚举在集中诊断记录，不以bounds构造支持区。

M07作用域明确：新增producer R/t与caller artifact隔离，下帧不受输出修改污染；ROS projection执行本身不修改缓存，保留现有nested浅拷贝语义，不新增“调用者随后原地修改projection的nested对象也必须隔离cache”要求。P05只附到原有ground摘要对象，ground=None仍null。monitor unavailable/requires_recalibration、prediction/lost在00_diag作为P04/P06既有行为映射复用或说明裁剪，不新增物理门槛。v1语义不变。

## 操作与消费者矩阵

每行实现前在00_diag映射函数、赋值顺序、检查和保留/失效行为；提交及独审引用本行，不只填P类结果。

| 行 | 操作/输入 | 消费者状态 | ID | 预期 | 结果 |
|---|---|---|---|---|---|
| M01 | startup/full valid artifact+matching ground | empty/unlocked/无candidate | P01/03 | 变换ready；无candidate不造框；wire→JS值一致 | PASS |
| M02 | startup/tilted+nonzero translation | unlocked/候选/选择入口 | P01/03/06 | 原值R/t与actual-points AABB；原snapshot/candidate ID | PASS |
| M03 | legacy/none/ground-only无derived | unlocked/locked | P02/06 | 无ground变换，不补identity；source旧行为保留 | PASS |
| M04 | full artifact only、ground=None | producer独立调用 | P02/03/06 | 旧unknown/null保持；JS unqualified，非假ready | PASS |
| M05 | 同内容reload | locked、baseline pending/ready | P04 | 既有连续性及版本原义，不引新清空 | PASS |
| M06 | 同ID异内容/新IDreload | locked、pending/ready | P02/04 | 同ID不同内容拒绝无副作用；合法新ID按原义清旧资格 | PASS |
| M07 | caller原地修改/输出R或t修改/ROS projection | startup/reload/后续帧 | P02/03/04 | canonical隔离；后续输出、artifact及候选cache不受污染 | PASS |
| M08 | foreign source frame/显式不同parent ground | unlocked/locked/有旧快照 | P02/04 | 不发可用变换；旧frame不可借新字段选择 | PASS |
| M09 | malformed/unsupported schema、units、ID、R/t、flags | producer及坏reload/pending/ready | P02/04 | 共同校验拒绝；没有部分应用/identity fallback | PASS |
| M10 | stream silent/invalid→current recovery | locked、pending/ready及历史 | P04/06 | 现有unknown/位置/基线/ACK原义；只恢复当前context | PASS |
| M11 | auto AABB/trusted ROI bounds但无actual轮廓 | producer/JS两mode | P05 | null支持+reason，support unavailable，physical flags不升 | PASS |
| M12 | strict JSON/ROS projection/旧reference路径 | candidate存在/空候选 | P03/06 | 无NaN，保留字段；只去候选evidence_indices | PASS |

完整V10仍BLOCKED：本单只闭合生产R/t能力，缺真实support与正式页面合并/实际ROS运行证据不能声称生产端到端及物理通过。

## R1独立结果 / 2026-10-03

v1不变，P01/P02/P03合法tuple容器FAIL，P04/P05/P06 PASS，D01 NOT_RUN；M02/M09 FAIL，其余PASS。唯一R2工单AI_PROMPT_GLP01_OPENCODE_R2.md，集中缺陷和独立证据见evidence/2026-10-03_gl_p01_r1/CODEX_REVIEW.md。未软件收口。


## R2独立结果 / 2026-10-03

P01-P06及M01-M12软件PASS，D01 NOT_RUN。20条独立检查、11新增回归和独立Node四容器格均通过；原R1 tuple FAIL闭合。源码447e4003...5373。完整结论evidence/2026-10-03_gl_p01_r2/CODEX_REVIEW.md。R2写前诊断顺序违规按事实分列FAIL，不追改历史；完整事后审计与独验完成，下单严格拆诊断/实施并由Codex实际核后放行。GL04真实DPR/完整V10及设备层未因此通过。


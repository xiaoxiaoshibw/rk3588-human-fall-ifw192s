# GL-04 验收基线 v1

建立：2026-10-02。来源：用户本轮GL-04启动指令、[工单](tickets/GL-04_webui_level_view.md)、[WORKFLOW v2](WORKFLOW.md)、[几何](GEOMETRY_CONTRACT.md)与[交互](INTERACTION_CONTRACT.md)契约。唯一活动工单GL-04；唯一编排/独立复审Codex，唯一生产写入OpenCode `opencode-go/deepseek-v4.1-flash`。判据不以测试数量代替。

本轮基线HEAD `8633eacf79619e96d3150d54f3fd8739be53910d`，master；用户所述2f5385a已由外部HR-02提交推进，保留。全树tracked/untracked SHA及原差异见[evidence](evidence/2026-10-02_gl04_r1/00_before_manifest.json)。GL02/03已获审软件证据继续有效；G06关闭，真实身份/根因BLOCKED，设备NOT_RUN。

## 固定条目与现行独立结果

| ID | 来源 / 可观察预期与负例 | 检查 / 层级 | 结果 |
|---|---|---|---|
| V01 | T1：原始与配平两模式；同session/时刻/样本一套坐标；只消费版本化显式R/t，ground_local俯瞰+Z向下；不浏览器拟合、不假身份矩阵 | 原始/正常/全倾斜/无外参；points/axes/boxes/labels逐项；synthetic/browser及实际snapshot源码 | PASS |
| V02 | T2：GridHelper永远显示；支持polygon/polyline独立层，颜色/透明度/图例明确；无限网格≠地面已验证；每层≤3000点，超限抽样、sampled_from/total及源索引 | 空/有效/超预算支持层，source/ground_local绑定；lib+browser | PASS |
| V03 | T3：frame/单位/calibration_id/schema/geometry版本/ground_status与实际snapshot一致；缺失/未知配平input禁用或明确回退原始；配平候选明确“配平预览（未地面核验）” | ground valid/unknown/none及degraded，字段缺失/损坏/错frame，读数矩阵 | PASS |
| V04 | T4：消费source和实际ground AABB，不转两个对角造ground框；当前摄像机视锥8角投影min/max；near/far/behind退化保守处理 | zoom/rotate/resize/DPR变化，CSS像素/画布DPR同步；独立lib+真实browser | NOT_RUN |
| V05 | T4/7：模式/坐标不改变原snapshot/candidate ID；同名candidate同frame不同coordinate不混；列表/拖选提交前再核当前快照/版本，旧快照select拒绝 | 两入口×源/ground模式×同/旧/外来frame×绑定版本；请求wire不变 | PASS |
| V06 | T5：calibration.schema换代、frame/版本不匹、断连/ws过期、ground unknown/none、verifier unavailable、旧snapshot→框unknown、旧select拒绝，历史事件保留 | lifecycle完整操作表+browser失效/恢复；锁/ack不退化 | PASS |
| V07 | T5：候选详情缺失、valid baseline仍在→fall_status unknown、position null，不冒充当前物理观测；基线按钮/历史不清 | locked/预测/缺候选/恢复，同源及异源状态组合 | PASS |
| V08 | T6：三场景同样本同帧原坐标/ground_local各截图，synthetic/offline、frame/版本明示；无外参ground入口灰掉/回退截图；FPS近似、queue_dropped、连接状态同一时间显示 | normal/tilted/no_extrinsics真实浏览器六图及指标；无门槛臆造 | PASS |
| V09 | T7/边界：driver fallback/topics/ack/基线/原点云/IMU/设备/history/告警颜色、R0–R7语义保留；旧断言不降低；仅许可preview文件及获审后可选正式同名同步 | 原18项+新增checks；diff/SHA；正式页未变则复用R7回归，不重跑326/7/12+2 | PASS |
| V10 | 集成交付：实际build_snapshot可提供变换/支持区字段，软件能力与实际生产消息可用性分列；缺字段不得synthetic冒充端到端PASS | 只读build_snapshot/node消费检查；缺口明确BLOCKED，不改core | BLOCKED |
| D01 | 真实板端运行/人体物理/性能（本轮未授权设备操作） | device/physical，明确未跑 | NOT_RUN |

## 必须逐行记录的矩阵

每行结果仅PASS/FAIL/NOT_RUN/BLOCKED；运行证据记录于本轮新目录，旧证据不覆写。派工前完整组合表见[02_operation_matrix](evidence/2026-10-02_gl04_r1/02_operation_matrix.md)，实现前00_diag必须逐行映射函数/赋值顺序/检查。

| 行 | 组合 | ID | 预期 | 结果 |
|---|---|---|---|---|
| M01 | 原始→配平，valid→unknown→none→valid，两模式 | V01/03/06 | unknown/none禁用/回退、颜色unknown、旧选拒绝，恢复只用当前数据 | PASS |
| M02 | ground实际框 / unavailable / 无字段 / 错derived版本 | V01/03/04 | 只用同绑定ground AABB；缺失不造框 | PASS |
| M03 | rotate→zoom→resize→仅DPR变化，两坐标 | V04/05 | 当前视锥实时重投、overlay尺寸同步、请求原ID | NOT_RUN |
| M04 | 同名ID同frame不同coordinate / 外来spatial frame / 旧列表click / 拖选 | V05/06 | 当前绑定再验证，绝不client-side ID或跨frame选择 | PASS |
| M05 | ws disconnect / silent expiry / reconnect，locked及baseline pending/ready | V06/07/09 | 当前颜色unknown、位置空、旧select拒绝；历史/ack原义保留 | PASS |
| M06 | 同内容reload / 同ID异内容 / 新ID / schema unsupported / caller原地修改 | V03/05/06 | 同内容保留；变换/版本变化清旧显示/选择；坏schema拒绝 | PASS |
| M07 | 当前candidate详情丢失 + valid baseline +旧state位置 / 恢复 | V06/07 | 顶层unknown、位置null；不撤销历史，不冒用缓存 | PASS |
| M08 | normal / tilted / no_extrinsics，source/ground请求入口，截图同帧 | V01/03/08/10 | synthetic/offline显式，缺外参回退；FPS/queue/connection诚实 | PASS |
| M09 | startup无消息 / ground缺R/t / ground缺support / malformed / unsupported | V01/02/03/10 | 原始点云可用、ground入口禁用，支持缺失不造支持区 | PASS |
| M10 | 有效支持0/3/3000/3001/9000点×两坐标 | V02 | 每层预算、抽样元数据/索引、网格常显且非有效地面声明 | PASS |
| M11 | near/far/behind全部或部分裁剪 / camera退化 | V04/05 | 无伪框命中，不红屏 | PASS |

## 现有消息缺口（派工前只读确认）

`core/lidar_candidates.py:612–662`输出coordinate的ground_derived_id及候选实际ground AABB，但ground摘要只有status/frame/normal/offset_m/sensor_height_m，无显式R/t或support_polygon/support_polyline。不能由normal/offset在浏览器生成基底或支持区。带显式渲染字段的synthetic夹具只能证明消费能力，现有生产快照端到端配平须单列BLOCKED；不在本单修改core或topic结构。

## R1独立结果 / 2026-10-02

V01–V09 FAIL，V10 BLOCKED，D01 NOT_RUN；判据v1不变。M01 FAIL、M02 PASS、M03–M10 FAIL、M11 NOT_RUN（pure clipping局部通过）。逐行证据和限制见[evidence/2026-10-02_gl04_r1/CODEX_REVIEW.md](evidence/2026-10-02_gl04_r1/CODEX_REVIEW.md)。


## R2独立结果 / 2026-10-02

固定表和矩阵结果列已更新；判据v1不变。V01/V05/V09 PASS，其余失败/未跑/阻塞分层见[R2复审](evidence/2026-10-02_gl04_r2/CODEX_REVIEW.md)。R3仅范围内集中返工，不同步正式、不启动GL05。


## R4独立结果 / 2026-10-03

固定判据v1不变，最新结果列已更新。R5同一工单范围内返工入口见[设计审查](evidence/2026-10-03_gl04_r5/PLAN_REVIEW.md)与[提示词](AI_PROMPT_GL04_OPENCODE_R5.md)。V10/D01分层，正式不发布。



## R5独立结果与R6服务阻塞 / 2026-10-03

固定判据v1不变，仅更新现行结果列。R5 **REWORK**：原R4的5+2FAIL已闭合，四源码SHA匹配交接/回传，因此原Codex90/92/91独立证据仍适用；95/97及真实browser补查揭示source physical fall/失效track、坐标token/单位及fixture缺绑定。全V/C/M结果和六图见[R5正式复审](evidence/2026-10-03_gl04_r5/CODEX_REVIEW.md)。V04真实DPR变化/确定camera退化NOT_RUN，M05 pending真实browser未跑；V10/D01分层保留。

后续唯一[R6集中提示词](AI_PROMPT_GL04_OPENCODE_R6.md)/[设计矩阵](evidence/2026-10-03_gl04_r6/PLAN_REVIEW.md)已准备，指定model/default DB无工具probe55.313秒超时、exit1，[服务BLOCKED](evidence/2026-10-03_gl04_r6/CODEX_BLOCKED.md)。R6尚未启动生产写入者，不计算法失败轮次。当前正式源码未获审不并入，GL05/部署/采集/板端网络未授权；外部Q/E/帮助/HR/重组及旧证据保持。

## R6独立结果 / 2026-10-03

v1不变，仅结果列更新。V07/V09 source来源消费者REWORK，R5原阻断全闭合；真实六图/生命周期、逐V/C/M与限制见[R6复审](evidence/2026-10-03_gl04_r6/CODEX_REVIEW.md)。R7同工作项范围内继续，先[设计矩阵](evidence/2026-10-03_gl04_r7/PLAN_REVIEW.md)/[工单](AI_PROMPT_GL04_OPENCODE_R7.md)/≤1分钟probe；源provenance门与bbox观察门分开，灰预测诊断原义保留。正式未获审不并入，V04未完成浏览器项、V10/D01分层；无GL05/部署/采集。

## R7独立结果 / 2026-10-03

v1判据不变，仅结果列更新。代码无FAIL，V04/C12/M03实际DPR-only NOT_RUN，所以GL04尚未软件收口；V10/D01分层。真实clip/退化M11已补PASS，来源反例全部闭合。详[R7复审](evidence/2026-10-03_gl04_r7/CODEX_REVIEW.md)。无writer、不派R8、不并入正式/不GL05/部署/采集/板端网络；原54/用户改动/旧证据不动。

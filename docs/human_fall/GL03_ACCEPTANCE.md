# GL-03 验收基线 v1 / 2026-10-02

范围来自[GL03工单](tickets/GL-03_candidates_geometry.md)、[PLAN](GROUND_LEVELING_PLAN.md)、[几何契约](GEOMETRY_CONTRACT.md)、[交互契约](INTERACTION_CONTRACT.md)、[GL00获审扩展](evidence/2026-10-01_gl00_r4/25_contract_extension_draft.json)。按[WORKFLOW](WORKFLOW.md)和[CLI_RECOVERY](CLI_RECOVERY.md)，单写入者、逐入口/状态证据，不按测试总数验收。

前置GL01/GL02软件PASS。用户本轮授权Codex接回唯一编排/独立复审/状态收口角色，恢复指定OpenCode CLI范围内自动派工。R7独立复审已闭合G03，G01/G02/G03/G04/G05/G07/G08软件PASS；G06及真实身份BLOCKED，O01统计PASS，D01设备NOT_RUN。[R7复审](evidence/2026-10-02_gl03_r7/codex_review_01/CODEX_REVIEW.md)。整单未标ACCEPTED；GL04/部署/采集/网络及模型变更仍未授权。旧403为隔离DB项目绑定问题，default DB已于17:49恢复（见CLI_RECOVERY）。

## 固定条目

| ID | 来源 | 必需预期与反例 |
|---|---|---|
| G01 reference修复 | T1/2，G/I | 合法非零旋转+平移不因中心数组嵌套崩溃；reference AABB包含所有实际变换点，不能只变换两个对角；center_reference保持原source中心经reference变换语义，与新ground逐点中位数区分 |
| G02 ground精确几何 | T2/3，C-B | 本候选evidence_indices实际点经同R/t后的三轴min/max/median；bbox_ground_from=actual_points或unavailable；非对称分布证明“变换源中位数”不等于“变换后中位数”；source中心/AABB/索引不变 |
| G03 入口/绑定/异常 | T1/3，C-A/E，GL02 | build_snapshot、decoder wrapper、node、replay现有入口；合法有/无derived，unknown/损坏/newer版本、parent/ground/from-frame不一致不能假成功；采样/过滤后索引可还原当前输入数组；finite JSON，caller不被修改，不混版本 |
| G04 state及消费者坐标 | T1/3，C-C，I | 当前实测state与对应snapshot/candidate地面框/中心/版本相同；tracker reference优先原义保留，但预测source/reference/ground不能错标坐标；参考系平移/旋转用负例；features不把预测或旧几何当当前测量 |
| G05 生命周期 | T3，C-E，I/GL02 | unselected/locked/occluded/lost/ambiguous/release、无新帧stale、坏帧、monitor失效/恢复、同/新标定；无当前实际候选的ground实际点字段为空/unavailable，不能把缓存/prediction称actual_points；旧事件保留、源seq/stamp/epoch不改、旧快照/基线资格失效 |
| G06 大候选及最小改造 | T4/5 | 先以相同样本/配置建立成员与水平cell连接证据，对疑似平面支持参与连接做有标识的消融；只有可信支持且证据证明桥接时可启用最小分离，阈值显式/单位明确；不无条件删近地厚层，源点云保留，接地/低卧及完全贴地证据不悄然丢失；不能用框缩小冒充人体分割通过 |
| G07 诚实性/兼容 | T5/6，G/I | semantic仍unknown，真实地面/物理flags不升级，空场背景只来自显式无人空场，不在线学习；无可信ground/disabled新路径保持既有行为；不引入深度模型/通用分割框架 |
| G08 回归/范围/追溯 | T允许修改，AGENTS | 旧选择/跟踪/基线/HF/GL02不退化，冻结资产/driver/软链接/UI/原数据/历史证据保留；源码SHA与报告对应，Python3.8/NumPy1.17兼容不冒充板端实跑 |
| O01 可得真实数据离线诊断 | T4验收 | 本地数据有SHA/来源/过滤/采样/帧信息限制；有frame_seq的ROI仅ROI子集，tgz XYZ是跨47帧pool，不能当单帧或造原始索引；允许pool探索性成员对照，但明确不能据此确认当前单帧大框根因/机器人身份；真实结论不足标BLOCKED |
| D01 真机与完整现场结论 | T4验收，PLAN | 当前完整bag只在板端、本轮不联网采集；完整逐帧大候选/人体和机器人/地面身份、Python3.8.10/NumPy1.17.4设备运行无证据则NOT_RUN/BLOCKED，不影响已验证的独立数学软件范围 |

新字段按获审兼容扩展实现，冻结旧coordinate枚举和source/reference含义。纯API带derived时要严格校验来源/frame/parent绑定；旧无derived最小calibration摘要仍按原支持行为，不为了新路径破坏legacy。

## 必须逐行覆盖的矩阵

| 入口/状态 | ID | 检查预期 |
|---|---|---|
| build_snapshot无标定/legacy摘要/有效source-only | G01/02/03/07 | 旧行为；可选ground字段空/unavailable，无身份矩阵假成功 |
| build_snapshot full artifact+ground+reference transform | G01/02/03 | ground逐点变换，reference不崩溃/包围完整，binding一致 |
| build_snapshot derived损坏/版本不支持/frame或parent错配 | G03 | 明确拒绝或不可用且不报有效ground ID/实际点字段；不静默用错变换 |
| build_snapshot采样/非法点/范围/background过滤 | G02/03/07 | evidence_indices恢复该候选实际输入点，原始点未修改；所有新坐标来自同点集合 |
| candidates_from_cloud / node / replay | G03/04 | wrapper复用共享geometry；不只修纯helper漏真实入口；已有replay无标定不新增热更新框架 |
| node当前locked实测 | G04 | state地面几何等于相应candidate，同seq/snapshot/calibration/GDID |
| reference优先track后occluded预测 | G04/05 | source输出必须逆变换回source或明确Unavailable，不能把reference prediction塞source；ground实际点字段为空，bbox_observed/predicted原义不变 |
| unselected/release/lost/ambiguous/stale/invalid/monitor_bad | G05 | state不发旧ground位置/实际框；正常candidate诊断不变成有效人体/动作观测 |
| 同版本reload/新版本reload/恢复 | G04/05 | 同版本保持资格/绑定；新版本清旧几何；恢复只从当前实测重建 |
| 无可信支持/auto AABB/分离disabled | G06/07 | 新分离不开启或明确不可用，保持旧候选；不能自动升trusted |
| 可信synthetic桥接/standing/contact/lying/完全近地 | G06 | 有效连接消融和保留证据；无法区分的完全近地样本保守fallback/明确限制，不悄然删除 |
| 真实ROI子集/跨帧pool/无空场 | O01/G07 | 分别报告采样层级；不造完整帧或人/机器人标签、不冒用空场 |

## 初始事实和交付

当前_reference_block把3向量中心写成嵌套数组导致ragged；bbox只转两角。build_snapshot目前只输出GDID、不输出ground几何；node不透传新字段，预测position_m可能在reference却被当source。必须集中检查，不仅补字段。

本地可用：GL00 r1 `14_current_roi_points.csv`（frame_seq/point_index/XYZ，ROI受限、非全集）；`14_current_sample.csv.tgz`（header x,y,z，跨帧pool，缺帧/原索引）；`14_current_capture_metadata.json`、`14_current_planes.json`。原bag路径是设备/root/catkin_ws/...，本机无完整bag。metadata旧“向前上倾”不作为安装真值，GL00 R4最新现场规则优先。无现场地面identity，pool消融只能假设诊断。新分离如实现，仅显式选择且在可信证据下启用，默认保持旧行为。

回传末尾追加returns/GL-03.md，G01–G08/O01/D01逐条SUBMITTED/BLOCKED；原始检查、源码manifest、数据SHA和诊断位于本轮目录。软件几何PASS与真实分割BLOCKED可以分列，不能整体冒称人体识别完成。

## 历史独立结果 / R3 / 2026-10-02

判据仍为v1；本轮新增反例揭示既有资格/生命周期要求的遗漏，不改变条目语义。完整入口矩阵、命令、SHA和失败条件见[R3独立报告](evidence/2026-10-02_gl03_r3/codex_review_01/CODEX_REVIEW.md)。

| ID | 软件/离线结果 | 设备/物理边界 |
|---|---|---|
| G01 | PASS | 数学证据 |
| G02 | PASS | 数学证据 |
| G03 | FAIL | 损坏reference/父资格和节点启动冲突 |
| G04 | FAIL | 同ID换T后的预测source错8m |
| G05 | FAIL | 同ID内容变化/standalone caller引用未失效或解绑 |
| G06 | BLOCKED | 默认关闭保留行为PASS；无可信真实桥接，不启用分离 |
| G07 | PASS | unknown/物理flags未提升 |
| G08 | PASS | 当前回归/范围/SHA/静态语法；目标运行NOT_RUN |
| O01 | PASS | pool探索性统计/成员通过；真实身份/单帧根因BLOCKED |
| D01 | NOT_RUN | 真机兼容/完整现场BLOCKED |

当前整体软件REWORK；R4仅集中修reference资格及固定版本绑定。G06/O01现场限制单列，不冒称人体分割/真机效果已通过。GL04未放行。


## 历史独立结果 / R4 / 2026-10-02

判据仍v1。完整矩阵/命令/SHA及同根因责任见[R4复审](evidence/2026-10-02_gl03_r4/codex_review_01/CODEX_REVIEW.md)和[设计再审查](evidence/2026-10-02_gl03_r4/codex_review_01/PLAN_REVIEW.md)。

| ID | 软件/离线结果 | 边界 |
|---|---|---|
| G01 | PASS | 正常reference全点几何 |
| G02 | PASS | 实际ground点/索引几何 |
| G03 | FAIL | 错kind父绕过资格、父lidar/T.from错配 |
| G04 | FAIL | standalone same-IDreload后occluded source错8m |
| G05 | FAIL | reload再次读取caller、只比较canonical忽略有效绑定 |
| G06 | BLOCKED | 默认关闭保留行为通过；真实桥接未知 |
| G07 | PASS | 语义unknown/物理flags未升级 |
| G08 | PASS | 回归/范围/SHA/静态兼容子范围，目标运行NOT_RUN |
| O01 | PASS | 沿用独立统计；真实身份/单帧根因BLOCKED |
| D01 | NOT_RUN | 真机/完整现场BLOCKED |

原9/4/10/8方法及当前314主线回归通过，不代替必需软件ID。R5先按已审固定输入/有效绑定设计实施，用户手动派工、不自动启动GL04。


## 历史独立结果 / R5 / 2026-10-02

判据仍v1，G03的完整artifact与旧最小摘要边界按[实际调用者/分类审查](evidence/2026-10-02_gl03_r5/codex_review_01/PLAN_REVIEW.md)澄清：完整产物结构不能因kind破损降级为legacy；既有真摘要兼容保留。不是新算法/设备/性能门槛。完整12行矩阵/命令/SHA见[R5复审](evidence/2026-10-02_gl03_r5/codex_review_01/CODEX_REVIEW.md)。

| ID | 软件/离线结果 | 边界 |
|---|---|---|
| G01 | PASS | 全点reference几何 |
| G02 | PASS | 实际ground点/索引 |
| G03 | FAIL | 完整schema99父kind缺失/null绕过验证 |
| G04 | PASS | 8m错移闭合、预测/实测坐标 |
| G05 | PASS | 固定startup、prospective有效绑定、原子reload/资格 |
| G06 | BLOCKED | 默认不开分离，真实桥接身份不足 |
| G07 | PASS | 合法legacy/unknown/物理诚实性 |
| G08 | PASS | 回归/范围/SHA/静态兼容，目标运行NOT_RUN |
| O01 | PASS | 统计沿用；真实身份/单帧根因BLOCKED |
| D01 | NOT_RUN | 真机/完整现场BLOCKED |

原反例与319回归通过不能代替G03；后续仅收敛输入分类，不重做G04/G05。不自动派工/切模型/启动GL04。


## 历史独立结果 / R6 / 2026-10-02

判据v1不变，已列损坏/frame/parent资格须先校验结构类型；Codex承认此前假设完整validator已充分严格而未检查内部字段。完整12行矩阵/SHA/命令见[R6复审](evidence/2026-10-02_gl03_r6/codex_review_01/CODEX_REVIEW.md)，[集中结构规则](evidence/2026-10-02_gl03_r6/codex_review_01/PLAN_REVIEW.md)先审后修。

| ID | 软件/离线结果 | 边界 |
|---|---|---|
| G01 | PASS | reference全点几何 |
| G02 | PASS | ground实际点/源索引 |
| G03 | FAIL | 父frame非字符串仍投影、坏摘要container/子记录资格泄漏 |
| G04 | PASS | 已过测量/预测坐标 |
| G05 | PASS | 固定standalone/prospective原子reload保持 |
| G06 | BLOCKED | 无可信真实桥接，新分离未启用 |
| G07 | PASS | 合法兼容/unknown/物理诚实性 |
| G08 | PASS | 回归/范围/SHA/保护资产/静态，目标运行NOT_RUN |
| O01 | PASS | 独立探索统计沿用；真实身份/单帧根因BLOCKED |
| D01 | NOT_RUN | 真机/完整现场BLOCKED |

R6分类修复已通过，不将其说成原方案未落实。321回归与原反例通过不代替G03；下一步仅结构资格，手动R7、不自动启动GL04/设备操作。


## 当前独立结果 / R7 / 2026-10-02

判据v1不变。详细逐格映射、命令/exit、SHA及来源见[R7独立复审](evidence/2026-10-02_gl03_r7/codex_review_01/CODEX_REVIEW.md)。R6 14d 的7方法不足以代表全部类型格，本轮独立补125格全部PASS，原矩阵exit0；相关fall 326回归exit0（含GL03 54），不以测试总数验收。提交manifest全匹配，独立逆patch重建三处改动文件与R6 SHA一致，node_runtime 889ead5e保持；O01 R7/R3逐字节一致。首尾源码/旧证据未变；HEAD 8a5a2b2及CLI_RECOVERY外部变化保留单列，不归因不回滚。

| ID | 独立结果 | 层级/边界 |
|---|---|---|
| G01 | PASS | reference 全点几何/中心原义 |
| G02 | PASS | ground 实际点/源索引 |
| G03 | PASS | R6旧矩阵及125格结构资格独立检查通过，类型/损坏/回退闭合 |
| G04 | PASS | R5/R6已过结果沿用；node_runtime 889ead5e 未变 |
| G05 | PASS | 固定standalone/prospective原子reload保留，不重做旧专项 |
| G06 | BLOCKED | disabled保留行为PASS；可信分离synthetic路径未启用NOT_RUN，真实桥接/分离BLOCKED |
| G07 | PASS | 合法legacy/None/unknown兼容、semantic及物理flags诚实性 |
| G08 | PASS | 相关回归/范围/SHA/静态语法；目标设备运行NOT_RUN |
| O01 | PASS | 仅ROI/pool探索统计；真实单帧根因/人体机器人身份BLOCKED |
| D01 | NOT_RUN | 设备运行未做；完整帧/现场身份物理BLOCKED |

已验证软件范围PASS，无新FAIL、不派R8。G06/O01真实身份/D01现场分层保留，整单未ACCEPTED，GL04等待用户授权。

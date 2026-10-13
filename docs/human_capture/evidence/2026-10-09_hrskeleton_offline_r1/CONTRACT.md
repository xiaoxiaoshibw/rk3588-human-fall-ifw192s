# SKO 离线原型契约 v1（首次算法运行前冻结）

2026-10-09；用户当前A–F授权优先于旧文档的“仅计划”。只写本证据轮与追加return。参数为工具默认值，真实开发人体GT缺失时不宣称已标定，不在验证窗口调参。所有固定窗口先登记；不称全盲。

输入信任链：核R2交付manifest和工具固定SHA，核所有传递导入，再只读调用R2 authority/source/receipt；R1 pass3完整clusters/frames/votes、固定job、raw meta/bin/TLS/诊断矩阵全部核对。原数据实际是28B小端布局，不采用README示例的16B。XYZ取原28B的0/4/8字节；global row=offset_points+row。按原R2顺序逐变换f32舍入，包含REF_SHADOW诊断矩阵；不是正式注册消费许可。WORKSPACE/V2空场共享TLS但保留分支身份。无效点先在raw识别：任一XYZ非有限或三值全零；变换后的原点平移不能变成支撑。旧上游可能受无效点污染，本轮不修复其聚类。

逐帧manifest包括无簇/未审/小簇记录及分母；candidate完整成员逐簇审阅。小簇/未分配点保留上游计数和小组件清单，不私自重新聚类生成新人体。输入身份或SHA冲突阻断对应入口，输出定位错误。

真实入口先用bind_inputs.js validate核sidecar。source=human只能来自实际人工提交；工具不验证人的身份或标签真值。必须有reviewer、时间、完整receipt、person_id、人工continuous identity与track_epoch；机器track_id分列。B门：两个开发sid各至少3个连续ordinal、同person_id/epoch的PERSON，有可见躯干region_rows以及真实缺失/拒绝对照，才能运行真实C/D。合成夹具标synthetic，不计此门。未审/STATIC/MIXED/UNKNOWN不产有效人体节点。本版不会从混合簇裁人体子集。

标准化对全部有效原始成员只作XY算术均值中心平移；Z逐位保留已有配平/参考坐标。输出有效rows/global_rows/xyz、排除无效rows及正逆平移、输入receipt与坐标身份、数值误差。描述量使用NumPy eigh，无原分类/PCA家具评分；近退化轴UNKNOWN，特征向量符号和人体朝向始终UNKNOWN。XY中心变化不改变坐标绑定，tracker在已有参考坐标而非移动局部坐标上滤波。逆变换≤1e-5m为数学门，不是关节精度或物理外参。

五固定槽位HEAD/UPPER_TORSO/CHEST/PELVIS_REGION/LOWER_REGION；仅明确支撑分离时增加LOWER_A/B。所有节点语义须有当帧人工可见证据；未标/不确定/不可见即UNKNOWN。躯干/胸/骨盆/下部的候选支撑是参数定义的已有Z闭开带中全部有效成员，不裁XY圆柱；与人工参考region_rows分列，区域参考中心只用于验证。缺点、跨度冲突或支撑<6为无效；有效观测用支撑XYZ逐轴中位数，support_rows/n均可重算。support_score=min(1,n/12)，confidence_kind=POINT_COUNT_DIAGNOSTIC，不是正确概率。还记录跨度和密度描述。仅直立片段的工具候选带；低姿态资格NOT_RUN。

HEAD首版是显式人工可见头区域条件下的代表点能力：只消费标明HEAD_CONFIRMED的头region_rows；没有该归属时HEAD_OR_HAND_AMBIGUOUS/NO_VISIBLE_HEAD_SUPPORT，不取最高点，不靠身高补头。它不是自主头部识别。LOWER_A/B沿下部XY无符号主轴投影最大空隙拆两组，必须双组点数/分离过门并各有可见区域；不够只保留LOWER_REGION。A/B按投影排序，无人体左右语义。不宣传骨盆或下部为解剖关节。

每有效节点xyz（参考坐标）/xyz_local/valid/support_score/confidence_kind/support_rows/support_n/reason绑定同一帧receipt、source/raw/member/coordinate/params/code/run；无效xyz=null。raw与filtered分列，measurement_valid与filter_valid分别说明；jump拒绝仅影响filter，raw不删除。当前无支撑filtered_xyz=null，history_xyz单列且非当前证据。

SkeletonTracker独立，不导入原Tracker。键含sid/branch/coordinate_id/person_id/track_epoch；stamp整数秒+纳秒转ns，dt先整数相减再除1e9。不用bag_time或墙钟。重复/倒退、ordinal不连续（含seek）、换键、dt>0.5s全部reset；支持explicit seek。缺失当帧保留无效；下一有效节点从raw重初始化，不历史补有效。EMA alpha=1-exp(-dt/tau)，跳变>0.5m或速度>3m/s拒绝滤波并清该节点历史。所有生命周期留日志。

审阅页使用全成员三个正交投影和row拾取；颜色只区分机器簇/人工区域/节点。input/frame文件有固定SHA校验；载入失败清旧状态；导出带同receipt和input摘要，非法导出由UI及CLI拒绝。人工标region是可见结构证据，不是精确独立关节GT。实际UI与headless测试分开。

真实GT不足仍输出120分支行normalized/nodes_raw/nodes_filtered，逐簇BLOCKED_GT或NO_CLUSTER，xyz=null；绝不把空输出当成功正例。合成正负/映射/生命周期结果另目录，与真实分母隔离。独立审计不导入算法/R2校验器，直接struct读取raw及独立坐标复算；两遍确定性数据比较SHA，runtime另外记录。

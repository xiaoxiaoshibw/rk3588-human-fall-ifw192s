# 下一阶段：可信人体簇上的离线粗骨架可行性

版本 v1；2026-10-08（Asia/Shanghai）。状态 **DRAFT_READY_FOR_DISPATCH / 仅计划**。

用户本轮授权制定计划。下一工单：[HR-SKELETON-OFFLINE](tickets/HR-SKELETON-OFFLINE.md)；其唯一验收表：[HR_SKELETON_OFFLINE_ACCEPTANCE.md v1](HR_SKELETON_OFFLINE_ACCEPTANCE.md)。本轮没有启动算法实施、人工标注、采集、部署或生产接入。以后用户明确“按此工单开工、仅离线”后，才执行下列范围。

## 1. 阶段目标与当前边界

回答一个具体问题：**在身份已经人工确认、成员和坐标可核验的人体簇上，能否输出真实点云支撑的粗结构节点，并保持合理的短时稳定性？** 先验证人体局部点云和可观测结构，不承担自动从全场景找人的资格。

这是正式 W04/W05 前的受控离线可行性工单，借用其标准化和粗节点思路；不宣布 W03 冻结，不放行正式 W04/W05，不用人工选样替代正式自动人体识别验收，不重开已经关闭的 HR-07/HR-08，不激活 HR-09 或 ML。原 [W01–W09 计划](W01_W09_FINAL_ALGORITHM_PLAN.md) 的主线顺序保留。

当前证据：[SEM-SHADOW-R2](evidence/2026-10-08_hrsemshadow_r2/REVIEW_R2.md) 已修复成员/SHA/审阅/票据绑定，SEM-12 PASS；四个人体会话的全帧身份GT仍缺。中央静立13/244、举手1/195是当前语义结构帧上界；举手HEAD0/195。高代理269/271和281/281也不能证明人体身份或骨架正确。W03自身仍REWORK_REQUIRED；WD02规范争议保持BLOCKED。

本计划不要求先解决WD02才能验证已确认的新会话人体簇，但**不处理WD02、不删除其历史代码检查、不改变其阻断状态**。主线收口与未来生产资格继续由各自原验收表管理。

## 2. 第一批固定输入与数据划分

只读复用 `captures/remote/<sid>/meta.json + points.bin`、固定TLS和诊断矩阵。权威成员来自SEM R1 pass3/clusters.jsonl；来源/摘要核对使用R2可信工具及新工单基线。固定job在新会话证据的 `leveling/<job>/`，不是按mtime找最新job。WARN会话只消费原REF_SHADOW成员，不执行正式V2或新配准。

第一批每段预登记中间20个**实际储存帧 ordinal**；这是工作量上限与选样规则，不是精度门槛。先登记、再标注，不根据骨架输出挑成功帧。

| 会话 | 既有分支 | 固定job | ordinal（含端点） | 用途 |
|---|---|---|---|---|
| cap_20261008_114205 | REF_SHADOW / WARN | 80a4bd6fe3a4476fa099b053d74de8be | 112–131 | 开发：普通静立、整簇外缘污染 |
| cap_20261008_114254 | REF_SHADOW / WARN | abe747de448a4974ad9e7a6e1c70bac4 | 125–144 | 开发：桌前人体/家具归属 |
| cap_20261008_114340 | 离线V2 / PASS | 9d389dc38cb84343b66f97db2198dbbb | 130–149 | 参数冻结后验证：隔板边缘；包含f140原185点 |
| cap_20261008_114422 | 离线V2 / PASS | 24a7ba629d904f63af03ecdaadb9a9ec | 87–106 | 参数冻结后难例：举手，手/头混淆、HEAD缺失 |
| cap_20261008_114819 | WORKSPACE + V2_IDENTITY | 6e87c6e4146f48ba84e24c801820e5e1 | 132–151 | 无人场景拒绝/空输入对照；两分支分别记账 |

首批100个唯一原始帧；空场两个分支时是120个分支行，不能报120个独立样本。开发/验证按会话拆分，不能把相邻帧随机拆成独立留出。以上数据已被观察过，只称固定验证/难例，不称全盲测试集。

所有预登记帧都进入清单：PERSON、STATIC_OBJECT、MIXED、UNKNOWN、无簇、输入不足和未审都保留分母。没有获得人体成员身份的帧记BLOCKED_GT；不因为旧语义输出OBJECT/UNKNOWN就从人体候选审阅列表剔除。

## 3. 按出口推进的执行顺序

| 阶段 | 实际工作 | 交付与进入下一步的条件 |
|---|---|---|
| A：绑定与预登记 | 核R2交付工具SHA、raw/TLS/矩阵/成员清单；冻结上述窗口、用途与输入契约 | input_manifest.json + split_manifest.json；身份/SHA不一致立即阻断该输入，保留故障 |
| B：最小可信GT | 人工审阅入选完整簇，记录实际reviewer/person_id、可见性和连续身份；审核节点的可见区域 | identity_gt.json + node_review.json；至少两个开发会话各3个连续实际帧的PERSON身份获人工确认，并有真实躯干可见正例及拒绝/缺失对照，才进入真实人体C/D。其余未审仍BLOCKED |
| C：W04离线标准化原型 | 读取确认簇全部有效raw成员，建立可逆人体局部坐标、可见性与主轴描述；导出行映射 | normalized_frames.jsonl + normalize_checks.json；映射/逆变换/无效点测试过，才给节点算法消费 |
| D：单帧粗结构 | 先实现胸/躯干/骨盆区域支撑，再检查头与下肢；逐节点输出支撑、有效性与拒绝原因 | nodes_raw.jsonl + 单帧对照与参数v1；合法真实正例能输出有支撑的节点，不能一律拒绝制造通过；难例保留失败 |
| E：独立时序状态 | 以原时间戳处理平滑、跳变、缺失/重获；原human Tracker只读，SkeletonTracker另建 | nodes_filtered.jsonl + 生命周期日志；原始观测与滤波输出分列，缺点不变成当前有效节点 |
| F：固定验证与独立复审 | 只在开发会话确定参数；冻结后运行隔板/举手/空场窗口，核全部分母、支撑成员、效果与资产 | 逐ID表、指标、审阅页、SHA/log、REVIEW.md与return；停在离线可行性可复审，不进入W06/W07或生产 |

不用等100帧全部标完才编写纯标准化函数和合成数学测试；真实人体节点试验必须满足B的人工身份条件。不能由Codex把ROI、机器track_id或场景有人自动改写为source:human；没有真实人工标签时，继续完成A、契约和synthetic工具检查，真人输出与效果项保持BLOCKED。

不承诺固定完成日期。最先执行A+B；满足最小GT后提交C+D第一增量，再做E+F。真正耗时依赖人工身份/节点可见性确认，软件测试数量不能替代这一步。

## 4. W04最小标准化契约

- 输入绑定：sid、mode、ordinal、seq、原stamp_sec/stamp_nanosec、完整成员ID/rows摘要、raw28B内容摘要、XYZ摘要、source meta/bin/TLS/诊断矩阵摘要、实际human person_id和reviewer。沿用28B布局，global row=offset_points+row。
- 原型身份必须写 `identity_source=MANUAL_GT_FIXTURE`，与原机器track_id分开；人工身份只用于受控输入，不能宣称已经解决生产自动关联。每个状态键含sid/branch/坐标变换身份/person_id/track_epoch。
- 首版局部坐标只做XY平移至人体有效成员中心，Z保留既有配平坐标；保存正/逆变换和未改写的源row。先不靠PCA旋转强猜人体正面或左右。配平z约定不等于物理安装外参已经核验。
- 输出全部有效成员，不重做背景删除/cleanup/聚类，不裁一个干净圆柱给骨架凑结果。MIXED/UNKNOWN不能自动改PERSON；本版不从MIXED簇生成未经人工审核的“人体子集”。无效源row单列排除，不能被平移成有效结构。
- 高度/跨度/质心/主轴是描述量；不套旧upright硬门判定人体资格，不把body_axis当绝对人体朝向。主轴近退化或正负号/前后不可确定时记录UNKNOWN。
- 一一row映射与逆变换数值检查：首版纯XY平移用最大坐标误差≤1e-5m，单位m；这是数值实现容差，不是关节精度或人体物理测量门。若以后增加旋转需独立契约版本，不能现场放宽断言。

## 5. 5–7个粗结构节点及无点纪律

首版固定5个槽位：`HEAD`、`UPPER_TORSO`、`CHEST`、`PELVIS_REGION`、`LOWER_REGION`；在可分离且有实际支撑时增加 `LOWER_A`、`LOWER_B`，最多7个。上躯干/胸区须在参数契约中定义各自支撑区域；骨盆/下肢是可见点云区域代表，不冒称精确解剖关节。正式W05命名与精度资格以后另审。

每节点：原始观测xyz（m）、valid、confidence_kind、support_score、support_rows、support_n、reason、坐标帧身份；`valid=false`时当前xyz=null。support_score是诊断支撑评分，不能称校准过的正确概率。输出原始点分布/跨度等辅助证据，支持人工复算稳健中心和支撑所属。

起步方法是带剖面、真实区域密度、稳健质心及PCA描述量，参数只在开发窗口确定，写不可变prototype_params_v1.json和SHA；不改冻结S-A+、背景或人体规则。数据不能支撑参数或节点语义时，保留UNKNOWN并报告，不靠高度比例生成不可见头/脚。

举手最高点可能是手，**最高点不自动命名HEAD**。HEAD需独立可见结构/区域归属；头/手难区分→HEAD_OR_HAND_AMBIGUOUS，缺头→NO_VISIBLE_HEAD_SUPPORT。腿不能可靠分离时只保留LOWER_REGION；不知道人体朝向就用A/B，不任意标左右。空、稀疏、家具、MIXED、遮挡、冲突均有明确拒绝路径。

## 6. 时序、显示与效果判定

时间基准固定原meta的stamp_sec/stamp_nanosec，不混bag_time、墙钟或固定10Hz；实际缺帧和时间间隔保留。重复/倒退、seek、换sid/branch/坐标绑定/person_id/track_epoch必须清空状态。不能靠最近质心强接真人身份，不继承原Tracker已知碰撞/观测票缺陷。

原始节点观测与滤波位置分列。当前无支撑时measurement_valid=false且当前观测null；历史位置只能单独显示为历史，不补成当前有效节点。滤波参数是骨架新原型的独立版本，不改原Tracker的3/5、EMA、lost或Fall。

可视化必须显示来源帧/成员、支撑点、raw与filtered、UNKNOWN原因和GT覆盖；导出与校验绑定同一成员/参数/运行SHA。原始点、算法颜色和人工标签分别说明；R2的合成UNKNOWN导出不算真实GT。

评估分别报告：计划帧/已审帧/可消费PERSON帧/拒绝与未审帧；逐节点的人工可见/不可见/不确定数、valid/UNKNOWN、已标可见区域上的粗节点覆盖与区域参考误差、跳变/时序延迟/缺失恢复。无点、UNKNOWN、失败帧不从分母删去。人工在点云上标的区域不是独立精确关节坐标，区域中心误差不得宣传为真实关节定位精度。

首版只验工具、绑定、支撑纪律和已标片段可行性；不设置凭空的全身精度承诺，不把报告完整当节点识别已达标。若关键真实正例全部无效，阳性能力项FAIL；人体GT/节点GT不足则相应项BLOCKED。头失败要披露，躯干成功不代表头或完整四肢通过。未来精度目标须在独立标注资料/口径冻结后另审，不回改本轮结果。

## 7. 范围、资产和正式阶段门

未来实施只在新 `evidence/<日期>_hrskeleton_offline_r<N>/` 新增PC离线工具/派生数据/测试/审阅材料，追加本工单return。Python采用3.8兼容的stdlib+已安装NumPy；已有raw/坐标纯函数与R2绑定实现只读复用，不安装PCL/OpenCV/RKNN或引入新模型。先审查已有_eig3/cluster_features及其调用者，不能将家具评分复用为人体真值。

只读：src、pc_apps现有生产/旧limb/ML、webui、所有captures、旧evidence、冻结threshold/config、原Tracker/背景/Registration/Fall。禁止本单部署、采集、板端连接、重签/安装artifact、启生产旗标、commit/push/reset/checkout/clean。临时本地审阅服务若需要只绑定127.0.0.1并在结束时停止。

骨架结果不能反向证明“这个簇是人”，不能提供背景删除权。弯腰/坐蹲/躺卧、多人、真实跌倒、关节精度当前NOT_RUN/BLOCKED；现有旧数据将来只有经单独绑定和人工身份/姿态确认后才可作为追加测试，不用合成姿态宣布真人能力通过。

正式进入主线W04/W05需：相关W03安全/保留/实例来源验收闭合并明确放行；人体身份/连续性有真实GT；涉及registration的固定输入和VALID消费资格经原契约验收；本离线标准化/节点原型独立复审；用户另外授权正式接入。本计划和离线工具PASS都不改变这些条件。

## 8. 交付和停止点

交付input/split/params契约、真实GT与来源、normalized/nodes raw/filtered JSONL、原row支撑、逐ID验收、正负测试/独立复算/相关回归、审阅页/关键帧、旧资产完整性、局限/REVIEW/return。与每个输出绑定实际命令、runtime、exit、输入/源码/参数/产物SHA，旧失败不覆盖。

独立复审须至少独立从raw重建支撑/逆变换并手算测试预期；外部审阅者/另一个agent未实际参与时不声称第三方签署。单writer，是否另行安排独立人员由后续明确指令决定，不自动启动代理。

现在停止在计划可转发。推荐下一指令范围：**“按HR-SKELETON-OFFLINE开工，仅做A–F的PC离线范围；GT缺失保持BLOCKED，不修改生产和旧资产。”** 这只是建议的清晰表述，其他同等明确的用户开工授权同样有效，不要求暗号。

# 下一阶段人体识别计划与当前效果（2026-10-07）

## 2026-10-07 W03 收口当前状态更新（R39-CLOSEOUT）

**REWORK_REQUIRED / SUBMITTED，未 ACCEPTED；W03 未冻结，不进入 W04。** 本轮用户明确授权 A–F 审计、可标注诊断、最小统计修复和完整离线 shadow；未授权 registration R3.9 生产接入、W04–W09、采集或部署。工单：[HR-W03-R39-CLOSEOUT](tickets/HR-W03-R39-CLOSEOUT.md)；[最终收口报告](evidence/2026-10-07_hrw03_r39_closeout/08_final_closeout.md)。下方保留同日先前计划与观测原文，旧“当前”数字须结合本更新读取。

- 背景收益复现：WD01 93,423→1,754（98.1225%）；WD02 159,247→24,508（84.6101%），仅为背景残留改善。
- [31 点逐点审计](evidence/2026-10-07_hrw03_r39_closeout/02_absorbed_points_analysis.md)：30 点 registration 后越过既有 z=0.10 workspace 下界，1 点 reference 匹配；29 点属于 P 输出候选 track 1，2 点已被 P cleanup 删除。涉及 7 帧/7 个 frame-cluster；人体语义全部 UNKNOWN，T38-05/S4 仍 FAIL，不能自动判地面。
- [confirmation 当前归因 r2](evidence/2026-10-07_hrw03_r39_closeout/04_confirmation_attribution.md)：new green61=gain39/history20/topology2；new purple70=gain58/history1/topology11；disappeared126=WD01静态期望102/reference8/history6/candidate-loss6/topology4。机械归因覆盖全部257行，但非静态155行真人身份/连续性仍 UNKNOWN。P/S候选 overlap split10/merge2，不声称已知真人 fragmentation 或 FP/FN。
- 统计 bug 已最小修复：PL 三个诊断表达式使用数组 length；P/S全部165帧非诊断输出及R3.6算法结果相等。cleanup自身 split/merge=0，但 S128帧簇数减少，严格 `cleanup_split_delta==0` 仍不满足；无新增确认门也 FAIL。T38-06/S7 不因修复NaN变成PASS。
- [gate固定解复核](evidence/2026-10-07_hrw03_r39_closeout/07_gate_diagnosis.md)：5938/11959=49.652981%<50%；差42 keep / 70 raw correspondence。真实协议支撑不足接近边界，未放宽门或重调解。旧 artifact 历史 gate 仍 DEGRADED；统计修复改变全文件SHA后**当前 loader 为 STALE（METHOD_STALE/REFMAP_DRIFT）**，全帧SAFE=P已验证，原artifact未改写。
- 新 metric/attribution、pipe、replay、registration/load、原R3.6 digest/equivalence及故障SAFE回归 PASS；完整 shadow 执行完毕 exit1（T38-05/06失败）。逐ID和实际命令见08；真人弯腰HP02 BLOCKED，设备/物理 NOT_RUN。

下一步仅补人工GT和既定gate支撑/契约审查：[点云审阅/标注页面](evidence/2026-10-07_hrw03_r39_closeout/09_point_review.html)，优先31点的 f63/65/85/90/99/123/146、24个非WD01消失行、10split/2merge帧；完整待标清单与格式见04及 `09_gt_pending.json`。标注后运行 `review_gt.js` 写新结果，再在新evidence轮复跑全链，不覆盖本轮。GT完成亦不自动绕过gate；W04放行条件保持。

状态：PLAN_RECORDED。来源：用户本轮“制定下一阶段人体识别计划、现在效果怎么样”。本文件落实规划，不启动 W04–W09、采集、模型切换或部署。既有 [W01–W09 架构](W01_W09_FINAL_ALGORITHM_PLAN.md) 保留；本文件补充当前前置、交付顺序和验收口径。W03 仍未冻结。

## 1. 当前效果

现行生产代码 `human_pipe_lib.js` 依靠身高、宽深、半径、直立度、人形证据、3/5 时序确认与 Tracker。几何相似的家具仍可能被识别成人；时序确认不能修复错误的上游聚类。现无真人测试集上的 Precision/Recall/F1、姿态混淆矩阵或跌倒误报/延迟，不能报告“识别率 90%”等数字。

| 已有观测 | 实测结果 | 结论与边界 |
|---|---|---|
| WD01 静态人形物 reference 查询残留 | 未对齐 A：14,966 点；固定 B：1,875 点，下降 87.5% | 对齐有效；仍有残留，不能等同人体误报率下降 87.5% |
| WD02 远场静态残留 | 104,742→11,625 点，下降 88.9% | 单一冻结会话对上的离线收益，未进入生产 |
| 对齐后 WD02 下一瓶颈 | oracle-like C 残留 10,581 点；77.7% geometry、13.3% missing、9.0% sparse | 再调 ICP 余量很小；matcher 修改仍须独立安全 A/B |
| 人体安全对照 | R3.6 clean controls 总吸收约 1 点；f155/f160 贴静态块高带仍有误吸收 | 窗口为 proxy，非真人逐点 GT；贴物体边界风险未消除 |
| 当前 R3.8 首个不可变 artifact | gate=WARN；loader=DEGRADED；5938/11959=49.653% trimmed inlier ratio，低于 v1 pass 50% | 只允许 shadow；不放宽门来凑 PASS，不能启动 R3.9 |
| R3.8 残差/几何 | fit p50=14.52 mm；holdout p50=11.09 mm；condition≈104.27 | 已有对齐指标，T38 整链安全门另验 |
| 本轮完整 shadow（相对生产 P） | WD01 93,423→1,754，减少 98.1%；WD02 159,247→24,508，减少 84.6% | 背景收益通过；仍是本机离线窗口/点级指标，不是识别率 |
| R3.8 人体安全门 | clean 人窗总吸收 **31 点**，全部在 z<0.3 带，超过预注册≤5 门；T38-05/S4 FAIL | r2 漏计近地带的 0/PASS 已纠正；点是否为人脚/地面须 GT，但不能跳过安全门 |
| R3.8 完整管线共同门 | T38-06/S7 FAIL：native cleanup_split_delta=NaN；相对 P 新增 green 61 行/purple 70 行，需逐簇归因 | 不能接生产、不能冻结 W03；新增确认不等于新增误报，须有 GT |
| 真人弯腰 HP02 | BLOCKED（合成数据不替代真人） | 弯腰识别未验证通过 |

来源：[R3.6 结果](evidence/2026-10-06_hrw03_r8/03_results.json)、[R3.6 分析](evidence/2026-10-06_hrw03_r8/06_summary.md)、[R9 归因](evidence/2026-10-06_hrw03_r9_ref_coverage/09_final_attribution.md)、[R3.8 最终自验/停止点](evidence/2026-10-07_hrw03_r38/10_final_submission.md)。A 是诊断 reference 查询，生产 P 为 online-only，两者分别报告。背景点消除比例不是人体识别精度。

## 2. W03 前置收口

1. **R3.8 shadow 返工/设计审查**：先审计 31 个近地点损失（裁剪/online/reference）、簇数统计数组减法与新增确认的逐簇归因，再验证真人 track 保留。PIPE/生产管线当前冻结，不擅改；返工许可应明确最小统计修复，不调 matcher。gate 实测 DEGRADED；支撑门定义须设计审查，不原地改 v1、不事后换解。物理/外参/runtime 旗标仍 false。
2. **R3.9 最小接入**：须另行授权且满足放行前置；默认关闭能力旗标，只有 VALID 使用注册分支，其余保持 P。浏览器/节点实际行为单独验证。
3. **R3.10 残留归因与 R3.11 matcher 方案**：冻结注册/参考图，先定位 geometry/missing/sparse。独立安全 A/B 后才提出 matcher 修改。禁止降低 online occupancy、以持续静止强删人体、重开已否定的 mobility 假设。
4. **W03 最终冻结**：沿用 WD01/WD02/HP01–03，空场固定物 0 human candidate/0 confirmed，站立/弯腰/躺卧人体保留；cleanup split=0、无新 green/purple、已确认人体静止后不吸回背景。HP02 缺数据明确 BLOCKED，单测数不能代替闭合。

## 3. W04：人体 Track 点云标准化

目标：每帧点属于谁、处于哪个坐标系、可见程度如何，都可追溯。输入 track_id、cluster points、原始 timestamp、frame tag、精确 leveling/registration 身份。仅对通过上游检查的 track 建立局部表示；不靠最高最密柱体选人，不以人工 pin 作为运行前提。

输出 normalized_points、原帧点索引、地面相对高度、宽/深/跨度、质心、主轴、点数、可见性/置信度和 UNKNOWN 原因。XY 平移至人体中心，Z 沿既有地面平面，保留逆变换。地面语义不等于已验证的绝对安装高度/外参；主轴朝向不确定时不硬猜。

验收：标准化/逆变换一致；跨 sid/frame/artifact 不混用；空帧、稀疏、遮挡、贴墙、家具粘连有明确失效输出；丢失/重获 track 不继承旧身份；静站、行走、弯腰、坐/蹲、躺卧均保留可见人体点。先审计“已确认人体→低姿态”连续性，现行 upright gate 可能把下降姿态排除，不能到 W05 才发现无骨架输入。

交付：不可变 normalized-track 契约、离线 exporter、逐帧诊断、现有会话基线与唯一验收表。涉及生产 eligibility 的变化另审，不直接放宽所有候选门。

## 4. W05：粗骨架与时序稳定

先做既有架构要求的 5–7 个结构节点：头、上躯干/胸、骨盆、下肢结构。每节点记录 valid/confidence/support_points；头、左右肢或脚缺乏点云证据时输出 UNKNOWN/invalid。暂不承诺 COCO 17 关节或完整四肢精度。

站立可用地面 Z 分带、稳健质心与局部 PCA；弯腰/躺卧须以身体主轴辅助分段，不能假设最高点始终为头。骨架 tracker 独立于原 human Tracker，按真实帧时间处理平滑、跳变、缺失、恢复；换 track/artifact 清空旧状态。节点误差与覆盖率来自人工标注，合成测试只验证数学和生命周期。

## 5. W06–W07：姿态与跌倒

W06 输出 UPRIGHT、BEND、CROUCH_OR_SIT、LYING、UNKNOWN；Walking 属 motion_state。先做可解释规则基线，结合头/骨盆高度、躯干角度、跨度、时序，记录证据。没有足够标注前不引入学习模型、不打开 dormant ML。

W07 再实现 NORMAL→DESCENDING→TRANSITION→GROUND_POSTURE→FALL_CONFIRMED/RECOVERY。利用下降速度、身体轴旋转、头/骨盆下降和落地持续；主动躺下、坐下、弯腰捡物作为负例。LYING 不直接等于 FALL。误报和延迟以真实事件时刻为准；采集前确定安全动作/标注方式，不要求危险摔倒。

## 6. GT 与评估

现有会话/leveled 输入只读复用。先做 `source:"human"` 标注：人/静态物、track 连续性、姿态、事件时刻、遮挡、点混合。截图视觉对应不作为精确坐标 GT；标注写派生文件，保留原始会话及 SHA。

待另行授权采集：正式 20–60 s 空场；静站/行走；真人弯腰 HP02；坐/蹲、主动躺下/起身；靠墙/家具、遮挡、不同距离、多人交叉。记录场景变化和可见性。

按会话拆开发/验证/最终留出集，避免相邻帧调参和验收泄漏。W08 报告人体 Precision/Recall/F1、姿态混淆矩阵和 UNKNOWN 比例、track 断裂/身份切换、节点可用率/标注误差、每小时跌倒误报及检测延迟。先冻结评测集/口径，再定性能目标；无 GT 项明确 NOT_RUN/BLOCKED，不编造精度。

## 7. 本次安排

R3.8 本机离线实现与验证已 SUBMITTED/停写；T38-05/06 与 S4/S7 未过，尚未 ACCEPTED。下一步为 W03 的近地带安全审计、统计缺陷审查、确认变化归因和支撑门定义复核，之后才有条件进入 R3.9/W03 最终验收，再进入 W04。W04 契约/GT 规划可先审阅，不跳过上游直接四肢识别。R3.9、W04–W09、采集、部署、模型切换未由“制定计划”自动授权。


## 2026-10-08 R2之后的离线骨架规划更新（仅计划）

用户本聊天在询问骨架时点后要求制定下一阶段计划。最新 [SEM-SHADOW-R2](evidence/2026-10-08_hrsemshadow_r2/REVIEW_R2.md)：SEM-12 PASS，其余人体GT/旧负例项与WD02仍BLOCKED，离线交付未ACCEPTED；W03正式冻结与W04/W05主线门保持。

新增 [HUMAN_SKELETON_OFFLINE_PLAN.md v1](HUMAN_SKELETON_OFFLINE_PLAN.md) / [HR-SKELETON-OFFLINE](tickets/HR-SKELETON-OFFLINE.md)，唯一验收表 [HR_SKELETON_OFFLINE_ACCEPTANCE.md v1](HR_SKELETON_OFFLINE_ACCEPTANCE.md)。先A固定来源/100原始帧窗口，B最小真实人工身份/节点可见性，C可逆标准化，D粗结构节点，E独立时序，F验证/复审。人工确认输入是实验夹具，不替代正式自动选人；WD02不进入本实验且继续阻断；head/hand歧义与无点UNKNOWN必测。

状态DRAFT_READY_FOR_DISPATCH，未实施。只规划受控离线可行性，不跳过原主线放行、不重开旧limb/ML；正式接入仍须原前置验收和单独授权。先最小GT再真实节点试验，GT缺失只完成独立工具部分、相应真实指标BLOCKED。

# Claude Code 离线开发任务书（待后续明确派工）

依据 [完整诊断报告](REPORT.md) 第10节。此文件是交付物，不代表本轮已经启动这些开发任务。按依赖顺序执行；生产源、当前GT、captures和历史证据只读；不部署、不采集、不切生产模型。一个任务一个writer，实施者首先读取并回传 `C:/Users/30680/.codex/skills/ponytail/SKILL.md` 的使用路径。

## 共同契约

- 开始读取仓库当前 HC/HR README 与 HF WORKFLOW（涉及HF时）；仅最新当前指令授权。检查并行工作树，保存含untracked SHA。使用新隔离目录，固定engine/model/tracker/GT/参考和输入SHA；不覆盖当前Claude成果。
- 写新版本验收表并冻结阈值、split、候选/轨迹匹配方式和UNKNOWN处理，再执行。证据新建 `docs/human_capture/evidence/<date>_<item>_r<N>/`，回传追加 `docs/human_capture/returns/<ID>.md`，按RETURN_TEMPLATE逐ID报PASS/FAIL/NOT_RUN/BLOCKED。
- candidate stage success必须在classifier前计算；所有分数使用实际raw pointset，点数/count/bbox/version一致。每次改变候选后重新评估旧、新失败，不能仅记录救回帧。
- 与当前XGB69+UniqueTracker比较candidate、observed confirmed和coasting；FP按帧率和持续事件并列；FN按段长、恢复延迟并列。预测不能记为当帧检测TP。
- 未标/混合/不可信绑定保持UNKNOWN。source human只来自实际人工审核，不用程序修改SHA或模型标签制造人工真值。
- 本轮报告五个实验的PASS阈值是建议；后续若改目标，先升新验收表版本并解释，不覆盖旧FAIL。

## HFUS-D01：完整分层账本与冻结基线

**输入：** 本证据目录 `workspace/`、snapshot_manifest、新S6 probe，以及当前Demo V2记录。**改动范围：** 新隔离工具/研究副本；不修生产。

**实现：** 每个有效GT观察输出sensor/level坐标、RAW数、crop/缺参考/envelope互斥损失、cleanup/retention、A/B每个component原始成员、拒绝门、actual scoring points、candidate score、关联对象、年龄/strong票、visible标志；所有环节记录版本。GT只用于事后归因，不能输入检测器。输出逐帧JSON和最差案例索引。

**验收：** 同阈值XGB+Unique复现 S1 0/0/0、near track256/9/2、S6 track61/1/10；S6 candidate65/1/6；每个阶段GT点分区守恒。对本轮f187/f188明确234/245缺参考损失；f128–130/f171拒绝原因可追。inputs前后SHA一致。不同版本则记录漂移，重新基线，不强行匹配旧数字。

**交付：** baseline/source manifests、账本JSON、命令/退出码、变更范围、失败清单。首次诊断通过不代表修复通过。

## HFUS-D02：人工审查包与评测资格

**实现：** 从现有会话导出S6失败及邻帧、S4/S8连续窗、S1传播抽检与非train困难候选；导出原点/成员映射/静帧图/已有标签，机器建议默认UNKNOWN。新版本manual review输入和旧GT只读分离。审查S9数据SHA、compact成员、双人对象与continuous track IDs，禁止仅rebind hash。

**验收 E1：** 拟评分观察全部有效绑定+审核来源；cross-fold exactduplicate=0；val/test拥有独立于train的已审核负候选；已标人体无候选仍进入召回分母。没有人工审核时，工具工程项可PASS，语义/双人/新家具泛化必须BLOCKED/UNKNOWN。

**交付：** 待审候选与片段清单、UNKNOWN理由、split manifest/去重报告、人工审核协议。保留低purity混合候选用于审查，不默认为负例。不要把S1同五家具传播1515次当作独立家具数量。

## HFUS-D03：参考三态与UNKNOWN受约束通道

**晚到V3补充：** 先读报告第12节。V3-B点保留改善但UI仅换mask，不是B全链；将现成B作为隔离候选路径对照，直接复用背景统计，集中测实际score/track/visible。B-S1家具XGB FP595/608，必须纳入负例压力。f128实际GT点已被cluster keys覆盖，不可按“15<60”独断失败门；必须记录所属簇纯度/score。禁止把GT选orphan的oracle脚本当可运行无人标检测器。

**前提：** D01已冻结。**实现：** 先追踪S6缺参考keys到reference构建、量化、变换及visibility；分明occupied/free/unknown，不在未知上直接判background。有效参考旧路径保留；unknown单独生成带coverage/context标签的候选，禁止在线将人写进参考。候选经过本域语义和背景困难负例约束再确认。开发初期保持XGB和tracker不动。

**禁止已FAIL方案：** 两处`bg===undefined`全放行。该方案在S1已确认FP740，S6候选召回没有净提升。

**验收 E2：** S6候选TP≥67/71、确认TP≥64/71；f187/188正确候选coverage≥50%/purity≥80%；S1确认FP=0；near确认TP≥256、FP≤9。新误检/新漏检任何一项破约束即FAIL；新家具泛化仍待独立数据。一次最多调整一项参考/候选语义。

## HFUS-D04：稀疏候选与因果时序支持

**前提：** D03或另一明确冻结基线。**实现：** 独立消融A 60点/3cells、B30点/连通性，加入可见性/距离上下文；只用过去0.2/0.5s窗，逐点保留frame/raw-index，按运动补偿或静止判定组织支持。不要把相同坐标、复制采样或生成点当新实测信息；不使用未来GTseed检测。

**验收 E3：** f128/129/130/171至少2帧正确候选coverage≥50%、purity≥80%；S6candidate FN≤4；S1确认FP=0、near确认TP≥256；PC计算p95≤50ms、不含渲染单独报。家具混入、未来信息和新增失败必须保留。严重物理缺失标UNKNOWN，不能用合成姿态替换观测。

## HFUS-D05a：固定候选分类与困难负样本

**先修工具契约：** V3 PointNet评测遗漏中心化，与训练不一致；新隔离推理已证实test58/65、stress39/58，不能沿用错误全中表。复用本报告中心化A/B结果，只需修新研究评测消费者并做对应一致性检查，别再重训或重演已确定根因。V3正文GT分母与JSON不符须对齐；模型“记忆”与残差形状域差先保持多假设，做去代理/固定位置消融。

**前提：** D02人工review及有效split。**实现：** 固定actual候选点集，RF51 / 去XY和密度代理 / 相对形状+背景coverage XGB消融；按session/独立片段分组、阈值仅validation确定；不复制负样本入不同fold。native导出需与Python Float32逐候选一致。tinyPointNet只是同预算控制；不直接切生产。

**验收 E4：** S3far candidateFP≤48、trackFP≤46，trackTP≥97；S6candidateTP≥65、trackTP≥61；S1trackFP=0，其他有资格场景不回退；已审负例precision/recall和final指标都报告。无有效heldout negatives→BLOCKED；分类分数改善而最终指标无改善→FAIL。

## HFUS-D05b：固定检测的ID、静止与显示一致性

**前提：** 有效S9身份GT与S4/S8连续人工窗。**实现：** Unique基线 vs XY常速度KF/Hungarian shadow；每帧一对一，出生/确认/漏观测/coast/结束用时间单位；内部计分、vote、actual pointset和可见状态来自同一源。几何后处理不应继续用未声明RF内部票冒充几何tracker。

**验收 E5：** duplicateID=0；IDF1≥.90且每序列IDSW≤1；≥20s已审静止窗observed confirmed覆盖≥95%，确认≤.3s；离开后visible coast≤.5s。coast不计检测TP；S9资格不齐→BLOCKED，不能以单人近景代替。shape保持GEOMETRIC_PROXY_ONLY/poseUNKNOWN。

## 停止与升级条件

E2/E3在已审空场和近景约束下没有净收益，停止堆过滤门，提出路线B独立RAW上下文/BEV原型的新工单。E4固定候选已很好而终端漏人，回到proposal/lifecycle；E5没有身份真值，先补审查，不凭肉眼宣布稳定。任何后续生产接入、ROS里程碑、模型切换、板端NPU/部署、真实采集均需要新的当前授权，不在本任务书自行执行。

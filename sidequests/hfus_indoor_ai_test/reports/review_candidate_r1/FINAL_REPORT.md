# HFUS-INDOOR-AI-TEST-01 FINAL_REPORT / review_candidate_r1

SUBMITTED；学习与独立检测效果BLOCKED。可运行真实点云/待核验框/无监督候选Demo，不宣称算法有效或统计泛化。设备、物理、采集、部署、HR09/HFUS E1未运行。

## 实际成果与分母

run `r5_20261015`；manifest SHA `7989548dd28d0030e10e9eac7a297a475c0da14167fedf6d37a583ce75b1bb6e`；split SHA `c3318abc686a4c8517bc98928319d72c3ca161c626e0c11cb403ed5654f06d82`。
det 106帧/293框（原目录training29/87、validation1/3、test76/203）；track80帧/233框。
总186帧/526框。跨包精确重复组2，近重复签名筛查1704对、记录前200对，余1504对保守UNKNOWN；全部一未核实组，不相加成独立样本。
可信独立采集组0；冻结train/val/test均0帧，全部186仅诊断。旋转RESOLVED0、完备CONFIRMED0、人工审核0。
新RF/PointNet训练0次、神经启动0、optimizer_steps0、训练耗时0；没有新有效学习权重。旧冻结权重SHA见BASELINE/PRESERVATION，不假称本轮模型。

## 实际几何运行（不等于人体识别）

|来源|模型|诊断帧/库存框|候选数|CPU计算P50/P95 ms|读取+计算P50/P95 ms|
|---|---|---|---|---|---|
|det|B0_GEOM|106/293|33215|915.02/1207.26|942.90/1241.66|
|det|B1_HDBSCAN|106/293|85795|5049.35/6570.22|5072.44/6596.71|
|track|B0_GEOM|80/233|26372|802.95/987.69|824.71/1009.53|
|track|B1_HDBSCAN|80/233|79229|4542.52/5171.98|4564.31/5194.82|

四行的诊断分母分别为det106和track80，不是独立test。每模型全局前5帧为预热，未纳入P50/P95；track没有重复扣除预热。CPU4计算线程，串行逐帧，不与训练并跑；I/O为ZIP读取+解析校验，端到端为同帧I/O+候选计算；没有分类器，特征/采样/分类推理不适用。非板端FPS。时延不包含离线代理GT分析/账本序列化，也不包含浏览器；这些不是在线检测阶段。峰值见RESOURCE_SUMMARY及逐帧observed RSS，监控后附着限制明确。

原cluster .05m voxel/.17m eps/4voxels/25points固定不改。B0为原聚类原语在完整源XYZ上的诊断，未套IFW背景、ROI或地面；完整G0 BLOCKED。HDBSCAN同voxel和源行，min_cluster_size4/min_samples4，固定未调优。候选框是实际成员AABB，GT不参与候选生成。没有学习分类分数，页面写N/A；不会把静态结构簇称人。

## 评价与案例

主IoU.25/.50：各来源test帧0、可评GT0，TP/FP/FN/P/R/F1、匹配IoU、漏检0分定位、可信候选覆盖/碎片/混合率均NOT_EVALUABLE。所有526框旋转未知，全部排除监督与主指标。完备性未知的未匹配候选不能算FP或负类。空场FP与逐点指标无GT，NOT_EVALUABLE。
metrics的proxy字段是明确不可信AABB代理诊断，不用于算法胜负、下一阶段覆盖阈值或完备负类。完整case_index列372个frame/model审阅项，均未核实结果；可信成功0、可信失败0，不冒充10成功/10失败。页面可查全部，十个多样样本另有真实浏览器证据。

## 启动与证据

当前准确URL：http://127.0.0.1:59840/indoor-ai/r5_20261015/
重启：双击 `D:/Code/ldiar/sidequests/hfus_indoor_ai_test/demo/start_demo.bat`，固定run，自动空闲端口，打印并打开准确URL。或 `python -B -W error sidequests/hfus_indoor_ai_test/demo/server.py --run r5_20261015`。不杀端口占用进程。
完整payload位于父run `r4_20261015`，由父manifest SHA与各artifact SHA绑定，不复制巨型账本。points接口提供完整XYZ，source_row为原float32×4的0基行号；无IFW字节伪造。
实际S1十帧包含1/2/3/4框、不同命名日期、training/test、最大/最小框及最低58点支持框；S2展示实际B0/HDBSCAN、全点与BLOCKED切换。最终浏览器记录/截图见本轮evidence。Python10项和JS状态机检查、失败日志、独立重算/保护检查均在evidence；测试数量不替代A01–A16。

## 用户八问

1. 公开数据支持HFUS哪部分：支持真实XYZ读取、框级审阅工具及候选生成诊断。当前不能支持可信逐点/实例/骨架/跌倒监督，也不能解锁E1。
2. 哪个算法实际识别人：本轮没有可审计的人体分类结论。B0/HDBSCAN仅生成真实候选；所有学习模型未在本轮有效推理/训练。
3. 家具混淆有改善吗：UNKNOWN。没有家具GT或可信完备负候选，不能用代理FP或框外点宣称改善。
4. 聚类上限及是否保留：可信上限未知；保留原参数作为对照。大量房间候选可视化表明需要核验，不能从不可信proxy直接触发“覆盖低”或选聚类赢家。
5. PointNet相对原RF/新RF：UNKNOWN。原RF51/69缺有效强度与IFW高度契约；新RF与PointNet缺两类监督，三seed均NOT_RUN。
6. L3D/L2D是否真训练：没有。L3D/L2D/LFUSION保持UNTRAINED；0优化步，不冒名本轮PointNet。
7. IFW192S域偏移：公开为overhead场景，源轴方向仅几何推断；IFW为已定R/T的本地场景。公开第四列全0、训练约5.6万点而test约11.2–16.8万点，叠帧/采样机制未核实；家具、遮挡、人物、反射/强度和背景不同。不能推断本地跌倒或板端性能。
8. 下一优先训练/标注/补采：先核对旋转/末列与序列映射，再做可追溯真实人工完备性/负候选审核。当前不继续训练、不先补采；已有数据门尚未闭合。下一阶段仅制定计划，不执行。

## 审查与限制

开发后OpenCode状态：NOT_RUN。仅AI源码/记录审查，不是人工GT或独立数值复现实验。原始jsonl、session、真实模型export、权限、briefSHA见evidence；服务失败不能换模型或报PASS。
本机软件可看/可核验，学习目标和统计证据仍BLOCKED。唯一逐条结果见RESULTS.md，不能自行ACCEPTED。旧数据/EXE/默认R1/learn/r01/冻结权重/历史证据未由本工单覆盖；其他并行工作不接管。新产物512MiB、CPU4与RSS停止12GiB约束见资源账本。

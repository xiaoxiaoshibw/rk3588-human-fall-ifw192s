# HUMAN-FUSION R5–R8 / Demo V1 实施与实测报告

2026-10-11（Asia/Shanghai）。本地研究软件 SUBMITTED；物理识别验收未完成，未 ACCEPTED。

## 可运行交付

现有仓库 D:/Code/ldiar 中新增 sidequests/human_fusion_lab：隔离引擎、模型、跟踪、Demo和实验结果。默认 xgb69_candidate，可选原RF、候选RF51、RF69、一对一跟踪 xgb69_unique，缺失模型回退原RF。失败静态支路保留研究源码，不进入正常菜单。入口 http://127.0.0.1:8791 ，启动见 START_HERE.md。

Demo显示候选实际点集、分数、分类、来源、Track ID、可信GT与0.75m一对一TP/FP/FN。九会话切换、拖动、回退、重播、重置、播放暂停与算法切换通过真实Chrome检查；拖动时重放前缀，恢复时序状态。

## R4 / R5 契约核查

R4的A+B联合评分与公开索引不符，已修复于lab/core/engine.js。九会话2605帧对拍PASS，43个合并候选的raw indices/count/bbox同步到有序去重的实际评分联合点集。概率、分类、关联锚点、Track ID、事件与R4完全一致。关联质心保持A锚点，评分点集质心另以scoring_centroid提供；engine_r4.js保留复现。

GT compact索引按同帧有效有限XYZ且非零点序映射回raw；验证边界、点数、重复身份和联合去重，不用坐标集合消除重复点的raw身份。

## 数据资格与无泄漏划分

|会话|帧数|GT版本/资格|已标帧|未标帧|
|---|---:|---|---:|---:|
|S1-empty-with-furniture|304|V3 / 绑定及review标记通过|304|0|
|S3-walk-x-near|258|V1 / 绑定及review标记通过|258|0|
|S3-walk-y-far|464|V1 / 绑定及review标记通过|99|365|
|S4-walk-stop-walk|239|V1 / 绑定及review标记通过|11|228|
|S5-turn-in-place|202|V1 / 绑定及review标记通过|6|196|
|S6-occlusion|238|V1 / 绑定及review标记通过|71|167|
|S7-far-5m|251|V1 / 绑定及review标记通过|12|239|
|S8-still-retention-long|523|V1 / 绑定及review标记通过|53|470|
|S9-two-person-cross|126|V2 / UNKNOWN：绑定不符|0|126|

九组meta/points均真实可读取，28B连续帧契约通过，总2605帧。八组GT版本/manifest SHA/reviewed/数据绑定/对象契约合格；这是元数据来源资格，非现场独立真人确认。S9 V2 SESSION_SHA_MISMATCH_OR_MISSING，未擅自重绑定或标注。

训练：S1、近行走、走停走、原地转向；验证：远行走；测试：远距S7、长静止S8；stress：遮挡S6。AUDIT在训练前冻结session划分、标签策略及0.55门限。所有特征来自候选点云，不含推理不可得GT。UNKNOWN未作为负例。

**RETROSPECTIVE_SESSION_HOLDOUT：历史研究曾查看测试会话，非前瞻全新测试。陌生人员、独立家具、新场景泛化UNKNOWN。S1负例只在train，空场改善不代表独立家具泛化；传播/相邻帧相关，观测数不等于独立样本数。**

## R7 实际候选级数据

主路6900个实际评分候选，859个符合固定交叠标签规则。训练正142/负566。人体纯度>=0.8且无明显异类混合；家具负例必须>=0.8家具点交叠。NO_OVERLAP/混合/缺标为UNKNOWN，不自动负标。候选raw点集、帧/session、51D/18D扩展、GT交叠、256点shadow采样及来源保存在results/*.jsonl。

这些标签是reviewed GT的规则派生标签，非人工逐簇确认。按session/class权重减弱重复观测，不能消除同场景偏差。第二次dataset_dual导出实际原始静态支路候选，沿用划分/规则重训，保留失败结果；没有根据test调门限。数据留在仓库，交付DATASET_MANIFEST提供路径/字节/SHA。

## 固定候选对比与特征消融

|模型|测试候选TP/正例|验证TP/正例|遮挡TP/正例|训练秒|
|---|---:|---:|---:|---:|
|rf51_baseline|65/65|28/28|58/58|UNKNOWN|
|rf51_candidate|57/65|13/28|4/58|0.13|
|rf69_candidate|60/65|17/28|33/58|0.11|
|xgb69_candidate|65/65|28/28|58/58|0.056|
|pointnet_shadow|58/65|28/28|39/58|3.889|

只统计同一冻结且可标候选，不含提案漏检，不能当端到端召回。RF51/RF69参数相同；18D为六高度切片点比例与XY的10–90%宽度，使用实际候选全点。RF96树、XGB CPU hist，4线程、固定0.55，无test调参。通过validation和训练空场行为综合选择XGB独立实验配置，生产不推广。

六个导出模型各200样本JS/native概率对拍PASS，最大误差<1e-7。已修正XGB decimal split条件与float32边界比较（Math.fround），缺模型RF回退通过。

## 完整同源回放对比

主对比36次、后续路线36次、默认带源码/GT/input SHA守卫复验9次，合计81个会话/模型完整回放、23445帧tick，不含R5对拍/导出/中断运行。下表主对比：候选接受HUMAN_CANDIDATE或CONFIRMED_HUMAN；轨迹仅当前lost=0确认；GT一对一匹配。

|模型|会话|候选TP/FP/FN|轨迹TP/FP/FN|相邻已标ID切换|P50/P95 ms|RSS观测峰值MB|
|---|---|---|---|---:|---|---:|
|rf51_baseline|S1-empty-with-furniture|0/604/0|0/600/0|0|9.29/11.97|612.1|
|rf51_baseline|S3-walk-x-near|258/393/0|256/379/2|1|10.78/13.87|1164.8|
|rf51_baseline|S3-walk-y-far|99/227/0|96/210/3|0|12.45/24.12|969.9|
|rf51_baseline|S4-walk-stop-walk|11/26/0|10/23/1|0|13.91/17.40|1277.5|
|rf51_baseline|S5-turn-in-place|6/6/0|5/5/1|0|13.38/20.15|1021.8|
|rf51_baseline|S6-occlusion|64/139/7|61/137/10|0|13.48/25.48|1066.4|
|rf51_baseline|S7-far-5m|12/21/0|11/18/1|0|13.87/20.12|1129.3|
|rf51_baseline|S8-still-retention-long|53/53/0|51/51/2|0|12.50/23.59|1695.9|
|rf51_baseline|S9-two-person-cross|UNKNOWN|UNKNOWN|UNKNOWN|23.86/32.31|530.9|
|rf51_candidate|S1-empty-with-furniture|0/0/0|0/0/0|0|4.88/8.95|665.7|
|rf51_candidate|S3-walk-x-near|258/19/0|250/9/8|0|5.51/6.59|1183.1|
|rf51_candidate|S3-walk-y-far|34/97/65|15/93/84|0|6.69/19.58|1583.1|
|rf51_candidate|S4-walk-stop-walk|11/9/0|10/8/1|0|6.35/8.02|1264.3|
|rf51_candidate|S5-turn-in-place|6/0/0|5/0/1|0|5.81/7.25|1019.9|
|rf51_candidate|S6-occlusion|35/1/36|5/1/66|0|4.37/6.95|1068.7|
|rf51_candidate|S7-far-5m|12/1/0|4/0/8|0|5.52/14.34|1110.3|
|rf51_candidate|S8-still-retention-long|53/0/0|51/0/2|0|5.22/7.87|1153.3|
|rf51_candidate|S9-two-person-cross|UNKNOWN|UNKNOWN|UNKNOWN|8.44/10.05|1076.1|
|rf69_candidate|S1-empty-with-furniture|0/0/0|0/0/0|0|3.74/4.51|1146.3|
|rf69_candidate|S3-walk-x-near|258/19/0|250/9/8|0|6.06/7.35|1170.7|
|rf69_candidate|S3-walk-y-far|99/3/0|30/0/69|0|8.11/26.08|1582.6|
|rf69_candidate|S4-walk-stop-walk|11/9/0|10/8/1|0|7.77/10.67|1265.9|
|rf69_candidate|S5-turn-in-place|6/0/0|5/0/1|0|6.61/8.32|1019.5|
|rf69_candidate|S6-occlusion|36/2/35|10/1/61|0|4.37/9.03|1058.1|
|rf69_candidate|S7-far-5m|12/0/0|4/0/8|0|5.80/16.14|1130.4|
|rf69_candidate|S8-still-retention-long|53/0/0|51/0/2|0|5.97/8.53|1689.7|
|rf69_candidate|S9-two-person-cross|UNKNOWN|UNKNOWN|UNKNOWN|10.57/12.92|532.8|
|xgb69_candidate|S1-empty-with-furniture|0/0/0|0/0/0|0|3.86/5.01|1140.1|
|xgb69_candidate|S3-walk-x-near|258/19/0|250/9/8|0|5.78/7.92|1183.1|
|xgb69_candidate|S3-walk-y-far|99/97/0|94/93/5|0|7.67/21.31|1575.4|
|xgb69_candidate|S4-walk-stop-walk|11/9/0|10/8/1|0|7.13/9.42|1266.6|
|xgb69_candidate|S5-turn-in-place|6/0/0|5/0/1|0|6.31/7.69|1022.6|
|xgb69_candidate|S6-occlusion|65/1/6|62/1/9|0|4.19/8.36|1062.8|
|xgb69_candidate|S7-far-5m|12/1/0|11/1/1|0|5.39/14.79|1127.7|
|xgb69_candidate|S8-still-retention-long|53/0/0|51/0/2|0|5.47/6.43|1694.3|
|xgb69_candidate|S9-two-person-cross|UNKNOWN|UNKNOWN|UNKNOWN|9.75/11.56|535.1|

FP是已review的零/单人协议下未匹配接受观测。除S1空场协议外，未匹配簇的家具身份未全面标定，不能把所有FP称家具误检。所有未标帧/S9为UNKNOWN。

默认XGB：静止53/53候选、51/53轨迹（全523帧召回UNKNOWN）；远距12/12、11/12（全251帧召回UNKNOWN）；近动态258/258、250/258；遮挡65/71、62/71。远动态轨迹94/99，略低于原RF96/99，错误确认210降为93。S1训练空场原RF候选误报604/轨迹600，XGB为0/0；独立家具FPR仍UNKNOWN。

ID切换仅相邻已标帧可测，不能连接未知区间。drops/reappearance/matchedIDs保存于JSON。模型分类会改变retention和后续候选，冻结候选对比与整链对比不能混称。

## RAW/BG/PROPOSAL/CLASSIFIER/TRACKER/DISPLAY归因

|会话|RAW|BG|PROPOSAL|CLASSIFIER|TRACKER|NONE|DISPLAY|
|---|---:|---:|---:|---:|---:|---:|---|
|S1-empty-with-furniture|0|0|0|0|0|0|UNKNOWN|
|S3-walk-x-near|0|0|0|0|2|256|UNKNOWN|
|S3-walk-y-far|0|0|0|0|2|97|UNKNOWN|
|S4-walk-stop-walk|0|0|0|0|1|10|UNKNOWN|
|S5-turn-in-place|0|0|0|0|1|5|UNKNOWN|
|S6-occlusion|0|2|5|0|3|61|UNKNOWN|
|S7-far-5m|0|0|0|0|1|11|UNKNOWN|
|S8-still-retention-long|0|0|0|0|2|51|UNKNOWN|
|S9-two-person-cross|0|0|0|0|0|0|UNKNOWN|

原RF已标人体逐点归因，RAW只说明声明人体点的有效支持。BG为参考envelope过滤比例，cleanup/retention另列；只有漏提案且BG支持不足10%时归BG，否则归PROPOSAL。proposal门为GT点覆盖>=10%且XY<=0.75m，公开操作门而非语义真值。DISPLAY只验证软件渲染，真人级展示损失UNKNOWN。

S6 f187保留9/260、f188为14/268，归BG；f91有55/303点但无提案，归PROPOSAL；f128–130及171原始只有19–36点，候选恢复优先。确认启动损失归TRACKER，不把所有漏检归RF。完整对象/帧/支持点/覆盖案例见ATTRIBUTION。

## 双路径与跟踪实际研究

实现参考BG/retention + 独立raw上身几何种子/有限XY形状/下身点恢复，并过统一分类器，未关闭全部BG，不用GT种子。原参考路径没有新增独立速度模型，不能混称完整运动支路。原始静态路径遮挡提高到68/71，却使空场候选FP624、轨迹605，FAIL；用实际dual候选重训后遮挡仅4/71候选、3/71轨迹，远距/静止退化，FAIL并退出默认。可靠静态负例缺失仍是问题，不把UNKNOWN自动负标美化效果。

旧融合Tracker观测21次同帧共享ID（近4、远14、走停1、遮挡2）。unique实现一对一关联、每轨每帧一票、失配0票及生命周期，单元检查通过。xgb69_unique近256/258、远动态97/99轨迹；遮挡61/71比默认少1，保留可切换研究，未宣称真实双人能力。S9双人分离/ID指标UNKNOWN。

## CPU资源与深度shadow

环境Windows-11-10.0.26300-SP0，RAM 31.3GiB，全部CPU。默认SHA守卫复验各会话P95最大27.14ms，RSS峰值观测最大1671.5MB。预热5帧；耗时为检测链，不含文件加载、网络JSON及绘制；系统存在其他工作，非受控硬实时测试。

PointNet-style共享MLP3/32/64/128+max+64/1，无T-Net，256点、20epoch、4CPU线程，非官方精度复现。实际训练并通过ONNX opset13/checker/ONNXRuntime CPU对拍；算子Conv/Gemm/ReduceMax/Relu/Squeeze等。第一轮RSS约1863MB是报告时值而非峰值；第二轮约2762MB。未优于XGB，保持shadow，不接Demo默认。

**RKNN转换、RK3588 CPU/NPU、8GB目标板内存、NPU耗时NOT_RUN/UNKNOWN；ONNX成功不等于NPU部署。**

## 论文/许可/源码/最小运行

- [Haselich论文DOI](https://doi.org/10.1109/IROS.2014.6943142)：大学PDF链接当前访问拒绝，未伪称全文已读；[Koide作者源码](https://github.com/koide3/hdl_people_tracking)和[2019论文](https://journals.sagepub.com/doi/10.1177/1729881419841532)核对split/merge及DP-means。固定2d125167ca2b0935b8075032b943edf11d996788、BSD-2-Clause。WSL g++/Eigen实际编译运行该DP-means PASS clusters=2；整链缺catkin/PCL BLOCKED。源码merge均值为坐标累加未除点数，直接引入须再审。
- [Kidono原论文](https://www.aisl.cs.tut.ac.jp/~jun/pdffiles/kidono-iv2011.pdf)：核对候选特征。作者实现213D缩放、协方差/惯性/PCA/切片/强度/OpenCV Boost，需PCL/ROS/OpenCV；模型未加载predict直接true有全部放行风险。本Demo不采用此策略，不宣称原权重已适配IFW强度。
- [PointNet论文](https://arxiv.org/abs/1612.00593)与[官方代码](https://github.com/charlesq34/pointnet)：固定2618f72bc1a0fd21b074096e748016960d44ef55、MIT。核对模型/transform_nets/tf_util/train及AST；原入口实测缺TensorFlow BLOCKED，自己的CPU简化shadow实际运行。ModelNet分类不等同本场景检测。
- [RandLA-Net论文](https://arxiv.org/abs/1911.11236)和[官方源码/许可](https://github.com/QingyongHu/RandLA-Net)：固定6b5445f5f279d33d2335e85ed39ca8b68cb1c57e，CC BY-NC-SA4.0，不当MIT自由商业部署。核对局部聚合/邻域/采样/自定义ops，原入口缺TF BLOCKED；逐点标注及旧算子成本较高，无伪造适配。
- [XGBoost官方接口](https://xgboost.readthedocs.io/en/stable/python/python_api.html)：CPU hist/线程/模型导出核对，原生训练与JS对拍实际完成。

固定源码/许可证/SHA在research及UPSTREAM_AUDIT/RUNTIME，未停于README摘要。

## 测试/隔离/未解决项

PASS：R5合成契约与2605帧对拍、6模型各200概率对拍、RF回退、一对一Tracker单元、原human_core7/7套、Chrome真实seek/reset/play/切换/候选/GT/UNKNOWN、五算法API真实点云/索引。独立另一审查者验收NOT_RUN，自验不ACCEPTED。

脏树已保存9186文件SHA、branch/HEAD、binary patch与4259文件ZIP约8.77GB；ZIP目录可读，全CRC扫描NOT_RUN。结束全树不是PASS：以下5原文件发生外部变化，本轮未写这些路径，保留未恢复/覆盖：

- pc_apps/human_replay/deploy_board.sh
- pc_apps/human_replay/gt_annotator.html
- pc_apps/human_replay/gt_annotator.js
- pc_apps/human_replay/gt_server.py
- pc_apps/human_replay/human_replay_lib.py

生产冻结模块/模型副本及默认复验SHA守卫有效；外部变化不回填历史。本轮无生产覆盖、采集、部署、提交或推送。

剩余：S9有效GT、未标区间和逐候选人工审核、独立人员/家具/场景、静态支路可靠负例、严重稀疏遮挡提案、远动态误确认、GT物理身份独立审核及RK3588实测。当前为可运行研究交付，不是完成现场识别验收。

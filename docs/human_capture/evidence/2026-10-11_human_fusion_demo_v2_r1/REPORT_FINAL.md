# HUMAN-FUSION Demo V2 实际交付

2026-10-11（Asia/Shanghai）。SUBMITTED；软件逐项作者自验通过，S9可信GT/真实骨架资格/整树冻结仍BLOCKED，未ACCEPTED。无部署、生产接入、采集、提交或推送。

## 启动与查看

当前本机服务已运行：[打开 Demo V2](http://127.0.0.1:8798/)。双击 `D:\Code\ldiar\sidequests\human_fusion_lab\start_demo_v2.cmd`；或在仓库根运行 `node sidequests/human_fusion_lab/server_v2.js 8798`。仅监听127.0.0.1，需要本机既有Node和九会话文件。

先选择会话和模型；播放/暂停、上一帧/下一帧、拖动帧条、重置均可用。3D、XY俯视、XZ侧视同步；分层勾选原始点、背景过滤后点、候选、分类着色、GT和轨迹。“聚焦人体/当前候选”可以放大真实人体点。原始点保留原成员，仅统一乘已有研究R/T用于显示，并非已经通过物理验收的坐标。

右侧案例下拉直接跳转35个代表性帧。点击候选行看同点集四模型分数、点数、GT距离、几何支撑和分层诊断。四模型比较均重新从当前候选完整原始行提取51/69维特征；模型切换另触发管线从帧0重放，其保留状态与候选可能改变。检测时间仅含engine.tick，不含四模型对比分数、点云IO、HTTP与绘制，不等于浏览器帧率。

人工标注：暂停→打开圈点→任意视图拖矩形（投影内所有深度点，需3D框进一步裁剪）或填XYZ框选点→选类别/人体编号→保存本帧草稿→下载。可导入或撤销本帧草稿；草稿是raw28B原始行索引，带实际meta/bin SHA与坐标契约，永远不自动成为可信GT。下载后可运行 `node sidequests/human_fusion_lab/annotation_v2.js draft.json NEW-output.json` 校验索引/边界/同帧编号/重叠/源点/绑定并导出新绑定草稿；不能覆盖既有文件。

## 真实运行和代表帧

截图由本机Chrome实际执行V2并通过CDP截取；原始点全部来自captures/remote，未生成模拟点云、未注入检测结果。九会话F0截图：`SESSION_cap_*_F0_03.png`。

[近距成功：打开真实帧](http://127.0.0.1:8798/?sid=cap_20261010_175429&model=xgb69_candidate&index=20)。S3-near f20：1167候选点；同候选RF51原0.980、XGB69约0.998；GT TP1/FP0/FN0。橙轴为表面几何代理，不是人体关节。

![近距成功](SUCCESS_NEAR_F20_03.png)

[遮挡漏检：打开真实帧](http://127.0.0.1:8798/?sid=cap_20261010_180235&model=xgb69_candidate&index=128)。S6 f128：GT人体33原始点→A链最终前景18点→对应候选覆盖0。另一处380点候选与该人体不对应，RF51原约0.88/XGB约0.01；人体漏检与模型分歧同时显示。

![遮挡漏检](PERSON_MISS_F128_03.png)

[家具误检：打开真实帧](http://127.0.0.1:8798/?sid=cap_20261010_175227&model=rf51_baseline&index=20)。S1空场 f20：RF51预测人体，可信家具GT重叠证实误检；同候选XGB拒绝。S1属于训练负样本，不能把此成功拒绝当独立家具泛化。

![家具误检](FURNITURE_RF51_F20_03.png)

S9示例：[f0双人会话](http://127.0.0.1:8798/?sid=cap_20261010_180751&model=xgb69_candidate&index=0)，GT UNKNOWN。见S9_UNKNOWN_F0_03.png；不计算双人GT指标。

## 全帧运行与跨会话验证

九会话共2605帧，两管线18次运行共5210 tick；全部同帧ID唯一，回退/重置后候选/分数/ID确定性复验通过。原21次共享ID缺陷由每轨每帧一对一关联和一次投票修复；V1权重/算法源只读，V2各模型在每个session/segment重置都使用现有UniqueTracker。18次运行明细在cap_*__*.json，原验证日志仍保留最后冻结断言失败。

TP/FP/FN为0.75m XY一对一门下的观测次数，不是独立受试人数。accepted>=0.35；strong>=0.55。UNKNOWN不算负例。非空场缺少完整家具GT，未匹配预测仅称FP，不能统称家具。S9全未知显示“—”，没有可靠0/0/0结论。

| 会话 | 已标 / 未知帧 | RF51候选 TP/FP/FN | XGB候选 TP/FP/FN | RF51轨迹 TP/FP/FN | XGB轨迹 TP/FP/FN |
|---|---:|---:|---:|---:|---:|
| S1-empty-with-furniture | 304 / 0 | 0/604/0 | 0/0/0 | 0/600/0 | 0/0/0 |
| S3-walk-x-near | 258 / 0 | 258/393/0 | 258/19/0 | 256/372/2 | 256/9/2 |
| S3-walk-y-far | 99 / 365 | 99/227/0 | 99/97/0 | 97/211/2 | 97/93/2 |
| S4-walk-stop-walk | 11 / 228 | 11/26/0 | 11/9/0 | 10/22/1 | 10/8/1 |
| S5-turn-in-place | 6 / 196 | 6/6/0 | 6/0/0 | 5/5/1 | 5/0/1 |
| S6-occlusion | 71 / 167 | 64/139/7 | 65/1/6 | 60/137/11 | 61/1/10 |
| S7-far-5m | 12 / 239 | 12/21/0 | 12/1/0 | 11/18/1 | 11/1/1 |
| S8-still-retention-long | 53 / 470 | 53/53/0 | 53/0/0 | 51/51/2 | 51/0/2 |
| S9-two-person-cross | 0 / 126 | — UNKNOWN | — UNKNOWN | — UNKNOWN | — UNKNOWN |

S1 RF51的604个未匹配候选中，566个有>=80%家具点重叠；XGB为0。S6 XGB仍漏6次，确认轨迹仍漏10次。远距/长静止标注稀疏，不能将已标帧召回推广到全会话。训练S1/S3-near/S4/S5；历史验证S3-far；历史测试S7/S8；压力S6；S9 BLOCKED。所有分组来自既有AUDIT/训练记录，历史测试曾被观察。独立未见人员/新场景、独立跨会话家具负样本泛化仍UNKNOWN；本轮没有训练或挑测试参数。

### 相同候选评分对比

下表分别固定RF51和XGB管线生成的当前候选，四模型复评分后累计已标帧GT对照。同组内点集相同；跨组候选和保留状态不同。仅分类评分，无独立跟踪对拍含义。

| 固定候选管线 | 复评分模型 | TP / FP / FN |
|---|---|---:|
| rf51_baseline | rf51_baseline | 503/1469/7 |
| rf51_baseline | rf51_candidate | 487/135/23 |
| rf51_baseline | rf69_candidate | 502/137/8 |
| rf51_baseline | xgb69_candidate | 503/134/7 |
| xgb69_candidate | rf51_baseline | 504/840/6 |
| xgb69_candidate | rf51_candidate | 456/127/54 |
| xgb69_candidate | rf69_candidate | 503/128/7 |
| xgb69_candidate | xgb69_candidate | 504/127/6 |

## 根因与修复边界

- 跟踪：旧FusionTracker逐候选找最近active轨迹，没有claimed集合，会多候选共享ID并多次投票。V2在engine._tick_fusion之前确保使用UniqueTracker，覆盖begin和segment重置，不修改V1/生产。每帧一票、失配0票、寿命及9×2重放验证通过。
- 家具：S1真实候选的几何/高度特征可像人体，原RF51高分；共同候选上的新RF/XGB可拒绝其中大量家具。研究模型看过S1，尚缺独立家具会话负样本验证。不能只降低阈值修复遮挡漏检。
- 漏检：S6 f128为提案层失败，33个GT原始点中18点保留、没有对应候选。rf51 f91为303→55点且无对应候选。当前前景诊断是A链清理/保留后的最终点集，BG与cleanup不能用此字段单独归因。原只读ATTRIBUTION另记录背景/提案失败；见CASE_DETAILS.json，所有推断按实际点支撑限定。
- S9：GT_V1/V2、draft和各备份均绑定aaaa…，meta绑定缺失；无法从现有声明证明人工标签属于当前文件。V2明确拒绝该绑定，并提供新原始行标注+实际双SHA验证，消除新草稿的错误绑定路径。历史可信GT恢复G01仍BLOCKED，需要真实重标/人工重新确认；本轮不伪造GT_V3。

## 骨架实现状态与可观测性

| 层 | 已存在内容 | 当前资格 |
|---|---|---|
| 雷达到地面坐标 | core/leveling.js使用既有R/T；可能来自参考地面，但不是本轮可靠物理标定 | UNCALIBRATED |
| 人体分割 | V1 A/B融合候选及RF/XGB识别，具备真实点索引；家具/遮挡失败保留 | 离线可观察，未生产验收 |
| 人体关键点 | pc_apps/human_limb有17点/6点启发式旧算法，README记录六代真实失败；HR-SKELETON-OFFLINE r1有5–7区域节点和独立时序原型 | 不是不存在算法；已有算法的真人GT效果仍BLOCKED |
| 拓扑连接 | 旧limb_lib有BONES；本V2只连upper/middle/lower三表面带中心 | GEOMETRIC_PROXY_ONLY，非解剖骨架 |
| 姿态与跌倒 | 主线存在相关代码；融合轨迹缺乏有效pose_history，当前演示不输出有效姿态/跌倒结论 | UNKNOWN |

既有skeleton.py normalize/nodes/process/SkeletonTracker代码已核查；既有15项纯数学/合成回归在本轮-W error重跑通过，日志existing_skeleton_tests.log。真实120行先前仍BLOCKED_GT，不把合成测试改成真人效果。旧limb_lib_test仅2个合成人形测试；未在V2执行或复活其失败的人体自动锁定。

可观测性固定抽取每个已标会话首/中/末annotated ordinal，而非按成功帧挑选；OBSERVABILITY.json仅列>=80%PERSON点纯度候选。17个候选支撑176–7587点，P5–P95高度跨度约1.15–1.48m。这表明部分主体表面有足够点支撑粗几何，但不是完整人体身高、不是头/盆骨/手腕可见性证明，点数多也可能混簇。

头部：最高点可能是手/背景，当前没有HEAD可见区域GT，UNKNOWN。躯干：中带重心可输出，但不是胸椎关节；骨盆：下中带仅表面代理，不能命名真实髋关节。四肢：缺左右身份/遮挡可见性/真实关节GT，全部UNKNOWN。不能以高度比例补齐17关节。本轮粗轴不做身份保证、置信概率或姿态/跌倒判断；缺点不输出伪关节。

## 验收、冻结及下一步

最终Chrome 24 条检查通过，包括九次真实会话切换和真实漏检截图；annotation binding 7项拒绝/边界检查通过；设备和物理未运行。软件作者自验不冒充独立复审。首轮浏览器检查在CASES生成前结束，其失败日志保留；第三轮新文件全通过。

全Git清单基线含untracked共9452文件；HEAD 026e06303f60ed1bbe4ddc4d037836db68da6d27 / master。最终核对9451文件，除README授权新增外的原文件变化见FREEZE_FINAL.json。发现下列5个既有文件（4个结果及V1 server.js）在工作期间被其他活动改写，本轮实现没有写它们，也没有还原或覆盖；S01整树冻结BLOCKED。

- docs/human_capture/evidence/2026-10-11_q01_review_r1/Q01_BROWSER_E2E.json
- docs/human_capture/evidence/2026-10-11_q01_review_r1/Q01_FINDINGS.json
- sidequests/human_fusion_lab/results/DEMO_BROWSER_E2E.json
- sidequests/human_fusion_lab/results/UNIFY_REGRESSION.json
- sidequests/human_fusion_lab/server.js

下一步明确任务：

1. 先实际查看成功/遮挡漏检/家具误检三例及九会话，标注工具重标S9关键帧，记录真实人编号/可见性/实际文件双SHA；可信评估仍须重新审阅，新草稿不自动放行。
2. 在新离线工单将S6点损失拆为参考背景→清理→聚类→候选，固定同原始点对比低点数提案或点集保留策略；同时增加独立家具会话负样本，避免靠S1训练集成功宣称修复。
3. 给头/躯干/骨盆及可见四肢画真实区域标签，核地面坐标来源与物理误差，再比较既有5–7区域原型与三表面轴的稳定性；没有可靠标定仍UNCALIBRATED，没有解剖GT仍UNKNOWN。
4. 单独处理外部证据漂移并保存新轮记录；本轮不改回R9/Q01。用户未确认离线检测、骨架及姿态效果前，板端部署、生产替换、现场发布持续禁止。

最终补充：V1 server.js也在工作期间被外部修改。V2不导入server.js，四模型权重、检测/跟踪依赖、生产源、九会话与冻结GT源均与基线相符；本轮没有修复或还原该外部修改。整树冻结S01保持BLOCKED。18次全帧运行、24项浏览器自验、真实截图可独立审阅。

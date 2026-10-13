# W03 人体安全收口研究与最小开发方案（R40，2026-10-07）

**最终状态：REWORK_REQUIRED；SUBMITTED，未 ACCEPTED。** GT 子问题 BLOCKED。当前 pair 的 gate 未过，严格共同门也未过，因此整单不能仅称 BLOCKED_BY_GT。没有生产补丁、registration 接入、W04、骨架、姿态、跌倒或 ML 实施。本轮不重复 R39 的完整 shadow、既有回归或 metric 审计，只解析旧证据、做新的坐标/索引/Tracker/有效性诊断。

## 1. 当前阻断项与证据

| 阻断项 / 现行 ID | 权威结果 | 本轮新增证据 | 解除条件 |
|---|---|---|---|
| clean 安全，T38-05 / S4 | FAIL：31>5；真实语义 UNKNOWN31 | [02_workspace_planes.json](02_workspace_planes.json)，31 行三种高度与裁剪反事实 | 人工点级 GT + 经审查的真实安全修复/契约处理；保持旧31 cohort，不从总数扣除原 P cleanup 的2点 |
| 共同门，T38-06 / S7 | FAIL：非零 cleanup count delta、新 green61/purple70、真人连续性不足 | [03_topology_point_cases.json](03_topology_point_cases.json)，33帧完整候选索引；[Tracker r2](04_tracker_reproduction_and_trace_r2.json) | 严格门保留；补 GT、修复已证实现缺陷后新轮完整验证；解释变化不等于过门 |
| registration 支撑 | 历史 DEGRADED：5938/11959=49.652981%<50% | [05_gate_protocol_review.json](05_gate_protocol_review.json) | 既定协议真实支撑过门；或有独立依据的契约设计另行审查，不让当前 pair 靠改门过关 |
| 当前 artifact 绑定 | R39 当前 loader STALE，SAFE=P 已验证 | 本轮固定输入/code/SHA 对照；未重绑定或调用载入回归 | 未来授权新 artifact 后仍须所有 gate；本轮 SAFE 维持 |
| 输入有效性 BUG-R40-I01 | 新证实：无效零 XYZ 在 JS 配平后变成有效高度点 | [04_zero_xyz_reproduction.json](04_zero_xyz_reproduction.json)，既有 report.invalid_xyz_count 精确对账 | 对齐现有无效点契约；单独授权最小补丁及离线回归 |
| 时序 BUG-R40-T01 / T02 | 新证实：同帧多簇可共用一 track；5票窗口按观测而非帧 | [04_tracker_reproduction_and_trace_r2.json](04_tracker_reproduction_and_trace_r2.json) | 最小共享入口修复及新序列回归；不改变3/5、0.75m、8帧或几何门 |
| 真人 HP02 / 设备 / 物理 | HP02 BLOCKED；设备/物理/部署/采集 NOT_RUN | 不以这对离线数据替代 | 需要后续明确授权和真实证据 |

承接背景残留：WD01 93423→1754（98.1%），WD02 159247→24508（84.6%）。这不是人体识别准确率。102个 WD01 静态期望消失行继续承接区域金标，不重复人工审计；其余155行身份/混合/连续性仍缺 GT。首次03归因已被 R39 r2 supersede，本轮不改变257行既有 primary category。

## 2. 最小人工 GT 计划与格式

已有 [09_point_review.html](../2026-10-07_hrw03_r39_closeout/09_point_review.html) 继续作为唯一主审阅界面；不重写标注工具。当前任务清单 [06_gt_tasks.json](06_gt_tasks.json) 与 [24行优先CSV](06_disappeared_priority.csv) 均为 `source:"diagnostic"`、全 UNKNOWN，并非人工标签。

按优先级执行：

1. **31点、7帧**：f63(18)、65(4)、85(1)、90(2)、99(1)、123(2)、146(3)。每点辨认脚/鞋、下腿、地面残留、人体与地面混合、registration/reference错配或 UNKNOWN。后两类不能当安全 ground；低高度不能自动标 ground。f63/p10660、p12476 原不在 P 输出候选，但保留在安全 cohort。
2. **24个非WD01消失 confirmation 行**：全部逐行见下表。特别先看 f17/20/21/22/23/24/30/31 的参考大比例删除，f104/107 的少量成员变化却证据翻转，f105/146 的点保留而确认票变化。
3. **10 split帧、2 merge帧**：f46/53/55/56/61/152/153/159/160/164；f102/151。标 P/S 各簇 PERSON/STATIC_OBJECT/MIXED/UNKNOWN；对 shared/lost/gained 子集标真实人/物归属；用独立真人 person_id 链接相邻帧，判断 PRESERVED/FRAGMENTED/LOST/STATIC_NOT_HUMAN/UNKNOWN。
4. 优先批去重共 **38个帧**，不是完成所有 GT：其余非静态155行仍需覆盖（97个帧）。green/purple同一对簇可复用一次人工判断，但每个要求ID须保留并明确人工复核，不自动由机器扩散标签。

观察每个关键帧前5帧到后2帧；边界仅看已有帧。153帧原viewer包含全部38个优先帧，但这段邻帧范围缺 f81/82/89/91/142。最小补充方案为在新evidence派生viewer中复用原HTML/JS，仅增加这5个同格式、同绑定帧及manifest入口。禁止用 `leveled_latest` 的另一job替代。该5帧扩展本轮 NOT_RUN；缺上下文时连续性保留 UNKNOWN。

**人工必须完成**点语义、P/S簇语义、是否人/物粘连、两 S子簇是否属于同一真人、真人身份与连续性、错配判断。机器可填 frame/index、point交集、过滤支撑和投票轨迹；不能填 `source:"human"` 或真人身份。不可辨认时允许 UNKNOWN，并记遮挡/密度/视角原因；不能为“补齐”强猜。

旧viewer导出的实际人工文件沿用 `hrw03_closeout_gt/schema:1/source:human/reviewer/created_iso/session_id/artifact_id/source_session/source_leveling/points/confirmations`。points保持31个唯一id和frame/seq/point_index；confirmations保持原行id和P/S track号，旧validator核绑定。但每行旧viewer只有一个pair级label，且split/merge并不都有独立confirmation行，因此它**不能独立表达**P/S分别语义、多真人身份、拓扑子簇关系，也不校验真人person_id。

最小补齐是一个人工 sidecar，见 [06_gt_label_format.md](06_gt_label_format.md)：按 `(frame, branch, cluster_index)` 分别标簇；真人id由人工建立，P/S track_id只作观测字段；按12个拓扑帧逐edge记录子集语义和同一真人关系。先旧 `review_gt.js` 校绑定和枚举，再独立sidecar检查覆盖/索引/身份；旧validator的格式通过不等于GT真实或完整。实际human文件本轮不存在，标注与语义验收 BLOCKED。

| 优先消失行ID | 机械归因 | 原始交集 | P-only对主配对S | S-only | P/S票 |
|---|---|---:|---:|---:|---|
| f17:disappeared:P0:Snull | REFERENCE_ABSORPTION | 0 | 1523 | 0 | [1, 1, 0, 0, 1] → None |
| f20:disappeared:P0:Snull | REFERENCE_ABSORPTION | 0 | 1481 | 0 | [0, 1, 0, 1, 1] → None |
| f21:disappeared:P0:Snull | REFERENCE_ABSORPTION | 0 | 1490 | 0 | [1, 0, 1, 1, 1] → None |
| f22:disappeared:P0:Snull | REFERENCE_ABSORPTION | 0 | 1568 | 0 | [0, 1, 1, 1, 0] → None |
| f23:disappeared:P0:Snull | REFERENCE_ABSORPTION | 0 | 1506 | 0 | [1, 1, 1, 0, 1] → None |
| f24:disappeared:P0:Snull | REFERENCE_ABSORPTION | 0 | 1569 | 0 | [1, 1, 0, 1, 0] → None |
| f30:disappeared:P0:Snull | REFERENCE_ABSORPTION | 0 | 1487 | 0 | [0, 1, 1, 0, 1] → None |
| f31:disappeared:P0:Snull | REFERENCE_ABSORPTION | 0 | 1558 | 0 | [1, 1, 0, 1, 0] → None |
| f37:disappeared:P0:S0 | TRACK_ID_REASSIGNMENT | 90 | 1426 | 2 | [1, 0, 0, 1, 1] → [0, 0, 1] |
| f39:disappeared:P0:S0 | HUMAN_CANDIDATE_LOSS | 196 | 1425 | 29 | [0, 1, 1, 0, 1] → [0, 0, 1, 1, 0] |
| f40:disappeared:P0:S0 | HUMAN_CANDIDATE_LOSS | 343 | 1297 | 78 | [1, 1, 0, 1, 1] → [0, 1, 1, 0, 0] |
| f41:disappeared:P0:S0 | TRACK_ID_REASSIGNMENT | 543 | 1096 | 102 | [1, 0, 1, 1, 0] → [1, 1, 0, 0, 0] |
| f53:disappeared:P0:S0 | CLUSTER_TOPOLOGY_CHANGE | 1454 | 1186 | 5 | [0, 1, 0, 1, 1] → [0, 0, 0, 0, 1] |
| f54:disappeared:P0:S0 | TRACK_ID_REASSIGNMENT | 2005 | 977 | 81 | [1, 0, 1, 1, 0] → [0, 0, 0, 1, 0] |
| f104:disappeared:P1:S0 | HUMAN_CANDIDATE_LOSS | 2766 | 47 | 1 | [0, 0, 1, 1, 1] → [0, 0, 0, 1, 0] |
| f105:disappeared:P1:S0 | TRACK_ID_REASSIGNMENT | 2607 | 0 | 5 | [0, 1, 1, 1, 0] → [0, 0, 1, 0, 1] |
| f106:disappeared:P0:S0 | TRACK_ID_REASSIGNMENT | 2499 | 4 | 4 | [1, 1, 1, 0, 0] → [0, 1, 0, 1, 0] |
| f107:disappeared:P1:S0 | HUMAN_CANDIDATE_LOSS | 2406 | 47 | 1 | [1, 1, 0, 0, 1] → [1, 0, 1, 0, 0] |
| f146:disappeared:P0:S0 | TRACK_ID_REASSIGNMENT | 3293 | 3 | 6 | [0, 0, 1, 1, 1] → [0, 0, 0, 1, 1] |
| f151:disappeared:P0:S0 | CLUSTER_TOPOLOGY_CHANGE | 3280 | 25 | 791 | [1, 0, 1, 0, 1] → [1, 0, 1, 0, 0] |
| f159:disappeared:P0:S0 | CLUSTER_TOPOLOGY_CHANGE | 1414 | 1204 | 44 | [0, 0, 1, 1, 1] → [0, 0, 0, 0, 1] |
| f160:disappeared:P0:S0 | CLUSTER_TOPOLOGY_CHANGE | 1166 | 1263 | 29 | [0, 1, 1, 1, 1] → [0, 0, 0, 1, 1] |
| f161:disappeared:P0:S0 | HUMAN_CANDIDATE_LOSS | 1053 | 1250 | 55 | [1, 1, 1, 1, 1] → [0, 0, 1, 1, 0] |
| f162:disappeared:P0:S0 | HUMAN_CANDIDATE_LOSS | 875 | 1280 | 56 | [1, 1, 1, 1, 1] → [0, 1, 1, 0, 0] |

P-only不能直接叫“删除点”：例如f53的1186包含分配到S1的190，实际退出所有S候选996；f159的1204含转到S1的37，实际退出1167；f160的1263含转到S1的34，实际退出1229。所有真实人体损伤仍待GT。

## 3. workspace 与地面坐标语义

实际离线 S 调用链是 **raw → 绑定source leveling → registration → denoise → workspace → reference → workspace → online → pipeline(denoise/workspace/cleanup/聚类/Tracker)**。leveling在载入阶段完成；P不registration。S的 online 图从registered帧建立，reference图从reference leveled帧建立。`extract_foreground` 每次都裁剪；进入 `pipeline_frame` 后还会裁剪，因此只移动第一处crop不能完成生产修复。

当前 workspace 的 z 是**输入缓冲坐标的z**，PL本身不读取plane/frame tag。在P中是source leveling的地面法向有符号高度；在S中是reference leveling的z，即reference地面高度。二者都只是离线拟合地面，不是已验证世界系/物理地面或安装高度。

源raw拟合平面为 `n=(-0.445671955,-0.006389912,0.895173546), d=1.323191507 m`；reference raw拟合面为 `n=(-0.453288332,-0.051425571,0.889879261), d=1.317114530 m`。各自leveling后均为z=0（数值误差<1e-12）。这些offset/pitch是拟合artifact值，不是现场安装测量；历史“约26°”不升级为已测角度，约1.1m光学窗口高度也不升级为点云原点高度。

源leveled面经固定registration后，在reference系变成：

`0.004919103837*x + 0.030495900678*y + 0.999522787364*z + 0.001184604929 = 0`。

一般平面变换规则为 `n' = R*n, d' = d - n'·t`。平面倾斜 **1.770153°**，因此不能只看 t_z=-0.132mm来判断高度影响；x/y旋转项在这些点处占主要差异。reference面仍z=0，源原平面与其变换后平面是同一个几何面，不能把不同坐标表示误当两个物理地面。

31点位置：transported source面在registered XY处 z=-24.565…-1.353mm，reference面为0；两面竖向差 **1.353–24.565mm**。点的reference有符号高度比source高度低 **1.305–24.508mm**；transported signed height与source z一致到1e-7m。平面差与点高度差因法向不同而略有区别，不能混为一值。

**结论**：S直接使用reference z阈值符合已冻结“reference坐标系”契约，未发现矩阵/方向错误；但它不能保持source拟合面以上同样的高度安全带。这里有可复现的参照不等价，尚不能裁决reference面更真实、source面更真实，或31点应当删除。不能直接称生产bug、正确地面消除或人体安全修复。

只读反事实保持R/t、阈值与当前S图：source面crop提前或使用transported source signed height，30点全改变workspace决策；其中f63/p10660和p20496仍有reference命中，另f63/p12476本来就是reference删除。**28点仅在固定图、cleanup前的单次反事实中可能保留**。未建立对应新online图、未改后续重复crop、未跑反事实cleanup/Tracker，不能称28点已找回或T38-05已过。若GT表明脚腿受损，再审查高度参照契约；不能通过挪z阈值修复。

| frame/point | source面高度(m) | reference面高度(m) | transported地面z(mm) | 潜在reference命中 | 人工标签 |
|---|---:|---:|---:|---|---|
| 63/p10660 | 0.103613 | 0.087596 | -16.066 | 是 | UNKNOWN |
| 63/p12476 | 0.290433 | 0.279997 | -10.575 | 是 | UNKNOWN |
| 63/p16671 | 0.111784 | 0.089889 | -21.948 | 否 | UNKNOWN |
| 63/p16696 | 0.109510 | 0.087353 | -22.209 | 否 | UNKNOWN |
| 63/p16708 | 0.108501 | 0.085468 | -23.085 | 否 | UNKNOWN |
| 63/p16796 | 0.118220 | 0.097232 | -21.044 | 否 | UNKNOWN |
| 63/p16816 | 0.114411 | 0.092162 | -22.303 | 否 | UNKNOWN |
| 63/p16832 | 0.120505 | 0.097425 | -23.138 | 否 | UNKNOWN |
| 63/p16980 | 0.117385 | 0.092876 | -24.565 | 否 | UNKNOWN |
| 63/p18314 | 0.100566 | 0.095723 | -4.892 | 否 | UNKNOWN |
| 63/p18350 | 0.101856 | 0.094820 | -7.084 | 否 | UNKNOWN |
| 63/p18668 | 0.114492 | 0.094751 | -19.795 | 否 | UNKNOWN |
| 63/p18672 | 0.116419 | 0.096459 | -20.015 | 否 | UNKNOWN |
| 63/p20273 | 0.106968 | 0.099300 | -7.719 | 否 | UNKNOWN |
| 63/p20338 | 0.101909 | 0.097760 | -4.198 | 否 | UNKNOWN |
| 63/p20440 | 0.100765 | 0.088870 | -11.943 | 否 | UNKNOWN |
| 63/p20484 | 0.106103 | 0.091127 | -15.027 | 否 | UNKNOWN |
| 63/p20496 | 0.108272 | 0.092447 | -15.876 | 是 | UNKNOWN |
| 65/p16476 | 0.105108 | 0.095721 | -9.437 | 否 | UNKNOWN |
| 65/p18182 | 0.103260 | 0.099039 | -4.271 | 否 | UNKNOWN |
| 65/p18317 | 0.100286 | 0.095771 | -4.563 | 否 | UNKNOWN |
| 65/p20213 | 0.101285 | 0.097680 | -3.653 | 否 | UNKNOWN |
| 85/p20338 | 0.100512 | 0.096359 | -4.201 | 否 | UNKNOWN |
| 90/p20185 | 0.101854 | 0.099942 | -1.961 | 否 | UNKNOWN |
| 90/p20313 | 0.100809 | 0.098722 | -2.135 | 否 | UNKNOWN |
| 99/p20190 | 0.100022 | 0.097669 | -2.401 | 否 | UNKNOWN |
| 123/p18262 | 0.101297 | 0.099992 | -1.353 | 否 | UNKNOWN |
| 123/p20198 | 0.101337 | 0.098421 | -2.965 | 否 | UNKNOWN |
| 146/p16142 | 0.102052 | 0.098160 | -3.941 | 否 | UNKNOWN |
| 146/p16233 | 0.101567 | 0.099779 | -1.837 | 否 | UNKNOWN |
| 146/p16262 | 0.101871 | 0.098261 | -3.658 | 否 | UNKNOWN |

## 4. 关键拓扑与track案例

逐点全集、几何、cleanup前后支撑、票与候选距离见 [03_topology_point_cases.json](03_topology_point_cases.json)。全部33个选定帧重建的raw-index overlap与旧证据逐值一致；其余165帧只重放已有候选特征来追踪Tracker，不重跑cloud完整管线。两分支165个active Tracker快照全部与保存输出一致。

| frame | 拓扑 | 原始point index交集 | 真人语义 |
|---|---|---|---|
| f46 | split | P0→S0:633; P0→S1:49 | UNKNOWN |
| f53 | split | P0→S0:1454; P0→S1:190 | UNKNOWN |
| f55 | split | P0→S0:1977; P0→S1:354 | UNKNOWN |
| f56 | split | P0→S0:2240; P0→S1:417 | UNKNOWN |
| f61 | split | P0→S0:3128; P0→S1:567 | UNKNOWN |
| f102 | merge | P0→S1:557; P1→S0:2865; P2→S0:22 | UNKNOWN |
| f151 | merge | P0→S0:3280; P1→S0:587 | UNKNOWN |
| f152 | split | P0→S0:3125; P0→S1:578 | UNKNOWN |
| f153 | split | P0→S0:2775; P0→S1:504 | UNKNOWN |
| f159 | split | P0→S0:1414; P0→S1:37 | UNKNOWN |
| f160 | split | P0→S0:1166; P0→S1:34 | UNKNOWN |
| f164 | split | P0→S0:594; P0→S1:49 | UNKNOWN |

- **f17及f20–31：可能的结构损失，不能仅称历史票差。** f17 P0 n=1523、h=1.239m、radius=.376m，S无可分类簇；1407reference删除、20crop、31online、2cleanup，另63点仍在S cleanup后但未成可分类簇。reference删除含低带36、中带1271、高带100（以source z分带）。原始高点也被删除，不能用“都近地”解释。这些簇可能是静态物/混合/真人；非WD01不等于真人。
- **f55：去粘连候选，亦可能同一人体碎裂。** P0 3190点、半径.543m硬门不过；S0 1987点/半径.252m，S1 454点/半径.319m，两侧瞬时CONFIRMED_HUMAN但当帧track尚未confirmed。P0→S0 shared1977、→S1 shared354；例如S0索引16931/16975/16979，S1索引21199/21348/23259，全集在JSON。仅变换原P候选点的Q分支不split，而实际S出现两支，成员筛选参与拆开；是否人/物去粘连必须人工判断。
- **f104/f107：少量点改变结构证据。** f104 P1 n2813→S0 n2767，共享2766；21reference删除，26点仍在cleanup后但未达候选支持；spread_cv .31693→.12099，HUMAN_SHAPE→SOLID_UNIFORM，joint确认消失。f107 shared2406，reference11/crop1、另35未成可分类簇，cv .46699→.08926。这证明证据敏感，不证明删除人体点或有新实现bug；不得调证据门来掩盖。
- **f105/f146：点保留但确认票变化。** f105共享全部2607个P候选点、S多5点；当前joint从HUMAN_CANDIDATE变CONFIRMED_HUMAN，P历史3票而S2票，故旧confirmation消失，不是点云消失。f146共享3293/3296，仅3crop、S多6点；P/S本帧joint均确认，票[0,0,1,1,1]→[0,0,0,1,1]。f65两边P0/S0本帧均NON_HUMAN，P2票/S3票仍能产生“new green”；harness的green只是track_confirmed，不等同UI真人绿色。
- **f151：网格重分箱即可merge。** P0 n3305、P1 n687；S0共享3280+587点，新增204点，n4071；半径由P0 .263m增至S .827m，宽深/直立度门失败。固定变换、只把P输出候选点重新分进现有0.15m XY 4邻网格、无删点的诊断Q，已经出现merge。故不能把此merge归为“背景删除导致去粘连”。它是网格不旋转不变的可复现事实；是否真人与家具粘连、两人合并或静态合并仍未知。
- **f102：小重叠也算merge。** S0保留全部P1的2865点，同时接纳P2的22点，占S0仅0.759%；旧any-shared-point定义仍算merge，不能据此报真人融合。S0 cv .12686，原P1 .26257，少量结构/成员变化即可改变证据。不得事后设置overlap比例来删除现有merge记录。
- **f159/f160：碎片样本必须人工查。** P0分别shared1414/1166到主S0，37/34到小S1（n63/65）；P0 reference删除1109/1163，覆盖中高带，不全近地。小S簇可能人/物/混合，不能直接称人体fragmentation或家具去除。

[03_topology_stage_decomposition.json](03_topology_stage_decomposition.json) 的Q只变换原P输出候选点，不增删点、不重跑cleanup；按同一raw index展示grid-only边。f102/152/159/160在Q本身有split；f151有merge；f164有Q merge但实际S split，说明最终topology是重分箱与成员筛选共同作用。Q是**候选子集诊断**，不含原P低于候选门的小分量；U也只覆盖两侧候选的逐点上下文，不能用它取代旧完整cleanup审计。原cleanup自身split/merge=0继续成立；簇数下降与split是不同现象，严格delta==0仍失败。

### 新实现缺陷（已复现，仅登记方案）

**BUG-R40-T01：同帧track复用。** `Tracker.tick`按候选顺序贪心，既更新位置又允许后续候选再次选择同一track，包括本帧新建track；votes/pose_history按每簇push。实际S/f46：S0和S1均分给track3，匹配距离.07036m、更新后的.66665m，追加两次0票；该实际帧没有新增正确认，不能把所有新增confirmation归因于此。合成repro在年龄3时一帧三个正簇能达到3票，只有一个正帧却confirmed。S/f53仅反转当帧候选顺序，S1从新track4变为既有track3，显示assignment身份敏感；原P反序多数仅新ID编号差，不能当真人身份切换。

**BUG-R40-T02：窗口没有按帧过期。** 空帧不追加0也不清旧票；5票=5观测。最小repro在f0/f1正、f2–8空、f9正，会确认，但f5–9只有1个正帧。真实S track4/f61观测帧[53,55,56,61]、票[0,1,1,1]已确认，而f57–61只有f61一票；与f61/63/64/65/66等变化行关联可查。机械关联不等于复跑修复后的因果统计，也不提供真人GT。

**BUG-R40-I01：无效零XYZ转换不一致。** `leveling.py:freeze_domain/export_dataset`均明确将nonfinite或全零XYZ当无效并保持原记录；`registration.loadFrames`与浏览器`human_detect.load_sid/apply_Rt`、`replay.apply_Rt_inplace`却无条件变换。source1250003 / reference778477 个全零XYZ分别等于既有report.invalid_xyz_count；大多数intensity并不为0，不能用intensity0过滤。原[0,0,0]被PL.denoise排除，配平后[0,0,1.3231915]却通过denoise/workspace。源gate样本i0正由全部1250003点平均而来，对应reference同类虚点、normal无效；仅占一个fine样本，不能把125万当支撑缺口或独立样本。这是数据有效性缺陷，不代表它解释全部378个无normal、或修复即可补70raw pair。

受影响入口、最小方案和最小repro见 [08_bug_and_patch_design.md](08_bug_and_patch_design.md)。未修改PL、Tracker、registration或leveling。

## 5. gate协议审查

现行定义与实现都使用trim后覆盖，并没有把raw覆盖误算成49.65%。`inlier_ratio`名字容易误读，但R3.7定义已写n_correspondence/n_static_source；不能用raw82.754%替换它后宣称PASS。

| 协议层 | 数值 | 意义 |
|---|---:|---|
| fine source / target / 有normal target | 11959 / 17053 / 15537 | fine样本，非原始点/独立观测数 |
| raw有效pair | 9897（82.754%） | 0.08m内最近target且normal有效，source可重复指向target，不是双射 |
| 无球门target / 最近target无normal | 1684 / 378 | 与raw互斥的求解输入状态，物理原因未定 |
| 60%trim保留 / 剔除 | floor(9897*.60)=5938 / 3959 | 根据绝对point-to-plane残差排序截断 |
| 现行覆盖 | 5938/11959=49.652981% | gate<50%，WARN |
| 达门支撑 | keep至少5980，raw至少9967 | 保持60%trim需增42keep/70raw |
| 60%trim的理论覆盖上限 | floor(11959*.60)/11959≈59.9967% | 50%门并非逻辑不可能，隐含raw覆盖至少约83.34% |

**分别裁决**：实测支撑不足=已证；命名/协议透明度不足=设计事项；reference/fine/normal覆盖问题=已测但物理归因未知；动态污染、遮挡、FOV、离散化、真实地面差=尚未证明。2062无效pair中813近coarse occ≥.5、410在.30m内也无coarse，桶不能随意相加；扇区5支撑明显弱，但不等于已证遮挡。nearest-invalid-normal不能自动跳到另一个target法向，也不能改normal半径凑pair。

fit p50 .014522m是0.30m查询下11056个匹配样本的条件残差；支撑门是0.08m查询+trim。好残差与覆盖不足不冲突。另有文本“最终接受迭代”与实现差异：`measure`在冻结B处重算trimmed point-to-plane pair，而不是保存B的point-to-point solver最后迭代集。R39诊断与该实现一致，未发现算数bug；应让协议文字准确指向测量集。

只提交设计建议：未来有独立多pair/错误变换/真人安全标签依据时，显式记录raw_valid_correspondence_ratio、trimmed_support_ratio、source/targetnormal count、半径、trim、分母有效性、重复target量、空间与平面支撑，并给profile校准来源。明确50%针对哪一类覆盖，不耦合成不透明单名。当前50%/60%都保留、不发布profile、不变换解、不挑样本；原artifact和绑定仍不变。PROVISIONAL六项没有独立多pair安全标定支撑，不能因当前pair接近门就升版放行。

## 6. 按优先级排列的最小开发方案

所有生产补丁均是**审查草案，待另行明确授权**；本轮已完成的是研究/repro/任务清单。各项独立，不捆绑重构。

| 优先级 / 方案 | 前置 | 最小改动范围 | 必要回归 | 停止条件 |
|---|---|---|---|---|
| P0 GT补齐 | 人工reviewer、绑定输入保持 | 原viewer人工导出；小sidecar分别P/S语义和person_id；必要时新evidence仅补5邻帧 | 31点/155行/12拓扑帧覆盖、错SHA/seq/index拒绝、缺标签保持UNKNOWN；人工语义核对 | 脚腿/混合损失或真人LOST/FRAGMENTED即安全问题未闭合；UNKNOWN不能改成ground；优先38帧完成不算155行全部完成 |
| P1 I01无效XYZ保留 | 既有invalid契约及repro已齐；生产修改需授权 | 共享最低变换入口保留全零/nonfinite XYZ与原索引；核同类浏览器载入入口；不改R/t、denoise半径或leveling拟合 | [0,0,0]、nonfinite、非零含0分量、intensity非零、28B附带字段/point id；有效点变换逐位一致；图/支撑影响单独新轮审计 | 需要更改数学/原始数据/扩大过滤语义则停；不得自动重绑定artifact；修复后gate仍要原门 |
| P2 T01单帧一对一 | 已证repro、f46/f53；生产修改需授权 | PL.Tracker.tick内每tick used set：已用含新track不再匹配；保留现有候选顺序/最近邻/EMA和门，不引入Hungarian | 同帧三正簇不能给一track三票；每track每帧最多一次pose/vote；f46/f53诊断、单人正常序列；前景/几何逐位保持，Tracker差异单列 | 真人GT身份冲突未解决或想用新分配器/调track门时停；修复不自动解释所有原confirmation |
| P3 T02按帧计票 | 原声明3/5帧与真实f61/repro；先T01；生产修改需授权 | tick共享入口记录frame_idx并按最近5帧过期；缺观测不保留过时正票；不要改3/5/年龄/8lost | f0/1/9仅1近期正不确认；连续3/5原行为；长gap/相同帧/倒退帧确定失败或明确reset协议，浏览器seek入口单独测 | 重复/倒退帧没有明确生命周期规则则停，不顺带改Fall；新增人工确认风险则停止放行 |
| P4 高度参照安全方案 | 31点GT完成，确认哪种面语义要保留；契约审查和生产授权 | 先保留reference系约定；若要source-height，必须显式height reference贯穿online builder、两次extract与pipeline crop；reference图自己的参照另列，不只改第一处 | 三平面恒等、31逐点、边界/非finite/绑定、旧PIPE不变；固定图反事实与真实重建图分开；T38-04/05/06完整新轮 | GT显示只是地面残留则不为凑数改坐标；source规则仍reference吞脚/混合则停；当前31>5不得扣cohort换PASS |
| P5 topology方案 | P/S每簇及edge真人GT，先排I01/T01/T02 | 默认不改聚类。若真人merge/split已证，先诊断固定网格变换与成员筛选，另提交单问题方案；不能现在改matcher/聚类/人体门 | raw index守恒、f55/102/151/159/160与真人identity、原严格T38-06；无GT不能算FN/FP | 仅机器候选拓扑不足以修复人体；需改PIPE/半径/聚类即超本轮，停在方案 |
| P6 gate契约与支撑设计 | 前序安全问题闭合、输入有效性清楚；独立数据/场景依据 | 仅文档设计：分清raw/trimmed及法向/空间支撑，保留v1数值；新profile仍不发布 | 对既有11959样本逐项恒等；独立留出pair未来验证，错误变换拒绝；T37/T38原门再验 | 50%仍不足就DEGRADED；新定义仅为当前pair翻PASS则拒绝；无独立依据停止设计升级 |

T01/T02是现有声明语义的缺陷修复候选，不引入新的确认门；但用户本轮禁止修改Tracker，所以只提供方案。I01属于原始有效性保留，不能把它当“移动denoise到raw”的借口：后者会改变全部距离窗语义。P4不是已批准补丁，若确证脚腿损失且不能在冻结范围内安全处理，就继续保留SAFE=P。

## 7. 现行验收与本轮执行记录

唯一验收表仍[R3.7 06_test_matrix.md v1](../2026-10-07_hrw03_r37_productionization/06_test_matrix.md)，SHA `70c82e401d0e4055ad85e1bef847d82dd32e718d682533ff25f22a24ac1f9b18`。逐ID本轮状态在 [07_acceptance_status.json](07_acceptance_status.json)：T37/T38全为NOT_RUN（不重复旧回归/整链），旁列R39承接PASS/FAIL；T38-05/06既有FAIL仍有效。设备/物理/部署/采集、T39-01–08、W04以后均NOT_RUN；实际human GT BLOCKED。

本轮baseline、整目录读取、02研究、03跟进、报告生成各有 `*.run.json/*.stdout.log/*.stderr.log`，真实exit均0；这是诊断执行成功，不是现行安全门PASS。原evidence目录293文件/1,257,292,336字节完整读取，其中大型JSON与viewer数据按完整JSON解析，首次03只承接superseded身份；清单 [01_evidence_read.json](01_evidence_read.json)。分支master/HEAD cfbb80c57508be1a0435fdb92260f698dc763934；全树含untracked/ignored基线及source/input/参数SHA见00文件。

诊断工具初次collisions.final_votes保存了可变数组引用，显示后期票；03跟进由不可变旧frame快照校正为r2，f46实际全0票。旧工具输出保留、r2为当前，逐步assignment trace与合成repro没有该问题。这不涉及生产代码修复或旧R39归因改写。

最终 [09_integrity.md](09_integrity.md) 检查本轮源码与输入/history SHA不变及return仅追加；范围外并发变化保留。ponytail实读 `C:/Users/30680/.codex/skills/ponytail/SKILL.md`（full），复用现有PL/registration数学与viewer、stdlib，无新依赖，无并行writer。

## 8. 现在可做与依赖GT的事项

**现在可做**：使用既有viewer人工审31点及24行/12拓扑帧；审查已交付的三类缺陷repro与最小补丁；审查gate指标文字/输入有效性；准备小sidecar与缺5邻帧。I01/T01/T02的根因证明不依赖真人GT，但实际生产实施未在本轮授权。

**依赖GT**：人体是否受伤害；P/S簇属于谁；去粘连还是同人体碎裂；真人continuity；哪一种crop参照适合安全要求；任何人体保留改进是否可称有效。GT完成后仍需严格T38-05/06与支撑gate通过，必要契约变化须单独审查。先证明背景删除没有伤害人体，再考虑识别能力；当前保持 REWORK_REQUIRED。

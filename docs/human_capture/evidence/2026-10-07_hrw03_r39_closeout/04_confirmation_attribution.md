# Confirmation 变化归因（当前为 r2）

现行逐行证据：[03_confirmation_attribution_r2.json](03_confirmation_attribution_r2.json)，257 行；首次 [03_confirmation_attribution.json](03_confirmation_attribution.json) 保留为 superseded。初次诊断把7个参考删除占主导的行因同时有1–4点 cleanup 标成 CLEANUP_SIDE_EFFECT；r2纠正为 REFERENCE_ABSORPTION，并补两分支逐帧 track 历史/票。首次 refinement 断言误填267而实际257，退出1日志保留；修正计数断言后 exit0，不改任何实验输入/管线。

严格复现 R38 原行集合：new green 61、new purple 70、disappeared confirmed track 行126、missed events0。green=track_confirmed；原 harness purple=joint==CONFIRMED_HUMAN，**并非 UI 的紫色 HUMAN_CANDIDATE**。这些是逐 frame-cluster 行，可重叠，不是人数。

| primary attribution | 新 green | 新 purple（原命名） | 消失 confirmation |
|---|---:|---:|---:|
| STATIC_REMOVAL_EXPECTED | 0 | 0 | 102 |
| CLUSTER_TOPOLOGY_CHANGE | 2 | 11 | 4 |
| TRACK_ID_REASSIGNMENT | 20 | 1 | 6 |
| HUMAN_CANDIDATE_GAIN | 39 | 58 | 0 |
| HUMAN_CANDIDATE_LOSS | 0 | 0 | 6 |
| REFERENCE_ABSORPTION | 0 | 0 | 8 |
| CLEANUP_SIDE_EFFECT | 0 | 0 | 0 |
| UNKNOWN | 0 | 0 | 0 |

green 总行数 P132→S67，净-65；purple P152→S85，净-67。新增与消失不等于净delta，也不等于 FP/FN。

## 家具和人体候选分别发生了什么

102个消失行的 P cluster 位于已登记 WD01 静态区域，且有 reference 删除支撑，可解释为 STATIC_REMOVAL_EXPECTED（区域金标，不伪造每点标签）。其余24消失行是 reference absorption8、candidate loss6、topology4、track history6；其真实人/物/混合语义未验证。

新增 green 的39个 candidate gain 记录几何门/证据变化；20个 track-history 行记录跨独立 Tracker 的id与确认票变化；2个 topology 行由原始点交集支持。新增 purple：58 candidate gain、11 topology、1 history。**静态残留变少同时改变了非 WD01 候选拓扑与时序，不能仅称“家具清掉了，真人无损”。**

例 f65/P0→S0：两侧 instantaneous joint 均 NON_HUMAN，但 P votes=2/5、S=3/5，故 S track_confirmed=true；不是本帧新确认了一个已知人。f146：共享3293点，仅损失3点，但 P votes=3、S=2，confirmation 消失主要是历史差异，不能叫人体点云消失。id数值不可跨分支互认。

## Topology 与 cleanup 要分开

跨 P/S 输出可分类簇（raw候选先≥3 XY cells，再n≥60）的原始点 overlap graph：884→230 frame-cluster，总计 split10、merge2、disappeared662、appeared0。split是一个P集合与多个S集合分享原始点；不是独立 GT 人体分裂数量，662大多是背景簇移除但不能全自动贴静态语义。

split帧：f46/53/55/56/61/152/153/159/160/164；merge帧：f102/151。f55 P0共享1977点到S0、354点到S1；需要人/物/混合标签来区分去粘连和人体 fragmentation。边、点数比例、形心和几何保留于06 topology.frames。

**cleanup自身实际 split=0/merge=0**，通过同XY key集合对照核实；然而过滤后簇数 delta 并非全0：P69帧减少89簇，S128帧减少230簇，原component整体移除或缩至固定3格候选门以下。对应 `05_cleanup_attribution.json`，它不是 source→registered 的10次跨分支split。旧 T38-06/S7 的严格 delta==0 与无新增确认门仍 FAIL，未偷换为“delta≤0 即 PASS”。

## 缺少的 GT

机械 primary category 已覆盖全部257行，category UNKNOWN=0；但非静态区域的155行真实身份/混合与人体连续性仍 UNKNOWN，这是关键 GT UNKNOWN。需要标这些行的 P/S cluster 是人/物/混合，并标真人 track 是否 preserved/fragmented/lost；P ids={1,20}、S ids={3,4,5}，缺簇时为null。优先24个非 WD01消失行和10个split帧。完整帧列表：

`17,20,21,22,23,24,30,31,37,38,39,40,41,53,54,55,56,57,61,63,64,65,66,67,68,69,70,71,72,73,74,75,76,77,78,83,84,85,86,87,88,93,94,95,96,97,98,99,100,101,102,103,104,105,106,107,108,109,110,111,112,113,114,115,116,117,118,119,120,121,122,123,124,126,128,129,130,131,132,133,134,135,139,141,143,144,145,146,147,148,151,152,159,160,161,162,164`

缺标签时不能声称“无系统性真人破坏”。与31点标签一起从 viewer 导出 `source:"human"` 格式；绑定原session SHA、leveling job、artifact id，始终保留 UNKNOWN 选项。


# R02 实物与结果（完整实跑，独审前事实账）

D04 frozen候选/terminal逐帧对拍一致；base/A06/split各9会话2605帧，退出码0。原D05缺验收ID、AB artifacts和完整demo独审证据；保留旧失败账，不将旧 return作为完成证明。独立代理已经核对27ledger、7815行与33加载源码SHA。

| 会话 | GT PERSON | base observed TP/FN | A06 | split | split主因 |
|---|---:|---|---|---|---|
| cap_20261010_175227 | 0 | 0/0 | 0/0 | 0/0 | {} |
| cap_20261010_175429 | 258 | 111/147 | 184/74 | 184/74 | {'human/7_ASSOCIATION_CONFIRMATION': 2, 'human/OBSERVED_STRICT_MATCH': 184, 'human/4_MIXED_COMPONENT': 55, 'human/2_BG_UNKNOWN_LOSS': 17} |
| cap_20261010_175553 | 99 | 14/85 | 20/79 | 67/32 | {'human/7_ASSOCIATION_CONFIRMATION': 2, 'human/OBSERVED_STRICT_MATCH': 67, 'human/4_MIXED_COMPONENT': 30} |
| cap_20261010_175804 | 11 | 3/8 | 9/2 | 10/1 | {'human/7_ASSOCIATION_CONFIRMATION': 1, 'human/OBSERVED_STRICT_MATCH': 10} |
| cap_20261010_175943 | 6 | 0/6 | 4/2 | 4/2 | {'human/2_BG_UNKNOWN_LOSS': 2, 'human/OBSERVED_STRICT_MATCH': 4} |
| cap_20261010_180235 | 71 | 7/64 | 10/61 | 10/61 | {'human/7_ASSOCIATION_CONFIRMATION': 1, 'human/OBSERVED_STRICT_MATCH': 10, 'human/4_MIXED_COMPONENT': 53, 'human/2_BG_UNKNOWN_LOSS': 7} |
| cap_20261010_180337 | 12 | 5/7 | 7/5 | 7/5 | {'human/4_MIXED_COMPONENT': 5, 'human/OBSERVED_STRICT_MATCH': 7} |
| cap_20261010_180557 | 53 | 51/2 | 51/2 | 51/2 | {'human/7_ASSOCIATION_CONFIRMATION': 2, 'human/OBSERVED_STRICT_MATCH': 51} |
| cap_20261010_180751 | 0 | UNKNOWN/UNKNOWN | UNKNOWN/UNKNOWN | UNKNOWN/UNKNOWN | {} |

恢复点/new accepted/人工支持分别在COMPARISON每场point_totals、FRAME_COMPARISON逐帧记录。整帧前景不代替人体保留。UNKNOWN不当人体，未标注帧仍UNKNOWN。S9始终INVALID_BINDING。

f238 base已产生p=.983高分确认候选，coverage=.492/purity=.323失败；A06/split coverage=.964/purity=.968通过。恢复点有人工支持的720/净BG恢复757，不能把其它37点叫真人。

far split legacy confirmed FP协议计数105→188（相对A06），人工覆盖不足，其它输出不能全部叫家具；保留原账不抹平。家具human accepted overlaps1/5、propagated351/1515，缺独立负例资格；纯家具高分仍存在。occl legacy TP65→64/FN6→7相对base为保留回退。

纯算法计时：Windows Node；9×3串行，前5热身，tick范围不含读取/渲染/trace/shadow，bank序列化在计时外。原<50ms门不改。
- cap_20261010_175227 base: p95=30.182ms PASS
- cap_20261010_175227 a06: p95=31.614ms PASS
- cap_20261010_175227 split: p95=30.843ms PASS
- cap_20261010_175429 base: p95=29.958ms PASS
- cap_20261010_175429 a06: p95=36.533ms PASS
- cap_20261010_175429 split: p95=36.721ms PASS
- cap_20261010_175553 base: p95=43.932ms PASS
- cap_20261010_175553 a06: p95=52.926ms FAIL
- cap_20261010_175553 split: p95=55.693ms FAIL
- cap_20261010_175804 base: p95=36.539ms PASS
- cap_20261010_175804 a06: p95=41.003ms PASS
- cap_20261010_175804 split: p95=41.550ms PASS
- cap_20261010_175943 base: p95=32.237ms PASS
- cap_20261010_175943 a06: p95=43.145ms PASS
- cap_20261010_175943 split: p95=45.546ms PASS
- cap_20261010_180235 base: p95=32.149ms PASS
- cap_20261010_180235 a06: p95=41.796ms PASS
- cap_20261010_180235 split: p95=45.284ms PASS
- cap_20261010_180337 base: p95=45.999ms PASS
- cap_20261010_180337 a06: p95=173.677ms FAIL
- cap_20261010_180337 split: p95=170.302ms FAIL
- cap_20261010_180557 base: p95=32.687ms PASS
- cap_20261010_180557 a06: p95=33.911ms PASS
- cap_20261010_180557 split: p95=34.002ms PASS
- cap_20261010_180751 base: p95=37.375ms PASS
- cap_20261010_180751 a06: p95=71.600ms FAIL
- cap_20261010_180751 split: p95=73.227ms FAIL

跟踪first仅首次有GT支持的严格观测，不是全片段首次确认；coast最长lost2、重复ID0不证明连续未标区身份正确。seek/重复/逆序/gap/reset/跨会话真实契约exit0；无合格退出参照，退出残留结论BLOCKED。保留银行timeout180s/maxlost30，不将其等同预测lost2；家具可以反复确认续命，尚未修复。

Demo真浏览器9会话、SHA、mouse drag f184、play/pause到f28、step/reset/end-seek、turn/occl/furniture/f238均记录BROWSER_OPERATIONS_V2与截图。旧Demo误标D03为D04已实证；新Demo确用D04 frozen。新R04 Demo另修异步加载清窗与人工参照区域投影。

失败方向：旧B/C/ABC没有超过A06的正式收益，不自动选复杂组合；R02密集核心分离有收益但剩余far32FN/occl61FN/turn2FN。未归咎传感器极限。

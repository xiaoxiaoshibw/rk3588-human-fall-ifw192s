# DET-04 唯一验收表 v1（2026-10-08）

授权：本轮用户 DET-04 指令；[预注册计划](DET04_PLAN.md)。状态仅作者自验；初始未执行均 NOT_RUN，缺资源 BLOCKED。完成后逐 ID 追加最终证据，执行 PASS 不等于识别可用或 ACCEPTED。

| ID | 要求 | 初始状态 |
|---|---|---|
| S01 | 指定 worktree/唯一 writer；full ponytail 实际路径；先阅读/当前基线/计划/表后实现；主树只读及资产3211口径 | NOT_RUN |
| A01 | 已有 artifact 同类审计/复用；4固定B帧×2同扫描counts删除；相交柱张量/计数/ID/编码逐值冻结，删除canvas零；地面带先声明 | NOT_RUN |
| A02 | base/context_points/context_pillars 对照；local/containing/final/global分列；条件归因/地面效应/解释冲突边界 | NOT_RUN |
| B01 | 全506配对、7高度带、两柱计数口径、头差与上带增益分会话描述相关；零新前向，无显著性宣称 | NOT_RUN |
| C01 | 215643 B两/E五负例全保留；逐柱计数/选点z与first32/源ID/完整local anchor变化集；覆盖与anchor分开归因 | NOT_RUN |
| F01 | empty17/35/53全场赢家与四真人local赢家并列；结构支撑柱/footprint/源ID/高度带；单模板不报误报率 | NOT_RUN |
| T01 | python -B -W error 现有test_experiment.py与新冻结/零counts/地面边界回归通过；不改阈值/容量/强度/z/权重 | NOT_RUN |
| R01 | 新编号日志含失败、rows/config、相对本轮baseline代码diff、artifact索引与逐文件SHA、大数组新忽略目录；18完整性/消费资产变化清单 | NOT_RUN |
| R02 | 回传append/README顶部同步、逐ID与技能路径、结论边界、三选一及各自授权需求；SUBMITTED不自行ACCEPTED | NOT_RUN |
| E03 | 固定上游原生ATen完整运行等价；继承DET-03资源限制，不以自检替代 | BLOCKED |
| G01 | 上游GPU逐值等价；本轮不启动等价轮 | BLOCKED |
| L01 | 人体点/框GT、人工标注及物理标定；本轮明确不做 | NOT_RUN |
| D01 | 设备/网络/驱动/部署/采集/生产；本轮明确不做 | NOT_RUN |


## R1 最终作者自验（2026-10-08，SUBMITTED）

|ID|作者自验|证据|
|---|---|---|
|S01|PASS|00 baseline / plan / acceptance / 18 integrity|
|A01|PASS|01 audit / 06 deletion / 10 independent tensor-ID checks|
|A02|PASS|06 comparisons / 07 attribution / full metric table|
|B01|PASS|03 dose rows/CSV/summary; 506 pairs; 0 forwards|
|C01|PASS|04 negative anatomy; 7 frames; complete local anchors; 0 forwards|
|F01|PASS|05 FP anatomy; 7 anchors/support NPZ; 0 forwards|
|T01|PASS|08 regression: 10 tests -B -W error exit0; 09 experiment exit0|
|R01|PASS|17 index / code diff / manifest; 18 integrity; numbered logs|
|R02|PASS|return append / top README / this report / options|
|E03|BLOCKED|DET-03 resource limitation inherited; native ATen not run|
|G01|BLOCKED|10: torch2.12.0+cpu CUDA false; no GPU round authorized|
|L01|NOT_RUN|No labels/physical calibration executed|
|D01|NOT_RUN|No device/network/driver/deploy/capture/production actions|

完整性详见18/22；执行PASS不等于识别可用。

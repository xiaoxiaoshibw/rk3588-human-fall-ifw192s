# DET-05 唯一验收表 v1（2026-10-08）

授权：用户 2026-10-08 选择 (a) 并确认 OpenCode 执行、"writer 初标 + 用户确认后冻结"；[预注册计划](DET05_PLAN.md)。状态仅作者自验；初始未执行均 NOT_RUN，缺资源 BLOCKED。完成后逐 ID 追加最终证据，执行 PASS 不等于识别可用或 ACCEPTED。

| ID | 要求 | 初始状态 |
|---|---|---|
| S01 | 指定 worktree/唯一 writer/ponytail 实际加载路径；00 baseline 先行（两树+3211 资产）；先读资料再计划/表再实现；主树只读 | NOT_RUN |
| A01 | 10 帧 prepared/raw 双链绑定标注（human/furniture/mixed_uncertain；未标不默认背景）；确定性初标 + 渲染 + 簇表；作者修正逐条记录 | NOT_RUN |
| A02 | 用户确认记录；`gt_v1` 冻结（行列表/质心/z 顶/AABB/provenance；帧集与变换 SHA）；冻结不回写 | NOT_RUN |
| B01 | 逐条目纯人体柱审计：全有效点 human 判定、纯/非纯/未标原因计数、边界保守处理 | NOT_RUN |
| C01 | 10 条目 base/pure_switch 成对运行；仅纯柱切换，其余逐值等于 base（张量/计数/坐标/槽位）；20 前向预算 | NOT_RUN |
| M01 | GT 三口径位置分、GT anchor 全库/局部排名、≥0.8m 竞争位与边距、框包含与 AABB IoU；base/pure_switch 并列；seed 口径三值复算一致 | NOT_RUN |
| T01 | 新增纯柱/切换/指标回归；`python -B -W error` 全过；不改阈值/容量/强度/z/权重 | NOT_RUN |
| R01 | 编号日志含失败；config；代码 diff；artifact 索引与逐文件 SHA；新忽略目录；18 完整性/消费资产清单 | NOT_RUN |
| R02 | 回传 append/README 顶部同步/逐 ID/技能路径/结论边界/后续选项；SUBMITTED 不自行 ACCEPTED | NOT_RUN |
| E03 | 上游原生 ATen 完整运行等价；继承 DET-03 资源限制 | BLOCKED |
| G01 | 上游 GPU 逐值等价；本轮不启动 | BLOCKED |
| L01 | 物理/辐射标定、独立人/场景泛化、新增数据；本轮不做 | NOT_RUN |
| D01 | 设备/网络/驱动/部署/采集/生产；本轮不做 | NOT_RUN |


## R1 最终作者自验（2026-10-08，SUBMITTED）

|ID|作者自验|证据|
|---|---|---|
|S01|PASS|00 baseline（两树+3211 资产全匹配）/ plan / acceptance / 18 integrity|
|A01|PASS|03 annotation proposal + 渲染 + prepared/raw 双链绑定 / 10 independent checks|
|A02|PASS|03b 用户确认（原文保留）/ 03c freeze / labels_v1 + gt_v1|
|B01|PASS|04 purity audit（纯柱 1-6/条；可切换 0-2）/ 10 checks 独立复算一致|
|C01|PASS|05 run rows / switch isolation（非纯柱逐值相等）/ 20 forwards|
|M01|PASS|06 metrics（GT 三口径 / anchor 排名 / 0.8m 竞争位与边距 / 框包含与 IoU）/ seed 三值 exact|
|T01|PASS|08 regression: 12 tests `python -B -W error` exit0|
|R01|PASS|17 code diff/快照/manifest/索引; 18 integrity; 编号日志含失败|
|R02|PASS|return append / 顶层 README / 本报告 / options|
|E03|BLOCKED|DET-03 资源限制继承；native ATen 未运行|
|G01|BLOCKED|仅 CPU；无 GPU 轮授权|
|L01|NOT_RUN|物理/辐射标定与独立人/场景泛化未做|
|D01|NOT_RUN|无设备/网络/驱动/部署/采集/生产动作|

完整性详见 18/22；执行 PASS 不等于识别可用；`gt_v1` 冻结后未再改动。

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

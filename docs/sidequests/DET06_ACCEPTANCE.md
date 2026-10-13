# DET-06 唯一验收表（v1，2026-10-08）

> **状态：v1，已冻结；R1 已执行，作者自验 SUBMITTED（未 ACCEPTED）。** 与 [DET06_PLAN.md v1](DET06_PLAN.md) 配套。初始未执行均 NOT_RUN，缺资源 BLOCKED。执行 PASS 不等于识别可用或 ACCEPTED。

## R1 最终作者自验（2026-10-08，SUBMITTED）

|ID|作者自验|证据|
|---|---|---|
|S01|PASS|00 baseline（6206 / 10877 / 3211 资产变化 0）先于实现；18 完整性|
|P01|PASS|01_data_conditions + 03b：五段到位与用户确认|
|P02|PASS|02_protocol_freeze：输入/匹配/预算/帧集先于前向冻结|
|A01|PASS|annotate_r4：24 帧人框提案 + 硬负例 + 渲染（确定性、无模型）|
|A02|PASS|03b "人框 OK"；03c gt_eval_v1 冻结（24/9/3）|
|B01|PASS|04：74 前向；失败首跑保留 04_eval_r1_fail|
|M01|PASS|05_metrics：两臂 PR/操作点/空场/硬负例/锚点辅助；对照帧复现逐值一致|
|T01|PASS|test_det06 3 项新增；`python -B -W error` 全部 15 项通过|
|R01|PASS|17 打包；18 完整性；编号日志含失败|
|R02|PASS|回传 DET-06.md；sidequests/human_detectors/README 顶部同步；完整报告 README.md|
|E03|BLOCKED|DET-03 资源限制继承；native ATen 未运行|
|G01|BLOCKED|仅 CPU；无 GPU 轮授权|
|L01|NOT_RUN|物理/辐射标定与独立人/场景泛化未做|
|D01|NOT_RUN|无设备/网络/驱动/部署/采集/生产动作|

完整性详见 18/22；执行 PASS 不等于识别可用；`gt_eval_v1` 冻结后未再改动。

| ID | 要求 | 初始状态 |
|---|---|---|
| S01 | 指定 worktree/唯一 writer/ponytail 实际加载路径；00 baseline 先行（两树+继承资产复验）；先读资料再计划/表再实现；主树只读 | NOT_RUN |
| P01 | 数据条件清单逐项结论（全部现有采集的人员/场景/可用性；第二人会话；未确认采集暂不使用；训练资源；标注预算）＋用户确认原文 | NOT_RUN |
| P02 | 评估协议冻结：切分（优先人/场景整体隔离，其次会话，最后时间块）、评估区域与区域完整标注原则、GT 定义、匹配口径、操作点 FP 预算、指标列表、输入定义（主/辅臂）先于任何模型动作；用户确认记录 | NOT_RUN |
| A01 | 评估集标注提案：逐帧人框＋人形硬负例＋无人帧清单；确定性提案＋渲染；prepared/raw 双链绑定 | NOT_RUN |
| A02 | 用户确认记录；`gt_eval_v1` 冻结（框/区域/硬负例/空场；帧集与变换 SHA；provenance）；冻结不回写 | NOT_RUN |
| B01 | 基线评测：现有权重按冻结协议运行；输入逐值断言；无训练、无权重/上游修改；前向限一次声明预算 | NOT_RUN |
| M01 | 指标：PR 曲线、操作点 recall、硬负例分布、anchor 辅助口径；dev 选点、test 仅一次；产出 DET-07 判据参照值 | NOT_RUN |
| T01 | 回归：新增协议/匹配/指标断言；`python -B -W error` 全过 | NOT_RUN |
| R01 | 编号日志含失败；config；代码 diff；artifact 索引与逐文件 SHA；新忽略目录；18 完整性/消费资产清单 | NOT_RUN |
| R02 | 回传 append/README 顶部同步/逐 ID/结论边界/后续选项；SUBMITTED 不自行 ACCEPTED | NOT_RUN |
| E03 | 上游原生 ATen 完整运行等价；继承 DET-03 资源限制，另行授权 | BLOCKED |
| G01 | 上游 GPU 逐值等价；另行授权 | BLOCKED |
| L01 | 物理/辐射标定；本单不做，显式以冻结输入假设运行（边界入报告） | NOT_RUN |
| D01 | 设备/网络/驱动/部署/采集/训练/生产；本单不做；第二人/新场景数据依赖此项授权 | NOT_RUN |

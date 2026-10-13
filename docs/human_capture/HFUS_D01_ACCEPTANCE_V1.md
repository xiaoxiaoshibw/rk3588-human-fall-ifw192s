# HFUS-D01 唯一开发验收表

v1 · 2026-10-11 · 当前用户离线实施授权，统一计划v2为依据。此表为开发验收，非规划验收。标准冻结，结果写return；工程/算法/人工/设备分开。

| ID | 层级/入口 | PASS预期与负例 | 初始状态 |
|---|---|---|---|
| D01-01 | 索引与有效性 | raw28B/valid compact/leveled xyzi 显式双向映射；传感器XYZ有限且非全零后R/T；重复坐标保持行身份；NaN/Inf/原零点经平移回归。 | NOT_RUN |
| D01-02 | 冻结接口 | 点集/51与69维特征/预处理/模型/输入/GT/config/imports SHA manifest；association_anchor 与 scoring_centroid 分开；最小接口v1先冻结，变更升级并通知。 | NOT_RUN |
| D01-03 | 完整层账本 | 分类前全部PA/PB组件与硬拒绝原因/当前raw成员；背景删除、proposal失败、分类拒绝、关联失败分开，逐层点守恒。 | NOT_RUN |
| D01-04 | 严格计分 | 一对一coverage>=.50/purity>=.80；缺候选GT进FN；当前accepted支持的observed_confirmed与coast分开；partial unmatched_unknown不当FP；GT资格/事件/有效暴露秒数显式。 | NOT_RUN |
| D01-05 | PointNet | 新消费者采样→Float32→中心化→转置；原权重不变；native与Float32一致，ONNX/forward同输入maxdiff<=1e-5；固定候选来源与旧错误差异。 | NOT_RUN |
| D01-06 | 基线 | 当前源码BG-A三会话S1/near/S6真实全帧复算strict/legacy与失败集合，九会话契约可消费；859固定候选数值/点集对拍，不强迫旧版本数字。 | NOT_RUN |
| D01-07 | 交接 | 实际命令、源/模型/schema/输入SHA、文件所有权、逐ID证据与失败、适用范围、ponytail路径和新return。 | NOT_RUN |
| D01-DEV | 设备/采集/部署 | 本轮无授权，保持NOT_RUN | NOT_RUN |
| D01-PHY | 物理/生产/独立新场景 | 缺充分证据与另行授权，保持BLOCKED | BLOCKED |

证据目录：`evidence/2026-10-11_hfus_d01_r1/`；回传：`returns/HFUS-D01.md`。每ID使用PASS/FAIL/NOT_RUN/BLOCKED并链接实证。

# HFUS-D03 唯一开发验收表

v1 · 2026-10-11 · 当前用户离线实施授权，统一计划v2为依据。此表为开发验收，非规划验收。标准冻结，结果写return；工程/算法/人工/设备分开。

| ID | 层级/入口 | PASS预期与负例 | 初始状态 |
|---|---|---|---|
| D03-01 | 真实接入 | 隔离副本BG-B输出实际进入PA和PB；PB不重复旧envelope；分类前组件、score、轨迹、visible输出证明。 | NOT_RUN |
| D03-02 | 归因控制 | 首轮候选门/XGB69/PIPE tracker及retention/最终Unique固定；retention来自当前raw并重走候选质量门；不得多变量掩盖。 | NOT_RUN |
| D03-03 | 参考UNKNOWN | 缺参考、未匹配、支持不足UNKNOWN，无射线覆盖不称FREE，不无条件放行；参考/采样每4帧/occ>=.5/参数与R/T绑定。 | NOT_RUN |
| D03-04 | 难帧证据 | S6 f128/f187/f188逐点流向/全组件/coverage/purity/分类score/轨迹可追；不预设15<60唯一原因。 | NOT_RUN |
| D03-05 | 九会话 | D01冻结schema全帧真实链strict/legacy/事件/失败集合/分层性能；source/input/model/config/schema SHA与同输入对照；复用可视化真实输出。 | NOT_RUN |
| D03-06 | 算法目标 | S6 legacy acceptedTP>=67/71、confirmed>=64/71，187/188正确proposal；S1 legacyFP=0，near confirmedTP>=256/FP<=9；strict有资格场景不回退；p95<=50ms heap<=1500MB。未达到FAIL保留证据，缺资格BLOCKED。 | NOT_RUN |
| D03-07 | 交接 | 所有权/命令/SHA/逐ID证据/失败/范围/ponytail与新return。 | NOT_RUN |
| D03-DEV | 设备/采集/部署 | 本轮无授权，保持NOT_RUN | NOT_RUN |
| D03-PHY | 物理/生产/独立新场景 | 缺充分证据与另行授权，保持BLOCKED | BLOCKED |

证据目录：`evidence/2026-10-11_hfus_d03_r1/`；回传：`returns/HFUS-D03.md`。每ID使用PASS/FAIL/NOT_RUN/BLOCKED并链接实证。

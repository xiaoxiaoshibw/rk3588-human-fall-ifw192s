# HFUS-INTEGRATION 唯一开发验收表

v1 · 2026-10-11 · 当前用户离线实施授权，统一计划v2为依据。此表为开发验收，非规划验收。标准冻结，结果写return；工程/算法/人工/设备分开。

| ID | 层级/入口 | PASS预期与负例 | 初始状态 |
|---|---|---|---|
| INTEGRATION-01 | 授权保护 | 全树含untracked/ignored baseline/branch/HEAD；只写授权新根与本轮docs，旧资产SHA对比与外部漂移解释；无设备/生产变更。 | NOT_RUN |
| INTEGRATION-02 | 并行冻结 | A contracts/eval、B review、C background、主控integration/统一入口；无跨目录写入；接口版本/SHA验证与returns完整。 | NOT_RUN |
| INTEGRATION-03 | 真实复跑 | 主控同一冻结输入复跑模块及实际A/B链，独立检查GT资格/分母/PointNet/输出/所有权，保留失败，不拼接最佳数字。 | NOT_RUN |
| INTEGRATION-04 | 第二轮门 | 据D03接通及证据决定D04；D05a负例不足BLOCKED；D05b身份/静止资格不足BLOCKED；启动项先独立目录/新唯一表/单writer。 | NOT_RUN |
| INTEGRATION-05 | D06/D07 | D06一个实际组合/同次完整计分；缺算法/人工门BLOCKED不晋级；D07缺真人/区域标注时完成待审要求与BLOCKED。 | NOT_RUN |
| INTEGRATION-06 | 独立审核 | 完整任务文件+短单行carrier；指定opencode-go/deepseek-v4.1-flash真实probe与只读审核，provider/model/session/read记录/exit验证；不完整读取不算有效。 | NOT_RUN |
| INTEGRATION-07 | 修复与提交 | 原所有者修复审核重大问题/必要复审；最终代码/证据/验收/审核意见处理记录与return，状态SUBMITTED不自签ACCEPTED。 | NOT_RUN |
| INTEGRATION-DEV | 设备/采集/部署 | 本轮无授权，保持NOT_RUN | NOT_RUN |
| INTEGRATION-PHY | 物理/生产/独立新场景 | 缺充分证据与另行授权，保持BLOCKED | BLOCKED |

证据目录：`evidence/2026-10-11_hfus_integration_r1/`；回传：`returns/HFUS-INTEGRATION.md`。每ID使用PASS/FAIL/NOT_RUN/BLOCKED并链接实证。

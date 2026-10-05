# GL-A：统一估计器接口 / 计划工单 v1

状态：PLANNED / IMPLEMENTATION_NOT_RUN。本轮只编制；实施需后续明确启动。逻辑编号GL-A，验收ID使用AGL-A-*，不与既有GL-I01/GL-B01等历史工单混用。

来源：[最终计划](../ADAPTIVE_GROUND_LEVELING_FINAL_PLAN.md)、[接口契约](../ADAPTIVE_GROUND_LEVELING_CONTRACT.md)、[WORKFLOW](../WORKFLOW.md)。本文件下表是本单唯一验收表v1，不再复制一张到其他提示词。

## 目标与范围

复用已有纯数值TLS covariance、centeredSVD、有界raw RANSAC，增加统一PointDomain/PlaneEstimate与thin adapters。规划contracts.py/selection.py、estimators/tls.py、svd.py、ransac.py与集中检查；不修改已冻结ground/calibration/config/driver，不把三适配器或整个框架堆到同一个文件/函数。估计器数值valid与后续quality valid分开，B未实现时不得输出可接受高confidence。

前置：本计划/坐标契约；现有P02源行与数字可作为已曝光fixture，不作为物理真值。输入同canonical float64 source array、weights、FrameKey/domain/config；输出含统一normal/d/source pitch/roll、全域指标字段、数值状态/quality_pending、confidence/reasons。

## 先诊断的操作矩阵

startup × 无输入/合法schema；同内容reload/同ID不同内容/新ID配置；caller原地改array/结果；wrong frame/domain/units/NaN/bool；缺点/共线/极窄；法向翻转；RANSAC budget耗尽；各结果到达顺序。逐行先映射入口、赋值顺序、保护/拒绝行为，再写实现。

## 唯一验收表 v1

| ID | 要求、触发/负例与预期 | 检查/证据入口（后续实现） | 当前结果 |
|---|---|---|---|
| AGL-A-01 | 三adapter同PointDomain实际point/row/weights SHA；不得各自筛点/cap/ROI；三输出标准schema及相同FrameKey | same-input adapter oracle/manifest | NOT_RUN |
| AGL-A-02 | n/d同步normalize/flip；source→display方向、pitch/roll符号、yaw gauge正确；已知GT 10/26/45°与roll±10°，Rn=up误差≤1e−12 | independent scalar transform/normal cases | NOT_RUN |
| AGL-A-03 | malformed/schema/units/frame/bool/string/NaN/Inf/empty/越界/重复/混source/domain拒；invalid明确不造identity/verified | strict constructor/negative matrix | NOT_RUN |
| AGL-A-04 | TLS/SVD同域clean/noisy normal gap≤.001°、d gap≤1e−5m；RANSAC支持/full残差分母明确，budget incomplete不伪valid | known source numerical cross-check | NOT_RUN |
| AGL-A-05 | caller/返回对象修改不污染下次；sameID不同内容/坏reload原子拒；新配置epoch清旧结果；连续同输入/seed可重复 | identity/reload/ownership combinations | NOT_RUN |
| AGL-A-S01 | ponytail先读；基线含untracked、前置诊断、有效回归、源SHA/回传/停写、指定独审；不生产接入 | scope + return + independent review | NOT_RUN |

## 交付与停止点

对应模块/集中检查/示例manifest，逐ID原命令与exit、已知反例、数据与源码SHA；`evidence/<date>_agl_a_rN/`，`returns/GL-A.md`按RETURN_TEMPLATE追加。实施者只SUBMITTED/BLOCKED，完成停写后独审。A过软件门后才可单独授权B，不因A输出能拟合就接runtime。

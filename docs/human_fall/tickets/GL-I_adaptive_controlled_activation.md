# GL-I：Controlled Activation与回退 / 计划工单 v1

状态：WAIT_DEPENDENCY / WAIT_EXPLICIT_AUTHORIZATION / IMPLEMENTATION_NOT_RUN。前置H获审shadow证据；物理/地面身份/外推范围/性能/消息版本/消费者门；获审release+profile+用户具体启用授权。PLAN_READY不等于本单启动或生产放行。

来源：[最终计划§13/14](../ADAPTIVE_GROUND_LEVELING_FINAL_PLAN.md)、[接口契约§7/9](../ADAPTIVE_GROUND_LEVELING_CONTRACT.md)、旧GEOMETRY/GL-P01契约与[WORKFLOW](../WORKFLOW.md)。本文件唯一验收表v1。

## 目标与范围

人工开关OFF默认、enable/disable/freeze/unfreeze、独立adaptive显示输出、immutable release回退。最初接管只到显示；候选/跌倒/背景/跟踪使用adaptive需在同单明确追加审核范围/消费者矩阵和物理门，不能隐式把显示成功当算法资格。

Raw原topic/原PCAP/driver/SDK/物理1.14/旧calibration保持。每次接受有transform_id/revision，reference rebase有epoch。旧coordinate.ground/physical flags不能自动改义。selected lock/standing baseline期间首版freeze updates。

## 前置操作矩阵（不可省略）

startup/no model/legacy；same content/sameID不同内容/newID reload；caller修改；wrong frame/domain/units/schema；enable/disable/freeze/unfreeze重复与并发；locked/pending/stand-baseline/无输入/过期/恢复；release/profile/source/ROI重定基准；producer/consumer/cache/实际点AABB/投影/选择绑定；资源错误与回退失败。

## 唯一验收表 v1

| ID | 要求、触发/负例与预期 | 检查/证据入口 | 当前结果 |
|---|---|---|---|
| AGL-I-01 | approved release/profile/ROI/适用范围/物理与目标机证据齐备才enable；DRAFT/null预算/缺授权拒；OFF默认 | activation gate/profile/token negative matrix | NOT_RUN |
| AGL-I-02 | enable/disable/freeze/unfreeze原子幂等；冻结R/t/revision逐位不变；disable回明确current固定模式；unfreeze仍RECOVERING，不能一帧恢复/自动清锁 | exact control/state sequences | NOT_RUN |
| AGL-I-03 | source/point/真实点AABB/二维投影/选择/诊断同frame+transform ID；跨epoch缓存/站姿基线失效或受审重投影；locked/采基线首版不自适应 | full lifecycle/consumer combinations | NOT_RUN |
| AGL-I-04 | 不把coordinate变化当目标运动/跌倒；no-input/过期invalid资格正确；旧recalibration latch与physical1.14不被score/GOOD治愈；source raw及driver保持 | downstream invariance/fault/no-write checks | NOT_RUN |
| AGL-I-05 | 已知固定模型/release一键disable/rollback，版本/SHA/log可复原；回退失败拒半切换并报告；不删除数据/旧release/失败证据 | authorized release/rollback rehearsal | NOT_RUN |
| AGL-I-06 | 独立真实精度/适用范围/false updates/性能/actual browser+DPR通过本次冻结profile要求；缺物理或真实UI不得只软件PASS后激活 | independent final evidence pack | NOT_RUN |
| AGL-I-S01 | 最终动作需实际具体授权及WF独审收口；单writer/ponytail/diag/SHA/return；只获准控制路径，不扩driver/network/SDK/采集 | scope/authorization/independent review | NOT_RUN |

## 交付

人工操作/发布与回退手册、具体release/profile/source绑定、所有消费者矩阵与真实证据，`evidence/<date>_agl_i_rN/`、`returns/GL-I.md`。任何门未过，保持旧方案，状态BLOCKED；不能为了闭环宣布ACCEPTED。

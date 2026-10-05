# GL-D：时间稳定、六状态与安全保持 / 计划工单 v1

状态：PLANNED / IMPLEMENTATION_NOT_RUN；前置C软件验收。来源：[最终计划§5/8](../ADAPTIVE_GROUND_LEVELING_FINAL_PLAN.md)、[接口契约§6](../ADAPTIVE_GROUND_LEVELING_CONTRACT.md)、[WORKFLOW](../WORKFLOW.md)。本文件唯一验收表v1。

## 目标与范围

新增temporal/controller/transition events：INIT、ACQUIRING、STABLE、DEGRADED、HOLD、RECOVERING；validated cohort→median→EMA→向量/逐轴rate limiter；observed d同步gate/filter；last_good/age/freeze/recover。时间显式输入，无ROS隐式clock。保持已有GroundMonitor latch，不自动治愈旧calibration失效。

## 前置操作矩阵

六状态 × GOOD/DEGRADED/BAD × last_good有/无；no-input tick/重复/乱序/dt0/坏time_domain/gap；同内容reload/sameID改内容/新ROI/source/config epoch/caller mutation；manual freeze/disable/unfreeze；单尖峰/持续小新pose/5～20°跳变；bad穿插恢复窗口；最后一帧后断流。窗口和last_good的赋值顺序逐行设计前置。

## 唯一验收表 v1

| ID | 要求、触发/负例与预期 | 检查/证据入口 | 当前结果 |
|---|---|---|---|
| AGL-D-01 | INIT不identity；N_acquire/最短duration/distinct同epoch满足才首次STABLE；前N−1无accepted；invalid打断连续性 | exact synthetic timeline + constructor | NOT_RUN |
| AGL-D-02 | 只validated coherent候选喂median/EMA；bad不污染窗口/EMA；输出轴步与组合步≤限、角rate按有效dt；offset同步限速 | independent scalar filter/rate oracle | NOT_RUN |
| AGL-D-03 | BAD/low score/遮挡/大jump/缺输入进入HOLD，R/t与revision逐位不变；expired保持显示但geometry失效；无last_good不伪造 | all six states × fault/time/age | NOT_RUN |
| AGL-D-04 | HOLD/DEGRADED恢复需N_recover及duration；第1/N−1不得应用，bad/gap/duplicate重置；≤2°持续可信小变化稳定确认后限速追踪；5～20°不被EMA吞下 | recovery/pending-rebase/outlier scenarios | NOT_RUN |
| AGL-D-05 | 不兼容epoch/reload清pending/旧资格；bad reload原子拒；manual freeze锁存，unfreeze仍走恢复；旧GroundMonitor latch不被单GOOD清 | lifecycle/consumer/ownership operation matrix | NOT_RUN |
| AGL-D-06 | 每次状态/accept/discard/reset/freeze事件都有frame/time域/old-new/reason/IDs/action；no-input不造帧；primary+全部fault可重放 | transition trace oracle | NOT_RUN |
| AGL-D-S01 | stdlib+NumPy，不先引Kalman/IRLS；设计前置与WF自验/回归/SHA/停写/独审；不接生产 | scope/return/review | NOT_RUN |

## 交付

两个小模块、状态/事件schema和完整时间序列检查；`evidence/<date>_agl_d_rN/`、`returns/GL-D.md`。所有变更仅proposal/accepted显示模型，不改1.14物理记录。没有有效dt，明确拒更新，不猜10FPS。

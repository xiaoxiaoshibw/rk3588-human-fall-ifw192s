# GL-F：Replay Validation与参数冻结 / 计划工单 v1

状态：PLANNED / IMPLEMENTATION_NOT_RUN；前置E软件验收及明确启动。来源：[最终计划§12/13](../ADAPTIVE_GROUND_LEVELING_FINAL_PLAN.md)、[接口契约](../ADAPTIVE_GROUND_LEVELING_CONTRACT.md)、[WORKFLOW](../WORKFLOW.md)。本单唯一验收表v1。

## 目标与范围

盘点现有A/B/C和其他PCAP/bin/NPZ，按source/hash/标签/单位/time_domain与曝光状态登记；replay八异常场景、完整分组指标，预注册median/EMA/profile比较与false-update判据，冻结最终可用profile。只读既有数据，不新采集/部署；缺必需真实场景记BLOCKED，不能用synthetic冒充。

当前已知：ABC只直接支持空地/箱/移除与短时静态，193帧已曝光；人在走动/完全遮挡/机械移动未在本计划确证。既有四区leave-one-out #1/#3/#4 FAIL必须保留；新框架不能仅靠temporal把数据几何问题签PASS。

## 唯一验收表 v1

| ID | 要求、触发/负例与预期 | 检查/证据入口 | 当前结果 |
|---|---|---|---|
| AGL-F-01 | 数据inventory actual SHA、session/frame/ROI/GT或专家标签/曝光记录；ABC原时间gap保持；virtual-time拼接另标WHAT_IF | immutable dataset manifests/adapters | NOT_RUN |
| AGL-F-02 | 八场景均有synthetic已知GT用例；真实场景有实际证据才PASS；每场状态/保持/恢复/角跳变与原因符合预登记期望 | scenario matrix + transition traces | NOT_RUN |
| AGL-F-03 | raw/median/EMA/limited/accepted与current固定参考同输入比较；pitch/roll std、逐帧/秒增量、全点/最差区RMS/P95、pair差完整；不挑seed/帧/区域或删除失败 | paired deterministic replay metrics | NOT_RUN |
| AGL-F-04 | forbidden applied updates精确0；异常false update按异常帧与应用次数两种分母、分母0=NA、标签/unknown排除数/容差/episode/CI/n公开；相关帧不冒称独立，CI不足则NOT_ESTIMATED，真实目标0只是样本目标 | known GT + independently annotated adversarial episodes | NOT_RUN |
| AGL-F-05 | candidate参数/score/rate/GOOD-DEGRADED门在开发集比较，方法/profile冻结后独立封存集再验；当前.74136°与.5候选门的DEGRADED不偷改为GOOD | pre-registration/config history/held-out evaluation | NOT_RUN |
| AGL-F-06 | 数据缺陷/coverage范围/leave-one-out FAIL逐项保留；没有真实人/遮挡/移动或独立holdout不得声称整体验证完成；明确可放行/仍BLOCKED项 | per-ID results + adoption decision | NOT_RUN |
| AGL-F-S01 | 不新算法/optimizer/生产改动；新证据目录不可覆盖、原输入零漂移；诊断/自验/停写后独审，不因大量tests宣称部署ready | provenance/scope/return/review | NOT_RUN |

## 交付

inventory、scenario/evaluation manifest、命令/exit/全失败、profile版本/阈值依据、dataset split与采用/否定决定；`evidence/<date>_agl_f_rN/`、`returns/GL-F.md`。软件replay框架可单独验收，真实数据缺失保持分层BLOCKED；H不可绕过必需真实门。

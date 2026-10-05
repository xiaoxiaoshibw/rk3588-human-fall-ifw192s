# AI 工单总表

2026-10-05新增已具体授权：[P03回放自动配平](P03_replay_auto_leveling.md)，唯一[P03 v1](../P03_ACCEPTANCE.md)，单writer Claude Code，NOT_RUN。该单不启动GL-A～I，不取消GL-W01人工确认哲学（auto只替画ROI，不替确认才消费）。

2026-10-05新增已具体授权：[GL-W01离线配平工作台](GL-W01_offline_workbench.md)，唯一[GLW01 v1](../GLW01_ACCEPTANCE.md)，SUBMITTED/指定独审服务BLOCKED。该单复用静态P02，不将下面AGL-A～I实施状态提升。

## 地面配平后续阶段（2026-10-02当前）

## 最终阶段新增：GL-A～GL-I 自适应地面配平（PLAN_READY，未实施）

入口：[正式计划](../ADAPTIVE_GROUND_LEVELING_FINAL_PLAN.md) / [接口契约](../ADAPTIVE_GROUND_LEVELING_CONTRACT.md)。每ticket含自身唯一v1验收表，所有实现结果NOT_RUN；实时shadow/启用另有具体授权和证据门，不因计划就启动。

| 工单 | 内容 | 依赖 / 当前状态 |
|---|---|---|
| [GL-A](GL-A_adaptive_estimator_interface.md) | 统一估计器与PointDomain接口 | 后续启动；PLANNED/NOT_RUN |
| [GL-B](GL-B_adaptive_quality.md) | Quality/coverage/退化与单法confidence | A；PLANNED/NOT_RUN |
| [GL-C](GL-C_adaptive_consensus.md) | 家族保护的三方法一致性仲裁 | A/B；PLANNED/NOT_RUN |
| [GL-D](GL-D_adaptive_temporal.md) | 时间滤波/六状态/last_good/恢复 | C；PLANNED/NOT_RUN |
| [GL-E](GL-E_adaptive_offline_leveling.md) | FINAL source R/t与离线应用 | D；PLANNED/NOT_RUN |
| [GL-F](GL-F_adaptive_replay_validation.md) | Replay八场景/profile/独立验证 | E+数据；PLANNED/NOT_RUN |
| [GL-G](GL-G_adaptive_diagnostics_webui.md) | 三列/FINAL/可信度/日志preview | D/E+F schema；PLANNED/NOT_RUN |
| [GL-H](GL-H_adaptive_shadow_mode.md) | 目标机只计算shadow与性能 | F/G+具体授权；WAIT_DEPENDENCY/AUTH |
| [GL-I](GL-I_adaptive_controlled_activation.md) | 人工受控接管/冻结/回退 | H+物理/consumer/启用授权；WAIT_DEPENDENCY/AUTH |

以上GL-A～GL-I与下方GL-00～05/GL-B01/I01等历史单不同；验收ID采用AGL-X-*避免重名。下一可启动的软件单是GL-A，当前只交计划，不已派发。

当前阶段入口：[GROUND_LEVELING_PLAN](../GROUND_LEVELING_PLAN.md)，方法依据：[调研与审查](../GROUND_LEVELING_METHOD_REVIEW.md)。GL00/01/02软件已分别获审，设备/真实物理独立记录；下方HF为历史验收。派工使用[WORKFLOW](../WORKFLOW.md)与对应工单验收表，不直接派旧宽范围提示词。

| 缩写 | 英文 | 中文 | 说明 |
|---|---|---|---|
| **GL** | **Ground Leveling** | 地面配平 | HF 第一阶段暴露出候选框贴地、吞入机器人及地面的问题。先完成地面几何/配平方法调研与 Candidate 重算，再将配平结果接入现有候选生成链路。工单范围：**GL-00～GL-05**。

| 编号 | 内容 | 前置/状态 |
|---|---|---|
| [GL-00](GL-00_data_roi_review.md) | 真实数据、地面ROI、先验与参数/契约审核 | R4软件/方案PASS，真实物理BLOCKED |
| [GL-01](GL-01_constrained_ground.md) | PCL方法参考的约束RANSAC/SVD原型 | R4软件PASS，真实来源/物理BLOCKED |
| [GL-02](GL-02_ground_frame.md) | 局部地面变换与标定生命周期 | R7 A01–A12软件PASS，设备NOT_RUN/物理BLOCKED |
| [GL-03](GL-03_candidates_geometry.md) | 正确地面框与当前大候选诊断/最小修复 | R7 G01/G02/G03/G04/G05/G07/G08软件PASS；G06/真实身份BLOCKED，O01统计PASS，D01设备NOT_RUN；整单未ACCEPTED |
| [GL-04](GL-04_webui_level_view.md) | 点云/框/二维选择/俯瞰同坐标显示 | WAIT_AUTHORIZATION：须用户另行授权，不因GL03软件PASS自动派发 |
| [GL-05](GL-05_device_acceptance.md) | 物理/浏览器/性能验收与回退发布 | GL-01～04软件PASS及现场条件 / WAIT_DEPENDENCY |

## HF 首版工单与历史状态

共同要求：[DISPATCH.md](../DISPATCH.md)。每张必须使用 ponytail（马尾辫）skill，按 [回传模板](../RETURN_TEMPLATE.md) 交付，由 Codex 审查。

| 编号 | 执行 AI | 内容 | 前置与状态 |
|---|---|---|---|
| [HF-00](HF-00_sensor_inventory.md) | Luna；Codex/OpenCode 真机探测 | 硬件、话题、SDK、时间与环境盘点 | ACCEPTED（盘点范围）；未知项已分配 |
| [HF-01](HF-01_contract_capture.md) | DeepSeek v4.1 Flash | 无相机契约、小 ROS 包、采集/健康工具 | ACCEPTED；第 2 轮复审通过，已实现范围冻结 |
| [HF-02](HF-02_time_imu.md) | DeepSeek v4.1 Flash | 时间归一、IMU 语义与质量检查 | 第3轮：软件PASS，R1–R5全闭合；设备BLOCKED，整单未ACCEPTED——**2026-10-02 用户决定降级为备忘，不进 GL-05，仅当后续接入移动/非静止场景时再回头核验** |
| [HF-03](HF-03_geometric_calibration.md) | DeepSeek v4.1 Flash | 安装变换、地面与 IMU 旋转标定 | 01/02 验收后 |
| [HF-04](HF-04_perception_candidates.md) | DeepSeek v4.1 Flash | 点云候选、几何特征与难例 | 01～03 验收后 |
| [HF-05](HF-05_target_lock.md) | DeepSeek v4.1 Flash | 网页选择后端、站姿基线、锁定跟踪 | 02～04 验收后 |
| [HF-06](HF-06_fall_logic.md) | DeepSeek v4.1 Flash | 特征与跌倒时序状态机 | 01～05 验收后 |
| [HF-07](HF-07_ros_events.md) | DeepSeek v4.1 Flash | ROS 状态/事件、源帧框与选择回执、集成 | 01～06 验收后 |
| [HF-11](HF-11_webui.md) | DeepSeek v4.1 Flash | 现有 WebUI 框选、标定、自动框与跌倒显示 | 04/05 接口后可分步，整体验收等 07 |
| [HF-08](HF-08_repeatable_evaluation.md) | Luna | 网页与算法回放、指标与失败索引 | 契约冻结后分步；07/11 后整体 |
| [HF-09](HF-09_deployment_profile.md) | DeepSeek v4.1 Flash | 板端算法与网页性能、必要优化、部署 | 07/11/08 验收后 |
| [HF-10](HF-10_codex_review.md) | 当前 Codex | 独立复核、通过/返工/待真机 | 指定工单的每次回传由Codex直接读取并复审 |

当前状态（2026-10-01）：软件首版与HF09可回退部署已完成独立复审，211两端回归/44独立Python边界/18网页纯检查PASS，最终HF10见returns/HF-10.md。HF00/01已冻结；**HF02 已于 2026-10-02 由用户决定降级为备忘——固定雷达判定跌倒不依赖 IMU，仅当未来移动/非静止场景再回头核验**；HF03物理标定、HF06/08真人准确性与性能门槛仍缺证据，整体不虚标ACCEPTED；confirmed/IMU融合禁用。所有原回传/失败和旧版本保留，当前无OpenCode运行任务。

已按用户自主推进授权实现RK3588算法和现有网页选择/基线/状态交互，详见[WEBUI_SCOPE.md](../WEBUI_SCOPE.md)。现有12张工单，后续完成HF09并由当前Codex记录HF10最终软件审查与剩余真人条件。

## 直接递交提示词

HF-02第3轮软件返工已完成并经Codex复审PASS，现无待派软件返工。当前需补设备证据；[第3轮返工要求](../HF-02_REWORK_R3_PROMPT.md)、原HF-02开工/第1轮返工提示词及HF-01第1轮返工要求均作为历史保留，不重新执行已闭合项。

2026-10-01起按[Codex–OpenCode CLI闭环](../CODEX_OPENCODE_WORKFLOW.md)连续执行，直接派工/读取/复审/续接返工。当前运行session和恢复检查见AUTONOMOUS_RUN.md，不重复已完成工单。

后续每次替换工单路径与编号；使用前检查前置是否已由 Codex 验收。执行 AI 最终须返回工单，不能自行给 ACCEPTED。

## GL-00 R4 Codex独立复审 / 2026-10-01

用户明确恢复开发，雷达向下看为最新安装事实，机器人总高1.4m/眼球离地约1.1m。R3参数/ceil/证据措辞返工后，R4软件方案、合成参数协议与兼容契约PASS；真实数据/物理BLOCKED，仅放行GL-01合成原型，不允许实际标定启用或部署。Codex独立13协议检查exit0、完整SHA核查src/webui/冻结资产未变；R2布局脚本修订与原版本保留已记录。p=.999/w=.2预算861；逐验证区域门槛、采样up_axis基底、源索引不泄漏等补充见evidence/2026-10-01_gl00_r4/CODEX_REVIEW.md。R2主动中断、R3 CR错误与旧失败保留，未造真实PASS。

## GL-01 R4独立软件复审PASS / 2026-10-01

显式约束RANSAC、数值CLI与加载器经Codex244回归/12独立方法exit0及同SHA板端244验证，软件PASS；真实bag源索引/帧组适配、ROI与物理BLOCKED，未部署。原9/10独立失败已闭合，两次API400在同DeepSeek session压缩后恢复，日志保留。hardware_inventory.md外来人工截图约26度粗估保留，不据此标实测。详evidence/2026-10-01_gl01_r4/CODEX_REVIEW.md。允许串行GL02数学软件/未核验候选预览，不升级真实外参/IMU/confirmed。

## 最新用户派工方式与GL02 R1复审 / 2026-10-01

用户要求“接下来任务让我手动给cluadecode”。后续改为用户手动交Claude Code；Codex只准备具体工单/独立复审，不自动调用OpenCode继续返工或派后续。当前GL02 OpenCode R1已结束exit0，Codex262常规回归通过但独立6方法6失败，软件REWORK/真实物理BLOCKED，GL03未放行。手动下一步为AI_PROMPT_GL02_CLAUDE_REWORK.md，详细证据evidence/2026-10-01_gl02_r1/CODEX_REVIEW.md与40_*。GL00/01已审软件不重做。无活动实现写入者，不部署/采集，旧失败保留。

## GL-02 Claude R2 Codex独立复审 / 2026-10-01

软件REWORK，GL03不放行；继续用户手动派Claude Code。Codex独立262回归/原6方法exit0；新增集成5方法5失败，补类型检查后最终7方法7失败exit1（evidence/2026-10-01_gl02_r2/50～54）。R2闭合原反例，但实际加载仍可保留旧ground、裸块版本错配；monitor失效仍发布位置/继续相关观测、散点误报整体变化、重标定被一帧清除；float版本/mixed bool矩阵仍通过。详同目录CODEX_REVIEW.md；下一步手动AI_PROMPT_GL02_CLAUDE_R3.md。板端兼容NOT_RUN，真实物理BLOCKED，未改生产算法/部署/采集。

## GL-02 Claude R3 Codex独立复审 / 2026-10-01

R2原七方法/267全回归/R2静态六方法独立通过（GL02 R3 evidence50～52），已闭合部分保留；新增其他入口四方法四失败，补单侧遮挡后最终五方法五失败exit1（55_*）。软件REWORK，设备兼容NOT_RUN/真实物理BLOCKED，GL03不放行。剩余为配套局部更新calibration版本错配/caller引用、同GDID新calibration版本未清旧资格、monitor不可用仍accepted基线请求、10%单侧遮挡误锁存整片变化。详evidence/2026-10-01_gl02_r3/CODEX_REVIEW.md；用户手动下一步AI_PROMPT_GL02_CLAUDE_R4.md，不自动派工。生产算法未由Codex修改，未部署/采集。

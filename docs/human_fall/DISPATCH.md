# HF/GL 当前派工入口

按[WORKFLOW.md](WORKFLOW.md) v2执行：用户最新授权Codex直接派OpenCode CLI `opencode-go/deepseek-v4.1-flash`、跟进与独立复审，无需手动搬运；一张工单一份版本化验收表，逐入口/状态集中诊断，提交按[RETURN_TEMPLATE.md](RETURN_TEMPLATE.md)逐条回传。

当前（2026-10-02）GL-02软件PASS（A01–A12），设备NOT_RUN/物理BLOCKED；[最终独立复审](evidence/2026-10-02_gl02_r7/CODEX_REVIEW.md)＋[GL02验收v1](GL02_ACCEPTANCE.md)。当前无活动实现写入者。GL-03软件前置已满足，本轮未启动；部署/采集不在本轮授权内。[CLI恢复流程](CLI_RECOVERY.md)记录上下文故障恢复及成本控制。

## 历史共同要求与回传记录

以下保留旧阶段记录；其中自动OpenCode派工、模型/会话、下一单状态受顶部当前入口覆盖。范围保护与冻结契约仍按WORKFLOW及当前工单执行。

把本文件与一张工单一起递交。工作区：`D:\Code\ldiar`。以当前代码、根 `AGENTS.md`、`CLAUDE.md` 和 `src/human_follow_calibration/README.md` 为事实来源；先读 `docs/human_fall/README.md` 与该工单。不要仅凭旧聊天实现。

2026-10-01用户授权持续自主开发，按[CLI闭环](CODEX_OPENCODE_WORKFLOW.md)直接派工/读取/独立复审/返工，无需用户搬运。软件首版已完成并可回退部署，最终结论见[HF10](returns/HF-10.md)，当前无运行中的CLI工单。真实物理/人体证据单列未验收；后续继续前先读[AUTONOMOUS_RUN.md](AUTONOMOUS_RUN.md)并实时核对版本，不能重复旧阶段。

范围已修订：用户确认没有相机，首版只用已验证的一个点云流、辅助六轴IMU与设备状态。HF-00/01已按范围验收，HF-02与HF-03软件PASS，真实单位/安装/地面物理未验收；“双目雷达”不扩展成相机或第二输入。依新授权继续几何候选/跟踪/ROS/现有网页，不伪造外参或启用未核验IMU融合/confirmed。先读CONTRACT.md冻结范围及GEOMETRY_CONTRACT.md，旧提示词“HF-03未放行”仅为历史。

最新目标见 [WEBUI_SCOPE.md](WEBUI_SCOPE.md)：算法在 RK3588，现有 WebUI 人工选人＋自动跟踪框、位置/站姿基线标定和跌倒状态显示。新增 HF-11 改造已有网页，HF-05/07 提供选择/回执与结果接口；不在浏览器判跌倒，不因点云人体可见就宣布算法已完成。

## 强制使用马尾辫 skill

开工前读取 `C:\Users\30680\.codex\skills\ponytail\SKILL.md`，在回传中写明使用路径。若 OpenCode 支持技能调用，调用同名 ponytail；无法调用时直接读取 SKILL.md 并遵守。其他机器需先由用户提供该文件的真实副本；找不到须报告，不得声称用了 skill。

按“现成实现 → 标准库 → 已安装依赖 → 最小新代码”的顺序选择。复用点云解析；纯计算用 NumPy 与 unittest。不要引入微服务、训练平台、通用插件体系或多个备用模型。仅在性能实测需要时做 NPU 移植。硬件阈值仍须可配置。为新增非平凡逻辑留下至少一个能失败的有效检查，不写照抄实现的测试。

## 修改与运行边界

- 执行前记录 `git status --short`、分支/HEAD 和相关文件差异。当前工作树已有用户修改，包括 `src/CMakeLists.txt`、`publish_manager.cpp` 和未跟踪标定包；不得重置、覆盖或代替用户提交。
- 不默认创建分支/提交/推送。需要隔离时协调工作副本；同一工作树禁止多模型同时改代码。
- 新功能置于已创建的 `src/human_fall_detection/`。保留 HF-01 采集/健康工具，具体文件只在当前工单需要时添加。
- 保留旧 `/human_follow/state` 与 schema_version=1 行为；不替换厂商 .so，不大范围重排驱动。驱动变更保持 ROS1/ROS2 条件分支；本首版应用只做 ROS1。
- 不发布 /cmd_vel 或电机控制，不部署自动通知/联系第三方。首版输出工程检测事件。
- Windows 只做编辑、静态检查与允许的纯函数测试；ROS 构建/传感器采集/性能验证在实际 Linux 板或现有容器执行。当前已验证 SSH `wel@192.168.3.125` 和 `slam-localization` 容器；先读 hardware_inventory.md，沿用已授权访问，不保存凭据，禁止猜用其他项目的 Jetson 地址。
- 已探测实际 RK3588/aarch64、约 8 GB、Ubuntu 20.04、Noetic 容器与 Python 3.8.10/NumPy 1.17.4。首版不要求 cv2/MediaPipe/推理库，不做 NPU 移植。重新操作前核对当前状态与镜像，不能把主机 RKNPU 驱动存在当容器模型已可运行。不要自动升级系统/Python/ROS。新依赖须说明用途与版本兼容，不上传二进制到 Git。
- 切换 ROS 构建脚本会改写 manifest/CMake；不要为验收无关功能随意运行切换。遇到 Windows 上 src/CMakeLists.txt 软链接访问问题，按环境事实报告。
- 不编造真机频率、模型性能、测试通过数、人工标签或标定结果。mock/synthetic/offline/device 必须区分；缺硬件可继续离线逻辑，但依赖硬件的验收标为 BLOCKED。
- 采集的人体点云留在授权设备/本地，不传云、不做身份库；原始 bag 不放入源码提交，记录数据路径/哈希与人工标签。没有相机时不要求图像录制。

## 共用接口（health/manifest 已冻结，state/event 仍为草案）

CONTRACT.md 的冻结范围优先于本节摘要。HF-01 health/manifest 已正式冻结；后续输出字段和语义变更须明确 schema_version/兼容策略，不得静默改变。state/event 的下列要求供后续工单设计，不代表已完成精确 schema 或实现验收。

新 `/human_fall/state`、`/human_fall/event` 与工具 `/human_fall/health` 用 std_msgs/String 的版本化 JSON；首版无需新增消息生成包。几何配置单位用 m、s、rad、m/s、m/s²，变换注明 from/to 方向；原始 IMU 的实际单位单独标已验证/未知，不因 ROS 字段名称就宣布验证成功。

状态至少含：schema_version、session_id、time_epoch、frame_id、source_stamp_s/source_time_domain、可用时的 normalized_stamp_s、track_id、track_status、fall_status、observability、sensor_quality、reason_codes。增加 method/input_profile 区分几何基线与经过验收的 IMU 辅助；target_kind 明确 human_like、selection_source 明确 operator。无效数值为 null，JSON 禁止 NaN/Inf。网页选择绑定源帧候选快照并等待板端回执，CLI 可保留作调试；位置/三维包围盒与选择/基线接口按 WEBUI_SCOPE.md 的独立草案冻结，不改 health v1。

- track_status：unselected / locked / occluded / ambiguous / lost。
- fall_status：unknown / upright / descending / low_posture_unclassified / suspected / confirmed / recovering。
- observability：valid / degraded / invalid。
- source_stamp_s 保留源时钟语义；normalized_stamp_s 只有验证转换后可用，不能直接给设备启动时间贴 Unix 标签。
- track_id 不保证真人身份。丢失/多人交叉不自动换人；恢复锁定按工单规定人工确认。
- sensor_quality 含各路新鲜度、几何参数版本、设备运动、地面有效性；单调时钟 watchdog 不与设备源时间相减。
- 时间回退、输入质量失效、设备运动、目标歧义：清空时序证据，fall_status=unknown；保留已经发出的事件记录。已确认事件不能被一帧姿态变化静默抹除。
- event 含 event_id、session/epoch/track、起止证据时间、reason_codes、证据索引、config/calibration/method 版本；首版没有模型版本。相同事件只发一次；状态降级不重新计数。确认是满足工程规则，不承诺医学诊断。
- 基线使用点云几何：人工确认目标，依据已验证地面/背景与连续观测判定；不是视觉骨架或通用人体分类。IMU 未验收单位/轴向/安装关系时只记录和报告有效性，不参与融合；明确算法必需输入与辅助输入，不能把辅助 IMU 失效等同必需点云失效。几何模式须单独验收后才允许 confirmed，未验收模式只提供观测/unknown。
- 加速度模长接近重力与静止角速度近零不能代替单位验证；源时间相近不能代替同钟/同步验证；没有 /dev/rknpu* 不能否定主机 RKNPU 驱动存在。HF-02/03 补证据，HF-01 可记录 unknown，不为填表伪造转换或单位。

## 统一回传与审查

完成当前工单后按 `RETURN_TEMPLATE.md` 向 `returns/HF-xx.md` 追加本轮，附 patch/分支或当前差异、运行命令、原始日志路径和真实数据证据。OpenCode 最后一条 CLI 消息必须列出回传文件、证据目录和未通过项，供 Codex 从共享工作区直接读取；不得自行批准工单，也不得把文件写入或进程退出当作 Codex 已验收。Codex 独立复审后，按记录的 session ID 直接递交范围内返工。

状态：READY（可执行）/ WAIT_DEPENDENCY（等前置验收）/ IN_PROGRESS / SUBMITTED（待审）/ BLOCKED（具体证据不足）/ ACCEPTED（只有审查者能写）/ REWORK。合成测试通过不能升级为真机 ACCEPTED。不得把本工单之外的“顺手改进”混入差异。

每张工单会做范围检查、接口一致性、失效行为、关键逻辑复现、证据真实性与兼容性审查。审查结论写 `REVIEW_LOG.md`；返工用原工单号追加版本，避免丢失追踪。

## 最新用户派工方式与GL02 R1复审 / 2026-10-01

用户要求“接下来任务让我手动给cluadecode”。后续改为用户手动交Claude Code；Codex只准备具体工单/独立复审，不自动调用OpenCode继续返工或派后续。当前GL02 OpenCode R1已结束exit0，Codex262常规回归通过但独立6方法6失败，软件REWORK/真实物理BLOCKED，GL03未放行。手动下一步为AI_PROMPT_GL02_CLAUDE_REWORK.md，详细证据evidence/2026-10-01_gl02_r1/CODEX_REVIEW.md与40_*。GL00/01已审软件不重做。无活动实现写入者，不部署/采集，旧失败保留。

## GL-02 Claude R4 Codex独立复审 / 2026-10-01

R3原五方法5/5、R2七方法7/7、静态6/6、fall 271/271、follow 2/2、两个webui各18/18均由Codex独立实跑通过。新增reload/已有pending三方法3失败exit1：空或相同配套reload沿用旧版本却丢input.sha256/evidence/note等完整产物字段；已accepted基线请求在随后monitor持续不可用超过10秒时仍pending且无终态回执。软件REWORK，GL-03不放行；设备兼容NOT_RUN、真实物理BLOCKED。详[evidence/2026-10-01_gl02_r4/CODEX_REVIEW.md](evidence/2026-10-01_gl02_r4/CODEX_REVIEW.md)与57_*。手动下一步[AI_PROMPT_GL02_CLAUDE_R5.md](AI_PROMPT_GL02_CLAUDE_R5.md)；只修这两项，不自动派工。生产源码/原测试/driver差异/Windows软链接表示保留，未部署/采集/commit/push/reset。

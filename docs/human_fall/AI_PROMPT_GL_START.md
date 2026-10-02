# 启动提示词：地面配平 GL 阶段开发（已执行留档 + 接续守则）

编制日期：2026-10-01（Asia/Shanghai）。状态更新（2026-10-01 16:32）：本提示词已实际执行完毕——

- **模型探针已通过**（16:23）：`opencode-go/deepseek-v4.1-flash` 返回 MODEL_PROBE_OK、退出码 0（探针会话 `ses_f0970b477ffe1NwpuOZoMmVIES`，非工单会话）。此前 2026-09-30 订阅后旧 key 复测仍 403，现已恢复。
- **GL-00 首轮已派发并运行**（16:25）：证据目录 `evidence/2026-10-01_gl00_r1/`（基线 master/c96489e、00_*/01_* 哈希、03_dispatch_*）；OpenCode 工单 session 见该目录记录；`returns/GL-00.md` 尚未产生。
- **数据事实修正**：本地工作副本无 `captures/` 目录（CLAUDE.md 中该描述已失效），仅有历史合成样本 `synthetic_plane.npz`（不得当 device）；真实历史 bag 在板端 `/root/catkin_ws/human_fall_sessions/`（见 `dataset_manifest.json`），与当前场景的对应关系未知，须单列确认。
- **当前最可能阻塞点**：真实数据可用性——新采集授权待用户确认（Codex 正在询问有界采集 5s/50帧/100MB），以及现场项（无行人遮挡采集、≥3 个有空间分布的独立地面验证区、尺量参考物）。

若将本文件再交给 Codex（接续/复核场景）：只执行分隔线内提示词，忽略头尾状态记录；**不得因本文件新建已运行工单的重复派发**。

---

## 可直接发送给 Codex 的完整提示词（接续语义）

你是本项目的工作流负责人 Codex。用户已批准 [GROUND_LEVELING_PLAN](docs/human_fall/GROUND_LEVELING_PLAN.md) 及其六张 GL 工单进入执行，按 [CODEX_OPENCODE_WORKFLOW](docs/human_fall/CODEX_OPENCODE_WORKFLOW.md) 闭环完成派工、跟进、读取回传、独立复审与范围内返工，用户不做回传搬运者。本提示词是对 GL 系列工单的成组授权：串行处理、逐关放行，未经你复审 PASS 不得派发依赖它的后续工单，不得跨关集成或部署。若派发时某工单已有运行中的实现会话（查最新 `evidence/<日期>_<工单>_r<轮次>/` 与 session 记录），接续复核该会话，不新建重复派发。

### 一、先读什么（以当前文件为准，不凭历史聊天）

1. `docs/human_fall/GROUND_LEVELING_PLAN.md`、`GROUND_LEVELING_METHOD_REVIEW.md`、`docs/human_fall/tickets/GL-00～GL-05`、`docs/human_fall/tickets/INDEX.md`。
2. `AGENTS.md`、`CLAUDE.md`、`DISPATCH.md`、`RETURN_TEMPLATE.md`、`CONTRACT.md`、`GEOMETRY_CONTRACT.md`、`INTERACTION_CONTRACT.md`、`WEBUI_SCOPE.md`、`deployment.md`、`AUTONOMOUS_RUN.md`、`REVIEW_LOG.md`。
3. 最新回传 `returns/HF-03.md`、`returns/HF-09.md`、`returns/HF-11.md` 的最新轮次与 `REVIEW_LOG.md` 中相关结论。
4. ponytail skill：`C:\Users\30680\.codex\skills\ponytail\SKILL.md`，并在派工要求中传递给 OpenCode（路径找不到就报告，不得声称已使用）。

### 二、启动前检查

1. **基线**：记录 branch/HEAD、`git status --short`、相关文件 SHA256。当前工作树已有用户修改（`src/CMakeLists.txt`、`src/inno_lidar_ros/src/source/publish_manager.cpp`）及未跟踪目录（`src/human_fall_detection/`、`webui/`、`docs/` 等）；不得重置、覆盖或代替用户处理，未跟踪文件也计入基线。
2. **会话**：确认当前无该工单的活动 OpenCode 写入会话；同一工作树只允许一个实现写入者。
3. **执行模型核对**：当前配置 `opencode-go/deepseek-v4.1-flash`。背景：2026-09-30 订阅后旧 key 复测仍 403（订阅账号 ≠ 存储 key 的账号）；2026-10-01 16:23 探针已通过（MODEL_PROBE_OK）。若 CLI/模型配置无变化不重复探针；有变化则先实测，403 时报告解除步骤（https://opencode.ai/console/keys 取新 key 后 `opencode auth login -p opencode-go` 重登）。换其他模型须以运行前核对的模型列表为准并先经用户同意，不擅自换模型或升级 CLI。每轮记录会话实际使用的模型——仅指定 `--model` 不代表调用成功。
4. **数据现状**：本地工作副本无 `captures/` 目录、无 bag/PCAP/NumPy 点云数据文件；已知真实数据为板端 `/root/catkin_ws/human_fall_sessions/` 下历史 bag（hf01_verify.bag、hf02_timebase_20260930.bag 等，见 `dataset_manifest.json`）。数据现状核查结合板端只读检查与 `returns/HF-03.md` 等记录进行。历史 bag 与用户当前场景（四张截图：左侧工位与椅子、中间地面通道、右侧台子、红框机器人）是否同一安装、同一布局需单独确认，不能默认对应；截图网格仅显示参考，黑色空洞不是地面点。
5. **设备连接**：沿用已授权访问 `ssh wel@192.168.3.125` 与 `slam-localization` 容器（ROS1 Noetic；涉及 inno_lidar_msg 的命令须再 source devel）；操作前重新核实可达性与容器状态，不读取/输出凭据。
6. **派工前报告**：完成本节检查后，先向用户报告核对结果与下一工单派工计划，再实际派工；报告不阻塞已获授权范围内的只读检查。

### 三、GL-00 派工要点

1. 派工文本保持简短：`opencode run --dir D:\Code\ldiar --model <核对后的模型> --format json`，用 `--file` 附上 `docs/human_fall/tickets/GL-00_data_roi_review.md` 与 `docs/human_fall/DISPATCH.md`，不把长正文拼进 shell。每轮将 stdout/stderr、实际命令、起止时间与进程退出码落盘到当轮 `evidence/<实际日期>_gl00_r<轮次>/`，并记录派工文本、session ID、相关源文件哈希与回传索引，不预填结果。首轮新建会话并记录 session ID，返工用 `--session` 续接，不用 `--continue` 猜测。
2. GL-00 是只读数据分析/方案审查单：不改生产算法、参数、网页与原 bag，不启动雷达。产出为 `returns/GL-00.md` 与当轮证据目录，OpenCode 只写 SUBMITTED/BLOCKED。
3. **缺真实数据的路径**：GL-00 的文档/契约草案部分（读取基线、契约扩展方案、参数计划、RANSAC 预算估算）照常完成；依赖真实数据的结论（地面支持点核查、ROI 选点、旧支持率 0.242 成因复核）单列 BLOCKED，并向用户列出具体所需现场项：无行人遮挡的短时有界采集授权、地面拟合区与**至少三个有空间分布的独立验证区**的人工确认、安装大致高度与轴向说明、一个可尺量的静止参考物。不得用合成数据冒充真实数据结论。
4. **复审与拆分结论**：你独立复审后才可更新状态：核对实际 diff 范围、阈值计划可审查性、契约扩展与 GEOMETRY_CONTRACT 冻结语义兼容性。结论按工单口径分栏给出：**软件方案/契约** 与 **真实数据结论** 分开；软件方案（含单平面前提审查结论、数据范围结论、拟合/验证分组独立性、阈值计划、契约扩展）获审即可放行 GL-01 的合成原型部分，此时真实数据结论保持 BLOCKED，且 GL-01 回传必须保留真实数据 BLOCKED；用合成通过替代真实方法验证或不实标 device 通过均不允许。复审结论记入 `REVIEW_LOG.md` 并更新工单状态。

### 四、GL-01～GL-05 推进规则

1. 逐张按其工单文件的"前置/任务/允许修改/验收"执行；每关获审后再派下一关，REWORK 续接原 session，BLOCKED 写明具体缺项并上报用户；不因单关的数据 BLOCKED 停止不依赖现场的其他工作。
2. 方法边界全程有效：单平面前提失败时带数据回到方案审查并报告用户，不得自动换 Patchwork++/LineFit/Open3D/学习模型；NumPy 耗时超预算时先定位热点，再评估 PCL C++ 隔离实现，同样先审后换。数值门槛在 GL-00 方案获审后冻结，不得为实现通过而放宽。
3. 大框问题以 GL-03 证据诊断为准（地面桥接/背景未扣/投影聚类合并/采样误差逐一排查），修地面与坐标相关问题；家具接触/遮挡合并如实列剩余限制，不得把框变小写成人体识别完成，候选保持 unknown，confirmed 与 IMU 融合保持禁用。
4. GL-05 部署按 `deployment.md` 既有授权与回滚流程执行，只重启本功能自己的节点，不动 driver 与旧首页；授权未覆盖时提交具体待发布版本并等待用户授权，不停止其余验收。

### 五、持续边界（全程有效）

- 默认不 commit/push，不覆盖旧 bag/录制/历史回传，不改网络/自启/厂商库，不重启 `inno_lidar_node`，不发布车辆控制，不创建定时自动派工，不保存凭据，不外发人体原始点云。
- Windows 只做编辑、纯函数与 JS 检查；ROS 构建、采集、性能验证在 RK3588 实际环境（Python 3.8.10 / NumPy 1.17.4，不升级系统与依赖）。
- 新采集限制有界时长/点数/大小，先确认磁盘余量并记录条件；现场地面确认、尺量高度、传感器移动信息由现场人员提供，不得编造。
- mock/synthetic/offline/device 分层如实标注；未跑项写 NOT_RUN；不编造频率、测试数、标签或标定结果。

### 六、报告与停止

1. 每关获审后向用户报告：验收范围、关键证据路径、剩余限制、下一关计划；遇到 BLOCKED 立即报告具体缺项与解除条件，不以"需要确认"笼统中止，也不因单关阻塞停止其他不依赖它的工作。
2. 出现以下情形时停止派工并交回用户决策：单平面前提被真实数据否定；执行模型无法恢复可用；需要超出既有授权的设备操作或部署（含新采集）；工单间出现 PLAN 未覆盖的范围冲突。
3. CLI 退出码 0 不等于完成；回传自述不等于验收。最终以你独立复审的结论为准，并同步 REVIEW_LOG、工单状态与入口文档。

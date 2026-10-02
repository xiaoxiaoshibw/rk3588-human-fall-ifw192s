# 人体跌倒检测开发前只读审计

本文件保留前序静态审计；最新用户明确没有相机，原先把“双目”解释为双目相机的假设已撤回。当前实时 IMU/点云证据及 HF-00 验收结论以 hardware_inventory.md、IMU_VERIFICATION.md 与 REVIEW_LOG.md 为准。

范围：只盘点当前仓库中可见的 ROS 接口、人体样目标处理、时间戳与测试，并整理跌倒检测的重复性验收方案。本报告没有读取 `captures/` 中的二进制内容，也没有运行测试、连接设备或推断实际硬件配置。下列行号对应本次审计时工作树中的文本文件。

## 1. 已有传感器接口、时间戳、IMU 字段与检测限制

### 点云接口

- ROS 驱动发布 `sensor_msgs/PointCloud2`，默认主题 `/innolidar_points`，帧名默认 `innolidar`；同时发布自定义 `/device_status`。证据：`src/inno_lidar_ros/config/config.yaml:31-35`、`src/inno_lidar_ros/src/source/publish_manager.cpp:177-197`。
- 点云至少包含 `x/y/z`、`intensity`、`ring`；编译时可选择再发布 `timestamp`，或再发布 `timestamp/distance/horizontal/vertical/speed`。具体启用哪种点类型由编译配置决定，不能只凭源代码断定运行消息包含这些扩展字段。证据：`src/inno_lidar_ros/src/source/publish_manager.cpp:60-89`。
- 校准脚本只读取 PointCloud2 的 `x/y/z`，支持行填充、FLOAT32/FLOAT64 和大小端，过滤非有限值和小于最小距离的点，再按固定 XYZ ROI 裁剪。它不读取 RGB/图像、人体关键点或检测框。证据：`src/human_follow_calibration/scripts/calibrate_human_follow.py:26-69,72-75`。
- 输入可配置为实时 LiDAR 或 PCAP 回放；仓库默认配置当前写的是 PCAP 来源。`pcap_repeat` 开启且本地帧索引到达末尾时，驱动代码把本地请求索引设为 0 并调用 SDK `SetLocalFrame(0)`；这只能证明代码请求回放首帧，不能据此断言输出时间戳一定回退或由此导致监测失效。SDK 对时间戳的处理须实测。证据：`src/inno_lidar_ros/config/config.yaml:1-5,18`、`src/inno_lidar_ros/src/source/source_driver.cpp:158-184`、`src/human_follow_calibration/README.md:58`。

### 时间戳

- 点云 ROS header stamp 取自驱动帧的 `inno_msg.timestamp`，拆成秒和纳秒；ROS1 还复制 `seq`。代码注释中的“使用当前墙钟”做法被注释掉，因此这不是代码所证明的电脑接收时间。证据：`src/inno_lidar_ros/src/source/publish_manager.cpp:138-152`。
- 校准采集拒绝零值、非法纳秒以及不大于上一帧的时间戳；并以 `time.monotonic()` 计量等待超时。README 说明设备时间戳只用于单调性检查，不与电脑墙钟比较。证据：`src/human_follow_calibration/scripts/calibrate_human_follow.py:208-230`、`src/human_follow_calibration/README.md:37`。
- 监测器对非递增/零时间戳或不匹配的 `frame_id` 发布 `invalid`；超过默认 2 秒没有新鲜帧则发布 `stale`。接收队列长度为 1。证据：`src/human_follow_calibration/scripts/monitor_human_follow.py:67-70,110-142`。
- PCAP 回放的实际时间基准、时钟复位行为及实时雷达时钟与主机的同步精度，不能从这些包装代码单独确认；需查 SDK 约定并用设备数据验证。

### IMU

- SDK 包装结构 `ImuMsg` 声明了 `state`、`timestamp`、四元数 `orientation_x/y/z/w`、三轴角速度和三轴线加速度。其头文件将时间戳注释为纳秒。证据：`src/inno_lidar_ros/third_party/inno_driver/inno_driver/msg/imu_types.hpp:3-15`。
- IMU 回调注册和 ROS 发布都受 `ENABLE_IMU_MSG_PARSE` 条件编译控制；启用后默认主题为 `/inno_imu`。证据：`src/inno_lidar_ros/src/source/source_driver.cpp:78-82`、`src/inno_lidar_ros/src/source/publish_manager.cpp:198-201,207-210`。
- 转为 `sensor_msgs/Imu` 时只赋值角速度和线加速度，未把结构体的四元数写入 ROS orientation；也未显式设置协方差。另有时间单位风险：SDK 结构体注释写“纳秒”，而 ROS 转换按“秒”拆分整数秒/小数纳秒。应以 SDK 定义及实机消息验证单位，不能据此声称 IMU 时间戳当前正确。证据：`src/inno_lidar_ros/third_party/inno_driver/inno_driver/msg/imu_types.hpp:5-15`、`src/inno_lidar_ros/src/source/publish_manager.cpp:156-174`。
- 本仓库的人体跟随校准/监测脚本没有订阅 IMU；已有状态算法仅用点云几何。设备内 IMU 反映的是设备运动，不能据此获取人体所受冲击或人体姿态；若用它辅助跌倒判断，仍须定义并验证设备运动如何参与判定。证据：`src/human_follow_calibration/scripts/calibrate_human_follow.py:26-30,90-137`、`src/human_follow_calibration/scripts/monitor_human_follow.py:75-84,110-130`、`src/inno_lidar_ros/third_party/inno_driver/inno_driver/msg/imu_types.hpp:3-15`。

### 现有“人体”检测的边界

- 这不是跌倒检测或通用人体识别：流程要求人工指定单个已知站位的静止目标，使用空场前 2/3 帧建立体素背景、剩余帧做空场检查，然后按 XY 网格连通分量与点数、高度、宽度、深度筛选。证据：`src/human_follow_calibration/README.md:35-46`、`src/human_follow_calibration/scripts/calibrate_human_follow.py:90-137,140-188`。
- 当前目标形状阈值包含高度下限 0.45 m，算法按站立尺寸过滤；蹲坐/弯腰/躺卧可能因高度或形状阈值而漏检，具体结果必须用标注数据测量，不能从阈值推成确定表现。证据：`src/human_follow_calibration/scripts/calibrate_human_follow.py:126-136,284-292`。
- 目标状态按单帧候选数输出 `present/absent/ambiguous`，没有跨帧身份跟踪；静止人体若在建背景时留在 ROI 中还可能被吸收为背景。证据：`src/human_follow_calibration/scripts/monitor_human_follow.py:44-58`、`src/human_follow_calibration/README.md:64-66`。
- 当前单元测试覆盖填充 PointCloud2 解码、零/NaN 过滤、静止目标、空场、歧义候选、远处变化和场景移动等合成案例；没有跌倒类别、摄像头数据、时序跟踪或真机运动测试。证据：`src/human_follow_calibration/tests/test_calibrate_human_follow.py:26-94`。

## 2. 双目接口缺失与硬件信息边界

据用户说明，实际设备具备双目相机和 IMU。本次代码审计在仓库文本源码、配置、包清单及文档中没有找到双目相机接入实现，包括图像消息接口、`camera_info`、左右目同步、深度图或相机标定链路；设备内 IMU 虽有驱动数据结构及可选 ROS 发布路径，但人体跟随脚本没有订阅它。仓库中出现的“Stereo Rendering”仅是 RViz 显示选项，不是相机接口：`src/inno_lidar_ros/rviz/rviz.rviz:127-130`、`src/inno_lidar_ros/rviz/rviz2.rviz:139-142`。README 也明确指出目前没有 WebUI 或 ROS 到浏览器的桥接：`src/human_follow_calibration/README.md:66`。

最新用户说明是没有相机、只有“双目雷达”；当前源码不提供图像接口，后续已实测六轴 IMU。不能把“双目雷达”推成左右相机或第二台独立设备；内部硬件形态、具体型号和安装关系仍需资料。配置声明 IFW192S 只说明驱动选择该类型：`src/inno_lidar_ros/config/config.yaml:7-10`。旧相机相关验收场景不属于当前无相机首版。

## 3. 跌倒开发的重复性验收数据与异常场景

以下是建议建立的验收集和场景矩阵，不表示仓库已有这些数据或已获得任何性能结果。每段数据应保存采集条件、传感器/软件配置、场景标签、事件起止时间、真值类别与遮挡/运动标签；按人员和场景划分训练/调参/盲测集，避免同一段连续视频跨集合造成泄漏。所有离线回放需保存原始数据及时间戳，并记录重复运行结果。

| 场景 / 标签 | 离线可测 | 需要真机 | 验收记录重点 |
|---|---|---|---|
| 站立、缓慢下蹲、坐下、弯腰、跪姿、拾物 | 有带真值的录制数据时可做固定回放/合成点云回归 | 必须采集真实传感器数据以评估视角、噪声与穿戴差异 | 每类动作起止、静止持续时长；将蹲坐/弯腰列为困难负例，量化误报与漏报 |
| 躺卧、主动躺下、绊倒/跌倒、跌倒后静止、缓慢滑落 | 可对带传感器时间戳和人工标注的录制片段重复回放 | 真机采集用于检查地面回波、姿态可见性和安装视角影响 | 动作阶段/跌倒事件时间、报警延迟、跌倒后持续状态；不同方向和速度单独分层 |
| 静态遮挡、部分遮挡、完全遮挡；多人交叉、旁人经过、多人同时动作 | 可用已标注录制数据与确定性合成点云测试检测逻辑 | 需真实设备验证遮挡结构、回波稀疏、人体交叉的实际影响 | 可见比例/遮挡持续时间、人数和角色、身份交换；跟踪中断/误关联及恢复时间 |
| 点云帧丢失、重复帧、时间戳停滞、回退、跳变；PCAP 循环边界 | 可构造消息序列或固定 PCAP 重放，检查 `invalid/stale`、恢复规则及重复运行一致性 | 真机验证网络丢包、驱动恢复和设备时钟复位是否与离线模拟一致 | 原始/接收时间、连续丢帧数、回退幅度、状态输出与恢复时长；记录回放循环边界的实际时间戳，不预设其回退 |
| 相机晃动、LiDAR/IMU/整机平移或旋转、底盘振动 | 可在有完整传感器记录时回放；可用坐标变换生成受控合成案例 | 必须在目标安装与运动条件下采集，验证运动补偿/背景变化 | 运动源、方向、速度、幅度及同步状态；观察静态背景漂移与事件误报 |
| 光照变化、反光/玻璃、低矮家具、宠物/杂物、ROI 边界 | 带标注录制可离线测 | 真机验证特定场地与传感器可见性 | 将硬负例与场地变化分组，避免只测单一空场 |

验收指标建议按类别和场景分别报告：事件级召回率/误报率、误报次数/小时（需足够长的负例时长）、报警延迟分布、遮挡后的恢复率，以及重复回放输出一致性。须先定义事件匹配窗口和“跌倒”标签标准；本报告不设数值门槛，也不提供任何尚未实测的结果。

### 离线可重复的最小验收包

1. 保存脱敏且带时间戳的原始点云/图像/IMU（若将接入）录制片段；配套逐帧/事件级标注和采集元数据。
2. 固定一组合成点云/消息序列用于确定性边界回归：站/蹲/坐/弯腰/躺卧形状、两人相邻与交叉、遮挡导致的点数下降、丢帧/重复/时间回退、背景整体平移/旋转。
3. 将离线数据集版本、参数、代码提交号和每次状态/事件输出一起归档；盲测集不参与阈值调整。仓库现有测试可作为 PointCloud2 解码和静态点云算法的基础，但并未覆盖上述跌倒验收集。

## 4. 提交主要 agent 的准确性风险

| 风险 | 代码/文档证据 | 建议（待实现或验证） |
|---|---|---|
| 把现有静态人体样目标当成跌倒识别 | README 将其定义为静止标定和“人体样目标”，脚本按单帧尺寸筛选：`src/human_follow_calibration/README.md:35,45,66`；`src/human_follow_calibration/scripts/calibrate_human_follow.py:90-137` | 先定义跌倒事件与困难负例，再单独设计/评估时序检测；报告中区分已有功能与计划功能 |
| 把蹲坐/弯腰/躺卧的几何外观误判为跌倒或直接漏掉 | 当前候选受 0.45 m 最小高度及宽深限制：`src/human_follow_calibration/scripts/calibrate_human_follow.py:126-136,288-289` | 将这些动作都纳入带持续时间的负例/正例数据，按姿势和视角分层出混淆矩阵 |
| 多人交叉时依赖单帧候选数，身份不连续 | 多候选只报 `ambiguous`，无跨帧跟踪：`src/human_follow_calibration/scripts/monitor_human_follow.py:44-58`；README `src/human_follow_calibration/README.md:66` | 将单人遮挡、多目标交叉和身份交换作为独立验收项；不能把某一帧候选当作稳定身份 |
| 忽略时间戳单位/对齐问题，导致跌倒时序或传感器融合错位 | IMU 结构注释为纳秒：`src/inno_lidar_ros/third_party/inno_driver/inno_driver/msg/imu_types.hpp:5`；ROS 转换按秒/纳秒拆分：`src/inno_lidar_ros/src/source/publish_manager.cpp:156-174`；点云时间来自驱动：`src/inno_lidar_ros/src/source/publish_manager.cpp:138-152` | 在做 IMU/双目融合前验证 SDK 单位、设备时钟、消息同步与外参；同步误差应记录实测值 |
| 误把可选 IMU 源字段当作已发布的有效姿态 | IMU 代码为条件编译且不映射 orientation：`src/inno_lidar_ros/src/source/source_driver.cpp:78-82`；`src/inno_lidar_ros/src/source/publish_manager.cpp:155-174,198-210` | 构建配置、实际主题、四元数有效性、协方差和轴向均需现场检查；不可只因结构体有字段就认为算法可用 |
| 误用本仓库默认配置声称在真机上运行，或用循环 PCAP 证明实时性 | 配置 `msg_source: 2` 指定 PCAP：`src/inno_lidar_ros/config/config.yaml:1-5`；循环路径把本地请求索引设回 0 并请求 SDK `SetLocalFrame(0)`：`src/inno_lidar_ros/src/source/source_driver.cpp:158-184`，输出时间戳是否回退仍须实测 | 验收材料注明数据源和回放模式；真实频率、端到端延迟、网络丢包与真机运动只能在目标设备验证 |
| 背景扣除把静止人体吸收，或设备运动造成大面积背景差异 | 2/3 空场帧建背景；README 要求空 ROI 且设备静止：`src/human_follow_calibration/scripts/calibrate_human_follow.py:144-150`；`src/human_follow_calibration/README.md:35,45,58` | 跌倒检测避免把单次静态空场假设当成长期有效；设计背景漂移/设备运动测试及安全失效状态 |
| 把站位角度偏移、表面距离或标定误差推广成全空间精度 | 单个正前方站位输出角偏移和距离残差；README 明确不能解算完整外参/比例修正：`src/human_follow_calibration/scripts/calibrate_human_follow.py:189-205,313-319`；`src/human_follow_calibration/README.md:43` | 跌倒位置/距离等输出需独立标定与多位置验证；不要把当前跟随标定 JSON 当作跌倒系统外参 |

## 检查范围与未验证项

检查了根 `AGENTS.md`、`CLAUDE.md`、人体跟随 README、校准/监测脚本、对应单元测试、LiDAR 发布与源驱动代码、IMU 结构体、ROS 消息和文本配置；仓库源码中只发现 RViz 立体显示设置，没有双目接入实现。没有遍历 captures 二进制文件，没有运行现有单元测试或 ROS 构建，没有连接真机，没有验证实际运行主题、IMU 时间戳单位、相机驱动/标定/同步、性能指标或任何跌倒识别结果。双目相机与 IMU 的硬件存在性来自用户说明；建议验收数据和风险项是后续工作建议，不代表已实现能力。

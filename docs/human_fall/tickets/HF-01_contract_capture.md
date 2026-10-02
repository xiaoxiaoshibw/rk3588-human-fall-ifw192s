# HF-01 冻结接口与最小采集/健康工具
执行：OpenCode DeepSeek v4.1 Flash。依赖：HF-00 盘点交付已由 Codex 验收。状态：**ACCEPTED**（2026-09-30 第 2 轮经 Codex 复审，R1–R7 闭合；已实现接口冻结）。首版无相机：一个点云输入、辅助 IMU、设备状态。详见 [审查记录](../REVIEW_LOG.md)；HF-02 READY，等待用户递交。

先读 ../DISPATCH.md 并读取 ponytail SKILL.md。本单不做人体/跌倒算法。

## 工作与代码
- 提交 docs/human_fall/CONTRACT.md：明确 lidar_geometry 基线、人工选人的人体样目标、输入/错误码、源时间与接收时间、变换方向、schema/version、必需点云与辅助 IMU 的区别。单位/同步/安装旋转未验证则记录 unknown，由 HF-02/03 补证据；不构造相机或第二台雷达输入。由 Codex 审查冻结；性能阈值不伪造。
- 为后续真正需要的脚本创建最小 ROS1 包 src/human_fall_detection/，package.xml/CMakeLists.txt/config/default.yaml；不提前实现其他工单模块。
- scripts/sensor_health.py：订阅 /innolidar_points、/inno_imu、/device_status，发布 /human_fall/health。测接收新鲜度、有限值、源 stamp 单调/回退/跳变、实际接收统计；PointCloud2 检查 fields/offset/datatype/count/point_step/row_step/endianness/数据长度。报告源 stamp 与接收 monotonic；未知时钟域不计算伪端到端延迟，帧回退递增 epoch 并记原因。
- orientation 全零或非单位四元数标不可用；协方差全零表示未知，不能凭全零协方差断言角速度/加速度不可用。IMU units_verified=false、alignment_verified=false，保留原值；不得默认转换 g/deg/s 或发布有效姿态。abnormal_flag=255 原样记录且语义未知，不解释为“正常/故障全开”。
- scripts/record_session.sh 或一个 Python CLI：优先复用 rosbag record，仅录点云/IMU/设备状态/健康话题；按 session 写 manifest.json（topic/type、配置/软件版本、bag 与标签路径/哈希、原始时间域、单位与同步状态、标定路径/状态）。当前无 TF，允许标定待提供，不等待 TF/CameraInfo。录制必有时长或明示终止方式，Ctrl-C/SIGINT 后 bag 可读取；不重写 rosbag 格式。
- schema 的 null/NaN/Inf 处理和状态字段校验用小纯函数；只加实际需要的结构。

## 验收与回传
使用板上 Python 3.8.10 / NumPy 1.17.4，与根 AGENTS.md 一致。合成测试覆盖 timestamp@18/point_step=26 非对齐读取、填充行/大小端、截断/非法 fields、零/NaN 点、全零四元数、重复/回退 stamp、点云停流与辅助 IMU 停流的区别、JSON 非有限值拒绝、manifest 缺字段。复用旧 xyz_from_cloud，先读调用方，不复制整份脚本或改旧接口。

ROS 构建和 5～10 秒短 bag 验收在现有 Linux 容器完成，记录命令/退出码/计数/类型与再读结果；不启动相机、不下载模型、不重启既有雷达服务、不改变网口/自启脚本/厂商库。只部署本单新增包与必要构建产物，不覆盖远端驱动副本。无同步不标已同步；无有效 orientation 不标正常姿态。提交代码、CONTRACT.md、日志与 returns/HF-01.md，状态 SUBMITTED，等待 Codex 冻结；不得自动开始 HF-02。

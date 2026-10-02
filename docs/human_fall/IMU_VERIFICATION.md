# 雷达 IMU 输出核验

2026-09-30，Codex 检查本地驱动、板上 SDK 和实时 ROS 数据。结论：**当前在线雷达/SDK 确实提供三轴角速度与三轴加速度输出，不再只是预留的 ROS 话题。姿态四元数当前不可用。** 芯片型号、机身具体安装位置及出厂标定仍没有资料可确认。

## 源码证据

- `src/inno_lidar_ros/CMakeLists.txt:29` 默认打开 ENABLE_IMU_MSG_PARSE。
- `src/inno_lidar_ros/src/source/source_driver.cpp:80` 向雷达 SDK 注册 RegisterImuCallBack；该节点没有订阅外部 IMU 话题。
- 同文件 `PutImuMsg` 将 SDK 回调的 ImuMsg 入队，`ProcessImuMsg` 取出后调用 SendImuMsg，并不是通过 ROS Timer 生成空 IMU 消息。
- `src/inno_lidar_ros/third_party/inno_driver/inno_driver/msg/imu_types.hpp:3` 定义有效性 state、时间戳、四元数、三轴角速度和三轴加速度。默认值/结构定义本身不能证明传感器存在。
- `src/inno_lidar_ros/src/source/publish_manager.cpp:156` 直接复制 SDK 的角速度和加速度。该转换没有复制 orientation，也没有在调用链中检查 state；这是后续有效性处理的待修项，本轮未改代码。
- `/inno_imu` publisher 是 Init 阶段声明的，因此仅有话题不能证明已有数据；本次进一步取得了连续实测消息。

SDK 核心是预编译 `libinno_driver.so`，仓库没有其完整解析源码。板上动态符号可看到 OnlineManager::GetImuMsg、Decoder::IsImuSame(IMUBlock)、DecoderIFW192S::DecodeMsopPacket。符号存在说明 SDK 有 IMU 处理链，不能仅凭符号推断芯片型号或所有型号都配 IMU。

上游仓库 [innolidar/inno_driver_ws](https://github.com/innolidar/inno_driver_ws) 描述支持 IFW192S/FW192SB；它没有提供足以确认当前设备 IMU 芯片型号的硬件规格。配置字符串 IFW192S 也不能代替铭牌。

## 本轮独立实时证据

[实时连续采样日志](evidence/2026-09-30_imu_live.log) 与 [单帧/SDK 探测日志](evidence/2026-09-30_imu_support.log) 均由本轮 Codex SSH 探测生成；可复查 [采样脚本](evidence/probe_imu_live.sh)。没有修改设备、驱动、网络或服务配置。

- 在线配置 msg_source=1；/inno_imu 唯一 publisher 为 /inno_lidar_node。已核对正在加载仓库挂载位置的 aarch64 SDK。
- 4.02 秒窗口收到 902 条 IMU 和 39 帧点云；按首尾接收时刻计算，IMU 接收频率约 226.766 Hz，点云约 9.646 Hz。这是短时接收观测，不是额定硬件频率或长期性能承诺。
- IMU 源时间戳严格递增，相邻间隔约 0.004311～0.004530 秒；角速度与加速度均为有限值且有变化。
- 加速度模长约 9.668～9.806（发布数值）。与含重力的静止加速度数量级一致，但单位、轴向和尺度仍需厂商约定/受控实验核验。
- 第一条加速度为 (-4.2282, 0.1389, 8.7197)，角速度为 (-0.002727, 0.034907, 0.022362)。不是 SDK 构造器中全零默认数值。
- 902 条消息的 orientation 都是 (0,0,0,0)，orientation_covariance[0] 都为 0。全零四元数非法，不能用于旋转/姿态估计；源码未复制姿态可以解释此输出，但不能由此判断 SDK 内部是否已有有效姿态。

## 对开发计划的影响

确认六轴测量链可用后，可以安排设备运动检测和静止重力参考验证。先核实单位、轴向、时间域、安装旋转、state 语义与偏置；不能直接把当前 orientation 接入融合，也不能把 IMU 当人体佩戴传感器。

第一轮 SSH 没有消息是当时的运行快照，本次重新采样时数据已恢复；两轮日志都保留。HF-00 的出流阻塞已解除，但双目输出、具体型号与完整同步/标定仍未验收。

后续正式移交审查已将 HF-00 盘点范围验收，并按用户确认无相机修订计划；无需补图像接口。单位/时间与安装关系分别转 HF-02/03，具体型号内部光学结构可后续补查，详见 REVIEW_LOG.md。

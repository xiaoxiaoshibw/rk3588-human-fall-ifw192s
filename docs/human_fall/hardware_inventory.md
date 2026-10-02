# HF-00 硬件与运行环境实测盘点

2026-09-30 后续目标补充：用户录屏与 Codex 再次只读抓取证明板端现有 WebUI 可显示可辨人体点云；本地尚未纳入该页面的产品源码。当前页面不含新增选人/跟踪/跌倒输出，后续改造范围见 [WEBUI_SCOPE.md](WEBUI_SCOPE.md)。以下 HF-00 的原始采样结论和证据保留，不把录屏显示结果当作人体检测或跌倒算法验收。

## Codex 独立复核补充

已独立 SSH 核对实时点云与 IMU，4.02 秒采到 902 条 IMU、39 帧点云；角速度与加速度持续变化且均有限值，orientation 全零。确认存在六轴测量输出，具体芯片型号/机身位置未查明。详见 [IMU 核验](IMU_VERIFICATION.md) 及 [独立采样日志](evidence/2026-09-30_imu_live.log)。上层 2026-09-30_host.log 等日志由 Codex 前轮 SSH 生成，有明确来源。

下文单位与时间项的证据边界须按本补充理解：约 9.7 的加速度模长只能支持 m/s² 数量级推断；静止角速度接近零不能验证 rad/s 尺度。两个话题时间戳处于同一数量级不能独立证明同一硬件时钟或时间偏移为零。厂商单位约定、受控运动验证及 HF-02 的时钟/偏移核验仍需要完成，不将它们列为已验证。

- 日期：2026-09-30（Asia/Shanghai），采集窗口约 12:52–13:46。
- 执行：OpenCode（有设备访问授权的执行者）。静态审计另见 `LUNA_AUDIT.md`（本轮未修改）。
- 执行者提交状态：BLOCKED。Codex 审查结论：**ACCEPTED（仅盘点交付范围）**；单位/同步转 HF-02，安装旋转/地面转 HF-03。用户明确没有相机，首版按点云与辅助 IMU 开发；双目雷达内部形态未查清不阻塞单个点云接口。下列量级推断不等于已验证单位。
- 访问方式：使用用户本机已有的 SSH 配置条目 `ldiar-wel`（HostName 192.168.3.125，User `wel`，密钥认证，来自 `~/.ssh/config`）。未猜测口令、未使用其他项目的设备地址；所有操作只读，日志不含口令。
- 原始日志目录：`docs/human_fall/evidence/2026-09-30_hf00/`（索引见文末第 9 节）。

## 1. 硬件与运行拓扑

- 板上主机 `welcomtech`：Rockchip RK3588 EVB7 LP4 V10 Board，Ubuntu 20.04.6 LTS aarch64，内核 5.10.160，8 核，内存 7.7 GiB，根分区 57G（已用 33G）。`[本次实测]`（A）
- 主机 `/opt/ros` 不存在；ROS 栈全部运行在容器 `slam-localization`（镜像 `slam-localization:noetic`，Id `43c3213a…`，`network=host`，绑定 `/home/wel/slam_localization_wuhan/src:/root/catkin_ws/src`）。板上工作目录不是 git 仓库。`[本次实测]`（B、C、D、G）
- 运行进程：`roscore`/`rosmaster`/`rosout`、`/inno_lidar_node`、`/foxglove_bridge`（8765）、`python3 -m http.server 8090 --directory /root/catkin_ws/webui`。`rosnode list`：`/foxglove_bridge`、`/inno_lidar_node`、`/rosout`。`[本次实测]`（E、H）
- 自启链路：`/etc/systemd/system/lidar-stack.service`（oneshot）→ `/usr/local/bin/lidar-stack.sh`：按 MAC `08:e2:6d:c4:fd:47` 动态识别雷达网口，配置 `192.168.1.35/24` 与 `192.168.1.10 dev <if> src 192.168.1.35` 路由，然后启动容器、roscore、驱动与 foxglove_bridge。`[本次实测]`（I）
- 采样开始时雷达链路为 NO-CARRIER（首轮采样 `/innolidar_points`、`/inno_imu` 0 消息，F 是阻塞状态证据）；用户接通后 eth2 carrier=1、`192.168.1.35/24` 在位、数据流动（L、M）。eth2 对 `192.168.1.10` 的 ICMP 2 包全丢，但 UDP 点云正常流入。`[本次实测]`
- 雷达运行配置（容器内 `/root/catkin_ws/src/inno_lidar_ros/config/config.yaml`）：`msg_source: 1`（在线雷达），`lidar_type: IFW192S`，UDP `cloud_port: 8080`，视场 ±60°/±45°，`max_distance: 30`，`ros_frame_id: innolidar`，extrinsic 全 0 且 `use_status: true`。`[本次实测]`（H）
- Windows 工作副本的 `src/inno_lidar_ros/config/config.yaml` 是 `msg_source: 2`（PCAP），与板上运行配置不同；涉及运行行为时以板上配置为准。`[源码配置事实]+[本次实测]`
- 节点二进制 `/root/catkin_ws/devel/lib/inno_lidar_ros/inno_lidar_node`（Sep 20 11:44）；板上包 CMake：`POINT_TYPE XYZI_TIME`、`ENABLE_IMU_MSG_PARSE ON`。启动日志打印 `ONLINE_LIDAR`、`ENABLE_IMU_MSG_PARSE`、标定加载 49152 项成功、Transform valid:1 全 0。`[本次实测]`（K、H）

## 2. 运行时传感器接口（本次实测，`rostopic`/`rospy` 采样）

| 话题 | 类型 | 发布者 | 实测频率 | frame_id | 备注 |
|---|---|---|---|---|---|
| `/innolidar_points` | `sensor_msgs/PointCloud2` | `/inno_lidar_node` | 9.65 Hz（min 92 ms / max 116 ms / std ≈5.4 ms，窗口 60） | `innolidar` | width ≈49140–49143，height=1，point_step=26，is_dense=False |
| `/inno_imu` | `sensor_msgs/Imu` | `/inno_lidar_node` | ≈218–233 Hz（窗口 60，多数 ≈230） | `innolidar` | orientation 全 0；三组 covariance 全 0 |
| `/device_status` | `inno_lidar_msg/DeviceStatus` | `/inno_lidar_node` | 9.65 Hz（min 94 ms / max 115 ms） | `innolidar` | device_number=71；trx=44.375 °C，main=40.25 °C；abnormal_flag=255 |
| `/rosout`、`/rosout_agg` | `rosgraph_msgs/Log` | — | 常规 | — | 无传感器语义 |

点云字段（实测 `fields`，与 `POINT_TYPE XYZI_TIME` 编译项一致）：

| 字段 | offset | 类型 | 说明 |
|---|---|---|---|
| x / y / z / intensity | 0 / 4 / 8 / 12 | float32 | |
| ring | 16 | uint16 | |
| timestamp | 18 | float64 | 8 字节起点**非 8 对齐**（point_step=26 紧凑排布） |

- 帧内存在无效点：首点 `x=y=z=0, intensity=954, ring=0`（is_dense=False），使用方必须自行过滤。`[本次实测]`（P）
- **不存在**图像、深度、CameraInfo、TF 话题：`rostopic list` 全量只有上表 5 个话题，`/tf`、`/tf_static` 均无。`[本次实测]`（E）

## 3. IMU 数据语义（本次实测）

- 单位边界：所采样 `linear_acceleration ≈ (-4.2, 0.15, 8.69)`，模长 6 个样本 9.66–9.71，支持 m/s² 数量级推断；`angular_velocity ≈ 0.003–0.04`。日志未记录受控静止条件，近零也不能验证 rad/s 尺度，实际单位/轴向/偏置仍待厂商约定或受控实验。`[本次实测]`（N）
- 姿态无效：`orientation = (0,0,0,0)`，`orientation_covariance` 全 0（未按 ROS 约定用首元素 -1 声明不可用）。发布代码本来就不写四元数；使用方不得把该话题当作有效姿态源。`[源码配置事实]+[本次实测]`
- 发布链路：`publish_manager.cpp` 的 `toRosMsg(ImuMsg)` 只赋角速度与线加速度，并将 `msg->timestamp` 按“秒”拆成 sec/nsec。SDK 头文件注释写“纳秒”，与发布代码矛盾。运行时输出（见第 4 节）表现为自洽的“秒”域时间戳；闭源 `.so` 内原始字段单位仍无法直接证实 → **原始单位标未验证**。

## 4. 时间语义（本次实测）

- 点云 `header.stamp` 与首点 `timestamp` 完全相等：`409.391589000 s`；同帧末点 `timestamp` = `409.494682 s`（帧跨度 +0.103093 s，≈9.65 Hz 帧周期）。`[本次实测]`（P）
- IMU 与点云在同一次会话中处于相近数值域（点云 268.098 s、IMU 269.884 s；后续 356.2 s、409.4 s 增长），frame_id 相同；这不能独立证明同一硬件时钟或零偏移。短样本有递增证据，偏移/漂移与长期复位行为仍待 HF-02。`[本次实测]`（N、O、P）
- 该时钟是无限定原点的单调“秒+纳秒小数”域；与主机墙钟无锚定（主机 `1790747133.3 s` vs 设备 `409.4 s`）。设备时钟与主机时钟的**速率比/漂移未精确测量**（跨命令锚点误差过大），不得用频率数值代替同步证据。`[本次实测]`
- 零点不能证明等于雷达上电时刻（链路恢复前设备时间已在累计）。跨话题（点云↔IMU）固定偏移尚未测，留待 HF-02。`[本次实测]`

## 5. 双目/相机（用户说明 vs 实测证据）

- `[用户说明 2026-09-30]` 设备**没有相机，只有“双目雷达”**；IMU 为雷达内置，无独立模块。
- `[本次实测]` 本次未枚举到 /dev/video*、/dev/media* 或明确 USB 相机设备，未找到具体相机驱动/专用 SDK 的接入证据；cam_ircut disabled，ROS 图无图像/深度/CameraInfo。I/J 仍有 MIPI/CSI 节点和通用摄像头/GStreamer 库，因此不能写成系统完全没有相机相关软件，也不能由一次枚举证明物理上无相机。无相机的项目范围来源于用户说明。
- 在已检查的源码、运行配置及 O 日志定向搜索路径中，未发现双目相机内参/基线/左右同步/深度或相机外参；不扩大为全板无遗漏搜索。config/ifw192s/ 是雷达内部标定 CSV（azimuth/elevation 192×256、model_weights、near_filter）。`[源码配置事实]+[本次实测]`（O）
- 计划文档此前把“双目”当作双目相机；现已按用户说明修订为无相机的点云路线。内部光学单元/型号后缀暂未知；当前一个点云 publisher 不足以推断两台独立雷达，也不应自行构造第二输入或相机输入。铭牌/厂商协议可后续补查。
- 容器 `devel/include` 残留旧工程 `ros_interface`（CameraParkingInfo 等）构建产物，不是相机存在的证据。`[本次实测]`（O）

## 6. 外参与安装参数

- `[真人肉眼观测预估值，2026-10-01（Asia/Shanghai）]` 雷达安装俯角暂估 **约 26°**（截图红线夹角粗估范围 **25°–27°**）。来源为用户提供的点云截图及人工标注的水平线、倾斜线，用户指定备注为“真人肉眼观测预估值”。该范围仅描述截图夹角粗估，不是实际安装角的测量误差或置信区间；将其理解为雷达俯角须满足侧视、倾斜线代表水平地面的假设，当前视角与轴向尚未核验。仅作为现场参考，不作为已验证外参或配置标定值。原图见 [人工标注截图](evidence/2026-10-01_manual_pitch_estimate.png)。
- 驱动 YAML `extrinsic`：全 0，`use_status: true`；启动日志 Transform Parameters valid:1，全 0。这是驱动内部变换配置，不是外部安装外参。`[源码配置事实]+[本次实测]`
- IMU 与点云共用 frame_id `innolidar`；无独立 IMU frame、无 TF、无 IMU→雷达安装旋转表 → **未验证**。
- 雷达内部标定：由 `calibrate_folder=/root/catkin_ws/src/inno_lidar_ros/config/ifw192s` 加载成功（每轴 49152 项）。`[本次实测]`（K）
- 雷达-相机外参：无相机，暂无对象；已有的 `captures/human_follow_calibration.json` 是单站位距离残差诊断，不是外参。`[源码配置事实]`

## 7. 算力与软件环境（本次实测）

- NPU：设备树 `npu@fdab0000` 与 devfreq `fdab0000.npu` 存在；`/dev/rknpu*` 节点不存在；容器内无 `librknn*`/`rknn_server`。
- GPU：devfreq `fb000000.gpu`；主机有 `/dev/dri/card0,card1,renderD128,renderD129`。Codex 独立诊断确认 renderD128 对应 rockchip-drm，renderD129 对应 RKNPU；不能把两个 render 节点都归为 GPU。无 `/dev/rknpu*` 也不等于没有 NPU 内核驱动。用户态模型运行尚未验证。
- 视频编解码：`/dev/mpp_service` 存在（权限 `crw------- root`）。
- 容器软件：Ubuntu 20.04 + Python 3.8.10 + NumPy 1.17.4；**无 cv2**、无 mediapipe/torch/rknn/python-serial；`rosbag`、`rviz` 可用。
- 串口/外设：`/dev/ttyACM0-3`（wch.cn USB Quad_Serial，CH9344）与 USB CAN-II 适配器在板上存在，当前无进程占用，用途未证实。
- WebUI：`/root/catkin_ws/webui`（three.js，“IFW192S 雷达实时可视化”），经 8090 静态服务 + foxglove_bridge 8765 提供；仅雷达可视化，无相机内容。

## 8. 结论与未验证项

已验证（有日志）：板卡/系统/容器/进程拓扑；三路 ROS 话题类型、短时频率、frame_id 和点云字段布局；六轴 IMU 输出及无效姿态；所采样时间戳数值递增、一帧首点 timestamp=header；链路前后状态与本次 ROS 图无图像/TF。用户明确没有相机；枚举未发现相机只能作为该次快照，不能独立证明物理世界不存在相机。

后续未验证项（已分配工单，不阻塞 HF-01）：

1. “双目雷达”内部硬件形态/型号（后续资料补查；首版只消费已验证的单个点云流）。
2. 设备时钟相对主机/UTC 的映射、漂移与速率比；点云↔IMU 固定偏移（HF-02 用同步采集测量）。
3. SDK `ImuMsg.timestamp` 原始字段单位（闭源 .so；仅能证明发布链路输出自洽）。
4. IMU→雷达安装旋转、外部安装外参（无参数、无 TF）。
5. `abnormal_flag=255` 的语义（消息定义只有 uint8，无枚举说明）。
6. ttyACM0-3 与 CAN 接口的实际用途。

## 9. 证据索引（`docs/human_fall/evidence/2026-09-30_hf00/`）

| 文件 | 内容 |
|---|---|
| `A_host_env.txt` | 板卡/OS/内核/资源、docker、video/iio/usb/ip、进程 |
| `B_host_runtime.txt` | ROS 进程完整参数、systemd、串口、网络、模块、主机无 `/opt/ros` |
| `C_ros_stack_location.txt` | cgroup 证明 ROS 在容器、`docker ps -a`、`/opt` 内容 |
| `D_container_ros_discovery.txt` | 容器 Id/网络/绑定、容器内 OS/包清单/配置目录 |
| `E_container_topics.txt` | ROS 环境、节点列表、话题列表与类型 |
| `F_samples.txt` | 链路未恢复时 0 消息的阻塞证据 |
| `G_config_launch_logs.txt` | `lidar-stack.service`、板上目录、非 git 仓库 |
| `H_runtime_config_log.txt` | 运行 config.yaml、launch、webui、容器 /dev、rknn/python/cv2 |
| `I_host_system2.txt` | `lidar-stack.sh` 全文、eth2、netplan、devfreq、device-tree |
| `J_host_netplan_boot.txt` | netplan 权限、`cam_ircut` disabled、串口属性、webui 页头 |
| `K_container_env_logs.txt` | `/tmp/lidar.log`、CMake 关键项、numpy/pip、查找结果 |
| `L_link_retry.txt` | 链路恢复过程（carrier、IP、路由、sudo 检查） |
| `M_data_check.txt` | ping 结果、点云/IMU/status 的 `rostopic hz` |
| `N_samples_live.txt` | fields/meta/header、IMU 原始 6 条、device_status、消息定义 |
| `O_point_raw_and_calib.txt` | header、标定文件清单、相机/标定查找（含 `rostopic` 切片报错） |
| `P_point_timestamp_probe.txt` | rospy 探针：首/末点 timestamp 原始值与 header 关系 |
| `Q_git_worktree_state.txt` | 分支/HEAD/工作树快照与用户修改 diff |

另：上层 `2026-09-30_host.log` 等为 Codex 前轮 SSH 原始日志，来源已由 Codex 确认；本轮独立 IMU 实测另见 `IMU_VERIFICATION.md`。Q 日志采集时间 13:46:22，属于采集末尾工作树快照；没有本轮执行者开工前快照，不能据此证明完整前后无变化。Codex 前序快照与当前相关源代码差异一致，本次保留此追溯限制。

## 10. 记录完整性与失败命令

A–Q 共 17 件均存在且非空，但不一致保留每条命令原文/外层 timeout/退出码；echo -n 只限制消息数，不能由它证明等待有界。HF-01 必须明确超时并保存退出码。

E 的 head、F 的设备列表、G 的日志尾部、H 的重定向、J 的权限/日志尾部、O 的 PointCloud2 文本格式化均有失败输出。对应成功的后续输出只覆盖已实际补查内容：M 支持出流，N 支持字段，P 支持一帧 header/点时间关系；P 不等于完成 O 原始字节转储。I 所示网络/自启脚本是读取内容，不等于本轮执行了脚本。失败日志保留，不记为通过。

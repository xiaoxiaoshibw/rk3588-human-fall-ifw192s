# 人体跟随距离标定（ROS1）

这个独立包先订阅 `/innolidar_points`，采集静止场景和一个站位目标，写出标定 JSON；之后可用独立节点持续发布人体样目标状态。它不发布 `/cmd_vel`，不驱动车辆，也不修改厂商雷达驱动。只用 ROS1、NumPy 和 Python 标准库。

## 板上运行

把本包放在板上 `/home/wel/slam_localization_wuhan/src/human_follow_calibration`；该主机目录映射为容器内 `/root/catkin_ws/src/human_follow_calibration`。确认现有雷达驱动正在容器中发布点云，然后从板上主机进入容器：

```bash
docker exec -it slam-localization bash
```

在容器内执行：

```bash
source /opt/ros/noetic/setup.bash
cd /root/catkin_ws
python3 -B -W error -m unittest discover -s src/human_follow_calibration/tests -v
chmod +x src/human_follow_calibration/scripts/calibrate_human_follow.py \
  src/human_follow_calibration/scripts/monitor_human_follow.py
catkin_make -DCATKIN_WHITELIST_PACKAGES='inno_lidar_ros;human_follow_calibration'
source /root/catkin_ws/devel/setup.bash
rostopic hz /innolidar_points
rostopic echo -n 1 /innolidar_points/header
rosrun human_follow_calibration calibrate_human_follow.py \
  --known-distance 2.00 \
  --follow-distance 1.50 \
  --output /root/catkin_ws/src/human_follow_calibration.json
```

`rostopic hz` 持续显示频率；看到稳定约 10 Hz 后按 Ctrl-C，再运行后续命令。
原工作区已把 Catkin 构建名单限制为 `inno_lidar_ros`，所以上述构建命令显式加入本包。
结果可在板上主机的 `/home/wel/slam_localization_wuhan/src/human_follow_calibration.json` 查看。

`--known-distance` 是用尺从**雷达原点**量到人体双脚中心的正前方距离，单位米；`--follow-distance` 是另行指定的雷达到人体可见表面的期望跟随距离。先确认传感器的 X 轴指向车体前方，Y 轴左右方向及站位均正确。执行后按提示先让 ROI 内无人，回车采 15 帧空场；再让一人站在标记处不动，回车采 15 帧。机器人全程保持静止，雷达或底盘移动后必须重新录空场。无点云、字段异常、帧时间戳停滞、空场有目标样物体、站位附近有多个候选目标、目标未出现或走动都会失败且不会写结果；远离已知站位的变化不会误判为第二个人。

默认 ROI 是传感器坐标 `x=0.6..6.0 m`、`y=-2..2 m`、`z=-0.2..2.2 m`，排除原点 0.3 m 内的回波。场地不匹配时使用 `--x-min`、`--x-max`、`--y-half-width`、`--z-min`、`--z-max` 调整。`--min-cluster-points`、`--background-cell`、`--background-z-cell`、`--cluster-cell`、`--stand-tolerance` 是检测阈值。可用 `--help` 查看完整参数。使用设备帧时间戳只检查单调递增；雷达时间戳是运行时间，不能和电脑墙上时钟比较。每帧收取超时默认 2 秒。

站位区域外超过半数点落入新背景体素时，程序会拒绝保存并要求重录空场；小幅设备移动仍需现场确认。输出的 `outside_scene_change_fraction` 记录该比例。

## 结果与边界

JSON 包含 `sensor_frame`、ROI 和阈值、`measured_target_x_m/y_m`、水平实测 `measured_distance_m`、`measured_bearing_rad`、已知站位 `known_forward_distance_m`、残差、`bearing_offset_rad`、`preferred_follow_distance_m`、有效帧数和 UTC 保存时间。角度偏移等于这个正前方站位的实测方位角。雷达返回的是可见衣物/躯干表面，若卷尺量到人体站位中心或脚中心，实测距离自然可能比尺量距离短；残差只供诊断。单个站位不能解算完整雷达到车体外参，也不能把距离残差当作全距离段的比例修正。

背景是空场前 2/3 帧在 XYZ 网格（各轴每 0.1 m）的占据并集；后 1/3 帧做空场误报检查。人物帧减去背景占据后按 XY 网格聚类，再检查点数、高度、宽度、深度、已知站位距离和跨帧稳定性。这是人工指定目标的静止标定，不是通用人体识别；人与墙、地面同 XYZ 网格时会被扣除，标定前应选择无遮挡站位并检查现场数据。

本包不输出控制命令。后续若接入跟随控制，必须另设点云接收超时、目标丢失立即零速度、下游电机命令看门狗和障碍物避让；不可仅凭这个 JSON 启动车辆。

## 实时状态监测

标定完成后，在**同一雷达安装位置、静止场景**下清空 ROI，再运行：

```bash
rosrun human_follow_calibration monitor_human_follow.py \
  --calibration /root/catkin_ws/src/human_follow_calibration.json
```

按回车后会重新采集 15 帧空场，随后持续订阅标定文件中的点云话题，并把 JSON 字符串发布到 `/human_follow/state`（`std_msgs/String`）。用 `rostopic echo /human_follow/state` 查看。雷达或场景移动后需重启并重新采空场；使用 PCAP 回放时避免时间戳循环倒退。

每条状态有 `status`、`person_present`、`distance_m`、`bearing_rad`、`follow_error_m`、`sensor_stamp_s`：

- `present`：只检测到一个符合人体尺寸的前景簇；距离是目标可见表面回波距离的第 10 百分位，方位已减去站位标定的角度偏移；`follow_error_m = distance_m - preferred_follow_distance_m`，正数表示比期望跟随距离远。
- `absent`：当前帧没有符合条件的目标，`person_present=false`。
- `ambiguous`、`invalid`、`stale`：分别表示多个候选、点云异常、超过 `--timeout` 秒无新帧；此时 `person_present=null`，距离、方位和误差也为 `null`。启动时若空场仍有人，静止人体可能被当作背景，因此采集前必须现场确认无人。

这仍是基于点云形状的“人体样目标”检测，不能证明目标一定是人，也没有跨帧身份跟踪。板端已存在 Three.js 点云 WebUI，经 foxglove_bridge 接收传感器数据；本包的 `/human_follow/state` 尚未证明在该页面接入，不能把点云显示当成本包人体检测结果。新目标由独立 human_fall_detection 包在 RK3588 实现，现有 WebUI 扩展人工选人、位置/站姿基线、自动跟踪框与跌倒状态，详见 [WEBUI_SCOPE.md](../../docs/human_fall/WEBUI_SCOPE.md)。旧接口保持原义。

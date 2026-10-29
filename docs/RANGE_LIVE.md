# RK3588 实时距离图旁路

本地开发入口：`src/human_fall_detection/scripts/range_image_node.py`。
ROS1 + Python 3.8 + NumPy；独立订阅原始点云，只发布距离图及诊断，不运行人体/跌倒判定，不接管生产节点，不写原始数据。2026-10-26已在RK3588隔离临时目录完成短时真实ROS验证，验证进程已退出，未安装常驻服务或接入Qt/Web。

## 转换

`PointCloud2 → 按字段/字节序/point_step/row_step读取 → 一次规范化打包 → ScanGrid.decode → 图像消息`。

- 支持驱动的26字节点及带额外字段的更长点记录、组织点云行填充、大小端。XYZ/强度必须float32，ring必须uint16，timestamp支持float32/float64；缺失或不支持的字段、重叠、越界、长度错误会明确拒绝。
- 方向表启动加载一次，按ring及标定方向匹配；保留原ScanGrid的方向容差、最近回波/等距最小源行规则。不是按接收顺序reshape。非有限/零点不在适配层删除，source_rows仍能反查原PointCloud2行优先展平后的点索引。
- 适配复用离线ROW_DTYPE，因此逐点timestamp降为float32，不能用于精确物理同步；源帧header的整数秒/纳秒、seq和frame_id保持。转换不推断时间戳单位，不修改驱动。
- 内部算法保留原生浮点距离；发布32FC1时才转float32。各图与离线v2一样旋转180度，无补洞。反查原生栅格：`native_row=height-1-image_row`，`native_col=width-1-image_col`。
- CPU/NumPy转换，不使用NPU、OpenCV、PNG压缩或逐帧磁盘写入。启动时需显式提供两份方向表及预期原始传感器frame_id；这些声明不证明物理安装/人体效果。

## 板端运行命令

在现有ROS1环境中，从仓库根目录运行独立进程：

```bash
python3 -B -W error src/human_fall_detection/scripts/range_image_node.py \
  --azimuth-table src/inno_lidar_ros/config/ifw192s/ifw192s_azimuth_192x256.csv \
  --elevation-table src/inno_lidar_ros/config/ifw192s/ifw192s_elevation_192x256.csv \
  --frame-id innolidar --preview
```

`--topic`默认`/innolidar_points`；`--output-prefix`默认`/range_image_live`；`--max-age-s`默认0.5秒。不加`--preview`时省去RGB着色/打包。脚本已登记catkin安装列表；尚未做ROS构建/安装，已在板端现有ROS环境以独立Python进程实际收发。

| 输出后缀 | 格式 | 数值/用途 |
| --- | --- | --- |
| `/range` | sensor_msgs/Image，32FC1 | 径向距离，米；无回波NaN，并非相机Z深度 |
| `/source_rows` | Image，32SC1 | 原始消息点索引；无回波-1，用于恢复对应3D点 |
| `/valid` | Image，mono8 | 有效255、无效0；不是人体mask |
| `/preview` | Image，rgb8，可选 | 红近蓝远，0.1–8米截色，缺测黑；不参与算法 |
| `/state` | std_msgs/String，JSON | 同帧源header、标定SHA、状态、计时与计数 |

图像保留同一源header，queue_size=1、不latch。消费者按完整header和grid_sha256关联图像/源点云，不能将各topic最近一条直接混合。32FC1与source_rows分别需约196608字节，valid需49152字节，可选RGB需147456字节；算法可直接在同进程消费RangeFrame，避免为内部消费绕行ROS图像传输。

ROS1 `rospy.msg.serialize_message`默认会改写带header消息的seq为本topic发布计数。节点使用继承Image线格式/type/md5的本地SourceImage类，设置`_has_header=False`仅阻止此处改写，不改变消息定义或ROS库。首轮真实收发暴露了该问题；修后已通过板端实际序列化器回归及真实四图/源点云完整header匹配。升级ROS客户端实现时应重跑该测试。

## 队列、异常及计时

回调只保留最新一个待处理消息；单worker在主线程计算。`queue_overwritten`只统计进程内待处理帧覆盖，不包含ROS/驱动/网络上游丢帧。`received`为进入回调的消息数。排队及转换完成时各检查一次本地接收年龄，超过max-age不发布图像，报告`expired`。布局/坐标frame不合法报告`invalid`；空消息/全无效回波发布明确的NaN/-1/黑图，状态`no_valid_pixels`。无新结果时每约0.5秒发心跳，超时`stale`。

消费者收到invalid/expired/stale须清除或遮蔽旧图；旧Image不会被重发，也不会因最后一张仍可见就成为有效观测。消费者自身还应对state断流设置超时。该入口仅转换，重复header不被伪装成新源帧；不建立人体跟踪身份。

`adapt_ms`、`decode_ms`、`image_pack_ms`、`conversion_ms`分别记录消息适配、标定转换、图像缓冲构造和合计；`queue_age_ms`、`local_frame_age_ms`使用本机perf_counter，不与设备时钟相减。`publish_enqueue_ms`只覆盖Image发布调用返回，不含state发布、ROS异步发送、网络或绘制，不能宣称端到端延迟。板端转换P95≤20ms是本阶段优化目标；首次实测未达到，见下文。

## 本地验证

```powershell
python -B -W error -m unittest discover -s src/human_fall_detection/tests
python -B -W error pc_apps/range_fall/live_replay_check.py --session data/sessions/cap_20261018_110029 --reference docs/evidence/2026-10-25_depth_fallen/oriented386 --out docs/evidence/<new_run> --rounds 3
```

追加`--paced`按源帧时间在生产线程送入同一个最新帧队列，实际消费帧逐帧对照；它是本地消息替身仿真，不是板端ROS性能。检查器将已有会话重新封装为26字节驱动布局，和离线ScanGrid的距离/索引/有效像素零容差对照，可再对历史PNG预览逐字节检查。计时排除读盘、驱动消息重封装、参考计算、PNG证据生成、ROS序列化/网络/页面；前10个源索引作为预热单列排除。证据见`docs/evidence/2026-10-26_range_live/`。

## 2026-10-26 RK3588真实ROS验证

用户明确授权板端验证后，将44份源码/方向表文件约248KB压缩包放在容器`/tmp/ldiar_range_live_*`独立目录，使用独立ROS节点名和话题前缀。没有安装服务、覆盖现有release或改驱动/网络/配置；仅停止本次创建的子进程，临时目录及结果保留。

- 环境：aarch64 / Python3.8.10 / NumPy1.17.4 / ROS Noetic，CPU governor=ondemand。两方向表SHA与本地一致。
- 板端15项测试在`-B -W error`下全部通过，包括实际`rospy.msg.serialize_message`的源seq与Image线格式回归；PC核心793项完成，1项实际ROS序列化测试本地跳过、已在板端通过。
- 约30秒观察窗：新节点收到282帧、处理282帧、四图和状态各收到282条，完整header关联282帧；内部覆盖/失效/过期均0。抽查14帧的距离float32、源索引、有效图及RGB全部逐像素一致。原始点云旁路观察在前/中/后约9.662/9.651/9.664Hz，seq缺口0。节点启动及注册前的输入不计为输出丢帧，也不据此声明长时零丢帧。

| 预热后272帧，ms | P50 | P95 | 最大 |
| --- | ---: | ---: | ---: |
| 消息适配 | 2.726 | 6.945 | 15.649 |
| ScanGrid转换 | 16.182 | 22.945 | 49.923 |
| 四图打包，含RGB | 4.384 | 5.787 | 13.962 |
| 转换合计 | 23.788 | 32.770 | 69.995 |
| 本地接收到转换完成 | 24.057 | 32.976 | 70.187 |
| 四图发布调用 | 0.510 | 0.836 | 1.382 |

各阶段分位数不能相加。当前短窗可跟随约103.664ms源间隔，**P95≤20ms优化目标FAIL**；NPU未使用，长期稳定性及设备采集/跨网络/PC显示端到端仍UNKNOWN。

验证前后驱动/桥/识别PID和两份受查配置SHA一致，无验证进程残留。既有识别节点在前/中/后均input_valid=true、unselected/unknown；其原有处理较慢、内部丢帧计数继续增长，不能将新转换链零覆盖写成整套识别零丢帧。观察数据见PRODUCTION_COMPARISON，不据单次自然场景窗口宣称性能等价或改善。

真实ROS连接/退出时出现`rospy/impl/masterslave.py`及socket清理的ResourceWarning，首次只读订阅预检也能复现；`-W error`在析构路径打印Exception ignored，子进程仍退出0。这些告警已保留，未抑制/修改ROS库；真实收发的像素契约通过，但不能声称运行无告警。证据：`docs/evidence/2026-10-26_range_live_board/`（失败run01、修后run02、BOARD_UNIT_TESTS_FIX、CORE_TESTS_FIX、POSTFLIGHT及现场PNG）。

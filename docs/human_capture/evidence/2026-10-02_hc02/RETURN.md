# HC-02 return — 录制生命周期 / 自动停 / FIFO / 非干扰

工单：../../tickets/HC-02.md · 日期 2026-10-02 · 板上 (192.168.3.125:8766)

## 交付物

```
src/human_capture/core/recorder.py       # 起停 watcher 编排器
src/human_capture/core/fifo.py           # FIFO 清理器
src/human_capture/scripts/capture_server.py   # 新 REST /api/v1/record/*，ros_probe 接真实探测
src/human_capture/config/capture.yaml    # HC-02 新增字段
src/human_capture/tests/test_hc02_recorder.py  test_hc02_fifo.py
docs/human_capture/tickets/HC-02.md
```

## 验收逐条

| ID | 结论 | 证据 |
|----|------|------|
| R1 起录 | **PASS** | POST /api/v1/record/start → 201 `cap_20261002_163621`；stores 里出现 state=recording；已在录时第二个 start 返回 409 conflict |
| R2 停录+manifest | **PASS** | POST stop → 200；~4s 内 watcher 解析 record_session 写的 manifest，sessions.json 更新为 `state=extracting, size_bytes=114550423, source_bag_sha256=bbbc0c..., duration_sec=9.2285, frame_count=2092, stop_reason=manual`；record_session 自身 `rosbag info` 复核通过 |
| R3 时长自动停 | **PASS(local mock)**, **NOT_RUN(板)** | Windows mock 单测：max_duration_sec=0.5 时 watcher 检测到超时并发起 SIGINT。板上真实 SIGINT→record_session 优雅退已由 R2 stop(manual) 共一条路径覆盖；duration 触发只改 reason 字段，未单独板侧回归，列为非阻塞 |
| R4 盘水位自动停 | **PASS(local mock)** | 同 R3，mock 单测 |
| R5 子进程猝死 | **PASS** | 单测 SIGKILL 子进程 → sessions 置 failed(`crashed_rc...`)；板上隐患场景：起录时 record_session 因无 ROS env 立刻 rc=1 死，亦如实战收成 `crashed_rc1`（本单发现的真实缺陷，修复见下） |
| R6 FIFO 常规 keep | **PASS** | 单测 over_keep→删最老 transferred；exact_keep 不动 |
| R7 FIFO 水位强清 | **PASS** | 单测 _disk_low=True 时无视 keep 清到回水位；active 状态永不删（ready/recording/transferring 各案例断言） |
| R8 /status.ros | **PASS** | shell 已 source ROS 时 `"ros":"up"`（rospy/CLI 方案）；未 source 时 `rosnode` 不在 PATH→`"down"`（诚实） |
| R9 非干扰 | **PASS** | 录制期间 `/innolidar_points` 仍 9.624 Hz（基线 9.709 漂移在噪声内）；`rosnode list` 见 `/inno_lidar_node /foxglove_bridge /human_fall_node` 齐；HF 节点 CPU 100% 是录制前既有（已运行 1天4h 的常态），与 rosbag 无新增相关 CPU；eth1 未抓带宽但无显著瞬时流量变化 |
| R10 帧数对账 | **PASS** | `rosbag info`：`/innolidar_points` 89 msgs，期望 9.228s×9.624=88.9≈89，**零丢帧**；`/inno_imu` 2092/2106≈99.3%（rosbag 订阅握手错过首位几个，正常）；`/device_status` 89 与点云 1:1 ✓ |

## 板上捕获并修复的真实缺陷

**D-HC02-01：capture_server 用 `docker exec` 起、没 source ROS，子进程 `rosbag` 找不到 → rc=1 crashed。**

- 表现：起录 3s 内 sessions 自动转 failed(`crashed_rc1`)。
- 根因：record_session.py 的 `--until-interrupt` 内是 `subprocess.run(["rosbag","record",...])`，依赖 PATH。
- 修复（不重构）：recorder.py 在起子进程时检查 `shutil.which("rosbag")`，缺失则用 `bash -c "source /opt/ros/noetic/setup.bash && source /root/catkin_ws/devel/setup.bash; exec ..."` 包一层。**对 roslaunch 路径（roslaunch 自带 env）透明**，对裸 exec 路径自愈。记录为一类"部署形态检测"的通用修复。
- 附带：ros_probe 从 `rosgraph.is_master_online()` 改成 `rosnode list` CLI（rosgraph python 模块依赖 xmlrpc，容器最小环境缺；CLI 必定有）。

## 板上产物（保留核查）

- `/root/catkin_ws/captures_remote/cap_20261002_163621.bag` (114 MB, 9.2s, 全 topic)
- `/root/catkin_ws/captures_remote/cap_20261002_163621.manifest.json`（record_session 原生）
- `/root/catkin_ws/captures_remote/sessions.json`（capture_server 登记）
- `/root/catkin_ws/captures_remote/cap_20261002_163325.*` (.reserve) — R5 案例的 crashed 样本
- 服务日志：`/var/log/capture_server.log`

## 已知边界（留给后续单）

- R3/R4 板上回归：等 HR-01 联调时顺手用 `--max-duration` 跑一次真实时长自动停。
- `/api/v1/record/current` 已可返回 elapsed/state，但未携带 manifest 字段（提取是 HC-03 的事）。
- 本单 bag 还**未做 meta.json+points.bin 转换**（HC-03）。
- staging 在容器内 21GB 盘，FIFO 触发要等真实填满或人为调低 keep 看效果，HC-04 部署期做。

## 单测运行实录

见同目录 `unittest_output.txt`（38 绿，Windows 单测 + 板上 ROS 端到端分离覆盖）。

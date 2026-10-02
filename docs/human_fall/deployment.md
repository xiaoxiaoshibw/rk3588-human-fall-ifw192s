# HF-07 / HF-11 部署、配置与回滚

日期：2026-10-01。适用：RK3588 (aarch64)、容器 `slam-localization`（Ubuntu 20.04 / Noetic / Python 3.8.10）。
所有算法在 RK3588 运行；浏览器只做交互/显示；不发布 `/cmd_vel` 等控制量。真实外参/地面/人体标签与
真实 IMU 单位/轴向/安装**均未验收**，`confirmed` 默认关闭，页面不会因此判故障或停雷达。

当前活动版本：`20261001T051310Z`（2026-10-01），PID26591，版本bundle/清单与本地关键源码完全匹配；操作前实时核对PID。正式URL：<http://192.168.3.125:8090/human_fall/index.html>，点连接。算法仍使用完整`/innolidar_points`，网页只读`/human_fall/display_points`最多12000点，实际ROS1wire序号与原始header显式映射。录制当前显示流不等于全量bag。旧首页和driver保留；最终软件/证据与剩余真人条件见[HF10](returns/HF-10.md)。

生命周期命令在容器内先source Noetic和`/root/catkin_ws/hf07_verify_ws/devel/setup.bash`，再执行`bash /root/catkin_ws/hf07_verify_ws/src/human_fall_detection/scripts/deploy_human_fall.sh status|stop|start|rollback <版本>`；release保存完整代码/config/冻结解码器与页面，start/profile先验证清单，错误PID/旧无bundle版本拒绝。冻结解码器从隔离WS的同哈希副本获取，原板静止标定脚本不覆盖。

## 1. 构建与安装

```bash
# 在目标工作区内，不运行会改写厂商 manifest 的顶层脚本
source /opt/ros/noetic/setup.bash
catkin_make -j4              # devel; 可选 catkin_make install
source devel/setup.bash
```

包 `human_fall_detection` 通过 `catkin_python_setup()` 安装纯 `core` 包（`setup.py`）。
`core/__init__.py` 的路径引导使用 `core.__path__` 定位真实源码 `core`（devel 下由 catkin relay 扩展）并加入其
`../scripts`；仅当找不到源码 scripts（真正的 install 布局）时才回退到 `<prefix>/lib/human_fall_detection`。
因此 source/devel/install 三种布局都能从任意 cwd `import core`，无需手工 `PYTHONPATH`。复用冻结的
`scripts/sensor_health.py`，不复制、不修改。

依赖：`rospy / sensor_msgs / std_msgs / inno_lidar_msg`，运行期 `human_follow_calibration`（点云解码）、NumPy、PyYAML。

## 2. 节点启动

```bash
source devel/setup.bash
# 方式一：launch（配置/话题/输出目录可参数化）
roslaunch human_fall_detection human_fall.launch config:=.../human_fall.yaml perception:=.../perception.yaml
# 方式二：rosrun
rosrun human_fall_detection human_fall_node.py --config <human_fall.yaml> --perception <perception.yaml>
```

- 节点：订阅 `/innolidar_points`、`/inno_imu`、`/device_status`、`/human_fall/selection_request`；
  发布 `/human_fall/candidates`、`/human_fall/state`、`/human_fall/event`、`/human_fall/selection_ack`。
- 配置：`config/human_fall.yaml`（话题/超时/跳变阈值/几何标定路径/输出目录/`mode.replay`），
  算法阈值在 `config/perception.yaml`。**不改** HF-01 冻结的 `config/default.yaml`、`health`/manifest。
- 必需点云：缺失/非法 stamp/layout 解不出时该帧不进入有效候选/观测；`mode.require_ground=true` 时
  无有效地面则启动失败，默认 `false` 为“明确等待”（候选以未标定雷达坐标发布，`observability=degraded`，
  跌倒状态 `unknown`）。

### 地面 / 标定

- `geometry.calibration_path`：HF-03 `geometry_calibration` JSON（推荐，使用其 `ground` 与 `calibration_id`）；
  或 `geometry.ground_path` 直接给地面平面 JSON。两者之一配置后按文件校验；已配置但无效会启动失败，不静默降级。
- `geometry.background_path`：显式空场 `candidate_background` JSON（可选）。

## 3. 操作流程（网页 = HF-11）

0. 正式页 `http://<board>:8090/human_fall/index.html`（默认 `prefix=/human_fall/`、点云 `/innolidar_points`，
   复用 `../three.min.js` 与 `../OrbitControls.js`）；隔离预览页保留在 `human_fall_preview/`，两者互不影响。
   旧首页 `http://<board>:8090/index.html` 从未替换（保留部署前哈希与多份 `.bak-20260930`）。
1. 浏览器打开正式页 `http://<board>:8090/human_fall/index.html`（活动页面 `index.html` 不受影响）。
2. 点“连接”（默认 `ws://<board>:8765`）。页面读取 bridge `serverInfo`，`clientPublish` 可用时自动声明
   `/human_fall/selection_request` 通道。
3. “选人模式：开”，在点云上拖框（拖框时不旋转视角）或点右侧候选；板端回执接受后才锁定。
4. 锁定后按“采集站姿基线”；板端在稳定实测下完成（质量不足会 `failed`，页面显示状态与版本）。
5. 页面实时显示目标框/位置/距离/坐标、跌倒状态与事件历史；“解除目标”清目标（不删历史事件）。

## 4. 默认门控与安全边界

- `fall.mode_verified=false`、`fall.allow_confirmed=false`：线上不产生 `confirmed`，最高 `suspected`。
  合成/夹具可在测试中显式开启，不作为真机验收。
- 不发布运动控制；不引入 ROSBridge/MQTT/新网站/模型库；网页不跑跌倒算法。
- 事件 JSONL 持久化到 `output.session_dir/events.jsonl`；磁盘失败在状态中标记 `event_persistence.degraded`，
  不假装保存成功；重启加载历史，不把旧事件重发为新事件。

## 5. 回放

`human_fall_node.py` 是实时 ROS 节点，回调/worker/请求处理**始终**使用同机 `time.monotonic`；
`config/human_fall.yaml` 设 `mode.replay=true` 会被明确拒绝（不会伪标消息时钟），离线消息时间回放请用
`scripts/fall_replay.py`（显式 source/message 时间域）。节点在每帧解码/计算后再读一次 monotonic，
若该帧已超过 `cloud_stale` 只发布 stale/unknown 状态，不发布会过期候选、旧正常状态或新警报；
请求在取得 core 锁后再取当前 monotonic 判定新鲜度。持续时间一律设备源秒，回放暂停不折算成物理低姿态时长。

## 6. 可回退部署（版本保留，不删目录）

节点/页面由 `src/human_fall_detection/scripts/deploy_human_fall.sh`（容器内运行）管理。版本保留在
`/root/catkin_ws/human_fall_deploy/releases/<UTC>`，`current` 与 `webui/human_fall` 是指向某版本的符号链接；
回滚只重指链接，**从不删除任何 release**，也不 `rm -rf`、不 `pkill`：

```bash
# 容器内（先 source /opt/ros/noetic/setup.bash 与 /root/catkin_ws/hf07_verify_ws/devel/setup.bash）
D=/root/catkin_ws/hf07_verify_ws/src/human_fall_detection/scripts/deploy_human_fall.sh
bash $D release          # 新建版本：存不可变代码 bundle(core/scripts/config+冻结解码器) + 正式页，更新链接
bash $D start            # 从 current 的 bundle 启动正式节点，写 pids/human_fall_node.pid/.cmd
bash $D status           # 显示节点/测量进程与页面链接
bash $D rollback         # 回滚到上一个含 bundle 的 release 并重启
bash $D rollback <stamp> # 回滚到指定 release（无 bundle 的旧版本被明确拒绝）
bash $D stop             # 仅按 pidfile 停止并校验 cmdline，绝不泛 pkill
```

- **不可变 bundle**：`release` 把 `core/`、`scripts/`、`config/` 与冻结解码器
  `human_follow_calibration/scripts/` 复制进 `releases/<stamp>/bundle/` 并写 `manifest.sha256`；`start`/`profile`
  用 `PYTHONPATH=<bundle>:<bundle>/scripts:<bundle>/human_follow_calibration/scripts:...` 只从 bundle 加载
  `core` 与节点，并显式校验 `core.__file__`/`sensor_health.__file__` 位于该 release（否则拒绝启动）。
  devel 工作树仅提供 rospy/inno_lidar_msg 等 ROS 依赖，不再提供算法代码。
- **精确停止**：pidfile 记录 `node 路径|config 路径`；kill 前校验 `/proc/<pid>/cmdline` 同时包含二者，
  不匹配则拒绝并非零退出，绝不 `pkill`、也不会在停止失败后再起第二个同名节点。空 cmdline 的 zombie 视为已停。
- **manifest**：`bundle/manifest.sha256` 生成时排除自身、`__pycache__`、`*.pyc`（内容稳定）；`start`/`profile`
  先 `sha256sum -c` 校验清单再导入，失败拒绝启动。
- **profile 生命周期**：profiler 的 pidfile 另记 `profile.cmd`（精确脚本路径|输出 JSONL 路径），停止按该 cmd 校验；
  已有存活 profiler 时拒绝再起，避免两个 observer 写同一文件；只清理本任务自己的 PID 文件。
- **原子 release**：先建 `.tmp` 并校验 bundle 导入，成功才 `mv` 并重指 `current`/`webui/human_fall`
  （切换前校验两者是符号链接）；失败不留半部署。
- **回滚**：仅重指链接、保留所有历史 release；无 bundle 的旧版本拒绝代码回滚，指针不变。
- 合成验证进程另用 `evidence/.../hf09_stop_synthetic.sh` 精确匹配 `hf07_verify.yaml` 或记录的 PID 后停止。
- 驱动 `inno_lidar_node`、网络、自启、厂商库全程未改、未重启；雷达源保持活动。
- 页面回滚：`webui/human_fall` 重指上一版本目录即可，旧首页 `webui/index.html` 与 `human_fall_preview/` 不动。
- 实际两版本验证：start(C bundle)→rollback(B bundle)→start，节点/页面/`core.__file__` 均指向所选 release；
  legacy 回滚 exit=6；PID 指向 driver 时 stop exit=1 且 driver 存活（见 `evidence/.../hf09_board_checks_r2.txt`）。

## 6b. 浏览器帧对齐与候选投影（HF-09 R2）

- **候选 ROS 投影**：节点在 `/human_fall/candidates` 上用 `project_snapshot_for_ros()` 发送**新 dict**，
  去掉网页不用的每候选 `evidence_indices`（真实帧 5025 点/4 候选：34424 B → 5296 B，**-84.6%**），
  保留 source/session/epoch/candidate_id/center/box/point_count/quality；纯算法/选择缓存与离线证据不变（未原地 pop）。
- **原始帧缓存+呈现**：页面缓存最近 **8** 帧原始点云 payload；只呈现“最新已有处理输出的源帧”（前向、不回退，
  无输出>800ms 回退最新 raw 仍显示点云+unknown），避免把旧框画到最新场景。session/epoch/网络切换清缓存，
  过期源帧隐藏框，不持续保留旧绿色状态。raw 接收 Hz 与“呈现 Hz/未呈现”分开统计。
- 未新增前端框架、无无界缓存、不改 driver/桥参数。

## 6c. 只读可视化抽样流（HF-09 R3）

- 授权备选已实施：节点新发布**只读** `/human_fall/display_points`（`visualization.enabled=true`，stride=4，
  max_points=12000）。算法仍订阅全量 `/innolidar_points` 并完成解码/候选/跟踪；只对“显示包”按 `point_step` 整点抽样，
  字段/XYZ 单位/端序/坐标不变，organized 行用 `row_step` 处理 padding；非法/空布局不发布（不伪造显示云）。
- **wire header 映射**：rospy 发布时会重写 `header.seq` 为本 topic 序号（已用探针证实），故不能复制源 seq。
  节点 publish 抽样包后从返回消息读回真实 wire seq，连同 `source_topic`（实际原始云话题）、`source`（原 seq/sec/nsec）、
  `topic`(display)、`wire_seq`、`stride`、原/显示点数随 candidate/state 的 `visualization` 块提供。
  真实订阅探针 60/60 帧 `wire_seq+source stamp` 完全匹配。
- **前端严格守卫**：`objectKeys(obj, selectedTopic)` 按所选 topic 显式隔离——选 `visualization.source_topic` 只回 S 键
  （支持 `?points=/innolidar_points` 全流诊断），选 `visualization.topic` 只回 D 键且要求 mapping.source 与对象 self source
  一致，其他 topic 或 source 错配返回 `[]`；无 mapping 的旧/synthetic 消息保留 S 键。前端所有匹配传实际 `POINTS_TOPIC`。
- 页面默认订阅显示流；统计改名“显示流/呈现/未呈现/抽样/帧龄(接收后)”，raw 接收与呈现分开；呈现 `rxMs` 用原包
  浏览器接收时刻（monotonic），另存 `presentedAtMs`，不把帧龄重置或称为端到端时延；断流/未知 schema/旧 epoch 清缓存。
  录制提示明确“抽样显示流录制≠原始全量 bag”。源 topic 与显示 topic 均只读，不改算法/driver/标签/confirmed。
- 原始点云 ~9.4MB/s 仍是主要带宽；抽样显示流显著降低浏览器侧带宽，实际效果由 Codex 正式页长于 1 分钟复测。

## 7. HF-09 性能测量（仅测量交付，非验收）

- 节点可选 `output.performance: true` 在 `state` JSON 内附加 `performance` 块（node 自身 monotonic
  `receive_s/process_start_s/process_finish_s/process_s/queue_age_s/receive_to_finish_s`、`frame_count`、
  `queue_dropped`、`input_valid`、`suppressed`、`ground_valid`、`fall_status`、`mode`）。默认关闭，
  **不改算法**，不改 HF-01 冻结 health/manifest；不加新话题。
- `scripts/profile_pipeline.py` 为只读 observer：以 `(session_id,time_epoch,seq,secs,nsecs)` 去重后读取
  上述 node 自报时间，得到真实处理 p50/p95 与队列延迟；`queue_dropped` 用 `LatestFrameQueue.dropped`
  而非输入减输出猜测；另记 CPU/RSS/温度（缺失记 `null`）。observer 的“到达→state”差单独命名，绝不当处理延迟。
- 启动：`bash $D profile 1800` → 写 `releases/<stamp>/profile_rows.jsonl` 与 `profile_summary.json`。
  仅有限统计，不录原始 bag。帧率/延迟是 RK3588 节点真实值；不含网络/浏览器/publish 序列化。
- 真实地面/外参/人体标签/冻结性能门槛均未验收：无地面则 `observability=degraded`、`fall_status=unknown`，
  不伪造地面；报告只作测量，不标 ACCEPTED。浏览器 FPS/到达间隔与设备源时间不混算成端到端延迟。

### 实测（live / 2026-10-01，30 分钟有限统计）

只读 observer 附在正式节点进程上连续采集 1800 s（见 `evidence/2026-10-01_autonomous_hf09_r1/profile_summary.json`、
`profile_rows.jsonl` 180 个 10 s 窗口）：

- 输入 `/innolidar_points`：17365 帧 @ **9.647 Hz**；有效处理 **15693 帧 @ 8.718 Hz**（全部 input_valid，
  0 invalid；`/human_fall/state` 与 processed 一一对应，0 重复、0 坏 JSON、0 未知 schema）。
- 节点自报处理延迟（decode+compute，同机 monotonic）：**p50 75.6 ms / p95 146.1 ms**；
  `receive→finish` p50 137.9 / p95 207.3 ms；`queue_age` p50 50.0 / p95 90.5 ms。
- 队列覆盖计数 `LatestFrameQueue.dropped` 累计 **4122**（节点自启用以来累计值，非本窗口增量）；
  observer 输入减处理差（1673）只作观测缺口，不当作丢帧。
- CPU ≈ 103 %（约 1 核）、RSS ≈ 86.8 MB、温度 ≈ 51 ℃；内存/温度有增长或热降频需更长时间序列另测。
- 分类：`ground_unavailable` 15693、`fall unknown` 15693（无真实地面，不伪造）；无 suppressed 帧。
- 未含网络/浏览器/publish 序列化；observer 的“到达→state”差 p50 159 ms 仅作次要参考，绝不当处理延迟。

**结论/边界：真实标签、真实地面/外参与冻结性能门槛均 NOT_VERIFIED；以上只是测量交付，不构成性能 ACCEPTED。**
处理率低于输入率（8.7 vs 9.6 Hz）与累计 queue drop 说明当前单核几何链在 10 Hz 输入下接近饱和，
后续优化（若做）需先回传 Codex 复审，不得直接覆盖活动版本。

### 运行版本（2026-10-01）

- 板：aarch64 RK3588，容器 `slam-localization`（ROS Noetic、Python 3.8.10、NumPy 1.17.4）。
- bridge：`ros-noetic-foxglove-bridge 0.8.4`，`foxglove_bridge` 监听 8765；静态页 8090（`python3 -m http.server`）。
  页面用 bridge `serverInfo`/`clientPublish` 声明 `/human_fall/selection_request` 写通道；算法只在板端。
- 驱动二进制未变（`.../inno_lidar_ros/inno_lidar_node`）；正式节点源码/配置哈希与 release 见 HF-09 证据。

# 生产链 / 演示链 / 现场试用链：差异、复现与“实时”评测检查

本文描述仓库内可复现的源码与**已部署的现场试用版**。板端操作遵循
`AGENTS.md` 的驱动/网络/数据边界；现场操作手册见
[FIELD_TRIAL_OPERATIONS.md](FIELD_TRIAL_OPERATIONS.md)。

## 1. 三条链

### 生产链（保持诚实降级）

| 项 | 内容 |
|---|---|
| 入口 | `roslaunch human_fall_detection human_fall.launch` → `scripts/human_fall_node.py` |
| 配置 | `config/human_fall_prod.yaml`（ROS 话题、超时、输出、performance）；感知阈值 `config/perception.yaml` |
| 目标模式 | 默认 `manual`（没有 `target_mode: automatic`）；不自动选人 |
| 地面/背景/标定 | `ground_path: null`、`background_path: null`、`calibration_path: null` |
| 结果 | 节点等待有效地面；没有绑定时保持 degraded/unknown，不伪造地面 |
| 区域 | 生产入口不挂 `LiveRegions` |

生产链的 null 不是遗漏，而是“没有经过验证的现场地面/背景工件”时的诚实状态。

### 演示/离线链（仓库内可复现）

| 项 | 内容 |
|---|---|
| 入口 | `src/human_fall_detection/scripts/single_target_node.py` |
| 配置 | `config/single_target_scene_v1.yaml` + `config/perception_single_target_v1.yaml` |
| 目标模式 | `target_mode: automatic`（共享 `TargetAcquisition`；语义仍是 `unknown`） |
| 地面/背景 | `config/single_target_scene_20261019/*.json`（`physical_validation: UNKNOWN`） |
| 区域 | 注入 `LiveRegions`，用同一实测目标来源行输出 `target_ground_v1` |

`single_target_node.py` 同时是**现场试用版的节点入口**；区别只在配置由现场 profile
生成，而不是直接用仓库示例。

### 现场试用链（2026-10-20 起）

| 项 | 内容 |
|---|---|
| 发布包 | `prepare_single_target_bundle.py` 生成的唯一标准 tar（repo 相对布局，逐文件 SHA） |
| 控制器 | `deploy_human_fall.sh`：`stage / preflight / activate / profile-init / verify-input / probe-scene / start / restart / stop / status / version / health / rollback / runs` |
| 生效绑定 | `human_fall_deploy/current` 符号链接（代码+页面），`state/binding.json` 记录 release/page/profile |
| 配置 | 现场 profile（`profiles/<site>/profile.json`）→ `release_config.py` 生成 `effective_node.yaml` / `effective_capture.yaml` / `runtime.js` |
| 输入来源 | `verify-input` 读真实驱动进程；`live_lidar / pcap / unknown` |
| 页面 | `http://<board>:8936/human_fall/`，`runtime.js` 绑定同一有效配置 |
| 运行记录 | `runs/<run_id>/run_events.jsonl`（含 `suspected_notification`、30 s 性能窗口） |
| 部署根 | `/root/catkin_ws/human_fall_deploy`（当前 release `666ad0eb40a64d4d`，RC15，selected=running） |
| 当前 profile | `site_lab_20261020_v2_displayfix_r1` / `scene_lab_a_v2`，地面/背景沿用 v2，仅修显示标定 ID；物理标志保持 false |

2026-10-20 配平修复现场应用：页面与节点 ID 同为 `ground-only-4a6062deb6a80d1d`，
用户刷新后确认“配平候选 · 未物理验证”；实时 RAW/state/抽样帧按 visualization 映射关联
通过。旧 RC14/profile v2 保留，见 `docs/evidence/2026-10-20_display_ground_binding_deploy/`。

算法没有分叉：三条链共用 `core/` 的候选、获取、跟踪、基线、跌倒与区域代码；差异只在
配置、输入绑定和运行壳。现场 release 的算法配置 SHA 记录在 `RELEASE.json`
（`single_target_scene_v1.yaml` / `perception_single_target_v1.yaml`）。

## 2. 本地复现（不启动 ROS、不部署）

```powershell
python -B -W error src/human_fall_detection/scripts/prepare_single_target_bundle.py `
  --out docs/evidence/<date>_<topic>/human_perception_release.tar
```

bundle 保留 repo 相对布局：`src/human_fall_detection/{core,scripts,config,launch}`、
`src/human_follow_calibration/scripts`、`src/human_capture/{core,scripts,config}`、
`sidequests/hfus_tcms_02/realdev/current/{project_regions,project_dependencies,region_runtime}.py`、
`r08/calibrate.py`、`docs/human_capture/evidence/2026-10-09_hrskeleton_offline_r1/{skeleton.py,prototype_params_v1.json}`、
`webui/human_fall/*` 与 `webui/{ui.css,three.min.js,OrbitControls.js}`。
`MANIFEST.json` 记录每个文件 SHA；`RELEASE.json` 记录 `release_id`、`page_version`、
算法配置 SHA 与 `file_count`。页面脚本的 `?v=` 在打包时改写为内容哈希，
`hf-page-version` meta 同时写入，所以浏览器不会拿旧 JS 解释新状态。

打包时若页面缺少可改写的 `?v=` 或共享静态资源缺失会直接失败，不会产出“能装但跑不起来”的包。

本地跑节点（需要 ROS 环境；不构成部署）：

```bash
python3 src/human_fall_detection/scripts/single_target_node.py \
  --config src/human_fall_detection/config/single_target_scene_v1.yaml \
  --perception src/human_fall_detection/config/perception_single_target_v1.yaml
```

配置优先级：显式 `--config/--perception` > ROS `_config:=`/`~config:=` > 包内示例默认。
wrapper 会发现 `_config:=` 后**不再**注入默认值；同时默认补
`__name:=single_target_live`，不再需要手工传 argv。

## 3. 采集服务

* `record_script` 由 `release_config.py capture` 改写为**当前 release 内**的
  `.../bundle/src/human_fall_detection/scripts/record_session.py`，不再指向可变工作树。
* 服务注册 `SIGTERM/SIGHUP/SIGQUIT`，统一走 `server_close()`（停止录制 → join extractor
  → FIFO → socket），并把 `shutdown_state` 写进日志；`/healthz` 现在报告 pid、release、
  三个线程是否存活、`record_script_present`，`/api/v1/status` 报告 `states` 分布与
  `inconsistent_recording`。
* 停止预算按配置推导：`sigint_grace_sec + sigterm_kill_sec + 8`（默认 15+5+8≈28 s），
  不是跌倒节点的 5 s。
* 平铺 YAML 解析现在把 `null`/`~` 当 `None`（此前 `record_config: null` 会变成字符串
  `"null"`，让每次录制都以 `--config null` 启动失败）。

## 4. “实时”评测前的检查项

1. **数据源**：`verify-input` 读实际进程。2026-10-20 本现场：`msg_source=1`、
   `pcap_repeat=true` 但无 pcap 打开、`/innolidar_points` 由 `inno_lidar_node`
   （PID 102，`_config_path:=/root/catkin_ws/src/inno_lidar_ros/config/config.yaml`，
   SHA `bd428a1e…`）发布 → `live_lidar`。仓库默认仍是 `msg_source: 2`，不要拿仓库值
   当现场事实。
2. **非循环证据**：节点 `input_source.loop_suspected` 统计重复/回退帧；seq 连续**不**
   单独证明实时。
3. **话题**：`rosnode info /innolidar_points` 的发布者必须是驱动；节点 state 的
   `source.frame_id` 必须是 `innolidar`。
4. **时间**：设备时间未锚定主机时钟（state 里
   `clock_cross_stream_unverified` / `host_anchor_unverified`），因此只报主机侧
   `process_s` / `receive_to_finish_s`，不算设备→浏览器端到端。
5. **队列**：看 `performance.queue_dropped` 增量与 `overwritten_sources`，不能只看
   一个累计数。
6. **绑定**：地面/背景/显示地面 SHA 在 `effective_node.json` 与 profile 里；页面
   `runtime.json` 的 release/page 版本必须与节点 state 的 `run` 一致。
7. **场景**：`probe-scene` 对比冻结地面/背景与实际点云。2026-10-20 旧工件先判
   `REVIEW`（持续前景约 770 点），按空场窗口 `freeze-scene` 重冻结后判 `CONSISTENT`
   （前景中位 21 点）。两者都只是几何一致性，不是物理验证。
8. **权限**：板端登录、服务启停、采集、驱动/网络改动都必须有用户明确要求。

## 5. 相关证据

* 演示链文件：`single_target_node.py`、`prepare_single_target_bundle.py`、
  `config/single_target_scene_v1.yaml`、`config/perception_single_target_v1.yaml`、
  `config/single_target_scene_20261019/`。
* 现场链文件：`deploy_human_fall.sh`、`release_config.py`、`init_site_profile.py`、
  `freeze_scene.py`、`verify_input_source.py`、`probe_scene.py`、`probe_state.py`、
  `core/run_record.py`。
* 回归：`tests/test_single_target_bundle.py`、`tests/test_release_integration.py`、
  `tests/test_run_record.py`，以及 `src/human_capture/tests/test_hc01_health.py`
  的 config 解析用例。
* 2026-10-20 实施证据：`docs/evidence/2026-10-20_release_integration/`
  （`BOARD_RUN.json`、`REPLAY_PARITY.json`、`bundle/`、`tests/`、`current_run/`、
  `page_check.json`、`scene_probe*.json`、`live_observation.json`、
  `locked_observation.json`、`rb_*.log`、`stop_*.log`）。

# 现场试用版：启动、诊断、停止与回滚

本文件是唯一有效的现场操作说明。正式入口是**不可变 release + 现场 profile + 固定页面**，
不是源码树、也不再用 `/tmp/.../run_optimized.py` 这类临时入口。历史流程与旧工单见
`docs/archive/`；算法边界见 `DEPLOYMENT_CHAINS.md` 与 `docs/PROJECT_STATE.md`。

## 1. 现场是什么

| 项 | 值 |
|---|---|
| 板端 | `192.168.31.58`，容器 `slam-localization`（Python 3.8.10 / NumPy 1.17.4 / PyYAML 5.3.1） |
| 部署根 | `/root/catkin_ws/human_fall_deploy`（`releases/ current/ profiles/ runs/ state/ www/`） |
| 控制器 | `/root/catkin_ws/human_fall_deploy/deploy_human_fall.sh`（随 release 一起校验 SHA） |
| 节点入口 | `<release>/bundle/src/human_fall_detection/scripts/single_target_node.py` |
| 当前 release | `666ad0eb40a64d4d`（RC15，`releases/20261020T141358Z_666ad0eb`；selected=running） |
| 页面 | `http://192.168.31.58:8936/human_fall/`（只需打开，不用拼任何参数） |
| ROS 话题 | `/single_target_live/{candidates,state,event,selection_request,selection_ack,display_points}`，输入 `/innolidar_points` |
| 采集服务 | `http://192.168.31.58:8766`（`/healthz`、`/api/v1/status`、录制与会话接口） |
| 现场 profile | `profiles/site_lab_20261020_v2_displayfix_r1/profile.json`（沿用 v2 地面/背景，只修显示标定 ID；路径记在 `state/profile.path`） |

**同一个生效绑定**：`current` 符号链接同时决定代码、页面和运行时配置；页面资源是
`www/human_fall/*` → `current/bundle/webui/...` 的符号链接，`runtime.js` 由启动时生成。
因此“页面是新版、进程还是旧版”不会静默发生：页面会把 `runtime.js` 的 release 与节点
state 里的 `run.release_id` 对比，不一致直接红字要求刷新。

## 2. 常用命令（都在容器内执行）

```bash
D=/root/catkin_ws/human_fall_deploy
$D/deploy_human_fall.sh status      # 选定/实际运行版本、PID、输入来源、state 摘要
$D/deploy_human_fall.sh health      # state 新鲜度 + worker + capture + 登记表
$D/deploy_human_fall.sh version     # release_id / page_version / 算法配置 SHA
$D/deploy_human_fall.sh runs 20     # 最近 run 目录
$D/deploy_human_fall.sh restart     # 停（含在途录制）再起
$D/deploy_human_fall.sh stop        # 停 capture（先停录制）→ 节点 → 页面服务
```

升级/回滚（先暂存，再激活，最后启动；`stage`/`preflight` 不动运行中的东西）：

```bash
$D/deploy_human_fall.sh stage /tmp/human_perception_release_rc15.tar   # 解包 + 逐文件 SHA + 导入检查
$D/deploy_human_fall.sh preflight <release>                           # 环境/profile/端口/磁盘/manifest
$D/deploy_human_fall.sh activate <release>                            # 切换代码+页面（不启动）
$D/deploy_human_fall.sh start                                         # 新 run_id 启动三件套
$D/deploy_human_fall.sh rollback <release>                            # 自动入口 → 自动入口
$D/deploy_human_fall.sh rollback 20261004T144415Z --legacy             # 只能回旧手动降级版
```

* `start` 在已运行时**拒绝**（不会产生第二实例）；要换版本用 `restart` 或
  `stop`→`start`。
* `stop` 遇到 pidfile 指向的进程命令行不符时**拒绝 kill**，并返回非零；不会误杀别的进程。
* `stop` 先通过 HTTP 停掉在途录制并等待其收尾，再用 `sigint_grace_sec + sigterm_kill_sec + 8`
  的预算发 SIGTERM（默认 ≈28 s），最后检查录制子进程与 8766 端口；仍有残留则报告
  “stop INCOMPLETE”，不谎报已停。
* 回滚先校验目标包 manifest；切回 `20261004T144415Z` 时脚本会明确打印**能力差异**
  （无自动入口/无区域/无页面绑定），并给出旧节点的手动启动命令。

## 3. 现场 profile 与输入来源

`profile-init <site> <scene> [release]` 把 release 里的场景工件复制到
`profiles/<site>/`，逐个校验 SHA 并写 `profile.json`。它**不会**把
`physical_verified` / `runtime_eligible` 置真：软件格式检查不等于物理验证。

换场地/家具变化后用 `freeze-scene <site> <scene> [frames]`：在**确认空场**的窗口采
50 帧，复用 `core.ground.fit_ground_plane` 与 `build_background` 重冻结地面/背景，
写 `FREEZE_MANIFEST.json`（逐帧 seq/stamp、静止守卫、拟合尝试、输出 SHA）。
非静止窗口（后半窗覆盖 < 0.995）或回放循环窗口会被拒绝；`--allow-nonstatic` 仅供诊断。

`verify-input` 读取**真实驱动进程**：命令行里的 `_config_path:=`、该 YAML 的 SHA 与
`msg_source`、进程打开的 `.pcap` 文件、`rosnode` 注册，输出：

| mode | 含义 |
|---|---|
| `live_lidar` | `msg_source=1` 且没有打开的 pcap：与实时雷达一致（仍不证明传感器物理输出） |
| `pcap` | 打开的 pcap 或 `msg_source=2`：回放，实时试用不成立 |
| `unknown` | 无法核实：页面显示“输入来源未核实” |

结论写入 `state/input_source.json` 并在节点 state 的 `input_source` 里显示。
节点另用 `SourceWatch` 统计重复/回退帧（`loop_suspected`）：这是“循环回放”的正证据，
但“seq 连续”仍然不能单独证明实时来源。2026-10-20 实测本现场为 `live_lidar`
（`msg_source=1`、无 pcap 打开、seq 无回退）。

## 4. 页面怎么读

| 页面行 | 含义 |
|---|---|
| 运行版本 | `runtime.js` 的 release/page 版本；与运行节点不一致时红字要求刷新 |
| 输入来源 | 实时雷达 / PCAP 回放 / 未核实，附带已观测帧数与“检测到重复/回退帧” |
| 运行记录 | `run_id`、记录条数、疑似提示数、写入错误 |
| 目标 / 状态 | `track_id` + acquisition 状态/原因；`unselected` 是等待目标，不是故障 |
| 跌倒状态 | `unknown/upright/descending/low_posture_unclassified/suspected/recovering/confirmed`；confirmed 永远关闭 |
| 目标基线 | `idle/pending/ready/failed`，pending 时显示样本数（规则是 3 s / 15 样本，页面不自行判 ready） |
| 区域 | 本帧有效区域数 / 已标定连接数；无区域时显示**具体原因**（如 `NO_CURRENT_MEASURED_TARGET`、`PRINCIPAL_PLANE_POINT_SUPPORTED_REGIONS_ONLY`） |
| 预测 | 实测 / 预测（带 age）；预测帧不输出区域 |
| 疑似提示 | 独立的运行记录列表，来自 `suspected_notification`；不是跌倒事件 |

页面打开即自动连接 bridge（手动“断开”后不再自动重连，刷新恢复）。页面服务对所有响应发 `Cache-Control: no-cache, must-revalidate`；若仍是旧页面（页面版本≠运行版本），页面会用带 `?v=` 的地址自动重载一次并在必要时提示强制刷新。

`runtime.js` 提供 `prefix/points/display_points/raw/state/candidates/event/
selection_request/selection_ack/ground/source_mode/release_id/page_version`，所以操作员
**不需要**手工拼 `?prefix=&points=&display=`；URL 参数仍可覆盖，用于排查。

疑似提示（`suspected_notification`）只写在运行记录里，绑定
`run/release/scene/session/track/epoch/source`，带单调递增 `notification_id`。页面用
“首次看到的 id 作为下限、只提示更大的 id”的规则，刷新/重连不会把历史提示重复当告警；
算法事件语义（只有 confirmed 产生事件）没有改变。

实测（2026-10-20，**合成 state**，不是真人）：注入 `n:101` 后提示行出现、跌倒状态
`suspected`、输入来源正确显示“未核实”；重复注入同一 id 不重复、结束态更新同一行；
再注入 `n:102` 才新增一行并记一条“疑似跌倒提示开始”。注意这条规则的两个后果：
①页面打开**时已经存在**的提示只进列表、不弹告警（避免刷新回放）；②页面打开**之后**
开始的提示会正常告警。真实跌倒检测本身仍未验证。

## 5. 运行记录与日志

每次 `start` 新建 `runs/<UTC时间>_<随机>/`，互不覆盖：

```
startup.json            启动清单（release/page/profile SHA、argv、topics、输入来源）
effective_node.yaml     实际传给节点的有效配置（绝对路径）
effective_node.json     同上 + 工件 SHA + 适用性
effective_capture.yaml  采集有效配置（record_script 指向本 release）
effective_capture.json  同上 + record_script SHA
node.log                节点日志（启动前按 20 MiB 轮转，保留 3 份）
run_events.jsonl        运行记录：目标/基线/跌倒/可观测性/原因/输入来源/worker 变化、
                        疑似提示开始结束、每 30 s 性能窗口
```

`run_events.jsonl` 自身按 8 MiB 轮转、最多 4 份；写失败会出现在 state 的
`run.write_error` 和页面“运行记录”行，不会静默丢记录。

## 6. 已知限制（2026-10-20 固定版本）

* `confirmed` 关闭，最高只到 `suspected`；没有真值，人体身份/身份正确率/真实跌倒效果
  **UNKNOWN**。
* 2026-10-20 已按用户确认的空场窗口重冻结（`site_lab_20261020_v2`）：静止守卫
  0.9952、地面 inlier 0.62、冻结后同窗前景 0/0，`probe-scene` 由 `REVIEW` 转为
  `CONSISTENT`（前景中位 21 点）。空场由操作员声明，**不是**独立测量的空场 GT；
  物理配平仍 UNKNOWN。
* 重冻结**之前**的观察窗里节点曾锁定 105 点的低矮目标（`low_posture_unclassified`，
  基线 `failed`）；重冻结后同一场景不再锁定它。该目标从未被证明是人，替换前后的
  差异只能说明背景陈旧，不能说明人体识别效果。
* 页面此前已在 Windows Chrome 验证空场渲染与真实 restart 后重连；合成 state 已验证疑似提示展示/去重。RC15 应用后，用户刷新确认“配平候选 · 未物理验证”；全量/抽样实时帧关联与显示变换守卫均通过。此次自动浏览器 debugger 连接失败，没有新的独立截图，证据见 `docs/evidence/2026-10-20_display_ground_binding_deploy/`。
* `suspected_notification` 的合成页面路径已有证据；真人动作对应的检测效果与误报/漏报仍 UNKNOWN。
* 一工作日耐久、容器重启恢复未完成（短时耐久与断流重连已验）。
* 驱动/网络/雷达固件未改；`/tmp/...` 旧临时入口已停止，但仍保留作人工兜底。

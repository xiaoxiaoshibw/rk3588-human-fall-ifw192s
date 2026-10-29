# 板端实时几何锁定与低位提示：下一次现场验证清单

2026-10-28。状态：**计划，未执行**。本文件不授权、也不代替设备操作；真正开窗仍需用户明确的时间段、现场人员和只读边界。配套机器可读计划与校验见 `docs/evidence/2026-10-28_board_live_window_plan/`。

## 为什么需要这一次窗口

当前板端（release `7530fd08938238d1003abb54576310007197db41754388315c57e1b81566ff90`，PID 64149）已建立 50 帧空场背景、绑定现场地面；15 秒只读窗口里 142/143 对原始消息 SHA 一致、无新增覆盖（见 [board_live_validation](evidence/2026-10-27_board_live_validation/SUMMARY.json)）。但受试者当时无法走动，`walkTest=not executed`，所以下面三件事仍是 UNKNOWN：

- 有真人在场走动时，几何目标能否连续锁定（同一 `track_id` 不频繁跳变）；
- 高度是否随站立/躺倒真实变化，并始终通过地面支撑门；
- `ground_alert_v1` 是否在躺倒区间触发、起身后清除——它**不是跌倒检测**，只是持续低位提示。

本清单把这次窗口的动作、最小字段和判定口径固定下来，避免再用静态物体、PC 替身或离线回放代替现场。

## 1. 前置条件（缺一不可）

| 项目 | 要求 | 开窗前核对 |
|---|---|---|
| 板端发布者 | 规范话题 `/single_target_live/state` 只有一个识别发布者 | `rostopic info` 只列出目标服务；无旧 `single_target_node` |
| 服务身份 | `service.protocol=range_recognition/1`、`releaseId`、`instanceId`、`configSha256` 开窗前后不变 | 心跳与收尾快照逐字段相等 |
| 初始化 | `background.status=ready`（`explicit_empty_prefix_50`）；`ground.available=true`，`ground.binding` 的 site/frame/grid 与现场一致 | heartbeat 的 `initialization` 与 `ground.sha256` |
| 现场人员 | 受试者 1 人（能连续走 2–3 m、能在垫上受保护躺下 ≥5 s）；操作员 1 人（口令/秒表/记录）；保护员 1 人（躺下段） | 受试者不能同时当操作员；缺人则延期 |
| 场地 | 瑜伽垫**预先放好、窗口内不移动**；无其他人走动；家具/门/风扇不动；传感器安装不动 | 开窗前后各拍一张现场照片（存 `data/` 侧，不入仓库） |
| 客户端 | Qt 已**构建完成**；`--live-url ws://<板端>:8765`（上次记录为 `192.168.31.58`）；连接后显示同一 `instanceId` 与 `ttlMs<=500` | 构建不得占用窗口（上次 45 秒被构建吃掉大半） |
| 探针 | 板端只读订阅 `/innolidar_points` + `/single_target_live/state`，逐帧写有界 JSONL，不落原始点云 | 仓库内 `pc_apps/range_fall/board_probe.py` 只服务旧 `range_image` 节点，**不能直接用于当前服务**；开窗前先在隔离目录确认字段 |
| 记录 | 操作员时间轴（相对窗口起点）、受试者身高/是否穿鞋、躺下是否辅助 | 时间轴用同一只秒表或视频时钟 |

## 2. 动作脚本（60 秒，一次成型）

所有时间相对窗口起点 t=0；操作员按表口令执行并记录实际起止。

| t (s) | 动作 | 目的 / 预期 |
|---:|---|---|
| 0–5 | 空场，无人 | 基线；不应出现 target |
| 5–15 | 从约 3 m 外进入，站定 10 s | 锁定 + 直立高度参照 |
| 15–25 | 横向走动 2–3 m 往返、转身 | 同一目标连续性（P2 主段） |
| 25–30 | 蹲下或坐地 ≥2 s | 负例；v1 按设计可能触发，标“预期低位”，不算误报 |
| 30–35 | 起身，走出画面 | 目标应消失 |
| 35–40 | 空场 | 确认 target/高度清空 |
| 40–50 | 垫上受保护躺下（辅助，不自由落体），保持 ≥5 s | P4 必需段；这是姿态事件，**不是跌倒正例** |
| 50–55 | 起身，走出画面 | 提示应清除 |
| 55–60 | 空场收尾 | 末态 target/result/depth 为空 |

安全与边界：

- 不做无保护跌倒、不要求“真实摔倒”；躺下由保护员辅助，受试者可随时停止。
- 垫子和保护员的位置尽量在背景建立时就已存在。若开窗时才引入垫子，它在 35–40 s / 55–60 s 的“空场”段可能作为新的静态目标出现；这种帧要单独标记为“开窗后引入的静态物”，不能算跟踪成功，也不能算跟踪失败，更不能据此宣称误报率。
- 本窗口**不产生跌倒 GT**，也不进入 `FALL_CAPTURE_PROTOCOL.md` 的采集批次；动作语义只借用其“站立 10 s → 躺姿保持 5 s → 起身”的顺序。
- 若受试者不能走动或不能躺下：只做能做的段，缺的段写 UNKNOWN，不用静止物体、离线回放或 PC 替身补位。

## 3. 每帧必采的最小字段（有界，不落原始云）

字段来自服务心跳/状态本身，不是客户端重算；完整清单与 `NEXT_WINDOW_MINIMUM.json` 逐项对应。

| 组 | 字段 |
|---|---|
| 服务身份 | `protocol`、`version`、`releaseId`、`instanceId`、`configSha256`、`configFileSha256`、`ttlMs`、`capabilities`、`confirmedEnabled`、`initialization.background/ground` |
| 源与选择 | `source.seq/stamp/frame_id`、`local_range.wireSha256`、`sourceBinding`、`target_source_rows`（数量 + 行 SHA）、`track_id`、`track_status`、`acquisition.reason`、诊断前 32 组件/轨/选择原因/历史重置 |
| 地面与判据 | `ground.available/reason/sha256/binding/regions`、`heightMedianM`、`groundAlert`（variant/state/active/duration/triggerFrame）、`groundAlertCandidate`（gap_v2，仅对照）、`fallEvidence.state/reason_codes`、`posture` |
| 时效 | `health.received/processed/published/overwritten/sourceGaps`、`inputAgeMs`、`resultSourceAgeMs`、`invalidationRevision`、`callbackMs/processingAgeMs/publishAgeMs`、`subscription`；`performance.process_ms/local_age_ms/queue_age_ms/serialize_hash_ms/stages` |
| Qt | 每呈现帧的 `rawSha256` 与板端 `wireSha256` 对照、`targetCount`/高度/提示、ACK、关闭后的 `clearTarget` |

边界：组件/轨只保留前 32、每轨 8 条边、每组件 8 行样例；摘要不能重建完整 XYZ，也不能证明人体归属。原始点云不落盘。

## 4. 判定口径

先过 P0，才讨论 P1–P5。所有阈值都是**本次窗口的工程判定门**，不是算法准确率。

### P0 窗口有效性（全过才计入）

- `releaseId`/`instanceId`/`configSha256` 开窗前后不变；
- `background.status=ready`，`ground.available=true` 且 binding 一致；
- 单一规范发布者，无迁移/启停动作；
- Qt 已订阅、探针已开始后才允许 t=0；
- 操作员时间轴存在，动作与时间可核对。

任一项不满足：窗口作废，重开新窗口，不拼接。

### P1 连续实时

| 指标 | 通过条件 | 不通过写什么 |
|---|---|---|
| 输入速率 | 实测约 9–10 Hz（记录实际值；明显低于 8 Hz 记异常） | 实际 Hz + 采样区间 |
| 处理覆盖 | `processed/received ≥ 0.95` | 缺口帧数 + 覆盖 header（最多 128 条） |
| 长缺口 | 无未解释的 >1 s 源缺口 | 缺口起止 `seq` + `invalidationRevision` |
| 处理耗时 | P95 `process_ms ≤ 150`，单帧 max ≤ 500（服务 TTL） | P50/P95/max + 阶段拆分 |

→ 通过只说明“本窗口实时余量够”，不说明 GPU 呈现延迟。

### P2 几何锁定（本窗口）

- 在 15–25 s 单人连续走动段（去掉进入后 1 s）内，`target_source_rows` 非空帧 ≥ 80%；
- 同一 `track_id` 变化 ≤ 2 次（允许一次重新捕获）；
- 人离开 ≥ 2 s 后不得继续报同一 track 或任何 target（开窗后才引入的垫子等静态物除外，单独标记后不计入本条）；
- 全程无其他人进入画面。

→ 通过只说明“本窗口几何目标连续”，**不说明锁的是同一个人**（身份 UNKNOWN）。

### P3 高度

- `ground.available=true`，且逐帧支撑门仍 PASS；
- 有 target 的帧中 `heightMedianM` 可用 ≥ 90%；
- 站立段中位高度落在 0.6–1.8 m 的合理性区间，躺倒段 < 0.7 m，两段差 ≥ 0.3 m；
- 地面/支撑失配的帧必须清高度，不能回填。

→ 物理地面身份仍 UNKNOWN；以上只是同一地面定义下的一致性检查。

### P4 低位提示（`ground_alert_v1`）

- 40–50 s 躺倒段内 `active=true`，且 `triggerFrame` 距首次 `heightMedianM<0.7` 的帧 ≤ 2.0 s（v1 需持续 1.5 s + 余量）；
- 50–55 s 起身后 ≤ 1.0 s 清除（`active=false`，`state` 不再为低位）；
- 0–5、5–15、15–25、35–40、55–60 段内不得 active；
- 25–30 s 蹲/坐段若触发，标“按设计预期”，不计入误报。

→ 通过只说明“持续低位提示与躺倒区间一致”，**不是跌倒检测通过**；`confirmed` 始终关闭。

### P5 Qt 同源

- 呈现帧的 `rawSha256` 与板端 `wireSha256` 匹配 ≥ 95%；
- 目标行、高度、提示与对应 state 一致；
- 无 GPU/渲染错误；关闭窗口后目标/深度清空。

→ 只说明客户端同源呈现，不等于 GPU 端到端延迟。

### 汇总规则

- P0 + P1 + P2 全过：可写“本窗口内板端能实时连续锁定几何目标”；
- 再加 P3 过：可写“高度随姿态变化且通过地面支撑门”；
- 再加 P4 过：可写“持续低位提示在躺倒区间触发并清除”；
- **任何情况下都不写“跌倒检测通过”“准确率/召回率”**；P4 不替代跌倒 GT。

## 5. 明确不能写进结论

- `confirmed` 仍关闭；没有跌倒正例 GT，不写准确率、召回率、误报率。
- 不写“稳定锁同一个人”（人体身份 UNKNOWN），不写“物理地面有效”。
- 单窗口不外推；`nohup` 没有重启自恢复，窗口后重启需重新确认空场。
- 不把 PC 替身、离线回放、静态物体、旧 release 证据当本次现场结果。

## 6. 中止、失败与重跑

- 受试者不到/不能走动/不能躺下：记录 `unavailable`，窗口不计，不补拍假动作。
- `instance`/背景/地面变化、Qt 掉线、源断流 >2 s、`wireSha256` 不匹配：立即停止，保留日志，按新窗口重来。
- 原则上只跑一次；确需重跑另开 take（`take2`），保留首次结果，不删除、不覆盖。

## 7. 产物（`docs/evidence/2026-10-28_live_window_<HHMM>/`）

| 文件 | 内容 |
|---|---|
| `TIMELINE.json` | 操作员真值：每段起止、动作、身高、是否辅助 |
| `FRAMES.jsonl` | 有界逐帧字段（§3），不含原始点云/PNG base64 |
| `HEARTBEAT.json` | 开窗/中段/收尾三次快照 |
| `QT.json` + `qt.png` | 呈现帧 SHA、ACK、清空；截图明确标 LIVE |
| `ACTUAL_SUMMARY.md` | P0–P5 逐项 PASS/FAIL/UNKNOWN + 数字 + 诚实边界 |
| `PROBE.txt` | 探针脚本 SHA、板端 Python/NumPy 版本 |

## 8. 关联文档

- 服务接口与报警语义：[BOARD_RANGE_SERVICE.md](BOARD_RANGE_SERVICE.md)
- 当前板端状态：[PROJECT_STATE.md](PROJECT_STATE.md) “2026-10-27 板端识别与实时配平接线”
- 上次最小字段雏形：[NEXT_WINDOW_MINIMUM.json](evidence/2026-10-27_service_diagnostics/NEXT_WINDOW_MINIMUM.json)
- 采集协议（仅借用动作顺序）：[FALL_CAPTURE_PROTOCOL.md](FALL_CAPTURE_PROTOCOL.md)
- 本地替身入口（不是现场）：[LOCAL_RANGE_LIVE.md](LOCAL_RANGE_LIVE.md)
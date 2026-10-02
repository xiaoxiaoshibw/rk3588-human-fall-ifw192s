# HF-01 接口契约（已实现范围冻结）

日期：2026-09-30。状态：**FROZEN（HF-01 已实现范围）/ HF-01 ACCEPTED**。冻结基线：`HF01-20260930-R2`，审查者：当前 Codex；执行：OpenCode DeepSeek v4.1 Flash。本契约实现于 `src/human_fall_detection/`，已冻结部分是后续工单的接口依据。单位、同步、安装旋转未验证项仍记 `unknown`/`pending`，由 HF-02/HF-03 补证据；冻结接口不等于物理量已验证。具体冻结范围见第 10 节。

历史：Codex 第 1 轮审查为 **REWORK，未冻结**，已复现录制覆盖保护、并发快照、非法源时间、嵌套 manifest 校验与中断原因问题。详见 [返工要求](HF-01_REWORK_PROMPT.md) 与 [审查记录](REVIEW_LOG.md)。

第 2 轮修复（2026-09-30，同一执行者）按 R1–R7 修复并同步本契约。Codex 已独立复跑本地与板上各 25 项回归及 6 项原边界检查，全部通过；源文件、驱动和新旧 bag 哈希与回传一致，已核对 SIGINT/安装证据并补做实际 IMU callback 的合成检查。结论：**ACCEPTED，已实现范围冻结**。原 SUBMITTED 及原证据保留，详见 REVIEW_LOG.md 第 2 轮审查。

## 1. 适用范围与输入

首版无相机：不使用图像、深度、CameraInfo，不构造第二台雷达或左右独立输入，不依赖 TF。允许输入：

| 话题 | 类型 | 角色 | 已验证事实 |
|---|---|---|---|
| `/innolidar_points` | `sensor_msgs/PointCloud2` | **必需**（lidar_geometry 基线） | 9.65 Hz 短时观测；frame_id=innolidar；point_step=26；x/y/z/intensity@0/4/8/12 float32、ring@16 uint16、timestamp@18 float64（非 8 对齐）；is_dense=False；帧含零点/无效回波 |
| `/inno_imu` | `sensor_msgs/Imu` | **辅助**（未验收时只记录，不参与融合） | 六轴测量确认；orientation 全零不可用；covariance 全零；单位/轴向/安装关系未验证 |
| `/device_status` | `inno_lidar_msg/DeviceStatus` | **辅助/诊断** | device_number/temperature 可读；`abnormal_flag=255` 语义未知 |

必需与辅助的区分：点云失效 = `observability=invalid`；IMU 或设备状态失效只是 `degraded` 并带 reason code。不得把辅助 IMU 停流当作点云停流，反之亦然。

## 2. 基线定义：lidar_geometry + 人工选人

- `method=lidar_geometry`：基于已装定、已验证地面/背景与连续观测的点云几何判定；不是视觉骨架、通用人体分类或医学诊断。
- `target_kind=human_like`：首版目标是**人工确认的人体样点云目标**（operator 现场选择/确认站位），不是姓名、人脸或生物身份识别。
- `selection_source=operator`：目标由人工指定；`track_id` 是会话内编号，不保证真人身份，丢失/多人交叉不自动换人。
- 几何模式未按工单验收前只输出观测或 `unknown`，不得输出 `confirmed`。
- 歧义、时间回退、输入质量失效、设备运动：清空时序证据，`fall_status=unknown`；已发出的事件不静默撤销。

## 3. 输出话题与 JSON 通用规则

- `/human_fall/health`（本单实现）、`/human_fall/state`、`/human_fall/event`（HF-05～07 实现）均为 `std_msgs/String` 承载版本化 JSON。
- 每个 JSON 必须含 `schema_version`（当前 1）。**禁止 NaN/Inf**；无效数值一律 `null`。实现按 `json.dumps(allow_nan=False)` 严格输出，写入失败即拒绝发布。
- 枚举值固定为小写字符串；未知语义字段填 `unknown`/`pending`，不得猜测。

## 4. 时间域、源时间与接收时间

- 源时间戳（`source_stamp_s`）= 设备秒域（sec+nsec 小数），原点未锚定，非 UTC、非主机墙钟；保留原样记录，不贴 Unix 标签。
- `source_time_domain` 固定为 `device_stamp_s_unanchored`。点云与 IMU 数值域相近不构成同一硬件时钟证据；`sync.cross_stream_same_clock_verified=false`、`host_anchor_verified=false`，`normalized_stamp_s=null` 直到 HF-02 验证。
- 接收时间用节点单调钟（`time.monotonic`）记录（`time_received_s`、`last_age_s`、`receive_hz`）；watchdog/新鲜度只与接收时间比较，**不**用源时间与主机时钟相减伪造端到端延迟。
- 源 stamp 分类：`first/ok/repeated/regressed/forward_jump/invalid`。原始 sec/nsec 均为 header 整数：`secs < 0`、`nsecs < 0`、`nsecs >= 1e9`、缺失或 `(0,0)` 均判 `invalid`（不改变 epoch，不更新比较基线）。`repeated/regressed/forward_jump`（阈值 `max_forward_jump_s` 可配）递增全局 `time_epoch` 并把 reason code 写入快照，直到下一帧恢复正常；`time_epoch` 供后续工单清空时序证据。
- 每个 topic 的当前帧原始值在快照中以 `stamp_secs`/`stamp_nsecs` 原样保留（包括非法值，如 `(0,0)`、越界 nsec）；`source_stamp_s` 只表示**当前帧**的合法设备秒，当前帧 `invalid` 时为 `null`，不得回填上一帧。单调性比较使用独立保存的“上一合法 stamp”：invalid 帧不更新该基线，恢复后的首个合法帧仍与它比较。

## 5. `/human_fall/health` JSON（HF-01 实现，schema_version=1）

顶层字段：

| 字段 | 说明 |
|---|---|
| `schema_version` | 1 |
| `kind` | `health` |
| `session_id` | 本次健康监视会话名 |
| `time_epoch` | 源时间不连续计数（见第 4 节） |
| `time_received_s` | 节点单调钟 |
| `source_time_domain` | `device_stamp_s_unanchored` |
| `normalized_stamp_s` | `null`（未验证同步前恒为空） |
| `observability` | `valid` / `degraded` / `invalid`（规则见下） |
| `reason_codes` | 当前有效 reason 列表（去重） |
| `sync` | `{cross_stream_same_clock_verified:false, host_anchor_verified:false}` |
| `units` | `{imu_units_verified:false, imu_alignment_verified:false}` |
| `calibration` | `{tf_available:false, extrinsics:"unknown", ground:"unknown", imu_alignment:"unknown", geometry_params:"pending"}` |
| `topics.cloud` | 点云块 |
| `topics.imu` | IMU 块 |
| `topics.device_status` | 设备状态块 |

每个 topic 块公共字段：`topic`、`required`、`status`（`fresh/stale/no_data`，阈值 `timeouts_s` 可配）、`messages`、`receive_hz`（单调接收统计）、`last_age_s`、`frame_id`、`stamp_status`、`stamp_reason`、`stamp_secs`/`stamp_nsecs`（当前帧原始整数，第 4 节）、`source_stamp_s`。

- `cloud` 附加：`layout`（`valid/errors/width/height/point_step/row_step/data_bytes/required_bytes/is_bigendian/field_names`）、`points`（`total_points/nonfinite_points/zero_points/finite_nonzero_points`，0 点回波单独计数，不代表故障）、`point_stamp`（`first_s/last_s/span_s`，按 offset 非对齐读取）、`header_equals_first_point_stamp`、`decode_error`。
- `imu` 附加：`measurements_finite`、`raw_acceleration`/`raw_angular_velocity`（原值 + `units:"unknown"`，不做 g/deg/s 换算）、`units_verified`/`alignment_verified`、`orientation_usable`/`orientation_reason`、`orientation_not_provided`、`orientation_covariance_zero`。四元数全零/非单位/非有限 = 不可用；covariance 全零 = 整个 9 项矩阵为零（只表示协方差未知，**不**据此判六轴测量无效）。ROS 约定 `orientation_covariance[0] == -1` 表示不提供姿态估计：此时 `orientation_not_provided=true`、`orientation_usable=false`、`orientation_reason=orientation_not_provided`，六轴测量状态不受影响。
- `device_status` 附加：`device_number`、`trx_temperature`、`main_temperature`、`abnormal_flag`（原样）、`abnormal_flag_semantics:"unknown"`。
- `observability` 规则：点云 `no_data/stale/stamp invalid/layout 非法/decode 失败` → `invalid`；点云正常但辅助任一 `no_data/stale`、IMU 非有限测量或 frame 不符合预期 → `degraded`；全部正常 → `valid`。

## 6. `/human_fall/state` 与 `/human_fall/event`（后续工单实现，草案随 DISPATCH）

- `state` 至少含：`schema_version, session_id, time_epoch, frame_id, source_stamp_s, source_time_domain, normalized_stamp_s, track_id, track_status, fall_status, observability, sensor_quality, reason_codes, method, input_profile, target_kind, selection_source`。
- 枚举：`track_status ∈ {unselected, locked, occluded, ambiguous, lost}`；`fall_status ∈ {unknown, upright, descending, low_posture_unclassified, suspected, confirmed, recovering}`；`observability ∈ {valid, degraded, invalid}`。
- `input_profile` 区分几何基线与已验证 IMU 辅助；`sensor_quality` 含各路新鲜度、几何参数版本、设备运动、地面有效性；IMU 未验收时不得进入融合。
- `event` 含 `event_id, session_id, time_epoch, track_id, 起止证据时间, reason_codes, 证据索引, config/calibration/method 版本`；相同事件只发一次；确认为工程规则，不承诺医学诊断。
- 本单不实现 state/event；字段冻结以 Codex 审查为准。

## 7. 单位、坐标系与变换方向

- 几何配置单位：m、s、rad、m/s、m/s²。
- 点云 frame_id=`innolidar`（设备坐标系）。雷达→底盘/场地安装变换、地面法向与高度、IMU→雷达安装旋转均**未验证**（HF-03）；无 TF。变换命名约定：`T_from_to` 表示把点从 `from` 系变到 `to` 系；未验证前不得填伪值。
- IMU 原始单位/轴向/偏置未验证；`abnormal_flag` 语义未验证。近零角速度、加速度模长≈g、时间戳相近均不构成单位/同步/安装验证。

## 8. reason/error codes（实现枚举）

`cloud_no_data/cloud_stale/cloud_layout_invalid/cloud_decode_failed/cloud_layout_missing/cloud_nonfinite_points/cloud_frame_unexpected/cloud_stamp_invalid/cloud_stamp_repeated/cloud_stamp_regressed/cloud_stamp_forward_jump`、`imu_no_data/imu_stale/imu_stamp_invalid/imu_stamp_repeated/imu_stamp_regressed/imu_stamp_forward_jump/imu_measurement_nonfinite/orientation_unusable/imu_units_unverified/imu_alignment_unverified`、`device_no_data/device_stale/device_stamp_invalid/device_stamp_repeated/device_stamp_regressed/device_stamp_forward_jump/device_abnormal_flag_uninterpreted`、`tf_absent/calibration_pending/clock_cross_stream_unverified/host_anchor_unverified`。

`orientation_usable=false` 时 `reason_codes` 记 `orientation_unusable`，具体原因写在 `orientation_reason`：`orientation_all_zero` / `orientation_non_unit` / `orientation_nonfinite` / `orientation_not_provided`（covariance[0]=-1）。

## 9. 录制与 manifest

### 会话预留与不覆盖

- `scripts/record_session.py` 复用 `rosbag record`，只录四路：`/innolidar_points`、`/inno_imu`、`/device_status`、`/human_fall/health`。必有时长（`--duration`，默认 10 s）或显式 `--until-interrupt`；SIGINT 后 bag 由 rosbag 正常关闭，并立即用 rosbag 模块再读验证。不重写 rosbag 格式。
- 启动录制前拒绝已有会话产物：输出目录存在 `<session>.bag`、`<session>.bag.active` 或 `<session>.manifest.json` 时失败退出并保留原文件；随后以 `O_CREAT|O_EXCL` 创建 `<session>.reserve` 作为独占预留，两个并发录制者不可能同时通过。默认不覆盖；`.reserve` 保留，重录同一 session 必须人工清理旧数据。失败运行不得把旧 bag 当成本次产物写 manifest（本工具在启动录制前即失败，不会走到写 manifest）。
- `termination` 记录实际停止原因：正常到时长记 `duration`；SIGINT 或 `--until-interrupt` 记 `sigint`，中断时 `duration_requested_s` 仍保留请求值且退出码 130。`duration_requested_s` 非有限或 ≤0 时拒绝。

### manifest 必填与嵌套 schema（schema_version=1）

- 顶层必含：`session_id`、`created_at_utc`、`requested_topics`（`/` 开头字符串列表）、`topics`（实际录到的名称/类型/非负消息数，来自再读）、`termination`（`duration`/`sigint`）、`duration_requested_s`、`source_time_domain`、`sync`、`units`、`calibration`、`labels`、`software`、`config`、`bag`。缺必填或类型不符拒绝写文件。
- `software`：`package`、`version` 非空字符串，`python` 可选字符串。`sync`：`cross_stream_same_clock_verified`、`host_anchor_verified` 均为布尔。`units`：`imu_units_verified`、`imu_alignment_verified` 均为布尔。`calibration`：`path`（字符串或 null）、`sha256`（64 位小写十六进制或 null）、`status ∈ {pending, verified}`（HF-01 写 `pending`）、`tf_available` 布尔。`config`/`labels`：`path`（字符串或 null）、`sha256`（64 位小写十六进制或 null）。
- `labels` 的实际形态是对象 `{path, sha256}`（人工标注前两项为 null），**不是整个 null**；`config` 未提供时为 `{path:null, sha256:null}`。
- 省略 `sync`/`units`/`calibration`/`config`/`labels` 时生成完整默认对象（unknown/pending）；显式提供但不完整或非法（含非有限数值、非法哈希）一律拒绝。`bag.readable=true` 时 `sha256` 与 `summary` 必填，且 `summary` 校验：`message_count` 非负整数、`topics` 非空、每个名称以 `/` 开头、`type` 非空字符串、`messages` 非负整数、频率/时长字段为有限数或 null。
- 原始 bag 不进入源码仓库；默认输出目录 `/root/catkin_ws/human_fall_sessions`（可覆盖），标签/配置哈希随 manifest 记录。

### 会话与时钟域

- 健康 `session_id`（如 `health_20260930_144334`）是监视会话名，manifest `session_id`（如 `hf01_verify`）是录制会话名；两者独立、不要求相等，当前 manifest 不记录健康会话名，需要时人工关联。
- bag `summary` 的 `start_time_s`/`end_time_s`/`duration_s` 与各 topic `frequency` 来自 rosbag 记录（ROS 时间域，回放/暂停时钟时语义随 ROS time），不是设备源 stamp（`source_stamp_s`/`stamp_secs`），也不是节点单调接收时间（`time_received_s`/`last_age_s`）；三者不得互相换算或相减。

### 默认配置与安装空间

- `config/default.yaml` 随包安装到 `${CATKIN_PACKAGE_SHARE_DESTINATION}/config`；`sensor_health.py` 默认配置路径由 rospkg 解析包路径后拼接，因此 devel 与 install space 均可默认启动；显式 `--config` 覆盖该路径。

## 10. 版本与冻结

本次是已实现接口的首次正式冻结，health/manifest 的 `schema_version=1`。冻结后变更接口字段必须提升对应输出的 `schema_version` 并同步本文件、消费者和测试；时间语义/有效性规则调整也须明确兼容策略并经审查，不能仅在实现中静默改变。实现与测试见 `returns/HF-01.md`。

本次冻结范围仅限已实现部分：第 3～5 节的 `/human_fall/health`（schema_version=1）、第 4 节时间/stamp 共同规则、第 8 节 reason codes、第 9 节录制与 manifest。第 6 节 state/event 仍是后续工单草案，字段名/类型未实现、未冻结，不得作为本单已验收接口引用；第 2、7 节的方法/未知量边界属于共同规则。

第一轮 `hf01_verify` 等冻结前采样保留原文件与原哈希；其中 schema_version=1 属当时的 DRAFT 输出，可能缺少当前冻结字段（如 stamp_secs/stamp_nsecs、orientation_not_provided）。离线消费者须按采集轮次和实际字段识别这些历史样本，不能仅凭版本数视为满足冻结 schema，也不能补写原始证据。需要适配时使用显式的离线读取兼容路径或另存派生产物。

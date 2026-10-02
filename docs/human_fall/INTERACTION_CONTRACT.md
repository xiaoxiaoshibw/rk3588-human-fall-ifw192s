# 新增交互接口契约 v1（已实现纯模块与请求冻结）

日期：2026-10-01。状态：**FROZEN（HF04–06第3轮已实现纯模块/候选/请求/回执语义）**；Codex独立本地/板上158回归与18边界通过。HF07将按下述ROS投影扩展并独立复审。HF-01的CONTRACT.md与GEOMETRY_CONTRACT.md保持不变，不向health/manifest v1混入控制或候选结构。真实物理/标签未验收、confirmed默认关闭。

所有话题继续用 `std_msgs/String` 承载版本化 JSON，`json.dumps(allow_nan=False)`，无效数值为 `null`，枚举小写。长度 m、角度 rad、速度 m/s、时间 s；持续时间一律设备源秒，不用固定帧数。

## 0. 共同时间域与标识

- `source_time_domain = device_stamp_s_unanchored`：源时间戳为设备秒（sec+nsec 小数），原点未锚定，非 UTC、非主机墙钟。保留原始 `seq`/`stamp_secs`/`stamp_nsecs`/`source_stamp_s`。
- `time_epoch`：源时间不连续（repeated/regressed/forward_jump）计数，由 HF-02 时间基维护；跨 epoch 的请求/快照一律拒绝。
- `snapshot_id`、`candidate_id`、`request_id`、`track_id`、`event_id` 仅在各自 session/快照内有效；`candidate_id` 绝不冒称已锁定 `track_id`，`track_id` 不保证真人身份。
- `calibration_id`/`calibration_version`：来自 HF-03 几何产物；当前真实外参/IMU/地面物理仍 NOT_VERIFIED，坐标仍应标注为雷达坐标 `innolidar` 或未标定，不得显示成已标定世界坐标。

## 1. 候选快照 `/human_fall/candidates`（RK3588 → WebUI，schema_version=1，kind=candidate_snapshot）

实现：`core/lidar_candidates.build_snapshot`。顶层字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| `schema_version` | int | 1 |
| `kind` | str | `candidate_snapshot` |
| `session_id` | str | 检测会话 |
| `time_epoch` | int | 源时间 epoch |
| `snapshot_id` | str | 帧快照标识，与源帧绑定 |
| `source` | obj | `{seq, stamp_secs, stamp_nsecs, source_stamp_s, frame_id}`，对应点云原始帧 |
| `units` | obj | `{length:"m", angle:"rad"}` |
| `coordinate` | obj | `source_frame`、`reference_frame`(可 null)、`horizontal_basis ∈ {ground_tangent, raw_xy_uncalibrated}`、`ground_relative_available`、`ground_frame`、`transform_status` |
| `calibration` | obj | `{calibration_id, schema_version, ground_status}` |
| `ground` | obj/null | 地面摘要 `{status, frame, normal, offset_m, sensor_height_m}`；null 表示无地面 |
| `settings` | obj | 生效的候选参数（有单位） |
| `quality` | obj | `ground_valid`、`background_applied`、`candidate_count`、`input_point_count`、`coverage`、`reasons` |
| `candidates` | array | 候选列表 |
| `note` | str/null | 备注 |

候选对象字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| `candidate_id` | str | 快照内唯一，`c0000`… |
| `semantic` | str | 恒 `unknown`，**不冒称 human**；人工确认后才在 track 语义层标 human_like |
| `point_count` | int | 证据点数 |
| `evidence_indices` | int[] | 指向解码点数组的索引，可回溯原始证据 |
| `center_source_m` | float[3] | 源(雷达)系稳健中心（中位数），非解剖质心 |
| `bbox_source_min_m`/`bbox_source_max_m` | float[3] | 源系三维包围盒，供原 WebUI 叠加 |
| `center_reference_m`/`bbox_reference_min_m`/`bbox_reference_max_m` | float[3]/null | 仅当有已验证变换时给参考系坐标 |
| `ground_relative_available` | bool | 是否可计算地面相对高度 |
| `height_m` | obj/null | `{min,p10,median,p90,max}`，单位 m，`n·p+d`；无有效地面时 null |
| `height_span_m` | float/null | p90-p10 |
| `horizontal_extent_m` | obj/null | `{u,v,max}`，地面切平面/（无地面时原始 XY）稳健跨度 |
| `range_m` | obj | `{min,median,max}` 源系距离 |
| `axis` | obj | `{axis(可 null), eigenvalues, elongation, ambiguous, reason, verticality(可 null)}`；点少或主特征值接近时 `axis=null` 且 `ambiguous=true`，不声称人体方向 |
| `quality` | obj | `{sufficient_points, low_points, ground_relative, axis_ambiguous, reasons}` |

边界：候选阶段只给几何，不输出跌倒事件；无地面时输出未标定雷达坐标候选，`height_m=null`，跌倒高度不可用（**不假设 z=0**）。地面覆盖检查用点的地面投影与 `valid_region`，不用窄 z 带拒绝站立/低卧。背景只能由显式空场采集生成并冻结（`build_background`），无在线更新，故静止倒地者不会被学习成背景。近地面人体与家具水平重叠会合并成单簇（已知局限，需人工确认/后续分割）。

样例（截断）：

```json
{"kind":"candidate_snapshot","schema_version":1,"session_id":"s1","time_epoch":0,
 "snapshot_id":"seq:12","source":{"seq":12,"stamp_secs":100,"stamp_nsecs":500,
 "source_stamp_s":100.0000005,"frame_id":"innolidar"},
 "coordinate":{"horizontal_basis":"ground_tangent","ground_relative_available":true,
 "transform_status":"unknown"},
 "candidates":[{"candidate_id":"c0000","semantic":"unknown","point_count":260,
 "center_source_m":[3.0,0.1,-1.2],"ground_relative_available":true,
 "height_m":{"min":0.02,"p10":0.05,"median":0.28,"p90":0.55,"max":0.9},
 "axis":{"ambiguous":false,"verticality":0.18},"quality":{"sufficient_points":true}}]}
```

## 2. 选择请求 `/human_fall/selection_request`（WebUI → RK3588，schema_version=1）

实现：`core/selection.SelectionBackend.handle`。请求字段：

| 字段 | 类型 | 必需 | 说明 |
|---|---|---|---|
| `schema_version` | int | 是 | 必须精确等于 1；未知版本直接拒绝，不做 int 截断 |
| `request_id` | str | 是 | 幂等键 |
| `action` | str | 是 | `select` / `release` / `capture_baseline` |
| `session_id` | str | 是 | 必须匹配后端 session |
| `time_epoch` | int | 是 | 必须精确等于后端当前 epoch（所有动作） |
| `snapshot_id` | str | select 必需 | 绑定用户当时看到的候选快照 |
| `candidate_id` | str | select 必需 | 不接受裸像素作空间坐标 |
| `track_id` | str | release/capture_baseline 可选 | 已锁定编号 |
| `selection_version` | int | 是 | 用户期望的当前选择版本；必须为整数，不等于后端则拒绝 |
| `calibration_version` | str/null | 可选 | 仅作核对；实际以板端快照 `calibration.calibration_id` 为准，不匹配则拒绝 |
| `operator_confirmed` | bool | capture_baseline 可选 | 记录操作者意图，不绕过实测质量门 |
| `source_stamp_s` | 忽略 | — | 基线起点取板端当前有效源时刻，不接受客户端时间 |

幂等与拒绝（第2轮 R2 收紧）：

- 注册快照与请求的接收时间必须有限（拒绝 NaN/Inf）；请求接收时间必须单调不回退（`nonmonotonic_time`）；二者同一时钟域。
- 未来快照（age<0）→ `snapshot_in_future`；过期快照（age>TTL，默认 2 s）→ `stale_snapshot`；未知快照 → `unknown_snapshot`。
- 跨 epoch → `epoch_mismatch`；`time_epoch` 非整数 → `invalid_time_epoch`；`schema_version` 非 1 → `unsupported_schema_version`。
- 未知候选 → `unknown_candidate`；质量不足 → `insufficient_candidate_quality`；标定不匹配 → `calibration_mismatch`。
- 旧选择版本（整数且小于当前）→ `stale_selection_version`；非整数/更大版本 → `invalid_selection_version`；未锁定 → `target_not_locked`；`track_id` 不符 → `track_mismatch`；接收时间非法 → `invalid_receive_time`。
- 以上拒绝均发生在任何状态修改之前。
- 相同 `request_id` + 相同内容 → 返回原回执（`idempotent_replay=true`），不重复执行（也不重复清基线）；相同 `request_id` + 不同内容 → `request_id_conflict`。

请求/回执样例：

```json
// selection_request
{"schema_version":1,"request_id":"r-8f1","action":"select","session_id":"s1",
 "time_epoch":0,"snapshot_id":"seq:12","candidate_id":"c0000",
 "selection_version":0,"calibration_version":"geo-2026-10-01"}
// selection_ack (accepted)
{"kind":"selection_ack","schema_version":1,"request_id":"r-8f1","action":"select",
 "session_id":"s1","time_epoch":0,"accepted":true,"reason":null,"track_id":"t0001",
 "candidate_id":"c0000","selection_version":1,"baseline":null,"idempotent_replay":false}
// selection_ack (rejected: stale snapshot)
{"kind":"selection_ack","schema_version":1,"request_id":"r-900","action":"select",
 "session_id":"s1","time_epoch":0,"accepted":false,"reason":"stale_snapshot",
 "track_id":null,"candidate_id":null,"selection_version":null,"baseline":null,
 "idempotent_replay":false}
```

## 3. 选择回执 `/human_fall/selection_ack`（RK3588 → WebUI，kind=selection_ack）

| 字段 | 类型 | 说明 |
|---|---|---|
| `schema_version` | int | 1 |
| `request_id` | str | 回显 |
| `action` | str | 回显 |
| `session_id`/`time_epoch` | str/int | 板端当前值 |
| `accepted` | bool | 板端是否接受，**唯一权威** |
| `reason` | str/null | 拒绝原因码 |
| `track_id` | str/null | 接受后的实际编号 |
| `candidate_id` | str/null | 接受锁定的候选 |
| `selection_version` | int/null | 板端实际选择版本 |
| `baseline` | obj/null | capture_baseline 时返回 `{status:pending/ready/failed, reason, baseline, ...}` |
| `idempotent_replay` | bool | 是否为重复回执 |

页面重连不自动重放旧选择；只有板端回执代表成功。切换/解除/epoch 变化/丢失会重置目标动作历史，但已存事件不删除。

## 4. 目标状态 `/human_fall/state`（kind=target_state，HF-05）与特征/跌倒（HF-06）

`core/tracking.TargetTracker.snapshot` 输出：

| 字段 | 说明 |
|---|---|
| `track_status` | `unselected/locked/occluded/ambiguous/lost` |
| `position_m` | 当前中心，可选为预测值 |
| `position_predicted` | true 表示预测，**不得作为跌倒观测** |
| `prediction_age_s`/`prediction_stale` | 预测时长与是否超过遮挡阈值 |
| `velocity_m_s` | 匀速度估计（有界） |
| `selection_version` | 选择版本（单调） |
| `requires_reselection` | ambiguous/lost 后要求人工重选 |
| `action_generation` | 动作历史代；reset 时递增 |
| `history_reset_reason` | `operator_select/release/ambiguous/lost/time_epoch_changed/…` |

`core/fall_state.FallStateMachine.update` 输出 `kind=fall_state`：

| 字段 | 说明 |
|---|---|
| `fall_status`（别名 `state`） | `unknown/upright/descending/low_posture_unclassified/suspected/confirmed/recovering` |
| `reason_codes` | 证据/原因码 |
| `event_id`/`new_event`/`event_count` | 当前事件、本帧新事件、已存事件数 |
| `confirmed_enabled`/`mode_verified`/`allow_confirmed` | 模式门控；默认 false，线上不产生 confirmed |
| `baseline_version`/`calibration_version` | 基线/标定绑定 |
| `limitations` | 已知不可区分/可能漏报（如主动躺下、慢滑落） |
| `features` | 当帧特征块 |

状态规则（持续时间全部为源秒，第2轮 R1/R4/R5 收紧）：

- 预测从最后实测位置/速度/时刻重算，绝不叠加上一次预测；预测位置 `position_predicted=true`，不作观测、不推进特征历史/近地面时长/下降估计。
- 时钟域在 select 时**固定**：有有效接收时间用 `time_received_s`（在线默认），否则用 `source_stamp_s`（纯离线显式源域）。后续当前帧在该域无效（缺失/NaN/Inf）即拒绝当前观测并保留上一合法实测基线（`position_predicted=true`、`status≠locked`、`clock_reason=current_invalid`），绝不切换到另一域制造有效 dt；超窗/负 dt（时钟回退）判 `lost`+需重选。
- 下降证据只来自当前同目标连续实测历史（实测峰值与下降速率）；静态基线差只是姿态量，不是下降证据。初始已躺（含已有站姿基线）保持 `low_posture_unclassified`。
- 预测/质量中断打破连续低姿态时长但不结束未恢复的 episode；同一 episode 不重复发事件。真实恢复或重新选择另一目标的完整新证据才产生新的 `event_id`。
- `confirmed` 必须同时满足有效且**绑定匹配**的站姿基线、同目标实测下降历史、持续低姿态，且 `mode_verified and allow_confirmed` 为真。
- 基线绑定字段（**全部必填**）：`session_id`/`track_id`/`time_epoch`/`selection_version`/`action_generation`/`calibration_version`；消费时逐项核对，任一缺失或不等即 `baseline_applies=false`，该 ready 基线对任何目标都无效（消费组件自身 `session_id` 可作为当前会话来源，但不得补出缺失的 track/epoch/选择/代/标定）。新目标/解除/epoch 变化使当前基线资格失效（历史产物保留在 `retired`），另一人的 ready 基线不可继承。回放 CLI 的高度/基线参数只能构造带完整绑定的当前手动目标/受控 fixture 基线，或报告未绑定，不生成无身份却 ready 的通用基线。
- 上下文重置是一次性事件：`features.reset_now=true` 仅出现在发生重置的那一帧，`history_reset_reason` 为持久诊断；重置后连续新有效观测可重新得到 `upright` 与新下降证据，不会被永久钉在 `unknown`。降级不撤销已存事件。
- 回放入口默认不选人（`track_status=unselected`）；仅显式 `initial_candidate_id`/`initial_position_m` 或测试专用 `auto_select=true`（`selection_source` 标注 `fixture_auto`）才初始化，丢失/歧义后不自动重识别。

事件 `/human_fall/event`（kind=fall_event）：`event_id, session_id, time_epoch, track_id, fall_status, method, start_source_s, end_source_s, low_duration_s, height_drop_m, reason_codes, baseline_version, calibration_version, config_version, evidence`。相同事件只发一次；确认是工程规则，不承诺医学诊断。主动躺下与跌倒可能无法几何区分，如实报告。

## 5. 版本与冻结

ROS集成投影：`/human_fall/state`采用kind=target_state、schema_version=1，在tracker已有字段上增加原HF-01契约第6节要求的frame/source时间域、source原始帧块、snapshot_id、method=lidar_geometry、input_profile、target_kind/selection_source、fall_status、observability、sensor_quality/reason_codes、基线/标定版本、当前地面/模式质量与有限recent_events。不要用简单dict.update让内部fall_state的kind覆盖对外kind。内部fall_state/target_features可作为命名块保留，新增字段允许消费者忽略；改变已冻结字段含义则需版本策略。位置必须说明source/reference坐标，三维框用于原点云叠加时保留source bbox。prediction_age_s从最后合法实测计时；过期框/位置不得伪装新测量。具体ROS/安装/写失败行为在HF07实际实现后复审，不因本模块冻结就宣称节点通过。

- 本已实现模块接口为v1，schema_version=1，已由Codex冻结；新增ROS集成投影仍需实际运行复审。已冻结字段/枚举/含义变更须提升版本并给兼容策略，新增可忽略字段不改变旧字段含义。
- 模式验收门控：真实几何模式未经人工标签验收，线上默认不允许 `confirmed`；合成测试可显式启用已验收夹具检查完整状态机，但不作为真机验收。
- 本草案不含车辆控制/通知接口，不替换 HF-01 health/manifest。

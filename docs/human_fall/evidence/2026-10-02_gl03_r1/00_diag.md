# GL-03 R1 集中诊断（实现前）

日期 2026-10-02 / 单写入者 OpenCode / 基线 `GL03_ACCEPTANCE.md` v1。
本文件覆盖整张矩阵：已有覆盖、缺检查、失败、最小根因与保留行为。实现前不写生产代码。

## 1. 已核查代码入口与调用链

- `core/lidar_candidates._reference_block(features, transform)` ← 仅 build_snapshot。
- `core/lidar_candidates.build_snapshot` ← `candidates_from_cloud`（decoder wrapper）、`node_runtime.FallNodeCore._process_locked`、replay（`fall_replay` 若走 build_snapshot）。
- `core/tracking.candidate_view(candidate)` ← `TargetTracker.select/update`（reference 优先）。
- `core/node_runtime._state_payload/_mask_unobservable/status_state/_sensor_quality` ← ROS `/human_fall/state`。
- `core/features.FeatureExtractor.update` ← 消费 `observed` candidate（不读 reference 字段，不新增）。

## 2. 逐矩阵行诊断（GL03_ACCEPTANCE.md “必须逐行覆盖的矩阵”）

| 入口/状态 | 现有实现 | 判定 | 最小根因 |
|---|---|---|---|
| build_snapshot 无标定/legacy/source-only | `ground=None`、`transform=None`、`calibration` 或空 | 已有覆盖；旧行为好 | — |
| build_snapshot full + ground + reference transform | `_reference_block` 对 `np.array([ [3] ], [3], [3] ])` ragged 报错 | **失败/崩溃** | 三向量被放进同一 list，NumPy 推成 object/ragged；且只变换 min/max 两角 |
| build_snapshot derived 损坏/版本/frame/parent 错配 | `build_snapshot` 直接读 `calibration.ground_derived`，**未验证**；`node_runtime` startup 会先 `validate_geometry_calibration`，纯 API 直接调用不校验 | 缺检查 | 纯 API 路径可把损坏 derived 的 `ground_derived_id` 写进 snapshot；无 parent/frame 绑定校验 |
| build_snapshot 采样/非法点/范围/background | `finite`→`max_points` stride→range→height→background，索引同步过滤 | 索引可回溯；未显式检查 derived 绑定 | 保留 |
| candidates_from_cloud / node / replay | 都经共享 build_snapshot | 修复共享入口即覆盖三处 | — |
| node 当前 locked 实测 | state 透传 `center_source/bbox_source/center_reference`，**无 ground 实际点字段** | 缺字段 | `_state_payload` 不输出 ground 几何 |
| reference 优先 track 后 occluded 预测 | tracker 在 reference 域预测；`_state_payload` 直接把 `position_m` 塞 `position_source_m`（错标坐标） | **失败** | 预测无逆变换回 source；无 reference 预测标记 |
| unselected/release/lost/ambiguous/stale/invalid/monitor_bad | `_mask_unobservable` 清 source 字段/bbox/range/coordinate | 需补 ground 字段与 predicted 标记的清空 | 新增字段须一并 mask |
| 同版本 reload / 新版本 reload / 恢复 | GL02 apply_ground_context 已处理资格 | 保留；新 geometry 字段随 snapshot 版本 | — |
| 无可信支持/auto AABB/disabled | `_ground_context_unavailable` + monitor | 保留旧行为 | — |
| 可信 synthetic 桥接/standing/contact/lying/完全近地 | 无分离改造（本单允许最小、显式关闭） | 见 §5，默认关 | — |
| 真实 ROI 子集/跨帧 pool/无空场 | 本机有 GL00 r1 CSV/tgz | 见 §6 探索分析 | — |

## 3. 关键根因

**R1 ragged/np.minimum 崩溃。** `_reference_block` 构造
`np.array([[min0,min1,min2],[max0,max1,max2],[center]])`，第三行是嵌套的 `[float]*3`
再包一层，得到 shape 不一致的嵌套 list；NumPy 生成 object 数组或直接抛
`ValueError: setting an array element with a sequence.`，合法非零旋转+平移下 reference
路径不可用。同时只用 min/max 两角变换后取 `np.minimum/maximum`，**不是**所有实际点的 AABB。

**R2 ground 几何缺失。** candidate 没有 `bbox_ground_min_m/max_m`、`center_ground_m`、
`bbox_ground_from`；state 无对应字段。契约要求：对本候选 **实际 evidence 点** 施加同一
ground-derived R/t 后取三轴 min/max 与逐轴中位数（非旋转后 source 中位数），来源标
`actual_points|unavailable`，且带 `ground_derived_id`。

**R3 source/reference 混标。** 预测位置在 tracker 时钟域（`candidate_view` 取
`center_reference_m` 优先），`_state_payload` 却把它写进 `position_source_m`。必须
逆变换回 source，或明确不可用（设 reference 预测标记）。

**R4 derived 未校验。** `build_snapshot` 直接使用 caller 传入的 `calibration.ground_derived`。
纯 API 可传损坏/newer版本/frame或parent错配而仍写出 GDID。需复用
`validate_ground_derived` + `_validate_ground_derived_consistency`（与 GL02 共享严格 validator），
失败时不输出有效 ground ID 且 ground 几何 `unavailable`。

## 4. 兼容与保留

- `center_source_m`、`bbox_source_min_m/max_m`、`evidence_indices`、`height_m`、
  `ground_relative_available`、`coordinate` 旧字段语义不变；新字段可加可忽略。
- 旧无 derived 的 calibration 摘要（ground-only / legacy）不破坏：ground 几何字段为
  `null`/`unavailable`，GDID `null`。
- tracker “reference 优先”契约不改；只修 node 输出坐标标注与逆变换。
- GL02 校验/生命周期/缓存/ACK、选择/会话/源时间/新鲜度守卫全部保留。

## 5. 大候选最小改造策略

先证据后改造。本单**不默认开启**任何分离：无可信支持、auto AABB、无 derived、disabled
一律旧行为。若实现可信 synthetic 桥接，仅显式默认关闭且支持可信 gate；地面点不做连接边
不无条件删近地厚层（保护脚/低卧/完全近地证据）。真实数据不足则 BLOCKED。

## 6. 本机数据层级

- `14_current_roi_points.csv`：frame_seq/point_index/x/y/z，**ROI 受限、非全集**，有逐帧索引。
- `14_current_sample.csv.tgz`：header x,y,z，**跨 47 帧 XYZ pool**，缺帧与原索引；不能当单帧重放。
- 原 bag 在设备 `/root/catkin_ws/...`，本机无完整 bag。无现场地面 identity/安装角。
- 因此大候选“全景逐帧重放”**BLOCKED**；仅做 pool 探索性成员/水平 cell 连接/疑似平面支持对照，
  不造完整帧、人体/机器人标签或空场。

## 7. 保留行为与检查计划

实现最小根因修复后：完整矩阵逐行 synthetic 检查（G01–G08）、fall 全回归、
GL02 独立 12 方法+pending 2 方法、follow 2、UI 静态。日志落本轮新目录，源码 manifest 含
未跟踪文件。未跑板端/物理不宣称 PASS。

## 8. Codex 检查点四根因修复（2026-10-02 续）

独立脚本 `codex_geometry_checks.py` 修复前 2 通过/5 失败/1 错误；按根因一次修共享入口：

- **G03 完整绑定**：`_validated_ground_derived` 改为先跑共享 `validate_geometry_calibration`
  校验 **整份 artifact**（parent id/版本、verification 矛盾、parent ground、derived 与
  artifact sha 一致性），再把实际 `frame_id`、显式 `ground` 与 artifact 绑定；任一不符
  即 `(None,None)`（降级 `unavailable`），绝不输出有效 GDID。
- **G07 optional 兼容**：`validate_snapshot` 不再无条件要求 `bbox_ground_from`；旧候选四个
  新字段全缺=合法，任一出现才校验完整一致性（现有损坏断言不放弱）。
- **G05 选择缓存**：`handle_request` 接受 `select`/`release` 后清空 `_last_state`/
  `_last_candidate`；`status_state` 从当前 tracker 绑定重建、无观测不伪造测量。幂等重放
  仍是纯缓存读、不重执行；GL02 pending/watchdog/ACK 保留。
- **G04 预测 reference 框**：occluded 预测分支把 `bbox_reference_min/max` 随 tracker 固定域
  位移同步，无可平移的实测 reference 框时显式 `null`，绝不给旧位置的旧框；ground 实测字段
  保持 `unavailable`。

修复后：独立 8/8 通过（`53_codex_checks_fixed.txt`），GL03 28/28（`57_gl03_suite.txt`），
fall 全回归 300/300（`58_suite_full.txt`），follow 2/2（`56_follow_suite.txt`）。

## 9. O01 探索性连接分析结果（G06/O01）

脚本 `60_o01_explore.py` → `61_o01_explore.json`（stdout `62_o01_explore_stdout.txt`）。
只读两份 GL00 产物，未改原数据：

- `14_current_roi_points.csv`：sha256 `4c9ccaac…`，**仅 2 帧**（1142510/1142511），
  6000 行 cap，point_index 16335–30585。是逐帧 **ROI 子集且被限流**，非全集、无
  全云 range/background 语境。
- `14_current_sample.csv.tgz`：sha256 `528d8ed2…`，97411 行 pool，**跨帧、无帧号、无原索引**，
  不能当单帧或重建原始索引。
- 同输入水平 cell 连接基线（cell=0.25m）：pool 1188 cell → 1 连通分量。
- **有标识**疑似平面消融（z 带 |z−median|≤max(0.05,3·MAD)，占 pool 78.7%）：移除后
  1026 cell → 仍 1 分量，`components_delta=0`。即 pool 层面**没有证据**显示近地厚层
  桥接了本应分离的独立簇。

**结论（诚实）**：无可信真实地面 identity、无完整帧/原始索引，pool 消融不能确认
当前单帧大候选根因，也不能做人/机器人标签。因此最小分离**保持默认关闭**
（`separation_decision.default_off=true, enabled=false`）；真实全景逐帧/身份结论
标 **BLOCKED**。不强行触发分离、不造标签、不冒用空场。

# GL-00 R4 逐项整改记录（对应 CODEX_REWORK.md）

本文件逐条对应 `evidence/2026-10-01_gl00_r3/CODEX_REWORK.md` 的 0–7 项；方案数值见
`24_synthetic_protocol.json`、`26_parameter_plan.json`；契约见 `25_contract_extension_draft.json`。
本轮只补方案/契约/回传与必要复核证据；未新采集、未改生产/网页/冻结配置、未启动 GL-01。

## 0. 版本与哈希（更正"R1/R2 完全未变"的笼统写法）

- 生产/冻结资产哈希与基线一致（`src/human_fall_detection/core/ground.py` `b1e7b54b…94e6` 等）。
- **更正**：`docs/human_fall/evidence/2026-10-01_gl00_r2/gl00_r2_layout_check.py` 在 R3 被修改过
  （新增非零点端序探针 `probe_nonzero_*`）。不再笼统写 R1/R2 完全未变。
- **已保存 R2 原版本**：从 `r2/03_events.jsonl` 的 write 事件恢复为
  `r2/gl00_r2_layout_check.original.py`（LF，SHA256 `b3c9e541ef6ba387d43e33d1d9d3136fa27a23a19023b29666bc7ac9be8b606b`）。
  当前 `r2/gl00_r2_layout_check.py` 为 R3 修订版；R3 目录内副本同 R3 修订版。

## 1. ceil 预算（p=.999,w=.20 应为 861）

- 精确值 `log(1-0.999)/log(1-0.20^3)=860.0109`，**ceil=861**（R3 的 860 是错的）。
- 完整表（ceil）见 `24_synthetic_protocol.json`/`26_parameter_plan.json`：修正只用 `ceil`，不再出现 860。
- **措辞更正**：相关性采样下该式只是**规划估计**，会低估或高估实际需要，**不是 upper bound、不是保证**；
  始终叠加 `ransac_iteration_hard_cap=2000` 与候选上限。

## 2. 可冻结的软件参数（补全 R3 缺项）

- 采样点数/空间尺度和每格预算：`fit_point_cap=5000`、`holdout_point_cap=10000`、`spatial_cell_m=0.20`、`max_points_per_cell=4`。
- 候选数：`max_candidates=3`（按法向+偏移去重，不超过 3 个不重复候选）。
- 固定迭代硬上限：`ransac_iteration_hard_cap=2000`（`ransac_iterations=861`）。
- 独立未截断验证门槛：≥3 区域、每区 ≥20 点、未截断 RMS ≤0.03m、|残差| p95 ≤0.05m、支持率 ≥0.8。
- 退化判据（**提案，未实现**）：`min_sample_separation_m=0.05`、`min_sample_triangle_area_m2=0.0025`、`min_planar_eigenvalue_ratio=0.02`。
- 歧义判据（**提案，未实现**）：次优支持 ≥0.8×最优 且 非同面（法向差>10° 或 |偏移差|>0.05m）→ `orientation_unverified`，要求 ROI/现场证据。
- 显式 up_axis + `max_angle_rad=0.2617993877991494`（15°，合成参考）；`sensor_height_interval_m` 由夹具给（**不套用 1.1m**）。
- 预算/点数不足、候选不足、验证区不足 → 明确失败码，**不放宽门槛**。
- 说明：以上只是**纯合成软件协议**，不是设备/现场验收门槛；真实现场参数仍 BLOCKED。
- 可执行自检：`24_synthetic_protocol_check.py` 校验表/顺序/数量，并验证该门槛**能通过也能失败**（干净面通过、平移面失败）。

## 3. 契约字段语义

- `center_ground_m` 定义为**候选实际点集变换后逐轴 median**（非旋转后的源中位数）。
- `ground_derived` 用**嵌套 `schema_version=1` + `units="m"` + `to_frame`**；加载器拒绝缺失/未知嵌套版本（不猜不并）。
- state 的派生框/变换/版本消费与 candidate 一致（同一 `ground_derived_id` 与源帧；不匹配即视为过期，不得当当前值显示）。
- `single_plane_premise` 拆为 `applicability.single_plane_assumed=true`（软件适用前提，仅表示声明了假设）与
  `single_plane_confirmed=false`（现场确认标志，未测不得置真）——**不硬真伪造现场核验**。
- 派生变换只存 `ground_derived`，**不进入 measured extrinsics**（`T_reference_lidar`/`rotations`/`frames.reference`/`extrinsics_verified` 不变）。

## 4. ROI 独立性（更正）

- 现状不独立，原因三条：对**全集**拟合与残差筛选；fit/val **共享 3.0m 边界**；验证点由**候选平面残差**挑选。
- 计划：使用**预先确认**的区域/帧组/源索引，**与拟合样本点索引不重叠**；验证点**不按待验证平面的残差**筛；**至少 3 区域**。
- **更正**：同一真实地面表面的**不同区域可以独立留出**——不再笼统声称"同表面就不能独立验证"。

## 5. 端序/解码结论措辞（更正）

- 端序依据：`is_bigendian=false` + 字段布局 + 独立解码一致性；LE=8.1765 与 BE=5.59e-21 的对比只是**支持性**，
  BE 读出仍是有限小数，**单点合理范围不能"证明"端序**。
- `header == 首点 timestamp` 只是**布局/时间戳解码一致性**检查，**不是 XYZ 空间或尺度真值**证据。

## 6. 现场参考物定义（更正）

- 用户已提供并定义：机器人地面到顶总高 **1.4m**、地面到雷达"眼球"垂直 **1.1m**。
  **不再写"无参考物/基准定义未知"**。
- 仍缺：对应**机器人点簇/高度误差**、**测量误差**、**光学窗口到设备坐标原点的偏移**。
- 旧 0.242 复核只支持**分母/采样范围**解释，**尚不能判定为唯一成因或地面身份**。

## 7. 退出码与失败保留

- 保留 R3 失败日志 `r3/20b_r3_verify.txt`（末尾 `bash: line 14: $'\r': command not found`）：
  **容器子命令 rc0 ≠ SSH 外层 rc0**。
- R4 用**文件（LF）**重跑并记录内外层退出码：`r4/20c_board_verify_lf.txt`
  （`PROTOCOL_INNER=0`、`LAYOUT_INNER=0`、`VIZ_INNER=0`，`SSH_OUTER_RC=0`，无 CR 报错）。
- 不再拼复杂引号/`chr` 链；如实记录外层退出码。

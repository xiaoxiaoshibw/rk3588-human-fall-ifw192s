# GL-E02 现场测量 Checklist / 2026-10-05 拟执行

> 本文档是 GL-E02 P1 阶段的**人工现场取证 checklist**，配合下一阶段计划 [GROUND_LEVELING_NEXT_STAGE_PLAN.md](../GROUND_LEVELING_NEXT_STAGE_PLAN.md) §4 和 [14_NEXT_PHYSICAL_EVIDENCE.md](2026-10-04_mainline_evidence_r1/14_NEXT_PHYSICAL_EVIDENCE.md) 使用。
>
> **目的**：去现场一次，把闭合 GL-E01 B02（外参/up 方向/原点高度/四 box 地面身份）所需的**全部物理测量**采集齐，避免多次往返。
>
> **不做什么**：不启动新采集 / 不改 config / 不部署 / 不动 driver / 不开 GL-05。它只是"到场把数据量出来"。
>
> **如何使用**：现场人手勾 ☑ / 填值 / 拍编号照片 / 录短语音备；离场前当场把 1–7 节填完，回 PC 后由 AI 把它结构化为 `measurement_record.json`（schema 见 §8）。带回 PC 前不要让 AI 帮你"估"任何数。

---

## §0 现场前 30 分钟（在 PC 上做）

| 步骤 | 验证对象 | 通过条件 |
|---|---|---|
| 0.1 | 板端 SSH | `ssh ldiar-wel` BatchMode 通；记录**远端 `hostname`、`date -Is`**，确认与 PC 时钟差 > 3h 这条已知 |
| 0.2 | 准备测量工具 | 卷尺 ≥ 3m ×1；手机水平尺（含不确定度说明）；激光测距仪（如有）；标签贴纸 ×8；记号笔 |
| 0.3 | 准备拍照规范 | 决定拍摄命名规则：建议 `YYYYMMDD_HHMM_<SITE_TAG>_<seq>.jpg`，同一测量点 `近景+中景+全景` 三张 |
| 0.4 | 准备 measurement_record.json 骨架 | 把 §8 模板拷到手机记事本/平板，离线可编辑 |
| 0.5 | 决定现场 4 个 ROI 候选标签 | 不能到场再临时起名；建议中文/拼音短标签（见 §5） |

**今天的照片已确认**：现场为**通透平整木地板**，存在机器人/桌腿/机箱/花盆/水桶/纸箱等大量静止障碍。这意味着 §5 ROI 选区时**必须避开**这些静止高物体，否则 FIT 会吸入非地面点。

---

## §1 板端只读取证（人坐在板子边，不动配置）

> 目标：把"当前这次启动所用的 SDK 运行参数 + config SHA + 时间窗"绑住。这是 B02 成立的前提。

| 步骤 | 命令（在板上 `slam-localization` 容器内） | 期望产物 |
|---|---|---|
| 1.1 记运行起点 | `date -Is && hostname && docker ps --no-trunc` | 一行时间戳 + 容器 ID 全量 |
| 1.2 记启动 config SHA | `sha256sum /root/catkin_ws/src/inno_lidar_ros/config/config.yaml` | 一个 sha256 |
| 1.3 记 SDK 日志路径与 mtime | `ls -la /root/catkin_ws/logs/` 找到本次 run 对应 SDK 日志；`stat <file>` 取 mtime | mtime **必须晚于** 1.1 记录的时间，**早于** 离场时间 |
| 1.4 记 bag 录制起止 | 如现场会录制新 bag：`rosbag record --duration=__ …` 记下**实际 start/end 时间戳** | 与 §1.1 同一时钟域 |
| 1.5 截图保留 | 上述所有命令输出用手机拍屏幕留存 | 至少 4 张 |

> ⚠️ 已知陷阱（GL-E01 A05 教训）：现有日志目录只能看到"当前状态"，mtime 经常晚于 bag 录制窗口，**无法反推 10/2 那次录制**。今天若**没有新录制**，b02 的"run/config 联合绑定"仍然 BLOCKED——这份 checklist 主要闭合**今天这一次新安装/新录制**的证据。
>
> 因此：**如果用户的意图是"今天重新采一段受控标定录制"**（GROUND_LEVELING_NEXT_STAGE_PLAN §4 末尾明确允许的分支），§1.4 必须留下新的 bag 与它的 config 快照；如果只是为了"补足 10/2 的旧证据"，请**直接放弃**——GL-E01 已确认旧证据链无法补全，不要浪费时间。

---

## §2 雷达安装位置测量（§B02 关键字段一）

> 目标：给出**点云坐标原点**到**地板平面**的真实距离，以及该测量值的不确定度。**不是光学窗口高度**——1.1 m 这个数字 GL-E01 已明确拒绝。

| 步骤 | 做法 | 记录字段 |
|---|---|---|
| 2.1 找到"原点" | 查 IFW192S 手册/外壳标注"coordinate origin"或"optical reference point"；**拍特写照片**（命名 `*_origin_closeup.jpg`） | `origin_description`: 文字描述（例如"机壳前缘螺纹孔中心"或"雷达底座平面中心"）|
| 2.2 选水平参考 | 在§5 已选的 FIT 区**正下方**或**紧邻位置**用激光测距/卷尺测**原点 → 地板**垂距 | `origin_to_floor_m`: 数值（米）；`method`: "laser_rangefinder" / "tape_plumb" |
| 2.3 估不确定度 | 同点测 3 次取 max−min；或按工具规格书（卷尺 ±2mm / 激光 ±1.5mm）| `origin_height_uncertainty_m`: 数值 |
| 2.4 排除光学窗口混淆 | 另测一次"光学窗口下沿"离地高度作对照 | `optical_window_to_floor_m`: 数值（明确**不等于** 2.2 的值）|
| 2.5 安装稳定性声明 | 本次安装**自何时起未动**：填日期时间 | `install_unchanged_since`: ISO8601 |
| 2.6 拍照编号 | 全景：雷达 + 周围 1m 环境 ×1；中景：原点位置 ×1；特写：原点 ×1 | `photo_refs`: ["`*_origin_panorama.jpg`", "`*_origin_mid.jpg`", "`*_origin_closeup.jpg`"] |

**红色门槛**：若 `origin_height_uncertainty_m > 0.02`，本次测量**不能用于**通过 P2 的 `|残差|P95 ≤ 0.05m` 物理门，需要换激光测距仪或加重复次数。

---

## §3 雷达朝向 / source 系的世界 up（§B02 关键字段二）

> 目标：把"向下看"这件事从**口语**变成**可粘进算法的数学**。不是"大约是 -Z"，而是 +X/+Y/+Z 三轴每一条的世界方向。

| 步骤 | 做法 | 记录字段 |
|---|---|---|
| 3.1 找雷达本体坐标标注 | 壳体/手册"X/Y/Z"刻印或彩色标贴；**拍照** | `body_axis_photo`: 文件名 |
| 3.2 对每轴写"指向世界哪边" | 用桌面/墙/地球重力作为参考，**逐轴**写：<br>`lidar_x_axis_world`: 例 "'east, 沿房间长边指向窗户'" <br>`lidar_y_axis_world`: 例 "'north, 指向窗边工作台'" <br>`lidar_z_axis_world`: 例 "'down, 指向地板'" | 三个 string 字段，**禁止偷懒写成 "down"** |
| 3.3 指明主动/被动 | 三轴描述对应的是"从雷达看出去的方向"（被动）还是"雷达系相对世界系的旋转"（主动）；若是后者，**附** Rodrigues 角或旋转矩阵 | `convention`: "passive_axes_from_lidar" / "active_R_lidar_to_world"; `rotation_matrix` 或 `rodrigues` |
| 3.4 向上方向定义 | 明确指出**世界 up** 在雷达系中的表达（例 "world_up_in_lidar_frame ≈ -z_lidar_unit"）| `world_up_in_lidar`: 三分量单位向量，保留 4 位小数 |
| 3.5 不确定度 | 角度误差（°）或轴向误差 | `up_direction_uncertainty_deg` |
| 3.6 异常处理 | 若安装并非严格朝下（有倾斜角），估倾斜角并记录测量方法 | `estimated_tilt_deg`, `tilt_method` |

> ❗ 已知陷阱：「PCA 拟合后取的法向」**不是**测量值。本节必须**独立**于点云算法给出结论。

---

## §4 SDK 外参 / source→world 变换绑定

> 目标：回答"SDK 输出的点云，是已经在源系里，还是已经做过一次旋转？"——GL-E01 A05 已确认无法用旧日志回答，今天**用现场做的这次运行**回答。

| 步骤 | 做法 | 记录字段 |
|---|---|---|
| 4.1 config.yaml 摘要 | 从板上 `cat src/inno_lidar_ros/config/config.yaml` 提取 `lidar[0].driver` 下：`extrinsic` / `lidar_type` / `angle_crop` / `distance_crop` / `calibrate_folder` 完整原文 | `config_excerpt`: 原文 yaml 片段 |
| 4.2 SDK 启动日志 | 找到与 §1.1 同时间窗的 SDK 日志，摘录**外参/变换**相关行 | `sdk_log_excerpt`: 原文行 + 行号 + 文件 sha256 |
| 4.3 若 extrinsic 非零 | 把 6 个数字直接记录下来，绑定 §1.2 的 config SHA | `extrinsic_value`: [x, y, z, roll, pitch, yaw] 或厂商实际字段名 |
| 4.4 若 SDK 无法绑定 | 写明"当前 config 未启用 extrinsic 且无可关联 run 日志" | `binding_status`: "bound" / "unbound_explicit_zero" / "unbound_unknown" |
| 4.5 数据源 | `msg_source: 1` 对应 live lidar；确认不是 pcap replay | `msg_source_value` |

**判定规则**：
- `binding_status = "unbound_unknown"` → 本次 B02 的一部分仍然 BLOCKED；仍可用 §5 ROI 数据但**禁止跑物理结论**。
- `binding_status = "bound"` 且 extrinsic ≠ 0 → 算法侧必须**先**用 SDK 的 R/t，再叠加 §3 的安装测量，不能两次旋转。

---

## §5 FIT 区与三个独立 validation 区

> 目标：选出 1 个 FIT + 3 个独立 holdout 区，让 §6 尺量能绑到具体的源帧 row 上。空间分布必须分散，不能是同一帧切三块。

### 5.1 现场选区原则

- 避开照片中的所有静止障碍：机器人底座 / 桌腿 / 机箱 / 花盆 / 水桶 / 纸箱 / 植物
- 每个区域直径约 **0.3–0.5 m**，区域内尽量无遮挡
- 四个区域两两间距 **≥ 1 m**（不是同一块地板切四份）
- 优先覆盖**雷达近处、中距、远处**，避开雷达正下方盲点

### 5.2 建议的 4 个 ROI 标签（基于今日照片）

| 标签 | 现场位置建议 | 为什么 |
|---|---|---|
| **`FIT_front_open`** | 画面中央，机器人与前景植物之间的空旷木地板 | 全景视野中心，最可能稳定可见 |
| **`VAL_left_desk`** | 左侧第一张办公桌**下方**的木地板（非桌面） | 近距、有遮蔽，验证算法不吸入桌腿 |
| **`VAL_right_walkway`** | 右侧长条工作台**前方走道**的木地板 | 中距，与 FIT 区不同方位角 |
| **`VAL_far_window`** | 窗边略远一处木地板（如画面右上角阳光区附近） | 远距、可能点稀疏，检验距离相关性 |

> ⚠️ 必须由**现场人员**确认这 4 个标签对应的实际物理区域；这里只是**基于单张照片的初稿建议**。

### 5.3 现场必填字段（每区一张表）

```yaml
- roi_id: "FIT_front_open"           # 与 §5.2 标签一致
  physical_description: "中央走道木地板，距雷达约2.1m"
  photo_refs: ["<ts>_FIT_front_open_panorama.jpg", "<ts>_FIT_front_open_closeup.jpg"]
  measured_height_m: 0.000          # 木地板本身高度，通常为 0
  measured_height_uncertainty_m: 0.002
  height_method: "laser_rangefinder"
  independent_from_fit: true         # 仅 validation 区必须为 true
  frame_window_hint: "<可选：录制此 ROI 时刻估计 bag 内 frame 区间>"
  observer: "<姓名>"
  observed_at: "2026-10-05T__:__:__+08:00"
  gps_or_marker: "<可选：贴纸编号或地面标记说明>"
```

**强制约束**：
- 3 个 validation 区的 `independent_from_fit` **必须**为 `true`
- 3 个 validation 区的 `frame_window_hint` **不能**与 FIT 区的 hint 重叠
- `measured_height_method` 不能是 "estimated" / "assumed"
- 任何一条 validation 区的 `measured_height_uncertainty_m > 0.005` 直接标黄

---

## §6 尺量与 ROI 绑定

> 目标：把 §5 选的 4 个区域**真的量出来**，让后续算法能用"独立尺量"做物理验证。

| 步骤 | 做法 | 记录 |
|---|---|---|
| 6.1 定点 | 每区贴一张已编号贴纸（Zone-FIT-01 / Zone-VAL-01…），**拍照** | `marker_photo` |
| 6.2 激光测距 | 雷达原点 → 每区中心的真实欧氏距离 ×3 次取中位数 | `laser_distance_m`, `median_of_3` |
| 6.3 与点云粗对 |  OPTIONAL：现场目测估算"该点在雷达坐标中应出现的方位角/俯仰角" | `expected_bearing_deg`, `expected_elevation_deg`（仅供参考，阻塞算法时不强制）|
| 6.4 记录摄影几何 | 拍摄每张 ROI 照片时**机位高度**（用作三角校核） | `camera_height_m` |

**绝不允许**：把"FIT 残差小"的区当成 validation 区。validation 区的身份必须由**本节的物理尺量**独立确定。

---

## §7 现场收尾离场前对照

离场前**当场**检查以下 6 条，任何一条不满足**留在现场继续补**，不要带着缺口回 PC：

- [ ] §1 全部 5 步已执行且有截图
- [ ] §2.2 `origin_to_floor_m` 已测 3 次且不确定度 ≤ 0.02 m
- [ ] §3.4 `world_up_in_lidar` 是**三分量向量**，不是单词 "down"
- [ ] §4.4 `binding_status` 三选一并写成字符串，**不能空**
- [ ] §5.3 4 个 ROI 各一张 yaml 表，3 个 validation `independent_from_fit=true`，4 张现场照片命名规范一致
- [ ] §6.2 每区激光测量 3 次，且全部 `median_of_3` 已记录

**离开前**把本文件 §1–§6 的填充版本**手机拍照**发回（或者就在现场填在 §8 模板里），不要等到回 PC 再补。

---

## §8 measurement_record.json 模板（回 PC 后由 AI 结构化）

> 把 §1–§6 的填充结果汇总成下面这个 JSON。**不要现场手写 JSON**——现场填表，回来让 AI 转。

```json
{
  "schema_version": "1.0",
  "field_session_id": "field_20261005_<seq>",
  "captured_at_local": "2026-10-05T__:__:__+08:00",
  "captured_at_board": "<远端 date -Is 输出原文>",
  "clock_skew_seconds_estimated": 10800,
  "captured_by": "<姓名>",
  "site_tag": "lab_main_floor",

  "board_binding": {
    "container_id_full": "<§1.1>",
    "config_sha256": "<§1.2>",
    "sdk_log_file": "<§1.3>",
    "sdk_log_mtime": "<§1.3>",
    "bag_record_start": "<§1.4 或 null>",
    "bag_record_end":   "<§1.4 或 null>"
  },

  "origin_height": {
    "origin_description": "<§2.1 原文>",
    "origin_to_floor_m": 0.0,
    "origin_height_uncertainty_m": 0.0,
    "method": "laser_rangefinder",
    "method_note": "<工具型号或 'tape_plumb_3trials'>",
    "optical_window_to_floor_m": 0.0,
    "install_unchanged_since": "<ISO8601>",
    "photo_refs": ["...", "...", "..."]
  },

  "world_up": {
    "convention": "passive_axes_from_lidar",
    "lidar_x_axis_world": "<§3.2 原文>",
    "lidar_y_axis_world": "<§3.2 原文>",
    "lidar_z_axis_world": "<§3.2 原文>",
    "world_up_in_lidar": [0.0, 0.0, -1.0],
    "up_direction_uncertainty_deg": 0.0,
    "estimated_tilt_deg": 0.0,
    "tilt_method": "<§3.6 或 null>",
    "body_axis_photo": "<§3.1>"
  },

  "sdk_extrinsic": {
    "config_excerpt": "<§4.1 原文 yaml>",
    "sdk_log_excerpt": "<§4.2 原文行>",
    "extrinsic_value": null,
    "binding_status": "bound",
    "msg_source_value": 1
  },

  "roi_list": [
    {
      "roi_id": "FIT_front_open",
      "physical_description": "<§5.3 原文>",
      "photo_refs": ["..."],
      "measured_height_m": 0.0,
      "measured_height_uncertainty_m": 0.0,
      "height_method": "laser_rangefinder",
      "independent_from_fit": false,
      "frame_window_hint": null,
      "observer": "<姓名>",
      "observed_at": "2026-10-05T__:__:__+08:00",
      "laser_distance_m": 0.0,
      "marker_photo": "<§6.1>"
    }
  ],

  "unresolved_gaps": [
    "<列出本次未补到的字段，如 'binding_status=unbound_unknown 部分'>"
  ]
}
```

**回到 PC 后**：
1. 把现场填的 §1–§6 整理上面 JSON，放入 `docs/human_fall/evidence/2026-10-05_field_<tag>/measurement_record.json`
2. 同步把 4 个 ROI 的现场照片同目录归档
3. 把 JSON 路径和 unresolved_gaps 列表告诉 Codex，**不要直接跑 GL-I06/P2**——下一步应由 Codex 复核这份证据后决定

---

## §9 谁不该在这份 checklist 上动手

- **AI**（包括我）：现场可以**陪你读**，但**不能替你估数、不能替你拍、不能替你下结论**
- **明天的 Codex / OpenCode**：在你回来交 JSON **之前**不要开工 GL-I06、不要提前跑算法研究——这份 checklist 的目的是**让物理证据先行**，避免再发生"算法在 synthetic 上 PASS 了、物理却被 BLOCKED 几个月"的情况
- **未来的自己**：离场前**一定**看 §7 的对照清单，任何一项空着就不要上车

---

## 变更记录

- **2026-10-04 v1**：首版，配合 GL-E01 收口和 GROUND_LEVELING_NEXT_STAGE_PLAN v2 制定；当前**未执行**，等待用户 10/5 现场执行。

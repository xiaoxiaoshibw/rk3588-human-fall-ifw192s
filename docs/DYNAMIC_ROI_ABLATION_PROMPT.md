# 动态 ROI 消融实验 · Codex 执行提示词

用法：在仓库根 `D:\Code\ldiar` 下把本文件从「## 提示词」起整段交给 Codex（或 `codex exec "$(Get-Content docs/DYNAMIC_ROI_ABLATION_PROMPT.md -Raw)"`）。
提示词里的行号是 2026-10-21 工作树的实测值，若已漂移，按符号名（`build_snapshot` / `TargetTracker.snapshot` / `ReplayPipeline.step`）定位，不要按行号硬编码。

本提示词不是"实现一个功能"，而是"用预注册的判定门槛回答一个问题"：在单目标已锁定后把点云裁到目标附近，到底能不能降低 CPU、且不损失目标点集与跟踪连续性。答不了就写 UNKNOWN，不要凑结论。

---

## 提示词

你在一台 Windows 开发机上，仓库是 ROS1 LiDAR 人体识别/跟踪/跌倒工程 `D:\Code\ldiar`。**只做离线软件实验，不碰板端、不部署、不采集、不改生产配置。** 先读 `AGENTS.md`、`docs/PROJECT_WORKFLOW.md`、`docs/PROJECT_STATE.md`，然后按本提示词连续执行到出报告，中途不要停下来问"要不要继续"。

### 0. 一句话任务

在 `src/human_fall_detection/` 的离线处理链里新增**可选、默认关闭**的「跟踪驱动的动态 ROI」掩码与四状态控制器，跑 A/B/C 消融，用预注册门槛回答：它是否降低单帧处理耗时，同时不减少目标点集、不增加掉锁、不制造新的碎片。当前现场仍是 RC15、工作树 RC16；本实验产物不进发布包。

### 1. 已核实事实（直接用，不要重复调研）

**处理链**：`xyz_from_cloud(preserve_rows=True)` → `core/lidar_candidates.py:834 build_snapshot` → 聚类 → `core/tracking.py` 跟踪 → 跌倒状态机。
`build_snapshot` 内部顺序（同文件）：

1. `finite = np.all(np.isfinite(array), axis=1)`，`original_indices = np.nonzero(finite)[0]`（:851）
2. `max_points` 步长截断（:852-855，`max_points` 默认 60000）
3. 距离门 `range_min_m/range_max_m`（:857-860）
4. 前置去噪 `denoise_mask`（:870-878，生产 `radius 0.1 m / min_neighbors 2`）
5. 地面相对高度门（:884-890）
6. 冻结背景 `foreground_mask`（:892-895）
7. 聚类 `spatial_components(cell=0.05)` 或水平连通（:897-900）

`original_indices` 全程只做行筛选、从不重编号，最后作为 `foreground_indices` 发布（:999）。候选 `evidence_indices` 是**同一数组域**的行号，`node_runtime` / `realdev/current/run.py` 再映射回会话 `source_rows`。`rebuild_candidate`（:812）明确规定调用方负责把会话行映射到本地数组，本实验不要改这条契约。

**三个调用方**（都要在 `roi=None` 时字节不变）：
- `core/pipeline.py:79` `ReplayPipeline.step`（离线回放）
- `core/node_runtime.py:765` `_process_locked`（板端节点，`points` 是整帧解码数组）
- `sidequests/hfus_tcms_02/realdev/current/run.py:83`（`current` 开发入口，注意它在 `build_snapshot` 之前还有 `selected` 数组与 `f['offset']` 的会话行偏移）

**跟踪状态**：`TargetTracker`（`core/tracking.py:93`）已有 `track_status ∈ {unselected, locked, occluded, lost}`、`position_m`、`velocity_m_s`、`prediction_age_s`、`last_measured_source()`、`snapshot()`（:337）；配置 `occlusion_timeout_s 1.5`、`lost_timeout_s 3.0`、`max_speed_m_s 2.5`、`velocity_smoothing 0.5`、`gate_m 0.8`、`ambiguity_margin_m 0.2`。`_predict`（:302）以最后实测点为锚 + 速度×dt，不重复积分 —— 控制器要复刻这个语义，不要自己搞卡尔曼。

**`resolve_settings`（:65）拒绝未知字段**：不能把 ROI 参数塞进 `candidates:`，会直接抛 `unknown candidate setting`。ROI 参数走独立 `roi:` 段 + 新配置文件。

**现场性能（30 s 窗口，962 s / 9277 帧）**：`process_s` P50 36 ms / P95 59 ms，`receive_to_finish` P50 46 / P95 69 ms，`queue_age` P50 10 / P95 15 ms，`queue_dropped` 累计 0，帧率 9.54–9.66 Hz，node RSS 58–68 MB。**当前全视野处理已经跟得上 9.7 Hz**，所以 ROI 的正当性不是"救实时性"，而是"省 CPU / 减少干扰候选"；如果省不下来就不值得加复杂度。

**本机数据规模**（直接读 `meta.json` 核对过）：`data/sessions/cap_20261017_113516` 780 帧 / 80.7 s / 每帧 43.7k–49.1k 点（均值 49,102，最大 49,133 < `max_points 60000`）；`data/sessions/cap_20261018_110029` 386 帧 / 每帧均值 49,098。两个会话 `human_annotations` 都是空数组 —— **没有人体的点级 GT**。

**已知缺陷（不要声称 ROI 能修）**：`fall_fast_walking` 合成场景在 30.292645942 s 人体裂成 420/482 两簇 → `ambiguous` → `unselected`，整段无疑似。这是"同一个人内部点集不连通"，ROI 只能减少远处干扰，不会自动把两簇连起来。实验里要单独报告 ROI 对它的影响，不许拿它当 ROI 的功劳或罪名。

### 2. 与初稿的三处硬性修正（照这个做，不要按直觉改回去）

1. **掩码位置放在步长截断之后、距离门之后、去噪之前**，而不是有限值检查之后。原因：`max_points` 步长由整帧点数决定，若在它之前裁 ROI，ROI 内的点密度会从 stride=2 变成 stride=1，"变好"可能只是点数变多。放在去噪之前仍能省掉去噪/背景/聚类/几何的全部开销（这三处是实测大头），索引语义完全不变。当前两会话 49.1k < 60k，stride 恒为 1，这个混淆暂时为零，但代码不能靠数据巧合正确。另外提供 `roi_before_stride=True` 的**对照变体 C′**，专门量化"密度红利"，默认关闭。
2. **ROI 定义在地面切平面坐标系**，用 `ground_plane_basis(ground)`（:101）给出的 `normal/u/v`，不要用原始传感器 XY（雷达有安装倾角）。垂直方向给**宽松**带（默认 `[-0.10, 2.50] m` 地面相对高度），不要随站立身高收紧。
3. **半径必须覆盖平躺几何**：躺倒的人水平跨度可达 1.8 m，站立中心圆 0.6–0.8 m 会在跌倒瞬间把头/腿切掉。默认 `roi_base_radius_m = 1.5`，并提供 `roi_lie_safe_radius_m = 2.0` 变体做对照；两种都要在合成躺姿帧上测"裁掉多少目标点"。

地面不可用（`ground=None` 或 `status != valid` 或 frame 不匹配）时：**拒绝应用 ROI，退化为全视野**，并在 `quality` 里写明原因，不要静默按原始 XY 硬裁。

### 3. 实验设计（8 个臂，先小后大）

| 臂 | 定义 | 实现 |
|---|---|---|
| A | 全局（现状） | `roi=None`，不传 `--search-bounds` |
| B | 固定 ROI | 复用现有 `realdev/current/run.py --search-bounds XMIN XMAX YMIN YMAX ZMIN ZMAX` 的语义（RAW 轴对齐盒，在 `build_snapshot` 之前裁剪），取 A 锁定段目标包围盒 ±0.5 m，**全程不变** |
| C | 动态 ROI | 新掩码 + 控制器，默认 `margin 0.8 m`、预测开、`k=1`、半径 1.5 m |
| C1 | 关预测 | 同 C，`roi_prediction=false`（隔离速度项） |
| C2 | margin 0.5 | 同 C，`roi_margin_m=0.5` |
| C3 | margin 1.0 | 同 C，`roi_margin_m=1.0` |
| C4 | 躺姿安全半径 | 同 C，`roi_base_radius_m=2.0` |
| C′ | 掩码前置 | 同 C，`roi_before_stride=true`（只用于量化密度红利） |

先全跑 A/C（两个会话），再按 §7 的判据挑 2 个变体补跑其余臂；B 只用来证明"固定框会漂走"，不需要跑全部输入。

**预注册划分**（防止过拟合）：参数默认值只在 `cap_20261018_110029`（386 帧）上选；`cap_20261017_113516`（780 帧，新录制）只做验证，不再回头调参。如果两者结论冲突，**以 780 帧验证会话为准**并如实写冲突。

### 4. 实现契约

**4.1 `build_snapshot` 新签名**（关键字参数，默认 `None`，保证三处调用方零改动的字节等价）：

```python
def build_snapshot(points, settings=None, *, session_id, time_epoch, snapshot_id,
                   seq=None, stamp_secs=None, stamp_nsecs=None,
                   source_stamp_s=None, frame_id="innolidar", ground=None,
                   calibration=None, transform=None, background=None, note=None,
                   roi=None, timings=None):
```

- `roi=None` → 走原路径，**输出必须与改动前逐字节相同**（用现有 386 帧固定回放对比 SHA）。
- `timings` 只在非 `None` 时用 `time.perf_counter()` 记 `finite_s/stride_s/range_s/roi_s/denoise_s/ground_s/background_s/cluster_s/geometry_s`，默认不启用，不影响输出。

**4.2 ROI 字典**（由控制器产生，纯数据，可 JSON 序列化）：

```python
{"schema": 1, "state": "locked"|"lost", "predicted": bool,
 "center_ground_m": [u, v],            # 地面切平面坐标（预测位置在 u/v 上的投影）
 "radius_m": float,                    # 水平半径
 "height_band_m": [hmin, hmax],        # 地面相对高度
 "basis": {"normal": [..], "u": [..], "v": [..], "offset_m": float},
 "predicted_from_s": float, "dt_s": float}
```

`state` 只有 `locked` / `lost` 两种取值：`SEARCH` 与 `RECOVER` 直接返回 `None`，不产生字典。

掩码条件（与 `build_snapshot` 既有高度门同一套公式 `h = p·n + offset_m`，见 :886）：`hmin <= p·n + offset_m <= hmax` 且 `((p·u)-u0)^2 + ((p·v)-v0)^2 <= r^2`，其中 `u0 = center_pred·u`、`v0 = center_pred·v`；全部 float64、与 `build_snapshot` 同样用向量化 numpy。半径非有限 / `< 0.3 m` / basis 非正交单位 → 抛 `ValueError`，不静默兜底。

**4.3 诊断字段**（只在 `roi` 生效时写入 `snapshot["quality"]["roi"]`，`roi=None` 时不得新增任何键）：

```
{"state","predicted","radius_m","margin_m","center_ground_m","height_band_m",
 "input_point_count","kept_point_count","dropped_point_count",
 "shell_point_count",        # r*0.9 到 r 之间的点数：>0 说明目标贴边，截断风险
 "ground_available": true, "refusal_reason": null}
```

`quality["reasons"]` 追加 `roi_applied` 或 `roi_refused_ground_unavailable`（后者只在显式传了 `roi` 但地面不可用时）。

**4.4 控制器**：新文件 `src/human_fall_detection/core/roi.py`，纯算法、无 ROS、无时间副作用（时间一律由调用方传 `source_stamp_s` / `dt_s`）。

```python
class RoiController:
    def __init__(self, settings=None): ...
    def update(self, track_snapshot, ground, source_stamp_s, dt_s=None) -> dict | None
```

`track_snapshot` 就是 `TargetTracker.snapshot()` 的字典，控制器只读它，不 import tracker、不碰私有字段。

四状态：
- `SEARCH`（`track_status == "unselected"`）→ `None`（全视野）。
- `LOCKED`（`track_status` 为 `locked`，或 `occluded` 且 `prediction_age_s < occlusion_timeout_s`）→ ROI 中心 = 最后实测位置 + `velocity_m_s × dt`（按 `max_speed_m_s` 截断），`radius = base + margin + k·σ`，`σ = min(max_sigma_m, 0.5·max_speed·prediction_age_s)`；`k = k_sigma`。
- `LOST`（`occluded` 超时或 `lost`）→ 半径按 `roi_expand_m_per_s`（默认 0.8 m/s）单调扩张，从 `last_radius` 到 `recover_radius_m`（默认 4.0 m）。
- `RECOVER`（扩张到 `recover_radius_m` 或 `lost_elapsed ≥ lost_timeout_s`）→ `None`（全视野重捕获）。

约束：状态机对 1 帧遮挡有滞回（不闪断）；重新锁定时半径按 `roi_shrink_m_per_s`（默认 2.0 m/s）收，不瞬间收缩（刚锁定的中心可能是错的）；`SEARCH→LOCKED` 的第一帧仍是全视野（当帧 `build_snapshot` 在跟踪更新之前执行，天然满足，不要为了"早点省"而用当帧候选反向决定当帧 ROI）。

**4.5 接线**：只接 `ReplayPipeline`（`settings.get("roi")`，默认 `None` 关闭）。`node_runtime` 只加一行可选参数透传、默认不启用，**不得**改变现场行为；`realdev/current/run.py` 不动（B 臂复用它现有的 `--search-bounds`）。

**4.6 配置**：新建 `src/human_fall_detection/config/perception_roi_v1.yaml`，内容 = `perception_single_target_v2.yaml` 的逐字节副本 + 末尾 `roi:` 段；**不得改 v1/v2/default/geometry/geometry_constrained*/human_fall*/prod**。`roi:` 段字段：

```yaml
roi:
  enabled: false
  base_radius_m: 1.5
  margin_m: 0.8
  k_sigma: 1.0
  max_sigma_m: 0.5
  height_band_m: [-0.10, 2.50]
  prediction: true
  expand_m_per_s: 0.8
  recover_radius_m: 4.0
  shrink_m_per_s: 2.0
  before_stride: false
```

**4.7 跑批器**：新建 `src/human_fall_detection/scripts/roi_ablation.py`：
`--arm {A,B,C,C1,C2,C3,C4,CPRIME} --session <data/sessions/...> --outdir <全新空目录> [--config perception_roi_v1.yaml] [--search-bounds XMIN XMAX YMIN YMAX ZMIN ZMAX] [--limit-frames N]`。B 臂在 `build_snapshot` 之前按 RAW 轴对齐盒裁 `selected`（与 `realdev/current/run.py` 同语义，也同它一样把 `search_bounds` 写进 summary，不要冒充成 ROI 控制器）。逐帧写 `frames.jsonl.gz`（`frame,t_rel_s,track_status,track_id,roi_state,roi_radius_m,target_rows,len(target_rows),points_in,points_kept,dropped,shell,timings_s,cluster_count`）+ `summary.json`（SHA、配置、门限、分位数）。`outdir` 非空直接拒绝；不写 `data/`。

### 5. 输入与命令

```powershell
# 基线（改动前先跑一次，存日志）
python -B -W error -m unittest discover -s src/human_fall_detection/tests

# 386 帧开发会话（参数选择集）
python -B -W error src/human_fall_detection/scripts/roi_ablation.py --arm A --session data/sessions/cap_20261018_110029 --outdir docs/evidence/<date>_dynamic_roi_ablation/raw/A_386

# 780 帧验证会话（只验证，不调参）
python -B -W error src/human_fall_detection/scripts/roi_ablation.py --arm C --session data/sessions/cap_20261017_113516 --outdir docs/evidence/<date>_dynamic_roi_ablation/raw/C_780
```

`<date>` 用当天（2026-10-21 起）。等价性基线是**同一配置**下的改动前输出：改动前先用这份 `perception_roi_v1.yaml` 跑一次 A 臂存 SHA（不改代码），改动后再跑对比。历史 `current/LATEST.json` 绑定的是 `docs/evidence/2026-10-21_tracking_repair_dev/release_current`，那轮用 `perception_single_target_v1.yaml`；本实验的 roi 配置复制自 v2，两者差 `entry_support_static_tolerance_m` 等字段，**只能逐帧比业务字段并说明配置差异，不能直接比 SHA**。

可选（有就做，没有就记 UNKNOWN，不要下载或转码别的数据）：591 帧真人 MCAP `C:\Users\30680\Downloads\ifw192s_20261020_222555.mcap`（SHA `d79c8cfb6037d0fd48ed956730d790d22950012681ca9d72957ba802b26920a0`，61.25 s，591 帧）与 `docs/evidence/2026-10-20_fall_scenario_chain/` 的 10 个合成场景。MCAP 读取参考 `docs/evidence/2026-10-20_person_walk_stand_raise_exit/{mcap_input.py,replay_mcap.py}`（**只读参考，不改 evidence**）；如要复用，把读取器复制成新文件 `src/human_fall_detection/scripts/mcap_points.py` 并标注来源，不要在 evidence 目录里写任何东西。

### 6. 指标

逐帧（每臂每个输入）：见 §4.7 字段。其中 `cluster_count` 只统计与目标中心最近的簇，用来观察碎片化，**不要**把它当人体识别率。

聚合（每臂每输入）：
- `process_s` P50/P95/max，按阶段拆（`roi_s` 单独列，不要把它算进"省下的时间"里）—— PC 实测，**不是板端**。
- `points_kept / points_in` 比例；`dropped` 绝对值。
- `locked_frames`、首次锁定时刻、`occluded/lost` 次数、`ambiguous` 次数、状态转移序列。
- **截断率（核心，无需 GT）**：以 A 臂同帧的 `target_rows` 为参照，
  `clipped_rate = |rows_A \ rows_C| / |rows_A|`（两侧都是同一数组域的行号，可直接做集合差），
  以及 `rows_C \ rows_A`（多出来的点，通常来自邻居/家具）。
  报告锁定帧上的均值、P95、最大值，和"目标点数 < `min_cluster_points`（v2 = 30）"的帧数。
- `shell_point_count > 0` 的帧占比（贴边预警）。

### 7. 预注册判定门槛（先写下来再跑，跑完逐条打勾或打叉）

- **G1 等价**：同一配置、同一输入下，改动前后 `roi=None` 的输出**逐字节相同**（`frames.jsonl.gz` 与 `summary.json` 的 SHA 一致）。不通过 → 停止，先修 bug。附加项（不计入门槛）：用 `perception_single_target_v1.yaml` 跑 386 帧，与 `release_current` 逐帧比业务字段，差异必须能归因到配置而不是本次改动。
- **G2 不裁人**：780 帧验证会话锁定帧上 `clipped_rate` P95 ≤ 2%、max ≤ 10%，且没有一帧因 ROI 掉到 `min_cluster_points` 以下。不通过 → 该臂淘汰，不做"再调调 margin"式抢救。
- **G3 不掉锁**：A 锁定而 C 未锁定的帧数 = 0；新增 `ambiguous` = 0；新增 `lost` = 0。若有，逐帧列出并解释是 ROI 造成还是本来就有。
- **G4 值得**：`process_s` P95 相对 A 至少 −25%（PC），且 G2/G3 同时成立，才建议"值得进下一步"。若只降 5–15%，如实写"不值得加这套复杂度"，不要为了有产出而推荐采用。
- **G5 躺姿安全**（仅当合成躺姿/跌倒场景可跑）：躺姿帧 `clipped_rate` P95 ≤ 5%，且 `suspected` 帧数不减少。跑不了 → 写 UNKNOWN，不允许引用别人旧结论。
- **G6 不放宽负例**：空场前缀、家具帧不得新增目标轨迹；`confirmed` / `mode_verified` 全程 false。

任一条**打叉**都要在报告里保留该臂的失败产物，不许只留成功臂。

### 8. 交付物

代码：
- `src/human_fall_detection/core/roi.py`（控制器 + 掩码，纯算法）
- `core/lidar_candidates.py` 的 `build_snapshot(roi=…, timings=…)` 与 `quality.roi` 诊断
- `core/pipeline.py` 的 `roi` 接线（默认关闭）
- `core/node_runtime.py` 仅透传参数（默认关闭，行为不变）
- `config/perception_roi_v1.yaml`（新文件，不动旧配置）
- `scripts/roi_ablation.py`（跑批 + 汇总）

测试（新建，放在 `src/human_fall_detection/tests/`）：
- `test_roi_mask.py`：`roi=None` 输出逐字节不变；掩码行集合与手算一致；`original_indices` 是整帧行号的子集且单调；地面不可用 → 拒绝并全视野；半径非法 → 抛错；`before_stride` 只影响点数不影响索引含义；边界点（恰好 r、恰好 hmin）行为固定。
- `test_roi_controller.py`：四状态转移；1 帧遮挡不闪断；扩张/收缩单调且限速；`velocity=None` 不外推；`dt` 用 `source_stamp_s` 而非墙上时钟；`max_speed` 截断；重捕获回到 `None`。
- `test_roi_ablation_smoke.py`：30 帧小样本跑通 A/C，产物字段齐全、`summary.json` 可解析、`outdir` 非空拒绝。

证据目录 `docs/evidence/2026-10-21_dynamic_roi_ablation/`：
`README.md`（结论 + 逐条门槛 + 已知限制）、`BASELINE.json`（改动前全仓 tracked+非忽略 untracked SHA，排除 `data/` 与 junction）、`preimages/`（将被改文件的原件）、`raw/<ARM>_<frames>/`、`COMPARE.json`（逐臂逐帧 join 后的截断率/转移/耗时）、`TIMING.md`（分阶段 P50/P95，注明 PC）、`TEST_RUNS.log`、`SHA256.json`。

`docs/PROGRESS.md` 追加一节（日期 + 标题 + 5–8 条事实条目），**不要**改历史条目；`docs/PROJECT_STATE.md` 只在 G1–G4 全过、准备进下一步时才更新，并明确"未部署、现场仍 RC15"。

### 9. 禁止项（违反任一条即视为本轮失败）

- 不改 `default.yaml`、`geometry.yaml`、`geometry_constrained*.yaml`、`human_fall.yaml`、`human_fall_prod.yaml`、`perception_single_target_v1/v2.yaml`、`single_target_geometry_v*.json`。
- 不改 `data/`、`captures/` 与三个 junction；不做删除、移动、改名。
- 不动 `docs/evidence/` 下任何历史目录（只读参考）；不写 `tmp_gl_diag/`。
- 不 commit / push / reset / checkout / clean；不部署、不连板端、不重启、不采集、不下载数据、不训练、不开 HR-09。
- 不加第三方依赖（板端 Python 3.8 + stdlib + NumPy 1.17 约束，代码要能在 3.8 语法下解析）。
- 不改 `pc_apps/human_core` 的 JS 引擎（那是独立同构引擎，改它会破坏 parity），不改 `webui/`。
- 不用"A 臂输出"以外的任何东西当人体参照；不把 `locked` 当"识别人"；不把 `suspected` 当"跌倒召回"。

### 10. 执行顺序与停止条件

1. 记录前件：`git rev-parse HEAD`（只读）、全仓 SHA、将被改文件复制到 `preimages/`。
2. 跑基线测试，存 `TEST_RUNS.log`（含 pre-existing failure，标注"改动前已存在"）。
3. 实现 `roi.py` + `build_snapshot` 参数 + 单元测试，先只保证 `roi=None` 字节等价（G1）。
4. 实现控制器并接 `ReplayPipeline`，30 帧 smoke。
5. 386 帧上跑 A/C 与变体，选定默认参数（写进 `perception_roi_v1.yaml`）。
6. 780 帧上只跑已定参数（不许回头调），算 G2/G3/G4。
7. 若有 MCAP/合成场景，补 G5/G6；否则 UNKNOWN。
8. 写 `README.md` 的结论节：**建议采用 / 不建议采用 / 证据不足**，三选一，必须给数字支撑。

**提前停止**：G1 不过就停在第 3 步修 bug；G2 在 C 默认臂上就 >10% P95 且肉眼可见整块缺失 → 停，写"该几何下 ROI 不可行"，不要靠调大 margin 硬凑（margin 越大收益越小，最后会退化成全视野）。

### 11. 报告口径（硬性）

- 所有耗时都标"PC / Python 3.12 开发机"，**不得**写成板端或端到端；板端性能 UNKNOWN（除非用户另行授权在板端跑只读计时）。
- 人体点级 GT、真人跌倒召回/精确率、物理配平：全部 UNKNOWN，不因为几何/软件通过而改写。
- 合成运动不是真人跌倒；`locked` 帧数不是"识别率"；`clipped_rate` 是相对 A 臂的几何一致性，不是"裁掉了多少人"。
- 结论里必须有一句"本实验未证明 ROI 对跌倒检测的影响"（除非 G5 真正跑完并有数字）。

### 12. 完成自检（逐条填数字，不许写"约"）

- [ ] A 臂 386 帧与改动前同配置基线 SHA 一致：`______`
- [ ] `roi=None` 单元测试字节等价：`通过/失败`
- [ ] 780 帧 A 臂：locked `__` 帧，process P50/P95 `__/__ ms`
- [ ] 780 帧 C 臂：locked `__` 帧，process P50/P95 `__/__ ms`，`points_kept/in = __%`
- [ ] G2 截断率：均值 `__%`，P95 `__%`，max `__%`
- [ ] G3 差异帧：`__` 帧（附清单或 0）
- [ ] G5 躺姿：`已跑（数字）/ UNKNOWN`
- [ ] 结论：`建议采用 / 不建议采用 / 证据不足`，一句理由 `______`
- [ ] 未改冻结配置/未动 data/未部署/未 commit：`是/否`
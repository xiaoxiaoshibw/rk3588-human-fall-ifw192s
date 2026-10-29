# 单人算法：把"几何目标"变成"几何上确定是一个人"的状态机

- 日期：2026-10-28
- 范围：**单人、单目标**。多人检测（数据关联、排他、跨人基线）只留接口，不在本轮实现。
- 语义边界：本文所有"人体相容/人形先验"都是**几何判据**；人体身份、跌倒真值、准确率/召回率仍为 **UNKNOWN**。

## 1. 单人场景到底要回答什么

一帧点云进来，单人系统要能回答四件事，缺一件都不算可用：

1. **有没有人**（不是"有没有前景团块"）；
2. **人在哪**（同一目标跨帧连续，不能每帧换一个团块）；
3. **人在什么姿态**（站 / 坐蹲 / 躺），且这个姿态不能因为遮挡、碎片、阈值边界跳变；
4. **状态怎么变**（站→下降→躺→恢复），以及"我没看清"时要明确输出未知，而不是编一个状态。

现有实现（`RangeRuntime`）已经把 1–4 的**几何底座**都做出来了：距离图前端、空场背景、连通域、体素支撑关联、地面相对高度分位、PCA 主轴、时序特征、规则状态机。缺的是三条把"团块"变成"人"的桥：人体相容性、单人选择策略、相对基线。

## 2. 现有实现的四个具体缺口（代码级）

| 缺口 | 位置 | 后果 |
|---|---|---|
| 选择分数只看点数和距离 | `core/range_tracker.py` 的 `selection_score = log1p(n)/max(0.5, r)` | 近处小而密的物体必然赢过远处的人 |
| 没有任何"这块几何能不能是人"的判据 | 全链 | 1.1 m 高的门框/柜边、0.15 m 宽的竖条都会被当成目标锁定 |
| 躺倒支持只有"高度低 或 跨度长" | `core/fall_state.py: _lying_support` | 少了最强的信号：**主轴垂直度崩塌**；蹲下/坐地也满足高度条件 |
| 站立基线未接入 | `core/range_runtime.py` 两处 `baseline=None` | 动作状态恒为 `baseline_not_ready`，没有"同一目标下降了多少" |

## 3. 本轮实现的三件套

### 3.1 `core/human_prior.py`（新）

纯 NumPy、Python 3.8 兼容、确定性输出，不读 ROS、不读时钟。

```python
describe(frame, rows, ground)   # 完整描述子 + 姿态相容分档
quick_screen(xyz, ground)       # 无 PCA 的廉价分档（逐组件预筛）
choose_single(entries, previous_track_id=None)  # 单人排他选择 + 迟滞
```

特征（全部在地面系里算，`z=0` 是地面）：

| 组 | 量 |
|---|---|
| 高度 | `top_m` / `bottom_m` / `height_span_m`(p90−p10) / 五分位 |
| 水平 | `horizontal_span_m`(p5–p95 主方向) / `horizontal_span_uv_m` / `footprint_elongation` |
| 体素 | `footprint_area_m2`、`occupied_voxels_2d/3d`、`occupancy_2d/3d`、`vertical_fill` |
| 剖面 | `height_histogram`（0.1 m 分层归一化）、`tier_width_m`（每层水平宽度） |
| 接地 | `ground_contact_fraction`（最低 0.1 m 层占比） |
| 形状 | `aspect_height_over_footprint`、`verticality`、`eigenvalues_m2`、`axis_ambiguous` |
| 距离 | `range_median_m`、`points_per_m2`、`distance_compensated_count`（`n/r²`） |

分档（`class`）：`standing_geometry` / `sitting_geometry` / `lying_geometry` / `fragment` / `planar_structure` / `not_compatible` / `unknown`。前三个 `compatible=True`。`unknown` 表示**无法评估**（点太少、缺地面），下游允许它继续占用目标但优先级最低；`fragment` / `planar_structure` / `not_compatible` 直接不参与选择。

`describe` 输出里固定带 `semantic='UNKNOWN'`、`identity='UNKNOWN'`、`definition='anthropometric_geometry_only_not_identity'`，避免下游把相容当成识别。

### 3.2 `core/range_tracker.py`（改，默认不改行为）

新增三个开关，写进 `SETTINGS` 也就是 `config_sha256`：

| 开关 | 默认 | 作用 |
|---|---|---|
| `human_prior_enabled` | `True` | 每条实测轨迹附 `human_prior` 块 + `single_person_policy`（影子，不改变选择） |
| `single_person_lock` | `False` | 由 `choose_single` 决定目标：碎片/平面/形状不相容不参与，无人形目标时**不锁** |
| `drop_fragment_candidates` | `False` | 碎片在关联之前就被剔除（`dropped_fragments` 留证） |

输出新增 `single_person_policy`（策略、理由、歧义标记、被拒列表）和 `dropped_fragments`。默认影子模式的行为与改动前逐帧一致（868 项核心测试全绿）。

### 3.3 `pc_apps/range_fall/human_prior_probe.py`（新）

与 `session_compare.py` 同一条链（同一 `RangeRuntime`、同一非因果背景、同一离线地面），额外对每帧**所有实测轨迹**跑 `describe`，再把 `choose_single` 的选择和跟踪器实际输出逐帧对比。这是"接入前后会改变什么"的唯一可信口径。

## 4. 判据为什么这么定（四段实测，905 帧）

四段开发会话（后倒/前倒/慢倒/系鞋带弯腰），795 帧有锁定目标：

| 版本 | 相容目标帧 | 非人形目标帧 | 策略改判帧 | 说明 |
|---|---|---|---|---|
| v1（初值） | 620 (78.0%) | 175 (22.0%) | 175 | `lying_top≤0.75`，无接地门 |
| v2（收紧接地） | 623 (78.4%) | 172 (21.6%) | 174 | 接地门 0.5/0.5/0.35 → 误拒"腿被家具挡住"的坐姿 |
| **v3（最终）** | **632 (79.5%)** | **163 (20.5%)** | **165** | 接地门放宽到 1.0/0.7/0.4，躺倒 top 放宽到 0.85 并接受"跨度或低垂直度" |

三条关键结论：

1. **误锁是可测量、可门控的**：163/795（20.5%）的锁定目标与任何人体姿态都不相容。主导形态是 **0.1–0.2 m 宽、约 1.1 m 高的竖直细条**（各段反复出现同一位置，属静止场景物：门框/柜边/墙面细节），以及**弯腰时被切成腿+躯干的碎片**。这正是现场记录的"静止小目标先被锁定"。
2. **策略在这些帧全部拒绝该目标**：163 个非人形目标帧里，122 帧改为"不锁"、41 帧改选当时另一条人形相容轨迹；另有 2 帧目标本身相容、但策略选了另一条相容轨迹（合计改判 165 帧）。反过来，**相容目标帧的策略改判率很低**：632 帧里 630 帧与跟踪器一致。
3. **阈值边界曾经误伤真人**：`houdao` 第 116 帧 top=0.7515 m、跨度 0.91 m、垂直度 0.24 是标准躺倒，却被 v1 的 0.75 卡掉 → 放宽到 0.85 并加"跨度或低垂直度"作为躺倒支持。这类边界必须有实测数据才能发现，不能只靠合成用例。

帧内"相容轨迹条数"分布（v3，905 帧）：1 条占 667 帧、0 条 227 帧、≥2 条 11 帧。说明单人先验**有选择性**（不是放行一切），且"两个人形团块"在本数据里罕见——多人场景的排他问题确实可以放到后面。

## 5. 输出怎么用（Qt / 服务 / 回放）

- `record['tracks'][i]['human_prior'] = {class, compatible, posture, reason, available, semantic}`：逐轨迹诊断，可显示"目标已跟踪 · 人体相容(躺)/不相容(碎片)"。
- `record['single_person_policy']`：本帧策略选择、理由（`best_compatible_target` / `previous_target_retained` / `no_human_compatible_target`）、`ambiguous` 与 `rejected` 列表。
- 界面文案要求：**"目标已跟踪 / 人体相容 / 人体身份未知"三层分开写**，不出现"已识别人体"。

## 6. 单人算法下一步（按此顺序，每步都可独立验收）

1. **姿态状态机（本轮没做）**：把 `unknown/upright/descending/low/...` 拆成两层——几何姿态层（`standing / sitting / lying / transitioning / unknown`，带 ≥0.2 s 最短驻留与迟滞），动作状态机在姿态层之上判跌倒。判据用实测可分维度：`Δverticality ≥ 0.3` 与/或 `Δtop ≥ 0.35 m` 同时发生、`horizontal_span ≥ 0.8 m`、`descent_rate ≥ 0.35 m/s`、终点 `top ≤ 0.7`、持续 1.5 s / 3.0 s、恢复撤销。
2. **接入站立基线**（一行改动）：

```python
# core/range_runtime.py: __init__
self.baseline_collector = StanceBaselineCollector(identity['session'])
# rules()
track = dict(track_id=record['target_track_id'], time_epoch=record['generation'],
             selection_version=record['generation'], action_generation=record['generation'],
             calibration_version=self.ground_sha or 'ground_unavailable',
             track_status='locked' if rows else 'unselected', position_predicted=False)
snapshot = self.baseline_collector.feed_automatic(candidate, track, record['time_s'])
features = self.features.update(observation, baseline=snapshot['baseline'])
state = self.state.update(features, observation, baseline=snapshot['baseline'])
```

之后 `height_drop_m` / `descent_rate` / 恢复判据才有意义，`baseline` 从字符串 `'not_supplied'` 变成 `{status, reason, sample_count, baseline}` 供 Qt 显示"基线采集中 1.2/3.0 s"。

3. **按会话复核阈值**：本次阈值来自四段开发数据 + 合成用例，必须在**新采集**的会话上复算（尤其 `lying_top_max_m=0.85`、`planar_thickness_max_m=0.25`、`fragment` 的两个跨度上限）。
4. **开锁策略的取舍**：把 `single_person_lock` 打开会把 20.5% 的"当前目标"变成"无目标"。要先用带真值的片段确认这些帧里没有真人在遮挡下被误拒（`houdao` 第 55/158–168 帧是候选风险点），再决定是否默认开启。
5. **多人预留**：`choose_single` 的输入已经是"每轨迹一个协议条目"，多人时替换为 `assign_targets`（贪心/匈牙利 + 排他 + 每人独立 `track_id/generation/baseline`），`human_prior` 与 `baseline` 的绑定字段不用改。

## 7. 复现与产物

```
python -B -W error -m unittest discover -s src/human_fall_detection/tests         # 868 项
python -B pc_apps/range_fall/human_prior_probe.py \
    --session data/sessions/cap_20261028_houdao \
    --out docs/evidence/2026-10-28_single_person_prior/replay_houdao
```

- 逐帧账本与汇总：`docs/evidence/2026-10-28_single_person_prior/`（`AGGREGATE.json`、`replay_*/PROBE.json`、`baseline_v1|v2/` 三轮对照）。
- 前端调研与 3D/2D 特征全表：`docs/human_fall/HUMAN_ID_ENGINEERING_PLAN.md`。
- 开销：`describe` 约 **3.5 ms/轨迹**（1200 点）、`quick_screen` 约 **0.7 ms/组件**（本机 Python 3.12）；影子模式每帧增加约 4–10 ms，板端（Python 3.8 / RK3588）需实测。

## 8. 边界

- 无人体验证真值：所有"相容/不相容"都是几何计数，不是准确率；`confirmed` 仍关闭。
- 四段数据是非因果整段背景 + 离线 RANSAC 地面（`runtime_eligible=false`），不能直接外推到板端在线链。
- 阈值只在开发集上调过；`houdao` 的 12 个拒绝帧里有 1 帧（第 55 帧）可能是被遮挡的真人，属于已知风险。
- 本轮没有部署、采集、训练、下模型，也没有改驱动/网络/数据。
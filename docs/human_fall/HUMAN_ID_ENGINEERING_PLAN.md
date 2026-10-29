# 人体识别的工程实现路线：3D 体素特征、2D 距离图与本项目落点

- 日期：2026-10-28
- 性质：技术调研 + 落地方案，不含算法改动、不连设备、不训练、不下模型。
- 语义边界：本文所有"人体相容""人形先验"都是**几何判据**，不是人体身份或跌倒真值；准确率/召回率仍为 **UNKNOWN**。

## 0. 先给结论

> **实施进展（2026-10-28 晚）**：§5 的 Step A（`core/human_prior.py`）与单人选择策略（`choose_single`）已落地并在四段会话上做过同链路 A/B，`core/range_tracker.py` 已接线（默认影子）。当前实现细节、实测数字与下一步（姿态状态机、基线接线）见 [SINGLE_PERSON_ALGORITHM.md](SINGLE_PERSON_ALGORITHM.md)。本文保留完整调研与算法选型依据。

1. 工业界并没有"识别体素特征"这种独立算法。点云里认人只有三条可落地路线：
   - **几何先验 + 浅层分类器**（人体尺度/姿态描述子 → 规则或 GBDT/SVM）：小样本、可解释、CPU 可跑，室内养老/看护场景的主流工程做法。
   - **体素/柱体深度学习**（VoxelNet、SECOND、PointPillars、CenterPoint、DSVT）：需要上万级标注目标框和 GPU 训练，行人只有 2–3 个体素宽，室内近距离更依赖 0.05–0.1 m 体素。
   - **距离图 2D 语义分割**（RangeNet++、SalsaNext、LENet）：把点云球面投影成 H×W 图，用 2D CNN 出像素级类别；算力最省，但受角度分辨率硬约束。
2. 本项目**不缺"体素化"**：`support_cells(xyz)` 已经在做 0.1 m 体素支撑，`range_shape.shape_features` 已经在做距离图像素级描述子，`lidar_candidates.rebuild_candidate` 已经在做地面相对高度分位 + PCA 主轴。缺的是四层：
   - (a) **人体相容性判别**：现在没有任何"这块几何能不能是一个人"的判据；
   - (b) **目标选择的先验**：`selection_score = log1p(点数)/max(0.5, 距离)`，近处点多的物体结构上必然赢过远处的人；
   - (c) **站立基线接入**：`range_runtime.rules` 里 `baseline=None` 是硬编码；
   - (d) **事件级证据链与真值**：低位提示 ≠ 跌倒，且没有会话级标签。
3. 用你们自己的四段离线账本（`docs/evidence/2026-10-28_demo_four_sessions/`）做了一次量化摸底，两个结论直接决定下一步怎么做：
   - 当前锁定的目标帧里 **12–30% 与任何人体姿态都不相容**（多出现在弯腰/慢倒时的碎片与换轨），说明"误锁"是可测量、可门控的，不是玄学。
   - 跌倒与弯腰/蹲下的可分维度是**主轴垂直度崩塌 + 水平跨度变长**，不是高度阈值：跌倒段低位时 `vt` 落到 0.00–0.12、水平跨度 1.28–1.53 m；弯腰段低位时 `vt ≥ 0.46`（多数 ≥ 0.9）、跨度最大只有 0.88 m。
   - 明细见 `docs/evidence/2026-10-28_human_prior_feasibility/`（`FEATURES.json`、`run.log`、`analyze.py`）。

## 1. 现状：这条链路每一段到底做了什么

| 段 | 实现 | 输出 | 位置 |
|---|---|---|---|
| 采集/解码 | 原生 ring×column 标定表做确定性最近回波，**不插值、不补点** | `RangeFrame`（range_m/valid/source_rows/intensity/point_time） | `core/range_image.py: ScanGrid.decode` |
| 前景 | 逐射线空场背景（在线：显式空场前缀；离线：整段分位，声明为非因果） | 前景掩码 + 状态 | `core/range_background.py: RayBackground` |
| 去噪 | 邻域一致性 | 清洗掩码 | `core/range_denoise.py: denoise` |
| 连通域 | 8 邻域 + 深度连续性 + 水平 run 优化；可选 3D 碎片合并 | 组件（≥15 点保留） | `core/range_components.py` |
| 关联/跟踪 | 预测中心门 + 射线支撑 + 运动补偿体素支撑；歧义显式阻塞 | 轨迹、目标、`selection_score` | `core/range_tracker.py: RangeTracker.update` |
| 目标选择 | `score = log1p(n)/max(0.5, r)`，次优 ≥0.9×最优即"竞争目标" | 单一目标 | `core/range_tracker.py:219` |
| 3D 几何 | 地面相对高度分位、包围盒、PCA 特征值/主轴/垂直度 | candidate | `core/lidar_candidates.py: rebuild_candidate` |
| 时序特征 | 高度历史、下降速率（线性拟合斜率）、近地持续时长 | features | `core/features.py: FeatureExtractor` |
| 规则 | 下降/低位/恢复/躺倒几何；`confirmed` 关闭 | 状态 | `core/fall_state.py`、`core/range_posture.py` |
| 基线 | 收集器写好了（`feed_automatic` 也在），但运行时**没有实例** | 无 | `core/baseline.py` vs `core/range_runtime.py:83,86` |
| 2D 旁路 | 距离图像素级形状（bbox/填充率/方位俯仰跨度/`fragments`） | 仅影子诊断 | `core/range_shape.py` |

结论：链路本身是合格的"几何目标检测器 + 几何状态机"。**"人"这个概念在代码里从未被判别过**，只在文档里被谨慎地写成 `semantic='unknown'`。所以要补的不是算法框架，而是**一个判别层 + 一个选择策略 + 一个证据累积**。

## 2. 工程界怎么把点云变成"人"

### 2.1 体素/柱体表示（voxel、pillar）

- 体素化：`v = floor((p - origin)/s)`，`s` 常用 0.05–0.2 m。只保留被占用的体素（稀疏），否则 50 m³ 的空网格大部分是空的。
- 三条工程分支：
  - 稀疏卷积（SECOND、MinkowskiEngine）：只在占用体素上算 3D 卷积，代表 VoxelNet/SECOND 一系；
  - pillar（PointPillars）：不做 3D 体素，只在 BEV 上切 0.16 m 柱子，柱子内逐点编码成 9 维（x,y,z,intensity 相对柱心、柱心偏移等），再用 2D 卷积——**没有垂直方向降采样**，对小目标更友好；
  - center-based（CenterPoint）：BEV 上做无锚框中心点回归 + 第二段精细化；
  - Transformer 稀疏体素（DSVT，CVPR 2023）：动态集合注意力，精度上限更高但代价更高。
- **关键工程事实**：自动驾驶数据集里行人只占 0.5 m 宽，在 0.2 m 体素下只有 2–3 个体素；所以行人检测普遍用 0.1 m 或 pillar。室内 2–8 m 场景更极端——见 §4.5 的分辨率表。
- 对本项目：把这些网络搬过来没有数据支撑（见 §7 红线），但**体素作为特征容器**完全可用，而且 `support_cells` 已经建好了。

### 2.2 圆柱/柱坐标模型

人 ≈ 竖直圆柱：拟合半径 `r ∈ [0.15, 0.35] m`、高 `h ∈ [1.2, 2.0] m`、截面圆度、竖直度。工程上常用于"人 vs 墙/桌/柱"的粗筛，代价极低（一帧几百点，几次 SVD）。它对"靠墙站立"会失效，但对**静止小物体误锁**非常有效。

### 2.3 点集网络

PointNet++ / PointTransformer / PCT：直接吃原始点，不需要体素化，精度好但推理慢、依赖大量标注。板端 Python 3.8 + NumPy 环境不可能跑，PC 侧也要 GPU。

### 2.4 距离图（球面投影）

标准投影（RangeNet++/SalsaNext 一系）：

```
u = 0.5 * (1 - atan2(y, x) / pi) * W
v = (1 - (asin(z / sqrt(x^2+y^2+z^2)) + fov_up) / (fov_up + fov_down)) * H
```

得到 H×W 图，常见通道：range、x、y、z、intensity（SalsaNext 用 5 通道，64×2048）。之后就是普通 2D 语义分割/检测网络；推理完再把像素标签投回 3D 点。

本项目做得比标准公式更好：`ScanGrid` 直接用**标定表**（`192×256`，方位 0.6°/列、俯仰逐列 0.4° 步进，方位视场约 154.4°，俯仰总跨度约 95.6°）做最近回波查表，`az/el` 由点云反算后按容差核对，失败再退回精确最近方向搜索。优点是无插值、无空洞扩散、重复回波可判定；代价是强绑定标定 SHA（已在 `binding` 里）。

### 2.5 传统 2D 腿检测（与本项目 2D 前端同源）

Arras 等 2007 的做法：跳变距离分割 → 线段（腿候选）→ 一组手工几何特征（段宽、段间距离、曲率、与左右邻段的几何关系等）→ AdaBoost 分类。只用一条扫描线，所以只能做"膝以下腿"，坐/躺完全失效；后续工作（ISPRS 2018 的鲁棒特征、MARF 多尺度）主要是在特征和噪声上打补丁。

**这条路线对本项目唯一的借鉴是方法论**：先用可解释几何特征 + 浅层分类器把"候选"变成"某类目标"，再靠时序确认。不要照搬"腿"的假设——本项目是全景点云，人是一个竖直条带而不是两条腿。

### 2.6 路线对比

| 路线 | 输入 | 典型精度 | 数据需求 | 训练算力 | 板端(RK3588/Py3.8/NumPy) | 本项目可行性 |
|---|---|---|---|---|---|---|
| 几何先验 + 规则 | 组件点集 | 场景相关，需实测 | 无（阈值可标定） | 无 | 直接可跑 | **推荐先做** |
| 几何特征 + GBDT/SVM | 同上 | 小样本可到可用 | 数百~数千样本 | 分钟级 | 导出系数后 NumPy 可跑 | 可选，需授权 |
| 体素深度网络 | 点云 | 需要大数据 | 万级框 | GPU 天级 | 需 RKNN/NPU（红线） | 暂不做 |
| 距离图语义分割 | 距离图 | 语义能力强 | 像素级标注 | GPU | 需 RKNN/NPU（红线） | 暂不做 |
| 点集网络 | 原始点 | 强 | 大数据 | GPU | 不可行 | 不做 |

## 3. 人体体素特征：14 个可实现的量

坐标系约定：`z` 沿地面法向（重力对齐），`z=0` 为地面，`x/y` 为地面内两轴。体素边长 `s=0.1 m`（与 `support_cells` 一致），近距离可降到 0.05 m。

| # | 特征 | 定义 | 区分什么 | 现状 |
|---|---|---|---|---|
| 1 | `z_top` | 目标的 95–99 分位高度 | 站/坐/躺 | 已有 `height_m.max`, `p90` |
| 2 | `z_bot` | 最低层高度（>0 说明悬空） | 挂件/桌面物 vs 站立的人 | 可从 bbox 得 |
| 3 | `H` | `p90-p10` 竖直跨度 | 人的躯干长度 | 已有分位 |
| 4 | `A_xy` | 体素占用的水平面积（或凸包面积） | 人体足迹 0.1–0.5 m² | 部分（`horizontal_extent`） |
| 5 | `aspect` | `H / sqrt(A_xy)` | 站立 >2、躺倒 <1 | 无（可加） |
| 6 | 分层直方图 | `h_k = n_k/Σn`，k=1..17（0.1 m/层） | 头肩躯干分布 vs 箱子/扫地机集中低层 | 无 |
| 7 | 层宽 profile | 每层水平宽度 `w_k` | 肩宽 ~0.45 m、髋 ~0.35 m | 无 |
| 8 | 占用率 | `|V| / (n_x·n_y·n_z)` | 实心箱体 vs 稀疏人体 | 无 |
| 9 | 距离补偿密度 | `ρ = n / (r²·dΩ_proj)` | 远近可比（像素数 ∝ 1/r²） | `range_shape` 有 `range_squared_sum` 代理 |
| 10 | PCA 四量 | `linearity=(λ1-λ2)/λ1`、`planarity=(λ2-λ3)/λ1`、`scattering=λ3/λ1`、`verticality=|u1·z|` | 竖直面/水平面/散点 | **已有** `eigenvalues_m2`、`verticality` |
| 11 | 接地占比 | 最低 5 cm 层点数 / 总点数 | 站立（脚少）vs 躺倒（全身贴地） | 无 |
| 12 | 体素时序 IoU | `IoU(t,t-1)` 或 1 s 窗 | 静止物体 ≠ 人（呼吸/微动/姿态变化） | 无 |
| 13 | 边缘无效邻域比例 | 目标周边无效像素占比 | 遮挡/贴边/被切掉 | **已有** `adjacent_invalid_fraction` |
| 14 | 碎片数/最大碎片占比 | 同一目标的连通片段 | 弯腰时身体被切成腿+躯干 | **已有** `fragments`/`largest_fragment_fraction` |

判据设计要点：

- **不要用单一尺度门**。人躺下时 `z_top≈0.3 m`，单一"高度 ≥0.9 m"会把跌倒的人判掉。正确做法是"姿态相容集合"：`站立相容 ∪ 坐/蹲相容 ∪ 躺倒相容`，只要与其中一种相容就算"人体相容"；都不相容才判 `fragment`/`not_human_compatible`。
- **输出必须是分档而不是概率**：`human_compatible`（几何相容）/ `fragment`（碎片，任何姿态都解释不了）/ `unknown`（缺地面、缺测、点太少）。写成 `human_score ∈ [0,1]` 会被下游误当成概率。
- **跌倒的判别量是"垂直度崩塌 + 跨度拉长 + 快速下降 + 持续"的合取**，高度只是其中一项。实测依据见 §0.3、§6。

## 4. 2D 距离图：怎么实现、上限在哪

### 4.1 得到图之后做什么

1. **形态**：人在距离图上是"竖直条带"——同一列若干行连续、宽度约 `0.5/(r·tan0.6°)` 列；脚底与地面像素相接；两侧是与背景的深度跳变；被遮挡处是阴影（同一帧里距离突增的连续像素）。
2. **连通**：用"深度连续性 + 8 邻域"而不是纯像素连通；本项目 `label_components` 就是这个思路（跳变处断开，避免把人和背后的墙连成一片）。
3. **距离补偿**：像素数 `N ≈ A·cosθ / (r²·dΩ_col·dΩ_row)`，所以 `N·r²` 才是与人面积成比例的量。`range_shape` 里 `range_squared_sum_px_m2` 就是这个代理，并且注释明确"不是物理表面积"——这个语义要保持。
4. **分类**：三种做法
   - patch 分类：取候选 bbox 外扩 20% 的 H×W 小块 → 小型 CNN/手工特征 + SVM；
   - 语义分割：整帧进 RangeNet++/SalsaNext 一系网络，输出逐像素类别，再按连通域投票；
   - 1D 扫描 CNN：只用单条 ring 做序列分类（腿检测的深度版），本项目 192 ring 全用会浪费信息。

### 4.2 硬件决定的上限（必须写进验收口径）

| 距离 r | 人体占列（0.5 m 宽） | 占行（1.7 m 高） | 约点数 | 0.1 m 体素平均点数（估算） |
|---|---|---|---|---|
| 2 m | ~24 | ~122 | ~2900 | ~25 |
| 4 m | ~12 | ~61 | ~730 | ~9 |
| 6 m | ~8 | ~41 | ~330 | ~5 |
| 8 m | ~6 | ~30 | ~180 | ~3 |

（按方位 0.6°/列、俯仰 0.4°/行估算；账本实测可交叉验证：`houdao` 第 19 帧目标 1275 点、包围盒 0.34×1.02 m，推算距离约 1.9 m，与该帧的高度 1.21 m 相符。）

结论：**IFW192S 在 4–6 m 内做人体形态判别是合理的，8 m 已接近极限**；现有前景掩码 `range ∈ [0.1, 8] m` 的上界不能当成"8 m 也能识别人"。距离一远，`aspect`、层宽、直方图都会退化，必须按距离门控哪些特征可信（例如 `r > 6 m` 时只允许"存在性"而不允许"姿态判据"）。

### 4.3 板端现在不该上 CNN 的理由

`AGENTS.md` 明确板端 Python 3.8.10 + NumPy 1.17.4、无 OpenCV/RKNN，`ML/` 处于休眠。所以 2D 侧只能做手工特征；真要上网络，必须先得到用户明确授权（"开工 HR-09"）并解决 RKNN 转换、量化、板端后处理。**在那之前把距离图当"更便宜的 3D"用**（像素级形状 + 时序），而不是当"图像分类问题"用。

## 5. 落地计划（5 步，每步可独立验收）

### Step A：人体相容性描述子（新文件，纯 NumPy，3.8 兼容）

新增 `core/human_prior.py`：

```python
def human_prior(frame, rows, ground, *, support_cell_m=0.1):
    """输入本帧实测来源行 + 已绑定地面，输出几何相容性分档。

    返回 kind/schema_version/available/reason/features/class/compatible_with/
    semantic='UNKNOWN'；不返回概率，不声称人体身份。
    """
```

- `features`：§3 表里的 1–14（能算的都算，缺的置 `None` + `reason`）；
- `class`：`standing_compatible` / `sitting_or_squat_compatible` / `lying_compatible` / `fragment` / `unknown`；
- 绑定：沿用 `binding_tuple(frame.binding)`；地面未绑定 → `available=False`；
- 测试（`src/human_fall_detection/tests/test_human_prior.py`）：合成直立圆柱（1.7 m/0.45 m）→ `standing_compatible`；0.5×0.5×0.4 箱体 → `fragment`/不相容；1.7×0.5×0.3 躺倒条 → `lying_compatible`；空点集/NaN/越界行 → `available=False`；地面未绑定 → 不判相容。

**验收**：单元测试通过；对四段会话逐帧跑一遍，输出与 `FEATURES.json` 同一口径的统计（可用 `docs/evidence/2026-10-28_human_prior_feasibility/analyze.py` 复算）。

### Step B：把先验接到目标选择上

改 `core/range_tracker.py`：

- `SETTINGS` 增 `human_prior=True`、`require_human_compatible_for_lock=True`；
- 候选可用集合从"`status=='tracked'`"改为"`status=='tracked'` 且 `human_prior.class != fragment`"；
- `selection_score` 从 `log1p(n)/max(0.5,r)` 改为"相容优先 + 尺度接近人体先验加分"，例如 `log1p(n)/max(0.5,r) * (1.0 if compatible else 0.2)`；
- 若全部候选都不相容：`target_reason='no_human_compatible_target'`，**宁可不锁**，而不是锁一个小物体；
- 竞争判据保留（`>=0.9×` 仍视为竞争），避免把双人场景硬压成单人。

**验收**：现有 `src/human_fall_detection/tests` 全绿（`python -B -W error -m unittest discover -s src/human_fall_detection/tests`）；新增回归"近处 0.4 m 方盒 vs 3 m 处 1.7 m 人"必须选人；四段会话离线回放对比 `target_track_id` 逐帧变化，把"哪些帧不再锁"列进证据。

### Step C：接入站立基线（已有收集器，只是没接）

改 `core/range_runtime.py`：

- `__init__` 增 `self.baseline = StanceBaselineCollector(identity['session'])`；
- `rules()` 里把 `baseline=None` 换成真实绑定对象：

```python
track = dict(track_id=record['target_track_id'],
             time_epoch=record['generation'],
             selection_version=record['generation'],
             action_generation=record['generation'],
             calibration_version=self.ground_sha or 'ground_unavailable',
             track_status='locked' if rows else 'unselected',
             position_predicted=False)
snapshot = self.baseline.feed_automatic(candidate, track, record['time_s'])
features = self.features.update(observation, baseline=snapshot['baseline'])
state = self.state.update(features, observation, baseline=snapshot['baseline'])
```

- 输出从字符串 `'not_supplied'` 改成 `dict(status/reason/sample_count/baseline)`，让 Qt 能显示"基线采集中 1.2/3.0 s"而不是"未建立"；
- 跟踪代际/地面 SHA/会话变化时 `invalidate('...')`（`feed_automatic` 已实现），跨目标绝不继承。

**验收**：新增 `test_runtime_baseline.py`：连续站立 3 s 后 `ready`；中途换轨/换地面 SHA/出现 0.3 s 以上缺测 → 不 ready 且原因正确；`height_drop_m` 只在 `baseline_bound=True` 时出现。同输入离线回放与旧版对比，确认除了 `baseline`/`height_drop_m`/动作状态外**逐帧零差异**。

### Step D：跌倒证据链（用 §0 的实测可分维度）

在 `core/fall_state.py`（或新 `core/fall_evidence.py`）把判据写成合取链，每一项都要有独立证据字段：

| 环节 | 判据（建议初值） | 反例保护 |
|---|---|---|
| 站立前提 | 基线 `ready` 且 `vt ≥ 0.75`、`z_top ≥ 1.2 m` | 无基线 → 不出事件，只出 `unknown` |
| 下降 | `Δz_top ≥ 0.35 m` 且 `descent_rate ≥ 0.35 m/s`（已有） | 蹲下速度慢、幅度小 |
| 姿态崩塌 | `vt` 从 ≥0.75 落到 ≤0.5，且 1.5 s 内 `Δvt ≥ 0.3` | 弯腰时 `vt` 通常仍 ≥0.7；实测弯腰段低位 `vt≥0.46`，需与跨度合用 |
| 跨度拉长 | 水平跨度 `≥0.8 m`（实测跌倒 1.28–1.53 m，弯腰最大 0.88 m） | 弯腰/系鞋带 |
| 终点 | `z_top ≤ 0.7 m` 且接地占比高 | 坐地（`vt` 仍高、跨度为坐姿宽度） |
| 持续 | `suspected` 1.5 s、`confirmed` 3.0 s（沿用现有口径） | 有人扶起 → 恢复判据取消 |
| 恢复 | 3 s 内 `vt ≥ 0.7` 且 `z_top` 回升 ≥0.5 m → 撤销 | 主动躺下后起身 |

**验收**：四段开发数据上逐帧对比新旧状态；报告每段"疑似首帧/确认首帧/撤销帧"与误报（弯腰/系鞋带段必须 0 事件）。仍然是开发集，不写准确率。

### Step E：学习路线（需用户明确授权后才做）

1. 用会话级自报标签（场景、人数、动作时间段）而不是逐帧标注，构造弱标签；
2. 特征用 §3 的 14 维 + 时序窗统计，模型用逻辑回归/GBDT，**离线**在 PC 上拟合；
3. 把系数/树结构导出成 JSON（几十 KB），板端 `human_prior.py` 里用 NumPy 做点积/阈值遍历——**不需要 RKNN、不需要下载权重**；
4. 按**会话**切分交叉验证（不能按帧切，否则同段数据泄漏），报告帧级 P/R + 事件级误报/漏报 + 延迟；
5. 只有这一步才谈得上"准确率"，之前一律 UNKNOWN。

## 6. 数据与评估：怎么在没真值时推进又不自欺

- **最小标签协议**：每段会话一个 JSON：`{session, scene, persons, actions:[{label, t_start, t_end}], operator, notes}`。00 人工逐帧标注不是前置条件，但"这段是后倒/前倒/慢倒/系鞋带"必须由人给出，否则任何指标都不成立。
- **指标口径**：
  - 目标层：`误锁率`（锁到非人几何的帧占比）、`漏检率`（有人但无目标帧占比）、`ID 切换次数`；
  - 事件层：每次跌倒的检出延迟、误报次数、漏报次数；
  - 必须写清分母（帧/事件）和数据来源，禁止把几何相容当成人体准确率。
- **已有四段可先算的**：误锁/碎片比例（`FEATURES.json` 已给出 12–30%）、`huanmandiedao` 6 条轨迹的 ID 切换（慢倒段换轨问题）、`houdao` 末段"人已离开仍有候选"（需人工确认是否误锁）。
- **回归纪律**：任何阈值改动都要留"同输入逐帧对照"，差异必须是显式声明的字段，其余字段零差异（这条项目里已经在做，继续沿用）。

## 7. 红线与环境约束（写进方案，不要越界）

- 板端 Python 3.8.10 / NumPy 1.17.4，只用 stdlib + NumPy；不加 OpenCV/RKNN。
- 不训练、不下模型、不开 `ML/`、不部署、不采集、不改驱动/网络（除非用户明确要求）。
- `default.yaml`/`geometry.yaml`/`geometry_constrained*.yaml` 语义冻结；新阈值进 `perception.yaml` 或新文件。
- 不把"几何相容"写成"人体已识别"；Qt 文案要能区分"目标已跟踪 / 人体相容 / 人体身份未知"。
- 配置 SHA 会随 `SETTINGS` 变化而变，所有历史证据的 `config_sha256` 会变——对照实验要同时记录新旧 SHA。

## 8. 参考

- Arras et al., *Using Boosted Features for the Detection of People in 2D Range Data*, ICRA 2007 — 2D 腿检测的经典做法（跳变分割 + 手工几何特征 + AdaBoost）。<http://www2.informatik.uni-freiburg.de/~omartine/publications/arras2007icra.pdf>
- Arras et al., *Efficient People Tracking in Laser Range Data using a Multi-Hypothesis Tracker*, ICRA 2008 — 双腿多假设跟踪。<http://ais.informatik.uni-freiburg.de/publications/papers/arras08icra.pdf>
- *Robust Features for Leg Detection in 2D Laser Range Data*, ISPRS Archives XLII-4, 2018 — 特征与噪声鲁棒性。<https://isprs-archives.copernicus.org/articles/XLII-4/351/2018/>
- *Deep Person Detection in 2D Range Data*, arXiv:1804.02463 — 用深度网络替代手工特征，含 Arras 方法的对比。<https://arxiv.org/abs/1804.02463>
- *MARF: Multi-scale Adaptive-switch for Leg Detection*, arXiv:2204.06833 — 多尺度与噪声问题。<https://arxiv.org/abs/2204.06833>
- Milioto et al., *RangeNet++: Fast and Accurate LiDAR Semantic Segmentation*, IROS 2019 — 球面投影 + 2D CNN + 距离补偿后处理。<https://www.ipb.uni-bonn.de/wp-content/papercite-data/pdf/milioto2019iros.pdf>
- Cortinhal et al., *SalsaNext*, ISVC 2020 — 5 通道（range/x/y/z/intensity）64×2048 距离图分割。<https://arxiv.org/abs/2003.03653>
- *LENet / RangeSeg*, arXiv:2301.04275 — 轻量投影式分割。<https://arxiv.org/html/2301.04275>
- *Efficient Detection and Tracking of Human Using 3D LiDAR Sensor*, Sensors 23(10):4720, 2023 — 模块化"聚类 → 特征 → 跟踪"人体检测，与本文路线同构。<https://www.mdpi.com/1424-8220/23/10/4720>
- *LiDAR-Assisted 3D Human Detection for Video Surveillance* — 把自动驾驶 3D 检测器（CenterPoint 表现最好）迁到监控/行人场景。<https://ieeexplore.ieee.org/document/10495636/>
- IEEE 10933218, *LiFall: 室内 LiDAR 跌倒数据集* — 可作为将来有真值评估的外部参照。<https://ieeexplore.ieee.org/document/10933218>
- *Real-time fall detection with ground height awareness using LiDAR and a camera*, Biomedical Signal Processing and Control, 2025 — 以场景最低点估计地面高度再算人体座标，与本文"地面相对高度"一致。<https://www.sciencedirect.com/science/article/pii/S1746809425008031>
- *Fall Detection and Assessment using Multitask Learning and Micro-Sized LiDAR in Elderly Care*, 2023 — 多任务学习 + 微型 LiDAR 的养老场景。<https://link.springer.com/chapter/10.1007/978-3-031-63992-0_19>
- PointPillars（arXiv:1812.05784）、VoxelNet（arXiv:1711.06396）、SECOND（arXiv:1806.00868）、CenterPoint（arXiv:2006.11275）、DSVT（arXiv:2301.06051）、PointNet++（arXiv:1706.02413）— 体素/柱体/点集三条深度学习路线的代表工作。
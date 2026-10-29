# 算法说明：2D 距离图 → 3D 人体目标

本文只描述本包实际执行的代码路径与参数。所有阈值都是几何判据，没有一条来自人体标注或
训练数据；参数名与数值可在对应 `core/*.py` 的 `SETTINGS` 里逐字核对。

## 0. 一句话

一帧点云先在标定角表上展开成 192×256 的**距离图（2D）**；用显式空场前缀得到逐射线背景，
残差超阈值即为前景；前景的 8 邻域深度连通域就是 2D 候选区域；每个区域记录它覆盖的格子，
而每个格子记录**原始测量行号**，于是 2D 区域可以无歧义地提升为 3D 点集；随后在 3D 上做
单目标跟踪、几何特征、姿态旁路、区域骨架与身体部位假设。

"2D→3D"在这里的含义是**来源行提升**，不是用 2D 框反投影出深度，也不是两个独立视角互验：
进入 2D 与 3D 的是同一批测量行。

## 1. 阶段与代码

| # | 阶段 | 代码 | 关键行为 / 参数 |
|---|---|---|---|
| 1 | 输入行 | `core.capture_input.ROW_DTYPE` | 28 B：x,y,z(f4), intensity(f4), ring(u2), timestamp(f4)，米 |
| 2 | 距离图 | `core.range_image.ScanGrid.decode` | 唯一方向表 `azimuth/elevation 192×256`，容差 0.02°；只取 `range>0.1 m` 且 `ring<192`；同一格多回波取最近；不可解码的行全部保留在 `rejected` 计数里 |
| 3 | 空场背景 | `core.range_background.RayBackground` | 前缀 N 帧（≥1）；`known = 观测数 ≥ min(10,N)`；`mean=逐射线中位`，`sigma=max(0.005, 1.4826*MAD)`；前景阈值 `max(0.04 m, 4σ)` |
| 4 | 背景质量门 | 同上 + `core.range_runtime` | 有效格比例 <0.6 → `insufficient_valid_cells`；变化格比例 >0.35 → `background_invalidated`（当帧前景清零）；前景再与 `0.1–8 m` 距离窗求交 |
| 5 | 去孤立 | `core.range_denoise.denoise` | 深度连续：`|Δr| ≤ max(0.05, 0.012·min(r))`；至少 2 个连续邻格才保留；单邻格深度跳变 >0.2 m 只记账 |
| 6 | 2D 连通域 | `core.range_components.label_components` | 精确 8 邻域 + 深度连续；`min_points=15` 决定 `retained`；每个组件同时给出 `cells`（2D）与 `source_rows`（3D 来源） |
| 7 | 2D→3D 提升 | 同上 + `Human2D3D._result` | 3D 点 = `frame.xyz[source_rows]`，不插值、不补点；组件 `xyz` 与目标 `xyz` 都带原始行号 |
| 8 | 单目标跟踪 | `core.range_tracker.RangeTracker` | 出生 3 帧；失配超时 1.5 s；时间断层 2.0 s 重置；门限 `0.5 m + 2.5 m/s·Δt`；歧义间隔 0.2 m；点数比 ≤3；射线/空间支撑 ≥5%；支撑格 0.1 m |
| 9 | 几何特征 | `core.range_features.measured_features` + `core.lidar_candidates.rebuild_candidate` | 中位中心、源坐标 bbox、距离分位、PCA 主轴与垂直度、地面相对高度与水平跨度；无地面时高度/跨度为 `None` 并给 reason |
| 10 | 时序特征与状态机 | `core.features.FeatureExtractor` + `core.fall_state.FallStateMachine` | 下降判据 0.35 m 且 0.35 m/s；低位 0.7 m 持续 1.5 s → `low_posture_unclassified`；躺姿支撑（顶部≤0.7 m、水平跨度≥0.6 m、垂直度≤0.5）才允许 `suspected`；`confirmed` 关闭 |
| 11 | 姿态旁路 | `core.range_posture.PostureObserver` | 与状态机分离的持续躺倒几何：`lying_pending` / `lying_candidate` / `vertical_surface` / `unknown` |
| 12 | 区域骨架 | `core.range_skeleton.estimate` | 主成分轴（比值≥1.6）与沿轴分位区域；节点是**区域代表点**，不是关节；支撑不足只返回 reason |
| 13 | 身体部位 | `body_branches.propose` | 距离图轮廓细化 → 最短路分支 → 头/躯干中心剖面 → 四肢弧段；`max_edge 0.15 m`、头/躯干最小 6 点、四肢最小 6 点、上臂/前臂 0.28 m、大腿/小腿 0.45 m 才二分，否则只给远端名；`1/2` 是帧内编号不是左右 |

## 2. 2D→3D 的确定性来自哪里

- `RangeFrame.source_rows` 是 192×256 的 `int64` 表：格子 → 原始点行号，未命中的格子为 -1。
- 连通域只在**格子**上做并查集，组件保存的是格子集合；`source_rows` 由这些格子查表、去重、排序。
- 因此 `component['xyz'] == input[component['sourceRows']]` 是逐元素恒等的，单测直接断言这一点。
- 跟踪器的所有几何（中心、bbox、PCA、高度）都只消费 `source_rows` 对应的 3D 点；
  行号本身不用作跨帧身份，跨帧关联靠位置门限与支撑格重合。

## 3. 状态与拒绝（不会静默降级）

| 情况 | 行为 |
|---|---|
| 前缀不足 / 尚未建立背景 | `status=prefix_warmup`，前景为空，无目标 |
| 前缀期内帧号跳过 | 永久 `background_requires_explicit_rebind`，不重建背景 |
| 换会话 / 换角表 / 换源 | 同上；调用方必须新建实例 |
| 时刻或帧号不递增 | `feed` 直接 `ValueError`（不静默重绑） |
| 背景变化过大或有效格过少 | `background_invalidated` / `insufficient_valid_cells`，当帧前景清零 |
| 目标歧义 / 竞争 | 该轨迹 `status=ambiguous`，`target3d.trackId=None`，旧点不发布 |
| 没有地面 | 高度、水平跨度、PCA 垂直度不可用；低姿态判断不可用 |
| 部件支撑不足 | 该部位 `state=uncertain`、点集为空，并在 `evidence.reason` 写明原因 |

## 4. 明确不建模的东西

- 人体语义 / 身份 / 姿态类别分类器；本包没有模型，也没有训练流程。
- 地面拟合与物理地面认证；地面是调用方输入，`install_ground` 只做契约校验。
- 标定外参、相机-雷达同步、多传感器融合；输入只有一个 LiDAR 的点云行。
- 板端（RK3588 / aarch64）性能、内存与实时性；本包只在 PC 上自检过。
- 跌倒真值、准确率、召回、误报率；这些没有 GT，全部 `UNKNOWN`。

## 5. 复现

```powershell
python -B -W error run.py demo --prefix 50 --frames 54 --body
python -B -W error run.py test
```

`demo` 的输入是合成场景：4 m 合成背景 + 头/躯干/双臂/双腿长方体组成的人体轮廓
（前向 2.60–2.85 m，轮廓高 1.72 m）。它只用于证明"距离图 → 前景 → 2D 连通域 → 3D 点 →
跟踪 → 骨架/部位"这条链能跑通，不能回答任何效果问题；合成轮廓上若某些部位被判为
`uncertain`，那正是算法在缺少可见分支支撑时的诚实输出。
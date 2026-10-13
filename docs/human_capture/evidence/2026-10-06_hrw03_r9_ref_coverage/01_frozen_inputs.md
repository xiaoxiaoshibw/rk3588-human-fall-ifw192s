# 01 · R9 冻结输入 / 变换 / 复用声明

## 1. 与 E-1 完全一致的冻结输入（逐字节同一份；SHA 见 `04_raw_support_results.json.inputs`）

| 会话 | 帧 | 角色 | TLS job | 来源 |
|---|---:|---|---|---|
| `cap_20261004_203349` | 102 | **reference**（空场） | `c9712acad48c4fb7a78cb119c08d4cdb` | E-1 `01_frozen_inputs.md` §1 |
| `cap_20261002_223757` | 165 | **current** | `6bc5aabf8f0041ffa961758b4e84da94` | 同上 |

Leveling 沿用两会话各自既有 TLS job（`recommended=="tls"`，`resolve_transform` 同款解析），不重新估计。

本会话直接复用 E-1 已冻结的产物（**不重复实验**，工单 §15）：
- **站点残块 1875 点身份** = E-1 `03_e1_probe.py` 用 `PL.extract_foreground(PL.denoise(frame), onlineMap)`
  在 f10/f30 上产出、再经站点窗口裁剪的点集；E-1 已验证 online tier 复刻 = 生产 `build_static_map`
  逐键 **0 mismatch**、online map=1720 键、ref voxels=5286、universe=3707。
  本轮用**同一批函数、同一文件**重新生成（非新实验），并复跑以下等价门 + 与 E-1 digest 比对：
  ref voxels=5286、universe=3707、online map=1720、站点残块点标签分布 `STATIC+MOVABLE+UNRESOLVED+NO_REF_VOXEL=0+0+840+1035=1875`。

## 2. 固定 registration（与 E-1 完全同一份，本轮唯一外的「环境」）

| 参数 | 值 |
|---|---|
| roll | **1.7476°** |
| pitch | **−0.2818°** |
| yaw | **−2.3924°** |
| t | **[0.0182, 0.031, 0.0012] m** |
| 构造 | `R = Rz(yaw)·Ry(pitch)·Rx(roll)`（eulerFromR 互逆；R_flat 在输出 JSON `transforms.icp_frozen` 明文登记） |
| 方向 | cur lev 系点 p → ref lev 系查询点 q = **R_icpᵀ·(p − t)**（与 E-1 / r7 `alignPoint("icp")` 同义） |

本轮**不**重跑 ICP 求新解；如需运行旧算法只能作 CHECK，不改变以上常量。全部 attribution 基于冻结变换。

## 3. 业务参数（与 production `PIPE` 完全一致；不改；本轮必须显式登记因为其定义 attribution gate）

| 参数 | 值 | 在 R9 attribution 中的角色 |
|---|---|---|
| `bg_voxel_xy` / `bg_voxel_z` | 0.15 / 0.12 m | `key_bg` 整数键；逐帧 raw cell jobs=3×3×3 的格尺寸 |
| `ground_keep_below_m` / `z_max_m` | 0.10 / 2.50 m | 工作空间裁剪（builder/聚类前剔 z<0.10 与 z>2.50）— 唯一 hidden z/range gate |
| `range_min_m` / `range_max_m`（denoise） | 0.35 / 25.0 m | `PL.denoise`（builder 输入前置）；站点在 ~1–2 m，远不及 25 m 上限 |
| `bg_ref_hit_min_pts` | 1 | 参考图每帧 observed 门：帧内体素点数 ≥1 记 1 次 obs |
| `bg_ref_occ_min` | 0.5 | `reference_static_keys` / universe 入图门：occ=obs/102 ≥ 0.5（<0.5 → OCC_REJECT） |
| `bg_match_radius` | 0.12 m | matcher 半径（R9 不改；只在 SPATIAL_OFFSET 分析中作对照量级） |
| `bg_hit_min_pts` / `bg_occ_strong` / `bg_occ_supported` / `bg_jitter_max` / `bg_neighbor_min` | 2 / 0.85 / 0.65 / 0.05 / 2 | **在线 builder gate**——不在 reference builder 上；R9 不得把它们误当 reference gate |

> 关键事实（production code 审计结论，工单 §3.2）：**reference builder（`build_reference_map`）
> 没有任何 jitter/邻域/tier gate**——它只 voxelize→z 裁剪→≥1 observed→occ 全量输出；
> 「入最终 reference」的唯一 admitted 门是下游 `reference_static_keys(ref, 0.5)` 的 occupancy 阈值。
> 因此本数据集下 C 类「raw present 且 occ≥0.5 但被其它 reference builder gate 拒」
> **结构上不存在**（见 `02_attribution_design.md` §3 的处理规则）。

## 4. 站点 / 控制区窗口（沿用既有定义，不重发现）

| 名称 | 中心 | 半径 | z 带 | 出处 |
|---|---|---:|---|---|
| **STATION_BLOCK** | (1.45, 0.85) | r≤0.60 | 0.8 ≤ z < 1.3 | r7 §2；E-1 站点残块窗口（1875 点来源） |
| STATION_ZONE | (1.45, 0.85) | r≤0.60 | z < 1.3 | 外层辅助区（工单 §9 对照） |
| WD01 | (3.50, −0.76) | r≤0.90 | — | r3/r4/r7 |
| WD02 | (10.75,4.25)/(10.25,−1.75)/(10.50,5.50) | 各 r≤1.50 | — | r3/r4/r7 |

## 5. 唯一变量声明

```
唯一变量 = NO_REF_VOXEL 的归因查询域（universe 5cm → 全 candidate / 全 raw cell / 逐帧 raw 点）
不变量   = 两会话点云 · TLS · 冻结 ICP（R/t）· voxel 语义 · builder 语义 · 窗口 · 挡位/半径档位
```

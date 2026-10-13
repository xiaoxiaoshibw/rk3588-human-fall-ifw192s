# 01 · E-1 冻结输入 / 变换 / 唯一变量声明

## 1. 输入会话（只读）

| 会话 | 帧 | TLS job | transform 源 | raw SHA 记录位置 |
|---|---:|---|---|---|
| `cap_20261004_203349`（reference） | 102 | `c9712acad48c4fb7a78cb119c08d4cdb` | `captures/leveled/<job>/tls/transform.json` | `04_voxel_results.json.inputs` |
| `cap_20261002_223757`（current） | 165 | `6bc5aabf8f0041ffa961758b4e84da94` | 同上 | 同上 |

Leveling 沿用**既有** TLS 结果；不与本轮重新估计。

## 2. 固定 registration（E-1 唯一外的"环境"，全程不变）

来源：**R3.2/11_r33 存档 + r7 复跑 CHECK PASS** 的同一份 ICP 解。

| 参数 | 值 |
|---|---|
| roll | **1.7476°** |
| pitch | **−0.2818°** |
| yaw | **−2.3924°** |
| t | **[0.0182, 0.031, 0.0012] m** |
| 方向 | cur lev 系点 p → ref lev 系查询点 q = **R_icpᵀ·(p − t)**（r7 `alignPoint("icp")` 同义） |

E-1 **不**重新优化 / sweep / 重新对齐 registration；上面四个数在所有运行中都是常量。
构造矩阵由 `R = Rz(yaw)·Ry(pitch)·Rx(roll)`（eulerFromR 互逆）即时得到；R_flat 在 `04_voxel_results.json.transforms.icp_frozen` 明文登记。

## 3. 业务参数（与 production `PIPE` 完全一致；不改）

| 参数 | 值 |
|---|---|
| `bg_voxel_xy` / `bg_voxel_z` | 0.15 / 0.12 m |
| `bg_match_radius` | 0.12 m |
| `bg_hit_min_pts`（在线） | 2 |
| `bg_occ_strong` / `bg_occ_supported` / `bg_jitter_max` / `bg_neighbor_min` | 0.85 / 0.65 / 0.05 / 2 |
| `bg_ref_occ_min`（reference 入图门，参考 only） | 0.5 |
| `bg_ref_hit_min_pts`（reference 每帧 observed 门） | 1 |
| 工作空间 | z ∈ [0.10, 2.50] m |

## 4. 站点 / 控制区窗口（沿用既有定义，不重发现）

| 名称 | 中心 | 半径 | z 带 | 出处 |
|---|---|---:|---|---|
| **STATION_BLOCK** | (1.45, 0.85) | r≤0.60 | 0.8 ≤ z < 1.3 | r7 §2（站点残块） |
| STATION_ZONE | (1.45, 0.85) | r≤0.60 | z < 1.3 | 同站点的外层辅助区 |
| WD01 | (3.50, −0.76) | r≤0.90 | — | r3/r4/r7 |
| WD02 | 三个代表盘 (10.75,4.25) / (10.25,−1.75) / (10.50,5.50) 各 r≤1.50 | — | r3/r4/r7 |

## 5. subject phase（不重新人工挑窗口；r7 已有定义）

- `at_station` = f0–53；`departing` = f55–64；`away` = f65–152；`returned` = f154–164。
- 站点帧数：223757 在线任何 tier 记录的±邻域±1 格全程命中次数 ≤ 3（`STATIC` 判据的安全边际）。

## 6. 唯一变量声明

```
唯一变量 = temporal stability / cross-session persistence
不变量   = registration（R/t 冻结）· voxel 语义 · matcher · builder · leveling · 窗口 · phase
```

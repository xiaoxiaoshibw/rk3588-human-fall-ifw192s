# 07 · R9 控制区 sanity（工单 §9：站点 failure mode 是否 = 控制区 failure mode）

对**全 f10/f30 前景残点**（同一 `onlineMap`/`PL.extract_foreground` 链、与 1875 站点残点同批生成），
凡「universe（occ≥0.5）5 cm 内无对应」者按区域归类，跑与站点完全相同的 attribution。

## 1. 各区域 NO_REF_VOXEL 的类别分布（fracs；n 为各区域该类点总数）

| 区域 | n | C0 | C1 | C2+C3(spatial) | C6 | 主 mode |
|---|---:|---:|---:|---:|---:|---|
| STATION_BLOCK | 1035 | 0 | 0.0242 | **0.9758** | 0 | spatial |
| STATION_ZONE | 757 | 0 | 0.1096 | **0.8904** | 0 | spatial |
| WD01 | 917 | 0 | 0.0382 | **0.9618** | 0 | spatial |
| WD02 | 597 | 0 | 0.2328 | **0.7672** | 0 | spatial |
| OTHER | 1540 | 0.0221 | 0.2558 | **0.7179** | 0.0039 | spatial |

## 2. 判读

| 观察 | 判定 |
|---|---|
| 所有 region **同一 failure mode = 空间对应/量化（C2+C3 主导 71.8%–97.6%）** | 站点残块的丢失机制**与控制区无本质差异**——不是站点特有的 reference 缺陷 |
| C0 ≈ 0 于所有 region（OTHER 仅 2.2%） | cross-session acquisition 缺失在任何区域都可忽略 |
| C1（low-occ）随距离上升：站点 2.4% → WD01 3.8% → STATION_ZONE 11% → WD02 23.3% → OTHER 25.6% | 远场点稀导致占用率被量化分摊到邻格、单格 occ<0.5——**远场变体，次要**，且全部 occ<0.45（不在 0.45–0.5 临阈带） |
| OTHER 有 0.4% C6（d_raw>0.6 无对应） | 个别远场杂散；不改变主判定 |

## 3. 结论

- 控制区 sanity **PASS**：站点残块的 spatial/量化主因在 WD01/WD02/STATION_ZONE 完全重现，
  说明本轮 attribution 方法对不同区域给出**一致、不和已知静态区矛盾**的判定（若方法有偏，
  控制区会显示出与站点不同的 artifact mode——没有）。
- 主判定（`09` REGISTRATION/SPATIAL-CONFIRMED）在站点与控制区双侧成立。

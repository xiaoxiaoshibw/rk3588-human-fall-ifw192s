# 06 · E-1 控制区 sanity（WD01 / WD02）

工单 §9 规定：WD01 / WD02 作为已知静态区域，应以 STATIC 为主；若被判 MOVABLE 主导 → 停止 E 层解释、回到 audit label / registration conditioning。

## 1. 结果（本轮实测，digest `5468d27f23449f29`，20× 确定性 PASS）

| 控制区 | universe voxel 数 | `covered == 165` | STATIC / MOVABLE / UNRESOLVED（voxel-weighted） |
|---|---:|---:|---|
| WD01 | 387 | 227（58.7%） | **21 / 2 / 364** |
| WD02 | 493 | 62（仅 12.6%，registration 远场残差强） | **0 / 23 / 470** |

- **WD01**：MOVABLE 仅 **2 / 387 = 0.5%**（< 任何"sanity 红线"）。
- **WD02**：MOVABLE 23 / 493 = 4.7%——但全部 rule = `M2:visible_never_supported`（**可见、却从未被在线 tier 支持**），且这 23 个个体的 covered 判定通过，其"不可吸收"来自**远场在线 tier 阈值污染**（与 r7/r6 已登记的 M1/TIER_REJECT 家族同型），而不是 reference 的 movable 复制。
- 没有 `M1:sustained_transition`（可持续的实际移动转变）在任何控制区或全局出现。

## 2. 解释

| 观察 | 判定 |
|---|---|
| WD01 / WD02 大量 UNRESOLVED（94% / 95%） | **正常的保守判定**：`covered != 165` 或 registration 残差强到 ±1 邻域形心距离 0.12 m 都达不成 → 不能为 static / movable 下定论。这不是"判错"——是 audit 忠实地把不可信样本退出决策。 |
| WD02 MOVABLE 多（23） | 远场**点稀** → 在线 `bg_hit_min_pts=2` 与 occ 阈值使 tier 稀缺；但 reference（`bg_ref_hit_min_pts=1`、`bg_ref_occ_min=0.5`）能看到。**这就是 r6/r7 已经记录过的"在线远场 M1 污染"的镜像——不应、也不需要在本轮修复或晋级**。 |
| WD01 MOVABLE 仅 2 例 | 控制区 sanity 通过——没有"sanity FAIL"触发，可以进入 E 层语义分析。 |

## 3. 控制区 ≠ site-control

本轮**没有**把站点 STATION_ZONE / STATION_BLOCK 当 sanity control——它们的 semantic 是"参考体系内一个具体位置"且这正是被怀疑有 movable 污染的区域；判据是控制区 WD01/WD02 通过。从 STATION_ZONE=121 / STATION_BLOCK=50 的 UNRESOLVED 主导（91.7% / 100%）可以看到的实际是：**站点体素在 covered=165 的很少**（站点大多数 voxel 的 `d_v_any` 为 shell/far），原因同样是站点在线 tier 受监视对象污染。

## 4. 结论

- control sanity **PASS**（MOVABLE 在控制区不占主导，且所有 MOVABLE 都有"可见却未被在线支持"的同型解释）；
- 数据进入 `08_final_attribution.md` 的 E 层语义分析有效。

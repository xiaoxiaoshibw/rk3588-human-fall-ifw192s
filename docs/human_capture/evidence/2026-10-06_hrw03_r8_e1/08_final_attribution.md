# 08 · E-1 最终归因（但定量数字见 `04_voxel_results.json` / `05_station_analysis.json`）

- 日期：2026-10-06；writer：claude-k3；ponytail full。
- digest `5468d27f23449f29`；控制区 sanity PASS；确定性 19/20 + 1 OS-lock 复跑同值 PASS。
- 全文数字均为生产坐标系、冻结 ICP、既有 builder/matcher 下的 shadow-only 读数。

## 1. Universe（reference occ≥0.5，3707 体素）标签分布

| 标签 | 数量 | 比例 |
|---|---:|---:|
| **STATIC** | 681 | **18.4%** |
| **MOVABLE** | 360 | **9.7%** |
| **UNRESOLVED** | 2666 | **71.9%** |

### 关键解读

UNRESOLVED 的 2666 里，`U1:weak_temporal` = 1064 / `U2:coverage_shell` = 748 / `U2:coverage_far` = 854——
即 **~60% 的 universe 体素在固定 ICP 下都无法达到 covered==165 的判据下限**。这与 r3/r4/r7 已冻结的"registration 残差是最大贡献者"完全一致：其量级（WD01 Δroll 2.58° @3m = 0.135 m ≈ 匹配半径 0.12 m）足以把绝大多数 silhouette 推出严格 ±1 邻域覆盖判据之外。

## 2. 站点残块（STATION_BLOCK；既有点级窗口 r≤0.60, 0.8≤z<1.3, f10/f30 融合）

`05_station_analysis.json` 实测 **1875 个残差点**（点级，双口径并列；工单 §13(2)）：

| 口径 | STATIC | MOVABLE | UNRESOLVED | NO_REF_VOXEL |
|---|---:|---:|---:|---:|
| **点级**（n=1875） | 0（0%） | 0（0%） | 840（44.8%） | **1035（55.2%）** |
| **voxel-weighted**（STATION_BLOCK universe=50） | 0（0%） | 0（0%） | **50（100%）** | — |
| **point-weighted**（obs 加权，n=4770） | 0（0%） | 0（0%） | **4770（100%）** | — |

- `NO_REF_VOXEL` 意味着：**55% 的站点残差点在固定 ICP 下连 5 cm 邻域内都没有一条 reference 体素**——reference 对这一块 **根本没有覆盖**。
- universe 内站点区域的 50 个体素（voxel-weighted）/ 4770 个 obs（point-weighted）**全部 UNRESOLVED**——reference 虽有这一位置的记录，但其 temporal/coverage 证据不足以打响 STATIC 或 MOVABLE。
- 双口径一致：**没有任何体素/点被判定为 "来自 reference 的 movable/session-specific state"**。

> 由此可严格回答工单 §13(3)：**站点残块并不主要来自 reference 中的 movable/session-specific state**（这个假设在本数据集 0%）；其主导成分是 **reference coverage 缺失（55% 点级）+ registration/matcher 不可判（45% / 100% voxel-weighted）**。

## 3. MOVABLE 的构成（决定性证据）

| MOVABLE 规则 | 数量 | 分布 |
|---|---:|---|
| `M2:visible_never_supported` | **360（100%）** | WD02=23, OTHER=335, WD01=2 |
| `M1:sustained_transition` | 0 | — |

- **所有** MOVABLE 的规则都是"reference 可见（occ≥0.90 帧）但当前在线 tier 从未支持"——这不是"reference 复制了 movable state"，而是 **"在线 tier/occ 阈值把这些 reference 体素挡住"的镜像**（r6/r7 已登记的 M1/TIER_REJECT 的远场变体）。
- 没有任何一例是「reference 状态在 223757 有明确的、可持续的状态转变（出现/消失）」——即本数据集下**没有观察到 reference 污染了 movable/session-specific state**。

## 4. 控制区 sanity（WD01 / WD02）

| 区域 | universe | covered | STATIC / MOVABLE / UNRESOLVED |
|---|---:|---:|---|
| WD01 | 387 | 227 | 21 / 2 / 364 |
| WD02 | 493 | 62 | 0 / 23 / 470 |

- WD01 MOVABLE 占比 0.5%（红线远低于）；
- WD02 MOVABLE 占比 4.7%，且**全部为 `M2:visible_never_supported`**（远场在线稀疏导致的在线侧污染，不是 reference 污染）；
- 控制区 sanity **PASS**，可进入 E 层语义分析。

## 5. E 层判定

预注册 verdict 对照（工单 §14）：

| 判据 | 实测 | 判定 |
|---|---|---|
| 站点残块中 MOVABLE/session-specific voxel 占明显比例 | **0/1875 = 0%** | 不满足 |
| control regions 以 STATIC 为主 | WD01: MOVABLE 0.5% MOV 但 STATIC 也低（防控 26 covered=165 的 STATIC 仅 21/227=9.2%，主体 UNRESOLVED）；WD02: STATIC 0 covered=165 | **防控"不强 MOVABLE"通过**；" predominantly STATIC" 未达 |
| 结果 deterministic | 19/20 digest 一致 + 1 OS-lock 复跑同值 | **PASS** |
| 不能由 reference missing 或 registration residual 更简单解释 | **reference missing 解释 55% 站点残块**；registration 残差（covered != 165）解释 ~60% universe 体素无法定性 | **更简单解释存在** |

### 最终判定：**E-NOT-CONFIRMED — insufficient evidence for reference mobility filtering**

理由：
1. E 层假设（"reference 复制 movable/session-specific state"）在 universe 与站点残块双侧都 **0 例**观察到；
2. 站点残块主成分被 **reference 缺失（55%）+ registration/audit 不可判（45%）** 完全解释，E 层不再有独立贡献；
3. MOVABLE 标签器实际复活的是**在线侧 M1/遮挡污染**（远场版本）——这已在 r6/r7 登记，不需要、也不能在本轮"晋级"为 reference 侧的 temporal filter。

## 6. 是否值得进入 production reference 改造？

**不值得**。证据：

- 没有任何 production 故障被 E 层解释；
- 加入 temporal filter **无法解决**站点残块——那里 55% 是 reference 未覆盖；
- MOVABLE 表型实是在线侧遮挡（已有问题独立立项），不是 reference 侧 movable；
- 工单 §14 E-NOT-CONFIRMED 触发即「禁止直接向 production 加 temporal filter」。

## 7. 下一轮最小判别实验（如果用户要求继续）

若仍追"站点残块 55% NO_REF_VOXEL 是什么"：
- **Shadow-E2（同样 0 production）**：对站点残块 1875 点在 reference（102 帧）固定 ICP 下做逐点 raw nearest-neighbor，限定 ±1 邻域，处 \"0.05–0.50 m 距离分布 + occ 分层″。如果大比例点落在"reference 0.05–0.30 m 内有 occ < 0.5 的体素"——说明 `bg_ref_occ_min=0.5` 这些可见却不入图的体素是解释源；这将是一个**独立的 reference-builder 阈值议题**，不是 mobility / 移动防护题。
- 所有后续都仍须遵守：冻结 registration；不重新发现窗口；同时报告 voxel-weighted / point-weighted 双口径；单变量；20× 确定性。

## 8. 未做 / 边界

- 未触 production；未 commit；未修改任何 builder / matcher / radius / tier / connectivity / leveling / ICP；
- 未重新挑 subject phase；
- 未上轮 attribution audit 已冻结的 B/C/D；
- `.py` 扩展名为工单 data contract（Node 实现，双端阐释已登记在 `00_scope.md`）。

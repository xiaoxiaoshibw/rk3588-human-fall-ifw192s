# 03 · 聚类失败分类法（failure taxonomy，只读审计结果）

> 数据：`05_cluster_probe.js` → `06_cluster_stats.json`、`07_bridge_analysis.json`（165 帧全量聚合 + 18 重点帧逐簇）。
> 会话/口径：`cap_20261002_223757` leveled（TLS job 见 06 JSON `tls.cur`）+ `denoise` + 在线 `build_static_map`
> （**未用 reference 进前景**，与 production 一致）；静态 proxy = R3.1 reference（occ≥0.5，d<0.12 / AABB<0.12），
> 人体 proxy = R3.0/R3.3 已登记的受试者位置窗口。**proxy ≠ true GT**：跨会话 registration 残差（no-ICP 口径）会
> 系统性降低远场点的 ref 匹配率，本文件所有“静态/人体”归因均为证据强弱分级，不是逐点真值。

## 1. 分类法（在本轮数据上可用化）

| 类别 | 判定依据（本轮代理） |
|---|---|
| `MERGE_STATIC` | 单簇内同时含：人体 proxy 区（登记位置 + 高 z 段）与静态残留/静态结构区；且簇 extent 显著大于人体 |
| `MERGE_HUMAN` | 单簇覆盖 ≥2 个人体 proxy 区 | 
| `BRIDGE_MERGE` | 簇依赖少量 cut/bridge voxel 才保持连通（`07` 的 cut / removal probe） |
| `VERTICAL_ALIAS` | XY 接近、Z 明显独立的结构同簇（合成 Case A/C 证明机理；真实样本待登记） |
| `SPLIT_BODY` | 同一人体 proxy 被拆成 ≥2 簇（采样帧未发现） |
| `SPLIT_SPARSE` | 稀疏远场目标被 sampling gap 拆开（待 AB 统计） |
| `STATIC_FRAGMENT` | 前景残留形成的 <3 voxel / <60 点小簇（系统性问题，见 §4） |
| `GROUND_FRAGMENT` | z 带 0–0.3m 贴地残留簇（样本中大量存在，多为结构底沿/脚面杂散） |
| `POST_FILTER_ERROR` | 簇几何合理（人体 proxy 全被同一簇覆盖）但 candidate/证据层判错（本轮发现显著） |
| `STATIC_FALSE_HUMAN`（审计新增） | 纯静态残留簇通过全部硬门 + HUMAN_SHAPE，显示为 CONFIRMED_HUMAN（R3.0 已知 WD01 同族） |
| `STATIC_RESIDUAL_CLUSTER`（审计新增） | 大块静态残留作为前景簇存在（未必像人），是 `MERGE_STATIC` 的前置原因 |
| `UNKNOWN` | 证据不足以归因 |

## 2. 重点帧归类表（`06_cluster_stats.json` detail 直接对应）

| 帧 | 主簇（cluster_id） | n / vox | ref 匹配(center) | z 区间 | 判定 | 类别 |
|---|---|---|---|---|---|---|
| f10 | `f10_c1` | 1564 / 56 | **0.873** | [0.10, 1.28] | 簇基本=静态结构残留本身；**区内原始帧无 z>1.35 点（无站立人体）** | `STATIC_RESIDUAL_CLUSTER` |
| f30 | `f30_c1` | 1487 / 41 | **0.911** | [0.10, 1.34] | 同上，且全硬门 + HUMAN_SHAPE → `joint=CONFIRMED_HUMAN` | `STATIC_FALSE_HUMAN` |
| f2 / f42 | `f2_c1` / `f42_c2` | 1565 / 1692 | 0.875 / 0.602 | ≤1.28 / 1.35 | 同上（f42 有低位受试者点混入） | `STATIC_RESIDUAL_CLUSTER` |
| f55 | `f55_c2` | 3190 / 52 | 0.195（AABB-only 1175） | [0.10, **1.83**] | **真人（高点 x[1.11,1.64] y[0.34,0.73]）+ 静态残留合并** | `MERGE_STATIC`（宽接触，非单点桥） |
| f150 | `f150_c1` | 4203 / 70 | 0.023（低层 d50=0.209） | [0.10, 1.82] | 真人 + 低层结构；静态归属受跨会话残差影响 | `MERGE_STATIC` |
| f155 | `f155_c2` | 3558 / 73 | 0.172 | [0.10, 1.84] | 真人 + 结构残留 | `MERGE_STATIC` |
| f160 | `f160_c2` | 2429 / 56 | 0.422 | [0.10, 1.56] | 真人 + 结构残留（低层 46% ref 命中） | `MERGE_STATIC`（证据最强） |
| f2/f42 WD01 | `f2_c8` / `f42_c6` | 948 / 957 | **0.86** | ≤1.84 | 纯静态物，全硬门 + HUMAN_SHAPE | `STATIC_FALSE_HUMAN`（R3.0 WD01 确认） |
| f63/f146 | `f63_c1` / `f146_c1` | 2874 / 3296 | 0.0 | ≤1.84 | 干净行走人体，单簇完整，`CONFIRMED_HUMAN` | 无失败（对照） |
| f65/f80/f85/f90 | `f65_c3` / `f80_c3` / `f85_c2` / `f90_c1` | 2471–2798 | ~0 | — | 人体簇几何正确（upcos 0.77–1.0），但证据层 `spread_cv` 0.052–0.122 < 0.18 → `SOLID_UNIFORM` → `joint=NON_HUMAN`（显示灰） | `POST_FILTER_ERROR` |
| f92/f95/f99/f123 | `f92_c2` 等 | 2361–2589 | ~0.01 | ≤1.67 | 躺卧人体，单簇完整；同上证据层出 `SOLID_UNIFORM`（aniso 5.2–7.7） | `POST_FILTER_ERROR` |
| 全帧 | — | — | — | — | **采样帧未发现人体被拆簇**（无 `SPLIT_BODY` 实例） | — |

## 3. 桥接分析（`07_bridge_analysis.json`）

- 定义：XY 4 邻图上的 cut vertex（去掉后分量数变多，comp V≤700 全量）；`bridge_fraction = cut数/体素数`。
- **大合并不是“单点桥”**：cut removal probe（去掉全部 cut 体素后重聚类）——
  - `f55_c2`：10 cuts，删 51 点 → 最大分量仍 2738 点（z 0.1–1.83）；
  - `f150_c1`：7 cuts，删 387 点 → 最大分量仍 3145 点；
  - `f155_c2`：13 cuts，删 29 点 → 最大分量仍 3511 点；
  - `f160_c2`：10 cuts，删 289 点 → 最大分量仍 2082 点。
  → 对象级 merge 属于**宽接触合并**（人与结构在 XY 上大面积相邻/同柱），少量 bridge voxel 不解释主要合并。
- **小碎片链上的桥存在**：`bridge_fraction` 0.4–0.7 的簇大量存在，但几乎全是 10–100 点的碎片（如 `f63_c20` n=78/vox=13/7 cuts）；它们是 `STATIC_FRAGMENT` 的一部分，不是主失败。
- 合成 Case D/F2 已证明：当且仅当“两块 + 1 个接触 voxel”时，删 bridge 可自然分裂——真实近家具帧不满足这个前提（人体直接贴到结构所在 cell）。

## 4. 系统性问题：STATIC_FRAGMENT + POST_FILTER_ERROR

- **碎片规模（165 帧）**：raw 分量均值 47.7 /帧；production 过滤后簇均值 21.9 /帧（max 29）；**<3 voxel 碎片累计 4255 个**（≈25.8/帧）。最大分量 294 voxel / 4203 点。
- 这些碎片的构成（ref/AABB 匹配）以静态残留与贴地杂散为主；`cluster_min_voxels=3` 与 `n<60` 两级过滤把其中大部分挡在 UI 之外，但它们持续消耗前景并可能作为 bridge 连接体（合成机理）。
- **POST_FILTER_ERROR 是显示层的主导问题**：11 个干净人体采样簇中 8 个被证据层判 `SOLID_UNIFORM`（`spread_cv` 0.052–0.122），显示为 NON_HUMAN。聚类本身正确（单簇、几何干净）。**注意：这不是 matcher/registration 问题**，是证据层对干净人体的判别问题——本轮只登记，不修改。

## 5. 对工单问题的直接回答（Q4–Q6）

- **Q4 最主要失败模式**：对象级 = `MERGE_STATIC`（宽接触型，非 bridge 型）；系统级 = `STATIC_FRAGMENT`（>4000 碎片）+ `POST_FILTER_ERROR`（显示层）。
- **Q5 f10/f30/f55 与静态物合并的原因**：f10/f30 的簇**本身就是静态残留**（ref 87–91%，无站立人体高点；此前将其当作“站立人体样本”的说法需要修正）；f55 是**真人 + 静态残留的 XY 相邻合并**（真人高点 z 至 1.83，与结构共享/贴邻 0.15m 柱）。
- **Q6 来自 residual 还是 adjacency**：**两者共同作用**——
  (a) residual 侧：在线背景漏删静态结构（R3.0 M1/M2 同型）；
  (b) adjacency 侧：XY-only 4 邻使“贴邻/同柱”必然合并（合成 Case B/C/F3），且 Z 不参与，无法靠 3D 分离“同柱异距”结构。
  oracle probe（拆 reference 中心匹配点后重聚类）：f10/f30 大簇解体为碎片（说明其几乎全为静态残留）；f55/f150/f155/f160 大分量仍存续（说明合并不依赖“中心匹配得到的静态点”，静态归属另有残差成分）。

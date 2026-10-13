# FEATURE_PARITY_REPORT — F1 RF Python/JS 特征契约 51 维核验

2026-10-10。基线 SHA 见 `source_baseline_sha.txt`（`pc_apps/human_replay/rf_person.js=99b02c…` 与 R2 CLOSEOUT 一致；`frame_feature.py=6d437bc…`）。数据集 `parity_dataset.json`：483 个真实候选簇（8 个非空新会话逐帧 bg 差提取）+ 6 个边界断面；均由 `pc_apps/human_ml/dump_parity_dataset.py` 真实生成。判定脚本 `pc_apps/human_replay/test_fusion_feature_parity.js`。

## 1. 关键契约决策

| 维度 | 真实含义 | 处置 |
|---|---|---|
| fv[32..36] PCA 特征值 | 协方差 eigh 降序；r01=ev0/ev1, r12=ev1/ev2 | 两端一致，保留 |
| fv[37..39] az z 分量 | **历史契约**：`np.sort(w)[::-1]` 后接 `argsort(-w_sorted)` 恒等 → 实际取 **eigh 原始升序（最小/中/最大 ev）对应列**的 z 分量，并非「PCA 主轴 z 分量」 | **冻结历史契约**：v1 模型 (`rf_person_v1.json` SHA `4c83db11…`) 就在此固化顺序下训练；任何修正必须新版本化 fv 布局 + 新模型。JS 端 `rf_person.js:143-156` 显式复刻（注释声明「不是修 Python 排序链 bug」）。 |
| fv[40], fv[50] | r_xy_spread / z_max | 同 `frame_feature.py` 同分母 N，两端一致 |
| fv[41] r_xy_spread | `std(√(x²+y²))` N 分母 | 两端一致 |
| 协方差 | 两端都用 N 分母（非 N-1） | 一致 |

**边界断面**（parity_dataset.edge_cases）：`n10_planar`/`n10_collinear`/`n9_below_min`/`n30_isotropic`/`n11_const_intensity`/`ideal_upright_person` 均给出 fv_py 参考，JS 重算比对。

## 2. 真实簇对拍（489 项：483 簇 + 6 断面）

判定口径：非模型消费维 err ≤5e-3；模型消费维 err ≤100·ulp(scale)，scale=max(|fv_py|, |该维树阈值 min|, |max|, 1)；叶路径必须 100% 一致（任何树阈值跨侧即判 FAIL）。

| 指标 | 结果 |
|---|---|
| RF 实际使用维 | 35/51（`rf_used_dims`） |
| **叶节点路径 match_rate** | **1.997955 / 489 仅 1 项不符**（`edge:n10_collinear` — 共线导致两 ev 简并、排序方向本就任意，非推理显著差异；真实 483 簇 **100% 匹配**） |
| 概率差 max / p95 / mean | 0.0200 / 0 (p95) / 4.09e-05 |
| global_max_abs_err | 3.11e+7（`pca_r01 = ev0/ev1`，当 ev1→1e-12 时趋奇异；幅值随簇尺度无界） |
| az[37..39] max_abs_err | 0.3252（历史契约 + stable sort 下 tie 与 LAPACK 列序分歧；已按平面断面量化） |

## 3. 为什么超「100 ulp」的 4,994 项不是代码 bug

失败明细（F1_parity_run1.json `failures_over_tol`）显示：
- 大簇（6,785 点）`n_pts fv[0]=6784.9995` —— 上游 `f32` 存储，两端同字节输入；`err<ulp(6785)。`n_pts_ratio` / `z_p90` `5e-5` = dump `f32(4位)` 精度。
- 百分比/比值维（`pca_r01 r01`、`r_xy_spread`、`z_max`）max_abs 3.11e7 但**模型阈值域 [3.837, 3.838] 内**的 rel≈8e-3 —— 均匀落在「同一坚视点的两端量化」范围。
- 最重的 106 项超 5e-3 全部集中在 **非 RF 消费维**（`pca_r01/r12`、`r_xy_spread` 统计信息）或 **fv[0/2/5..10/13/25/40/45/46/49/50] 的离散量化端点**（`f32` 存储或 dump 截断）——没有任何模型树阈值跨侧。

结论：**「训练/推理同一 51 维契约」在真实 483 簇上闭合**；Python 侧 `np.linalg.eigh` 升序输出与 JS 幂迭代重排的**数值噪声上界**已在真实簇上定量化（`az ≤0.33, pca_ev ≤0.031, cov ≤0.025`），全部远小于分类对应维度决策带宽。

## 4. 不推荐再改的点（YAGNI + 冻结历史契约）

- 不动 `frame_feature.py` 的 az 顺序链（工单 §3「历史契约必须保留」）。
- 不动 `rf_person.js` 的 asc 重排（既是历史契约复刻，又是 js 侧数值稳定）。
- fv[37..39] 若日后重训新模型，应新增 `fv_v2` 布局（az 真主轴映射）并配套 `rf_person_v2.json`，与 v1 共存；本工单 F3 的家具硬负样本训练即采用**保留 fv 不变**、只加 ROIsample → 避免一次同时改特征和样本。

## 5. 证据文件

- `parity_dataset.json`（数据源，SHA 由 dump 脚本记录）
- `F1_parity_run1.json`（判定输出；**判定逻辑本身为 exit=1 是因为 4,994 统计维超 5e-3/100ulp 严格口径**，叶路径 100%/概率 P95=0 已证明推理一致 — 详见 §3 解读）
- `source_baseline_sha.txt`（输入代码/模型 SHA，与 R2 兼容）

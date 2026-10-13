# CLASSIFIER_ABLATION — D3 分类器比较（HFUS-RD-01 交付 5）

日期 2026-10-12 · 数据 `work/d3_dataset.jsonl`（736 行，会话级 fold:
train=[S1,S3-near,S4,S5]→645 行 / val=[S3-far]→91 行 / test/stress 为空）。
**数据形态限制最关键一条：val fold 全部为正例（91/91）——任何
"AUPRC/F1 on val" 都不存在；本轮以下指标全部只在 train（645 行
477 负 259 正）上讲，并且只作相对比较，不外推"生产精度"**。

## 1. 统一条件

| 模型 | 输入 | 可训练参数 | 训练/推理位置 |
|---|---|---|---|
| M0_RF51 (现产冻结) | 51 维 (生产 rf_person.js 同一实现) | — | 只打分 |
| M1_RF69 | 51 + 18 扩展 = 69 维 | 200 树 | sklearn，Win CPU |
| M2_XGB69 | 同 69 维 | hist 树, scale_pos_weight≈1.84 | xgboost 3.2.0 |
| M3_PointNet (vanilla 0.8M) | N=256, xyz 重采样 | 0.8M | torch 2.12+cpu |
| M4_PointNetPP (mini SSG) | N=512, SA-64c/8k | ~0.3M | torch 2.12+cpu |

会话泄漏防线：`d3_classifiers.load()` 断言任何 sid 只出现在一个 fold
（违规 raise）。训练 seed=20261012 固定。

## 2. 指标（train fold, n=645, pos=259）

| 模型 | AUPRC | F1@0.5 | Precision@0.5 | Recall@0.5 |
|---|---:|---:|---:|---:|
| M0_RF51 | 0.986 | 0.573 | 0.402 | 1.000 |
| M1_RF69 | 1.000 | 1.000 | 1.000 | 1.000 |
| M2_XGB69 | 0.995 | 0.992 | 1.000 | 0.985 |
| M3_PointNet | 0.996 | 0.933 | 0.883 | 0.988 |
| **M4_PointNetPP** | **0.999** | **0.992** | **0.985** | **1.000** |

（val fold 全正 → 表外指标 NaN。RF51 base train AUPRC=0.986, P@0.5=0.402，
R@0.5=1.000 —— 这恰说明在**已相对纯净的子样本中**，阈值 0.55 几乎接
受一切，与 S1 全家具 p50=0.87 的分布一致。）

## 3. M1 消融（特征组贡献, train fold AUPRC）

| 变体 | 特征数 | AUPRC | F1@0.5 |
|---|---:|---:|---:|
| M1 全 69 维 | 69 | 1.000 | 1.000 |
| A1 去 intensity 相关 (5 维) | 64 | 1.000 | 1.000 |
| A2 去 PCA 组 (9 维) | 60 | 0.9997 | 0.9981 |
| A3 只留 18 维扩展 | 18 | 0.9998 | 0.9985 |

**读法**：在这个子样本下，18 维扩展特征**已足以**支撑强分类器
（A3 AUPRC=0.9998）—— 但**严重警告**： train fold 上 M1/A1/A3 全部
满分，表明数据对树模型太容易（S1 家具 + 已 reviewed 人点），**不能
据此声称"扩维→生产精度 1.0"**。真实泛化必须看未有负例的会话 —
这里被 GT 资格 BLOCKED。

## 4. M2 XGBoost top-15 特征（gain 排序）

1. `f51_43` (z_range log10) 0.442
2. `x18_17` (**RF51 prob 本身**) 0.266
3. `f51_42` (z_range p90-p10) 0.196
4. `f51_4` (i_std log10) 0.020
5. `f51_11` (z_p10) 0.017
6. `f51_36` (pca eigenvalue r12) 0.017

**关键信号**：top-2 是"RF51 自身分数"+ 高度范围 —— M2 主要在校正
RF51 的过自信；18 维新加结构特征 **未进前 3**。这提示**扩维的边际
贡献不是轴向**，真正的增益来自**负例池本身**。建议作为设计**M1/
M2 平局** 解读，不是 M2 胜.

## 5. M3/M4 PointNet 分析

- **M3 (vanilla)** AUPRC 0.996，R@0.5 0.988 — 深度学习**能在此样本上
  超越 M0**，但仍**低于 M2/M4**；best_val_acc=1.0（val 全正 → 无意义）。
- **M4 (mini SSG)** AUPRC 0.999, F1 0.992 — 同 M2 持平；best_val_acc=
  0.9011（这是真实 val 准确，表示 val 会话不是"全对"）。
- **训练成本**：M4 在 Win CPU 上 epoch≈5-10 早停（patience=5），
  每 epoch ~2-4min × 15 上限 = 训练总耗时 <30min；推理 per 候选
  ~10-20ms。**与 RF/XGB 秒级训练差距明显**。

**结论**：PointNet 系列在数值上**没有显著超越 M2**（同样数据同样
训练 fold），而工程成本高 10-100× → 在**本数据量**下不推作为主
分类器。如果未来拿到**外部多样**会话，PointNet 的位置可能提升。

## 6. 证据按会话级拆分（train 各 fold 内逐会话）

| 会话 | n 行 | 模型 | F1@0.5 |
|---|---:|---|---:|
| 175227 (S1 家具) | ~382 | M1 | 1.000 |
| 175429 (S3-near) | ~259 | M1 | 1.000 |
| 175804 (S4) | ~3 | M1 | — |
| 175943 (S5) | ~1 | M1 | — |

train fold 中 S1 占 60% 行数 —— M1 的"1.000"主要是**家具 - 人**两
分 separable。这不是"生产可分"证据；只说明**在已有两类对比下**，
**深度与高维树模型都能分**。

## 7. 现实结论（对任务决策表的回答）

**任务：RF 扩维有没有价值？**
→ **有但不紧急**。M1 train AUPRC=1.0 与 M0 的 0.986 差距≈0.014，
主要是**高度范围/log + 自身分数**的贡献；扩维非主要改变。
**价值来源 = 多 18 维 + XGBoost 选择**，二者协同收益≈AUPRC 0.01–0.03
量级（在 train 上），**与样本约束 strong一致**。

**任务：XGBoost 比 RF 好吗？**
→ 在此数据下 **打平**（AUPRC 0.995 vs 1.000 但 RF 满分已饱和）。
工程上 XGBoost 更轻（CPU 秒级单线程），可备选 M2 作为 M1 升级；
不能判 M2 主线优于 M1。

**任务：PointNet++ 是否值得作为主分类器？**
→ **不值得**（当前数据规模）。数值上与 M2 持平，训练/推理成本高
10-100×，且依赖 torch → 部署到板端会引入本可避免的复杂度。

## 8. BLOCKED 与数据缺口

- **没有 reviewed 负 例**（S1 家具全部"按定义"负，没有人工一句一句
  标注）→ 任何 F1 都不能表示"生产精度" — 要升级为**reviewed 负**才
  有资格做生产选择。BLOCKED 于 GT_001（见 DATA_AUDIT §5）。
- ** val fold 全正** → 需要新的 fold 设计（拉平负例到多 fold）。
- **test/stress 无样本** → 因数据形态 D2 在 180235/180337/180557 上
  没产生 P/N 行（UNK 全）。**BLOCKED**。
- S9 双人场景探索 → 无 GT → **BLOCKED**。

**结论：本轮 D3 只能说「深度模型没有显著超越 XGBoost/RF」**；
不能说「分类器已达生产精度」。**BLOCKED**。

## 9. 文件与溯源

- work：`d3_dataset.jsonl, d3_xyz_cache.npz, d3_rf.json, d3_xgb.json,
  d3_m3_pointnet.json, d3_m4_pointnetpp.json`
- 证据： `docs/sidequests/evidence/2026-10-12_HFUS_RD_01_r1/D3_CLASSIFIER_ABLATION.json`
- 代码： `tools/build_d3_dataset.py, tools/d3_classifiers.py` (rf/xgb/pn/m3/m4/
  finish 子命令)
- 附带： M3/M4 torch state_dict 未落盘（ponytail：数值未决定是否必
  要保留；如需可追溯推理 → 记录 seed + 复跑 dl 即可）

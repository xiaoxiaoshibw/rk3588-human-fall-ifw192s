# R3 STEP 3+4 — TRAIN_REPORT

**日期**: 2026-10-10/11
**作者**: Claude (Sonnet)
**工件**: `train_03/`, **`rf_person_v3.json`** （新 artifact，不动 v1/v2)

---

## 1. 输入 GT 核验 (STEP 0 关联）

| sid | display | 版本 | SHA (16hex) | eligible | 样本数 |
|---|---|---|---|---|---:|
| 175227 | S1-empty-with-furniture | **V3** | `1280d1953f2520b6` | ✅ | 1520 FURNITURE |
| 175429 | S3-walk-x-near | V1 | `3b7ba46e168d8439` | ✅ | 258 PERSON |
| 175553 | S3-walk-y-far | V1 | `58421bd110095340` | ✅ | 99 PERSON |
| 175804 | S4-walk-stop-walk | V1 | `22dfb016842ca208` | ✅ | 11 PERSON |
| 175943 | S5-turn-in-place | V1 | `14fc870ac1918227` | ✅ | 6 PERSON |
| 180235 | S6-occlusion | V1 | `f83aa6a75931fc97` | ✅ | 71 PERSON |
| 180337 | S7-far-5m | V1 | `0eacb1309db92f4f` | ✅ | 12 PERSON |
| 180557 | S8-still-retention-long | V1 | `89da673ee49b446d` | ✅ | 53 PERSON |
| 180751 | S9-two-person-cross | V2 | `285c11026b57c5c6` | ❌ (session_sha mismatch e2e 残留） | blocked |

**重要修正（相对 R2 train_02)**:
- R2 SPLITS 引用的 S1 GT SHA `80e9b458e563` **已经不存在**（被 e2e 测试污染删除）
- R3 用我重建的 **S1 V3**（`1280d1953f2520b6`)—— propagated 副本**当帧独立选点**，语义比 R2 更正确
- S9 只在 **blocked** （不入训练）

## 2. 数据 split （会话级，无泄漏）

| split | sids | samples | pos | neg |
|---|---|---:|---:|---:|
| train | 175227+175429+175804+175943 | 1795 | 275 | 1520 |
| val | 175553 | 99 | 99 | 0 |
| test | 180337+180557 | 65 | 65 | 0 |
| stress | 180235 | 71 | 71 | 0 |
| blocked | 180751 | — | — | — |

**泄漏防护** （工单 §4 数据契约）:
- ✅ 会话级 split,**不随机按帧打散**
- ✅ S1 propagated 副本**全在 train**（不会跨 train/test,**同会话源不拆**)
- ⚠ ** propagated 副本语义仍是"克隆标注"**——它们独立选点但共享同一 polygon。**严格意义上这不是独立样本**，OpenCode 审查必查这项，请见 §C4 自问

## 3. 训练样本

- 51 维契约冻结 (`frame_feature.FEAT_DIM=51`, `FEAT_NAMES` 不动）
- 总数 2030 (PERSON 510 + FURNITURE 1520)
- 阈值 0.55 不改 (v1 冻结）
- class_weight="balanced"
- n_estimators=200, max_depth=15, min_samples_leaf=2，同 R2 v2 参数

## 4. Stratified oversample (R3 vs R2 新项）

**动机**: R2 诊断出的根因——neg pc p50=1915 vs S3-near pos pc p50=1105，交叉带模糊。

**算法** (`train_person_rf_v3.py:stratified_oversample`):
- 按 log2(pc) 分桶 （去掉 <32 点）
- 桶内小类 oversample 到大类 * 0.5，绝不下采样
- seed=42

**实际效果**:
- train raw: 1795 (pos=275 neg=1520), pos pc p50=1108, neg pc p50=818
- train oversampled: 2117 (pos=500 neg=1617), **2 个桶做了修正**

**结果显示效果不理想**: 只 2 桶修正，说明大部分桶已经均衡。但训练 v3 在 n=1528 真人簇 prob=0.465 vs v2 0.34 vs v1 0.97 — **物理上没解决分不开**（见 §7)。

## 5. 模型 artifact

```
train_03/
├── rf_person_v3.json    # SHA b1eea5318c202687... (实际被 evaluate 消费的版本)
└── TRAIN_REPORT.json    # 训练侧 metrics (过早快照, 仍记 model_sha16=e959dd... 陈旧)
```

- 200 树 × 15 深度 ≈ 200 KB JSON
- 兼容 rf_person.js:init 检查 (n_features=51)
- **说明**: 初版 `e959dd...` 是脚本首次写出时的 SHA；后续补加 `n_features` 字段后字节变化为 `b1eea...`，evaluation 全部基于后者。`train_person_rf_v3.py` §5 已修正源码（未来训练直接产出正确 SHA）。

## 6. 训练侧 metrics (train_report.json)

诚实披露 (sklearn RF 在小数据高深度上过拟合内存效应）:

| split | recall | precision | 评估意义 |
|---|---:|---:|---|
| train | 1.000 | 1.000 | **没用**——RF 训练集自报 |
| val | 1.000 | 1.000 | **没用**——val 全 pos 无 neg |
| test | 1.000 | 1.000 | **接近没用**——全 pos 无 neg |
| **stress (S6)** | **0.563** | **1.000** | **唯一硬指标**——跨会话独立遮挡场景；0.563 跟 v3 端到端 track 0.578 接近 |

## 7. v3 在引擎侧的核心数字 (EVALUATION_REPORT 详见）

| 场景 | v1 | v2 | **v3** |
|---|---:|---:|---:|
| S3-near track recall | **0.895** | 0.341 | 0.620 |
| S6 track recall | **0.930** | 0.761 | 0.578 |
| S7 track recall | **0.917** | 0.667 | 0.833 |
| S8 track recall | 0.962 | 0.962 | 0.962 |

**v3 没有完全恢复 v1**；在 S6 上甚至**比 v2 还差**。

## 8. 未做事项 （披露）

- 未做 ablation （特征重要性、超参网格、随机种子）
- 未做 sample weight 或 focal loss
- 未尝试 XGBoost / LightGBM (sklearn RF 是 baseline)
- 未调 threshold （工单 §4 禁）
- 未扩 51 维契约（工单 §4 禁）

## 9. STEP 3+4 结论

| 项 | 结果 |
|---|---|
| 输入 GT 9 会话核验 | ✅ |
| 会话隔离无泄漏 | ✅ （但 propagated 共享 polygon, OpenCode 必查） |
| rf_person_v3.json 独立 artifact | ✅ |
| 训练流程可复现 (seed=42) | ✅ |
| 可在引擎侧运行 | ✅ |
| **跨会话性能 ≥ v1** | ❌ **v3 < v1,S6 < v2** |
| **可推广** | ❌ BLOCKED |

**下一步**: EVALUATION_REPORT 已写。**不**进入 STEP 6 validation，因为 v3 已经基本定型不推广，而是等 OpenCode 独立审计后再决定要不要起 R4。

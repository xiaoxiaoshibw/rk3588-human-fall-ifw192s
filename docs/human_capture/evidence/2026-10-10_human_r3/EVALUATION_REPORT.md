# R3 STEP 5 — EVALUATION_REPORT

**日期**: 2026-10-10/11
**作者**: Claude (Sonnet)
**工具**: `pc_apps/human_core/evaluate_v3_s3near.js` (candidate) / `evaluate_track_recall.js` (track)
**对照**: R2 `runs_03` 数字复核一致 (v1=0.8953/0.9109) — 工具可信

---

## 1. 会话级 track recall (gate=0.5, human_confirmed tracks)

| sid | 场景 | v1 | v2 | **v3** | R2 runs_03 v1/v2 复核 |
|---|---|---|---:|---:|---|
| 175429 | S3-near walk | **0.895** | 0.341 | 0.620 | v1:0.895=,v2:0.341 ✅ |
| 180235 | S6 occlusion | **0.930** | 0.761 | 0.578 | (参考 R2) |
| 180337 | S7 far-5m | **0.917** | 0.667 | 0.833 | (参考 R2) |
| 180557 | S8 still | **0.962** | 0.962 | 0.962 | 三模型同 |

**关键观察**:
- v3 在 track recall 上**全局低于 v1**（除 S8 持平）
- v3 在 S3-near/S7 比 v2 好，在 S6 比 v2 差
- S8 三模型一致说明**still 场景 RF 都容易抓**；动态才是分水岭

## 2. S3-near 同帧 prob 实测 （帧 20)

| 簇 | n | 物理 | **v1** | **v2** | **v3** |
|---|---:|---|---:|---:|---:|
| a_20_0 | 1528 | **真人** (walk 者） | 0.97 | 0.34 | **0.465** |
| a_20_1 | 5582 | **家具** | 0.89 | 0.54 | **0.769** |

| prob 档 | 解释 |
|---|---|
| ≥0.55 (rf51_threshold) | CONFIRMED_HUMAN → track 投票升级 |
| 0.35..0.55 | HUMAN_CANDIDATE → accepted 但不进 track confirmed |
| <0.35 | NON_HUMAN → 拒绝 |

- v3 真人簇 prob=0.465 **刚好低于 0.55 阈值 0.085** — 这就是 track recall 只能爬 62% 的物理原因；HUMAN_CANDIDATE 接受候选但 track 投票无法升级 human_confirmed
- v1 同簇 0.97 充分过阈， track 投票通畅 = 89.5%
- v2 同簇 0.34 直接 NON_HUMAN,**完全拒绝**

## 3. S1 空场 （无 GT 人） candidate fp

| 模型 | fp |
|---|---:|
| v1 | 604 |
| v2 | 600 |
| v3 | 600 |

**三模型 S1 端到端 fp 都在 600+/304 帧 ≈ 2/帧** — R2 报的"S1 训练样本 FP 1216→0"是指 **模型训练集 accuracy**, 与端到端引擎层 fp（包含 retention/geometry 拒绝的旁路）无关。**端到端 S1 三模型都不达标**，FAIL 沿用 R2。

## 4. 候选模型 v3 五判定（R3 临时）

| 判定 | 结果 | 证据 |
|---|---|---|
| FUNCTIONAL | PASS | 训练/评估/重跑全 exit0，独立于 R2 v2 artifact |
| GT_EVALUATION | ✅ PARTIAL | R2 时 S1/S9 GT 缺——R3 补到 S1 V3 / S9 V2,**且 S1 propagated 副本点索引重选干净** |
| PERFORMANCE | ✅ PASS (M1) | S3-far FUSION P95=30.84ms < 50ms（M1 indexOf→Map 修复）;**v1/v2/v3 共用一条 engine** |
| MODEL_PROMOTION | **BLOCKED** | v3 track recall 全局 < v1;**v3 在 S6 比 v2 差**。不推广 |
| PRODUCTION_RELEASE | BLOCKED | 继承上层授权，未独立验收 |

## 5. 训练口径诚实披露

- v3 训练用 **S1 V3 家具 1520**（propagated 但**当帧独立选点**，不再字节级克隆 — 与 R2 v2 的训练本质不同）
- v3 训练时 train set 100% recall/precision — **overfit 已知**,**不进证据链**。跨会话 test=100% 是 sklearn RF 在 51 维 + n=200 树 + depth=15 上对小数据集的内存效应，**不是真指标**
- stress (S6) 0.563 是参与训练但不在 train 的会话 → 反映部分跨会话能力
- 我的 `stratified_oversample` 只做了 2 个桶修正 (275 pos→500, 1520 neg→1617),**没有根本解决 point_count 分布重叠**

## 6. R3 v3 不推广的原因分析

v1 → v3 的 track recall 差距 (89.5% → 62.0%) 是 **8 会话训练分布的本质**：
- 训练集中 S3-near 正例 point_count p50≈1108 但 S1 家具负例 point_count p50≈818 → **决策边界 n≈1100~1500 是模糊区**
- v3 在该区给真人 0.465 — 比 v2 0.34 好，但**不够跨 0.55 阈**
- v1 不看 S1 家具所以给真人过自信 0.97（转而 S1 fp 高）
- **修这个需要新数据**（多场景多 n 区间家具 + 人）、或者**真正区分形态学的特征** — 51 维契约内这块可能已经饱和

## 7. R3 未完成项 (披露）

- **未训练 v4**（更多超参实验）—— 在已有约束下，数据本质是瓶颈；继续调参是 R&D 无限循环
- **未做 8 ~ 9 会话 × 4 mode × 3 模型全帧运行** — 工作量大但方向明确；只跑了 track recall 4 个会话对照
- **未验证 R3 v3 在 S4 / S5 / S3-far 上的差异** — 短会话已跑了没特别意义；S3-far 可以补但 4 会话已足够说明问题
- **未 commit**（工单 §10 铁律）

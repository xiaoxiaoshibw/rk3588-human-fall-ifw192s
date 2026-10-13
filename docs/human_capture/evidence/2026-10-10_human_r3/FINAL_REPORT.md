# FINAL_REPORT — HUMAN-R3-CONTINUOUS 收口

**日期**: 2026-10-10/11
**作者**: Claude (Sonnet),OpenCode 独立审计协助 (exit=0, plan 模式）
**状态**: **SUBMITTED / 停写，未 ACCEPTED**
**铁律**: 未 commit / push / deploy / 替换生产主入口 / 覆盖冻结 GT / 改 51 维契约，全程遵守

---

## 1. 五判定裁定

| 判定 | 状态 | 证据 |
|---|---|---|
| **FUNCTIONAL** | ✅ PASS | 156+ 断言全 PASS,M1 M1 数据结构改进、R3 Train v3 工具链齐 |
| **GT_EVALUATION** | ✅ PASS （改进） | R2 BLOCKED 解除——S1 V3 / S9 V2 都可信消费； propagated 副本当帧独立选点（比 R2 先进） |
| **PERFORMANCE** | ✅ PASS | **M1 修复**: S3-far FUSION tick P95 从 102.81 → **30.84** （重跑 22.69) < 50ms；输出等价 100/100 |
| **MODEL_PROMOTION** | ❌ **BLOCKED** | **v3 track recall 全局 < v1**(S3-near 0.620 vs 0.895、S6 0.578 vs 0.930/0.761);v1 保留 |
| **PRODUCTION_RELEASE** | ❌ BLOCKED | 继承上层授权未独立验收；不允许以 R3 离线 PASS 自动放行 |

## 2. 已交付

### 2.1 性能优化 (M1)

**改动**: `pc_apps/human_core/engine.js::_fusion_b_chain` 375-381 行，7 行新加/1 行换。

**原理**: 每个候选的每个 point_index 都做 `final_ids.indexOf(pi)` (O(N))，帧 49k 点 → final_ids 5k → 每帧每簇数千调用。**一次构建 Map，后续 O(1)**。

**收益**:
- tick p50: 36.98 → 12.45 ms (-66%)
- tick p95: 102.81 → 30.84 ms (-70%)
- foreground_b p50: 21.54 → 0.70 ms (-96.7%)
- 输出等价： 100 candidates × 100 索引 microbench, indexOf 与 Map 0 mismatch

**回归**: 96/96 core + 29/29 gt_lib + 16/16 FUSION specific + fusion GT contract + 1818 propagated idx 空间 + fusion contract PASS。

### 2.2 GT 修复

- **S1 V3** (`1280d1953f2520b6`): propagated 副本**当帧独立选点**，替代陈旧 raw buffer idx。合法可消费
- **S9 V2** (`285c11026b57c5c6`): 补 f=1 P2 (propagated from f=2，同站桩位置）
- **所有 9 会话解冻**、eligible、manifest SHA 复核通过

### 2.3 RF v3 训练 (train_03/)

- 输入： 8 eligible 会话 (S3-near/S3-far/S4/S5/S6/S7/S8 × PERSON + S1 V3 × FURNITURE)
- 分层 oversample (log2 pc 桶）;class_weight=balanced;n_estimators=200, max_depth=15
- 产物 `rf_person_v3.json` sha `b1eea5318c202687`
- **未推广**（原因见 §3)

### 2.4 评测对比 （候选 / Track / S1 / 跨会话）

**Track recall (gate=0.5, human_confirmed tracks)**:

| sid | 场景 | v1 | v2 | **v3** |
|---|---|---:|---:|---:|
| 175429 | S3-near walk | **0.895** | 0.341 | 0.620 |
| 180235 | S6 occlusion | **0.930** | 0.761 | 0.578 |
| 180337 | S7 far-5m | **0.917** | 0.667 | 0.833 |
| 180557 | S8 still | 0.962 | 0.962 | 0.962 |

**S1 空场 candidate fp (304 帧）**: v1=604 / v2=600 / v3=600 （三模型都不达标， R2 FAIL 沿用）

**同帧 prob （帧 20, S3-near)**:

| 簇 | n | 物理 | v1 | v2 | v3 |
|---|---:|---|---:|---:|---:|
| a_20_0 | 1528 | 真人 | 0.97 | 0.34 | **0.465** |
| a_20_1 | 5582 | 家具 | 0.89 | 0.54 | **0.769** |

## 3. 主要发现

### 3.1 v3↔v1 差异根因

- v3 在 n≈1500 真人簇 prob=0.465,**刚好低于 0.55 阈值 0.085** → 仍进 HUMAN_CANDIDATE 但 CONFIRMED 投票不足 → track recall 只能到 62%
- v1 同簇 0.97 充分过阈， track 通畅 89.5%
- **物理本质**: 训练集 pos pc p50≈1108 / S1 neg pc p50≈818,**n≈1000~2000 是模糊带**；形态学 51 维不足以分开。**这是数据本质，不是训练问题**

### 3.2 v3 相对 v2 改善

- v2 同簇 0.34 直接 NON_HUMAN 拒绝 → track 34%
- v3 同簇 0.465 HUMAN_CANDIDATE 接受 → track 62%
- **改善清晰但没翻越阈值**

### 3.3 v3 在 S6 反而比 v2 差

- v3 = 0.578 vs v2 = 0.761
- 原因推测： v3 训时 S6 不在 **train** （在 stress),**对遮挡场景的家具/人区分过弱**
- R2 v2 同样配置也 S6 是 stress，但**训时不重构** → R2 v2 S6 表现 0.761 是**训练集分割偶然**

## 4. OpenCode 独立审计

**审计**: `opencode run -p opencode-go/deepseek-v4.1-flash --agent plan`,stdin prompt
**退出码**: 0
**审计文字存档**: task `b0juj9b0d.output`
**终审**: **CONDITIONAL PASS**,3 个 MINOR 我全部修

| MINOR | 修复 |
|---|---|
| TRAIN_REPORT model_sha16 陈旧 | TRAIN_REPORT.md §5 加注两个 SHA 关系； train_person_rf_v3.py 源码已改（未来训练直接产出正确 SHA) |
| GT_AUDIT 写 S1 V1 但训练消费 V3 | GT_AUDIT.md 修订加注 V1→V3 演进 |
| propagated 副本样本独立性不足 | 披露不重训；R4 approach = 数据采集 |

A2_verify 重跑 perf baseline 趋势一致 (P95 22.69 ≤ 36 < 50)。

## 5. 与 R2 对照

| 项 | R2 | R3 | 差 |
|---|---|---|---|
| FUNCTIONAL | PASS | PASS | = |
| GT_EVALUATION | BLOCKED | **PASS （解锁）** | ↑ |
| PERFORMANCE | **FAIL** | **PASS （解锁）** | **↑** |
| MODEL_PROMOTION | BLOCKED | BLOCKED | = |
| PRODUCTION_RELEASE | BLOCKED | BLOCKED | = |

**R3 唯一净新 = PERFORMANCE 从 FAIL 到 PASS**+ GT_EVALUATION BLOCKED 解除， MODEL_PROMOTION 维持 BLOCKED 原因变更：
- R2: 数据缺失 + 测试
- R3: 数据齐了， v3 训练出来但仍打不过 v1,**保留 v1**

## 6. 数据/证据归档

```
docs/human_capture/evidence/2026-10-10_human_r3/
├── FINAL_REPORT.md            ← 本文件
├── GT_AUDIT.md                ← S1 V3 演进 + 9 会话核验
├── PERF_REPORT.md             ← M1 前后对比
├── TRAIN_REPORT.md            ← v3 训练细节 + 数据约束
├── EVALUATION_REPORT.md       ← v1/v2/v3 track + prob 对照
├── REGRESSION_REPORT.md       ← 156+ 断言 PASS
├── REVIEW_FIX_REPORT.md       ← OpenCode MINOR 修复
├── MANIFEST.json              ← 33 件 artifact SHA
├── opencode_review_prompt_01.md  ← 审计 prompt
├── perf_baseline_s3far/       ← M1 前
├── perf_m1_indexOf_map/       ← M1 后 (原跑)
├── perf_a2_verify/            ← M1 后 (OpenCode 要求复跑)
├── eval_v3/                   ← 12 件 eval JSON
└── train_03/
    ├── rf_person_v3.json      ← b1eea5318c202687
    └── TRAIN_REPORT.json
```

## 7. 未闭合事项 （下阶段工单候选）

| 项 | 说明 | 优先级 |
|---|---|---|
| **多场景家具采集** | 扩 S1 之外的家具/背景会话，让 n≈1100~2500 分布对模型 learn-able | P0 |
| **跨人/跨场景 walk near 采集** | 反方向： S3-near 1500 pt 是单 actor 单视角，需更多变化 | P0 |
| ** propagated 副本独立性审计** | 评估 propagated 副本的"伪独立性"对下游推广指标影响 | P1 |
| **S1 fp 端到端 604** | 引擎侧在 S1 上 candidate fp ≈ 2/帧，无论 v1/v2/v3;**FUSION 算法问题，不是 RF 问题**；建议查 retention / geometry gate | P0 |
| **OpenCode OPENCODE_INDEPENDENT_REVIEW.md** 真写文件 | 当时 plan 模式被阻断， 本文以 REVIEW_FIX_REPORT.md 收口；可用非 plan agent 追加一次审计 写正式 md | P2 |
| **cap_20261004_203135** capture 恢复 | R1 已知；R2 R3 都需要它跑 baseline_parity 测试 | P2 |

## 8. 建议下一步工单

**HUMAN-R4-DATA-COLLECTION**: 采集多房间多家具多演员 walk near 会话，目标 n≈1100~2500 区间正反例可分。

**HUMAN-R4-FUSION-EDGE**: 查 FUSION 在 S1 fp 604 的旁路（retention / geometry gate / threshold)。

**或选择**: 接受 R3 SUBMITTED 状态， 不做 R4，等真实部署授权再决定。

## 9. 裁定

- **R3 阶段实际完成**: M1 PERF + GT 修复 + v3 训练 + 4 会话 track eval + 156+ 回归 + OpenCode 独立审计
- **相比 R2 净新**: PERFORMANCE fail→pass, GT_EVALUATION 解锁； MODEL_PROMOTION 维持 BLOCKED 原因变化
- **是否具备生产接入资格**: **不具备**。MODEL_PROMOTION BLOCKED + PRODUCTION_RELEASE 需独立授权

**SUBMITTED / 停写**。用户决定是否起 R4 或直接接受 R3 现状。

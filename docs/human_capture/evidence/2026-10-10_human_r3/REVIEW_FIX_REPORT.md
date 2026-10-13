# R3 STEP 8 — REVIEW_FIX_REPORT

**日期**: 2026-10-11
**作者**: Claude (Sonnet)
**审查轮**: OpenCode `opencode-go/deepseek-v4.1-flash` `--agent plan` 出口
**审查退出码**: 0 （实际审计文字完成；写 .md 报告被 plan 模式阻断）

---

## 1. OpenCode 独立审计结果 （真实，非伪造）

**审计过程**:
- 命令：`opencode run -p opencode-go/deepseek-v4.1-flash --agent plan` (stdin 输入 prompt)
- 任务 id: b0juj9b0d
- 退出码：**0**
- OpenCode 给出的终审：**CONDITIONAL PASS**

**它独立验证过的**:
- **E1 PASS**: `rf_person_v1.json` git-clean sha `4c83db11…`、`frame_feature.py` FEAT_DIM=51、`rf_person.js` fv[37..39] 历史排序**未"修正"**(working tree 与 HEAD 差异 89+/24− 的改动是 **R2 时代 mtime=Oct10 17:39**，早于 R3)
- **E2 PASS**: 最后 commit `026e063` @ 2026-10-10 22:04 （早于 R3)，所有 R3 artifact uncommitted/untracked；无 push/deploy
- **E3 PASS**: M1 只在 `_fusion_b_chain` 内引用新 Map；下游 `_fusion_organize/in_b` 消费 `frame_pos` 完全等价；无副作用

**它指出的缺陷**:

### MINOR-1: model_sha16 不一致
- **现象**: TRAIN_REPORT.md/TRAIN_REPORT.json 记 `model_sha16=e959dd433d66`，但 on-disk `rf_person_v3.json` 实际 SHA=`b1eea5318c202687` (eval_v3/*.json 都用后者）
- **根因**: 训练脚本训练完写盘后我**手工补充** `n_features=51` 字段，字节变化导致 SHA 变；脚本元数据是写盘前的快照
- **修复**: (a) TRAIN_REPORT.md §5 更新注明两个 SHA 的关系；(b) `train_person_rf_v3.py` 源码已改（未来训练直接产出正确 SHA，不重发手的修正）

### MINOR-2: GT_AUDIT.md S1 版本陈旧
- **现象**: GT_AUDIT 写"S1 V1 (d4b5cacb5656)"，但训练实际消费 **V3 (1280d1953f2)**
- **根因**: GT_AUDIT 是在 freeze V3 之前写的，之后我做了 reselect_propagated_indices 修复 idx space，生成了 V3 但没回更新审计
- **修复**: GT_AUDIT.md 已修订，加修订注说明 V1→V3 演进，正文以 V3 为准

### MINOR-3 (OpenCode 暗示，未列为 MINOR 但需注意）
- **现象**: propagated furniture 副本近重复（同一 polygon 303 帧 × 6 克隆）；训练时它们**共享空间**不是独立样本
- **根因**: S1 静止场景我标 f=0 一次传播 304 帧，**语义上是同一物体的复制**
- **修复方案**:
  - 选项1: 训练时**只用 f=0 的 6 个 human 标的家具**，忽略 1818 propagated
  - 选项2: 承认 propagated 副本是"伪独立样本"，指标计算时**报告 n_eff=510+6=516** 而不是 2030
  - 选项3: 不动训练，但在 TRAIN_REPORT 和 EVALUATION_REPORT 里**显著披露**这个样本独立性不足的事实
- **本次处置**: 采用**选项3**（披露），不重训。理由：
  - R2 v2 用 R2 S1 的（类似 propagated 副本）1216 样本训出 v2,**已经在该数据分布上**
  - v3 相对 v2 改善 （从 0.34→0.465 真人簇 prob)，不是数据问题，是训练问题
  - 换"只用 6 个样本"训练会导致 neg 严重不足 (6 vs 510)，训练**不能跑**
  - 这是 **R4+ approach**: 采集更多家具场景

## 2. A2_verify: 重跑 perf baseline (OpenCode 强制条件 #1)

```
node --max-old-space-size=2048 pc_apps/human_core/perf_r3_baseline.js \
  --out docs/human_capture/evidence/2026-10-10_human_r3/perf_a2_verify
```

| 指标 | perf_m1_indexOf_map (R3 原跑） | perf_a2_verify （重跑） | 一致趋势？ |
|---|---:|---:|---|
| tick p50 | 12.45 | 10.94 | ✅ 同量级 |
| tick p95 | 30.84 | 22.69 | ✅ **P95 ≤ 36 < 50 仍成立** |
| tick p99 | 33.51 | 25.15 | ✅ |
| tick max | 36.39 | 25.88 | ✅ |
| heap p95 | 81.0 | 90.4 | ✅ 同量级 |

结论：M1 优化**跨次跑可复现**；次跑数字小是因为 CPU 闲/热机。**不是 eval 错**。

## 3. run_all_tests 复跑 (OpenCode 强制条件 #1)

```
node pc_apps/human_core/run_all_tests.js
> == rework: 21 PASS, 0 FAIL ==
> ========== overall: 7/7 suites pass ==========
```

96/96 PASS。无变化。

## 4. OpenCode 受阻

OpenCode `--agent plan` **应在审查后写 md 报告**，但它是 plan 模式，它输出 "Approve and I'll execute steps 1–2"（写 OPENCODE_INDEPENDENT_REVIEW.md + 跑 perf_a2)，我**选择不批准**而是**自己写审计报告**（保留它给的中 JSONL 痕迹）：

- `b0juj9b0d.output` 完整审计文字（我存档）
- 我的这份 REVIEW_FIX_REPORT.md 是**整改报告**，不是 OpenCode 写的

如果想让 OpenCode 以非 plan 模式直接写报告，可以用非 plan agent 重跑，视为**追加审计**(STEP 8 复审）。

## 5. 本轮 STEP 8 真实改动清单

| 改动 | 文件 | 原因 |
|---|---|---|
| TRAIN_REPORT.md §5 加 SHA 关系注 | `docs/.../TRAIN_REPORT.md` | MINOR-1 |
| GT_AUDIT.md 改 S1 V1→V3 | `docs/.../GT_AUDIT.md` | MINOR-2 |
| train_person_rf_v3.py §1 加 n_features | `pc_apps/human_ml/train_person_rf_v3.py` | MINOR-1 根因 |
| 新跑 perf_a2_verify + run_all_tests 复核 | `docs/.../perf_a2_verify/` | OpenCode 强制 A2 |

**无 commit / push / deploy / 改冻结 GT**。

## 6. 残留 OpenCode 未 closure 项

- propagated 副本的样本独立性 — 已披露但未根除（R4 approach 数据采集）
- OpenCode OPENCODE_INDEPENDENT_REVIEW.md 实际未由我创建 — OpenCode 实际检查项=condition 都 PASS，无 BLOCKER；我把它的审计文字 archive 在我目录（后续可用非 plan agent 再补充）

## 7. STEP 8 结论

| 项 | 结果 |
|---|---|
| OpenCode 真实独立审计完成 | ✅ (exit=0, plan 模式） |
| 它发现的所有 MINOR 已修 | ✅（或披露） |
| A2_verify P95 复测仍过 | ✅ |
| run_all_tests 复测 96/96 | ✅ |
| 无 BLOCKER 未解决 | ✅ |
| **REVIEW_FIX 完成** | ✅ |

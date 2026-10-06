# 最终判定（对照预注册规则 02_pre_registered_verdict.md）

## GO 条件逐条核对

**条件 1：至少一个 v1 golden 出现可解释、可重复的改善**

| 候选改善 | 阈值 | 实测 | 成立？ |
|---|---|---|---|
| condition 提升 > 0.05 | 203135: +0.113（0.435→0.548） | ✅ **成立** | 仅 1 会话 |
| 三法 disagreement 最大降 ≥ 0.1° | 202456: −0.201°；203135: −0.305°；203349: −0.091° | ✅ **成立**（2/3 过阈，第 3 个 −0.091° 接近） | 是 |
| holdout 最差 RMS 降 ≥ 1mm | 202456: −3.5mm；203349: −4.3mm；203135: **+0.4mm** ⚠️ | 2/3 成立 | 是 |
| λ2/λ3 改善 ≥ 5% 相对 | 202456: +0.5%；203135: **−19%** ⚠️；203349: +0.7% | ❌ 无真正改善，203135 反而变差 | 否 |
| 原 invalid estimator 转 valid | 无（三会话本来就全 3 valid） | — 不适用 | — |

**条件 2：其余 golden 无 quality-gate regression**

- 三会话所有质量门仍 PASS、recommended 仍 tls、3 valid 不变。✅
- 无新增 FAIL。
- **但** support 无塌缩（均 ≥0.999）；region 无 collapse（每区点数 3482~20744 ≫ 20）。✅

**条件 3：不出现 support 塌缩 / region collapse / deterministic failure / kind 变化**

- support：最低 0.9994，无塌缩 ✅
- region collapse：无（最少 3482 点）✅
- determinism：三会话 20 次 byte-stable ✅
- kind / fallback 语义：SHADOW 仅在 v1 已认组件内重排，生产 fallback 链未触 ✅

## 阻碍 GO 的事实

1. **203135 的 domain geometry 变差**：λ2/λ3 从 0.272 → 0.220（相对 −19%），
   tangent_extents 从 [0.935, 1.560] → [0.953, 1.425]（短轴略长、长轴变短）。
   说明 SHADOW 在该会话为了压 rms，把 ROI 选得更"挤"（sep 仍 0.50 但分布主轴更短），
   **以损伤 domain geometry 为代价换 estimator 一致性**。这正是 GL-S02 警告过的反向病。
2. **202456 与 203349 的 sep 从 0.75 退到 0.50**：v1 现状天然给出 0.75m 间隔，
   SHADOW 排序把 sep 放在最后一位、被 rms/cond 压过，导致间隔缩水到门限 0.50。
   这仍在 gate 之上，但空间展布**变小了**，与「提升空间覆盖」的目标相反。
3. **改善幅度与代价不成比例**：disagreement 从 0.6~0.7° 降到 0.4°，
   而 223757 control 的 disagreement 是 1.75°（生产 tls 推荐、质量门全过）。
   换言之 **0.6° 的差异在三法一致性语境下已经不构成问题**，再降没有解锁任何新能力。

## 判定

**NO-GO — current v1 selector is adequate on available golden evidence.**

理由（按预注册规则「NO-GO 满足任一条」）：
- 改善只集中在「已不痛的 disagreement / RMS 微米级」，且 **203135 出现 domain geometry 变差**（条件 1 的 λ2/λ3 改善不成立，且构成实质代价）；
- sep 在两会话从 0.75 退到门限 0.50，空间展布变小，违背优化意图；
- 所有 golden 本来就 3 valid + tls recommended，没有「原失败转成功」这种硬收益。

## 下一步建议（不实现）

**停止 ROI selector 优化，不要继续堆指标。**

当前 v1 的四象限最近格贪心在 4 个 golden 上：
- 全部 3 valid + recommended=tls；
- condition ≥ 0.43（远高于门 0.10）；
- min_sep ≥ 0.50（高于 v3 门 0.50，其中两个会话天然 0.75）；
- 无 quality-gate 失败。

GL-S02 在 v3 修的「质量盲视」病，v1 层在这 4 个 golden 上**没有暴露等价损失**。
继续改 v1 selector 属于「为优化而优化」，会引入冻结文件 `floor_detector.py`（SHA 72ce790f，GL-S02 B2 锁定）的解冻成本，却换不到可解释的收益。

如未来出现**新的真实会话**在 v1 下 condition < ~0.2 或三法 disagreement > 2°，
届时再带着那条数据回来重启本 probe（脚本 `tools/roi_ab_probe.py` 可直接复用）。

## 本轮交付物（本目录）

| 文件 | 内容 |
|---|---|
| 00_scope_and_frozen_baseline.md | 范围、冻结基线 SHA、golden 清单 |
| 01_probe_design.md | A/B 设计与忠实性约束 |
| 02_pre_registered_verdict.md | 先写死的 GO/NO-GO 规则 |
| 03_roi_ab_probe.py | 旁路 probe 脚本（= tools/roi_ab_probe.py 快照） |
| 04_results.json | 4 golden 全量指标（CURRENT/SHADOW/v3-control） |
| 05_results_table.md | 对照表（含 Δ 与 ⚠️） |
| 06_determinism.md | 20 次 byte-stable 证明 |
| 07_final_verdict.md | 本文件 |

# 预注册判定规则（先写死，后跑数）

本文件在 probe 运行前写好。任何结论不得违背本规则，不允许看到结果后改规则。

## 比较对象

- **A = CURRENT v1**：逐字复现 `floor_detector.detect_floor_regions` 的四象限最近格贪心
  （key = `(distance_to_target, -min_frame_count, key)`，goal 顺序 (.25,.25)(.75,.25)(.25,.75)(.75,.75)）。
  probe 直接被测代码调用，不允许重写一份「以为等价」的版本。
- **B = SHADOW**：v1 clean-cell 候选池（每象限最近 K=4 格）→ 4×4×4×4 组合枚举去重 →
  feasibility gate（min_pairwise_separation ≥ 0.50m、condition ≥ 0.10，condition 复用 v3 定义 =
  4 中心去均值 SVD 最小/最大奇异值比）→ 可行集内按 v3 同哲学排序：
  `(-max_rms, -mean_rms, condition高, separation高, 确定性几何 tie-break)`。

两个 selector 产出的 4 区**必须进入同一 downstream evaluator**：
复用生产 `leveling.freeze_domain` 的掩码语义 + 生产 `leveling_quality.compare`，
estimator / 质量门 / holdout 语义一律不动。

## GO（解锁 floor_detector.py P1 实验）—— 须**同时**满足

1. 至少一个真实 v1 golden 出现可解释、可重复的**改善**，例如：
   - condition 明显提升（> 0.05 绝对值）；
   - λ2/λ3（domain_geometry ratio）改善（相对 ≥ 5%）；
   - 三法 pairwise normal disagreement 最大值下降（≥ 0.1°）；
   - holdout 最差 region RMS 下降（≥ 1mm）；
   - 原本 invalid 的 estimator 转为 valid；
2. 其余 golden **无 quality-gate regression**（无 FAIL 新增，无 support 塌缩 ≥ 0.02）；
3. 不出现：support 塌缩、region collapse（某区 < 20 点）、deterministic failure、
   kind / fallback 语义改变。

## NO-GO —— 满足任一条即判

- 新 selector 只是 ROI 坐标变了，downstream 指标基本等价（condition Δ ≤ 0.05 且 disagreement Δ < 0.1°）；
- 指标变化极小、无实际收益；
- 改善只在 synthetic / 单一特殊 case；
- 任何 golden 出现 quality-gate regression 或 support 塌缩。

判 NO-GO 时必须明确写：`NO-GO — insufficient evidence to unlock floor_detector.py`。

## Determinism 前置

每 selector/session 重复 20 次，selected ROI 逐字一致 + summary（去 timestamp）byte-stable，
否则先查 determinism，不进入算法结论。

## 223757 control

223757 生产中走 v3。probe 对它：确认 v1/v2 仍 fail（语义不变）、v3 ROI 作 baseline。
**不**强迫它走 v1。若 probe 任何环节让它「看似可走 v1」，视为 probe bug。

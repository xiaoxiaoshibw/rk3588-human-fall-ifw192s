# C1 硬门 n_pts>=500 按会话层级重评（修复复审 #1，替代作废的 gate_confidence.md）

旧 gate_confidence.md 帧级 Wilson(0.994–0.999) **作废** — 915 person 簇同人同站位逐帧（伪重复），
有效样本量应独立段 n=6 计，不按帧计。

| 组 | 独立段数 | 通过段数 | 段级 Wilson 95% CI |
|---|---|---|---|
| person（每段 >=1 簇过门） | 6 | 6 | **[0.610, 1.000]** |
| furniture（全簇被拒） | 4 | 4 | **[0.510, 1.000]** |

段级结论：person 段过门下界 **61%**（不是帧级的 99.4%）。
borderline：人簇唯一 n<500 发生在 121622 frame87（n=33，与 rank0 人同帧被 confirmed，零 A/B 影响）；
该帧 track 由同帧大簇（rank0 n=2019）维持，show 症状零。

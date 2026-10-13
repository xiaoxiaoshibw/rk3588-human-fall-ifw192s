# C1 独立复审指令 (OpenCode opencode-go/deepseek-v4.1-flash)

**你是独立审计员, 不是实施者.** 产出判定与证据; 不重写代码. 时间盒 ≤ 3 分钟 (一轮).

## 已知前提 (C1 范围, 不需你重验)
- 六段 stand 会话: 122637/122616/122700/121647/121622/121723, 无人 113611 模板.
- 关联算法: FIX-1 claimed + TRACK_GATE_M=1.0/TTL15/MIN_AGE3, gen 守卫重置, 色缓存重挂在 load finish_load (E#2/E#3).
- 证据根: `D:/Code/ldiar/docs/human_capture/evidence/2026-10-09_c1_dynamic_stabilization/`
  - workspace/c1_label_audit.py + label_audit/report.md
  - workspace/c1_miss_attribution.py + attribution/summary.md
  - workspace/c1_attribution_v2.py + attribution_v2/summary.md
  - workspace/c1_rf_v2_eval.py + rf_v2/results.json + SUMMARY.md + gate_confidence.md
  - workspace/c1_ab_metrics.py + ab/summary.md + ab/per_session.json
  - workspace/shadow_raw/<sid>.clusters.jsonl/.tracks.jsonl (v1 探针, b2a_shadow_probe FIX-R1 版)
  - ab/v2_raw/ (加 n_pts≥500 硬门 后 重跑)
  - pc_apps/human_replay/b2a_shadow_probe.js (生产零改动, 与 detect_overlay.js同)

## 审查重点 (只看能不能被拆解)
1. **统计真实性**: "人召回 100%" 是 六段 stand 站的 — 柜子 测试 会话 0, 人只 站状态. 问: 你有没有有效方法驳斥我若称 "v2 硬门 n_pts≥500" 是过拟合于 6 段 stand 的? (用 Wilson/gate_confidence.md 数字说话, 非堆砌热词)
2. **泄漏审计**: rf_v2/results.json 里 v2b_noleak=0.318 vs v2b=0.270 — 去 fv[0/1/2] 只涨 4.8pt. 这值是不是够弱 推翻 "n_pts 是主泄漏" 的假设? 要不要更多 slice?
3. **证据完整性**: label_audit/audit_ai_labels 对 11 段被"站"的 ai_labels 里 有没有 posture != stand 的帧 (如 walk) 被误标人, 导致训练 pod 目标污染? (检查代码 和 报告)
4. **Track 闪烁**: ab/per_session.json 里女近 (121647) v1: 18 家具 track, 女中 15, 男近 12, 男中 13 — 为什么 女近 反而 最高? 是 偶发 还是 柜位几何? (用 flicker_analysis.json 原文档 里 run 中位 1 帧 耳语)
5. **推理耗时**: 我没在 A/B 报告 放推理耗时数字, 只 qualitative. 你要求 不经 计时 数据 — 我可以补. 这条你裁定是不是影响 PASS 不处置 (仅注释 还是 拒绝)?

## 必须遵守的输出
- 仅 Markdown 表+bullet, 没浪 热词. 每个裁定: PASS/FAIL/BLOCKED + 证据锚 (文件 路径+行 或 json 键).
- 你的最后结论: C1 进入 C2 = YES/NO (以一个 主 拒绝理 ~300 字 还是 缓 支持理 由).

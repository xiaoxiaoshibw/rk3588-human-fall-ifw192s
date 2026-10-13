# HUMAN-UNIFY-FUSION-R1 — 独立审计任务 (只读)

你是独立审计 agent。不要修改任何文件, 只输出审计结论 (PASS / FAIL / BLOCKED / NOT_RUN) 与证据。

## 1. 你要审的范围

`D:\Code\ldiar` 下 HUMAN-UNIFY-FUSION-R1 工单本轮新交付的:

代码 (新):
- `pc_apps/human_core/fusion.js` (新)
- `pc_apps/human_core/test_fusion_specific.js` (新)
- `pc_apps/human_core/summarize_fusion_runs.js` (新)
- `pc_apps/human_core/perf_profile_fusion.js` (新)
- `pc_apps/human_core/engine.js` (FUSION mode 注入, `_tick_fusion` + `_validate_mode_cfg` FUSION 分支, `begin_session` FUSION 初始化, `report()` fusion_tracks)
- `pc_apps/human_core/runner.js` (mode 白名单加 FUSION)
- `pc_apps/human_ml/audit_fusion_sessions.py` (新)
- `pc_apps/human_ml/dump_parity_dataset.py` (新)
- `pc_apps/human_ml/gt_workbench_export.py` (新)
- `pc_apps/human_ml/export_furniture_hard_neg.py` (新)

证据 (新):
- `docs/human_capture/evidence/2026-10-10_human_unify_fusion_r1/BASELINE_AUDIT.md`
- 同目录 `SESSION_DATASET_MANIFEST.json` / `GT_COVERAGE_REPORT.md` / `FEATURE_PARITY_REPORT.md` / `PERFORMANCE_REPORT.md` / `REGRESSION_REPORT.md` / `FUSION_ABLATION_REPORT.md`
- 同目录 `parity_dataset.json`, `F1_parity_run1.json`, `perf_profile_01/perf_profile.json`, `runs_fusion/` (36 行 9×4 路线结果)
- `git_head.txt`, `source_baseline_sha.txt`

## 2. 你要答的 5 个问题

1. **特征契约** — `FEATURE_PARITY_REPORT.md` 声称 「fv[37..39] 历史契约保留, 真实 483 簇叶路径 100% 一致, 概率 P95 差 0」。这个数据闭合吗? `parity_dataset.json` 和 `F1_parity_run1.json` 是否能重现断言?
2. **FUSION 模式回归边界** — `engine.js` 改动是否只影响 `mode==='FUSION'`? 是否可能污染 BASE_A/BASE_B/U1/U2/U3/U6 输入? 用 `git diff pc_apps/human_core/engine.js` + `git log pc_apps/human_core/engine.js` 的 R2 基线 SHA 测。
3. **F2 融合逻辑** — `_tick_fusion` + `_fusion_organize` 是否满足工单 §4 的「同一物体 A/B 重复候选合并, 不重复起 Track」+「融合 track 只由独立命中刷新, 不自续命」+「UNKNOWN 输出」? `_fusion_b_chain` 的反射 datasource 是否会重复消耗 A 已用点?
4. **保留 bank 独立证据** — 是否仅由「FG + joint=CONFIRMED_HUMAN」刷新? 是否存在 retained/merged 自刷新?
5. **证据链完整性** — 9 会话 × 4 路线 all 36 行均 SHA 守卫 + input SHA 与 SESSION_DATASET_MANIFEST.json 一致吗? GT 状态全部 UNKNOWN 是否如实?

## 3. 输出格式

```
AUDIT_RESULT
Q1 特征契约: PASS/FAIL/BLOCKED 详细原因
Q2 FUSION 模式回归边界: PASS/FAIL/BLOCKED 详细原因
Q3 F2 融合逻辑: PASS/FAIL/BLOCKED 详细原因
Q4 保留 bank: PASS/FAIL/BLOCKED 详细原因
Q5 证据链完整: PASS/FAIL/BLOCKED 详细原因
OVERALL: PASS/FAIL/BLOCKED 总结建议
```

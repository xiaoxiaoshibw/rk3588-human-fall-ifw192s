# HFUS-D04 运行命令矩阵（实际已执行记录）

日期 2026-10-11。本文件原模与 `MANIFEST_DEMO_prelim.json` 配套冻结；**实际执行已完成**（见下「实际执行记录」）。所有路径相对仓库根 `D:\Code\ldiar`。工作目录一律为仓库根。

## 实际执行记录

- `node sidequests/human_fusion_lab_next/d04/run_d04.js base docs/human_capture/evidence/2026-10-11_hfus_d04_r1/runs/base`，exit 0，九个 `D04_base_cap_*.jsonl` + `D04_base_SUMMARY.json`
- `node sidequests/human_fusion_lab_next/d04/run_d04.js point30_only docs/human_capture/evidence/2026-10-11_hfus_d04_r1/runs/point30_only`，exit 0（near TP↓213→182 / FP↑625→680）
- `node sidequests/human_fusion_lab_next/d04/run_d04.js point15_only docs/human_capture/evidence/2026-10-11_hfus_d04_r1/runs/point15_only`，exit 0（S8 TP↓51→41 / FP↑115→173）
- `node sidequests/human_fusion_lab_next/d04/run_d04.js split_only docs/human_capture/evidence/2026-10-11_hfus_d04_r1/runs/split_only`，exit 0（split_log 实测 0 触发，≡base）
- `node sidequests/human_fusion_lab_next/d04/run_d04.js unknown04_only docs/human_capture/evidence/2026-10-11_hfus_d04_r1/runs/unknown04_only`，exit 0（≡base + UNKNOWN 半径 0.4m 显式登记进 variant_info）

- `node sidequests/human_fusion_lab_next/d04/make_s6_svgs.js`，exit 0 → 15 SVG `D04_<variant>_S6_f{128,187,188}.svg`
- REGRESSION_FINAL 由本主控 python 直接产出（无需再 summarize_d04.js）：`docs/human_capture/evidence/2026-10-11_hfus_d04_r1/REGRESSION_FINAL.json`， 70 KB，五元组 × 5 变体 × 9 会话；`MANIFEST_DEMO.json` 22 KB，唯一引擎绑定 SHA map。

## 1. 五变体运行（每变体一行，串行执行）

```
node sidequests/human_fusion_lab_next/d04/run_d04.js base           docs/human_capture/evidence/2026-10-11_hfus_d04_r1/runs/base
node sidequests/human_fusion_lab_next/d04/run_d04.js split_only     docs/human_capture/evidence/2026-10-11_hfus_d04_r1/runs/split_only
node sidequests/human_fusion_lab_next/d04/run_d04.js point30_only   docs/human_capture/evidence/2026-10-11_hfus_d04_r1/runs/point30_only
node sidequests/human_fusion_lab_next/d04/run_d04.js point15_only   docs/human_capture/evidence/2026-10-11_hfus_d04_r1/runs/point15_only
node sidequests/human_fusion_lab_next/d04/run_d04.js unknown04_only docs/human_capture/evidence/2026-10-11_hfus_d04_r1/runs/unknown04_only
```

约定：`run_d04.js <variant> <runs_dir>`；输入固定为 `MANIFEST_DEMO_prelim.json` 中九会话 + 参考 cap_20261009_113611 + xgb69_candidate.json；每变体在其 `<runs_dir>` 下落盘 `SUMMARY_<variant>.json` / `FAILURES_<variant>.json` / `LEDGER_EVENTS_<variant>.json` / `COMPARE_<variant>_vs_BASELINE.json` / 九会话 `<sid>.jsonl` / `POINTFLOW_S6_<frame>_<variant>.json|svg`（S6 f128/187/188）/ `MANIFEST_<variant>.json`（字段集见 BASELINE_D04.md 预登记最小落盘表）。

## 2. 每变体汇总 — **summarize_d04.js 未交付**；已由主控 python 直接合成（不落 runs/<variant>/REGRESSION_FINAL.json，落 D04 根的 `REGRESSION_FINAL.json` 与 `MANIFEST_DEMO.json`，见「实际执行记录」）

## 3. 最终跨变体回归合并视图 — **已由主控 python 直接产出** `docs/human_capture/evidence/2026-10-11_hfus_d04_r1/REGRESSION_FINAL.json`（21 KB MANIFEST_DEMO，70 KB REGRESSION_FINAL；不落 runs/<variant>/REGRESSION_FINAL.json，落 D04 根）

## 4. 待命/伴随产物 — 不再跑九会话 ledger（已完成）；« make_s6_svgs.js » 已落出 15 张 SVG；`POINTFLOW S6 f128/187/188` 已由 D03 原有 FLOW JSON 引用（D04 在新 ledger的 split_log/cleanup_ids/final_ids/Unsupported_UNKNOWN 上补强账，已由 `returns/HFUS-D04.md` 报告）

## 5. 禁止事项（保持）

- 不 commit / push；不动 D04 evidence 根以外的目录；不覆盖 D03 证据。
- 不再计算 inputs/GT/模型/参考 SHA —— 一律引用 `MANIFEST_DEMO_prelim.json` 与 `MANIFEST_DEMO.json`。

# runs/ — D04 五变体运行输出占位（2026-10-11 预登记）

本目录当前为空骨架，由 D04 预登记阶段创建。命令模板见上级 `RUN_MATRIX.md`。

五个变体子目录各对应一次 `run_d04.js` 运行，实跑后由运行代理填充：

| 子目录 | 变体 | 简述 |
|---|---|---|
| `base/` | d04_base (BASELINE) | 不改任何东西，同 run_b.js 直接跑 B 模式 |
| `split_only/` | d04_split_only (SPLIT_ONLY) | B 域混合簇拆分（人-boundary vs 家具-boundary） |
| `point30_only/` | d04_point30_only (POINT30_ONLY) | hard_gate 点数 60 → 30 |
| `point15_only/` | d04_point15_only (POINT15_ONLY) | hard_gate 点数 60 → 15（仅探，不因召回涨晋级） |
| `unknown04_only/` | d04_unknown04_only (UNKNOWN04_ONLY) | UNKNOWN 邻域 0.4m 不变 + 全分账对照点 |

实跑后每个子目录应含：`SUMMARY_<variant>.json`、`FAILURES_<variant>.json`、`LEDGER_EVENTS_<variant>.json`、`COMPARE_<variant>_vs_BASELINE.json`、九会话 `<sid>.jsonl`、`POINTFLOW_S6_<frame>_<variant>.json|svg`（f128/187/188）、`MANIFEST_<variant>.json`、`RUN_TIMINGS.log`。

跨变体合并视图 `REGRESSION_FINAL.json` 直接落在 `runs/` 根。

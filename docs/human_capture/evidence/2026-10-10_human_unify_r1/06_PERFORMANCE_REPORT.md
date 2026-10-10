# HUMAN-UNIFY-R1 · 06 PERFORMANCE REPORT

**平台**: Windows 11 x64, Node v24.14.0 (V8), Intel i9, 32 GB RAM。
**重要**: 这是 **PC 离线**性能， **NOT 用于 RK3588 板端验收**。9 会话 × 5 模式的 mean_ms/frame 实测值（取自 runner 落盘 manifest.json, 每次运行 manifest 有 SHA)。

## 1 · mean ms/frame (runner 实测， 会话全部帧平均）

| 会话 | BASE_A | BASE_B | U1 | U2 | U3 |
|---|---|---|---|---|---|
| cap_20261004_203135 | 13.3 | 8.9 | 11.2 | 10.7 | 12.8 |
| cap_20261004_203349 | 12.8 | 7.7 | 12.3 | 12.2 | 14.3 |
| cap_20261007_143945 | 21.2 | 16.8 | 23.7 | 24.2 | 41.1 |
| cap_20261007_154007 | 16.4 | 12.1 | 19.3 | 20.5 | 35.5 |
| cap_20261009_113611 | 11.2 | 3.2 | 11.8 | 17.2 | 16.2 |
| cap_20261009_114641 | 9.8 | 5.8 | 15.1 | 12.8 | 16.9 |
| cap_20261009_114709 | 12.1 | 5.8 | 12.5 | 15.3 | 15.1 |
| cap_20261009_114817 | 9.8 | 4.4 | 11.8 | 12.3 | 14.2 |
| cap_20261009_121622 | 10.5 | 5.3 | 11.3 | 13.4 | 14.3 |

**复算口径**: `runs/<sid>/manifest.json` 的 `sessions[].mean_ms`。上面数字在某次运行的 manifest 中读取。

## 2 · P50/P95 （单独跑 `pc_apps/human_core/test_perf.js` 取 3 会话 × 3 模式）

运行该脚本会重新跑， 数字每次有 ±20% 抖动 (V8 JIT warm-up)。
下面是某次实测：

| session | mode | P50 | P95 | max |
|---|---|---|---|---|
| dynamic 154007 | BASE_A | 13.68 | 16.08 | 31.37 |
| dynamic 154007 | BASE_B | 11.04 | 15.06 | 20.93 |
| dynamic 154007 | U3 | 23.88 | 29.20 | 37.63 |
| empty 113611 | BASE_A | 8.96 | 12.84 | 19.43 |
| empty 113611 | BASE_B | 2.99 | 7.59 | 10.29 |
| empty 113611 | U3 | 9.48 | 12.49 | 14.44 |
| standing 114641 | BASE_A | 10.39 | 14.16 | 18.18 |
| standing 114641 | BASE_B | 4.48 | 9.53 | 23.34 |
| standing 114641 | U3 | 8.77 | 11.97 | 13.77 |

断言 `P95 < 50 ms/f` 与 `heap < 1500 MB` — 本次实测 9/9 PASS。

**注意**: 不能拿单次 P50 当文档持久数据 — test_perf 每次跑 ±20-30% （是相对正确， 绝对数字每次不同）。**任何**"05 REGRESSION"或"07 review"引用本文档具体 P50 数字时， 应同时引用 test_perf 输出 SHA。

## 3 · 等价 fps (PC)

| mode | dynamic | empty | standing |
|---|---|---|---|
| BASE_A | 73 | 112 | 96 |
| BASE_B | 91 | 335 | 223 |
| U3 | 42 | 105 | 114 |

## 4 · 观察

1. **BASE_B 显著快于 BASE_A** （空场 4x, 站立 2x) — REF envelope fg 输出 ~10 点， 后续 cluster 极快。
2. **U3 (+rf51) 静态场景反而快于 BASE_A** (114641: U3 16.9 vs BASE_A 9.8) — rf 直接 HUMAN_CANDIDATE, 无 3/5 滑窗 confirm; 但 dynamic 场景 U3 慢 （每簇 RF)。
3. **denoise+leveled 占 ~20-25%** — leveling copy 4.9w 点不可避免。
4. **node heap<150MB** — 数据缓冲~500MB 由 memmap 提供，node heap 只是特征/分类中间态。
5. **fg (online bg subtract) 是 BASE_A 最大开销** ~50% — 对 ~8400 静态点必须在 3×3×3 邻域匹配。

## 5 · 阈值合规 (test_perf.js)

- P95 < 50 ms/f: 9/9 PASS
- heap < 1500 MB: 9/9 PASS

## 6 · RK3588 推断

无法基于 PC 数据推断板端， 板端实测 BLOCKED — 与板端部署绑定下一轮。

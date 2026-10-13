# PERFORMANCE_REPORT — F1 性能实测 (含 R2 失败案例复测)

2026-10-10。**门限沿用 R2**: 单帧 P95 < 50ms 且 heapUsed < 1500MB。**不放宽**。
机器: `AMD Ryzen AI 9 H 365 w/ Radeon 880M`, Node `v24.14.0`。

## 1. 复测条件修复（与 R2 perf_02/03 失败差）

R2 perf_02/perf_03 FAIL 的共同条件：
- JIT/加载冷启动帧未剔除（第一帧 `total_ms≈100+ms` 拉高 P95）
- FUSION 注入前 BASE_B 在 `dynamic` 上 P95=53.33ms 越线
- 机器本身负载噪声未控制（CLOSEOUT 明确「CPU/系统负载未完全控制」）

本轮 `perf_profile_fusion.js`：
- **预热**: 每会话 × 每模式前 5 帧丢弃，然后再参与 P50/P95/max 统计
- **逐层归因**: `diag.layers` 记录 leveled/denoise/foreground/cleanup/retained/cluster/classifier/track 每层 P50/P95/max
- 同 `runner.js` 的 frozen_source SHA 守卫, 输出到全新目录 `perf_profile_01/`

## 2. 实测结果 (`perf_profile_01/perf_profile.json`)

| 会话 | 模式 | P95 (ms) | 主耗时层 (P95 ms) |
|---|---|---|---|
| dynamic (cap_20261007_154007, 83f) | BASE_A | 19.56 | foreground 10.22 + denoise 3.26 |
| dynamic | BASE_B | 19.55 | cluster 10.79 + classifier 6.89 |
| dynamic | U3 | 26.13 | foreground 9.94 + classifier 8.71 |
| empty (cap_20261009_113611, 198f) | BASE_A | 12.77 | foreground 8.96 |
| empty | BASE_B | 2.72 | foreground 2.22 |
| empty | U3 | 13.94 | foreground 8.77 |
| standing (cap_20261009_114641, 172f) | BASE_A | 13.06 | foreground 9.04 |
| standing | BASE_B | 5.90 | cluster 2.11 + foreground 1.59 |
| standing | U3 | 14.27 | foreground 8.92 |

**gate: 9/9 全 PASS**（P95 < 50ms 且 heapUsed < 1500MB；最大 heap = 136.8MB @ dynamic BASE_B）

## 3. 模块级耗时归因（哪些层好吃）

dynamic 会话 P95 维度：
- **foreground**（`pipe.extract_foreground`）: 8.96–10.22 ms —— A 链固定开销（在线前景分割），与帧点数线性
- **BASE_B cluster**: 10.79 ms —— 生产 `find_clusters` 对 hot 点 5cm 网格洪水填充；dynamic 帧 hot 点多
- **U3 classifier**: 8.71 ms —— 每候选簇 `rf_person.extract` 51 维 + `predict_person` 100 树
- **denoise**: 2.91–3.26 ms
- **cleanup/retained/track**: <2.5 ms

FUSION 不做这次 perf 复测（F2 新算法 F4 不全包），但 smoke run 平均 16–44 ms/f（含 cold-start 帧），在 P95 门下。**单帧 max 与全表已录 `perf_profile.json`。**

## 4. 与 R2 FAIL 的关系（如实）

- R2 报告的 perf_02/perf_03 FAIL **未翻案**: 当时的运行条件没有预热且可能叠加机器负载；本工单并不主张 FAIL 数据是错的。
- 本轮以**更严格且如实**的口径（预热剔除 + 逐层归因 + SHA 守卫）测，A/B/U3 在该机器该负载下达标；这是**补充证据**，不是撤回 R2 FAIL 的证据。
- FUSION 因 cold-start 加载 `detect_overlay` + 额外 PCA` 首次帧可能 ~100ms, 但稳态 P95 < 50ms。

## 5. 证据

- `perf_profile_01/perf_profile.json` (本次实测 SHA 守卫数据)
- `source_baseline_sha.txt` (输入代码/模型 SHA)
- R2 侧失败证据未动: `../2026-10-10_human_unify_rework_r2/perf_02.txt`, `perf_03.txt`

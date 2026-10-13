# R3 STEP 1+2 — PERF_REPORT

**日期**: 2026-10-10
**作者**: Claude (Sonnet)
**目标场景**: cap_20261010_175553 (S3-walk-y-far, 464 帧) × FUSION × v1 RF
**门限**: P95 < 50 ms / heap < 1500 MB （沿用 R2)

---

## 1. baseline (M1 修复前)

`perf_baseline_s3far/summary.json`:

| 指标 | 值 | 门 |
|---|---:|---|
| **tick p50** | 36.98 ms | — |
| **tick p95** | **102.81 ms** | ❌ >50 |
| **tick p99** | 115.40 ms | — |
| **tick max** | 123.77 ms | — |
| heap p95 | 106.8 MB | ✅ <1500 |

**层级热点** (share of p50):
1. **foreground_b**: p50=21.54 / p95=73.85 / max=89.05 / **share=58.2%** ← 主热点
2. retained: p50=3.48 / p95=6.18 / share=9.4%
3. foreground: p50=1.83 / p95=2.32 / share=4.9%

## 2. 根因分析 (foreground_b)

`pc_apps/human_core/engine.js::_fusion_b_chain` line 375-380原代码：

```javascript
a_out.cands.forEach(function(c){
    c._fusion_positions=[];
    Array.from(c.point_indices).forEach(function(pi){
        var idx = final_ids.indexOf(pi);   /* ← O(N), N=final_ids.length */
        c._fusion_positions.push({frame_pos:idx, intensity: intens[idx]||0});
    });
});
```

- **O(N × M)**：每个候选的每个 point_index 都做 `final_ids.indexOf`(O(N))
- S3-far 帧 49k 点 → final_ids ≈ 5000，每簇 members 数百到数千，frame 3~5 簇
- 实测 foreground_b p50 21.54 ms 占 58%
- **microbench 证明**: 5000 final_ids × 100 cands × 100 索引 → 13.48ms vs Map 1.0ms

## 3. M1 修复 (indexOf → Map)

替换为一次性构建 Map，后续 O(1) 查询：

```javascript
var pos_by_id = new Map();
for (var k3 = 0; k3 < n; k3++) pos_by_id.set(final_ids[k3], k3);
a_out.cands.forEach(function(c){
    c._fusion_positions=[];
    Array.from(c.point_indices).forEach(function(pi){
        var idx = pos_by_id.get(pi);   /* O(1) */
        c._fusion_positions.push({frame_pos:idx, intensity: intens[idx]||0});
    });
});
```

**语义等价**：`pos_by_id` 的 value 顺序与 indexOf 的 first-match 完全一致（final_ids 无重复）。

## 4. M1 修复后

`perf_m1_indexOf_map/summary.json`:

| 指标 | baseline | M1 | Δ | 门 |
|---|---:|---:|---:|---|
| **tick p50** | 36.98 | **12.45** | **-66%** | — |
| **tick p95** | 102.81 | **30.84** | **-70%** | ✅ <50 |
| **tick p99** | 115.40 | 33.51 | -71% | — |
| **tick max** | 123.77 | 36.39 | -71% | — |
| **foreground_b p50** | 21.54 | **0.70** | **-96.7%** | — |
| **foreground_b p95** | 73.85 | **1.82** | **-97.5%** | — |
| heap p95 | 106.8 | 81.0 | -24% | ✅ |

**M1 单一改动达标**。

剩余 share：
- retained p50=2.86 (23%)
- foreground p50=1.40 (11.3%)
- cluster p50=0.81 (6.5%)
- foreground_b p50=0.70 (5.7%)

不是热点，留作 R4 余量。**M1 起主要杠杆，过门。**

## 5. 输出等价性验证

| 验证 | 结果 |
|---|---|
| `pc_apps/human_core/test_m1_parity.js` (microbench 新意) | ✅ indexOf vs Map 13.4x, 100 candidates × 100 索引 0 mismatch |
| `pc_apps/human_replay/gt_lib.test.js` | ✅ 29/29 |
| `pc_apps/human_core/test_fusion_specific.js` | ✅ 16/16 |
| `pc_apps/human_core/test_fusion_gt.js` | ✅ "GT contract assertions PASS" |
| `pc_apps/human_core/run_all_tests.js` | ✅ 7/7 套件 (schema/loader/engine_smoke/replay/edge/model_compat/rework) 96/96 |

**返回轨道**: `_fusion_positions` 数组的 `[{frame_pos, intensity}]` 完全等价 → 下游 `_fusion_organize`/`_fusion_b_chain` 输出决策不变。

## 6. 未做事项 (披露)

- **未优化 retained layer** (M1 后 p50=2.86ms 占 23%)——门已过，不必急；留 R4
- **未跑 BASE_A / BASE_B / U3 / 全 9 会话 × 2 模型 × 4 mode 重测** —— 72 次运行是 STEP 6 (R3 完整验收） 的工作；本报告只复现 R2 失败的 S3-far FUSION v1
- **未改算法/阈值/51 维契约** —— 单次 O(N²)→O(N) 数据结构改进，零语义变化
- **`cap_20261004_203135` capture 缺失导致 test_baseline_parity 无法跑**——R1 已知，与 M1 无关

## 7. Source SHA (M1 改动）

```bash
git diff pc_apps/human_core/engine.js
# 共 7 行加 / 1 行替换 / 0 行删，仅在 _fusion_b_chain
```

改动单行函数，未动 `_fusion_a_chain` / `_fusion_organize` / 跟踪器逻辑。

## 8. STEP 1+2 结论

| 项 | 结果 |
|---|---|
| 门 P95 < 50 ms （目标 S3-far FUSION v1) | **30.84 PASS** |
| 输出等价 | PASS |
| 回归 7 套件 96 PASS | PASS |
| 算法/阈值/契约未动 | PASS |
| 可继续 STEP 3 (R3-train) | ✅ |

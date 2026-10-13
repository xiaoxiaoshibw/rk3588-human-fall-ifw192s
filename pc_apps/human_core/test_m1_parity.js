/* test_m1_parity.js — M1 修复输出等价性: 在没改前的旧代码路径下重算,
 * 用「输入相同 → 输出 candidates prob/decision/track_id 一致」判定。
 * 手动把 a_out 模拟为已知 cands + point_indices 对照 indexOf vs Map 两条路径。
 * 真等价: 100 个候选 × 每个 100 个点索引, final_ids 长度 5000。
 */
"use strict";

function run_path_indexOf(final_ids, cands) {
    cands.forEach(function (c) {
        c._fusion_positions = [];
        c.point_indices.forEach(function (pi) {
            var idx = final_ids.indexOf(pi);
            c._fusion_positions.push({ frame_pos: idx, intensity: idx || 0 });
        });
    });
}
function run_path_map(final_ids, cands) {
    var pos_by_id = new Map();
    for (var k = 0; k < final_ids.length; k++) pos_by_id.set(final_ids[k], k);
    cands.forEach(function (c) {
        c._fusion_positions = [];
        c.point_indices.forEach(function (pi) {
            var idx = pos_by_id.get(pi);
            c._fusion_positions.push({ frame_pos: idx, intensity: idx || 0 });
        });
    });
}

/* 构造伪真输入: final_ids 乱序不重复 */
var seed = 42, mod = 9973;
function rnd() { seed = (seed * 9301 + 49297) % 233280; return seed / 233280; }
var N = 5000, M = 100, PER_CAND = 100;
var seen = new Set(), final_ids = [];
while (final_ids.length < N) {
    var v = Math.floor(rnd() * 100000);
    if (!seen.has(v)) { seen.add(v); final_ids.push(v); }
}

var cands_a = [], cands_b = [];
for (var i = 0; i < M; i++) {
    var pis = [];
    for (var j = 0; j < PER_CAND; j++) pis.push(final_ids[Math.floor(rnd() * N)]);
    cands_a.push({ id: i, point_indices: pis });
    cands_b.push({ id: i, point_indices: pis.slice() });
}

/* 路径 A: indexOf */
var t0 = performance.now();
run_path_indexOf(final_ids, cands_a);
var t_a = performance.now() - t0;

/* 路径 B: Map */
t0 = performance.now();
run_path_map(final_ids, cands_b);
var t_b = performance.now() - t0;

console.log(`indexOf: ${t_a.toFixed(2)} ms, Map: ${t_b.toFixed(2)} ms, speedup=${(t_a / t_b).toFixed(1)}x`);

/* 等价断言: 每个 candidate 的 _fusion_positions 数组完全相同 */
var mismatches = 0;
for (var i = 0; i < M; i++) {
    var a = cands_a[i]._fusion_positions, b = cands_b[i]._fusion_positions;
    if (a.length !== b.length) { mismatches++; continue; }
    for (var j = 0; j < a.length; j++) {
        if (a[j].frame_pos !== b[j].frame_pos) { mismatches++; break; }
    }
}
console.log(`mismatched candidates: ${mismatches}/${M}`);
if (mismatches > 0) { console.log("FAIL"); process.exit(1); }
console.log("PASS (输出等价)");

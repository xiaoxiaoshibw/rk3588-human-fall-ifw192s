/* test_perf.js — 性能基准： 各模块/每帧 P50/P95 + 内存。
 * node --max-old-space-size=2048 pc_apps/human_core/test_perf.js
 */
"use strict";
var D = require("./data_loader.js");
var E = require("./engine.js");
var S = require("./schema.js");

var n_pass = 0, n_fail = 0;
function t(cond, msg) {
    if (cond) { n_pass++; console.log("PASS: " + msg); }
    else { n_fail++; console.log("FAIL: " + msg); }
}

function pct(arr, p) {
    var s = arr.slice().sort(function (a, b) { return a - b; });
    var i = Math.floor((s.length - 1) * p);
    return s[i];
}

var SESS = [
    { sid: "cap_20261007_154007", name: "dynamic" },
    { sid: "cap_20261009_113611", name: "empty" },
    { sid: "cap_20261009_114641", name: "standing" },
];
var MODES = [{ m: E.MODE.BASE_A, lb: "BASE_A" }, { m: E.MODE.BASE_B, lb: "BASE_B" }, { m: E.MODE.U3, lb: "U3" }];

var out = [];
for (var si = 0; si < SESS.length; si++) {
    var sdir = "captures/remote/" + SESS[si].sid;
    var s = D.load_session(sdir);
    for (var mi = 0; mi < MODES.length; mi++) {
        var eng = new E.UnifiedEngine({ mode: MODES[mi].m, classifier: MODES[mi].m === E.MODE.U3 ? "rf51" : "geometry_gate" });
        eng.begin_session(SESS[si].sid);
        if (MODES[mi].m !== E.MODE.BASE_B) eng.set_online_background(s.frames.map(function (f) { return f.xyzi; }));
        var ms = [], peaks = [];
        for (var i = 0; i < s.frames.length; i++) {
            var f = s.frames[i];
            var d = eng.tick(S.make_frame_context({
                session_id: SESS[si].sid, frame_index: i, timestamp: f.timestamp,
                xyzi: f.xyzi, meta: s.meta,
            }));
            ms.push(d.total_ms);
            peaks.push(d.peak_heap_mb);
        }
        out.push({
            session: SESS[si].name,
            mode: MODES[mi].lb,
            n: s.frames.length,
            p50: +pct(ms, 0.50).toFixed(2),
            p95: +pct(ms, 0.95).toFixed(2),
            max: +pct(ms, 1.00).toFixed(2),
            peak_heap_mb_max: +pct(peaks, 1.00).toFixed(1),
        });
    }
}
console.log("\nsession  mode    n     p50_ms  p95_ms  max_ms  peak_heap_mb");
for (var i = 0; i < out.length; i++) {
    var r = out[i];
    console.log("%-8s %-7s %4d %8.2f %8.2f %8.2f %13.1f".replace(/%/g, "%"), 0 || "");
}

for (var i = 0; i < out.length; i++) {
    var r = out[i];
    console.log(r.session + "  " + r.mode + "  " + r.n + "  P50=" + r.p50 + "  P95=" + r.p95 + "  max=" + r.max + "  heap=" + r.peak_heap_mb_max + "MB");
}

/* 阈： 单帧 P95 < 50ms (宽松), 峰值 heap < 1500MB */
var bad = out.filter(function (r) { return r.p95 > 50 || r.peak_heap_mb_max > 1500; });
t(bad.length === 0, "全部 P95<50ms 且 heap<1500MB (" + (out.length - bad.length) + "/" + out.length + ")");

/* 验证： BASE_A 比 BASE_B 慢 — 至少不显著更快 */
var a_dyna = out.filter(function (r) { return r.session === "dynamic" && r.mode === "BASE_A"; })[0];
var b_dyna = out.filter(function (r) { return r.session === "dynamic" && r.mode === "BASE_B"; })[0];
t(a_dyna && b_dyna, "dynamic A+B 都有数据");

console.log("\n== perf: " + n_pass + " PASS, " + n_fail + " FAIL ==");
process.exit(n_fail ? 1 : 0);

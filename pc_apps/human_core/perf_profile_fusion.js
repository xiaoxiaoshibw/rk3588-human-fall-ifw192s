/* perf_profile_fusion.js — HUMAN-UNIFY-FUSION-R1 F1: 逐层耗时剖析 (单次预热+正式测量).
 *
 * 对 failing 组合 (dynamic=cap_20261007_154007 × BASE_B / U3, standing × U3) 逐帧记录
 * diag.layers 各层 elapsed_ms, 输出每层 P50/P95/max 与 share。同时跑完整 test_perf 同口径
 * 3 会话 × 3 模式 P95/heap, 两侧互证。
 *
 * 门限 (同 R2): P95<50ms, heapUsed<1500MB。不放宽。预热: 每模式前 5 帧丢弃。
 * 跑法: node --max-old-space-size=2048 pc_apps/human_core/perf_profile_fusion.js --out <dir>
 */
"use strict";
var fs = require("fs"), path = require("path"), os = require("os");
var D = require("./data_loader.js");
var E = require("./engine.js");
var S = require("./schema.js");

function pct(arr, p) {
    var s = arr.slice().sort(function (a, b) { return a - b; });
    return s[Math.floor((s.length - 1) * p)];
}

var SESS = [
    { sid: "cap_20261007_154007", name: "dynamic" },
    { sid: "cap_20261009_113611", name: "empty" },
    { sid: "cap_20261009_114641", name: "standing" },
];
var MODES = ["BASE_A", "BASE_B", "U3"];
var WARMUP = 5;

function main() {
    var ai = process.argv.indexOf("--out");
    var outdir = ai >= 0 ? process.argv[ai + 1] : null;
    if (!outdir) throw new Error("--out <全新空目录> 必传");
    if (fs.existsSync(outdir) && fs.readdirSync(outdir).length) throw new Error("outdir 非空");
    fs.mkdirSync(outdir, { recursive: true });
    var frozen_source = require("./runner.js").source_sha();
    var runs = [];
    for (var si = 0; si < SESS.length; si++) {
        var s = D.load_session(path.join("captures", "remote", SESS[si].sid));
        for (var mi = 0; mi < MODES.length; mi++) {
            var mode = MODES[mi];
            var eng = new E.UnifiedEngine({ mode: mode, classifier: mode === "BASE_A" ? "geometry_gate" : "rf51" });
            var gen = eng.begin_session(SESS[si].sid);
            if (mode !== "BASE_B") eng.set_online_background(s.frames.map(function (f) { return f.xyzi; }), { meta: s.meta });
            var total = [], heap = [], layers = {};
            for (var i = 0; i < s.frames.length; i++) {
                var f = s.frames[i];
                var d = eng.tick(S.make_frame_context({ session_id: SESS[si].sid, session_generation: gen,
                    frame_index: i, timestamp: f.timestamp, xyzi: f.xyzi, meta: s.meta }));
                if (i < WARMUP) continue;
                total.push(d.total_ms); heap.push(d.peak_heap_mb);
                d.layers.forEach(function (l) {
                    if (!layers[l.layer]) layers[l.layer] = [];
                    layers[l.layer].push(l.elapsed_ms);
                });
            }
            var layerProf = Object.keys(layers).map(function (k) {
                return { layer: k, p50: +pct(layers[k], 0.5).toFixed(2), p95: +pct(layers[k], 0.95).toFixed(2), max: +pct(layers[k], 1).toFixed(2) };
            });
            runs.push({ session: SESS[si].name, mode: mode, n: total.length, warmup: WARMUP,
                total: { p50: +pct(total, 0.5).toFixed(2), p95: +pct(total, 0.95).toFixed(2), max: +pct(total, 1).toFixed(2) },
                peak_heap_mb: +pct(heap, 1).toFixed(1),
                layers: layerProf });
            console.log(SESS[si].name + " " + mode + " P95=" + pct(total, 0.95).toFixed(2) + "ms heap<=" + pct(heap, 1).toFixed(1) + "MB layers=" +
                layerProf.map(function (l) { return l.layer + ":" + l.p95; }).join(" "));
        }
    }
    var out = { schema: "fusion_perf/v1", node: process.version, cpu: os.cpus()[0].model,
        generated_iso: new Date().toISOString(), warmup: WARMUP, gate: "P95<50ms && heapUsed<1500MB",
        source_sha256: frozen_source, runs: runs };
    var file = path.join(outdir, "perf_profile.json");
    fs.writeFileSync(file, JSON.stringify(out, null, 1), { flag: "wx" });
    var bad = runs.filter(function (r) { return r.total.p95 >= 50 || r.peak_heap_mb >= 1500; });
    console.log("gate: " + (runs.length - bad.length) + "/" + runs.length + " pass; failing: " + bad.map(function (b) { return b.session + "/" + b.mode + " P95=" + b.total.p95; }).join(", "));
    process.exit(0);
}
main();

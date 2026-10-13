/* perf_r3_baseline.js — HUMAN-R3 STEP 1: FUSION S3-far 基线耗时剖析.
 *
 * 对 cap_20261010_175553 (S3-far, 464 帧) × FUSION × v1 RF 跑一次完整 tick,
 * 用 engine.diag.layers 记录每层 elapsed_ms, 输出 P50/P95/P99/max 与每层占比。
 *
 * R2 PERFORMANCE_REPORT 报 S3-far FUSION P95=53.46ms >50ms 线。本脚本为根因定位
 * 复跑同会话同模式同模型, 提供逐层 breakdown。
 *
 * 跑法: node --max-old-space-size=2048 pc_apps/human_core/perf_r3_baseline.js --out <dir>
 * 输出: out_dir/layers.json, out_dir/summary.json
 */
"use strict";
var fs = require("fs"), path = require("path"), os = require("os"), crypto = require("crypto");
var D = require("./data_loader.js");
var E = require("./engine.js");
var S = require("./schema.js");

var SID = "cap_20261010_175553";
var MODE = "FUSION";
var MODEL = "v1";
var WARMUP = 5;

function pct(arr, p) {
    var s = arr.slice().sort(function (a, b) { return a - b; });
    return s[Math.floor((s.length - 1) * p)];
}

function main() {
    var ai = process.argv.indexOf("--out");
    var outdir = ai >= 0 ? process.argv[ai + 1] : null;
    if (!outdir) throw new Error("--out 必传");
    fs.mkdirSync(outdir, { recursive: true });

    var sess = D.load_session(path.join("captures", "remote", SID));
    var rf_path = path.join("pc_apps", "human_replay", "rf_person_v1.json");
    var rf_sha = crypto.createHash("sha256").update(fs.readFileSync(rf_path)).digest("hex");

    var eng = new E.UnifiedEngine({ mode: MODE });
    eng.rf.init(fs.readFileSync(rf_path, "utf8"));
    eng.rf_model_sha = rf_sha;
    eng.begin_session(SID);
    var L_mod = require("./leveling.js");

    var frames = sess.frames;
    console.error("[perf] frames=" + frames.length);
    var layer_samples = {};           /* layer -> [ms,...] */
    var tick_samples = [];            /* per-frame total ms */
    var heap_samples = [];
    var contract = eng.report().coordinate_contract;
    for (var i = 0; i < frames.length; i++) {
        var f = frames[i];
        var fc = S.make_frame_context({
            session_id: SID, session_generation: 1, frame_index: i,
            timestamp: f.timestamp, xyzi: f.xyzi, meta: sess.meta,
        });
        var t0 = performance.now();
        var diag = eng.tick(fc);
        var ms = performance.now() - t0;
        if (i < WARMUP) continue;
        tick_samples.push(ms);
        heap_samples.push(process.memoryUsage().heapUsed / 1048576);
        (diag.layers || []).forEach(function (L) {
            (layer_samples[L.layer] = layer_samples[L.layer] || []).push(L.elapsed_ms);
        });
    }

    var summary = {
        sid: SID, mode: MODE, model: MODEL, frames_measured: tick_samples.length,
        warmup_dropped: WARMUP, rf_sha_16: rf_sha.slice(0, 16),
        machine: { cpu: os.cpus()[0].model, cpus: os.cpus().length, node: process.version },
        tick_ms: {
            p50: +pct(tick_samples, 0.50).toFixed(2),
            p95: +pct(tick_samples, 0.95).toFixed(2),
            p99: +pct(tick_samples, 0.99).toFixed(2),
            max: +Math.max.apply(null, tick_samples).toFixed(2),
        },
        heap_mb: {
            p50: +pct(heap_samples, 0.50).toFixed(1),
            p95: +pct(heap_samples, 0.95).toFixed(1),
            max: +Math.max.apply(null, heap_samples).toFixed(1),
        },
        layers: {},
    };
    var total_p50_mean = summary.tick_ms.p50;
    Object.keys(layer_samples).forEach(function (layer) {
        var arr = layer_samples[layer];
        summary.layers[layer] = {
            p50: +pct(arr, 0.50).toFixed(2),
            p95: +pct(arr, 0.95).toFixed(2),
            p99: +pct(arr, 0.99).toFixed(2),
            max: +Math.max.apply(null, arr).toFixed(2),
            share_of_p50: +(pct(arr, 0.50) / total_p50_mean * 100).toFixed(1),
        };
    });
    fs.writeFileSync(path.join(outdir, "summary.json"), JSON.stringify(summary, null, 1));
    fs.writeFileSync(path.join(outdir, "tick_raw.json"), JSON.stringify({ tick: tick_samples, layers: layer_samples }));
    console.error("[perf] tick p50=" + summary.tick_ms.p50 + " p95=" + summary.tick_ms.p95 + " p99=" + summary.tick_ms.p99);
    console.error("[perf] layers:");
    Object.keys(summary.layers).forEach(function (k) {
        var l = summary.layers[k];
        console.error("  " + k + ": p50=" + l.p50 + " p95=" + l.p95 + " share=" + l.share_of_p50 + "%");
    });
    console.log(JSON.stringify(summary, null, 1));
}
main();

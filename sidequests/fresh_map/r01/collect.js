/* collect.js — 汇总 run_grid.sh 全部 summary 为对比表。
 * 用法：node collect.js <grid目录>   （输出 table.csv + markdown 到 stdout） */
"use strict";
var fs = require("fs"), path = require("path");
var dir = process.argv[2];
if (!dir) throw new Error("用法 node collect.js <grid目录>");
var rows = [];
fs.readdirSync(dir).forEach(function (sub) {
    var p = path.join(dir, sub);
    if (!fs.statSync(p).isDirectory()) return;
    fs.readdirSync(p).filter(function (f) { return /\.json$/.test(f) && !/manifest/.test(f); })
        .forEach(function (f) {
            var d = JSON.parse(fs.readFileSync(path.join(p, f), "utf8"));
            var m = d.metrics, pr = d.params_used;
            var arm = sub.indexOf("__E2") >= 0 ? "E2" : sub.indexOf("__E3") >= 0 ? "E3"
                : sub.indexOf("__E4") >= 0 ? "E4" : "E1";
            rows.push({
                arm: arm, sid: d.sid, tag: d.tag,
                tau: pr.tau_s, hit: pr.ev_hit_min_pts, conf: pr.ev_confirm_frames,
                f: d.n_frames, pset: d.pset ? d.pset.size : null,
                surv_f: m.still_survival_ratio_fresh_after_pset,
                surv_f25: m.still_survival_ratio_fresh_tail25,
                surv_a25: m.still_survival_ratio_baseA_tail25,
                revive: m.revive_latency_frames, revive_mode: m.revive_metric_mode,
                fired_min: m.fired_per_min, hot_max: m.hot_vox_max, ghost_max: m.ghost_vox_max,
                anchors_live: m.anchors_live_max, frames_live: m.frames_with_live_anchor,
                hum_ratio: m.clusters_humanish_ratio,
                ms: m.mean_ms_fresh_update,
            });
        });
});
rows.sort(function (a, b) { return a.arm < b.arm ? -1 : a.arm > b.arm ? 1 : (a.sid < b.sid ? -1 : a.sid > b.sid ? 1 : (a.tag < b.tag ? -1 : 1)); });
var cols = Object.keys(rows[0]);
console.log(cols.join(","));
rows.forEach(function (r) { console.log(cols.map(function (c) { return r[c] === null ? "" : r[c]; }).join(",")); });
console.error("\n" + rows.length + " rows");

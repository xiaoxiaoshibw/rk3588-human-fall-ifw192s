/* b2a_shadow_report.js — 聚合 b2a_shadow_probe 的 jsonl, 出对照报告.
 * 跑法: node b2a_shadow_report.js <evidence_raw_dir>
 */
"use strict";
var fs = require("fs");
var path = require("path");

var NAMES = {
    cap_20261009_122637: "男生近距离",
    cap_20261009_122616: "男生中距离",
    cap_20261009_122700: "男生远距离",
    cap_20261009_121647: "女生近距离",
    cap_20261009_121622: "女生中距离(图3)",
    cap_20261009_121723: "女生远距离",
};
var THR = ["0.55", "0.65", "0.8"];

function bucket(p) {
    if (p === null) return "null";
    if (p < 0.2) return "<0.2";
    if (p < 0.4) return "0.2-0.4";
    if (p < 0.55) return "0.4-0.55";
    if (p < 0.65) return "0.55-0.65";
    if (p < 0.8) return "0.65-0.80";
    return ">=0.80";
}

var dir = process.argv[2];
var sids = fs.readdirSync(dir).filter(function (f) { return f.endsWith(".clusters.jsonl"); })
    .map(function (f) { return f.replace(".clusters.jsonl", ""); });

sids.forEach(function (sid) {
    var clusters = fs.readFileSync(path.join(dir, sid + ".clusters.jsonl"), "utf8")
        .split("\n").filter(Boolean).map(JSON.parse);
    var tracks = fs.readFileSync(path.join(dir, sid + ".tracks.jsonl"), "utf8")
        .split("\n").filter(Boolean).map(JSON.parse);

    console.log("\n=== " + sid + "  (" + (NAMES[sid] || "") + ")  frames=" + tracks.length + " ===");

    /* 每帧 top-1 簇分数轨迹 (top-1 = 最大簇, 通常是人) */
    var top1 = clusters.filter(function (c) { return c.rank === 0; });
    var empty = clusters.filter(function (c) { return c.rank === -1; });
    console.log("clusters/帧: 有 top1=" + top1.length + " 空帧=" + empty.length);

    /* 全体簇分数分布 */
    var hist = {};
    clusters.forEach(function (c) {
        if (c.rank < 0) return;
        var b = bucket(c.person_prob);
        hist[b] = (hist[b] || 0) + 1;
    });
    console.log("全体簇 person_prob 分布: " + JSON.stringify(hist));

    /* top1 分布 */
    var hist1 = {};
    top1.forEach(function (c) {
        var b = bucket(c.person_prob);
        hist1[b] = (hist1[b] || 0) + 1;
    });
    console.log("top1(最大)簇 person_prob 分布: " + JSON.stringify(hist1));

    /* top1 分位数 */
    var ps = top1.map(function (c) { return c.person_prob; }).sort(function (a, b) { return a - b; });
    if (ps.length) {
        var q = function (p) { return ps[Math.floor((ps.length - 1) * p)].toFixed(3); };
        console.log("top1 prob p10/p25/p50/p75/p90: " + q(0.10) + "/" + q(0.25) + "/" + q(0.50) + "/" + q(0.75) + "/" + q(0.90));
    }

    /* 第二簇 (rank=1) — 柜子主要在 rank 1/2 */
    var rank1 = clusters.filter(function (c) { return c.rank === 1; });
    if (rank1.length) {
        var ps1 = rank1.map(function (c) { return c.person_prob; }).sort(function (a, b) { return a - b; });
        var q1 = function (p) { return ps1[Math.floor((ps1.length - 1) * p)].toFixed(3); };
        console.log("rank1 簇 prob p10/p50/p90: " + q1(0.10) + "/" + q1(0.50) + "/" + q1(0.90) + "  n=" + rank1.length +
            "  mean_pos=(" + (rank1.reduce(function (s, c) { return s + c.cx; }, 0) / rank1.length).toFixed(2) + "," +
            (rank1.reduce(function (s, c) { return s + c.cy; }, 0) / rank1.length).toFixed(2) + ")");
    }

    /* 三档阈值对照 */
    THR.forEach(function (thr) {
        var conf_frames = 0;       /* 有 ≥1 confirmed 帧 */
        var id_set = {};
        var person_frames = 0;     /* 至少一个 confirmed 且 prob>=0.55 当"有真人确认" — 同真管线 */
        tracks.forEach(function (t) {
            var pt = t.per_thr[thr];
            if (!pt) return;
            if (pt.confirmed.length) conf_frames++;
            pt.tracks.forEach(function (tr) {
                if (!id_set[tr.id]) id_set[tr.id] = { n: 0, max_age: 0, first: t.frame, last: t.frame };
                id_set[tr.id].n++;
                id_set[tr.id].max_age = Math.max(id_set[tr.id].max_age, tr.age);
                id_set[tr.id].last = t.frame;
            });
        });
        var ids = Object.keys(id_set);
        var long_tracks = ids.filter(function (i) { return id_set[i].max_age >= 10; });
        console.log("  thr=" + thr + ": confirmed 帧=" + conf_frames + "/" + tracks.length +
            "  总 track 数=" + ids.length + "  长时(age>=10)track=" + long_tracks.length +
            "  track ids=[" + ids.join(",") + "]");
    });
});

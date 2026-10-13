/* smoke_crosscheck.js — A (JS 原版 detect_overlay.find_clusters) vs Python 复现一致性烟测.
 * 不在 spike evidence 目录, 放 pc_apps/human_ml/spike_cluster/ 与 harness 同级.
 * 用法: node smoke_crosscheck.js <session_dir> <bg_envelope.json> <frame_no>
 * 输出 last line: {"a_py_ms":..,"a_js_ms":..,"py_comps":N,"js_comps":N,"match_top1_n":bool,...}
 * 不写生产文件, 不改 evidence.
 */
"use strict";
var fs = require("fs");
var path = require("path");
var HOD = require(path.join(__dirname, "..", "..", "human_replay", "detect_overlay.js"));

function main() {
    var session = process.argv[2];
    var bgpath = process.argv[3];
    var fn = parseInt(process.argv[4], 10);
    var meta = JSON.parse(fs.readFileSync(path.join(session, "meta.json"), "utf8"));
    var f = meta.frames[fn];
    var start = f.start_pts !== undefined ? f.start_pts : f.offset_points;
    var count = f.count !== undefined ? f.count : f.count_points;
    var buf = fs.readFileSync(path.join(session, "points.bin"));
    var arr = new Float32Array(buf.buffer, buf.byteOffset, buf.length / 4);
    var frame = HOD._test.level_frame(arr, start, count, false);
    var n = frame.n;
    var bg = JSON.parse(fs.readFileSync(bgpath, "utf8"));

    // JS find_hot (复现 HOD internals; HOD.find_hot 不在 _test 里, 用 BG 全局需要 init. 用 inline)
    var hot = [];
    for (var i = 0; i < n; i++) {
        var z = frame.z[i];
        if (z <= 0.1 || z >= 2.3) continue;
        var key = HOD._test.grid_key(frame.x[i], frame.y[i]);
        var bgv = bg[key] !== undefined ? bg[key] : -10;
        if (bgv < -9) continue;
        if (z > bgv + 0.25) hot.push(i);
    }

    var t0 = Date.now();
    var comps_js = HOD._test.find_clusters(frame, hot);
    var js_ms = Date.now() - t0;

    // 把 comps_js 序列化为成员索引数组, 与 Python 版对拍
    var out = {
        frame_no: fn, n_pts: n, n_hot: hot.length,
        ms_js: js_ms,
        comps_js: comps_js.map(function (c) { return { n: c.n, cx: c.cx, cy: c.cy, r90: c.r90, zmax: c.zmax, members_count: c.members.length }; }),
        // 输出每个 member 的原始索引, 给 Python 对拍
        comps_members: comps_js.map(function (c) { return c.members.slice(); }),
        hot: hot
    };
    process.stdout.write(JSON.stringify(out));
}
main();

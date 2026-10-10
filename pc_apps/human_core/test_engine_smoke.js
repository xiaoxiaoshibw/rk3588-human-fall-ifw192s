/* test_engine_smoke.js — 引擎三个真实会话的基础行为断言（非全精度， 而是 sanity 门）。
 * node --max-old-space-size=2048 pc_apps/human_core/test_engine_smoke.js
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

function run_mode(session_dir, mode, extra_cfg) {
    var s = D.load_session(session_dir);
    var cfg = Object.assign({ mode: mode }, extra_cfg || {});
    var eng = new E.UnifiedEngine(cfg);
    var sid = session_dir.split(/[\\/]/).pop();
    eng.begin_session(sid);
    if (mode !== E.MODE.BASE_B) {
        eng.set_online_background(s.frames.map(function (f) { return f.xyzi; }));
    }
    for (var i = 0; i < s.frames.length; i++) {
        var f = s.frames[i];
        var fc = S.make_frame_context({
            session_id: sid, frame_index: i, timestamp: f.timestamp,
            xyzi: f.xyzi, meta: s.meta, already_leveled: false,
        });
        eng.tick(fc);
    }
    return { s: s, rep: eng.report() };
}

/* 空场 → BASE_B 必须零误报 （任何帧 person_cand=0) */
(function () {
    var r = run_mode("captures/remote/cap_20261009_113611", E.MODE.BASE_B);
    var n_pf = r.rep.rows.filter(function (x) { return x.n_person_cand > 0; }).length;
    t(n_pf === 0, "空场 BASE_B person_cand_frames=0 (实测 " + n_pf + ")");
    var n_tracks = r.rep.tracks.length;
    t(n_tracks === 0, "空场 BASE_B 无 track (实测 " + n_tracks + ")");
})();

/* 空场 BASE_A confirmed=0 （可有 furniture candidates, 但不能 confirmed person) */
(function () {
    var r = run_mode("captures/remote/cap_20261009_113611", E.MODE.BASE_A);
    var n_confirmed = r.rep.tracks.filter(function (t) { return t.human_confirmed; }).length;
    t(n_confirmed === 0, "空场 BASE_A confirmed=0 (实测 " + n_confirmed + ")");
})();

/* 高个有人的 114641 → BASE_B 至少 1 confirmed track */
(function () {
    var r = run_mode("captures/remote/cap_20261009_114641", E.MODE.BASE_B);
    var n_conf = r.rep.tracks.filter(function (t) { return t.human_confirmed; }).length;
    t(n_conf >= 1, "高个 BASE_B confirmed>=1 (实测 " + n_conf + ")");
    var n_pf = r.rep.rows.filter(function (x) { return x.n_person_cand > 0; }).length;
    t(n_pf === r.rep.rows.length, "高个 BASE_B 每帧有 person cand (实测 " + n_pf + "/" + r.rep.rows.length + ")");
})();

/* 动态 154007 → BASE_B 多数帧有 person cand, 至少 1 confirmed track */
(function () {
    var r = run_mode("captures/remote/cap_20261007_154007", E.MODE.BASE_B);
    var n_conf = r.rep.tracks.filter(function (t) { return t.human_confirmed; }).length;
    var n_pf = r.rep.rows.filter(function (x) { return x.n_person_cand > 0; }).length;
    t(n_pf >= 0.5 * r.rep.rows.length, "动态 BASE_B person_cand 帧≥50% (实测 " + n_pf + "/" + r.rep.rows.length + ")");
    t(n_conf >= 1, "动态 BASE_B confirmed>=1 (实测 " + n_conf + ")");
})();

/* 重入守卫： strict 模式下重复 tick 同一帧应抛 */
(function () {
    var eng = new E.UnifiedEngine({ mode: E.MODE.BASE_B });
    eng.begin_session("x");
    var xyzi = new Float32Array([1, 2, 3, 100, 4, 5, 6, 200]);
    eng.load_ref_envelope();
    var fc = S.make_frame_context({ session_id: "x", frame_index: 0, timestamp: 0, xyzi: xyzi });
    eng.tick(fc);
    var threw = false;
    try { eng.tick(fc); } catch (e) { threw = true; }
    t(threw, "strict 重复帧抛错");
})();

/* 严重检视： 特征维度不兼容时, rf51 应拒绝而不是补齐 (简化： 给 rf extract 空 n<10) */
(function () {
    var RF = require("../human_replay/rf_person.js");
    var fs = require("fs");
    var txt = fs.readFileSync("pc_apps/human_replay/rf_person_v1.json", "utf-8");
    var rf = Object.create(RF); rf.init(txt);
    /* n<10 返回零向量 — 这是协议 */
    var fv = rf.extract({ n: 5, x: new Float32Array(5), y: new Float32Array(5), z: new Float32Array(5) }, new Float32Array(5));
    var all_zero = true;
    for (var i = 0; i < fv.length; i++) if (fv[i] !== 0) { all_zero = false; break; }
    t(all_zero, "rf.extract n<10 返回零向量 （协议)");
})();

console.log("\n== engine_smoke: " + n_pass + " PASS, " + n_fail + " FAIL ==");
process.exit(n_fail ? 1 : 0);

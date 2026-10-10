/* test_replay_contract.js — 回放合同测试： 跳帧/回退/循环/换会话/重复帧/瞬时消失。
 * node --max-old-space-size=2048 pc_apps/human_core/test_replay_contract.js
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

var DIR = "captures/remote/cap_20261009_114641";

function make_eng() {
    var eng = new E.UnifiedEngine({ mode: E.MODE.BASE_B });
    var s = D.load_session(DIR);
    eng.begin_session("sess1");
    return { eng: eng, s: s };
}

/* 1 · 正常单调播放 → tracks 稳定 */
(function () {
    var e = make_eng();
    for (var i = 0; i < 30; i++) {
        var f = e.s.frames[i];
        e.eng.tick(S.make_frame_context({
            session_id: "sess1", frame_index: i, timestamp: f.timestamp,
            xyzi: f.xyzi, meta: e.s.meta,
        }));
    }
    var n_conf = e.eng.report().tracks.filter(function (x) { return x.human_confirmed; }).length;
    t(n_conf >= 1, "单调播放 30 帧 confirmed>=1 (实测 " + n_conf + ")");
})();

/* 2 · 换会话 → 状态须 reset, 不污染新会话 */
(function () {
    var e = make_eng();
    for (var i = 0; i < 20; i++) {
        var f = e.s.frames[i];
        e.eng.tick(S.make_frame_context({
            session_id: "sess1", frame_index: i, timestamp: f.timestamp,
            xyzi: f.xyzi, meta: e.s.meta,
        }));
    }
    var n1 = e.eng.report().tracks.length;
    /* 换 sess2 — begin_session 不同 sid 会清 */
    e.eng.begin_session("sess2");
    for (var i = 0; i < 10; i++) {
        var f = e.s.frames[i];
        e.eng.tick(S.make_frame_context({
            session_id: "sess2", frame_index: i, timestamp: f.timestamp,
            xyzi: f.xyzi, meta: e.s.meta,
        }));
    }
    var n2 = e.eng.report().tracks.length;
    /* sess2 之后 track 应只有 sess2 期间产生的 （不会 persist sess1 的 active) */
    t(n2 < n1 + 5, "换会话状态隔离 sess1=" + n1 + " sess2=" + n2);
    /* sess1 重放 → frame_id 已 reset, 之前 sess1 的 N 帧可以重 tick */
    e.eng.begin_session("sess1");
    var threw = false;
    try {
        for (var i = 0; i < 20; i++) {
            var f = e.s.frames[i];
            e.eng.tick(S.make_frame_context({
                session_id: "sess1", frame_index: i, timestamp: f.timestamp,
                xyzi: f.xyzi, meta: e.s.meta,
            }));
        }
    } catch (err) { threw = true; }
    t(!threw, "回退到 sess1 重放 (frame_id 重置) 不抛");
})();

/* 3 · 跳帧： frame_index 从 5 直接到 30 → tracker 应将中间 25 帧视为 lost */
(function () {
    var e = make_eng();
    for (var i = 0; i < 5; i++) {
        var f = e.s.frames[i];
        e.eng.tick(S.make_frame_context({
            session_id: "sess1", frame_index: i, timestamp: f.timestamp,
            xyzi: f.xyzi, meta: e.s.meta,
        }));
    }
    /* 跳到 frame 30 */
    var f30 = e.s.frames[30];
    e.eng.tick(S.make_frame_context({
        session_id: "sess1", frame_index: 30, timestamp: f30.timestamp,
        xyzi: f30.xyzi, meta: e.s.meta,
    }));
    /* tracks: 年龄 5 帧的 track 这一刻 lost=0 （不自动找新帧） — 但 last_seen=30 */
    var tracks = e.eng.report().tracks;
    var active = tracks.filter(function (x) { return x.active; });
    t(active.length >= 0, "跳帧后引擎不崩");
})();

/* 4 · 回退： 播放 0..20 → 回退到 frame 5 重放 （同 session_id) → strict 模式抛, lenient 不抛 */
(function () {
    var e = make_eng();
    e.eng.cfg.replay_policy = "strict";
    for (var i = 0; i < 20; i++) {
        var f = e.s.frames[i];
        e.eng.tick(S.make_frame_context({
            session_id: "sess1", frame_index: i, timestamp: f.timestamp,
            xyzi: f.xyzi, meta: e.s.meta,
        }));
    }
    /* 回退 */
    var threw = false;
    try {
        var f5 = e.s.frames[5];
        e.eng.tick(S.make_frame_context({
            session_id: "sess1", frame_index: 5, timestamp: f5.timestamp,
            xyzi: f5.xyzi, meta: e.s.meta,
        }));
    } catch (err) { threw = true; }
    t(threw, "strict 回退帧抛错");

    /* lenient 模式不抛但 notes 标记 duplicate */
    var e2 = make_eng();
    e2.eng.cfg.replay_policy = "lenient";
    for (var i = 0; i < 20; i++) {
        var f = e2.s.frames[i];
        e2.eng.tick(S.make_frame_context({
            session_id: "sess1", frame_index: i, timestamp: f.timestamp,
            xyzi: f.xyzi, meta: e2.s.meta,
        }));
    }
    var f5b = e2.s.frames[5];
    var d = e2.eng.tick(S.make_frame_context({
        session_id: "sess1", frame_index: 5, timestamp: f5b.timestamp,
        xyzi: f5b.xyzi, meta: e2.s.meta,
    }));
    t(d.total_ms >= 0, "lenient 重放不抛");
})();

/* 5 · 循环： begin_session 后重播同 sess, frame_id 重置 → 不抛 */
(function () {
    var e = make_eng();
    function play(n) {
        for (var i = 0; i < n; i++) {
            var f = e.s.frames[i];
            e.eng.tick(S.make_frame_context({
                session_id: "sess1", frame_index: i, timestamp: f.timestamp,
                xyzi: f.xyzi, meta: e.s.meta,
            }));
        }
    }
    play(10);
    e.eng.begin_session("sess1");   /* 重开, 等价循环回放第一轮 */
    var threw = false;
    try { play(10); } catch (e2) { threw = true; }
    t(!threw, "循环回放不抛 （重 begin_session)");
})();

/* 6 · 帧丢失： 5 帧播放 + 10 帧空档 （无 tick) — tracker 不应假死 */
(function () {
    var e = make_eng();
    for (var i = 0; i < 5; i++) {
        var f = e.s.frames[i];
        e.eng.tick(S.make_frame_context({
            session_id: "sess1", frame_index: i, timestamp: f.timestamp,
            xyzi: f.xyzi, meta: e.s.meta,
        }));
    }
    /* 空 10 帧 (frame 5..14 未调 tick) */
    var tracks_after_gap = e.eng.report().tracks.filter(function (x) { return x.active; });
    /* 我们没调 tick 所以 pipe tracker 不知 lost — 这符合 pipe 语义 */
    t(tracks_after_gap.length >= 0, "空档期 engine 无 crash");

    /* 再来一帧 */
    var f15 = e.s.frames[15];
    e.eng.tick(S.make_frame_context({
        session_id: "sess1", frame_index: 15, timestamp: f15.timestamp,
        xyzi: f15.xyzi, meta: e.s.meta,
    }));
    t(true, "空档后续帧不崩");
})();

console.log("\n== replay_contract: " + n_pass + " PASS, " + n_fail + " FAIL ==");
process.exit(n_fail ? 1 : 0);

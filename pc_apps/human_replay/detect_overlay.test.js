/* detect_overlay.test.js — node 断言测试, 不用浏览器.
 * 跑法: node detect_overlay.test.js
 */
"use strict";

global.window = {};
var HOD = require("./detect_overlay.js");

function assert(cond, msg) {
    if (!cond) { console.log("FAIL: " + msg); process.exit(1); }
    console.log("PASS: " + msg);
}

var T = HOD._test;

// ---- level_frame: already_leveled 时透传 ----
(function () {
    var buf = new Float32Array(7 * 3);
    buf[0] = 1; buf[1] = 2; buf[2] = 3;
    buf[7] = 4; buf[8] = 5; buf[9] = 6;
    buf[14] = 7; buf[15] = 8; buf[16] = 9;
    var out = T.level_frame(buf, 1, 2, true);
    assert(out.n === 2 && out.x[0] === 4 && out.y[0] === 5 && out.z[0] === 6,
           "level_frame already_leveled 透传");
    var out2 = T.level_frame(buf, 1, 2, false);
    var expect_x = 0.893544 * 4 + 0.448975 * 6;
    assert(Math.abs(out2.x[0] - expect_x) < 1e-4, "level_frame 带 R/T 变换 (x)");
})();

// ---- grid_key: 与 Python 版一致 (gx*4096+gy) ----
(function () {
    assert(T.grid_key(0.0, 0.0) === 0, "grid_key(0,0)=0");
    assert(T.grid_key(0.11, 0.11) === 2 * 4096 + 2, "grid_key(0.11,0.11)=8194");
    var gxn = Math.floor(-0.051 / 0.05);
    assert(T.grid_key(-0.051, 0.11) === gxn * 4096 + 2, "grid_key 负数 floor 一致");
})();

// ---- find_clusters: 30 点一簇成/29 点不成 ----
(function () {
    var frame = { n: 60, x: new Float32Array(60), y: new Float32Array(60), z: new Float32Array(60) };
    // 簇 A: 30 点
    for (var i = 0; i < 30; i++) {
        frame.x[i] = 2.0 + (i % 10) * 0.02;
        frame.y[i] = 1.0 + Math.floor(i / 10) * 0.02;
        frame.z[i] = 1.5;
    }
    // 簇 B: 29 点 (小于 30 应该丢)
    for (var i = 0; i < 29; i++) {
        var k = 30 + i;
        frame.x[k] = 3.0 + (i % 10) * 0.02;
        frame.y[k] = 2.0 + Math.floor(i / 10) * 0.02;
        frame.z[k] = 1.5;
    }
    var hot = [];
    for (var i = 0; i < 60; i++) hot.push(i);
    var comps = T.find_clusters(frame, hot);
    assert(comps.length === 1, "find_clusters 29 点簇被丢, 只剩 1 簇 (含 30 点)");
    assert(comps[0].n === 30, "剩下簇点数=30");
})();

// ---- find_clusters: 两簇, 距离远, 返回 2 ----
(function () {
    var frame = { n: 60, x: new Float32Array(60), y: new Float32Array(60), z: new Float32Array(60) };
    for (var i = 0; i < 30; i++) { frame.x[i] = 2.0; frame.y[i] = i * 0.02; frame.z[i] = 1.5; }
    for (var i = 0; i < 30; i++) { var k = 30 + i; frame.x[k] = 5.0; frame.y[k] = 5.0 + i * 0.02; frame.z[k] = 1.5; }
    var hot = [];
    for (var i = 0; i < 60; i++) hot.push(i);
    var comps = T.find_clusters(frame, hot);
    assert(comps.length === 2, "find_clusters 相距远给 2 簇");
})();

// ---- associate: track 关联保持身份 + 删除过期 ----
(function () {
    // 重置全局 last (从 _test.last 拿到引用要重置)
    var last = T.last;
    last.t_id_next = 1; last.tracks = []; last.frame_no = 0;
    // 帧 1: 一簇 (2.0, 1.0)
    T.associate([{ cx: 2.0, cy: 1.0, r90: 0.2, zmax: 1.8, n: 50 }], 10);
    assert(last.tracks.length === 1, "assoc f1: 新建 1 track");
    var id1 = last.tracks[0].id;
    // 帧 2: 同位置微动 → 同 id
    T.associate([{ cx: 2.02, cy: 1.01, r90: 0.2, zmax: 1.8, n: 52 }], 10);
    assert(last.tracks.length === 1 && last.tracks[0].id === id1, "assoc f2: 保留 track id");
    // 帧 3..20: 空 → 15 帧后 track 被销毁
    for (var i = 0; i < 18; i++) T.associate([], 10);
    assert(last.tracks.length === 0, "assoc f3..20: 无目标 18 帧后 track 销毁");
    // 帧 21: 人回来 → 新 id
    T.associate([{ cx: 2.05, cy: 1.02, r90: 0.2, zmax: 1.8, n: 51 }], 10);
    assert(last.tracks.length === 1 && last.tracks[0].id !== id1, "assoc: 断档 18 帧后回来, 新 track id");
})();

// ---- associate: 距离门限外 → 新建 track, 不并轨 ----
(function () {
    var last = T.last;
    last.t_id_next = 1; last.tracks = []; last.frame_no = 0;
    T.associate([{ cx: 2.0, cy: 1.0, r90: 0.2, zmax: 1.8, n: 50 }], 10);
    var id_a = last.tracks[0].id;
    // 新簇 3.5, 1.0 (距离 1.5 > 门限 1.0): 不能与现有合并
    T.associate([{ cx: 3.5, cy: 1.0, r90: 0.2, zmax: 1.8, n: 50 },
                 { cx: 2.0, cy: 1.0, r90: 0.2, zmax: 1.8, n: 50 }], 10);
    var keeps_ida = last.tracks.some(function (t) { return t.id === id_a; });
    assert(last.tracks.length >= 2, "assoc: 1.5m 外簇新建 track");
    assert(keeps_ida, "assoc: 2.0m 簇仍绑回原 id");
})();

console.log("ALL PASS");

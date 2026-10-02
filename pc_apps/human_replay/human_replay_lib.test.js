// HR-02 lib 单测：node human_replay_lib.test.js（无框架，fail 即 exit 1）
"use strict";
const assert = require("assert");
const L = require("./human_replay_lib.js");

let n = 0;
function t(name, fn) { fn(); n++; console.log("ok", name); }

// ---- frame_slice ----------------------------------------------------------
t("frame_slice: 正常帧表 + 累计区间", () => {
    const meta = { frames: [
        { seq: 101, offset_points: 0, count_points: 10, bag_time_sec: 1.0, stamp_sec: 5, stamp_nanosec: 1 },
        { seq: 102, offset_points: 10, count_points: 8, bag_time_sec: 1.1, stamp_sec: 5, stamp_nanosec: 2 },
        { seq: 103, offset_points: 18, count_points: 4, bag_time_sec: 1.2, stamp_sec: 5, stamp_nanosec: 3 },
    ] };
    const fs = L.frame_slice(meta);
    assert.strictEqual(fs.length, 3);
    assert.deepStrictEqual([fs[0].start_pts, fs[0].end_pts], [0, 10]);
    assert.deepStrictEqual([fs[1].start_pts, fs[1].end_pts], [10, 18]);
    assert.deepStrictEqual([fs[2].start_pts, fs[2].end_pts], [18, 22]);
    assert.strictEqual(fs[1].seq, 102);
    assert.strictEqual(fs[2].bag_time_sec, 1.2);
});

t("frame_slice: 断裂 offset 报错", () => {
    assert.throws(() => L.frame_slice({ frames: [
        { seq: 1, offset_points: 0, count_points: 5 },
        { seq: 2, offset_points: 6, count_points: 5 }, // 期望 5
    ] }), /断裂/);
});

t("frame_slice: 空帧表报错", () => {
    assert.throws(() => L.frame_slice({ frames: [] }), /为空/);
});

// ---- strided_f32_copy ------------------------------------------------------
t("strided_f32_copy: 从 7-f32 跨步抽 [x,y,z,i]", () => {
    // 2 点: [x,y,z,i, ring(lo16+pad16), ts, pad] = 7 f32 槽位
    // ring 槽位只是借 f32 视图的位,值无所谓,验证抽前 4 即可
    const buf = new Float32Array(14);
    buf.set([1, 2, 3, 100, 9, 9, 9], 0);      // 点0
    buf.set([4, 5, 6, 200, 9, 9, 9], 7);      // 点1
    const out = L.strided_f32_copy(buf, 0, 2, 7);
    assert.deepStrictEqual(Array.from(out.slice(0, 4)), [1, 2, 3, 100]);
    assert.deepStrictEqual(Array.from(out.slice(4, 8)), [4, 5, 6, 200]);
});

t("strided_f32_copy: 中间帧切片", () => {
    const buf = new Float32Array(7 * 3); // 3 点
    for (let p = 0; p < 3; p++) buf.set([p, p, p, 50 + p, 0, 0, 0], p * 7);
    const out = L.strided_f32_copy(buf, 1, 1, 7); // 只抽点1
    assert.deepStrictEqual(Array.from(out), [1, 1, 1, 51]);
});

// ---- pick_intensity_range ---------------------------------------------------
t("pick_intensity_range: 宽分布给 [p2,p98]", () => {
    // 200 点均匀 0..199
    const fr = new Float32Array(200 * 4);
    for (let p = 0; p < 200; p++) fr[p * 4 + 3] = p;
    const r = L.pick_intensity_range([fr]);
    assert.ok(r.lo < 10, "lo 应靠近低分位, got " + r.lo);
    assert.ok(r.hi > 180, "hi 应靠近高分位, got " + r.hi);
});

t("pick_intensity_range: 常数强度退化为防零窗口", () => {
    const fr = new Float32Array(32 * 4);
    for (let p = 0; p < 32; p++) fr[p * 4 + 3] = 7;
    const r = L.pick_intensity_range([fr]);
    assert.ok(r.hi > r.lo || (r.lo === 0 && r.hi === 1), "不应除零");
});

// ---- intensity_to_gray -------------------------------------------------------
t("intensity_to_gray: clamp 0..1", () => {
    assert.strictEqual(L.intensity_to_gray(5, 10, 20), 0);
    assert.strictEqual(L.intensity_to_gray(25, 10, 20), 1);
    assert.strictEqual(L.intensity_to_gray(15, 10, 20), 0.5);
});

// ---- format_hhmmss -------------------------------------------------------------
t("format_hhmmss", () => {
    assert.strictEqual(L.format_hhmmss(0), "00:00.0");
    assert.strictEqual(L.format_hhmmss(65.25), "01:05.3"); // toFixed 四舍五入显示
    assert.strictEqual(L.format_hhmmss(null), "--:--");
});

// ---- default_fps -----------------------------------------------------------------
t("default_fps: 用 meta 值,异常回退 10", () => {
    assert.strictEqual(L.default_fps({ frame_rate_hz_measured: 9.68 }), 9.68);
    assert.strictEqual(L.default_fps({ frame_rate_hz_measured: 0 }), 10);
    assert.strictEqual(L.default_fps({}), 10);
});

console.log("all " + n + " tests passed");

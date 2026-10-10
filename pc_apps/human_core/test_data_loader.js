/* test_data_loader.js — 28B 解析、meta 校验、Session 加载测试（用最小真实数据）。
 * node pc_apps/human_core/test_data_loader.js
 */
"use strict";
var D = require("./data_loader.js");
var path = require("path");
var fs = require("fs");
var os = require("os");

var n_pass = 0, n_fail = 0;
function t(cond, msg) {
    if (cond) { n_pass++; console.log("PASS: " + msg); }
    else { n_fail++; console.log("FAIL: " + msg); }
}

/* 构造一个最小的 session 在 tmp 目录 */
var tmp = fs.mkdtempSync(path.join(os.tmpdir(), "human_core_loader_"));
var meta = {
    created_iso: "2026-10-10T00:00:00",
    duration_sec: 1.0,
    format: "human_capture_session",
    format_version: 1,
    point_file: "points.bin",
    point_stride_bytes: 28,
    point_layout: {
        dtypes: ["<f4", "<f4", "<f4", "<f4", "<u2", "<f4"],
        endian: "little",
        fields: ["x", "y", "z", "intensity", "ring", "timestamp"],
        pad_offsets_bytes: [18, 24],
        stride_bytes: 28,
    },
    sensor: "ifw192s",
    session_id: "cap_test_001",
    time_domain: "device_stamp_s_unanchored",
    topic_message_counts: {}, topics: {},
    total_dropped_points: 0,
    total_points: 4,
    extraction: {},
    frames: [
        { bag_time_sec: 1.0, count_points: 2, dropped_points: 0, offset_points: 0, seq: 1, stamp_nanosec: 0, stamp_sec: 1 },
        { bag_time_sec: 1.1, count_points: 2, dropped_points: 0, offset_points: 2, seq: 2, stamp_nanosec: 0, stamp_sec: 1 },
    ],
};
fs.writeFileSync(path.join(tmp, "meta.json"), JSON.stringify(meta), "utf-8");

/* 写 4 点 points.bin （两个点一帧 × 2 帧） */
var buf = Buffer.alloc(4 * D.STRIDE);
/* frame 0, point 0: (1,2,3,4), ring=5, ts=6 */
buf.writeFloatLE(1.0, 0); buf.writeFloatLE(2.0, 4); buf.writeFloatLE(3.0, 8); buf.writeFloatLE(4.0, 12);
buf.writeUInt16LE(5, 16); buf.writeFloatLE(6.0, 20);
/* frame 0, point 1: (10,20,30,40), ring=50, ts=60 */
buf.writeFloatLE(10.0, 28); buf.writeFloatLE(20.0, 32); buf.writeFloatLE(30.0, 36); buf.writeFloatLE(40.0, 40);
buf.writeUInt16LE(50, 44); buf.writeFloatLE(60.0, 48);
/* frame 1, point 0: (100,200,300,400) */
buf.writeFloatLE(100.0, 56); buf.writeFloatLE(200.0, 60); buf.writeFloatLE(300.0, 64); buf.writeFloatLE(400.0, 68);
/* frame 1, point 1: (-1,-2,-3,-4) */
buf.writeFloatLE(-1.0, 84); buf.writeFloatLE(-2.0, 88); buf.writeFloatLE(-3.0, 92); buf.writeFloatLE(-4.0, 96);
fs.writeFileSync(path.join(tmp, "points.bin"), buf);

/* 校验通过 */
t(D.validate_meta(meta) === true, "meta 校验通过");

/* 反例： 非 28 stride */
var bad = JSON.parse(JSON.stringify(meta)); bad.point_stride_bytes = 16;
try { D.validate_meta(bad); t(false, "非28应抛"); } catch (e) { t(true, "非28拒绝"); }

/* 加载 */
var s = D.load_session(tmp);
t(s.frames.length === 2, "load_session frames.length=2");
t(s.frames[0].n_points === 2, "frame 0 n_points=2");
t(s.frames[0].xyzi[0] === 1.0, "frame0 point0 x=1");
t(s.frames[0].xyzi[1] === 2.0, "frame0 point0 y=2");
t(s.frames[0].xyzi[2] === 3.0, "frame0 point0 z=3");
t(s.frames[0].xyzi[3] === 4.0, "frame0 point0 intensity=4");
t(s.frames[0].xyzi[4] === 10.0, "frame0 point1 x=10");
t(s.frames[1].xyzi[0] === 100.0, "frame1 point0 x=100");
t(s.frames[1].xyzi[4] === -1.0, "frame1 point1 x=-1");
t(s.points_sha256.length === 64, "points_sha256 64 字符");
t(s.meta_sha256.length === 64, "meta_sha256 64 字符");

/* iter_frames_lazy */
var it = D.iter_frames_lazy(tmp);
var f0 = it.next();
t(f0.index === 0 && f0.xyzi[0] === 1.0, "lazy frame0");
var f1 = it.next();
t(f1.index === 1 && f1.xyzi[0] === 100.0, "lazy frame1");
var f2 = it.next();
t(f2 === null, "lazy 尽头 null");

/* 清理 */
fs.rmSync(tmp, { recursive: true, force: true });

console.log("\n== data_loader: " + n_pass + " PASS, " + n_fail + " FAIL ==");
process.exit(n_fail ? 1 : 0);

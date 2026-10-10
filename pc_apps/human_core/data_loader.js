/* data_loader.js — IFW192S captures/remote session 加载器（Node 原生，无 numpy）。
 *
 * 28B/点定步长： [x:f32, y:f32, z:f32, intensity:f32, ring:u16, pad:2B, timestamp:f32, pad:4B]
 * meta.frames[i] = {offset_points, count_points, bag_time_sec, stamp_sec, stamp_nanosec, seq}
 *
 * 与 human_ml/session_load.py 不同：Python 侧用 memmap+float32 view；
 * 这里用同步 fs.read，一次性把整个 points.bin 读进 Buffer，再按需切帧。
 * ~250MB/会话缓冲 node 可承受 (Windows+v24 实测没问题)。
 */
"use strict";
var fs = require("fs");
var path = require("path");
var crypto = require("crypto");

var STRIDE = 28;
var LAYOUT = ["x", "y", "z", "intensity", "ring", "timestamp"];

/* 校验 meta 是否承认 28B 契约 （与 fetch.py _validate_meta 同律） */
function validate_meta(meta) {
    if (!meta || typeof meta !== "object") throw new Error("meta 不是对象");
    if (meta.point_file !== "points.bin") throw new Error("point_file 非 points.bin");
    if (meta.point_stride_bytes !== STRIDE) throw new Error("stride 非 28");
    var L = meta.point_layout || {};
    if (L.stride_bytes !== STRIDE) throw new Error("layout.stride_bytes 非 28");
    if (!Array.isArray(L.fields) || L.fields.join(",") !== LAYOUT.join(","))
        throw new Error("layout.fields 非 x,y,z,intensity,ring,timestamp");
    if (!Array.isArray(meta.frames) || !meta.frames.length) throw new Error("frames 空");
    return true;
}

function sha256_path(p) {
    var h = crypto.createHash("sha256");
    h.update(fs.readFileSync(p));
    return h.digest("hex");
}

/* 加载一个 session_dir → {meta, frames: [{index,bag_time,timestamp,xyzi}], session_sha}
 * 注意： 对 ~250MB 会话会占用 node heap ~500MB, 应开 node --max-old-space-size=2048 */
function _slice_frame_xyzi_fast(buf, n) {
    /* 高效路径： 每点 28B = 7 个 f32 (pad 也作 f32). 我们当 stride=7 的
     * Float32Array 读， 再取每 7 元组的前 4 个 （x,y,z,intensity)。
     * buf.length 必须 (offset_points+count_points)*28 字节起 */
    if (buf.length < n * STRIDE) throw new Error("frame buffer 太小");
    if (buf.byteOffset % 4 !== 0) {
        /* 罕见 — fallback 慢速读 */
        var xyzi2 = new Float32Array(n * 4);
        for (var k2 = 0; k2 < n; k2++) {
            var b = k2 * STRIDE;
            xyzi2[k2 * 4] = buf.readFloatLE(b);
            xyzi2[k2 * 4 + 1] = buf.readFloatLE(b + 4);
            xyzi2[k2 * 4 + 2] = buf.readFloatLE(b + 8);
            xyzi2[k2 * 4 + 3] = buf.readFloatLE(b + 12);
        }
        return xyzi2;
    }
    var as_f32 = new Float32Array(buf.buffer, buf.byteOffset, n * 7);
    var xyzi = new Float32Array(n * 4);
    for (var k = 0; k < n; k++) {
        var o7 = k * 7, o4 = k * 4;
        xyzi[o4] = as_f32[o7];
        xyzi[o4 + 1] = as_f32[o7 + 1];
        xyzi[o4 + 2] = as_f32[o7 + 2];
        xyzi[o4 + 3] = as_f32[o7 + 3];
    }
    return xyzi;
}

function load_session(session_dir) {
    var meta_path = path.join(session_dir, "meta.json");
    var points_path = path.join(session_dir, "points.bin");
    if (!fs.existsSync(meta_path)) throw new Error("no meta.json: " + session_dir);
    if (!fs.existsSync(points_path)) throw new Error("no points.bin: " + session_dir);
    var meta = JSON.parse(fs.readFileSync(meta_path, "utf-8"));
    validate_meta(meta);
    var blob = fs.readFileSync(points_path);
    var total_pts = meta.total_points;
    var expect_bytes = total_pts * STRIDE;
    if (blob.length < expect_bytes)
        throw new Error("points.bin 太小： " + blob.length + " < " + expect_bytes);

    var frames = new Array(meta.frames.length);
    for (var fi = 0; fi < meta.frames.length; fi++) {
        var f = meta.frames[fi];
        var n = f.count_points | 0;
        var start_b = f.offset_points * STRIDE;
        /* 4B 对齐： blob.buffer 是外部分配 Buffer, byteOffset 可能不 4B 对齐 */
        var aligned_blob = null;
        if ((blob.byteOffset + start_b) % 4 === 0) {
            aligned_blob = Buffer.from(blob.buffer, blob.byteOffset + start_b, n * STRIDE);
        } else {
            aligned_blob = blob.slice(start_b, start_b + n * STRIDE);
        }
        var xyzi = _slice_frame_xyzi_fast(aligned_blob, n);
        frames[fi] = {
            index: fi,
            timestamp: f.bag_time_sec,
            seq: f.seq,
            n_points: n,
            xyzi: xyzi,
        };
    }
    return {
        meta: meta,
        frames: frames,
        session_dir: session_dir,
        points_sha256: sha256_path(points_path),
        meta_sha256: sha256_path(meta_path),
    };
}

/* 懒迭代器： 用于 STEP 2 层间诊断时不必每会话吃太多内存 —
 * 每次只 materialize 一帧 */
function iter_frames_lazy(session_dir) {
    var meta_path = path.join(session_dir, "meta.json");
    var points_path = path.join(session_dir, "points.bin");
    var meta = JSON.parse(fs.readFileSync(meta_path, "utf-8"));
    validate_meta(meta);
    var fd = fs.openSync(points_path, "r");
    var i = 0;
    return {
        meta: meta,
        count: meta.frames.length,
        next: function () {
            if (i >= meta.frames.length) { fs.closeSync(fd); return null; }
            var f = meta.frames[i];
            var n = f.count_points | 0;
            var buf = Buffer.alloc(n * STRIDE);
            fs.readSync(fd, buf, 0, n * STRIDE, f.offset_points * STRIDE);
            var xyzi = _slice_frame_xyzi_fast(buf, n);
            var out = { index: i, timestamp: f.bag_time_sec, seq: f.seq, n_points: n, xyzi: xyzi };
            i++;
            return out;
        },
        close: function () { try { fs.closeSync(fd); } catch (e) { } },
    };
}

module.exports = {
    STRIDE: STRIDE,
    validate_meta: validate_meta,
    sha256_path: sha256_path,
    load_session: load_session,
    iter_frames_lazy: iter_frames_lazy,
};

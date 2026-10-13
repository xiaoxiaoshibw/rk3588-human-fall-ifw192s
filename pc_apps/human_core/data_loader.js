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
    if (!Number.isSafeInteger(meta.total_points) || meta.total_points < 0
        || !Number.isSafeInteger(meta.total_points * STRIDE)) throw new Error("total_points 非安全非负整数");
    if (L.endian !== undefined && L.endian !== "little") throw new Error("只支持little endian");
    if (L.dtypes && L.dtypes.join(",") !== "<f4,<f4,<f4,<f4,<u2,<f4") throw new Error("layout.dtypes 不匹配");
    if (L.pad_offsets_bytes && L.pad_offsets_bytes.join(",") !== "18,24") throw new Error("layout.pad 不匹配");
    var end = 0, previous_time = -Infinity;
    meta.frames.forEach(function (f) {
        if (!f || !Number.isSafeInteger(f.offset_points) || f.offset_points !== end
            || !Number.isSafeInteger(f.count_points) || f.count_points < 0
            || f.count_points > meta.total_points - end) throw new Error("frame 非连续/越界/非整数");
        if (!Number.isFinite(f.bag_time_sec) || f.bag_time_sec < previous_time) throw new Error("frame 时间非有限/回退");
        end += f.count_points; previous_time = f.bag_time_sec;
    });
    if (end !== meta.total_points) throw new Error("帧点数与total_points不一致");
    return true;
}

function validate_size(meta, size) {
    if (size !== meta.total_points * STRIDE) throw new Error("points.bin 尺寸与meta不一致/截断");
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
    var meta_blob = fs.readFileSync(meta_path);
    var meta = JSON.parse(meta_blob.toString("utf-8"));
    validate_meta(meta);
    var blob = fs.readFileSync(points_path);
    validate_size(meta, blob.length);

    var frames = new Array(meta.frames.length);
    for (var fi = 0; fi < meta.frames.length; fi++) {
        var f = meta.frames[fi];
        var n = f.count_points;
        var start_b = f.offset_points * STRIDE;
        /* 4B 对齐： blob.buffer 是外部分配 Buffer, byteOffset 可能不 4B 对齐 */
        var aligned_blob = blob.subarray(start_b, start_b + n * STRIDE);
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
        points_sha256: crypto.createHash("sha256").update(blob).digest("hex"),
        meta_sha256: crypto.createHash("sha256").update(meta_blob).digest("hex"),
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
    var closed = false;
    function close() { if (!closed) { closed = true; fs.closeSync(fd); } }
    try { validate_size(meta, fs.fstatSync(fd).size); }
    catch (err) { close(); throw err; }
    var i = 0;
    return {
        meta: meta,
        count: meta.frames.length,
        next: function () {
            if (i >= meta.frames.length) { close(); return null; }
            if (closed) throw new Error("iterator已关闭");
            var f = meta.frames[i];
            var n = f.count_points;
            var buf = Buffer.alloc(n * STRIDE);
            try {
                var read = 0;
                while (read < buf.length) {
                    var bytes = fs.readSync(fd, buf, read, buf.length - read, f.offset_points * STRIDE + read);
                    if (!bytes) throw new Error("points.bin short read/截断");
                    read += bytes;
                }
                var xyzi = _slice_frame_xyzi_fast(buf, n);
                var out = { index: i, timestamp: f.bag_time_sec, seq: f.seq, n_points: n, xyzi: xyzi };
                i++;
                return out;
            } catch (err) { close(); throw err; }
        },
        close: close,
    };
}

module.exports = {
    STRIDE: STRIDE,
    validate_meta: validate_meta,
    sha256_path: sha256_path,
    load_session: load_session,
    iter_frames_lazy: iter_frames_lazy,
};

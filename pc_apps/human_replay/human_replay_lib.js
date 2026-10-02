/* HR-02 纯函数层：node 可测，零 DOM/THREE 依赖。
 * 消费 meta.json（28B/点: x,y,z,intensity@f32×4 + ring u16 + pad + timestamp f32 + pad）。
 * 浏览器层(replay.js)只从这里取可测逻辑，着色/渲染不进本文件。
 */
"use strict";

// 与板上 meta 一致；改 stride 就是改数据契约,先改 bag2session
var STRIDE_BYTES = 28;
var STRIDE_F32 = STRIDE_BYTES / 4; // 7

/* frames[i] → 点区间表 [{seq, bag_time_sec, start_pts, end_pts, count}]。
 * 顺带校验 offset 单调连续（HR-01 已验过一轮，这里再挡一次读错文件）。
 */
function frame_slice(meta) {
    var frames = meta.frames;
    if (!Array.isArray(frames) || frames.length === 0) {
        throw new Error("meta.frames 为空");
    }
    var out = new Array(frames.length);
    var cursor = 0;
    for (var i = 0; i < frames.length; i++) {
        var f = frames[i];
        var start = f.offset_points | 0;
        var count = f.count_points | 0;
        if (start !== cursor) {
            throw new Error("frames[" + i + "] 点索引断裂: offset=" + start + " 期望=" + cursor);
        }
        cursor = start + count;
        out[i] = {
            seq: f.seq,
            bag_time_sec: (typeof f.bag_time_sec === "number") ? f.bag_time_sec : null,
            stamp_sec: f.stamp_sec, stamp_nanosec: f.stamp_nanosec,
            start_pts: start, end_pts: cursor, count: count,
        };
    }
    return out;
}

/* 从跨步点缓冲抽一帧的稠密 [x,y,z,i]* 段。
 * buf: 整个点区的 Float32Array 视图（len = total_pts * 7），跨step_items=7。
 * 返回新的 Float32Array(count*4)。HR-05 的框内点查询也靠它。
 */
function strided_f32_copy(buf, start_pts, count, stride_items) {
    var base = start_pts * stride_items;
    var out = new Float32Array(count * 4);
    for (var p = 0; p < count; p++) {
        var s = base + p * stride_items;
        var d = p * 4;
        out[d] = buf[s]; out[d + 1] = buf[s + 1];
        out[d + 2] = buf[s + 2]; out[d + 3] = buf[s + 3];
    }
    return out;
}

/* 分位值（sample 抽稀版）：全量 81k 点/帧全量算第 2/98 位成本可忽略，
 * 但跨帧复用时调用方一般传抽稀样本。q∈[0,1]。
 */
function percentile(sorted_vals, q) {
    var n = sorted_vals.length;
    if (n === 0) return 0;
    var idx = Math.min(n - 1, Math.max(0, Math.round(q * (n - 1))));
    return sorted_vals[idx];
}

/* intensity 归一化窗口：按 ~1/16 抽稀+排序算 [p2, p98]。
 * 返回 {lo, hi}；退化（全零/单值）时给 [0,1] 防除以零。
 */
function pick_intensity_range(frame_xyz_i_list) {
    // 把多帧的强度汇成抽稀样本，排序取分位
    var sample = [];
    for (var k = 0; k < frame_xyz_i_list.length; k++) {
        var fr = frame_xyz_i_list[k];
        for (var i = 3; i < fr.length; i += 4 * 16) { // i 通道, 每 16 点抽 1
            sample.push(fr[i]);
        }
    }
    if (sample.length === 0) return { lo: 0, hi: 1 };
    sample.sort(function (a, b) { return a - b; });
    var lo = percentile(sample, 0.02);
    var hi = percentile(sample, 0.98);
    if (!(hi > lo)) { lo = sample[0]; hi = sample[sample.length - 1]; }
    if (!(hi > lo)) { lo = 0; hi = 1; }
    return { lo: lo, hi: hi };
}

/* 强度→灰度 0..1（clamp）。着色公式放这里，node 可测。 */
function intensity_to_gray(v, lo, hi) {
    var t = (v - lo) / (hi - lo);
    if (t < 0) return 0;
    if (t > 1) return 1;
    return t;
}

/* 秒 → "MM:SS.d" 显示用 */
function format_hhmmss(sec) {
    if (sec == null || !isFinite(sec)) return "--:--";
    var neg = sec < 0; sec = Math.abs(sec);
    var m = Math.floor(sec / 60), s = sec - m * 60;
    var str = (m < 10 ? "0" : "") + m + ":" + (s < 10 ? "0" : "") + s.toFixed(1);
    return neg ? "-" + str : str;
}

var PLAYBACK_SPEEDS = [0.25, 0.5, 1, 2, 4];

/* 默认 fps：meta.frame_rate_hz_measured，拿不到就 10（板实测 9.68 量级） */
function default_fps(meta) {
    var r = meta.frame_rate_hz_measured;
    return (typeof r === "number" && r > 0 && r < 120) ? r : 10;
}

var _api = {
    STRIDE_BYTES: STRIDE_BYTES,
    STRIDE_F32: STRIDE_F32,
    frame_slice: frame_slice,
    strided_f32_copy: strided_f32_copy,
    pick_intensity_range: pick_intensity_range,
    intensity_to_gray: intensity_to_gray,
    format_hhmmss: format_hhmmss,
    PLAYBACK_SPEEDS: PLAYBACK_SPEEDS,
    default_fps: default_fps,
};

if (typeof module !== "undefined" && module.exports) { module.exports = _api; }
if (typeof globalThis !== "undefined") { globalThis.human_replay_lib = _api; }

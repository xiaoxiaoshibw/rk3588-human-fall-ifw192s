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

/* 飞行相机数学（我的世界旁观者式）：F 进入，WASD 沿视线移动，
 * 空格升 / Shift 降（世界 +Z），鼠标指针锁定后偏航+俯仰。
 * 零 THREE 依赖，node 可测；角度均为右手系 z-up（yaw=绕+Z, pitch=仰角）。 */
var FLY_SPEED_MPS = 6;
var FLY_MOUSE_SENS = 0.0024;   // rad/像素（≈MC 默认手感）
var FLY_PITCH_LIMIT = 1.4835;  // 85°：离 lookAt up=(0,0,1) 奇异远点，绝不翻转

/* 鼠标增量 → 新 (yaw,pitch)。鼠标右移(dx>0)=向右转(yaw 减)，下移(dy>0)=低头。 */
function fly_aim(yaw, pitch, dx_px, dy_px, sens) {
    yaw -= dx_px * sens;
    pitch -= dy_px * sens;
    if (pitch > FLY_PITCH_LIMIT) pitch = FLY_PITCH_LIMIT;
    else if (pitch < -FLY_PITCH_LIMIT) pitch = -FLY_PITCH_LIMIT;
    return [yaw, pitch];
}

/* 视线基向量：fwd 带俯仰（W 沿视线飞，含垂直分量），right 永远水平。 */
function fly_axes(yaw, pitch) {
    var c = Math.cos(pitch);
    return {
        fwd: [c * Math.cos(yaw), c * Math.sin(yaw), Math.sin(pitch)],
        right: [Math.sin(yaw), -Math.cos(yaw), 0],
    };
}

/* 从当前视线方向(= target-camera 任意非零向量)反推 (yaw,pitch)，进入飞行时续接视角。
 * 垂直方向(水平分量=0)直接给 ±π/2，避开 atan2(h~0) 精度损失。 */
function fly_aim_from_dir(d) {
    var h = Math.hypot(d[0], d[1]);
    if (h === 0) return [0, d[2] > 0 ? Math.PI / 2 : -Math.PI / 2];
    return [Math.atan2(d[1], d[0]), Math.atan2(d[2], h)];
}

var PLAYBACK_SPEEDS = [0.25, 0.5, 1, 2, 4];

/* 默认 fps：meta.frame_rate_hz_measured，拿不到就 10（板实测 9.68 量级） */
function default_fps(meta) {
    var r = meta.frame_rate_hz_measured;
    return (typeof r === "number" && r > 0 && r < 120) ? r : 10;
}

/* ---------------- HR-04 编辑器导航层纯函数（新增） ---------------- */

/* 视图预设：四个预设 + home 归位。雷达 z-up x-forward y-left。
 * proj: "ortho" 正交 / "persp" 透视。所有 ortho 用同一左右上下框（由调用方按视野微调）。*/
var VIEW_PRESETS = {
    top:    { pos: [5, 0, 15],       tgt: [5, 0, 0],      up: [1, 0, 0], proj: "ortho" },
    front:  { pos: [-6, 0, 1.6],     tgt: [5, 0, 1.0],    up: [0, 0, 1], proj: "ortho" },
    side:   { pos: [5, 12, 1.5],     tgt: [5, 0, 1.5],    up: [0, 0, 1], proj: "ortho" },
    persp:  { pos: [-3.5, -4, 2.8],  tgt: [2.5, 0, 0.6],  up: [0, 0, 1], proj: "persp" },
    home:   { pos: [-3.5, -4, 2.8],  tgt: [2.5, 0, 0.6],  up: [0, 0, 1], proj: "persp" },
};
var ORTHO_HALF_W = 10;    // 左右各 10m（雷达常用范围）
var ORTHO_HALF_H = 7;     // 上下各 7m

function view_preset(name) {
    var p = VIEW_PRESETS[name];
    if (!p) throw new Error("view_preset 未知名称: " + name);
    return {
        pos: p.pos.slice(), tgt: p.tgt.slice(), up: p.up.slice(), proj: p.proj,
        ortho_half_w: ORTHO_HALF_W, ortho_half_h: ORTHO_HALF_H,
    };
}

/* 两点欧氏距离 */
function measure_dist(p1, p2) {
    return Math.hypot(p2[0] - p1[0], p2[1] - p1[1], p2[2] - p1[2]);
}

/* 距离格式化："1.23m" / "<0.01m" 精度防 0.00 歧义 */
function measure_format(d) {
    if (d < 0.005) return "<0.01m";
    return d.toFixed(2) + "m";
}

/* 射线与平面 z=0 的交点：ray origin + t*dir，dir_z≠0 → t=-origin_z/dir_z
 * 返回 [x,y,0]；dir_z≈0 时返回 null（视线与地面平行，打不到点）。*/
function ray_ground_intersect(origin, dir) {
    if (Math.abs(dir[2]) < 1e-9) return null;
    var t = -origin[2] / dir[2];
    if (t < 0) return null;   /* 交点在相机背后 */
    return [origin[0] + t * dir[0], origin[1] + t * dir[1], 0];
}

/* 在稠密 [x,y,z,i]* 点缓冲里按 xy 找最近点索引；O(N) brute-force。
 * 返回 {idx, x, y, z, i, d_xy}。空缓冲返回 null。*/
function find_nearest_xy(xyzi, qx, qy) {
    var n = xyzi.length / 4;
    if (n === 0) return null;
    var best = -1, best_d2 = Infinity;
    for (var k = 0; k < n; k++) {
        var dx = xyzi[k * 4] - qx, dy = xyzi[k * 4 + 1] - qy;
        var d2 = dx * dx + dy * dy;
        if (d2 < best_d2) { best_d2 = d2; best = k; }
    }
    return {
        idx: best,
        x: xyzi[best * 4], y: xyzi[best * 4 + 1],
        z: xyzi[best * 4 + 2], i: xyzi[best * 4 + 3],
        d_xy: Math.sqrt(best_d2),
    };
}

/* localStorage 键名统一前缀，方便审 / 测试断言 */
var LS_PREFIX = "human_replay.";

/* ---------------- HR-05 标注编辑纯函数（新增） ---------------- */

/* 标注工具标识：写入 human_annotations[].tool */
var ANNOTATION_TOOL = "human_replay/0.1";

/* 从地面矩形 + 点云推算轴对齐盒体；
 * p0/p1: [x,y] 或 [x,y,*]，points 可选 Float32Array
 * 返回 {center:[3], size:[3], yaw, zmin, zmax}。 */
function bbox_from_ground_rect(p0, p1, xyzi) {
    var xmin = Math.min(p0[0], p1[0]), xmax = Math.max(p0[0], p1[0]);
    var ymin = Math.min(p0[1], p1[1]), ymax = Math.max(p0[1], p1[1]);
    var cx = (xmin + xmax) / 2, cy = (ymin + ymax) / 2;
    var sx = xmax - xmin, sy = ymax - ymin;
    var zmin = 0.0, zmax = 1.8;   // 人形默认高度
    if (xyzi && xyzi.length >= 4) {
        var zvals = [];
        for (var k = 0; k < xyzi.length; k += 4) {
            var x = xyzi[k], y = xyzi[k + 1], z = xyzi[k + 2];
            if (x >= xmin && x <= xmax && y >= ymin && y <= ymax) zvals.push(z);
        }
        if (zvals.length > 0) {
            zvals.sort(function (a, b) { return a - b; });
            zmin = quantile(zvals, 0.02);
            zmax = quantile(zvals, 0.98);
        }
    }
    return { center: [cx, cy, (zmin + zmax) / 2], size: [sx, sy, zmax - zmin], yaw: 0, zmin: zmin, zmax: zmax };
}

/* 无点云时兜底，与地面矩形同型 */
function bbox_from_rect(p0, p1, zmin, zmax) {
    var xmin = Math.min(p0[0], p1[0]), xmax = Math.max(p0[0], p1[0]);
    var ymin = Math.min(p0[1], p1[1]), ymax = Math.max(p0[1], p1[1]);
    return {
        center: [(xmin + xmax) / 2, (ymin + ymax) / 2, (zmin + zmax) / 2],
        size: [xmax - xmin, ymax - ymin, zmax - zmin],
        yaw: 0, zmin: zmin, zmax: zmax,
    };
}

/* 准星射线沿 direction 找最近点云点（用于「指哪放哪」）。
 * 返回射线最近点 (在 MAX_DIST 垂直半径内，world 距离最小的点)，或 null。
 * MAX_DIST：降低到 ~0.5m —— 用户期望"枪指到哪打到哪"，不是 1m 半径里糊掉一片。*/
function pick_point_on_ray(origin, dir, xyzi, max_dist) {
    var md = max_dist || 0.5;
    var best = null, best_along = Infinity;
    for (var k = 0; k < xyzi.length; k += 4) {
        var px = xyzi[k], py = xyzi[k + 1], pz = xyzi[k + 2];
        var vx = px - origin[0], vy = py - origin[1], vz = pz - origin[2];
        /* v 投影到 dir 上 */
        var along = vx * dir[0] + vy * dir[1] + vz * dir[2];
        if (along < 0) continue;   /* 相机背后 */
        /* v 垂直于 dir 的分量长度 = 点到射线的垂直距离 */
        var perpx = vx - along * dir[0], perpy = vy - along * dir[1], perpz = vz - along * dir[2];
        var d_perp2 = perpx * perpx + perpy * perpy + perpz * perpz;
        if (d_perp2 > md * md) continue;
        if (along < best_along) { best_along = along; best = { x: px, y: py, z: pz, along: along, d_perp: Math.sqrt(d_perp2) }; }
    }
    return best;
}

/* 人形默认定形参数（放框用）。随 v1 约定写死，与 README §5 D9 一致。*/
var HUMAN_DEFAULT = { size: [0.5, 0.5, 1.8], yaw: 0 };

/* 用 pick_point_on_ray 的结果生成默认人形框（center/size/yaw）。
 * 决策：落点用射线找的点（x,y 用点位置），z 强制落地面 z=0（人脚），高度 = HUMAN_DEFAULT.size[2]。
 * 这样跨视角放框，人都是在地面上站起来而不是空中飞。*/
function human_box_from_pick(pick, ground_xy) {
    var cx, cy;
    if (pick) { cx = pick.x; cy = pick.y; }
    else if (ground_xy) { cx = ground_xy[0]; cy = ground_xy[1]; }
    else return null;
    return {
        center: [cx, cy, HUMAN_DEFAULT.size[2] / 2],
        size: HUMAN_DEFAULT.size.slice(),
        yaw: HUMAN_DEFAULT.yaw,
        zmin: 0, zmax: HUMAN_DEFAULT.size[2],
    };
}

/* 200ms 连击限制器：闭包模子。new 一个在 ANN 内持引用。*/
function make_click_throttle(gap_ms) {
    var last = 0, gap = gap_ms || 200;
    return function () {
        var now = Date.now ? Date.now() : performance.now();
        if (now - last < gap) return false;
        last = now; return true;
    };
}

/* 已排序数组取分位（HR-05 专用；不引入 math 库） */
function quantile(sorted, q) {
    if (sorted.length === 0) return NaN;
    var idx = q * (sorted.length - 1);
    var lo = Math.floor(idx), hi = Math.ceil(idx);
    if (lo === hi) return sorted[lo];
    return sorted[lo] + (sorted[hi] - sorted[lo]) * (idx - lo);
}

/* undo 栈（20 层，无 redo） */
function undo_stack_new() { return { stack: [], capacity: 20 }; }
function undo_stack_push(st, entry) {
    var copy = st.stack.slice();
    copy.push(entry);
    while (copy.length > st.capacity) copy.shift();
    return { stack: copy, capacity: st.capacity };
}
function undo_stack_pop(st) {
    if (st.stack.length === 0) return { entry: null, new_stack: st };
    var copy = st.stack.slice();
    var entry = copy.pop();
    return { entry: entry, new_stack: { stack: copy, capacity: st.capacity } };
}

/* 契约校验：box 字段完整、有限、尺寸合法 */
function annotation_validate_box(box) {
    if (!box || typeof box !== "object") return "box 不是对象";
    var c = box.center, s = box.size, yaw = box.yaw;
    if (!Array.isArray(c) || c.length !== 3 || !Array.isArray(s) || s.length !== 3) return "center/size 不是 3 元数组";
    for (var i = 0; i < 3; i++) {
        if (!isFinite(c[i]) || Math.abs(c[i]) > 100) return "center[" + i + "]=" + c[i] + " 超界 [-100,100]";
        if (!isFinite(s[i]) || s[i] <= 0 || s[i] > 20) return "size[" + i + "]=" + s[i] + " 超界 (0,20]";
    }
    if (!isFinite(yaw) || yaw <= -Math.PI || yaw > Math.PI) return "yaw=" + yaw + " 超界 (-π,π]";
    return true;
}

/* 捕捉步进：move 0.1m / rotate 5° / scale 0.05 */
function annotation_snap_step(mode, value, ctrl) {
    if (!ctrl) return value;
    var step = mode === "move" ? 0.1 : mode === "rotate" ? Math.PI / 36 : mode === "scale" ? 0.05 : 0;
    if (step <= 0) return value;
    return Math.round(value / step) * step;
}

/* 序列化 output：把 frames-bucketed annotations 拍平为契约数组 */
function annotation_serialize(annotations_by_seq, session_meta, include_unfinished) {
    var frames = (session_meta && session_meta.frames) ? session_meta.frames : [];
    var seq_set = {};
    for (var i = 0; i < frames.length; i++) seq_set[frames[i].seq] = frames[i];
    var out = [];
    for (var seq in annotations_by_seq) {
        var arr = annotations_by_seq[seq]; if (!Array.isArray(arr)) continue;
        for (var k = 0; k < arr.length; k++) {
            var a = arr[k];
            if (!include_unfinished && !a.fixed) continue;
            var f = seq_set[seq]; if (!f) continue;
            out.push({
                id: a.id,
                source: "human",
                label: a.label || "person",
                frame_seq: Number(seq),
                stamp_sec: f.stamp_sec,
                stamp_nanosec: f.stamp_nanosec,
                box: { center: a.center.slice(), size: a.size.slice(), yaw: a.yaw },
                created_iso: new Date().toISOString(),
                tool: ANNOTATION_TOOL,
                frame_valid: true,
            });
        }
    }
    return out;
}

/* ---------------- HR-03 剪辑纯函数层（新增） ---------------- */

/* 剪辑工具标识：写入 dst meta.extraction.tool */
var TRIM_TOOL = "human_replay_trim/0.1";

/* 切片：校验 + 返回 {frames（新 offset 累计）, byte_range, seq_range, point_total, stride_bytes}
 * - s_seq/e_seq 用驱动 ROS seq 定位（HR-05 契约要 seq 原值）
 * - bin_size_bytes 由调用方给（fs.statSync(points.bin).size）；不传则跳过累计守门
 * - stride_bytes 以 meta.point_stride_bytes 为准（板上 28；不硬编 STRIDE_BYTES）
 */
function compute_trim_slice(meta, s_seq, e_seq, bin_size_bytes) {
    var stride = meta.point_stride_bytes | 0;
    if (!(stride > 0)) throw new Error("meta.point_stride_bytes 非法: " + stride);
    var frames = meta.frames;
    if (!Array.isArray(frames) || frames.length === 0) throw new Error("meta.frames 为空");
    for (var i = 1; i < frames.length; i++) {
        if (frames[i].seq !== frames[i - 1].seq + 1) {
            throw new Error("seq 非连续: frames[" + i + "].seq=" + frames[i].seq +
                " 期望 " + (frames[i - 1].seq + 1));
        }
    }
    var last = frames[frames.length - 1];
    var total_pts = (last.offset_points | 0) + (last.count_points | 0);
    var expect_bytes = total_pts * stride;
    if (typeof bin_size_bytes === "number" && bin_size_bytes !== expect_bytes) {
        throw new Error("总点数与 points.bin 字节数不符: 期望 " + expect_bytes +
            " 实给 " + bin_size_bytes);
    }
    var s_idx = -1, e_idx = -1;
    for (var k = 0; k < frames.length; k++) {
        if (frames[k].seq === s_seq) s_idx = k;
        if (frames[k].seq === e_seq) e_idx = k;
    }
    if (s_idx < 0 || e_idx < 0 || s_idx > e_idx) {
        throw new Error("区间越界: seq_range=[" + s_seq + "," + e_seq + "]" +
            " 合法 seq=[" + frames[0].seq + "," + last.seq + "] 要求 start<=end");
    }
    var new_frames = new Array(e_idx - s_idx + 1);
    var cursor = 0;
    for (var j = s_idx; j <= e_idx; j++) {
        var f = frames[j];
        var c = f.count_points | 0;
        var nf = {};
        for (var key in f) if (Object.prototype.hasOwnProperty.call(f, key)) nf[key] = f[key];
        nf.offset_points = cursor;
        nf.bag_time_sec = f.bag_time_sec - frames[s_idx].bag_time_sec;
        new_frames[j - s_idx] = nf;
        cursor += c;
    }
    var byte_start = (frames[s_idx].offset_points | 0) * stride;
    var byte_end = ((frames[e_idx].offset_points | 0) + (frames[e_idx].count_points | 0)) * stride;
    return {
        frames: new_frames,
        byte_range: [byte_start, byte_end],
        seq_range: [s_seq, e_seq],
        point_total: cursor,
        stride_bytes: stride,
    };
}

/* 新 sid：src_sid + _clip_<s_seq>-<e_seq>（seq 原值可定位） */
function trim_session_id(src_sid, s_seq, e_seq) {
    return src_sid + "_clip_" + s_seq + "-" + e_seq;
}

/* 新 meta：白名单继承 + frames 重写 + extraction 全替换（源 extraction.bag 对剪辑而言已失真）
 * now_iso 由调用方传（node 可控）。
 */
function rewrite_meta_for_trim(src_meta, slice, new_sid, tool_ver, now_iso) {
    var src_ext = src_meta.extraction || {};
    return {
        format: src_meta.format,
        format_version: src_meta.format_version,
        session_id: new_sid,
        created_iso: now_iso,
        sensor: src_meta.sensor,
        time_domain: src_meta.time_domain,
        duration_sec: slice.frames[slice.frames.length - 1].bag_time_sec -
                      slice.frames[0].bag_time_sec,
        point_layout: src_meta.point_layout,
        point_stride_bytes: src_meta.point_stride_bytes,
        point_file: src_meta.point_file,
        total_points: slice.point_total,
        frames: slice.frames,
        human_annotations: [],
        extraction: {
            tool: tool_ver || TRIM_TOOL,
            source_session: src_meta.session_id,
            source_range: slice.seq_range,
            source_tool: src_ext.tool || null,
        },
    };
}

/* 剪辑前守门：磁盘余量 ≥ 切片字节 + slack */
function pre_trim_check(dst_dir, need_bytes, free_bytes_at_dst, slack_bytes) {
    if (free_bytes_at_dst < need_bytes + (slack_bytes || 0)) {
        throw new Error("磁盘空间不足: 需 " + (need_bytes + (slack_bytes || 0)) +
            " 字节 余量 " + free_bytes_at_dst + " 字节 (dst=" + dst_dir + ")");
    }
    return true;
}

/* 浏览器 HUD 复制的命令行（字符串拼装，不执行）
 * base_dir 是 pc_apps/human_replay 的绝对磁盘根（由 lib 调用方注入，不在浏览器推断）。
 */
function trim_command_string(src_dir, s_seq, e_seq, base_dir) {
    if (!base_dir) {
        // 浏览器在 file:// 下没法推 pc_apps 路径——给出提示性占位
        return "node pc_apps/human_replay/trim.js --src \"" + src_dir +
            "\" --start " + s_seq + " --end " + e_seq;
    }
    return "node \"" + base_dir.replace(/[\\/]+$/, "") + "\\trim.js\"" +
        " --src \"" + src_dir + "\" --start " + s_seq + " --end " + e_seq;
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
    FLY_SPEED_MPS: FLY_SPEED_MPS,
    FLY_MOUSE_SENS: FLY_MOUSE_SENS,
    FLY_PITCH_LIMIT: FLY_PITCH_LIMIT,
    fly_aim: fly_aim,
    fly_axes: fly_axes,
    fly_aim_from_dir: fly_aim_from_dir,
    // HR-03
    TRIM_TOOL: TRIM_TOOL,
    compute_trim_slice: compute_trim_slice,
    trim_session_id: trim_session_id,
    rewrite_meta_for_trim: rewrite_meta_for_trim,
    pre_trim_check: pre_trim_check,
    trim_command_string: trim_command_string,
    // HR-04
    VIEW_PRESETS: VIEW_PRESETS,
    ORTHO_HALF_W: ORTHO_HALF_W,
    ORTHO_HALF_H: ORTHO_HALF_H,
    view_preset: view_preset,
    measure_dist: measure_dist,
    measure_format: measure_format,
    ray_ground_intersect: ray_ground_intersect,
    find_nearest_xy: find_nearest_xy,
    LS_PREFIX: LS_PREFIX,
    // HR-05
    ANNOTATION_TOOL: ANNOTATION_TOOL,
    quantile: quantile,
    bbox_from_ground_rect: bbox_from_ground_rect,
    bbox_from_rect: bbox_from_rect,
    undo_stack_new: undo_stack_new,
    undo_stack_push: undo_stack_push,
    undo_stack_pop: undo_stack_pop,
    annotation_validate_box: annotation_validate_box,
    annotation_snap_step: annotation_snap_step,
    annotation_serialize: annotation_serialize,
    /* HR-06 准星放框 */
    HUMAN_DEFAULT: HUMAN_DEFAULT,
    pick_point_on_ray: pick_point_on_ray,
    human_box_from_pick: human_box_from_pick,
    make_click_throttle: make_click_throttle,
};

if (typeof module !== "undefined" && module.exports) { module.exports = _api; }
if (typeof globalThis !== "undefined") { globalThis.human_replay_lib = _api; }

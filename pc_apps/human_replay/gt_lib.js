/* gt_lib.js — HUMAN-GT-ANNOTATOR-R1 无 DOM 纯函数层。
 * node 直测（gt_lib.test.js），gt_annotator.js 浏览器层只包事件。
 *
 * 核心不变量（一步错全错）：
 *   1. 索引空间 = "leveled-compact"：把 points.bin 每帧的原始点做过滤
 *      (finite && any(x,y,z)!=0) 后剩下的 n<=49k 点，下标 0..n-1。
 *      原始 raw index ↔ compact index 由 split_frame_indices 的
 *      Int32Array 映射 (leaf→raw) + apply_rt_inverse(render_person_label.R/T)
 *      无损还原。GT 冻结回写的就是 compact 空间。
 *   2. compact 下标在 JSON 里用 run-length + sparse 混合编码，
 *      避免 49k-点帧数 MB 的 GT 文件。
 *   3. 传播出来的对象 source=propagated / review_status=unreviewed；只有
 *      人工确认才进 human/reviewed。模型建议 source=model 同样永远 unreviewed。
 */
"use strict";

/* 与 render_person_label.py R/T 严格一致（行主序 9 元 + 3 元平移）。
 * leveling.js REF_RT 是同一份；两处复制是有意的：python 端没有 require 通路。 */
var RT = {
    R: [0.893544, 0.0, 0.448975,
       -0.014337, 0.99949, 0.028533,
       -0.448746, -0.031932, 0.893089],
    T: [0.0, 0.0, 1.380286],
};
var TRANSFORM_ID = "render_person_label.R/T";

function apply_rt_point(R, T, x, y, z) {
    return [
        R[0] * x + R[1] * y + R[2] * z + T[0],
        R[3] * x + R[4] * y + R[5] * z + T[1],
        R[6] * x + R[7] * y + R[8] * z + T[2],
    ];
}

/* 逆旋转：R 正交（由 TLS 求出的合法旋转），invert = transpose；再减 T。
 * 浮点合成误差不累积——每次只从"原始传感系 xyz"出发做一次正向。 */
function apply_rt_inverse(R, T, lx, ly, lz) {
    var x0 = lx - T[0], y0 = ly - T[1], z0 = lz - T[2];
    return [
        R[0] * x0 + R[3] * y0 + R[6] * z0,
        R[1] * x0 + R[4] * y0 + R[7] * z0,
        R[2] * x0 + R[5] * y0 + R[8] * z0,
    ];
}

/* raw 传感系点（STRIDE=28B 含义的 Float32Array [x,y,z,i,...] 连续）+ 原始点总数 →
 * { leveled_xyz: Float32Array n*3, raw_of_leaf: Int32Array n, leaf_of_raw: Int32Array orig_n (-1=被过滤) }。
 * 整会话（1493 万点）一遍过；annotator 载入一次后不再重算。 */
function split_frame_indices(raw_f32, point_stride_items) {
    var stride = point_stride_items || 7;   /* [x,y,z,i,<pad>,<time>,<pad>] f32 view */
    var total = raw_f32.length / stride;
    var leaf_of_raw = new Int32Array(total);
    var n = 0;
    for (var p = 0; p < total; p++) {
        var o = p * stride;
        var x = raw_f32[o], y = raw_f32[o + 1], z = raw_f32[o + 2];
        if (isFinite(x) && isFinite(y) && isFinite(z) && (x !== 0 || y !== 0 || z !== 0)) {
            leaf_of_raw[p] = n; n++;
        } else {
            leaf_of_raw[p] = -1;
        }
    }
    var lev = new Float32Array(n * 3);
    var raw_of_leaf = new Int32Array(n);
    var k = 0;
    for (var q = 0; q < total; q++) {
        if (leaf_of_raw[q] < 0) continue;
        var oo = q * stride;
        var lv = apply_rt_point(RT.R, RT.T, raw_f32[oo], raw_f32[oo + 1], raw_f32[oo + 2]);
        lev[k * 3] = lv[0]; lev[k * 3 + 1] = lv[1]; lev[k * 3 + 2] = lv[2];
        raw_of_leaf[k] = q; k++;
    }
    return { leveled_xyz: lev, raw_of_leaf: raw_of_leaf, leaf_of_raw: leaf_of_raw, n_leveled: n };
}

/* ---------------- 索引编码 ----------------
 * 统一整数数组编码：
 *   n<=64                              → ["s", a0, a1, ...]     (稀疏)
 *   起 a0、步长 d、长度 m（末=a0+(m-1)d）→ ["r", a0, d, m]       (run)
 *   其它                                → ["m", [run 头...], [tail...]]
 * decode 展开到整数数组（新数组，避免共享 buffer）。 */
function encode_indices(arr) {
    var a = Array.from(arr);
    if (a.length === 0) return ["s"];
    if (a.length <= 64) return ["s"].concat(a);
    var runs = [], i = 0;
    while (i < a.length - 1) {
        var a0 = a[i], d = a[i + 1] - a[i], m = 2;
        while (i + m < a.length && a[i + m] === a0 + m * d) m++;
        if (m >= 4) { runs.push(a0, d, m); i += m; }
        else break;
    }
    if (i === 0) return ["s"].concat(a);            /* 一个 run 都组不出 */
    var tail = a.slice(i);
    if (runs.length === 3 && tail.length === 0) return ["r"].concat(runs);
    return ["m", runs, tail];
}
function decode_indices(v) {
    if (!v || !v.length) return [];
    var t = v[0];
    if (t === "s") return v.slice(1);
    if (t === "r") {
        var a0 = v[1], d = v[2], m = v[3], out = new Array(m);
        for (var k = 0; k < m; k++) out[k] = a0 + k * d;
        return out;
    }
    if (t === "m") {
        var runs = v[1], tail = v[2], out2 = [];
        for (var r = 0; r < runs.length; r += 3)
            for (var k2 = 0; k2 < runs[r + 2]; k2++) out2.push(runs[r] + k2 * runs[r + 1]);
        return out2.concat(tail);
    }
    throw new Error("未知 index 编码 tag: " + t);
}

/* ---------------- 几何 ---------------- */
function point_in_poly(px, py, poly) {
    /* ray-casting, poly=[[x,y],...] */
    var inside = false;
    for (var i = 0, j = poly.length - 1; i < poly.length; j = i++) {
        var xi = poly[i][0], yi = poly[i][1], xj = poly[j][0], yj = poly[j][1];
        if ((yi > py) !== (yj > py)
            && px < ((xj - xi) * (py - yi)) / (yj - yi) + xi) inside = !inside;
    }
    return inside;
}
function point_in_rect(px, py, rect) {
    return px >= Math.min(rect.x0, rect.x1) && px <= Math.max(rect.x0, rect.x1)
        && py >= Math.min(rect.y0, rect.y1) && py <= Math.max(rect.y0, rect.y1);
}

/* leveled_xyz (n*3) → 通过 ROI + z 带 选出的 leveled-compact 下标数组。
 * shape 输入用统一格式 {type:"rect"|"poly", ...}，坐标均 leveled-ground。 */
function select_points(leveled_xyz, selection, z_min, z_max) {
    var n = leveled_xyz.length / 3;
    var out = [];
    for (var k = 0; k < n; k++) {
        var x = leveled_xyz[k * 3], y = leveled_xyz[k * 3 + 1], z = leveled_xyz[k * 3 + 2];
        if (z < z_min || z > z_max) continue;
        var inside = false;
        if (selection.type === "rect") inside = point_in_rect(x, y, selection);
        else if (selection.type === "poly") inside = point_in_poly(x, y, selection.poly);
        else if (selection.type === "circle") {
            var dx = x - selection.x, dy = y - selection.y;
            inside = (dx * dx + dy * dy) <= selection.r_xy * selection.r_xy;
        }
        if (inside) out.push(k);
    }
    return out;
}

/* 冲突检测：新对象/已存在对象间 shared compact 点。返回 {conflicts:[oid...]} */
function point_owner_conflicts(objects, new_id, new_indices) {
    var own = {};
    for (var k = 0; k < new_indices.length; k++) own[new_indices[k]] = 1;
    var conflicts = [];
    (objects || []).forEach(function (o) {
        if (o.object_id === new_id) return;
        var idx = decode_indices(o.raw_point_indices);
        for (var i = 0; i < idx.length; i++)
            if (own[idx[i]]) { conflicts.push(o.object_id); return; }
    });
    return conflicts;
}

/* 地图坐标 → 屏幕。y 轴屏幕向下 → leveled.y 朝上显示，翻号。 */
function transform_for_view(view) {
    /* view: {cx,cy,scale_px_per_m, vw,vh}：cx/cy=视图中心（leveled 系米） */
    return function (mx, my) {
        return [view.vw / 2 + (mx - view.cx) * view.scale_px_per_m,
                view.vh / 2 - (my - view.cy) * view.scale_px_per_m];
    };
}

/* ---------------- 对象构造 ---------------- */
/* FIX-R3-Q1: 加 _oseq 单调尾：同帧多人/多家具产物不再因为 seq 相同覆盖。
 * 调用方应该每次创建对象时给递增 oseq (整会话一份计数)，而不是帧 seq。 */
function mk_object_id(frame_idx, seq) {
    return "obj_f" + frame_idx + "_s" + seq;
}
function mk_object_id_unique(frame_idx, oseq) {
    return "obj_f" + frame_idx + "_n" + oseq;
}
/* sel={shape:{...}, z_min, z_max}；annot/meta 传来源。
 * 契约字段见工单 STEP 2：session/frame/object/track/class/polygon|box/z/raw_idx/
 * coordinate_frame/leveling_transform_id/source/review_status/annotator/schema。 */
function make_object(opts) {
    var shape = opts.shape;
    var o = {
        session_id: opts.session_id,
        frame_id: opts.session_id + ":" + opts.frame_idx,
        frame_idx: opts.frame_idx,
        timestamp: opts.timestamp,
        object_id: opts.object_id || mk_object_id(opts.frame_idx, opts.seq | 0),
        track_id: opts.track_id != null ? String(opts.track_id) : null,
        class_name: opts.class_name,            /* PERSON|FURNITURE|BACKGROUND|UNKNOWN */
        z_min: opts.z_min, z_max: opts.z_max,
        raw_point_indices: opts.raw_point_indices,
        point_count: opts.point_count,
        coordinate_frame: "leveled-IFW192S",
        leveling_transform_id: TRANSFORM_ID,
        source: opts.source,                     /* human|model|propagated */
        review_status: opts.review_status,       /* draft|unreviewed|reviewed */
        annotator: opts.annotator || null,
        schema_version: "gt_workbench/1",
        visibility: opts.visibility || "visible",  /* PERSON 用：visible|partial|occluded */
        note: opts.note || null,
    };
    if (opts.class_name === "PERSON" && !o.track_id) o.track_id = "P1";
    /* 形状字段按契约并并保留：polygon_xy 或 box_xy + 竣工 ROI 也拟合 bounding box
     * 供下游 RF 硬负样本/圆柱裁剪直接吃 (session_load.crop_roi 只吃 {x,y,r_xy})。 */
    if (shape.type === "poly") o.polygon_xy = shape.poly;
    if (shape.type === "rect") o.box_xy = [shape.x0, shape.y0, shape.x1, shape.y1];
    if (shape.type === "circle") { o.x = shape.x; o.y = shape.y; o.r_xy = shape.r_xy; }
    if (!o.polygon_xy) {
        /* box_xy/circle 都补 polygon_xy（模型建议下游吃圆：r_xy 由 bbox 半径估） */
        if (o.box_xy) {
            var x0 = o.box_xy[0], y0 = o.box_xy[1], x1 = o.box_xy[2], y1 = o.box_xy[3];
            o.x = (x0 + x1) / 2; o.y = (y0 + y1) / 2;
            o.r_xy = Math.max(Math.abs(x1 - x0), Math.abs(y1 - y0)) / 2;
        }
    } else {
        var c = polygon_centroid(o.polygon_xy);
        o.x = c[0]; o.y = c[1];
        var r = 0;
        o.polygon_xy.forEach(function (p) { r = Math.max(r, Math.hypot(p[0] - c[0], p[1] - c[1])); });
        o.r_xy = r;
    }
    return o;
}
function polygon_centroid(poly) {
    var sx = 0, sy = 0, n = poly.length;
    poly.forEach(function (p) { sx += p[0]; sy += p[1]; });
    return n ? [sx / n, sy / n] : [0, 0];
}

/* ---------------- 形状平移（移框）----------------
 * 就地平移对象 ROI：circle/box/poly 三种形状全适配；x/y/r_xy 派生字段同步。
 * 点后处理（重选点）由调用方做（它知道当前帧的点云）。 */
function translate_shape(o, dx, dy) {
    if (o.polygon_xy) {
        o.polygon_xy = o.polygon_xy.map(function (p) { return [p[0] + dx, p[1] + dy]; });
        var c = polygon_centroid(o.polygon_xy);
        o.x = c[0]; o.y = c[1];
    } else if (o.box_xy) {
        o.box_xy = [o.box_xy[0] + dx, o.box_xy[1] + dy, o.box_xy[2] + dx, o.box_xy[3] + dy];
        o.x = (o.box_xy[0] + o.box_xy[2]) / 2;
        o.y = (o.box_xy[1] + o.box_xy[3]) / 2;
    } else if (typeof o.x === "number") {
        o.x += dx; o.y += dy;
    }
    return o;
}

/* ---------------- 形状线性插值（I 键） ----------------
 * 按 track_id 匹配两个端点，中间逐帧产 ROI（仍是 unreviewed）。
 * circle: x,y,r_xy 线性；rect: 四角各分量线性；poly: 顶点数必须相同才能插。
 * 返回 per-frame [{frame_idx, shape:{...}}, ...]。 */
function interpolate_shapes(src_shape, dst_shape, steps) {
    /* steps >= 1：1 表示只有 1 个中间帧 */
    var out = [];
    function lerp(a, b, t) { return a + (b - a) * t; }
    for (var k = 1; k <= steps; k++) {
        var t = k / (steps + 1);
        if (src_shape.box_xy && dst_shape.box_xy) {
            var s = src_shape.box_xy, d = dst_shape.box_xy;
            out.push({
                type: "rect",
                x0: lerp(s[0], d[0], t), y0: lerp(s[1], d[1], t),
                x1: lerp(s[2], d[2], t), y1: lerp(s[3], d[3], t),
            });
        } else if (src_shape.polygon_xy && dst_shape.polygon_xy
                   && src_shape.polygon_xy.length === dst_shape.polygon_xy.length) {
            var sp = src_shape.polygon_xy, dp = dst_shape.polygon_xy, n = sp.length, poly = [];
            for (var vi = 0; vi < n; vi++) poly.push([lerp(sp[vi][0], dp[vi][0], t), lerp(sp[vi][1], dp[vi][1], t)]);
            out.push({ type: "poly", poly: poly });
        } else if (typeof src_shape.x === "number" && typeof dst_shape.x === "number") {
            out.push({
                type: "circle",
                x: lerp(src_shape.x, dst_shape.x, t),
                y: lerp(src_shape.y, dst_shape.y, t),
                r_xy: lerp(src_shape.r_xy || 0.5, dst_shape.r_xy || 0.5, t),
            });
        } else {
            return [];   /* 形状不兼容 */
        }
    }
    return out;
}
/* 对象 → 形状对象化（interpolate_shapes 的输入形态） */
function shape_of_object(o) {
    if (o.polygon_xy) return { polygon_xy: o.polygon_xy };
    if (o.box_xy) return { box_xy: o.box_xy };
    return { x: o.x, y: o.y, r_xy: o.r_xy };
}

/* ---------------- undo / redo ----------------
 * 纯 stack；人不要自己 push raw state，用 push(prev, action) → 新数组。 */
function undo_new() { return { undo: [], redo: [] }; }
function undo_push(st, prev_objects) {
    /* prev_objects 是深拷贝快照；置栈后 redo 清空 */
    return { undo: st.undo.concat([prev_objects]).slice(-50), redo: [] };
}
function undo_undo(st, current_objects) {
    if (!st.undo.length) return { stack: st, objects: null };
    var prev = st.undo[st.undo.length - 1];
    return {
        stack: { undo: st.undo.slice(0, -1), redo: st.redo.concat([current_objects]) },
        objects: prev,
    };
}
function undo_redo(st, current_objects) {
    if (!st.redo.length) return { stack: st, objects: null };
    var nxt = st.redo[st.redo.length - 1];
    return {
        stack: { undo: st.undo.concat([current_objects]), redo: st.redo.slice(0, -1) },
        objects: nxt,
    };
}

/* ---------------- 跨帧传播 ---------------- */
/* 把 src_obj 捏成 frame_idx 上的新对象。双人交叉时由调用方（按 track_id）
 * 决定目标 ROI —— 本函数只克隆几何+标记 spread。dest 可覆盖 x,y,r_xy
 * （track 匹配上的人）或保持原 ROI（静止对象）。 */
function propagate_object(src_obj, frame_idx, timestamp, moves) {
    moves = moves || {};
    var clone = JSON.parse(JSON.stringify(src_obj));
    clone.frame_idx = frame_idx;
    clone.frame_id = src_obj.session_id + ":" + frame_idx;
    clone.timestamp = timestamp;
    clone.object_id = mk_object_id(frame_idx, 0) + "_p";
    clone.source = "propagated";
    clone.review_status = "unreviewed";
    clone.parent_object_id = src_obj.object_id;
    if (moves.x !== undefined) clone.x = moves.x;
    if (moves.y !== undefined) clone.y = moves.y;
    if (moves.r_xy !== undefined) clone.r_xy = moves.r_xy;
    if (moves.polygon_xy) clone.polygon_xy = moves.polygon_xy;
    if (moves.box_xy) clone.box_xy = moves.box_xy;
    if (moves.track_id !== undefined) clone.track_id = moves.track_id;
    delete clone.raw_point_indices;   /* 由调用方立即重新 select_points */
    delete clone.point_count;
    /* FIX-R3-Q6: 传播克隆不伪增关键帧；审计字段 interpolated_from/suggested_engine_track
     * 是可读审计，来自模型建议的 source 对象；后续粘贴时不再级联(避免传染),
     * 但 interpolate 本意要记录在 object 上，故只删 is_keyframe。 */
    delete clone.is_keyframe;
    return clone;
}

/* 断点检测：返回可疑 frame_idx 列表。
 *   disappearing: f-1 有 track_id，f 没了（且 f 非结束帧）
 *   appearing:    f-1 没有，f 出现了
 *   gap:          frame 数组本身不连续 */
function find_breaks(frames_map, track_ids) {
    /* frames_map: frame_idx(int) → [obj...]；track_ids: 要跟踪的 track_id 数组 */
    var out = [];
    if (!frames_map) return out;
    var idxs = Object.keys(frames_map).map(Number).sort(function (a, b) { return a - b; });
    for (var i = 1; i < idxs.length; i++) {
        var prev = idxs[i - 1], cur = idxs[i];
        if (cur !== prev + 1) {
            out.push({ frame: cur, kind: "gap", from: prev, to: cur });
            /* 跨 gap 仍要继续测 appear/disappear —— gap 意味「中间没数据」，
             * 但 P 出现/消失本身正是标注需要发现的时机。与 annotate 的任务语义
             * 更贴近的做法：把"前一有记录的帧"作为 prev_track_state。 */
        }
        track_ids.forEach(function (tid) {
            var a = frames_map[prev].some(function (o) { return o.track_id === tid; });
            var b = frames_map[cur].some(function (o) { return o.track_id === tid; });
            if (a && !b) out.push({ frame: cur, kind: "disappear", track_id: tid });
            if (!a && b) out.push({ frame: cur, kind: "appear", track_id: tid });
        });
    }
    return out;
}

/* ---------------- GT 文档 ----------------
 * 会话级 GT 状态机。每会话一份 doc；frame map 存 object_id 列表（对象本体在 objects 字典）。
 * 不存 leveled_xyz/pixels——那些是运行时视图。这里**只存可持久化最小集**。 */
function make_session_doc(session_id, session_sha256, annotator) {
    return {
        schema_version: "gt_workbench/1",
        session_id: session_id,
        session_sha256: session_sha256,
        annotator: annotator || null,
        review_status: "draft",
        gt_level: "UNKNOWN",                 /* 冻结重算 */
        episodes: [],
        uncertain_intervals: [],
        objects: {},                          /* object_id → obj */
        frames_objects: {},                   /* frame_idx(str) → [object_id...] */
        frozen_versions: [],
        history: [],                          /* 人工修改历史 (action, object_id, at_iso, before, after) */
        annotated_at: null,
    };
}
function doc_add_object(doc, obj) {
    /* FIX-R3-Q1: id 重名直接抛，别默默覆盖.*/
    if (doc.objects[obj.object_id]) throw new Error("object_id 已存在: " + obj.object_id);
    doc.objects[obj.object_id] = obj;
    var f = String(obj.frame_idx);
    (doc.frames_objects[f] = doc.frames_objects[f] || []).push(obj.object_id);
}
function doc_remove_object(doc, object_id) {
    var o = doc.objects[object_id];
    if (!o) return;
    var f = String(o.frame_idx);
    var arr = doc.frames_objects[f] || [];
    doc.frames_objects[f] = arr.filter(function (id) { return id !== object_id; });
    delete doc.objects[object_id];
}
function doc_snapshot_objects(doc) {
    /* 深拷贝 frame → [obj,...] 的渲染态；undo 用
     * FIX-AUDIT-Q7: JSON 往返保证快照与 doc 对象无引用共享，编辑后 undo 不被污染。 */
    return JSON.parse(JSON.stringify(
        Object.keys(doc.frames_objects).reduce(function (acc, f) {
            acc[f] = doc.frames_objects[f].map(function (id) { return doc.objects[id]; }).filter(Boolean);
            return acc;
        }, {})));
}
/* FIX-AUDIT-R2: 返回 frame → doc 对象原参照（非拷贝）。渲染/编辑单一数据源。 */
function doc_render_map(doc) {
    return Object.keys(doc.frames_objects).reduce(function (acc, f) {
        acc[f] = doc.frames_objects[f].map(function (id) { return doc.objects[id]; }).filter(Boolean);
        return acc;
    }, {});
}

/* GT level 由全部对象最低审查等级导出（诚实版：没有 reviewed 对象不宣称 HUMAN） */
function compute_gt_level(doc) {
    var any = false, anyReviewed = false;
    Object.keys(doc.objects).forEach(function (id) {
        any = true;
        if (doc.objects[id].review_status === "reviewed" && doc.objects[id].source === "human") anyReviewed = true;
    });
    if (!any) return "UNKNOWN";
    if (doc.review_status === "reviewed" && anyReviewed) return "HUMAN_VERIFIED";
    if (anyReviewed) return "HUMAN_UNVERIFIED";
    return "PSEUDO_LABEL";
}

/* 冻结验证（STEP 7 双检） */
function validate_doc(doc) {
    var errs = [];
    if (!doc.session_sha256 || !doc.session_sha256.points) errs.push("session_sha256.points 缺");
    var per_frame_track = {};  /* frame:tid 同帧内唯一 */
    var track_seen = {};       /* track_id → [{frame,obj_id}] */
    Object.keys(doc.objects).forEach(function (id) {
        var o = doc.objects[id];
        if (!o.object_id) errs.push("object_id 空");
        if (!["PERSON", "FURNITURE", "BACKGROUND", "UNKNOWN"].includes(o.class_name))
            errs.push(id + " class 非法: " + o.class_name);
        if (!["human", "model", "propagated"].includes(o.source))
            errs.push(id + " source 非法: " + o.source);
        if (o.review_status === "reviewed" && o.source === "model")
            errs.push(id + " reviewed 但 source=model（模型不可冒充人工）");
        if (!(o.point_count > 0)) errs.push(id + " point_count 非正");
        if (!o.raw_point_indices) errs.push(id + " 缺 raw_point_indices");
        if (o.class_name === "PERSON") {
            if (!o.track_id) errs.push(id + " PERSON 缺 track_id");
            var fk = o.frame_idx + ":" + o.track_id;
            if (per_frame_track[fk]) errs.push("帧 " + o.frame_idx + " track " + o.track_id + " 重复");
            per_frame_track[fk] = 1;
            (track_seen[o.track_id] = track_seen[o.track_id] || []).push(o.frame_idx);
        }
    });
    /* track 不合法：同 track 的 frame 集合必须单调不跳变（双人交叉靠各自 track 隔离） */
    Object.keys(track_seen).forEach(function (tid) {
        var fr = track_seen[tid].slice().sort(function (a, b) { return a - b; });
        for (var i = 1; i < fr.length; i++) if (fr[i] === fr[i - 1]) errs.push("track " + tid + " 同帧重复");
    });
    return errs;
}

/* 进展面板数据 */
function session_progress(doc, n_frames) {
    var frames_with = Object.keys(doc.frames_objects).filter(function (f) {
        return doc.frames_objects[f].length > 0;
    }).map(Number);
    var reviewed_frames = {};
    var tracks = {}, furniture = 0, person = 0, conflicts = 0;
    Object.keys(doc.objects).forEach(function (id) {
        var o = doc.objects[id];
        if (o.review_status === "reviewed") reviewed_frames[o.frame_idx] = 1;
        if (o.class_name === "PERSON") { person++; if (o.track_id) tracks[o.track_id] = 1; }
        if (o.class_name === "FURNITURE") furniture++;
    });
    /* 冲突数：两两对象 compact 索引交叠（O(K^2)，K=对象总数，单会话 <1k 无所谓） */
    var ids = Object.keys(doc.objects);
    for (var a = 0; a < ids.length; a++) {
        var ia = doc.objects[ids[a]].raw_point_indices;
        var set = {};
        decode_indices(ia).forEach(function (v) { set[v] = 1; });
        for (var b = a + 1; b < ids.length; b++) {
            var ob = doc.objects[ids[b]];
            if (ob.frame_idx !== doc.objects[ids[a]].frame_idx) continue;
            var hit = decode_indices(ob.raw_point_indices).some(function (v) { return set[v]; });
            if (hit) { conflicts++; }
        }
    }
    return {
        total_frames: n_frames,
        annotated_frames: frames_with.length,
        reviewed_frames: Object.keys(reviewed_frames).length,
        unknown_frames: n_frames - frames_with.length,
        person_objects: person,
        furniture_objects: furniture,
        track_ids: Object.keys(tracks).length,
        conflicts: conflicts,
    };
}

/* sha256 — node 与 browser 共用 */
function sha256_hex(str) {
    if (typeof require !== "undefined") {
        try { return require("crypto").createHash("sha256").update(str, "utf8").digest("hex"); } catch (e) { /* fall through */ }
    }
    /* 浏览器 SubtleCrypto 是异步的 —— 同步接口用 sha256 简实现占位
     * （生产环境 annotator 页面本来就是 server-side freeze，browser 里只走导出读）。 */
    if (typeof globalThis !== "undefined" && globalThis.crypto && globalThis.crypto.subtle) {
        throw new Error("浏览器 sha256 用 server 端 /api/gt/freeze（同步接口）");
    }
    throw new Error("no sha256");
}

var _api = {
    RT: RT,
    TRANSFORM_ID: TRANSFORM_ID,
    apply_rt_point: apply_rt_point,
    apply_rt_inverse: apply_rt_inverse,
    split_frame_indices: split_frame_indices,
    encode_indices: encode_indices,
    decode_indices: decode_indices,
    point_in_poly: point_in_poly,
    point_in_rect: point_in_rect,
    polygon_centroid: polygon_centroid,
    select_points: select_points,
    point_owner_conflicts: point_owner_conflicts,
    transform_for_view: transform_for_view,
    mk_object_id: mk_object_id,
    mk_object_id_unique: mk_object_id_unique,
    make_object: make_object,
    undo_new: undo_new,
    undo_push: undo_push,
    undo_undo: undo_undo,
    undo_redo: undo_redo,
    propagate_object: propagate_object,
    translate_shape: translate_shape,
    interpolate_shapes: interpolate_shapes,
    shape_of_object: shape_of_object,
    find_breaks: find_breaks,
    make_session_doc: make_session_doc,
    doc_add_object: doc_add_object,
    doc_remove_object: doc_remove_object,
    doc_snapshot_objects: doc_snapshot_objects,
    doc_render_map: doc_render_map,
    compute_gt_level: compute_gt_level,
    validate_doc: validate_doc,
    session_progress: session_progress,
    sha256_hex: sha256_hex,
};
if (typeof module !== "undefined" && module.exports) module.exports = _api;
if (typeof globalThis !== "undefined") globalThis.gt_lib = _api;

/* gt_suggest.js — HUMAN-GT-ANNOTATOR-R1 预标注批跑（node 唯一写者）。
 *
 * 调用：
 *   node --max-old-space-size=2048 gt_suggest.js --session <dir> --sid <sid> [--max-frames N] [--mode FUSION]
 * 落盘：
 *   pc_apps/human_replay/gt_store/<sid>/fusion_frames.json
 *
 * 每帧输出（leveled-compact 系）：
 *   [{ cls:'PERSON', x,y,r_xy, track_id, confidence, source:'fusion_u3',
 *      raw_point_indices_compact: <gt_lib 编码>, n_cand, decision, frame_idx }]
 *
 * 永不把 source 写成 human，永不把 review_status 写成 reviewed。
 * 引擎 mode 默认 FUSION（A+U3 双侧聚合）；显式 --mode U3/A/B 可切换。
 */
"use strict";
var fs = require("fs"), path = require("path");
var D = require("../human_core/data_loader.js");
var E = require("../human_core/engine.js");
var S = require("../human_core/schema.js");
var L = require("../human_core/leveling.js");
var GT = require("./gt_lib.js");

function parse_args(argv) {
    var o = { mode: "FUSION", max_frames: 0 };
    for (var i = 2; i < argv.length; i++) {
        var a = argv[i], v = argv[i + 1];
        if (a === "--session") { o.session = v; i++; }
        else if (a === "--sid") { o.sid = v; i++; }
        else if (a === "--mode") { o.mode = v; i++; }
        else if (a === "--max-frames") { o.max_frames = Number(v); i++; }
    }
    if (!o.session || !o.sid) throw new Error("--session/--sid 必填");
    if (!["FUSION", "U3", "U1", "U2", "BASE_A", "BASE_B"].includes(o.mode)) throw new Error("mode 非法");
    return o;
}

/* FIX-AUDIT-Q3: 引擎 point_indices 是【帧内 raw】(0..n_points-1, 未过滤零/NaN)；
 * gt_lib.split_frame_indices 产的是【帧内 compact】(过滤零/NaN 后保序)。
 * 需要 raw ↦ compact 投影。 */
function raw_to_compact_frame_indices(raw_engine_idx, leaf_of_raw) {
    var out = [];
    for (var i = 0; i < raw_engine_idx.length; i++) {
        var g = leaf_of_raw[raw_engine_idx[i]];
        if (g >= 0) out.push(g);
    }
    return out;
}

/* bbox → 圆柱估计（强 RT 系：bbox 已是 leveled） */
function bbox_to_circle(bbox, centroid) {
    if (!bbox) {
        return { x: centroid.x, y: centroid.y, r_xy: 0.6 };
    }
    var sx = Math.max(0.05, bbox.max[0] - bbox.min[0]);
    var sy = Math.max(0.05, bbox.max[1] - bbox.min[1]);
    var r = Math.max(sx, sy) / 2;
    var cx = (bbox.min[0] + bbox.max[0]) / 2, cy = (bbox.min[1] + bbox.max[1]) / 2;
    return { x: cx, y: cy, r_xy: Math.min(1.4, Math.max(0.25, r)) };
}

function main() {
    var opts = parse_args(process.argv);
    var sess = D.load_session(opts.session);
    var sid = opts.sid;
    var all_xyzi = sess.frames.map(function (f) { return f.xyzi; });

    /* FIX-AUDIT-Q3: 引擎 candidate.point_indices 是帧内 raw 索引 (0..n_points-1)；
     * gt_lib 的 compact 是过滤零/NaN 后保序 —— 需要 per_frame split 映射。 */
    var per_frame = sess.frames.map(function (f) {
        var sp = GT.split_frame_indices(f.xyzi, 4);
        return { n_lev: sp.n_leveled, leaf_of_raw: sp.leaf_of_raw };
    });

    var cfg = { mode: opts.mode, leveling_rt: L.IDENTITY_RT };
    /* 数据已经是传感系：engine 内部还会再 level。传 IDENTITY 等价于直通吗？
    * — 不对，data_loader 帧是原始雷达系。FUSION 与 BASE_B 走 ref_only 背景路但仍会先 _level。
    * 引擎默认 REF_RT（=我们 RT.R/T），所以正常。 */
    var eng = new E.UnifiedEngine({ mode: opts.mode });
    var generation = eng.begin_session(sid);
    if (opts.mode !== "BASE_B") eng.set_online_background(all_xyzi, { meta: sess.meta });

    var frames_out = {};
    var n = opts.max_frames > 0 ? Math.min(opts.max_frames, sess.frames.length) : sess.frames.length;
    for (var fi2 = 0; fi2 < n; fi2++) {
        var f = sess.frames[fi2];
        var diag = eng.tick(S.make_frame_context({
            session_id: sid, session_generation: generation, frame_index: fi2,
            timestamp: f.timestamp, xyzi: f.xyzi, meta: sess.meta,
        }));
        var sp = per_frame[fi2];
        var cands = diag._candidates || [];
        var out = [];
        for (var ci = 0; ci < cands.length; ci++) {
            var c = cands[ci];
            var circ = bbox_to_circle(c.bbox, c.centroid);
            /* candidate.point_indices 是帧内 raw 索引（未过滤零/NaN）；
             * raw_to_compact_frame_indices 把它们投到与 gt_lib 视图一致的 compact 空间。 */
            var raw_idx = c.point_indices ? Array.from(c.point_indices) : [];
            var leaf_idx = raw_to_compact_frame_indices(raw_idx, sp.leaf_of_raw);
            var track_label = null;
            if (c.track_id_fusion) track_label = String(c.track_id_fusion);
            else if (c.track_id != null) track_label = String(c.track_id);
            else if (c.track_segment != null && c.track_id != null) track_label = c.track_segment + ":" + c.track_id;
            var rf = (c.scores && c.scores.rf51) || {};
            out.push({
                cls: "PERSON",
                x: +circ.x.toFixed(4), y: +circ.y.toFixed(4), r_xy: +circ.r_xy.toFixed(4),
                track_id: track_label,
                confidence: rf.prob != null ? +rf.prob.toFixed(4) : null,
                decision: c.classifier_decision || "UNKNOWN",
                source: "model",
                review_status: "unreviewed",
                engine: opts.mode,
                raw_point_indices_compact: GT.encode_indices(leaf_idx),
                point_count: c.point_count | 0,
                foreground_source: c.foreground_source || null,
            });
        }
        if (out.length) frames_out[String(fi2)] = out;
    }

    var out_dir = path.join(__dirname, "gt_store", sid);
    fs.mkdirSync(out_dir, { recursive: true });
    var payload = {
        sid: sid, engine: opts.mode, generated_at: new Date().toISOString(),
        note: "PSEUDO_LABEL — 仅供人工接受/修改；绝不直接当 GT",
        frames: frames_out,
    };
    var out_path = path.join(out_dir, "fusion_frames.json");
    fs.writeFileSync(out_path, JSON.stringify(payload, null, 1), { flag: "w" });
    console.log("wrote " + out_path + " frames=" + Object.keys(frames_out).length);
}
if (require.main === module) main();
module.exports = {
    parse_args: parse_args,
    bbox_to_circle: bbox_to_circle,
    raw_to_compact_frame_indices: raw_to_compact_frame_indices,
};

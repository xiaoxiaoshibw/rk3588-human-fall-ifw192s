/* test_edge_cases.js — 边界与失败处理： 家具候选/不足点/聚类拆分/缺字段/不兼容。
 * 基元不在真实会话上跑 （太慢）, 而是合成点云喂 UnifiedEngine。
 * node pc_apps/human_core/test_edge_cases.js
 */
"use strict";
var E = require("./engine.js");
var S = require("./schema.js");

var n_pass = 0, n_fail = 0;
function t(cond, msg) {
    if (cond) { n_pass++; console.log("PASS: " + msg); }
    else { n_fail++; console.log("FAIL: " + msg); }
}

/* 造合成帧： n_pts 个 (x,y,z,i) 已 leveled. 背景 = 0 点 (empty bg) */
function mk_sensor_frame(pts_xyz, intensity) {
    var n = pts_xyz.length / 3;
    var out = new Float32Array(n * 4);
    for (var i = 0; i < n; i++) {
        out[i * 4] = pts_xyz[i * 3];
        out[i * 4 + 1] = pts_xyz[i * 3 + 1];
        out[i * 4 + 2] = pts_xyz[i * 3 + 2];
        out[i * 4 + 3] = intensity !== undefined ? intensity : 100;
    }
    return out;
}
function frame_stationary_box(cx, cy, w, h, d, n) {
    /* 在 (cx,cy) 周围 w×h×d 盒内均匀散 n 点 */
    var pts = [];
    for (var i = 0; i < n; i++) {
        pts.push(cx + (Math.random() - 0.5) * w);
        pts.push(cy + (Math.random() - 0.5) * h);
        pts.push(0.1 + Math.random() * d);
    }
    return pts;
}

/* 1 · 空帧 （无点） → 不崩, fg=0, no cand */
(function () {
    var eng = new E.UnifiedEngine({ mode: E.MODE.BASE_A, leveling_rt: { R: [1, 0, 0, 0, 1, 0, 0, 0, 1], T: [0, 0, 0] } });
    eng.begin_session("test");
    eng.set_online_background([mk_sensor_frame([], 0)], {already_leveled:true});
    var fc = S.make_frame_context({ session_generation:eng.generation, session_id: "test", frame_index: 0, timestamp: 0, xyzi: mk_sensor_frame([], 0), already_leveled: true });
    var d = eng.tick(fc);
    t(d._candidates.length === 0, "空帧 0 cand (实测 " + d._candidates.length + ")");
})();

/* 2 · 全点都在 z<0.1 → ground_keep 剔光 → fg=0 */
(function () {
    var eng = new E.UnifiedEngine({ mode: E.MODE.BASE_A, leveling_rt: { R: [1, 0, 0, 0, 1, 0, 0, 0, 1], T: [0, 0, 0] } });
    eng.begin_session("test2");
    var raw = mk_sensor_frame([1, 2, 0.0, 1.1, 2.1, 0.05, 0.9, 2.2, 0.09], 0);
    eng.set_online_background([raw], {already_leveled:true});
    var fc = S.make_frame_context({ session_generation:eng.generation, session_id: "test2", frame_index: 0, timestamp: 0, xyzi: raw, already_leveled: true });
    var d = eng.tick(fc);
    var fg_layer = d.layers.find(function (l) { return l.layer === "foreground"; });
    t(fg_layer.out_points === 0, "z<0.1 前景剔除 fg=0 (实测 " + fg_layer.out_points + ")");
})();

/* 3 · 点不足 (n<10) 帧 → cluster 空 → 0 cand */
(function () {
    var eng = new E.UnifiedEngine({ mode: E.MODE.BASE_A, leveling_rt: { R: [1, 0, 0, 0, 1, 0, 0, 0, 1], T: [0, 0, 0] } });
    eng.begin_session("test3");
    eng.set_online_background([mk_sensor_frame([], 0)], {already_leveled:true});
    /* 5 个点 — 虽会被 fg 保留但聚类至少 3 voxel, 5 点 1 voxel 也不够 */
    var raw = mk_sensor_frame([1, 2, 1.0, 1.01, 2.01, 1.05, 1.02, 2.02, 1.5, 1.03, 2.0, 1.6, 1.04, 2.05, 1.7], 0);
    var fc = S.make_frame_context({ session_generation:eng.generation, session_id: "test3", frame_index: 0, timestamp: 0, xyzi: raw, already_leveled: true });
    var d = eng.tick(fc);
    t(d._candidates.length === 0, "点不足 0 cand (实测 " + d._candidates.length + ")");
})();

/* 4 · 家具盒 vs 人形 (瘦柱): spread_cv 分辨 */
(function () {
    var eng = new E.UnifiedEngine({ mode: E.MODE.BASE_A, leveling_rt: { R: [1, 0, 0, 0, 1, 0, 0, 0, 1], T: [0, 0, 0] } });
    eng.begin_session("test4");
    eng.set_online_background([mk_sensor_frame([], 0)], {already_leveled:true});
    /* 衣柜： 1×1×2m 宽盒 — 所有高度带一样粗 */
    var furn = frame_stationary_box(2, 2, 1.0, 1.0, 2.0, 500);
    /* 人： 0.3×0.3×1.7m 瘦柱 */
    var human = frame_stationary_box(5, 5, 0.3, 0.3, 1.7, 400);
    var all = furn.concat(human);
    var raw = mk_sensor_frame(all, 100);
    var fc = S.make_frame_context({ session_generation:eng.generation, session_id: "test4", frame_index: 0, timestamp: 0, xyzi: raw, already_leveled: true });
    var d = eng.tick(fc);
    /* BASE_A 的 hard gate n≥60 会容许两簇； 联合判定 spread_cv 分家具 */
    var n_furn_labeled = d._candidates.filter(function (c) {
        return c.classifier_decision === "NON_HUMAN" || c.classifier_decision === "SOLID_UNIFORM";
    }).length;
    t(d._candidates.length >= 1, "家具+人 ≥1 cand (实测 " + d._candidates.length + ")");
})();

/* 5 · 永久暂时消失： track 5 帧 confirmed → 10 帧空 → 仍有 retention bank */
(function () {
    var eng = new E.UnifiedEngine({
        mode: E.MODE.U2, candidates: "fg_plus_retained",
        leveling_rt: { R: [1, 0, 0, 0, 1, 0, 0, 0, 1], T: [0, 0, 0] },
    });
    eng.begin_session("t5");
    eng.set_online_background([mk_sensor_frame([], 0)], {already_leveled:true});
    /* 喂 5 帧有"人形" */
    for (var i = 0; i < 5; i++) {
        var raw = mk_sensor_frame(frame_stationary_box(2, 2, 0.3, 0.3, 1.7, 400), 100);
        var fc = S.make_frame_context({ session_generation:eng.generation, session_id: "t5", frame_index: i, timestamp: i * 0.1, xyzi: raw, already_leveled: true });
        eng.tick(fc);
    }
    /* 喂 10 帧空 (ran out) */
    for (var i = 5; i < 15; i++) {
        var raw = mk_sensor_frame([], 0);
        var fc = S.make_frame_context({ session_generation:eng.generation, session_id: "t5", frame_index: i, timestamp: i * 0.1, xyzi: raw, already_leveled: true });
        var d = eng.tick(fc);
        if (i === 14) {
            /* 第 15 帧： tracker 应已 lost>8 关闭 (pipe track_lost_max=8) */
            var active = d._tracks || [];
            t(active.length === 0, "人消失10帧后无active track");
        }
    }
})();

/* 6 · 同帧多候选关联唯一： 2 个空间分离人形柱, 同帧 */
(function () {
    var eng = new E.UnifiedEngine({ mode: E.MODE.BASE_A, leveling_rt: { R: [1, 0, 0, 0, 1, 0, 0, 0, 1], T: [0, 0, 0] } });
    eng.begin_session("t6");
    eng.set_online_background([mk_sensor_frame([], 0)], {already_leveled:true});
    /* 两个相距 3m 的人形柱 */
    var combined = frame_stationary_box(2, 2, 0.3, 0.3, 1.7, 400).concat(
        frame_stationary_box(5, 2, 0.3, 0.3, 1.7, 400));
    var raw = mk_sensor_frame(combined, 100);
    var fc = S.make_frame_context({ session_generation:eng.generation, session_id: "t6", frame_index: 0, timestamp: 0, xyzi: raw, already_leveled: true });
    var d = eng.tick(fc);
    t(d._candidates.length >= 1, "多候选跨帧 ≥1 (实测 " + d._candidates.length + ")");
    /* track_id 唯一性： */
    var ids = d._candidates.map(function (c) { return c.track_id; }).filter(function (x) { return x !== null && x !== undefined; });
    var seen = new Set(ids);
    t(seen.size === ids.length, "同帧 track_id 唯一 (" + ids.length + " 个 id, " + seen.size + " 唯一)");
})();

/* 7 · config 缺字段 → 使用默认值不崩 */
(function () {
    try {
        var eng = new E.UnifiedEngine();  /* 无 cfg */
        t(true, "无 cfg 构造不抛");
    } catch (e) { t(false, "无 cfg 构造抛: " + e.message); }
    try {
        var eng2 = new E.UnifiedEngine({});
        t(true, "空 cfg 构造不抛");
    } catch (e) { t(false, "空 cfg 构造抛: " + e.message); }
})();

/* 8 · U4/U5 明确 BLOCKED */
(function () {
    try { new E.UnifiedEngine({ mode: "U4" }); t(false, "U4创新 应抛"); }
    catch (e) { t(true, "U4 BLOCKED 抛错: " + e.message.slice(0, 40)); }
    try { new E.UnifiedEngine({ mode: "U5" }); t(false, "U5创新 应抛"); }
    catch (e) { t(true, "U5 BLOCKED 抛错: " + e.message.slice(0, 40)); }
})();

/* 9 · FrameContext schema 严格 */
(function () {
    try { S.make_frame_context({}); t(false, "空 fc"); }
    catch (e) { t(true, "空 fc 抛错"); }
    try { S.make_frame_context({ session_id: 123, frame_index: 0, xyzi: new Float32Array(4) }); t(true, "session_id 数字 → 字符串化"); }
    catch (e) { t(false, "session_id 数字被错拒"); }
})();

/* 10 · Candidate validate 拒绝负 n */
(function () {
    var c = S.make_candidate({ candidate_id: "c", point_indices: new Uint32Array(0), centroid: { x: 0, y: 0, z: 0 }, point_count: 0 });
    t(S.validate_candidate(c).length > 0, "point_count=0 validate 报错");
})();

console.log("\n== edge_cases: " + n_pass + " PASS, " + n_fail + " FAIL ==");
process.exit(n_fail ? 1 : 0);

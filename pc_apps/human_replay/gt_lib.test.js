/* gt_lib.test.js — HUMAN-GT-ANNOTATOR-R1 纯函数单测（node，无依赖）。
 * 跑： node pc_apps/human_replay/gt_lib.test.js
 * 覆盖 STEP 7 的契约断言 + 所有模型/传播/审核不变量。
 */
"use strict";
var GT = require("./gt_lib.js");
var assert = require("assert");

var pass = 0, fail = 0;
function t(name, fn) {
    try { fn(); pass++; console.log("  ✓ " + name); }
    catch (e) { fail++; console.log("  ✗ " + name + ": " + e.message); }
}

console.log("== gt_lib 单测 ==");

/* ---------- 1. 索引编码 ---------- */
t("encode/decode 稀疏小数组", function () {
    [0, 5, 19, 100].forEach(function (n) {
        var arr = [0, 5, 19, 100];
        var d = GT.decode_indices(GT.encode_indices(arr));
        assert.deepStrictEqual(d, arr);
    });
});
t("encode/decode run (等差)", function () {
    var arr = []; for (var i = 100; i < 200; i += 3) arr.push(i);
    var enc = GT.encode_indices(arr);
    if (enc[0] === "r") { assert.strictEqual(enc[1], 100); }
    assert.deepStrictEqual(GT.decode_indices(enc), arr);
});
t("encode/decode 混合", function () {
    var arr = [0, 1, 2, 3, 4, 5, 6, 7, 100, 150, 200];   /* 前段 run, 后段杂散 */
    var enc = GT.encode_indices(arr);
    var d = GT.decode_indices(enc);
    assert.deepStrictEqual(d, arr);
});
t("encode/decode 空/单点", function () {
    assert.deepStrictEqual(GT.decode_indices(GT.encode_indices([])), []);
    assert.deepStrictEqual(GT.decode_indices(GT.encode_indices([42])), [42]);
});

/* ---------- 2. 几何 ---------- */
t("point_in_poly 正方形", function () {
    var poly = [[0, 0], [2, 0], [2, 2], [0, 2]];
    assert.strictEqual(GT.point_in_poly(1, 1, poly), true);
    assert.strictEqual(GT.point_in_poly(3, 1, poly), false);
    assert.strictEqual(GT.point_in_poly(-0.01, 1, poly), false);
});
t("select_points rect + z 带", function () {
    var pts = new Float32Array([0, 0, 0.1, 1, 1, 0.5, 5, 5, 1.0, 1.5, 1, 3.0]);
    /* 4 点：(0,0,0.1)(1,1,0.5)(5,5,1.0)(1.5,1,3.0) —— 都在 z 带外 */
    var sel = { type: "rect", x0: 0, y0: 0, x1: 2, y1: 2 };
    var out = GT.select_points(pts, sel, 0.05, 2.0);
    assert.strictEqual(out.length, 2);           /* 0 和 1 */
    assert.deepStrictEqual(out.sort(), [0, 1]);
});
t("select_points circle (模型建议半径)", function () {
    /* pts: (0,0,1),(1,0,1),(3,0,1),(2,0,1) — 后两个 r≥2 应排 */
    var pts = new Float32Array([0, 0, 1, 1, 0, 1, 3, 0, 1, 2, 0, 1]);
    var sel = { type: "circle", x: 0, y: 0, r_xy: 1.5 };
    var out = GT.select_points(pts, sel, 0, 2);
    assert.deepStrictEqual(out.sort(), [0, 1]);
});

/* ---------- 3. 坐标往返 ---------- */
t("RT 应用 + 逆应用 接近恒等", function () {
    var src = [1.3, 2.5, -0.7];
    var lev = GT.apply_rt_point(GT.RT.R, GT.RT.T, src[0], src[1], src[2]);
    var back = GT.apply_rt_inverse(GT.RT.R, GT.RT.T, lev[0], lev[1], lev[2]);
    assert(Math.abs(back[0] - src[0]) < 1e-4, "x drift " + Math.abs(back[0] - src[0]));
    assert(Math.abs(back[1] - src[1]) < 1e-4, "y drift");
    assert(Math.abs(back[2] - src[2]) < 1e-4, "z drift");
});

/* ---------- 4. split / map ---------- */
t("split_frame_indices 过滤 (0,0,0)/NaN", function () {
    /* 4 个 raw 点：valid, zero, NaN, valid */
    var raw = new Float32Array([
        1, 2, 3, 9,  0, 0, 0,
        0, 0, 0, 8,  0, 0, 0,                  /* 全零 → 滤 */
        NaN, 0, 0, 7, 0, 0, 0,                /* NaN → 滤 */
        4, 5, 6, 6,  0, 0, 0,
    ]);
    var sp = GT.split_frame_indices(raw, 7);
    assert.strictEqual(sp.n_leveled, 2);
    assert(sp.leaf_of_raw[0] === 0 && sp.leaf_of_raw[1] === -1 && sp.leaf_of_raw[2] === -1 && sp.leaf_of_raw[3] === 1);
    assert(sp.raw_of_leaf[0] === 0 && sp.raw_of_leaf[1] === 3);
});

/* ---------- 5. 对象构造 ---------- */
t("make_object 契约字段齐全", function () {
    var o = GT.make_object({
        session_id: "cap_1", frame_idx: 3, timestamp: 100.5, seq: 3,
        shape: { type: "rect", x0: 1, y0: 1, x1: 2, y1: 2 },
        class_name: "PERSON", z_min: 0.05, z_max: 2.0,
        raw_point_indices: ["s", 0, 1, 2], point_count: 3,
        source: "human", review_status: "unreviewed", annotator: "A",
    });
    assert.strictEqual(o.session_id, "cap_1");
    assert.strictEqual(o.class_name, "PERSON");
    assert.strictEqual(o.track_id, "P1");          /* PERSON 默认 P1 */
    assert.strictEqual(o.coordinate_frame, "leveled-IFW192S");
    assert.strictEqual(o.leveling_transform_id, GT.TRANSFORM_ID);
    assert.strictEqual(o.schema_version, "gt_workbench/1");
    assert(o.point_count > 0);
});
t("PERSON 必须 track_id — 缺时自动 P1", function () {
    var o = GT.make_object({
        session_id: "x", frame_idx: 0, timestamp: 0, seq: 0,
        shape: { type: "rect", x0: 0, y0: 0, x1: 1, y1: 1 },
        class_name: "PERSON", z_min: 0, z_max: 2,
        raw_point_indices: ["s", 1], point_count: 1,
        source: "human", review_status: "unreviewed",
    });
    assert.strictEqual(o.track_id, "P1");
});

/* ---------- 6. undo / redo ---------- */
t("undo/redo 恢复对象 map", function () {
    var doc = GT.make_session_doc("cap_t", { points: "h", meta: "h" }, "A");
    var snap0 = GT.doc_snapshot_objects(doc);
    var u = GT.undo_new();
    u = GT.undo_push(u, snap0);
    var o = GT.make_object({
        session_id: "cap_t", frame_idx: 0, timestamp: 0, seq: 0,
        shape: { type: "rect", x0: 0, y0: 0, x1: 1, y1: 1 },
        class_name: "PERSON", z_min: 0, z_max: 2,
        raw_point_indices: ["s", 5], point_count: 1,
        source: "human", review_status: "unreviewed",
    });
    GT.doc_add_object(doc, o);
    assert.strictEqual(Object.keys(doc.objects).length, 1);
    var cur = GT.doc_snapshot_objects(doc);
    var r = GT.undo_undo(u, cur);
    assert.strictEqual(Object.keys(r.objects).length, 0);
    var r2 = GT.undo_redo(r.stack, cur);
    assert.strictEqual(Object.keys(r2.objects).length, 1);
});

/* ---------- 7. 传播不冒充人工 ---------- */
t("propagate_object source=propagated / unreviewed", function () {
    var src = GT.make_object({
        session_id: "cap_a", frame_idx: 5, timestamp: 0.5, seq: 5,
        shape: { type: "rect", x0: 1, y0: 1, x1: 2, y1: 2 },
        class_name: "PERSON", z_min: 0, z_max: 2,
        raw_point_indices: ["s", 10], point_count: 1,
        source: "human", review_status: "reviewed", track_id: "P2",
    });
    var c = GT.propagate_object(src, 6, 0.6, {});
    assert.strictEqual(c.source, "propagated");
    assert.strictEqual(c.review_status, "unreviewed");
    assert.strictEqual(c.parent_object_id, src.object_id);
    assert.strictEqual(c.frame_idx, 6);
    assert.strictEqual(c.track_id, "P2");       /* 双人交叉：track 跟随，不靠最近合并 */
    assert(c.raw_point_indices === undefined);
    assert(c.point_count === undefined);
});

/* ---------- 8. 双人交叉 / TrackID 唯一 ---------- */
t("validate_doc 同帧 track_id 冲突", function () {
    var doc = GT.make_session_doc("cap_a", { points: "h" }, "A");
    for (var i = 0; i < 2; i++) {
        var o = GT.make_object({
            session_id: "cap_a", frame_idx: 7, timestamp: 7, seq: 7,
            shape: { type: "rect", x0: i, y0: i, x1: i + 0.5, y1: i + 0.5 },
            class_name: "PERSON", z_min: 0, z_max: 2,
            raw_point_indices: ["s", 100 + i], point_count: 1,
            source: "human", review_status: "unreviewed", track_id: "P1",
            object_id: "_o" + i,
        });
        GT.doc_add_object(doc, o);
    }
    var errs = GT.validate_doc(doc);
    assert(errs.length > 0, "同帧 track 重复必须报错");
    assert(errs.some(function (e) { return e.indexOf("track") >= 0; }), errs.join("|"));
});

/* ---------- 9. GT level 诚实 ---------- */
t("空 doc → UNKNOWN；含 model 但不 reviewed 不 → HUMAN_VERIFIED", function () {
    var doc = GT.make_session_doc("cap_a", { points: "h" }, "A");
    assert.strictEqual(GT.compute_gt_level(doc), "UNKNOWN");
    var o = GT.make_object({
        session_id: "cap_a", frame_idx: 0, timestamp: 0, seq: 0,
        shape: { type: "rect", x0: 0, y0: 0, x1: 1, y1: 1 },
        class_name: "PERSON", z_min: 0, z_max: 2,
        raw_point_indices: ["s", 1], point_count: 1,
        source: "model", review_status: "unreviewed",
    });
    GT.doc_add_object(doc, o);
    assert.strictEqual(GT.compute_gt_level(doc), "PSEUDO_LABEL");
    /* 人工 reviewed 但 review_status 面板未拉 reviewed → 最多 HUMAN_UNVERIFIED */
    o.source = "human"; o.review_status = "reviewed";
    assert.strictEqual(GT.compute_gt_level(doc), "HUMAN_UNVERIFIED");
    doc.review_status = "reviewed";
    assert.strictEqual(GT.compute_gt_level(doc), "HUMAN_VERIFIED");
});

/* ---------- 10. 审核守卫（模型建议不冒充 GT） ---------- */
t("validate_doc: reviewed 但 source≠human 报错", function () {
    var doc = GT.make_session_doc("cap_x", { points: "h" }, "A");
    var o = GT.make_object({
        session_id: "cap_x", frame_idx: 1, timestamp: 1, seq: 1,
        shape: { type: "rect", x0: 0, y0: 0, x1: 1, y1: 1 },
        class_name: "PERSON", z_min: 0, z_max: 2,
        raw_point_indices: ["s", 1], point_count: 1,
        source: "model", review_status: "reviewed",   /* 伪装的假 reviewed */
    });
    GT.doc_add_object(doc, o);
    var errs = GT.validate_doc(doc);
    assert(errs.some(function (e) { return e.indexOf("reviewed") >= 0 && e.indexOf("model") >= 0; }), errs.join());
});

/* ---------- 11. 断点发现 ---------- */
t("find_breaks: 出现/消失/跳帧", function () {
    var fm = {
        "0": [{ track_id: "P1" }], "1": [{ track_id: "P1" }],
        "2": [], /* 消失 */
        "4": [{ track_id: "P1" }],   /* 出现，但 3 缺 → gap */
        "6": [{ track_id: "P2" }],
    };
    var out = GT.find_breaks(fm, ["P1", "P2"]);
    var kinds = out.map(function (b) { return b.kind; });
    assert(kinds.indexOf("disappear") >= 0);
    assert(kinds.indexOf("appear") >= 0);
    assert(kinds.indexOf("gap") >= 0);
});

/* ---------- 12. 请求双向一致性 (doc 序列化往返) ---------- */
t("doc JSON round-trip", function () {
    var doc = GT.make_session_doc("cap_r", { points: "h" }, "A");
    var o = GT.make_object({
        session_id: "cap_r", frame_idx: 2, timestamp: 0.2, seq: 2,
        shape: { type: "poly", poly: [[0, 0], [1, 0], [1, 1], [0, 1]] },
        class_name: "FURNITURE", z_min: 0, z_max: 2,
        raw_point_indices: ["s", 1, 2, 3], point_count: 3,
        source: "human", review_status: "unreviewed",
    });
    GT.doc_add_object(doc, o);
    var back = JSON.parse(JSON.stringify(doc));
    var o2 = back.objects[o.object_id];
    assert.deepStrictEqual(o2.polygon_xy, o.polygon_xy);
    assert.strictEqual(o2.point_count, 3);
    assert(back.frames_objects["2"].indexOf(o.object_id) >= 0);
});

/* ---------- 13. 进度统计 ---------- */
t("session_progress 覆盖工单 §5 列项", function () {
    var doc = GT.make_session_doc("cap_p", { points: "h" }, "A");
    for (var i = 0; i < 3; i++) {
        var o = GT.make_object({
            session_id: "cap_p", frame_idx: i, timestamp: i, seq: i,
            shape: { type: "rect", x0: i, y0: i, x1: i + 0.5, y1: i + 0.5 },
            class_name: i === 2 ? "FURNITURE" : "PERSON",
            z_min: 0, z_max: 2, raw_point_indices: ["s", i], point_count: 1,
            source: "human", review_status: i === 0 ? "reviewed" : "unreviewed",
            track_id: i === 2 ? null : "P1", object_id: "_x" + i,
        });
        GT.doc_add_object(doc, o);
    }
    var p = GT.session_progress(doc, 10);
    assert.strictEqual(p.total_frames, 10);
    assert.strictEqual(p.annotated_frames, 3);
    assert.strictEqual(p.reviewed_frames, 1);
    assert.strictEqual(p.unknown_frames, 7);
    assert.strictEqual(p.person_objects, 2);
    assert.strictEqual(p.furniture_objects, 1);
    assert.strictEqual(p.track_ids, 1);
});

/* ---------- 14. 覆盖率/双人交叉分离 ---------- */
t("双人交叉各自 track 隔离：P1 消失 ≠ P2 消失", function () {
    var fm = { "0": [{ track_id: "P1" }, { track_id: "P2" }],
               "1": [{ track_id: "P2" }] };                 /* P1 走了 */
    var out = GT.find_breaks(fm, ["P1", "P2"]);
    var p1_disappear = out.filter(function (b) { return b.kind === "disappear" && b.track_id === "P1"; });
    var p2_disappear = out.filter(function (b) { return b.kind === "disappear" && b.track_id === "P2"; });
    assert.strictEqual(p1_disappear.length, 1);
    assert.strictEqual(p2_disappear.length, 0);
});

/* ---------- 15. 线性插值（I 键） ---------- */
t("interpolate_shapes: circle 三点均匀插", function () {
    var src = { x: 1, y: 2, r_xy: 0.5 };
    var dst = { x: 5, y: 6, r_xy: 1.0 };
    var out = GT.interpolate_shapes(src, dst, 3);
    assert.strictEqual(out.length, 3);
    assert.strictEqual(out[0].type, "circle");
    /* t=1/4: x=1+(5-1)/4=2, y=2+(6-2)/4=3, r=0.5+(1-0.5)/4=0.625 */
    assert(Math.abs(out[0].x - 2) < 1e-9);
    assert(Math.abs(out[0].y - 3) < 1e-9);
    assert(Math.abs(out[0].r_xy - 0.625) < 1e-9);
    /* t=3/4: x=4, y=5 */
    assert(Math.abs(out[2].x - 4) < 1e-9);
});
t("interpolate_shapes: rect 四角分量独立线性", function () {
    var src = { box_xy: [0, 0, 2, 2] };
    var dst = { box_xy: [4, 4, 6, 6] };
    var out = GT.interpolate_shapes(src, dst, 1);
    assert.strictEqual(out.length, 1);
    assert.deepStrictEqual(out[0], { type: "rect", x0: 2, y0: 2, x1: 4, y1: 4 });
});
t("interpolate_shapes: poly 顶点数不匹配 → 空数组（拒绝插）", function () {
    var a = { polygon_xy: [[0, 0], [1, 0], [1, 1]] };
    var b = { polygon_xy: [[0, 0], [1, 0], [1, 1], [0, 1]] };
    var out = GT.interpolate_shapes(a, b, 2);
    assert.strictEqual(out.length, 0);
});
t("interpolate_shapes: poly 顶点数匹配 → 逐顶点插", function () {
    var a = { polygon_xy: [[0, 0], [2, 0], [2, 2], [0, 2]] };
    var b = { polygon_xy: [[4, 4], [6, 4], [6, 6], [4, 6]] };
    var out = GT.interpolate_shapes(a, b, 1);
    assert.strictEqual(out.length, 1);
    assert.deepStrictEqual(out[0].poly, [[2, 2], [4, 2], [4, 4], [2, 4]]);
});
t("shape_of_object: 三种形态归一", function () {
    var o1 = { polygon_xy: [[0, 0], [1, 0], [1, 1]] };
    var o2 = { box_xy: [0, 0, 1, 1] };
    var o3 = { x: 2, y: 3, r_xy: 0.4 };
    assert.deepStrictEqual(GT.shape_of_object(o1), { polygon_xy: o1.polygon_xy });
    assert.deepStrictEqual(GT.shape_of_object(o2), { box_xy: o2.box_xy });
    assert.deepStrictEqual(GT.shape_of_object(o3), { x: 2, y: 3, r_xy: 0.4 });
});

/* ---------- 16. R3 修复回归（防退步）---------- */
t("R3-Q1: 同帧多对象 object_id 不冲突（mk_object_id_unique）", function () {
    var id1 = GT.mk_object_id_unique(5, 1);
    var id2 = GT.mk_object_id_unique(5, 2);
    var id3 = GT.mk_object_id_unique(5, 3);
    assert(id1 !== id2 && id2 !== id3 && id1 !== id3, id1 + "|" + id2);
    /* 同帧用旧 mk_object_id 是缺陷 —不得在生产代码中再让它默认产生冲突 id */
    var doc = GT.make_session_doc("cap_s9", { points: "h" }, "A");
    function mk(tid) {
        return GT.make_object({
            session_id: "cap_s9", frame_idx: 5, timestamp: 5, seq: 4262546,
            object_id: GT.mk_object_id_unique(5, ++mk._n),
            shape: { type: "rect", x0: 0, y0: 0, x1: 1, y1: 1 },
            class_name: "PERSON", z_min: 0, z_max: 2,
            raw_point_indices: ["s", 1], point_count: 1,
            source: "human", review_status: "unreviewed", track_id: tid,
        });
    }
    mk._n = 0;
    var p1 = mk("P1"), p2 = mk("P2");
    GT.doc_add_object(doc, p1);
    GT.doc_add_object(doc, p2);
    assert.strictEqual(Object.keys(doc.objects).length, 2, "S9 双人同帧必须能并存");
    assert.strictEqual(doc.frames_objects["5"].length, 2);
});
t("R3-Q1 哨兵: 重 id 时 doc_add_object 抛错不静默覆盖", function () {
    var doc = GT.make_session_doc("cap_x", { points: "h" }, "A");
    var o = GT.make_object({
        session_id: "cap_x", frame_idx: 0, timestamp: 0, seq: 0,
        object_id: "fixed_id",
        shape: { type: "rect", x0: 0, y0: 0, x1: 1, y1: 1 },
        class_name: "PERSON", z_min: 0, z_max: 2,
        raw_point_indices: ["s", 1], point_count: 1,
        source: "human", review_status: "unreviewed",
    });
    GT.doc_add_object(doc, o);
    /* 用同 id 再放一个 应抛 — 不能静默覆盖 */
    var threw = false;
    try {
        GT.doc_add_object(doc, o);
    } catch (e) { threw = true; }
    assert(threw, "重复 object_id 必须抛");
    assert.strictEqual(Object.keys(doc.objects).length, 1);
});
t("R3-Q6: propagate_object 不再传染 is_keyframe", function () {
    var src = GT.make_object({
        session_id: "cap_a", frame_idx: 3, timestamp: 0.3, seq: 3,
        shape: { type: "rect", x0: 0, y0: 0, x1: 1, y1: 1 },
        class_name: "PERSON", z_min: 0, z_max: 2,
        raw_point_indices: ["s", 1], point_count: 1,
        source: "human", review_status: "reviewed",
    });
    src.is_keyframe = true;
    var c = GT.propagate_object(src, 4, 0.4, {});
    assert.strictEqual(c.is_keyframe, undefined);
});
t("R3-Q10: WASD 移框 y 方向 = leveled +y (W=上移)", function () {
    var o = GT.make_object({
        session_id: "x", frame_idx: 0, timestamp: 0, seq: 0,
        shape: { type: "rect", x0: 0, y0: 0, x1: 1, y1: 1 },
        class_name: "PERSON", z_min: 0, z_max: 2,
        raw_point_indices: ["s", 1], point_count: 1,
        source: "human", review_status: "unreviewed",
    });
    GT.translate_shape(o, 0, +0.05);     /* W 应产生 leveled +y */
    assert.strictEqual(o.box_xy[1], 0.05);
    assert.strictEqual(o.box_xy[3], 1.05);
});

console.log("\n" + pass + " PASS, " + fail + " FAIL");
process.exit(fail ? 1 : 0);

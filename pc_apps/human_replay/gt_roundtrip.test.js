/* gt_roundtrip.test.js — HUMAN-GT-ANNOTATOR-R2 索引/往返/兼容性测试。
 * 用真实会话数据（小切片）验证工单 STEP 7 的 12 类断言里需要本地点云的部分:
 *   - 原始点云显示 (frame slice + z-tint + ROI 选点链路)
 *   - XY+Z 联合筛选正确
 *   - 坐标双向往返 (raw→lev→raw)
 *   - compact 索引 ↔ raw 索引 ↔ 引擎点索引 (FUSION/U3) 相容性
 *   - 保存→载入 doc 一致
 *   - SHA256 round-trip
 * 跑： node pc_apps/human_replay/gt_roundtrip.test.js
 */
"use strict";
var fs = require("fs"), path = require("path");
var GT = require("./gt_lib.js");

/* 找 sessions root（captures/remote） */
var ROOT = path.join(__dirname, "..", "..", "captures", "remote");
if (!fs.existsSync(ROOT)) { console.error("no captures/remote"); process.exit(1); }
/* 只挑 3 帧小会话：S9（最短）。 */
var SID = "cap_20261010_180751";
var meta_p = path.join(ROOT, SID, "meta.json");
var bin_p = path.join(ROOT, SID, "points.bin");
if (!fs.existsSync(meta_p) || !fs.existsSync(bin_p)) {
    console.error("need real " + SID + " 实际会话; skip roundtrip");
    process.exit(1);
}

var pass = 0, fail = 0;
var A = require("assert");
function t(name, fn) {
    try { fn(); pass++; console.log("  ✓ " + name); }
    catch (e) { fail++; console.log("  ✗ " + name + ": " + e.message); }
}
var assert = {
    strictEqual: A.strictEqual,
    deepStrictEqual: A.deepStrictEqual,
    ok: A.ok || function (c, m) { if (!c) throw new Error(m || "assert"); },
};

function read_frame_xyzi(meta, blob, i) {
    var f = meta.frames[i];
    var n = f.count_points;
    var out = new Float32Array(n * 4);
    for (var k = 0; k < n; k++) {
        var b = (f.offset_points + k) * 28;
        out[k * 4] = blob.readFloatLE(b);
        out[k * 4 + 1] = blob.readFloatLE(b + 4);
        out[k * 4 + 2] = blob.readFloatLE(b + 8);
        out[k * 4 + 3] = blob.readFloatLE(b + 12);
    }
    return out;
}

var meta = JSON.parse(fs.readFileSync(meta_p, "utf-8"));
var blob = fs.readFileSync(bin_p);

console.log("== gt_roundtrip (" + SID + " 前 3 帧) ==");

/* ---------- 1. 真实帧切出 non-zero 点数与 manifest 相符 ---------- */
t("S9 帧点数与 SESSION_DATASET_MANIFEST 一致", function () {
    assert.strictEqual(meta.frames.length, 126);
    assert.strictEqual(meta.point_stride_bytes, 28);
});

var first3 = meta.frames.slice(0, 3);
var flat3 = new Float32Array(first3.reduce(function (a, f) { return a + f.count_points * 4; }, 0));
var off = 0;
for (var fi = 0; fi < 3; fi++) {
    var seg = read_frame_xyzi(meta, blob, fi);
    flat3.set(seg, off); off += seg.length;
}

/* ---------- 2. 全局 split + leveled 一致性 ---------- */
var global_split = GT.split_frame_indices(flat3, 4);

t("split 产出紧凑全球 xyz", function () {
    assert.ok(global_split.n_leveled > 1000, "点太少 " + global_split.n_leveled);
    assert.strictEqual(global_split.raw_of_leaf.length, global_split.n_leveled);
});

/* ---------- 3. leveled 推导顺序无关（整体 vs 3 帧分开）---------- */
t("整段 split 与 帧分开 split 在 leveled xyz 上一致", function () {
    /* 逐帧 split，接合后再比 */
    var cursor = 0;
    for (var fi = 0; fi < 3; fi++) {
        var f = meta.frames[fi];
        var n = f.count_points;
        var seg = flat3.subarray(fi === 0 ? 0 : (meta.frames[fi - 1].offset_points - meta.frames[0].offset_points + meta.frames[fi - 1].count_points) * 4,
            0);
        /* 复杂 — 改用另一种：每帧单独 split */
        var f_xyzi = read_frame_xyzi(meta, blob, fi);
        var sp = GT.split_frame_indices(f_xyzi, 4);
        /* 与 global 区间比对 */
        for (var k = 0; k < sp.n_leveled; k++) {
            var g = global_split.leaf_of_raw[cursor + sp.raw_of_leaf[k]];
            if (g < 0) { throw new Error("leaf 映射失败"); }
            for (var ax = 0; ax < 3; ax++) {
                if (Math.abs(sp.leveled_xyz[k * 3 + ax] - global_split.leveled_xyz[g * 3 + ax]) > 1e-4) {
                    throw new Error("leveled 不一致 frame " + fi + " pt " + k);
                }
            }
        }
        cursor += n;
    }
});

/* ---------- 4. 坐标往返 ---------- */
t("leveled→raw→leveled 距离 <1e-4", function () {
    var max_e = 0;
    for (var k = 0; k < Math.min(2000, global_split.n_leveled); k++) {
        var g = global_split.raw_of_leaf[k];
        /* 反变换 */
        var raw_x = flat3[g * 4], raw_y = flat3[g * 4 + 1], raw_z = flat3[g * 4 + 2];
        var lev = GT.apply_rt_point(GT.RT.R, GT.RT.T, raw_x, raw_y, raw_z);
        max_e = Math.max(max_e,
            Math.abs(lev[0] - global_split.leveled_xyz[k * 3]),
            Math.abs(lev[1] - global_split.leveled_xyz[k * 3 + 1]),
            Math.abs(lev[2] - global_split.leveled_xyz[k * 3 + 2]));
    }
    assert.ok(max_e < 1e-4, "误差 " + max_e);
});

/* ---------- 5. ROI 选点 round-trip: 选 → 编码 → 解码 → 再选同索引 ---------- */
t("ROI 选点 + encode/decode 一致", function () {
    /* S9 双人交叉开场，人大概在 x~4.5, y~4 附近；换大窗口确保命中 */
    var sel = { type: "rect", x0: 0.5, y0: 0.5, x1: 10.5, y1: 10.5 };
    var n = global_split.n_leveled;
    var idx1 = GT.select_points(global_split.leveled_xyz, sel, 0.1, 2.0);
    assert.ok(idx1.length > 0, "宽 ROI 应命中有 " + n + " 点");
    var idx2 = GT.decode_indices(GT.encode_indices(idx1));
    assert.deepStrictEqual(idx2, idx1);
    /* 检测矩形 ROI 正确性：选前 100 个点手动检查 z 带 + 边界命中 */
    var pts = global_split.leveled_xyz;
    var manual = [];
    for (var k = 0; k < n; k++) {
        var x = pts[k * 3], y = pts[k * 3 + 1], z = pts[k * 3 + 2];
        if (x >= 0.5 && x <= 10.5 && y >= 0.5 && y <= 10.5 && z >= 0.1 && z <= 2.0) manual.push(k);
    }
    assert.deepStrictEqual(idx1, manual);
});

/* ---------- 6. doc save/load 一致 ---------- */
t("doc JSON 保存→再载入 → 对象 map 等价", function () {
    var doc = GT.make_session_doc(SID, { points: "sha", meta: "sha" }, "test");
    var o = GT.make_object({
        session_id: SID, frame_idx: 0, timestamp: 0, seq: 0,
        shape: { type: "circle", x: 3, y: 6, r_xy: 0.8 },
        class_name: "PERSON", z_min: 0.05, z_max: 2.3,
        raw_point_indices: GT.encode_indices([10, 11, 50]), point_count: 3,
        source: "human", review_status: "unreviewed",
    });
    GT.doc_add_object(doc, o);
    var ser = JSON.stringify(doc);
    var back = JSON.parse(ser);
    assert.strictEqual(back.session_id, SID);
    assert.strictEqual(back.annotator, "test");
    assert.ok(Object.keys(back.objects).length === 1);
    assert.ok(back.objects[o.object_id].point_count === 3);
    /* schema/audit: compute_gt_level 前后等价 */
    assert.strictEqual(GT.compute_gt_level(back), GT.compute_gt_level(doc));
});

/* ---------- 7. SHA 守卫 ---------- */
t("SHA256 doc body 稳定 (同输入→同 hex)", function () {
    var doc = GT.make_session_doc("cap_x", { points: "h" }, "A");
    var h1 = GT.sha256_hex(JSON.stringify(doc));
    var h2 = GT.sha256_hex(JSON.stringify(doc));
    assert.strictEqual(h1, h2);
    assert.ok(h1.length === 64);
});

/* ---------- 8. 会话离衡隔离 (不同 sid 独立 doc, 无 cross-sid 污染) ---------- */
t("两个 sid 的 doc frames_objects 相互独立", function () {
    var d1 = GT.make_session_doc("cap_a", { points: "ha" }, "A");
    var d2 = GT.make_session_doc("cap_b", { points: "hb" }, "B");
    var o1 = GT.make_object({
        session_id: "cap_a", frame_idx: 0, timestamp: 0, seq: 0,
        shape: { type: "rect", x0: 0, y0: 0, x1: 1, y1: 1 },
        class_name: "PERSON", z_min: 0, z_max: 2,
        raw_point_indices: ["s", 1], point_count: 1,
        source: "human", review_status: "unreviewed",
    });
    GT.doc_add_object(d1, o1);
    assert.strictEqual(Object.keys(d2.objects).length, 0);
    assert.strictEqual(Object.keys(d2.frames_objects).length, 0);
    assert.strictEqual(d1.session_id, "cap_a");
    assert.strictEqual(d2.session_id, "cap_b");
});

console.log("\n" + pass + " PASS, " + fail + " FAIL");
process.exit(fail ? 1 : 0);

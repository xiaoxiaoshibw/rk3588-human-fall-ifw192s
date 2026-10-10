/* test_schema.js — 公共抽象单元测试。node pc_apps/human_core/test_schema.js */
"use strict";
var S = require("./schema.js");

var n_pass = 0, n_fail = 0;
function t(cond, msg) {
    if (cond) { n_pass++; console.log("PASS: " + msg); }
    else { n_fail++; console.log("FAIL: " + msg); }
}

/* FrameContext */
var xyzi = new Float32Array(16); xyzi[0] = 1.0; xyzi[1] = 2.0; xyzi[2] = 0.5; xyzi[3] = 100;
var fc = S.make_frame_context({ session_id: "test", frame_index: 0, timestamp: 1.0, xyzi: xyzi });
t(fc.n_points === 4, "FrameContext n_points=" + fc.n_points);
t(fc.frame_id === "test:0", "FrameContext frame_id=" + fc.frame_id);
try { S.make_frame_context({ session_id: "x", frame_index: 0, xyzi: [1, 2, 3] }); t(false, "非 Float32Array 应抛"); }
catch (e) { t(true, "非 Float32Array 拒绝: " + e.message); }
try { S.make_frame_context({ session_id: "x", frame_index: 0, xyzi: new Float32Array(3) }); t(false, "非 %4 应抛"); }
catch (e) { t(true, "非 %4 拒绝: " + e.message); }

/* Candidate */
var c = S.make_candidate({
    candidate_id: "c1",
    point_indices: new Uint32Array([1, 2, 3]),
    centroid: { x: 1, y: 2, z: 0.5 },
    point_count: 3,
    foreground_source: S.CAND_SRC.FG,
});
var errs = S.validate_candidate(c);
t(errs.length === 0, "有效 candidate validate=" + JSON.stringify(errs));

var c2 = S.make_candidate({ candidate_id: "c2", point_indices: [1, 2], centroid: { x: 1, y: 2, z: 0 }, point_count: 2 });
errs = S.validate_candidate(c2);
t(errs.length > 0, "point_indices 非 Uint32Array 应报错");

/* Track */
var tr = S.make_track({ track_id: 1, status: S.TRACK_STATUS.ACTIVE, confidence: 0.9, age_frames: 5 });
t(tr.track_id === 1 && tr.status === S.TRACK_STATUS.ACTIVE && tr.confidence === 0.9, "Track 构造正确");

/* Diagnostics */
var dg = S.make_diagnostics("s:0");
t(dg.layers.length === 0 && dg.total_ms === 0, "Diagnostics 初始为空");
var L = S.make_layer_diag(S.LAYER.FOREGROUND);
L.in_points = 100; L.out_points = 30; L.elapsed_ms = 1.5;
dg.layers.push(L);
t(dg.layers[0].layer === "foreground" && dg.layers[0].out_points === 30, "LayerDiag 字段正确");

/* GT attestation */
var a1 = S.gt_attestation("x", {});
t(a1.level === S.GT_LEVEL.UNKNOWN, "空 meta → UNKNOWN");
var a2 = S.gt_attestation("x", { human_annotations: [{ source: "human", box: {} }] });
t(a2.level === S.GT_LEVEL.HUMAN_UNVERIFIED, "有 human_annotations → HUMAN_UNVERIFIED");
/* ai_labels → PSEUDO_LABEL (HR09 会话) */
var fs = require("fs"), os = require("os"), path = require("path");
var tmp = fs.mkdtempSync(path.join(os.tmpdir(), "schema_pseudo_"));
fs.writeFileSync(path.join(tmp, "ai_labels.json"), JSON.stringify({
    session_id: "x", labelled_by: "auto_person_label.py+empty-template-bgdiff",
    posture_set: ["stand"], frames: { "0": { posture: "stand", x: 1, y: 1, r_xy: 0.5 } },
}), "utf-8");
var a3 = S.gt_attestation(tmp, {});
t(a3.level === S.GT_LEVEL.PSEUDO_LABEL, "ai_labels → PSEUDO_LABEL (实测 " + a3.level + ")");
t((a3.disclaimer || "").indexOf("非人工 GT") !== -1, "PSEUDO disclaimer 含'非人工 GT'");
fs.rmSync(tmp, { recursive: true, force: true });

console.log("\n== schema: " + n_pass + " PASS, " + n_fail + " FAIL ==");
process.exit(n_fail ? 1 : 0);

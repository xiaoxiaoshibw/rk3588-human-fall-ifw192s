/* evaluate_track_recall.js — R3 STEP 5: track-level recall
 * 按 R2 runs_03 相同算法: accepted tracks 质心 match GT 算 TP/FN/FP。
 * 跑法: R3_SID=<sid> node --max-old-space-size=2048 evaluate_track_recall.js --model <path>
 */
"use strict";
const fs = require("fs"), path = require("path"), crypto = require("crypto");
const E = require("./engine"), D = require("./data_loader"), S = require("./schema");

function main() {
    const SID = process.env.R3_SID || "cap_20261010_175429";
    const ap = process.argv;
    let model = "pc_apps/human_replay/rf_person_v1.json";
    let out = null;
    for (let i = 2; i < ap.length; i++) {
        if (ap[i] === "--model") model = ap[++i];
        else if (ap[i] === "--out") out = ap[++i];
    }
    const sess = D.load_session(path.join("captures", "remote", SID));
    const eng = new E.UnifiedEngine({ mode: "FUSION" });
    eng.rf.init(fs.readFileSync(model, "utf8"));
    eng.rf_model_sha = crypto.createHash("sha256").update(fs.readFileSync(model)).digest("hex");
    eng.begin_session(SID);

    const gate = 0.5;
    let tp = 0, fn = 0, fp = 0;
    const per_frame = [];

    /* 读 GT (最新非 e2e 版) */
    const manifest = JSON.parse(fs.readFileSync(
        `pc_apps/human_replay/gt_store/${SID}/manifest.json`, "utf8"));
    const usable = manifest.versions.filter(v => v.annotator !== "e2e");
    const gt_ver = usable.length ? usable[usable.length - 1].version : manifest.versions[0].version;
    const gt_all = JSON.parse(fs.readFileSync(
        `pc_apps/human_replay/gt_store/${SID}/GT_${gt_ver}.json`, "utf8"));

    for (let i = 0; i < sess.frames.length; i++) {
        const f = sess.frames[i];
        const fc = S.make_frame_context({
            session_id: SID, session_generation: 1, frame_index: i,
            timestamp: f.timestamp, xyzi: f.xyzi, meta: sess.meta,
        });
        const diag = eng.tick(fc);
        /* track 级: 用当前 fusion tracks (human_confirmed) */
        const tracks = (diag._tracks || []).filter(t => t.human_confirmed);
        /* GT */
        const fo = gt_all.frames_objects[String(i)] || [];
        const gts = fo.map(oid => gt_all.objects[oid])
            .filter(o => o.class_name === "PERSON")
            .map(o => ({ x: o.x, y: o.y }));
        const used = new Set();
        let f_tp = 0;
        for (const g of gts) {
            let hit = -1, hd = gate;
            for (let j = 0; j < tracks.length; j++) {
                if (used.has(j)) continue;
                const d = Math.hypot(g.x - tracks[j].x, g.y - tracks[j].y);
                if (d < hd) { hd = d; hit = j; }
            }
            if (hit >= 0) { used.add(hit); f_tp++; }
        }
        const f_fn = gts.length - f_tp;
        const f_fp = tracks.length - f_tp;
        tp += f_tp; fn += f_fn; fp += f_fp;
        per_frame.push({ frame_index: i, tp: f_tp, fn: f_fn, fp: f_fp, n_gt: gts.length, n_tracks: tracks.length });
    }
    const result = {
        sid: SID, model, rf_sha_16: eng.rf_model_sha.slice(0, 16), gate, gt_version: gt_ver,
        track_metric: {
            tp, fn, fp,
            recall: tp + fn ? +(tp / (tp + fn)).toFixed(4) : null,
            precision: tp + fp ? +(tp / (tp + fp)).toFixed(4) : null,
        },
        per_frame,
    };
    if (out) fs.writeFileSync(out, JSON.stringify(result, null, 1));
    console.log(JSON.stringify({
        rf_sha_16: result.rf_sha_16, recall: result.track_metric.recall,
        precision: result.track_metric.precision,
        tp, fn, fp,
    }, null, 1));
}
main();

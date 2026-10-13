/* evaluate_v3_s3near.js — R3 STEP 5: 用 rf_person_v3.json 跑 S3-near (175429) FUSION,
 * 输出 recall/precision/track metrics, 与 R2 v1/v2 对照。
 * 关键: 检查 walk-near 召回是否回到 v1 水平 (v1=99.2%, v2=35.7%).
 *
 * 跑法: node evaluate_v3_s3near.js --model <path-to-rf_json> --out <JSON>
 */
"use strict";
const fs = require("fs"), path = require("path"), crypto = require("crypto");
const E = require("./engine"), D = require("./data_loader"), S = require("./schema");

const SID = process.env.R3_SID || "cap_20261010_175429";

function main() {
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

    const frames = [];
    for (let i = 0; i < sess.frames.length; i++) {
        const f = sess.frames[i];
        const fc = S.make_frame_context({
            session_id: SID, session_generation: 1, frame_index: i,
            timestamp: f.timestamp, xyzi: f.xyzi, meta: sess.meta,
        });
        const diag = eng.tick(fc);
        /* 提取所有 fusion candidates + tracks */
        frames.push({
            frame_index: i,
            candidates: (diag._candidates || []).map(c => ({
                id: c.candidate_id, x: c.centroid.x, y: c.centroid.y, z: c.centroid.z,
                n: c.point_count, prob: c.scores && c.scores.rf51 ? c.scores.rf51.prob : null,
                decision: c.classifier_decision,
                accepted: /HUMAN/.test(c.classifier_decision || ""),
                track_id: c.track_id, src: c.fusion_source_SRC || c.foreground_source,
            })),
        });
    }
    /* 用 GT 判 recall */
    const GT = require("../human_replay/gt_lib.js");
    const manifest = JSON.parse(fs.readFileSync(
        `pc_apps/human_replay/gt_store/${SID}/manifest.json`, "utf8"));
    const usable = manifest.versions.filter(v => v.annotator !== "e2e");
    const gt_ver = process.env.R3_GT_VERSION || usable[usable.length - 1].version;
    const gt_all = JSON.parse(fs.readFileSync(
        `pc_apps/human_replay/gt_store/${SID}/GT_${gt_ver}.json`, "utf8"));
    const gate = 0.5;
    let tp = 0, fn = 0, fp = 0;
    const per_frame = [];
    for (let i = 0; i < frames.length; i++) {
        const fo = gt_all.frames_objects[String(i)] || [];
        const gts = fo.map(oid => gt_all.objects[oid])
            .filter(o => o.class_name === "PERSON")
            .map(o => ({ x: o.x, y: o.y }));
        const preds = frames[i].candidates.filter(c => c.accepted);
        const used = new Set();
        let f_tp = 0;
        for (const g of gts) {
            let hit = -1, hd = gate;
            for (let j = 0; j < preds.length; j++) {
                if (used.has(j)) continue;
                const d = Math.hypot(g.x - preds[j].x, g.y - preds[j].y);
                if (d < hd) { hd = d; hit = j; }
            }
            if (hit >= 0) { used.add(hit); f_tp++; }
        }
        const f_fn = gts.length - f_tp;
        const f_fp = preds.length - f_tp;
        tp += f_tp; fn += f_fn; fp += f_fp;
        per_frame.push({ frame_index: i, tp: f_tp, fn: f_fn, fp: f_fp, n_gt: gts.length, n_pred: preds.length });
    }
    const result = {
        model: model,
        rf_sha_16: eng.rf_model_sha.slice(0, 16),
        sid: SID, gate, frames: frames.length,
        candidate: {
            tp, fn, fp,
            recall: tp + fn ? +(tp / (tp + fn)).toFixed(4) : null,
            precision: tp + fp ? +(tp / (tp + fp)).toFixed(4) : null,
        },
        per_frame,
    };
    if (out) fs.writeFileSync(out, JSON.stringify(result, null, 1));
    console.log(JSON.stringify({
        rf_sha_16: result.rf_sha_16,
        candidate: result.candidate,
    }, null, 1));
}
main();

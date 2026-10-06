/* 单帧 before/after 簇对照：确认 R2.6 的 +1 簇是否为分裂
 * 用法：node inspect_split.js <sid> <frameIdx>
 */
"use strict";
const fs = require("fs");
const path = require("path");
const REPO = path.resolve(__dirname, "..", "..", "..", "..");
const RP = path.join(REPO, "pc_apps", "human_replay");
const RL = require(path.join(RP, "human_replay_lib.js"));
const PL = require(path.join(RP, "human_pipe_lib.js"));

const sid = process.argv[2], fi = Number(process.argv[3] || 16);
const dir = path.join(REPO, "captures", "remote", sid);
const meta = JSON.parse(fs.readFileSync(path.join(dir, "meta.json"), "utf8"));
const raw = fs.readFileSync(path.join(dir, "points.bin"));
const f32 = new Float32Array(raw.buffer, raw.byteOffset, raw.byteLength / 4);
const frames = RL.frame_slice(meta);
const STRIDE = RL.STRIDE_F32;

const ded = frames.map(f => PL.denoise(RL.strided_f32_copy(f32, f.start_pts, f.count, STRIDE)));
const sm = PL.build_static_map(ded, { drop_ground: true });

function clustersOf(pts, tracker, frameIdx) {
    const rawC = PL.cluster_voxels(PL.voxelize(pts));
    const ev = PL.evidence_postpass(pts, rawC);
    const out = [];
    for (let i = 0; i < rawC.length; i++) {
        const f = PL.cluster_features(rawC[i]);
        if (!f.ok) continue;
        const c = PL.classify_human(f);
        f.label = c.label;
        f.evidence_tag = PL.evidence_label(ev.clusters_extra[i]);
        f.joint = PL.joint_status(f);
        out.push(f);
    }
    tracker.tick(frameIdx, out);
    return out;
}
function show(tag, cs) {
    console.log(tag + " n=" + cs.length);
    for (const c of cs) {
        console.log("  (" + c.cx.toFixed(2) + "," + c.cy.toFixed(2) + ") z=" + c.zmin.toFixed(2)
            + ".." + (c.zmin + c.height_m).toFixed(2) + " h=" + c.height_m.toFixed(2)
            + " n=" + c.n + " " + c.joint + "/" + c.evidence_tag.label
            + " track=" + c.track_id + (c.track_confirmed ? "*" : ""));
    }
}
const f = frames[fi];
const slice = RL.strided_f32_copy(f32, f.start_pts, f.count, STRIDE);
const clean = PL.denoise(slice);
const fg = PL.extract_foreground(clean, sm);
const before = clustersOf(fg.fg_xyzi, new PL.Tracker(), fi);
const iso = PL.cleanup_isolated_fg(fg.fg_xyzi);
const after = clustersOf(iso.xyzi, new PL.Tracker(), fi);
console.log("frame " + fi + " fg " + fg.n_fg + " -> " + iso.after + " removed " + iso.removed_points
    + " (" + iso.removed_voxels + " voxels)");
show("BEFORE", before);
show("AFTER", after);

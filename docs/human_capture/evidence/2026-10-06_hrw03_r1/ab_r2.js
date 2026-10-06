/* W03-R2 A/B：用生产函数逐帧跑全链路，统计簇/联合判定/工作空间/保留人
 * 用法：node ab_r2.js <sid> [sid2 ...]
 */
"use strict";
const fs = require("fs");
const path = require("path");
const REPO = path.resolve(__dirname, "..", "..", "..", "..");
const RP = path.join(REPO, "pc_apps", "human_replay");
const RL = require(path.join(RP, "human_replay_lib.js"));
const PL = require(path.join(RP, "human_pipe_lib.js"));

function run(sid) {
    const dir = path.join(REPO, "captures", "remote", sid);
    const meta = JSON.parse(fs.readFileSync(path.join(dir, "meta.json"), "utf8"));
    const raw = fs.readFileSync(path.join(dir, "points.bin"));
    const f32 = new Float32Array(raw.buffer, raw.byteOffset, raw.byteLength / 4);
    const frames = RL.frame_slice(meta);
    const STRIDE = RL.STRIDE_F32;
    const ded = frames.map(f => PL.denoise(RL.strided_f32_copy(f32, f.start_pts, f.count, STRIDE)));
    const sm = PL.build_static_map(ded, { drop_ground: true });
    let strong = 0, sup = 0;
    sm.forEach(v => { if (v.tier === "strong") strong++; else sup++; });

    const tracker = new PL.Tracker();
    let fgSum = 0, nClusters = 0, high = 0, tall = 0, confirmed = 0;
    const joint = {}, ev = {}, perFrame = [];
    for (let i = 0; i < frames.length; i++) {
        const f = frames[i];
        const slice = RL.strided_f32_copy(f32, f.start_pts, f.count, STRIDE);
        const r = PL.pipeline_frame(slice, i, { static_keys: sm, tracker: tracker });
        fgSum += r.n_foreground;
        perFrame.push(r.clusters.length);
        for (const c of r.clusters) {
            nClusters++;
            if (c.zmin > 2.2) high++;
            if (c.height_m > 2.3) tall++;
            joint[c.joint] = (joint[c.joint] || 0) + 1;
            ev[c.evidence_tag.label] = (ev[c.evidence_tag.label] || 0) + 1;
            if (c.joint === "CONFIRMED_HUMAN" && c.track_confirmed) confirmed++;
        }
    }
    const med = perFrame.slice().sort((a, b) => a - b)[perFrame.length >> 1];
    const line = {
        sid, frames: frames.length, static: sm.size, strong, supported: sup,
        fg_per_frame: Math.round(fgSum / frames.length),
        clusters: nClusters, per_frame_med: med, zmin_gt_2_2: high, height_gt_2_3: tall,
        confirmed_frames_clusters: confirmed, joint, evidence: ev,
    };
    console.log(JSON.stringify(line));
    return line;
}
for (const sid of process.argv.slice(2)) run(sid);

/* HR-W03 背景占用率门槛扫描（只读，不改生产代码）
 * 对同一会话扫 bg_occupancy_ratio，统计：
 *   静态柱数 / 前景点数 / 簇数 / zmin>2.2 的簇数 / 标签分布
 * 用法：node sweep_bg_ratio.js <sid> [ratio,ratio,...]
 */
"use strict";
const fs = require("fs");
const path = require("path");
const REPO = path.resolve(__dirname, "..", "..", "..", "..");
const RP = path.join(REPO, "pc_apps", "human_replay");
const RL = require(path.join(RP, "human_replay_lib.js"));
const PL = require(path.join(RP, "human_pipe_lib.js"));

const sid = process.argv[2] || "cap_20261002_223757";
const ratios = (process.argv[3] || "0.95,0.92,0.90,0.88,0.85,0.80").split(",").map(Number);
const dir = path.join(REPO, "captures", "remote", sid);
const meta = JSON.parse(fs.readFileSync(path.join(dir, "meta.json"), "utf8"));
const raw = fs.readFileSync(path.join(dir, "points.bin"));
const f32 = new Float32Array(raw.buffer, raw.byteOffset, raw.byteLength / 4);
const frames = RL.frame_slice(meta);
const ded = frames.map(function (f) {
    return PL.denoise(RL.strided_f32_copy(f32, f.start_pts, f.count, RL.STRIDE_F32));
});

const rows = [];
for (const r of ratios) {
    PL.PIPE.bg_occupancy_ratio = r;
    const staticKeys = PL.build_static_map(ded, { drop_ground: true });
    let fgSum = 0, nClusters = 0, high = 0, tall = 0, tags = {};
    for (let i = 0; i < frames.length; i++) {
        const f = frames[i];
        const slice = RL.strided_f32_copy(f32, f.start_pts, f.count, RL.STRIDE_F32);
        const clean = PL.denoise(slice);
        const fg = PL.extract_foreground(clean, staticKeys);
        fgSum += fg.n_fg;
        const rawC = PL.cluster_voxels(fg.vox_fg);
        const ev = PL.evidence_postpass(fg.fg_xyzi, rawC);
        for (let ci = 0; ci < rawC.length; ci++) {
            const feat = PL.cluster_features(rawC[ci]);
            if (!feat.ok) continue;
            nClusters++;
            if (feat.zmin > 2.2) high++;
            if (feat.height_m > 2.3) tall++;
            const tag = PL.evidence_label(ev.clusters_extra[ci]).label;
            tags[tag] = (tags[tag] || 0) + 1;
        }
    }
    rows.push({ ratio: r, static_cols: staticKeys.size,
                fg_pts_per_frame: Math.round(fgSum / frames.length),
                clusters: nClusters, zmin_gt_2_2: high, height_gt_2_3: tall, tags: tags });
}
console.log(JSON.stringify({ sid: sid, frames: frames.length, rows: rows }, null, 1));

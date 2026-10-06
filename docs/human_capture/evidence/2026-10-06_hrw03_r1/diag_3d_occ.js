/* 对照实验：2D 柱占用率 vs 3D 体素占用率（均 0.95 门槛，只读）
 * 目的：静态面在 2D 柱口径下 ~90% 占用，3D 体素口径是否更高（=更抗采样抖动）。
 * 用法：node diag_3d_occ.js <sid>
 */
"use strict";
const fs = require("fs");
const path = require("path");
const REPO = path.resolve(__dirname, "..", "..", "..", "..");
const RP = path.join(REPO, "pc_apps", "human_replay");
const RL = require(path.join(RP, "human_replay_lib.js"));
const PL = require(path.join(RP, "human_pipe_lib.js"));

const sid = process.argv[2] || "cap_20261002_223757";
const dir = path.join(REPO, "captures", "remote", sid);
const meta = JSON.parse(fs.readFileSync(path.join(dir, "meta.json"), "utf8"));
const raw = fs.readFileSync(path.join(dir, "points.bin"));
const f32 = new Float32Array(raw.buffer, raw.byteOffset, raw.byteLength / 4);
const frames = RL.frame_slice(meta);
const STRIDE = RL.STRIDE_F32;
const inv = 1 / PL.PIPE.voxel_m;
const key3 = (x, y, z) => Math.floor(x * inv) + "," + Math.floor(y * inv) + "," + Math.floor(z * inv);

const ded = frames.map(f => PL.denoise(RL.strided_f32_copy(f32, f.start_pts, f.count, STRIDE)));

/* 2D / 3D 占用率（剔贴地后计） */
const occ2 = new Map(), occ3 = new Map();
for (const fr of ded) {
    const s2 = new Set(), s3 = new Set();
    for (let i = 0; i < fr.length; i += 4) {
        if (fr[i + 2] < PL.PIPE.ground_keep_below_m) continue;
        const k2 = PL.key_vox(fr[i], fr[i + 1]);
        if (!s2.has(k2)) { s2.add(k2); occ2.set(k2, (occ2.get(k2) || 0) + 1); }
        const k3 = key3(fr[i], fr[i + 1], fr[i + 2]);
        if (!s3.has(k3)) { s3.add(k3); occ3.set(k3, (occ3.get(k3) || 0) + 1); }
    }
}
const thr = Math.ceil(frames.length * 0.95);
const st2 = new Set(), st3 = new Set();
occ2.forEach((c, k) => { if (c >= thr) st2.add(k); });
occ3.forEach((c, k) => { if (c >= thr) st3.add(k); });
console.log("sid=" + sid + " frames=" + frames.length + " thr=" + thr);
console.log("2D: cols=" + occ2.size + " static=" + st2.size
    + " | 3D: voxels=" + occ3.size + " static=" + st3.size);

/* 逐帧：分别用 2D/3D 静态集剔点后聚类（都用 XY 体素聚类） */
function run(staticSet, use3d) {
    let clusters = 0, fgSum = 0, high = 0;
    const tags = {};
    const cells = {};
    for (let i = 0; i < frames.length; i++) {
        const f = frames[i];
        const slice = RL.strided_f32_copy(f32, f.start_pts, f.count, STRIDE);
        const clean = PL.denoise(slice);
        const out = [];
        for (let k = 0; k < clean.length; k += 4) {
            if (clean[k + 2] < PL.PIPE.ground_keep_below_m) continue;
            const kk = use3d ? key3(clean[k], clean[k + 1], clean[k + 2]) : PL.key_vox(clean[k], clean[k + 1]);
            if (staticSet.has(kk)) continue;
            out.push(clean[k], clean[k + 1], clean[k + 2], clean[k + 3]);
        }
        const fgArr = new Float32Array(out);
        fgSum += fgArr.length / 4;
        const vox = PL.voxelize(fgArr);
        const rawC = PL.cluster_voxels(vox);
        const ev = PL.evidence_postpass(fgArr, rawC);
        for (let ci = 0; ci < rawC.length; ci++) {
            const feat = PL.cluster_features(rawC[ci]);
            if (!feat.ok) continue;
            clusters++;
            if (feat.zmin > 2.2) high++;
            const tag = PL.evidence_label(ev.clusters_extra[ci]).label;
            tags[tag] = (tags[tag] || 0) + 1;
            const c = Math.round(feat.cx) + "," + Math.round(feat.cy);
            cells[c] = (cells[c] || 0) + 1;
        }
    }
    const top = Object.entries(cells).sort((a, b) => b[1] - a[1]).slice(0, 6);
    return { clusters: clusters, fg_per_frame: Math.round(fgSum / frames.length), zmin_gt_2_2: high, tags: tags, top: top };
}
console.log("2D@0.95:", JSON.stringify(run(st2, false)));
console.log("3D@0.95:", JSON.stringify(run(st3, true)));

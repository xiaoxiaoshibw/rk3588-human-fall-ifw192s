/* HR-W03 候选修复组合仿真（只读，不改生产代码）
 *
 * 组合：
 *   base : ratio 0.95, 无半径滤波（现状）
 *   A    : ratio 0.9  + 半径滤波 r=0.10m k=2
 *   B    : A + 不可能为人门（zmin<=2.3 且 height<=2.3）
 *   C    : B + 人体形状门（宽/深<=0.7 且 躯干半径<=0.45 且 upcos>=0.5）
 *
 * 用法：node sim_fix.js <sid>
 */
"use strict";
const fs = require("fs");
const path = require("path");
const REPO = path.resolve(__dirname, "..", "..", "..", "..");
const RP = path.join(REPO, "pc_apps", "human_replay");
const RL = require(path.join(RP, "human_replay_lib.js"));
const PL = require(path.join(RP, "human_pipe_lib.js"));

/* 半径滤波：与板端 HF denoise_mask 同语义（27 格邻域点数 >= k 才留），纯 JS 版 */
function denoise_radius(xyzi, radius, k) {
    const inv = 1 / radius, OFF = 512, B = 1024;
    function key(ix, iy, iz) { return ((ix + OFF) * B + (iy + OFF)) * B + (iz + OFF); }
    const counts = new Map();
    for (let i = 0; i < xyzi.length; i += 4) {
        const c = key(Math.floor(xyzi[i] * inv), Math.floor(xyzi[i + 1] * inv), Math.floor(xyzi[i + 2] * inv));
        counts.set(c, (counts.get(c) || 0) + 1);
    }
    const out = [];
    for (let i = 0; i < xyzi.length; i += 4) {
        const ix = Math.floor(xyzi[i] * inv), iy = Math.floor(xyzi[i + 1] * inv), iz = Math.floor(xyzi[i + 2] * inv);
        let n = 0;
        for (let a = -1; a <= 1; a++) for (let b = -1; b <= 1; b++) for (let c = -1; c <= 1; c++) {
            const v = counts.get(key(ix + a, iy + b, iz + c)); if (v) n += v;
        }
        if (n >= k) out.push(xyzi[i], xyzi[i + 1], xyzi[i + 2], xyzi[i + 3]);
    }
    return new Float32Array(out);
}

const sid = process.argv[2] || "cap_20261002_223757";
const dir = path.join(REPO, "captures", "remote", sid);
const meta = JSON.parse(fs.readFileSync(path.join(dir, "meta.json"), "utf8"));
const raw = fs.readFileSync(path.join(dir, "points.bin"));
const f32 = new Float32Array(raw.buffer, raw.byteOffset, raw.byteLength / 4);
const frames = RL.frame_slice(meta);
const STRIDE = RL.STRIDE_F32;

/* 全帧基础去噪（现状）与 +半径滤波 两套，供不同组合复用 */
const dedBase = frames.map(function (f) {
    return PL.denoise(RL.strided_f32_copy(f32, f.start_pts, f.count, STRIDE));
});
const dedR = dedBase.map(function (fr) { return denoise_radius(fr, 0.10, 2); });

const CONFIGS = [
    { name: "base", ratio: 0.95, ded: dedBase, zgate: false, shape: false },
    { name: "A", ratio: 0.90, ded: dedR, zgate: false, shape: false },
    { name: "B", ratio: 0.90, ded: dedR, zgate: true, shape: false },
    { name: "C", ratio: 0.90, ded: dedR, zgate: true, shape: true },
];

const report = [];
for (const cfg of CONFIGS) {
    PL.PIPE.bg_occupancy_ratio = cfg.ratio;
    const staticKeys = PL.build_static_map(cfg.ded, { drop_ground: true });
    let fgSum = 0, drawn = 0, droppedZ = 0, droppedShape = 0;
    const tags = {}, drawnInfo = [];
    for (let i = 0; i < frames.length; i++) {
        const f = frames[i];
        const slice = RL.strided_f32_copy(f32, f.start_pts, f.count, STRIDE);
        const clean = cfg.ded === dedR ? denoise_radius(PL.denoise(slice), 0.10, 2) : PL.denoise(slice);
        const fg = PL.extract_foreground(clean, staticKeys);
        fgSum += fg.n_fg;
        const rawC = PL.cluster_voxels(fg.vox_fg);
        const ev = PL.evidence_postpass(fg.fg_xyzi, rawC);
        for (let ci = 0; ci < rawC.length; ci++) {
            const feat = PL.cluster_features(rawC[ci]);
            if (!feat.ok) continue;
            const tag = PL.evidence_label(ev.clusters_extra[ci]).label;
            if (cfg.zgate && (feat.zmin > 2.3 || feat.height_m > 2.3)) { droppedZ++; continue; }
            if (cfg.shape && (feat.width_m > 0.7 || feat.depth_m > 0.7
                || feat.radius_m > 0.45 || feat.upcos < 0.5)) { droppedShape++; continue; }
            drawn++;
            tags[tag] = (tags[tag] || 0) + 1;
            if (i % 10 === 0) drawnInfo.push({ zmin: +feat.zmin.toFixed(2), h: +feat.height_m.toFixed(2), n: feat.n, tag: tag });
        }
    }
    report.push({ cfg: cfg.name, ratio: cfg.ratio, static_cols: staticKeys.size,
                  fg_pts_per_frame: Math.round(fgSum / frames.length),
                  drawn: drawn, dropped_zgate: droppedZ, dropped_shape: droppedShape,
                  tags: tags, sample: drawnInfo.slice(0, 6) });
}
console.log(JSON.stringify({ sid: sid, frames: frames.length, report: report }, null, 1));

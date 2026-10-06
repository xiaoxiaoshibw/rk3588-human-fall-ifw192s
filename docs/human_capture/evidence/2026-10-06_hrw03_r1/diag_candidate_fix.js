/* HR-W03 指定组合下的簇明细（只读）
 * 用法：node diag_candidate_fix.js <sid> <ratio> <radiusM> <k> <gates:0|z|zs>
 *   radiusM=0 关闭半径滤波；gates: z=不可能为人门, zs=再加人体形状门
 * 输出：stdout 摘要 + <sid>_fix_<ratio>_<radius>.json（全部绘制簇）
 */
"use strict";
const fs = require("fs");
const path = require("path");
const REPO = path.resolve(__dirname, "..", "..", "..", "..");
const RP = path.join(REPO, "pc_apps", "human_replay");
const RL = require(path.join(RP, "human_replay_lib.js"));
const PL = require(path.join(RP, "human_pipe_lib.js"));

function denoise_radius(xyzi, radius, k) {
    const inv = 1 / radius, OFF = 512, B = 1024;
    const key = (ix, iy, iz) => ((ix + OFF) * B + (iy + OFF)) * B + (iz + OFF);
    const counts = new Map();
    for (let i = 0; i < xyzi.length; i += 4)
        counts.set(key(Math.floor(xyzi[i] * inv), Math.floor(xyzi[i + 1] * inv), Math.floor(xyzi[i + 2] * inv)),
            (counts.get(key(Math.floor(xyzi[i] * inv), Math.floor(xyzi[i + 1] * inv), Math.floor(xyzi[i + 2] * inv))) || 0) + 1);
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

const sid = process.argv[2], ratio = Number(process.argv[3]), radius = Number(process.argv[4]),
    k = Number(process.argv[5] || 2), gates = process.argv[6] || "0";
const dir = path.join(REPO, "captures", "remote", sid);
const meta = JSON.parse(fs.readFileSync(path.join(dir, "meta.json"), "utf8"));
const raw = fs.readFileSync(path.join(dir, "points.bin"));
const f32 = new Float32Array(raw.buffer, raw.byteOffset, raw.byteLength / 4);
const frames = RL.frame_slice(meta);
const STRIDE = RL.STRIDE_F32;
const ded = frames.map(function (f) {
    const d = PL.denoise(RL.strided_f32_copy(f32, f.start_pts, f.count, STRIDE));
    return radius > 0 ? denoise_radius(d, radius, k) : d;
});

PL.PIPE.bg_occupancy_ratio = ratio;
const staticKeys = PL.build_static_map(ded, { drop_ground: true });
const occ = new Map();
for (const fr of ded) {
    const seen = new Set();
    for (let i = 0; i < fr.length; i += 4) {
        if (fr[i + 2] < PL.PIPE.ground_keep_below_m) continue;
        const kk = PL.key_vox(fr[i], fr[i + 1]);
        if (seen.has(kk)) continue; seen.add(kk);
        occ.set(kk, (occ.get(kk) || 0) + 1);
    }
}

const rows = [];
for (let i = 0; i < frames.length; i++) {
    const f = frames[i];
    const slice = RL.strided_f32_copy(f32, f.start_pts, f.count, STRIDE);
    let clean = PL.denoise(slice);
    if (radius > 0) clean = denoise_radius(clean, radius, k);
    const fg = PL.extract_foreground(clean, staticKeys);
    const rawC = PL.cluster_voxels(fg.vox_fg);
    const ev = PL.evidence_postpass(fg.fg_xyzi, rawC);
    for (let ci = 0; ci < rawC.length; ci++) {
        const feat = PL.cluster_features(rawC[ci]);
        if (!feat.ok) continue;
        if (gates !== "0" && (feat.zmin > 2.3 || feat.height_m > 2.3)) continue;
        if (gates === "zs" && (feat.width_m > 0.7 || feat.depth_m > 0.7
            || feat.radius_m > 0.45 || feat.upcos < 0.5)) continue;
        const occs = rawC[ci].keys.map(kk => occ.get(kk) || 0);
        rows.push({ f: i, cx: +feat.cx.toFixed(2), cy: +feat.cy.toFixed(2),
                    zmin: +feat.zmin.toFixed(2), h: +feat.height_m.toFixed(2), n: feat.n,
                    tag: PL.evidence_label(ev.clusters_extra[ci]).label,
                    occ: occs.length ? occs.sort((a, b) => a - b)[occs.length >> 1] : 0 });
    }
}

const perFrame = {};
for (const r of rows) perFrame[r.f] = (perFrame[r.f] || 0) + 1;
const cnts = frames.map((_, i) => perFrame[i] || 0).sort((a, b) => a - b);
const cells = {};
for (const r of rows) { const c = Math.round(r.cx) + "," + Math.round(r.cy); cells[c] = (cells[c] || 0) + 1; }
const top = Object.entries(cells).sort((a, b) => b[1] - a[1]).slice(0, 8);
console.log("sid=" + sid + " ratio=" + ratio + " radius=" + radius + " gates=" + gates
    + " frames=" + frames.length + " static=" + staticKeys.size);
console.log("drawn=" + rows.length + " per-frame min/med/max=" + cnts[0] + "/" + cnts[cnts.length >> 1] + "/" + cnts[cnts.length - 1]);
console.log("top cells(1m): " + JSON.stringify(top));
const out = path.join(__dirname, sid + "_fix_" + ratio + "_" + radius + "_" + gates + ".json");
fs.writeFileSync(out, JSON.stringify(rows));
console.log("-> " + path.basename(out));

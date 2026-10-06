/* W03-R3.0 shape probe — READ-ONLY. Walks a session, prints the presence timeline of a scene
 * window (raw count / foreground count / clusters), then ASCII renders the biggest cluster in
 * that window (XY top view + XZ side view; o=map exact cell, +=map in 3x3x3, *=no map).
 * Usage: node 07_probe_shapes.js <sid> <cx> <cy> <half> <f0> <f1>
 */
"use strict";
const fs = require("fs");
const path = require("path");
const HERE = __dirname;
const REPO = path.resolve(HERE, "..", "..", "..", "..");
const RP = path.join(REPO, "pc_apps", "human_replay");
const RL = require(path.join(RP, "human_replay_lib.js"));
const PL = require(path.join(RP, "human_pipe_lib.js"));

const [sid, cxs, cys, halfs, f0s, f1s] = process.argv.slice(2);
const CX = +cxs, CY = +cys, HALF = +halfs, F0 = +f0s, F1 = +f1s;
const dir = path.join(REPO, "captures", "remote", sid);
const meta = JSON.parse(fs.readFileSync(path.join(dir, "meta.json"), "utf8"));
const raw = fs.readFileSync(path.join(dir, "points.bin"));
const f32 = new Float32Array(raw.buffer, raw.byteOffset, raw.byteLength / 4);
const frames = RL.frame_slice(meta);
const STRIDE = RL.STRIDE_F32;
const ded = frames.map(f => PL.denoise(RL.strided_f32_copy(f32, f.start_pts, f.count, STRIDE)));
const sm = PL.build_static_map(ded, { drop_ground: true });

const BG_BASE = 8192, BG_OFF = 4096;
function bg_key_ijk(ix, iy, iz) { return ((ix + BG_OFF) * BG_BASE + (iy + BG_OFF)) * BG_BASE + (iz + BG_OFF); }
function nearest_static(x, y, z) {
    const ix = Math.floor(x / PL.PIPE.bg_voxel_xy), iy = Math.floor(y / PL.PIPE.bg_voxel_xy),
          iz = Math.floor(z / PL.PIPE.bg_voxel_z);
    let exact = false, nb = false;
    for (let a = -1; a <= 1; a++) for (let b = -1; b <= 1; b++) for (let c = -1; c <= 1; c++) {
        const rec = sm.get(bg_key_ijk(ix + a, iy + b, iz + c));
        if (!rec) continue;
        nb = true; if (!a && !b && !c) exact = true;
    }
    return { exact, nb };
}
function inWin(x, y, z) { return Math.abs(x - CX) <= HALF && Math.abs(y - CY) <= HALF && z >= 0.1 && z <= 2.5; }

console.log("== " + sid + " window c=(" + CX + "," + CY + ") half=" + HALF + " frames " + F0 + ".." + F1);
console.log("   f | raw | fg | clusters (ci n joint conf track) | biggest c=(x,y,z) h");
let best = null;
for (let i = F0; i <= F1; i++) {
    const slice = RL.strided_f32_copy(f32, frames[i].start_pts, frames[i].count, STRIDE);
    let nRaw = 0, nFg = 0;
    const clean = PL.denoise(slice);
    for (let k = 0; k < clean.length; k += 4) if (inWin(clean[k], clean[k + 1], clean[k + 2])) nRaw++;
    const fg = PL.extract_foreground(clean, sm);
    const iso = PL.cleanup_isolated_fg(fg.fg_xyzi);
    for (let k = 0; k < iso.xyzi.length; k += 4) if (inWin(iso.xyzi[k], iso.xyzi[k + 1], iso.xyzi[k + 2])) nFg++;
    const rawC = PL.cluster_voxels(PL.voxelize(iso.xyzi));
    const ev = PL.evidence_postpass(iso.xyzi, rawC);
    const hits = [];
    for (let ci = 0; ci < rawC.length; ci++) {
        const f = PL.cluster_features(rawC[ci]);
        if (!f.ok) continue;
        const c = PL.classify_human(f);
        f.label = c.label; f.evidence = ev.clusters_extra[ci];
        f.evidence_tag = PL.evidence_label(f.evidence); f.joint = PL.joint_status(f);
        if (Math.abs(f.cx - CX) <= HALF && Math.abs(f.cy - CY) <= HALF)
            hits.push("ci" + ci + " n" + f.n + " " + f.joint + " h" + f.height_m.toFixed(2));
    }
    if (hits.length) {
        console.log("   " + String(i).padStart(3) + " | " + String(nRaw).padStart(4) + " | " + String(nFg).padStart(4)
            + " | " + hits.join(" ; "));
        /* 取窗口内最大簇供 ASCII */
        let bigCi = -1, bigN = 0;
        for (let ci = 0; ci < rawC.length; ci++) {
            const f = PL.cluster_features(rawC[ci]);
            if (!f.ok) continue;
            if (Math.abs(f.cx - CX) <= HALF && Math.abs(f.cy - CY) <= HALF && f.n > bigN) { bigN = f.n; bigCi = ci; }
        }
        if (bigCi >= 0 && (!best || bigN > best.n)) best = { f: i, ci: bigCi, n: bigN };
    } else {
        console.log("   " + String(i).padStart(3) + " | " + String(nRaw).padStart(4) + " | " + String(nFg).padStart(4) + " | -");
    }
}
if (!best) { console.log("no cluster found in window"); process.exit(0); }
/* ASCII 渲染最大簇 */
const slice = RL.strided_f32_copy(f32, frames[best.f].start_pts, frames[best.f].count, STRIDE);
const clean = PL.denoise(slice);
const fg = PL.extract_foreground(clean, sm);
const iso = PL.cleanup_isolated_fg(fg.fg_xyzi);
const rawC = PL.cluster_voxels(PL.voxelize(iso.xyzi));
const keys = new Set(rawC[best.ci].keys);
const pts = [];
for (let k = 0; k < iso.xyzi.length; k += 4) {
    const x = iso.xyzi[k], y = iso.xyzi[k + 1], z = iso.xyzi[k + 2];
    if (!keys.has(PL.key_vox(x, y))) continue;
    const m = nearest_static(x, y, z);
    pts.push({ x, y, z, ch: m.exact ? "o" : (m.nb ? "+" : "*") });
}
function render(label, a, b, arr) {
    const W = 64, H = 22;
    const amin = Math.min.apply(null, arr.map(p => p[a])), amax = Math.max.apply(null, arr.map(p => p[a]));
    const bmin = Math.min.apply(null, arr.map(p => p[b])), bmax = Math.max.apply(null, arr.map(p => p[b]));
    const grid = [];
    for (let r = 0; r < H; r++) grid.push(new Array(W).fill(" "));
    for (const p of pts) {
        const col = Math.min(W - 1, Math.floor((p[a] - amin) / (amax - amin + 1e-9) * (W - 1)));
        const row = Math.min(H - 1, Math.floor((bmax - p[b]) / (bmax - bmin + 1e-9) * (H - 1)));
        grid[row][col] = p.ch;
    }
    console.log("-- " + label + "  " + a + "[" + amin.toFixed(2) + "," + amax.toFixed(2) + "] "
        + b + "[" + bmin.toFixed(2) + "," + bmax.toFixed(2) + "]  n=" + pts.length);
    for (const row of grid) console.log("   |" + row.join("") + "|");
}
console.log("frame " + best.f + " cluster#" + best.ci + " n=" + best.n);
render("XY top", "x", "y", pts);
render("XZ side", "x", "z", pts);

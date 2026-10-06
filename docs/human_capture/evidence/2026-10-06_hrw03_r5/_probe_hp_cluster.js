/* _probe_hp_cluster.js — HP01/HP03 簇点构成探针（只读，辅助 11_r33_ab.js 判读）
 * 对每帧簇点分三类：center 命中 / 仅 AABB 命中 / 未命中，按 z 带与 XY 分布统计，
 * 并统计簇心附近 reference 占用格（看是否有同场静态物污染 retention 口径）。 */
"use strict";
const fs = require("fs");
const path = require("path");
const HERE = __dirname;
const REPO = path.resolve(HERE, "..", "..", "..", "..");
const RP = path.join(REPO, "pc_apps", "human_replay");
const RL = require(path.join(RP, "human_replay_lib.js"));
const PL = require(path.join(RP, "human_pipe_lib.js"));
const REF_SID = "cap_20261004_203349";
const CUR_SID = "cap_20261002_223757";

const BG_BASE = 8192, BG_OFF = 4096;
function bg_key_ijk(ix, iy, iz) { return ((ix + BG_OFF) * BG_BASE + (iy + BG_OFF)) * BG_BASE + (iz + BG_OFF); }
function resolve_transform(sid) {
    const LV = path.join(REPO, "captures", "leveled");
    let best = null;
    for (const job of fs.readdirSync(LV)) {
        const jd = path.join(LV, job);
        const tfPath = path.join(jd, "tls", "transform.json");
        const rpPath = path.join(jd, "report.json");
        if (!fs.existsSync(tfPath) || !fs.existsSync(rpPath)) continue;
        let report, tr;
        try { report = JSON.parse(fs.readFileSync(rpPath, "utf8")); tr = JSON.parse(fs.readFileSync(tfPath, "utf8")); } catch (e) { continue; }
        if (report.sid !== sid || report.recommended !== "tls") continue;
        if (!tr || !tr.R || !tr.t) continue;
        const mt = fs.statSync(jd).mtimeMs;
        if (!best || mt > best.mtime) best = { mtime: mt, R: tr.R, t: tr.t, job: job };
    }
    return best;
}
function apply_Rt(arr, R, t) {
    const r = R.flat ? R.flat() : R;
    for (let k = 0; k < arr.length; k += 4) {
        const x = arr[k], y = arr[k + 1], z = arr[k + 2];
        arr[k] = r[0] * x + r[1] * y + r[2] * z + t[0];
        arr[k + 1] = r[3] * x + r[4] * y + r[5] * z + t[1];
        arr[k + 2] = r[6] * x + r[7] * y + r[8] * z + t[2];
    }
}
function load_leveled_denoised(sid) {
    const dir = path.join(REPO, "captures", "remote", sid);
    const meta = JSON.parse(fs.readFileSync(path.join(dir, "meta.json"), "utf8"));
    const raw = fs.readFileSync(path.join(dir, "points.bin"));
    const f32 = new Float32Array(raw.buffer, raw.byteOffset, raw.byteLength / 4);
    const frames = RL.frame_slice(meta);
    const STRIDE = RL.STRIDE_F32;
    const tf = resolve_transform(sid);
    const ded = frames.map(f => {
        const s = RL.strided_f32_copy(f32, f.start_pts, f.count, STRIDE);
        if (tf) apply_Rt(s, tf.R, tf.t);
        return PL.denoise(s);
    });
    return { dir: dir, frames: ded };
}
const REF = load_leveled_denoised(REF_SID);
const CUR = load_leveled_denoised(CUR_SID);
const refMap = PL.build_reference_map(REF.frames);
const CUR_ONLINE = PL.build_static_map(CUR.frames, { drop_ground: true });
const VX = PL.PIPE.bg_voxel_xy, VZ = PL.PIPE.bg_voxel_z;
function scanRef(occMin, px, py, pz) {
    const ix = Math.floor(px / VX), iy = Math.floor(py / VX), iz = Math.floor(pz / VZ);
    let d0 = Infinity, d1 = Infinity;
    for (let a = -1; a <= 1; a++) for (let b = -1; b <= 1; b++) for (let c = -1; c <= 1; c++) {
        const rec = refMap.voxels.get(bg_key_ijk(ix + a, iy + b, iz + c));
        if (!rec || rec.occ < occMin) continue;
        const dx = rec.x - px, dy = rec.y - py, dz = rec.z - pz;
        const c2 = dx * dx + dy * dy + dz * dz; if (c2 < d0) d0 = c2;
        const bx = (ix + a) * VX, by = (iy + b) * VX, bz = (iz + c) * VZ;
        const ex = Math.max(bx - px, 0, px - (bx + VX)), ey = Math.max(by - py, 0, py - (by + VX)), ez = Math.max(bz - pz, 0, pz - (bz + VZ));
        const b2 = ex * ex + ey * ey + ez * ez; if (b2 < d1) d1 = b2;
    }
    return { d0: d0 === Infinity ? null : Math.sqrt(d0), d1: d1 === Infinity ? null : Math.sqrt(d1) };
}
function clusterNear(frameIdx, cx, cy, half) {
    const fr = CUR.frames[frameIdx];
    const fg = PL.extract_foreground(fr, CUR_ONLINE);
    const iso = PL.cleanup_isolated_fg(fg.fg_xyzi);
    const rawC = PL.cluster_voxels(PL.voxelize(iso.xyzi));
    let bestCi = -1, bestN = 0;
    for (let ci = 0; ci < rawC.length; ci++) {
        const f = PL.cluster_features(rawC[ci]);
        if (!f.ok) continue;
        if (Math.abs(f.cx - cx) <= half && Math.abs(f.cy - cy) <= half && f.n > bestN) { bestN = f.n; bestCi = ci; }
    }
    if (bestCi < 0) return { pts: [], f: null };
    const keys = new Set(rawC[bestCi].keys);
    const pts = [];
    for (let k = 0; k < iso.xyzi.length; k += 4) {
        const x = iso.xyzi[k], y = iso.xyzi[k + 1], z = iso.xyzi[k + 2];
        if (keys.has(PL.key_vox(x, y))) pts.push({ x: x, y: y, z: z });
    }
    return { pts: pts, f: PL.cluster_features(rawC[bestCi]) };
}
function zband(z) { return z < 0.3 ? "0-0.3" : z < 0.8 ? "0.3-0.8" : z < 1.2 ? "0.8-1.2" : z < 1.8 ? "1.2-1.8" : "1.8+"; }
function probe(label, frameIdx, cx, cy, half) {
    const { pts, f } = clusterNear(frameIdx, cx, cy, half);
    if (!f) { console.log(label + " f" + frameIdx + ": no cluster"); return; }
    const buckets = { center: {}, aabbOnly: {}, miss: {} };
    let sx = 0, sy = 0;
    for (const p of pts) { sx += p.x; sy += p.y; }
    const mx = sx / pts.length, my = sy / pts.length;
    const cnt = { center: 0, aabbOnly: 0, miss: 0 };
    for (const p of pts) {
        const r = scanRef(0.5, p.x, p.y, p.z);
        const b = (r.d0 !== null && r.d0 < 0.12) ? "center" : (r.d1 !== null && r.d1 < 0.12 ? "aabbOnly" : "miss");
        cnt[b]++;
        const zb = zband(p.z);
        buckets[b][zb] = (buckets[b][zb] || 0) + 1;
    }
    /* 簇心附近 reference 占用格（XY 0.6m 内，按 z 带） */
    const refNear = {};
    refMap.voxels.forEach(rec => {
        if (rec.occ < 0.5) return;
        const dx = rec.x - mx, dy = rec.y - my;
        if (dx * dx + dy * dy > 0.36) return;
        const zb = zband(rec.z);
        refNear[zb] = (refNear[zb] || 0) + 1;
    });
    console.log("[" + label + "] f" + frameIdx + " n=" + pts.length + " c=(" + mx.toFixed(2) + "," + my.toFixed(2) + ")"
        + " h=" + f.height_m.toFixed(2) + " upcos=" + f.upcos.toFixed(2)
        + " w=" + f.width_m.toFixed(2) + " d=" + f.depth_m.toFixed(2)
        + " | center=" + cnt.center + " aabbOnly=" + cnt.aabbOnly + " miss=" + cnt.miss);
    console.log("   zbands center: " + JSON.stringify(buckets.center) + "  aabbOnly: " + JSON.stringify(buckets.aabbOnly) + "  miss: " + JSON.stringify(buckets.miss));
    console.log("   ref voxels near cluster (XY 0.6m) by z: " + JSON.stringify(refNear));
}
console.log("== HP01 (standing/walk) ==");
for (const fi of [10, 30, 55, 80, 85, 90, 160]) probe("HP01", fi, 1.45, 0.85, 0.80);
console.log("== walking frames ==");
for (const fi of [63, 65, 146, 150, 155]) probe("walk", fi, fi <= 65 ? 1.44 : 1.45, fi <= 65 ? 0.0 : 0.6, 1.0);
console.log("== standing on sight line ==");
for (const fi of [80, 85, 90]) probe("stand", fi, 1.52, -0.40, 0.80);
console.log("== HP03 (lying) ==");
for (const fi of [92, 95, 99, 123]) probe("HP03", fi, 1.52, -0.40, 0.80);

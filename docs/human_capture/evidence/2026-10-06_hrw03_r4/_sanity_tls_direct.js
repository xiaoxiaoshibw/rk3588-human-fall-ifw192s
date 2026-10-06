/* _sanity_tls_direct.js — 用 TLS 直接差（R_cur·R_ref^T）变换 ref recs，对照 ICP 结果的 sanity check */
"use strict";
const fs = require("fs");
const path = require("path");
const HERE = __dirname;
const REPO = path.resolve(HERE, "..", "..", "..", "..");
const REF_JOB = "c9712acad48c4fb7a78cb119c08d4cdb";
const CUR_JOB = "6bc5aabf8f0041ffa961758b4e84da94";
const REF_SID = "cap_20261004_203349";
const CUR_SID = "cap_20261002_223757";

const RP = path.join(REPO, "pc_apps", "human_replay");
const RL = require(path.join(RP, "human_replay_lib.js"));
const PL = require(path.join(RP, "human_pipe_lib.js"));

function m3_mul(A, B) {
    const o = new Array(9).fill(0);
    for (let i = 0; i < 3; i++) for (let j = 0; j < 3; j++) for (let k = 0; k < 3; k++) o[3 * i + j] += A[3 * i + k] * B[3 * k + j];
    return o;
}
function m3_t(A) { return [A[0], A[3], A[6], A[1], A[4], A[7], A[2], A[5], A[8]]; }
function m3_apply(A, x, y, z) { return [A[0] * x + A[1] * y + A[2] * z, A[3] * x + A[4] * y + A[5] * z, A[6] * x + A[7] * y + A[8] * z]; }

const R_ref = JSON.parse(fs.readFileSync(path.join(REPO, "captures", "leveled", REF_JOB, "tls", "transform.json"), "utf8")).R.flat();
const R_cur = JSON.parse(fs.readFileSync(path.join(REPO, "captures", "leveled", CUR_JOB, "tls", "transform.json"), "utf8")).R.flat();
const t_ref = JSON.parse(fs.readFileSync(path.join(REPO, "captures", "leveled", REF_JOB, "tls", "transform.json"), "utf8")).t;
const t_cur = JSON.parse(fs.readFileSync(path.join(REPO, "captures", "leveled", CUR_JOB, "tls", "transform.json"), "utf8")).t;

/* R_direct = R_cur · R_ref^T —— 把「ref session leveled 点」直接转到「cur session leveled 点」 */
const R_direct = m3_mul(R_cur, m3_t(R_ref));

function load_leveled(sid) {
    const dir = path.join(REPO, "captures", "remote", sid);
    const meta = JSON.parse(fs.readFileSync(path.join(dir, "meta.json"), "utf8"));
    const raw = fs.readFileSync(path.join(dir, "points.bin"));
    const f32 = new Float32Array(raw.buffer, raw.byteOffset, raw.byteLength / 4);
    const frames = RL.frame_slice(meta);
    const STRIDE = RL.STRIDE_F32;
    const LV = path.join(REPO, "captures", "leveled");
    let tf = null;
    for (const job of fs.readdirSync(LV)) {
        const jd = path.join(LV, job);
        const tfPath = path.join(jd, "tls", "transform.json");
        const rpPath = path.join(jd, "report.json");
        if (!fs.existsSync(tfPath) || !fs.existsSync(rpPath)) continue;
        let report, tr;
        try { report = JSON.parse(fs.readFileSync(rpPath, "utf8")); tr = JSON.parse(fs.readFileSync(tfPath, "utf8")); } catch (e) { continue; }
        if (report.sid !== sid || report.recommended !== "tls") continue;
        if (!tf) tf = { R: tr.R.flat(), t: tr.t };
    }
    const ded = frames.map(f => {
        const s = RL.strided_f32_copy(f32, f.start_pts, f.count, STRIDE);
        if (tf) {
            const r = tf.R;
            for (let k = 0; k < s.length; k += 4) {
                const x = s[k], y = s[k + 1], z = s[k + 2];
                s[k] = r[0] * x + r[1] * y + r[2] * z + tf.t[0];
                s[k + 1] = r[3] * x + r[4] * y + r[5] * z + tf.t[1];
                s[k + 2] = r[6] * x + r[7] * y + r[8] * z + tf.t[2];
            }
        }
        return PL.denoise(s);
    });
    return ded;
}

const refFrames = load_leveled(REF_SID);
const curFrames = load_leveled(CUR_SID);

const refMap = PL.build_reference_map(refFrames);
const refRecs = [];
refMap.voxels.forEach((rec, key) => { if (rec.occ >= 0.5) refRecs.push(rec); });
console.log("ref recs occ>=0.5:", refRecs.length);

/* 用 R_direct 变换所有 ref recs（不带平移） */
const refTransformed = refRecs.map(r => {
    const q = m3_apply(R_direct, r.x, r.y, r.z);
    return { x: q[0], y: q[1], z: q[2] };
});

/* 体素哈希 */
function buildIdx(recs, cell) {
    const map = new Map();
    for (const r of recs) {
        const k = Math.floor(r.x / cell) + "," + Math.floor(r.y / cell) + "," + Math.floor(r.z / cell);
        let a = map.get(k); if (!a) { a = []; map.set(k, a); }
        a.push(r);
    }
    return { map, cell };
}
function nn(idx, x, y, z, maxR) {
    const n = Math.max(1, Math.ceil(maxR / idx.cell));
    const ix = Math.floor(x / idx.cell), iy = Math.floor(y / idx.cell), iz = Math.floor(z / idx.cell);
    let best = null, bestD2 = maxR * maxR;
    for (let a = -n; a <= n; a++) for (let b = -n; b <= n; b++) for (let c = -n; c <= n; c++) {
        const arr = idx.map.get((ix + a) + "," + (iy + b) + "," + (iz + c));
        if (!arr) continue;
        for (const r of arr) {
            const dx = r.x - x, dy = r.y - y, dz = r.z - z, d2 = dx * dx + dy * dy + dz * dz;
            if (d2 < bestD2) { bestD2 = d2; best = r; }
        }
    }
    return best ? Math.sqrt(bestD2) : null;
}

/* WD01 簇点：f42 leveled */
const CUR_ONLINE = PL.build_static_map(curFrames, { drop_ground: true });
const fr = curFrames[42];
const fg = PL.extract_foreground(fr, CUR_ONLINE);
const iso = PL.cleanup_isolated_fg(fg.fg_xyzi);
const rawC = PL.cluster_voxels(PL.voxelize(iso.xyzi));
const W = { cx: 3.50, cy: -0.76, half: 0.5 };
let bestCi = -1, bestN = 0;
for (let ci = 0; ci < rawC.length; ci++) {
    const f = PL.cluster_features(rawC[ci]);
    if (!f.ok) continue;
    if (Math.abs(f.cx - W.cx) <= W.half && Math.abs(f.cy - W.cy) <= W.half && f.n > bestN) { bestN = f.n; bestCi = ci; }
}
const keys = new Set(rawC[bestCi].keys);
const wdPts = [];
for (let k = 0; k < iso.xyzi.length; k += 4) {
    const x = iso.xyzi[k], y = iso.xyzi[k + 1], z = iso.xyzi[k + 2];
    if (keys.has(PL.key_vox(x, y))) wdPts.push({ x, y, z });
}
console.log("WD01 f42 cluster n:", wdPts.length);

function coverage(label, recs) {
    const idx = buildIdx(recs, 0.28);
    const dists = [];
    for (const p of wdPts) { const d = nn(idx, p.x, p.y, p.z, 1.0); if (d !== null) dists.push(d); }
    const ds = dists.slice().sort((a, b) => a - b);
    const c12 = dists.filter(d => d < 0.12).length, c20 = dists.filter(d => d < 0.20).length;
    const d50 = ds.length ? ds[Math.floor(ds.length * 0.5)] : null;
    const d95 = ds.length ? ds[Math.floor(ds.length * 0.95)] : null;
    console.log("  " + label + "  cov@0.12=" + (c12 / wdPts.length).toFixed(4)
        + "  cov@0.20=" + (c20 / wdPts.length).toFixed(4)
        + "  d50=" + (d50 === null ? "null" : d50.toFixed(4))
        + "  d95=" + (d95 === null ? "null" : d95.toFixed(4)));
}
console.log("WD01 f42 reference coverage:");
coverage("before         ", refRecs);
coverage("TLS-direct     ", refTransformed);

/* 全文匹配率（薄点） */
const allCurThin = [];
for (const fr2 of curFrames) {
    for (let k = 0; k < fr2.length; k += 4 * 4) {  /* 抽稀 ×4 */
        const z = fr2[k + 2];
        if (z < PL.PIPE.ground_keep_below_m || z > PL.PIPE.z_max_m) continue;
        allCurThin.push({ x: fr2[k], y: fr2[k + 1], z: z });
    }
}
console.log("all thin points:", allCurThin.length);
function fullCov(label, recs) {
    const idx = buildIdx(recs, 0.28);
    let n = 0, hit = 0;
    const dists = [];
    for (const p of allCurThin) {
        n++;
        const d12 = nn(idx, p.x, p.y, p.z, 0.12);
        if (d12 !== null) { hit++; dists.push(d12); }
        else { const d = nn(idx, p.x, p.y, p.z, 1.0); if (d !== null) dists.push(d); }
    }
    const ds = dists.slice().sort((a, b) => a - b);
    const d50 = ds.length ? ds[Math.floor(ds.length * 0.5)] : null;
    console.log("  " + label + "  match=" + (hit / n).toFixed(4) + "  d50=" + (d50 === null ? "null" : d50.toFixed(4)));
}
console.log("full-frame match:");
fullCov("before         ", refRecs);
fullCov("TLS-direct     ", refTransformed);

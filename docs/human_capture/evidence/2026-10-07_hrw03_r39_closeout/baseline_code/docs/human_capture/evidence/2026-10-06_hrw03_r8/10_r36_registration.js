/* ============================================================================
 * W03-R3.6 — Registration Causality / Shared-Frame Validation（离线只读；production 零改动）
 *
 * 唯一目标：验证 R3.5 "Registration attribution" 的因果性 ——
 *   若 reference 与 current 被放到足够准确的共享坐标系，WD02 的 registration residual 是否系统性下降？
 *
 * 条件（唯一变量 = registration transform，方向统一 current→reference）：
 *   A      = production/current（无跨会话对齐，none；生产现状）
 *   B      = R3.2/R3.5 固定 ICP 解（严格复用，不重调参）
 *   C      = point-to-plane 静态结构高置信对齐（oracle-like upper bound，非 GT）
 *   C_ALT  = C 的第二个收敛盆地（tls 初值；敏感性）
 *   TLS    = R_direct 直逆（仅旋转；辅助对照）
 *
 * 硬门（失败即 STOP）：
 *   G0 逐点等价 / 守恒 / micro-cases / 在线 map 复刻 / ICP 复跑 / 5286/3707/2063 /
 *   R3.3 A 层 0.7796 / probe 群 / **r7 02 JSON 逐帧逐组逐整数复现** / C 复现与初值稳健性 /
 *   inputs_unchanged（11 输入 SHA）/ production mtime 不变。
 *
 * 冻结（工单 §三）：不调 matcher（radius/XY/Z/voxel/AABB/morphology/connectivity 全不动）；
 *   不改任何 production 文件/阈值/接口；不写输入；不接 production。
 *
 * 依据：docs/human_capture/evidence/2026-10-06_hrw03_r8/01_registration_chain_audit.md
 *       docs/human_capture/evidence/2026-10-06_hrw03_r8/02_experiment_design.md
 * 同源复用：r7/10_r35_attribution.js（加载/扫描/归因/聚合段，逐行复用）
 *
 * 用法：
 *   node 10_r36_registration.js                                  # full → 03/04/04b + 13_tool_run.log
 *   node 10_r36_registration.js --frames=10,55,160 --outdir=D    # 调试子集
 *   node 10_r36_registration.js --digest-only                    # 确定性复跑（只打印 digest）
 * ========================================================================== */
"use strict";
const fs = require("fs");
const path = require("path");
const crypto = require("crypto");

const HERE = __dirname;
const REPO = path.resolve(HERE, "..", "..", "..", "..");
const RP = path.join(REPO, "pc_apps", "human_replay");
const RL = require(path.join(RP, "human_replay_lib.js"));
const PL = require(path.join(RP, "human_pipe_lib.js"));

const ARGV = process.argv.slice(2);
function arg(name, dflt) {
    const hit = ARGV.find(a => a === "--" + name || a.startsWith("--" + name + "="));
    if (hit === undefined) return dflt;
    const eq = hit.indexOf("=");
    if (eq < 0) return true;
    return hit.slice(eq + 1);
}
const OUTDIR = String(arg("outdir", HERE));
const DIGEST_ONLY = arg("digest-only", false);
const FRAME_SUBSET = arg("frames", null) ? String(arg("frames", "")).split(",").map(v => parseInt(v, 10)) : null;

const CUR_SID = "cap_20261002_223757";
const REF_SID = "cap_20261004_203349";
const OCC_MIN = PL.PIPE.bg_ref_occ_min;                  // 0.5（v1 候选，冻结）
const MATCH_R = PL.PIPE.bg_match_radius;                 // 0.12（production，冻结）
const VX = PL.PIPE.bg_voxel_xy, VZ = PL.PIPE.bg_voxel_z; // 0.15 / 0.12
const R2 = MATCH_R * MATCH_R;
const ICP_SAVED = { roll: 1.7476, pitch: -0.2818, yaw: -2.3924, t: [0.0182, 0.031, 0.0012] }; // R3.2 存值
const C_EXPECT = { euler: { roll: -2.3102, pitch: 0.0813, yaw: 2.2269 }, t: [-0.0064, -0.0288, -0.0099] }; // 预研（_recon_c2）

const FOCAL_FRAMES = [2, 10, 30, 42, 55, 63, 65, 80, 85, 90, 92, 95, 99, 123, 146, 150, 155, 160];
const PROBLEM_FRAMES = [10, 30, 55, 150, 155, 160];
const CLEAN_FRAMES = [63, 65, 80, 85, 90, 92, 95, 99, 123, 146];
const NEAR_FURNITURE_FRAMES = [55, 150, 155, 160];
const PROXY_FRAMES = [10, 30, 55, 150, 155, 160];
const CORROB_FRAMES = [63, 80, 92, 123];
const FURNITURE_XY = { x: 1.45, y: 0.85 };
const WD01_XY = { x: 3.50, y: -0.76 };
const WD02_REPS = [{ x: 10.75, y: 4.25 }, { x: 10.25, y: -1.75 }, { x: 10.50, y: 5.50 }];

const COND_KEYS = ["A", "TLS", "B", "C", "C_ALT"];
const COND_LABEL = { A: "NONE", TLS: "TLS", B: "ICP", C: "C", C_ALT: "C_ALT" };
const STATE_KEYS = ["ABSORB", "REG_GAP", "GEOM", "MISSING", "SPARSE"];

const L = [];
function log(s) { L.push(s); console.log(s); }
function round(v, d) { return v === null || v === undefined || !isFinite(v) ? null : +v.toFixed(d === undefined ? 4 : d); }
function pct(sorted, q) {
    if (!sorted.length) return null;
    return sorted[Math.min(sorted.length - 1, Math.max(0, Math.ceil(q * sorted.length) - 1))];
}
function quantiles(arr) {
    const s = arr.slice().sort((a, b) => a - b);
    return { n: s.length, p10: round(pct(s, 0.10)), p25: round(pct(s, 0.25)), p50: round(pct(s, 0.50)),
             p75: round(pct(s, 0.75)), p90: round(pct(s, 0.90)), p95: round(pct(s, 0.95)), p99: round(pct(s, 0.99)), max: round(s[s.length - 1]) };
}
function qOnly(arr, q) { const s = arr.slice().sort((a, b) => a - b); return s.length ? round(pct(s, q)) : null; }
function sha256_buf(b) { return crypto.createHash("sha256").update(b).digest("hex"); }
function sha256_file(p) { return sha256_buf(fs.readFileSync(p)); }
function sha256_file_canon(p) {
    const b = fs.readFileSync(p);
    return sha256_buf(Buffer.from(b.toString("latin1").replace(/\r\n/g, "\n").replace(/\r/g, "\n"), "latin1"));
}

/* ---- 3×3 矩阵 / Jacobi / 小角解（r7 同源逐行复用） ---- */
const m3 = {
    mul(A, B) { const o = new Array(9).fill(0); for (let i = 0; i < 3; i++) for (let j = 0; j < 3; j++) for (let k = 0; k < 3; k++) o[3 * i + j] += A[3 * i + k] * B[3 * k + j]; return o; },
    t(A) { return [A[0], A[3], A[6], A[1], A[4], A[7], A[2], A[5], A[8]]; },
    apply(A, x, y, z) { return [A[0] * x + A[1] * y + A[2] * z, A[3] * x + A[4] * y + A[5] * z, A[6] * x + A[7] * y + A[8] * z]; },
    rodrigues(a) {
        const th = Math.hypot(a[0], a[1], a[2]);
        if (th < 1e-12) return [1, 0, 0, 0, 1, 0, 0, 0, 1];
        const x = a[0] / th, y = a[1] / th, z = a[2] / th, c = Math.cos(th), s = Math.sin(th), C = 1 - c;
        return [c + x * x * C, x * y * C - z * s, x * z * C + y * s,
                y * x * C + z * s, c + y * y * C, y * z * C - x * s,
                z * x * C - y * s, z * y * C + x * s, c + z * z * C];
    },
};
function jacobi_eig(Ain, n) {
    const A = Ain.map(r => r.slice());
    const V = []; for (let i = 0; i < n; i++) { V.push(new Array(n).fill(0)); V[i][i] = 1; }
    for (let sweep = 0; sweep < 100; sweep++) {
        let off = 0;
        for (let p = 0; p < n; p++) for (let q = p + 1; q < n; q++) off += A[p][q] * A[p][q];
        if (off < 1e-24) break;
        for (let p = 0; p < n - 1; p++) for (let q = p + 1; q < n; q++) {
            if (Math.abs(A[p][q]) < 1e-18) continue;
            const app = A[p][p], aqq = A[q][q], apq = A[p][q];
            const tau = (aqq - app) / (2 * apq);
            const tt = (tau >= 0 ? 1 : -1) / (Math.abs(tau) + Math.sqrt(1 + tau * tau));
            const c = 1 / Math.sqrt(1 + tt * tt), s = tt * c;
            for (let k = 0; k < n; k++) { const akp = A[k][p], akq = A[k][q]; A[k][p] = c * akp - s * akq; A[k][q] = s * akp + c * akq; }
            for (let k = 0; k < n; k++) { const apk = A[p][k], aqk = A[q][k]; A[p][k] = c * apk - s * aqk; A[q][k] = s * apk + c * aqk; }
            for (let k = 0; k < n; k++) { const vkp = V[k][p], vkq = V[k][q]; V[k][p] = c * vkp - s * vkq; V[k][q] = s * vkp + c * vkq; }
        }
    }
    const vals = [], vecs = [];
    for (let i = 0; i < n; i++) { vals.push(A[i][i]); vecs.push(V.map(r => r[i])); }
    return { vals: vals, vecs: vecs };
}
function solveSmallAngle(pairs) {
    const H = [], rhs = [];
    for (const pr of pairs) {
        const [x, y, z] = pr.p, [qx, qy, qz] = pr.q;
        H.push([0, -z, y]); rhs.push(qx - x);
        H.push([z, 0, -x]); rhs.push(qy - y);
        H.push([-y, x, 0]); rhs.push(qz - z);
    }
    const M = [[0, 0, 0], [0, 0, 0], [0, 0, 0]], b = [0, 0, 0];
    for (let k = 0; k < H.length; k++) for (let i = 0; i < 3; i++) {
        b[i] += H[k][i] * rhs[k];
        for (let j = 0; j < 3; j++) M[i][j] += H[k][i] * H[k][j];
    }
    const e3 = jacobi_eig(M, 3);
    const ord = [0, 1, 2].sort((i, j) => e3.vals[j] - e3.vals[i]);
    const lamMax = e3.vals[ord[0]];
    const a = [0, 0, 0];
    for (const i of ord) {
        const lam = e3.vals[i];
        if (lam < lamMax * 1e-10 || lam < 1e-18) continue;
        const v = e3.vecs[i];
        const dot = v[0] * b[0] + v[1] * b[1] + v[2] * b[2];
        for (let j = 0; j < 3; j++) a[j] += (dot / lam) * v[j];
    }
    return a;
}
function solve6(M, b) {
    const A = M.map((r, i) => r.concat([b[i]]));
    for (let c = 0; c < 6; c++) {
        let pivot = c;
        for (let r = c + 1; r < 6; r++) if (Math.abs(A[r][c]) > Math.abs(A[pivot][c])) pivot = r;
        if (Math.abs(A[pivot][c]) < 1e-14) return null;
        const tmp = A[c]; A[c] = A[pivot]; A[pivot] = tmp;
        for (let r = 0; r < 6; r++) {
            if (r === c) continue;
            const f = A[r][c] / A[c][c];
            if (!f) continue;
            for (let k = c; k <= 6; k++) A[r][k] -= f * A[c][k];
        }
    }
    const x = new Array(6);
    for (let i = 0; i < 6; i++) x[i] = A[i][6] / A[i][i];
    return x;
}
function eulerFromR(R) {
    const pitch = Math.asin(Math.max(-1, Math.min(1, -R[6])));
    const roll = Math.atan2(R[7], R[8]);
    const yaw = Math.atan2(R[3], R[0]);
    return { roll: roll * 180 / Math.PI, pitch: pitch * 180 / Math.PI, yaw: yaw * 180 / Math.PI };
}
function build_vox_index(recs, cell) {
    const map = new Map();
    for (const r of recs) {
        const k = Math.floor(r.x / cell) + "," + Math.floor(r.y / cell) + "," + Math.floor(r.z / cell);
        let a = map.get(k); if (!a) { a = []; map.set(k, a); }
        a.push(r);
    }
    return { map: map, cell: cell };
}
function nn_query(idx, x, y, z, maxR) {
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
    return best ? { rec: best, d: Math.sqrt(bestD2) } : null;
}

/* ---- 会话加载（console/r7 同口径：TLS → denoise） ---- */
function resolve_transform(sid) {
    const LV = path.join(REPO, "captures", "leveled");
    if (!fs.existsSync(LV)) return null;
    let best = null;
    for (const job of fs.readdirSync(LV)) {
        const jd = path.join(LV, job);
        const tfPath = path.join(jd, "tls", "transform.json");
        const rpPath = path.join(jd, "report.json");
        const mfPath = path.join(jd, "manifest.json");
        if (!fs.existsSync(tfPath) || !fs.existsSync(rpPath)) continue;
        let report, tr, manifest;
        try { report = JSON.parse(fs.readFileSync(rpPath, "utf8")); tr = JSON.parse(fs.readFileSync(tfPath, "utf8")); manifest = JSON.parse(fs.readFileSync(mfPath, "utf8")); }
        catch (e) { continue; }
        if (report.sid !== sid || report.recommended !== "tls") continue;
        if (!tr || !tr.R || !tr.t) continue;
        /* 完整性（与 server leveled_latest 对齐的一部分）：manifest 内 transform.json SHA 必须一致 */
        const expect = manifest && manifest.artifacts && manifest.artifacts.tls && manifest.artifacts.tls["transform.json"];
        if (expect && sha256_file(tfPath) !== expect) continue;
        const mt = fs.statSync(jd).mtimeMs;
        if (!best || mt > best.mtime) best = { mtime: mt, R: tr.R, t: tr.t, job: job, transform_id: tr.transform_id, tf_path: tfPath, rp_path: rpPath };
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
    return { dir: dir, meta: meta, frames: ded, tf: tf, frame_slices: frames };
}

/* ---- 背景体素整数键（与生产 key_bg 同源） ---- */
const BG_BASE = 8192, BG_OFF = 4096;
function bg_key_ijk(ix, iy, iz) { return ((ix + BG_OFF) * BG_BASE + (iy + BG_OFF)) * BG_BASE + (iz + BG_OFF); }
function bg_key(x, y, z) { return bg_key_ijk(Math.floor(x / VX), Math.floor(y / VX), Math.floor(z / VZ)); }
function bg_decode(key) {
    var iz = key % BG_BASE; key = (key - iz) / BG_BASE;
    var iy = key % BG_BASE;
    return [(key - iy) / BG_BASE - BG_OFF, iy - BG_OFF, iz - BG_OFF];
}

/* ---- stats-preserving 在线 map 复刻（r7 同源） ---- */
function build_static_map_stats(frames_xyzi, opts) {
    opts = opts || {};
    var drop_ground = opts.drop_ground !== false;
    var nframes = frames_xyzi.length;
    var stats = new Map(), per = new Map();
    for (var f = 0; f < nframes; f++) {
        per.clear();
        var frame = frames_xyzi[f];
        for (var k = 0; k < frame.length; k += 4) {
            var z = frame[k + 2];
            if (drop_ground && z < PL.PIPE.ground_keep_below_m) continue;
            if (z > PL.PIPE.z_max_m) continue;
            var key = bg_key(frame[k], frame[k + 1], z);
            var a = per.get(key);
            if (!a) { a = { n: 0, sx: 0, sy: 0, sz: 0 }; per.set(key, a); }
            a.n++; a.sx += frame[k]; a.sy += frame[k + 1]; a.sz += z;
        }
        per.forEach(function (a, key) {
            if (a.n < PL.PIPE.bg_hit_min_pts) return;
            var s = stats.get(key);
            if (!s) { s = { hits: 0, cx: 0, cy: 0, cz: 0, mx: 0, my: 0, mz: 0 }; stats.set(key, s); }
            s.hits++;
            var px = a.sx / a.n, py = a.sy / a.n, pz = a.sz / a.n;
            var dx = px - s.cx, dy = py - s.cy, dz = pz - s.cz;
            s.cx += dx / s.hits; s.mx += dx * (px - s.cx);
            s.cy += dy / s.hits; s.my += dy * (py - s.cy);
            s.cz += dz / s.hits; s.mz += dz * (pz - s.cz);
        });
    }
    var thr_strong = Math.ceil(nframes * PL.PIPE.bg_occ_strong);
    var thr_sup = Math.ceil(nframes * PL.PIPE.bg_occ_supported);
    var out = new Map(), strong = new Set();
    stats.forEach(function (s, key) {
        s.occ = s.hits / nframes;
        s.jit = Math.sqrt(Math.max(s.mx, s.my, s.mz) / s.hits);
        if (s.hits >= thr_strong) { s.tier = "strong"; s.x = s.cx; s.y = s.cy; s.z = s.cz; strong.add(key); }
    });
    stats.forEach(function (s, key) {
        if (s.hits < thr_sup || s.hits >= thr_strong) return;
        if (s.jit > PL.PIPE.bg_jitter_max) return;
        var nb = 0, ij = bg_decode(key);
        for (var a = -1; a <= 1 && nb < PL.PIPE.bg_neighbor_min; a++)
            for (var b = -1; b <= 1 && nb < PL.PIPE.bg_neighbor_min; b++)
                for (var c = -1; c <= 1 && nb < PL.PIPE.bg_neighbor_min; c++)
                    if ((a || b || c) && strong.has(bg_key_ijk(ij[0] + a, ij[1] + b, ij[2] + c))) nb++;
        if (nb >= PL.PIPE.bg_neighbor_min) { s.tier = "supported"; s.x = s.cx; s.y = s.cy; s.z = s.cz; }
    });
    var tiers = new Map();
    stats.forEach(function (s, key) { if (s.tier) tiers.set(key, { x: s.x, y: s.y, z: s.z, hits: s.hits, tier: s.tier }); });
    return { stats: stats, tiers: tiers, thr_strong: thr_strong, thr_sup: thr_sup, nframes: nframes };
}

/* ---- 探针扫描（r7 同源） ---- */
function scanTierCells(map, px, py, pz, occMin, wantBox) {
    const ix = Math.floor(px / VX), iy = Math.floor(py / VX), iz = Math.floor(pz / VZ);
    let bd2 = -1, bdx = 0, bdy = 0, bdz = 0, brec = null, bkey = 0;
    let boxd2 = -1;
    for (let a = -1; a <= 1; a++) {
        const kx = (ix + a + BG_OFF) * BG_BASE;
        for (let b = -1; b <= 1; b++) {
            const kxy = (kx + (iy + b + BG_OFF)) * BG_BASE;
            for (let c = -1; c <= 1; c++) {
                const key = kxy + (iz + c + BG_OFF);
                const rec = map.get(key);
                if (!rec) continue;
                if (occMin > 0) { const o = rec.occ; if (o === undefined || o < occMin) continue; }
                const dx = rec.x - px, dy = rec.y - py, dz = rec.z - pz;
                const d2 = dx * dx + dy * dy + dz * dz;
                if (bd2 < 0 || d2 < bd2) { bd2 = d2; bdx = dx; bdy = dy; bdz = dz; brec = rec; bkey = key; }
                if (wantBox) {
                    const bx = (ix + a) * VX, by = (iy + b) * VX, bz = (iz + c) * VZ;
                    const ex = Math.max(bx - px, 0, px - (bx + VX));
                    const ey = Math.max(by - py, 0, py - (by + VX));
                    const ez = Math.max(bz - pz, 0, pz - (bz + VZ));
                    const e2 = ex * ex + ey * ey + ez * ez;
                    if (boxd2 < 0 || e2 < boxd2) boxd2 = e2;
                }
            }
        }
    }
    if (bd2 < 0) return { d: null, dx: null, dy: null, dz: null, rec: null, key: 0, boxd: wantBox ? null : undefined };
    return { d: Math.sqrt(bd2), dx: bdx, dy: bdy, dz: bdz, rec: brec, key: bkey,
             boxd: wantBox ? (boxd2 < 0 ? null : Math.sqrt(boxd2)) : undefined };
}
function scanAnyCells(map, px, py, pz, field) {
    const ix = Math.floor(px / VX), iy = Math.floor(py / VX), iz = Math.floor(pz / VZ);
    let any = false, cells = 0, maxVal = -Infinity;
    for (let a = -1; a <= 1; a++) {
        const kx = (ix + a + BG_OFF) * BG_BASE;
        for (let b = -1; b <= 1; b++) {
            const kxy = (kx + (iy + b + BG_OFF)) * BG_BASE;
            for (let c = -1; c <= 1; c++) {
                const rec = map.get(kxy + (iz + c + BG_OFF));
                if (!rec) continue;
                any = true; cells++;
                const v = rec[field];
                if (v !== undefined && v > maxVal) maxVal = v;
            }
        }
    }
    return { any: any, cells: cells, max: any ? maxVal : null };
}
function shadowBgMatch(static_map, x, y, z) {
    const ix = Math.floor(x / VX), iy = Math.floor(y / VX), iz = Math.floor(z / VZ);
    for (let a = -1; a <= 1; a++) for (let b = -1; b <= 1; b++) for (let c = -1; c <= 1; c++) {
        const rec = static_map.get(bg_key_ijk(ix + a, iy + b, iz + c));
        if (!rec) continue;
        const dx = rec.x - x, dy = rec.y - y, dz = rec.z - z;
        if (dx * dx + dy * dy + dz * dz < R2) return true;
    }
    return false;
}
function shadowExtract(xyzi, static_map) {
    const out = [], resIdx = [];
    let nZ = 0, nBG = 0;
    const n = xyzi.length / 4;
    for (let pi = 0, k = 0; pi < n; pi++, k += 4) {
        const x = xyzi[k], y = xyzi[k + 1], z = xyzi[k + 2];
        if (z < PL.PIPE.ground_keep_below_m || z > PL.PIPE.z_max_m) { nZ++; continue; }
        if (static_map && shadowBgMatch(static_map, x, y, z)) { nBG++; continue; }
        resIdx.push(pi); out.push(x, y, z, xyzi[k + 3]);
    }
    return { fg: new Float32Array(out), resIdx: resIdx, nZ: nZ, nBG: nBG, nRes: resIdx.length, nIn: n };
}
function axisLabel(dx, dy, dz) {
    const dxy = Math.hypot(dx, dy);
    if (dxy < MATCH_R && Math.abs(dz) >= MATCH_R) return "XY_MATCH_Z_FAIL";
    if (Math.abs(dz) < MATCH_R && dxy >= MATCH_R) return "Z_MATCH_XY_FAIL";
    return "DISTANCE_OVER_GATE";
}
function zBandOf(z) { return z < 0.3 ? "0-0.3" : z < 0.8 ? "0.3-0.8" : z < 1.2 ? "0.8-1.2" : z < 1.8 ? "1.2-1.8" : "1.8+"; }
function shellBandOf(d) { return d === null ? "ABSENT" : d < MATCH_R ? "IN" : d < 2 * MATCH_R ? "SHELL" : "OVER"; }

/* ---- micro-cases（G0 行为门；r7 同源） ---- */
function microCases(onlineMap) {
    const cases = [];
    function outcomeOfPoint(map, x, y, z) {
        if (z < PL.PIPE.ground_keep_below_m || z > PL.PIPE.z_max_m) return 0;
        return map && shadowBgMatch(map, x, y, z) ? 1 : 2;
    }
    function runCase(name, pts, map, expectedOutcomes) {
        const arr = new Float32Array(pts.length * 4);
        for (let i = 0; i < pts.length; i++) { arr[4 * i] = pts[i][0]; arr[4 * i + 1] = pts[i][1]; arr[4 * i + 2] = pts[i][2]; arr[4 * i + 3] = 1; }
        const prod = PL.extract_foreground(arr, map);
        const sh = shadowExtract(arr, map);
        let mismatch = 0;
        if (prod.fg_xyzi.length !== sh.fg.length) mismatch = 1;
        else for (let i = 0; i < prod.fg_xyzi.length; i++) if (prod.fg_xyzi[i] !== sh.fg[i]) { mismatch++; break; }
        let expectedOk = null;
        if (expectedOutcomes) {
            expectedOk = true;
            for (let i = 0; i < pts.length; i++) {
                const oc = outcomeOfPoint(map, pts[i][0], pts[i][1], pts[i][2]);
                if (oc !== expectedOutcomes[i]) expectedOk = false;
            }
        }
        cases.push({ name: name, n: pts.length, prod_residual: prod.n_fg, shadow_residual: sh.nRes,
                     mismatch: mismatch, expected_ok: expectedOutcomes ? expectedOk : null, skipped: false });
        return mismatch === 0 && (!expectedOutcomes || expectedOk);
    }
    let ok = true;
    {
        const ix = 100, iy = 100, iz = 10;
        const key = bg_key_ijk(ix, iy, iz);
        const cx = ix * VX + VX / 2, cy = iy * VX + VX / 2, cz = iz * VZ + VZ / 2;
        const map = new Map([[key, { x: cx, y: cy, z: cz, hits: 9, tier: "strong" }]]);
        const e = 1e-6, diagIn = (MATCH_R / Math.sqrt(3)) * (1 - 1e-9), diagOut = (MATCH_R / Math.sqrt(3)) * (1 + 1e-9);
        const pts = [
            [cx + MATCH_R - e, cy, cz], [cx - MATCH_R + e, cy, cz],
            [cx + MATCH_R + e, cy, cz], [cx - MATCH_R - e, cy, cz],
            [cx, cy + MATCH_R - e, cz], [cx, cy - MATCH_R + e, cz],
            [cx, cy, cz + MATCH_R - e], [cx, cy, cz - MATCH_R + e],
            [cx, cy, cz + MATCH_R + e], [cx, cy, cz - MATCH_R - e],
            [cx + diagIn, cy + diagIn, cz + diagIn],
            [cx + diagOut, cy + diagOut, cz + diagOut],
            [50, 50, 1.26],
        ];
        const outcomes = [1, 1, 2, 2, 1, 1, 1, 1, 2, 2, 1, 2, 2];
        ok = runCase("C1_handcrafted_single_voxel_radius_and_cells", pts, map, outcomes) && ok;
    }
    {
        const map = new Map();
        const pts = [[50, 50, 0.10], [50, 50, 0.10 - 1e-9], [50, 50, 2.50], [50, 50, 2.50 + 1e-9], [50, 50, 1.00]];
        const outcomes = [2, 0, 2, 0, 2];
        ok = runCase("C2_workspace_z_boundary", pts, map, outcomes) && ok;
    }
    {
        const cell = 0.5, idx = new Map();
        onlineMap.forEach((rec, key) => {
            const k = Math.floor(rec.x / cell) + "," + Math.floor(rec.y / cell) + "," + Math.floor(rec.z / cell);
            let a = idx.get(k); if (!a) { a = []; idx.set(k, a); }
            a.push({ x: rec.x, y: rec.y, z: rec.z, key: key });
        });
        let cand = null;
        onlineMap.forEach((rec, key) => {
            if (cand) return;
            if (rec.z < 0.30 || rec.z > 2.30) return;
            const ix = Math.floor(rec.x / cell), iy = Math.floor(rec.y / cell), iz = Math.floor(rec.z / cell);
            let hasNeighbor = false;
            for (let a = -1; a <= 1 && !hasNeighbor; a++) for (let b = -1; b <= 1 && !hasNeighbor; b++) for (let c = -1; c <= 1 && !hasNeighbor; c++) {
                const arr = idx.get((ix + a) + "," + (iy + b) + "," + (iz + c));
                if (!arr) continue;
                for (const r of arr) if (r.key !== key && Math.hypot(r.x - rec.x, r.y - rec.y, r.z - rec.z) < 0.35) { hasNeighbor = true; break; }
            }
            if (!hasNeighbor) cand = { x: rec.x, y: rec.y, z: rec.z };
        });
        if (!cand) { cases.push({ name: "C3_realmap_isolated_voxel", skipped: true, reason: "no isolated voxel found" }); }
        else {
            const e = 1e-6;
            const pts = [
                [cand.x + MATCH_R - e, cand.y, cand.z], [cand.x - MATCH_R + e, cand.y, cand.z],
                [cand.x + MATCH_R + e, cand.y, cand.z], [cand.x - MATCH_R - e, cand.y, cand.z],
                [cand.x, cand.y + MATCH_R - e, cand.z], [cand.x, cand.y + MATCH_R + e, cand.z],
                [cand.x, cand.y, cand.z + MATCH_R - e], [cand.x, cand.y, cand.z + MATCH_R + e],
            ];
            const outcomes = [1, 1, 2, 2, 1, 2, 1, 2];
            ok = runCase("C3_realmap_isolated_voxel_axis_pm", pts, onlineMap, outcomes) && ok;
        }
    }
    return { cases: cases, pass: ok };
}

/* ---- 条件 C：静态细集 + 法向 + point-to-plane（预研 _recon_c2 冻结参数） ---- */
function fineStatic(frames, staticSet, cell) {
    const m = new Map(), inv = 1 / cell;
    for (const fr of frames) {
        for (let k = 0; k < fr.length; k += 4) {
            const x = fr[k], y = fr[k + 1], z = fr[k + 2];
            if (!staticSet.has(PL.key_bg(x, y, z))) continue;
            const kk = Math.floor(x * inv) + "," + Math.floor(y * inv) + "," + Math.floor(z * inv);
            let a = m.get(kk); if (!a) { a = { n: 0, sx: 0, sy: 0, sz: 0 }; m.set(kk, a); }
            a.n++; a.sx += x; a.sy += y; a.sz += z;
        }
    }
    const out = [];
    m.forEach(a => out.push({ x: a.sx / a.n, y: a.sy / a.n, z: a.sz / a.n, n: a.n }));
    return out;
}
function estimateNormals(pts, radius) {
    const idx = build_vox_index(pts, radius);
    const R2loc = radius * radius;
    for (const p of pts) {
        const ix = Math.floor(p.x / radius), iy = Math.floor(p.y / radius), iz = Math.floor(p.z / radius);
        const nbr = [];
        for (let a = -1; a <= 1; a++) for (let b = -1; b <= 1; b++) for (let c = -1; c <= 1; c++) {
            const arr = idx.map.get((ix + a) + "," + (iy + b) + "," + (iz + c));
            if (!arr) continue;
            for (const r of arr) {
                const dx = r.x - p.x, dy = r.y - p.y, dz = r.z - p.z;
                if (dx * dx + dy * dy + dz * dz <= R2loc) nbr.push(r);
            }
        }
        if (nbr.length < 4) { p.nx = null; continue; }
        let mx = 0, my = 0, mz = 0;
        for (const r of nbr) { mx += r.x; my += r.y; mz += r.z; }
        mx /= nbr.length; my /= nbr.length; mz /= nbr.length;
        const C = [[0, 0, 0], [0, 0, 0], [0, 0, 0]];
        for (const r of nbr) {
            const v = [r.x - mx, r.y - my, r.z - mz];
            for (let i = 0; i < 3; i++) for (let j = 0; j < 3; j++) C[i][j] += v[i] * v[j];
        }
        const e = jacobi_eig(C, 3);
        let mi = 0; for (let i = 1; i < 3; i++) if (e.vals[i] < e.vals[mi]) mi = i;
        const v = e.vecs[mi];
        const nrm = Math.hypot(v[0], v[1], v[2]);
        p.nx = v[0] / nrm; p.ny = v[1] / nrm; p.nz = v[2] / nrm;
    }
}
function ppICP(src, tgtIdx, R0, t0, sched, tag) {
    let R = R0.slice(), t = t0.slice();
    let iters = 0;
    for (const sc of sched) {
        const P = sc.stride > 1 ? src.filter((_, i) => i % sc.stride === 0) : src;
        for (let iter = 0; iter < sc.iters; iter++) {
            const pairs = [];
            for (const p of P) {
                const q = m3.apply(R, p.x, p.y, p.z);
                const X = q[0] + t[0], Y = q[1] + t[1], Z = q[2] + t[2];
                const hit = nn_query(tgtIdx, X, Y, Z, sc.inlier);
                if (!hit || hit.rec.nx === null) continue;
                const r = hit.rec.nx * (X - hit.rec.x) + hit.rec.ny * (Y - hit.rec.y) + hit.rec.nz * (Z - hit.rec.z);
                pairs.push({ X, Y, Z, r, q: hit.rec });
            }
            if (pairs.length < 30) break;
            pairs.sort((a, b) => Math.abs(a.r) - Math.abs(b.r));
            const keep = pairs.slice(0, Math.max(30, Math.floor(pairs.length * sc.keep)));
            const M = [], b = [];
            for (let i = 0; i < 6; i++) { M.push(new Array(6).fill(0)); b.push(0); }
            for (const pr of keep) {
                const nx = pr.q.nx, ny = pr.q.ny, nz = pr.q.nz;
                const wx = pr.Y * nz - pr.Z * ny, wy = pr.Z * nx - pr.X * nz, wz = pr.X * ny - pr.Y * nx;
                const row = [wx, wy, wz, nx, ny, nz];
                const rhs = nx * (pr.q.x - pr.X) + ny * (pr.q.y - pr.Y) + nz * (pr.q.z - pr.Z);
                for (let i = 0; i < 6; i++) { for (let j = 0; j < 6; j++) M[i][j] += row[i] * row[j]; b[i] += row[i] * rhs; }
            }
            const x = solve6(M, b);
            if (!x) break;
            const a = [x[0], x[1], x[2]], dt = [x[3], x[4], x[5]];
            const Rn = m3.rodrigues(a);
            const Rmup = m3.apply(Rn, t[0], t[1], t[2]);
            t = [Rmup[0] + dt[0], Rmup[1] + dt[1], Rmup[2] + dt[2]];
            R = m3.mul(Rn, R);
            iters++;
            const rotDeg = Math.hypot(a[0], a[1], a[2]) * 180 / Math.PI;
            if (rotDeg < 5e-5 && Math.hypot(dt[0], dt[1], dt[2]) < 5e-5) break;
        }
    }
    const eu = eulerFromR(R);
    log("[r36] " + tag + ": euler=" + JSON.stringify({ roll: round(eu.roll, 4), pitch: round(eu.pitch, 4), yaw: round(eu.yaw, 4) })
        + " t=[" + t.map(v => round(v, 4)).join(",") + "] iters=" + iters);
    return { R: R, t: t, eu: eu, iters: iters };
}
function normalResiduals(src, tgtIdx, R, t, maxR) {
    const rs = [];
    for (const p of src) {
        const q = m3.apply(R, p.x, p.y, p.z);
        const hit = nn_query(tgtIdx, q[0] + t[0], q[1] + t[1], q[2] + t[2], maxR);
        if (!hit || hit.rec.nx === null) continue;
        rs.push(Math.abs(hit.rec.nx * (q[0] + t[0] - hit.rec.x) + hit.rec.ny * (q[1] + t[1] - hit.rec.y) + hit.rec.nz * (q[2] + t[2] - hit.rec.z)));
    }
    return rs;
}
const PP_SCHED = [
    { inlier: 0.30, keep: 0.70, iters: 25, stride: 5 },
    { inlier: 0.20, keep: 0.60, iters: 25, stride: 3 },
    { inlier: 0.15, keep: 0.50, iters: 25, stride: 2 },
    { inlier: 0.10, keep: 0.50, iters: 25, stride: 1 },
    { inlier: 0.08, keep: 0.60, iters: 25, stride: 1 },
];
const I3 = [1, 0, 0, 0, 1, 0, 0, 0, 1];

/* ---- 输入 SHA（11 项） ---- */
function inputSHAs() {
    const s = {};
    for (const f of ["human_pipe_lib.js", "human_replay_lib.js", "human_pipe_lib.test.js"]) {
        const p = path.join(RP, f);
        s[f] = { raw: sha256_file(p), canonical: sha256_file_canon(p) };
    }
    for (const sid of [REF_SID, CUR_SID]) {
        s[sid + ":meta"] = sha256_file(path.join(REPO, "captures", "remote", sid, "meta.json"));
        s[sid + ":points"] = sha256_file(path.join(REPO, "captures", "remote", sid, "points.bin"));
    }
    for (const [sid, job] of [[CUR_SID, "6bc5aabf8f0041ffa961758b4e84da94"], [REF_SID, "c9712acad48c4fb7a78cb119c08d4cdb"]]) {
        s[sid + ":transform"] = sha256_file(path.join(REPO, "captures", "leveled", job, "tls", "transform.json"));
        s[sid + ":report"] = sha256_file(path.join(REPO, "captures", "leveled", job, "report.json"));
    }
    return s;
}
function productionMTimes() {
    const s = {};
    for (const f of ["human_pipe_lib.js", "human_replay_lib.js", "human_pipe_lib.test.js", "human_detect.js", "human_detect.html"]) {
        s[f] = fs.statSync(path.join(RP, f)).mtimeMs;
    }
    return s;
}

/* ============================================================================
 * 主流程
 * ========================================================================== */
const T0 = Date.now();
log("[r36] W03-R3.6 registration causality tool");
log("[r36] repo=" + REPO);
log("[r36] node=" + process.version + "  mode=" + (DIGEST_ONLY ? "digest-only" : FRAME_SUBSET ? "subset:" + FRAME_SUBSET.join(",") : "full"));
log("[r36] production source (human_pipe_lib.js) canonical=" + sha256_file_canon(path.join(RP, "human_pipe_lib.js")));

const SHA_BEFORE = inputSHAs();
const MTIME_BEFORE = productionMTimes();

log("[r36] loading reference " + REF_SID + " ...");
const REF = load_leveled_denoised(REF_SID);
log("[r36] loading current  " + CUR_SID + " ...");
const CUR = load_leveled_denoised(CUR_SID);
if (!CUR.tf || !REF.tf) { console.error("[r36] FATAL: missing tls transform"); process.exit(2); }
log("[r36] transforms: cur job=" + CUR.tf.job + " id=" + CUR.tf.transform_id + "  ref job=" + REF.tf.job + " id=" + REF.tf.transform_id);
const N_CUR = CUR.frames.length, N_REF = REF.frames.length;

log("[r36] building maps ...");
const onlineMap = PL.build_static_map(CUR.frames, { drop_ground: true });
const onlineStats = build_static_map_stats(CUR.frames, { drop_ground: true });
const refMapObj = PL.build_reference_map(REF.frames);
const refSessionOnline = PL.build_static_map(REF.frames, { drop_ground: true });
const curMap1Obj = PL.build_reference_map(CUR.frames);

/* G0: 在线 map 复刻等价 */
const eqChk = (function () {
    let mismatch = 0, firstBad = null;
    if (onlineMap.size !== onlineStats.tiers.size) { mismatch++; firstBad = "size " + onlineMap.size + " vs " + onlineStats.tiers.size; }
    onlineMap.forEach((rec, key) => {
        const t = onlineStats.tiers.get(key);
        if (!t) { mismatch++; if (!firstBad) firstBad = "missing key " + key; return; }
        if (t.tier !== rec.tier || t.hits !== rec.hits) { mismatch++; if (!firstBad) firstBad = "tier/hits key " + key; return; }
        if (!(t.x === rec.x && t.y === rec.y && t.z === rec.z)) { mismatch++; if (!firstBad) firstBad = "centroid key " + key; }
    });
    onlineStats.tiers.forEach((t, key) => { if (!onlineMap.has(key)) { mismatch++; if (!firstBad) firstBad = "extra key " + key; } });
    return { size_prod: onlineMap.size, size_replica: onlineStats.tiers.size, mismatch: mismatch, first_bad: firstBad, pass: mismatch === 0 };
})();
let strong = 0, supported = 0;
onlineMap.forEach(rec => { if (rec.tier === "strong") strong++; else supported++; });
let refTotal = 0, refOcc05 = 0;
refMapObj.voxels.forEach((rec, key) => { refTotal++; if (rec.occ >= OCC_MIN) refOcc05++; });
let refSessStrong = 0;
refSessionOnline.forEach(rec => { if (rec.tier === "strong") refSessStrong++; });
log("[r36] online current: " + onlineMap.size + " (strong " + strong + " / supported " + supported + ")");
log("[r36] reference map: " + refTotal + " (occ>=0.5 " + refOcc05 + ")  ref-session online: " + refSessionOnline.size);
log("[r36] G0 online-map replica equivalence: " + (eqChk.pass ? "PASS" : "FAIL " + eqChk.first_bad));

/* ---- ICP-B 复跑（R3.2/r7 同款） ---- */
const icp = (function () {
    const refRecs09 = [];
    refMapObj.voxels.forEach((rec, key) => { if (rec.occ >= 0.9) refRecs09.push({ x: rec.x, y: rec.y, z: rec.z, occ: rec.occ, key: key }); });
    const tgt = [];
    onlineMap.forEach((rec, key) => { if (rec.tier === "strong") tgt.push({ x: rec.x, y: rec.y, z: rec.z, key: key }); });
    const tgtIdx = build_vox_index(tgt, 0.28);
    let R_icp = [1, 0, 0, 0, 1, 0, 0, 0, 1], t_icp = [0, 0, 0];
    const INLIER = 0.25;
    let iters = 0;
    function transformSrc(P) {
        return P.map(p => {
            const q = m3.apply(R_icp, p.x, p.y, p.z);
            return { x: q[0] + t_icp[0], y: q[1] + t_icp[1], z: q[2] + t_icp[2], occ: p.occ };
        });
    }
    let P = transformSrc(refRecs09);
    for (let iter = 0; iter < 50; iter++) {
        const pairs = [];
        for (const p of P) {
            const hit = nn_query(tgtIdx, p.x, p.y, p.z, INLIER);
            if (hit) pairs.push({ p: [p.x, p.y, p.z], q: [hit.rec.x, hit.rec.y, hit.rec.z], d: hit.d });
        }
        if (pairs.length < 20) break;
        const aEst = solveSmallAngle(pairs);
        const a = aEst.map(v => -v);
        const mup = [0, 0, 0], muq = [0, 0, 0];
        for (const pr of pairs) { for (let i = 0; i < 3; i++) { mup[i] += pr.p[i]; muq[i] += pr.q[i]; } }
        for (let i = 0; i < 3; i++) { mup[i] /= pairs.length; muq[i] /= pairs.length; }
        const Rn = m3.rodrigues(a);
        const Rmup = m3.apply(Rn, mup[0], mup[1], mup[2]);
        const tNew = [muq[0] - Rmup[0], muq[1] - Rmup[1], muq[2] - Rmup[2]];
        R_icp = m3.mul(Rn, R_icp);
        const Rnt = m3.apply(Rn, t_icp[0], t_icp[1], t_icp[2]);
        t_icp = [Rnt[0] + tNew[0], Rnt[1] + tNew[1], Rnt[2] + tNew[2]];
        P = transformSrc(refRecs09);
        iters = iter + 1;
        const rotDeg = Math.hypot(a[0], a[1], a[2]) * 180 / Math.PI;
        if (rotDeg < 1e-3 && Math.hypot(tNew[0], tNew[1], tNew[2]) < 1e-4) break;
    }
    const eu = eulerFromR(R_icp);
    const pass = Math.abs(eu.roll - ICP_SAVED.roll) <= 0.02 && Math.abs(eu.pitch - ICP_SAVED.pitch) <= 0.02
        && Math.abs(eu.yaw - ICP_SAVED.yaw) <= 0.02 && Math.abs(t_icp[0] - ICP_SAVED.t[0]) <= 0.002
        && Math.abs(t_icp[1] - ICP_SAVED.t[1]) <= 0.002 && Math.abs(t_icp[2] - ICP_SAVED.t[2]) <= 0.002;
    log("[r36] ICP-B rerun iters=" + iters + " roll=" + round(eu.roll, 4) + " pitch=" + round(eu.pitch, 4) + " yaw=" + round(eu.yaw, 4)
        + " t=[" + t_icp.map(v => round(v, 4)).join(",") + "] → " + (pass ? "CHECK PASS" : "CHECK FAIL"));
    return { R: R_icp, t: t_icp, eu: eu, iters: iters, pass: pass, n_src: refRecs09.length, n_tgt: tgt.length };
})();

/* ---- registration transforms（方向统一 current→reference） ---- */
const R_ref = REF.tf.R.flat ? REF.tf.R.flat() : REF.tf.R;
const R_cur = CUR.tf.R.flat ? CUR.tf.R.flat() : CUR.tf.R;
const R_direct = m3.mul(R_cur, m3.t(R_ref));      // ref-leveled → cur-leveled
const R_tls = m3.t(R_direct);                     // cur → ref
const R_Bc2r = m3.t(icp.R);                       // B: cur → ref
const t_Bc2r = m3.apply(R_Bc2r, -icp.t[0], -icp.t[1], -icp.t[2]);

/* ---- 条件 C：静态结构 point-to-plane（预研冻结） ---- */
log("[r36] building fine static sets + normals ...");
const refSet = new Set(); refMapObj.voxels.forEach((r, k) => { if (r.occ >= 0.9) refSet.add(k); });
const curSet = new Set(); onlineMap.forEach((r, k) => { if (r.tier === "strong") curSet.add(k); });
const cfFine = fineStatic(CUR.frames, curSet, 0.06);
const rfFine = fineStatic(REF.frames, refSet, 0.06);
estimateNormals(rfFine, 0.10);
const rfNormOk = rfFine.filter(p => p.nx !== null).length;
const idxRFine = build_vox_index(rfFine, 0.10);
log("[r36] C sets: curFine=" + cfFine.length + " refFine=" + rfFine.length + " normals_ok=" + rfNormOk);

const cPrimary = ppICP(cfFine, idxRFine, I3, [0, 0, 0], PP_SCHED, "C_primary(init=identity)");
const cAlt = ppICP(cfFine, idxRFine, R_tls, [0, 0, 0], PP_SCHED, "C_alt(init=tls)");
const cBchk = ppICP(cfFine, idxRFine, R_Bc2r.slice(), t_Bc2r.slice(), PP_SCHED, "C_check(init=B)");
const evenHalf = cfFine.filter((_, i) => i % 2 === 0), oddHalf = cfFine.filter((_, i) => i % 2 === 1);
const cEven = ppICP(evenHalf, idxRFine, I3, [0, 0, 0], PP_SCHED, "C_primary(fit=even)");
const cOdd = ppICP(oddHalf, idxRFine, I3, [0, 0, 0], PP_SCHED, "C_primary(fit=odd)");
const C_QA = {
    c_primary_expect: C_EXPECT,
    c_primary_match: Math.abs(cPrimary.eu.roll - C_EXPECT.euler.roll) <= 2e-3 && Math.abs(cPrimary.eu.pitch - C_EXPECT.euler.pitch) <= 2e-3
        && Math.abs(cPrimary.eu.yaw - C_EXPECT.euler.yaw) <= 2e-3 && Math.abs(cPrimary.t[0] - C_EXPECT.t[0]) <= 2e-4
        && Math.abs(cPrimary.t[1] - C_EXPECT.t[1]) <= 2e-4 && Math.abs(cPrimary.t[2] - C_EXPECT.t[2]) <= 2e-4,
    c_init_robust: Math.abs(cBchk.eu.roll - cPrimary.eu.roll) <= 5e-3 && Math.abs(cBchk.eu.pitch - cPrimary.eu.pitch) <= 5e-3
        && Math.abs(cBchk.eu.yaw - cPrimary.eu.yaw) <= 5e-3 && Math.hypot(cBchk.t[0] - cPrimary.t[0], cBchk.t[1] - cPrimary.t[1], cBchk.t[2] - cPrimary.t[2]) <= 1e-3,
    c_alt_euler: { roll: round(cAlt.eu.roll, 4), pitch: round(cAlt.eu.pitch, 4), yaw: round(cAlt.eu.yaw, 4) },
    c_alt_t: cAlt.t.map(v => round(v, 5)),
    c_even_fit: { roll: round(cEven.eu.roll, 4), pitch: round(cEven.eu.pitch, 4), yaw: round(cEven.eu.yaw, 4), t: cEven.t.map(v => round(v, 5)) },
    c_odd_fit: { roll: round(cOdd.eu.roll, 4), pitch: round(cOdd.eu.pitch, 4), yaw: round(cOdd.eu.yaw, 4), t: cOdd.t.map(v => round(v, 5)) },
    normal_residual: {},
    holdout: {},
};
for (const [tag, R, t] of [["A", I3, [0, 0, 0]], ["TLS", R_tls, [0, 0, 0]], ["B", R_Bc2r, t_Bc2r],
                           ["C", cPrimary.R, cPrimary.t], ["C_ALT", cAlt.R, cAlt.t]]) {
    const rs = normalResiduals(cfFine, idxRFine, R, t, 0.30);
    C_QA.normal_residual[tag] = { n: rs.length, p50: qOnly(rs, 0.5), p90: qOnly(rs, 0.9), p99: qOnly(rs, 0.99) };
    log("[r36] normal-residual " + tag + ": n=" + rs.length + " p50=" + C_QA.normal_residual[tag].p50 + " p90=" + C_QA.normal_residual[tag].p90 + " p99=" + C_QA.normal_residual[tag].p99);
}
{
    const rsE = normalResiduals(oddHalf, idxRFine, cEven.R, cEven.t, 0.30);
    const rsO = normalResiduals(evenHalf, idxRFine, cOdd.R, cOdd.t, 0.30);
    const rsAll = normalResiduals(cfFine, idxRFine, cPrimary.R, cPrimary.t, 0.30);
    C_QA.holdout = { fit_even_eval_odd: { n: rsE.length, p50: qOnly(rsE, 0.5), p90: qOnly(rsE, 0.9) },
                     fit_odd_eval_even: { n: rsO.length, p50: qOnly(rsO, 0.5), p90: qOnly(rsO, 0.9) },
                     fit_all_eval_all: { n: rsAll.length, p50: qOnly(rsAll, 0.5), p90: qOnly(rsAll, 0.9) } };
    log("[r36] C holdout: " + JSON.stringify(C_QA.holdout));
}

/* 条件变换表 */
const COND_TF = {
    A: { R: I3, t: [0, 0, 0] },
    TLS: { R: R_tls, t: [0, 0, 0] },
    B: { R: R_Bc2r, t: t_Bc2r },
    C: { R: cPrimary.R, t: cPrimary.t },
    C_ALT: { R: cAlt.R, t: cAlt.t },
};
function alignPoint(cond, x, y, z) {
    const tf = COND_TF[cond];
    return [tf.R[0] * x + tf.R[1] * y + tf.R[2] * z + tf.t[0],
            tf.R[3] * x + tf.R[4] * y + tf.R[5] * z + tf.t[1],
            tf.R[6] * x + tf.R[7] * y + tf.R[8] * z + tf.t[2]];
}
function probeRef(x, y, z) {
    const tier = scanTierCells(refMapObj.voxels, x, y, z, OCC_MIN, false);
    const any = scanAnyCells(refMapObj.voxels, x, y, z, "occ");
    return { tier: tier, any: any };
}
function refLabelOf(s) {
    if (s.tier.d !== null && s.tier.d < MATCH_R) return "MATCHED";
    if (s.tier.d !== null) return axisLabel(s.tier.dx, s.tier.dy, s.tier.dz);
    if (s.any.any) return "REFERENCE_HOLE";
    return "NO_REFERENCE_NEIGHBOR";
}
function primaryOf(cond, s, oStats) {
    if (s.tier.d !== null && s.tier.d < MATCH_R) return "MATCHED_REF_" + COND_LABEL[cond];
    if (s.tier.d !== null) return axisLabel(s.tier.dx, s.tier.dy, s.tier.dz);
    if (s.any.any) return "REFERENCE_HOLE";
    if (oStats.any) return "TIER_REJECT";
    return "NO_REFERENCE_NEIGHBOR";
}
function bucketOf(cond, primary, matched, matchedA, o1max) {
    if (primary.startsWith("MATCHED_REF_")) return matchedA ? "REFERENCE_ABSORB" : "REGISTRATION";
    if (primary === "REFERENCE_HOLE" || primary === "NO_REFERENCE_NEIGHBOR") return "REFERENCE_MISSING";
    if (primary === "TIER_REJECT") return (o1max !== null && o1max >= PL.PIPE.bg_occ_supported) ? "SPARSE_GATE" : "REFERENCE_MISSING";
    return "MATCHER_GEOMETRY";
}
function stateOf(cond, matched, matchedA, matchedC, scan, oStats, o1max) {
    if (matched) return "ABSORB";
    if (cond !== "C" && matchedC) return "REG_GAP";
    if (scan.tier.d !== null) return "GEOM";
    if (scan.any.any) return "MISSING";
    if (oStats.any) return (o1max !== null && o1max >= PL.PIPE.bg_occ_supported) ? "SPARSE" : "MISSING";
    return "MISSING";
}

/* ---- corroboration index（f55 族 proxy；r7 同源） ---- */
log("[r36] building corroboration index from frames " + CORROB_FRAMES.join(",") + " ...");
const CORROB = (function () {
    const cell = 0.10, frameIdx = new Map();
    for (const fi of CORROB_FRAMES) {
        const sh = shadowExtract(CUR.frames[fi], onlineMap);
        const idx = new Map();
        for (const pi of sh.resIdx) {
            const x = CUR.frames[fi][4 * pi], y = CUR.frames[fi][4 * pi + 1], z = CUR.frames[fi][4 * pi + 2];
            const k = Math.floor(x / cell) + "," + Math.floor(y / cell) + "," + Math.floor(z / cell);
            let a = idx.get(k); if (!a) { a = []; idx.set(k, a); }
            a.push([x, y, z]);
        }
        frameIdx.set(fi, idx);
    }
    function corrobCount(fi, x, y, z) {
        let n = 0;
        for (const cfi of CORROB_FRAMES) {
            if (cfi === fi) continue;
            const idx = frameIdx.get(cfi);
            const ix = Math.floor(x / cell), iy = Math.floor(y / cell), iz = Math.floor(z / cell);
            let hit = false;
            for (let a = -1; a <= 1 && !hit; a++) for (let b = -1; b <= 1 && !hit; b++) for (let c = -1; c <= 1 && !hit; c++) {
                const arr = idx.get((ix + a) + "," + (iy + b) + "," + (iz + c));
                if (!arr) continue;
                for (const p of arr) {
                    const dx = p[0] - x, dy = p[1] - y, dz = p[2] - z;
                    if (dx * dx + dy * dy + dz * dz <= 0.01) { hit = true; break; }
                }
            }
            if (hit) n++;
        }
        return n;
    }
    return { corrobCount: corrobCount, frames: CORROB_FRAMES };
})();

/* ---- probe 复现所需 clusterNear（r7 同源） ---- */
function clusterNear(frameIdx, cx, cy, half) {
    const fr = CUR.frames[frameIdx];
    const fg = PL.extract_foreground(fr, onlineMap);
    const iso = PL.cleanup_isolated_fg(fg.fg_xyzi);
    const rawC = PL.cluster_voxels(PL.voxelize(iso.xyzi));
    let bestCi = -1, bestN = 0;
    for (let ci = 0; ci < rawC.length; ci++) {
        const f = PL.cluster_features(rawC[ci]);
        if (!f.ok) continue;
        if (Math.abs(f.cx - cx) <= half && Math.abs(f.cy - cy) <= half && f.n > bestN) { bestN = f.n; bestCi = ci; }
    }
    if (bestCi < 0) return [];
    const keys = new Set(rawC[bestCi].keys);
    const pts = [];
    for (let k = 0; k < iso.xyzi.length; k += 4) {
        const x = iso.xyzi[k], y = iso.xyzi[k + 1], z = iso.xyzi[k + 2];
        if (keys.has(PL.key_vox(x, y))) pts.push([x, y, z]);
    }
    return pts;
}

/* ---- 人窗口中心（R3.5 同款站点窗；clean 帧用最大簇质心） ---- */
const HUMAN_FRAMES = Array.from(new Set([...NEAR_FURNITURE_FRAMES, ...CLEAN_FRAMES])).sort((a, b) => a - b);
const PERSON_CENTER = {};
for (const fi of HUMAN_FRAMES) {
    if (NEAR_FURNITURE_FRAMES.includes(fi)) { PERSON_CENTER[fi] = [FURNITURE_XY.x, FURNITURE_XY.y]; continue; }
    let best = null;
    for (const cand of [[FURNITURE_XY.x, FURNITURE_XY.y], [1.52, -0.40]]) {
        const pts = clusterNear(fi, cand[0], cand[1], 0.80);
        if (pts.length >= 100 && (!best || pts.length > best.n)) {
            let sx = 0, sy = 0;
            for (const p of pts) { sx += p[0]; sy += p[1]; }
            best = { x: sx / pts.length, y: sy / pts.length, n: pts.length };
        }
    }
    PERSON_CENTER[fi] = best ? [round(best.x, 3), round(best.y, 3)] : [1.52, -0.40];
    log("[r36] person window f" + fi + ": center=[" + PERSON_CENTER[fi].join(",") + "] n=" + (best ? best.n : 0));
}

/* ---- r7 baseline 期望（复现门） ---- */
const r35Path = path.join(HERE, "..", "2026-10-06_hrw03_r7", "02_attribution_results.json");
const R35 = (!FRAME_SUBSET && fs.existsSync(r35Path)) ? JSON.parse(fs.readFileSync(r35Path, "utf8")) : null;

/* ---- 聚合器 ---- */
function newCondAgg() {
    return { absorbed: 0, reasons: {}, buckets: {}, dAll: [], dMatched: [], online_matched: 0 };
}
function newAgg6() {
    return { n: 0, cond: { A: newCondAgg(), TLS: newCondAgg(), B: newCondAgg(), C: newCondAgg(), C_ALT: newCondAgg() },
             states: { A: {}, B: {}, C: {} }, trans: { A2B: {}, B2C: {}, A2C: {} },
             recovery: { B: { rec: 0, lost: 0 }, C: { rec: 0, lost: 0 }, C_ALT: { rec: 0, lost: 0 } },
             zband: {}, proxy: {}, corrob: {} };
}
function aggAdd6(a, rec) {
    a.n++;
    for (const cond of COND_KEYS) {
        const c = a.cond[cond], s = rec.scans[cond], m = rec.matched[cond];
        if (m) { c.absorbed++; c.dMatched.push(s.tier.d); }
        if (s.tier.d !== null) c.dAll.push(s.tier.d);
        c.reasons[rec.labels[cond]] = (c.reasons[rec.labels[cond]] || 0) + 1;
        c.buckets[rec.buckets[cond]] = (c.buckets[rec.buckets[cond]] || 0) + 1;
        if (rec.matched_online) c.online_matched++;
    }
    a.states.A[rec.states.A] = (a.states.A[rec.states.A] || 0) + 1;
    a.states.B[rec.states.B] = (a.states.B[rec.states.B] || 0) + 1;
    a.states.C[rec.states.C] = (a.states.C[rec.states.C] || 0) + 1;
    const tk = rec.states.A + "->" + rec.states.B;
    a.trans.A2B[tk] = (a.trans.A2B[tk] || 0) + 1;
    const tk2 = rec.states.B + "->" + rec.states.C;
    a.trans.B2C[tk2] = (a.trans.B2C[tk2] || 0) + 1;
    const tk3 = rec.states.A + "->" + rec.states.C;
    a.trans.A2C[tk3] = (a.trans.A2C[tk3] || 0) + 1;
    if (rec.matched.B && !rec.matched.A) a.recovery.B.rec++;
    if (rec.matched.A && !rec.matched.B) a.recovery.B.lost++;
    if (rec.matched.C && !rec.matched.A) a.recovery.C.rec++;
    if (rec.matched.A && !rec.matched.C) a.recovery.C.lost++;
    if (rec.matched.C_ALT && !rec.matched.A) a.recovery.C_ALT.rec++;
    if (rec.matched.A && !rec.matched.C_ALT) a.recovery.C_ALT.lost++;
    const zb = a.zband[rec.z_band] || (a.zband[rec.z_band] = { n: 0, abs: {} });
    zb.n++;
    for (const cond of COND_KEYS) if (rec.matched[cond]) zb.abs[cond] = (zb.abs[cond] || 0) + 1;
    if (rec.proxy_class) {
        const pr = a.proxy[rec.proxy_class] || (a.proxy[rec.proxy_class] = { n: 0, abs: {} });
        pr.n++;
        for (const cond of COND_KEYS) if (rec.matched[cond]) pr.abs[cond] = (pr.abs[cond] || 0) + 1;
    }
    if (rec.corrob_n !== null) a.corrob[rec.corrob_n] = (a.corrob[rec.corrob_n] || 0) + 1;
}
function aggFinalize6(a) {
    const out = { residual_points: a.n, conditions: {}, states: { A: Object.assign({}, a.states.A), B: Object.assign({}, a.states.B), C: Object.assign({}, a.states.C) },
                  transitions: { A2B: Object.assign({}, a.trans.A2B), B2C: Object.assign({}, a.trans.B2C), A2C: Object.assign({}, a.trans.A2C) },
                  recovery: a.recovery, zband: a.zband, proxy_class: a.proxy, corrob_n: a.corrob };
    out.transition_share = {};
    for (const k of ["A2B", "B2C", "A2C"]) {
        out.transition_share[k] = {};
        for (const tk in a.trans[k]) out.transition_share[k][tk] = round(a.trans[k][tk] / (a.n || 1));
    }
    for (const cond of COND_KEYS) {
        const c = a.cond[cond], shareB = {}, shareR = {};
        for (const k in c.buckets) shareB[k] = round(c.buckets[k] / (a.n || 1));
        for (const k in c.reasons) shareR[k] = round(c.reasons[k] / (a.n || 1));
        out.conditions[cond] = {
            absorbed: c.absorbed,
            absorbed_share: round(c.absorbed / (a.n || 1)),
            residual: a.n - c.absorbed,
            residual_share: round((a.n - c.absorbed) / (a.n || 1)),
            bucket_counts: Object.assign({}, c.buckets),
            bucket_share: shareB,
            reason_counts: Object.assign({}, c.reasons),
            reason_share: shareR,
            d_all: quantiles(c.dAll),
            d_matched: quantiles(c.dMatched),
            matched_online_selfcheck: c.online_matched,
        };
    }
    out.gain = {};
    for (const cond of ["B", "C", "C_ALT"]) {
        const resA = a.n - a.cond.A.absorbed, resX = a.n - a.cond[cond].absorbed;
        out.gain[cond] = { residual_A: resA, residual_X: resX, points: resA - resX,
                           pp: round((resA - resX) / (a.n || 1) * 100, 3),
                           rel: resA ? round((resA - resX) / resA) : null };
    }
    return out;
}
function dominantBucketOf(buckets) {
    let best = null, bn = -1;
    for (const b of ["REFERENCE_ABSORB", "REGISTRATION", "REFERENCE_MISSING", "MATCHER_GEOMETRY", "SPARSE_GATE", "OTHER"]) {
        const c = buckets[b] || 0; if (c > bn) { bn = c; best = b; }
    }
    return bn > 0 ? best : null;
}

/* ---- 输出 CSV 表头 ---- */
const COND_CSV = ["A", "TLS", "B", "C", "C_ALT"];
const csvPointLines = [];
const csvPointHeader = ["session_id", "frame_index", "frame_seq", "point_id",
    "x", "y", "z", "z_band",
    "in_wd01_region", "in_wd02_proxy", "in_furniture_window", "corrob_n", "proxy_class",
    "d_A", "d_TLS", "d_B", "d_C", "d_C_ALT",
    "matched_A", "matched_TLS", "matched_B", "matched_C", "matched_C_ALT",
    "recover_B", "recover_C", "recover_C_ALT", "lost_B", "lost_C_ALT",
    "state_A", "state_B", "state_C",
    "bucket_A", "bucket_B", "bucket_C", "bucket_C_ALT",
    "label_A", "label_B", "label_C",
    "nearest_ref_x_C", "nearest_ref_y_C", "nearest_ref_z_C", "nearest_ref_voxel_C", "nearest_ref_occ_C", "nearest_ref_tier_C",
    "delta_d_AC", "delta_d_BC", "shell_A", "shell_C"];
csvPointLines.push(csvPointHeader.join(","));
const csvVoxelLines = [];
const csvVoxelHeader = ["session_id", "frame_index", "voxel_ix_iy_iz", "point_count",
    "dom_bucket_A", "dom_bucket_B", "dom_bucket_C", "dom_bucket_C_ALT",
    "absorbed_A_count", "absorbed_B_count", "absorbed_C_count",
    "recover_B_count", "recover_C_count", "recover_C_ALT_count"];
csvVoxelLines.push(csvVoxelHeader.join(","));

/* ---- 全量聚合 ---- */
const baseline = { frames_compared: 0, count_mismatch_frames: 0, point_mismatch_points: 0, conservation_fail_frames: 0, self_check_violations: 0 };
const groups = { ALL: newAgg6(), WD01: newAgg6(), WD02: newAgg6(), PROBLEM: newAgg6(), CLEAN: newAgg6(), NEAR_FURN: newAgg6() };
const GROUP_PRED = {
    ALL: (fi, r) => true,
    WD01: (fi, r) => r.in_wd01,
    WD02: (fi, r) => r.in_wd02,
    PROBLEM: (fi, r) => PROBLEM_FRAMES.includes(fi),
    CLEAN: (fi, r) => CLEAN_FRAMES.includes(fi),
    NEAR_FURN: (fi, r) => NEAR_FURNITURE_FRAMES.includes(fi) && r.in_furn,
};
const groupVoxel = {};
for (const g of Object.keys(GROUP_PRED)) { groupVoxel[g] = { A: new Map(), B: new Map(), C: new Map(), C_ALT: new Map() }; }
const HS = { near: {}, clean: {}, proxies: {} };
for (const cls of ["STATIC_STATION", "AMBIGUOUS", "NON_STATIC"]) HS.proxies[cls] = { n: 0, abs: {} };
for (const fi of HUMAN_FRAMES) HS.near[fi] = null; /* 复用容器 */

const frameRows = [];
const CAND_BANDS = ["z>=1.2", "0.8-1.2", "0.3-0.8"];
function bandOf(z) { return z >= 1.2 ? "z>=1.2" : z >= 0.8 ? "0.8-1.2" : z >= 0.3 ? "0.3-0.8" : null; }

/* ---- 主循环 ---- */
const useFrames = FRAME_SUBSET || Array.from({ length: N_CUR }, (_, i) => i);
for (const fi of useFrames) {
    const clean = CUR.frames[fi];
    const sh = shadowExtract(clean, onlineMap);
    const prod = PL.extract_foreground(clean, onlineMap);
    baseline.frames_compared++;
    if (sh.nRes !== prod.n_fg || sh.nZ + sh.nBG !== prod.n_dropped) baseline.count_mismatch_frames++;
    if (sh.fg.length !== prod.fg_xyzi.length) baseline.point_mismatch_points += 1;
    else for (let i = 0; i < sh.fg.length; i++) if (sh.fg[i] !== prod.fg_xyzi[i]) { baseline.point_mismatch_points++; break; }
    if (sh.nZ + sh.nBG + sh.nRes !== sh.nIn) baseline.conservation_fail_frames++;

    const isFocal = FOCAL_FRAMES.includes(fi);
    const doProxy = PROXY_FRAMES.includes(fi);
    const humanCenter = PERSON_CENTER[fi] || null;
    const frameAgg = { ALL: newAgg6(), WD01: newAgg6(), WD02: newAgg6(), PROBLEM: newAgg6(), CLEAN: newAgg6(), NEAR_FURN: newAgg6() };
    const frameCond = { A: newCondAgg(), TLS: newCondAgg(), B: newCondAgg(), C: newCondAgg(), C_ALT: newCondAgg() };
    const frameTrans = { A2B: {}, B2C: {}, A2C: {} };
    const voxMaps = { A: new Map(), B: new Map(), C: new Map(), C_ALT: new Map() };
    const framePerson = humanCenter ? { center: humanCenter, n: 0, bands: {} } : null;
    let dMatchedSum = 0, dMatchedN = 0;

    for (let j = 0; j < sh.resIdx.length; j++) {
        const pi = sh.resIdx[j];
        const k4 = pi * 4;
        const x = clean[k4], y = clean[k4 + 1], z = clean[k4 + 2];
        /* online 视角（生产语义自检） */
        const oT = scanTierCells(onlineMap, x, y, z, 0, false);
        const matchedOnline = oT.d !== null && oT.d < MATCH_R;
        const oStats = scanAnyCells(onlineStats.stats, x, y, z, "hits");
        const o1 = scanAnyCells(curMap1Obj.voxels, x, y, z, "occ");
        /* 条件探针 */
        const scans = {}, matched = {}, labels = {}, buckets = {}, states = {};
        for (const cond of COND_KEYS) {
            const [X, Y, Z] = alignPoint(cond, x, y, z);
            const s = probeRef(X, Y, Z);
            scans[cond] = s;
            matched[cond] = s.tier.d !== null && s.tier.d < MATCH_R;
            labels[cond] = primaryOf(cond, s, oStats);
            buckets[cond] = bucketOf(cond, labels[cond], matched[cond], matched.A, o1.max);
        }
        states.A = stateOf("A", matched.A, matched.A, matched.C, scans.A, oStats, o1.max);
        states.B = stateOf("B", matched.B, matched.B, matched.C, scans.B, oStats, o1.max);
        states.C = stateOf("C", matched.C, matched.C, matched.C, scans.C, oStats, o1.max);
        const corrobN = doProxy ? CORROB.corrobCount(fi, x, y, z) : null;
        const proxyClass = corrobN === null ? null : (corrobN >= 2 ? "STATIC_STATION" : corrobN === 0 ? "NON_STATIC" : "AMBIGUOUS");
        const inWd01 = Math.hypot(x - WD01_XY.x, y - WD01_XY.y) <= 0.9;
        const inWd02 = Math.hypot(x, y) > 8 || WD02_REPS.some(r => Math.hypot(x - r.x, y - r.y) <= 1.5);
        const inFurn = Math.hypot(x - FURNITURE_XY.x, y - FURNITURE_XY.y) <= 0.6;
        const rec = { x: x, y: y, z: z, z_band: zBandOf(z), scans: scans, matched: matched, labels: labels, buckets: buckets,
                      states: states, matched_online: matchedOnline, proxy_class: proxyClass, corrob_n: corrobN,
                      in_wd01: inWd01, in_wd02: inWd02, in_furn: inFurn };
        if (matchedOnline) baseline.self_check_violations++;
        aggAdd6(frameAgg.ALL, rec);
        if (PROBLEM_FRAMES.includes(fi)) aggAdd6(frameAgg.PROBLEM, rec);
        if (CLEAN_FRAMES.includes(fi)) aggAdd6(frameAgg.CLEAN, rec);
        if (NEAR_FURNITURE_FRAMES.includes(fi) && inFurn) aggAdd6(frameAgg.NEAR_FURN, rec);
        if (inWd01) aggAdd6(frameAgg.WD01, rec);
        if (inWd02) aggAdd6(frameAgg.WD02, rec);
        aggAdd6(groups.ALL, rec);
        if (PROBLEM_FRAMES.includes(fi)) aggAdd6(groups.PROBLEM, rec);
        if (CLEAN_FRAMES.includes(fi)) aggAdd6(groups.CLEAN, rec);
        if (NEAR_FURNITURE_FRAMES.includes(fi) && inFurn) aggAdd6(groups.NEAR_FURN, rec);
        if (inWd01) aggAdd6(groups.WD01, rec);
        if (inWd02) aggAdd6(groups.WD02, rec);
        for (const cond of COND_KEYS) {
            if (matched[cond]) frameCond[cond].absorbed++;
            frameCond[cond].reasons[labels[cond]] = (frameCond[cond].reasons[labels[cond]] || 0) + 1;
            frameCond[cond].buckets[buckets[cond]] = (frameCond[cond].buckets[buckets[cond]] || 0) + 1;
        }
        const tk = states.A + "->" + states.B; frameTrans.A2B[tk] = (frameTrans.A2B[tk] || 0) + 1;
        const tk2 = states.B + "->" + states.C; frameTrans.B2C[tk2] = (frameTrans.B2C[tk2] || 0) + 1;
        const tk3 = states.A + "->" + states.C; frameTrans.A2C[tk3] = (frameTrans.A2C[tk3] || 0) + 1;
        if (matched.B && matched.C && !matched.A) dMatchedSum += scans.C.tier.d, dMatchedN++;
        /* 分组 voxel（A/B/C/C_ALT） */
        for (const g of Object.keys(GROUP_PRED)) {
            if (!GROUP_PRED[g](fi, rec)) continue;
            const vk = fi + "|" + bg_key_ijk(Math.floor(x / VX), Math.floor(y / VX), Math.floor(z / VZ));
            for (const cond of ["A", "B", "C", "C_ALT"]) {
                const gm = groupVoxel[g][cond];
                let m = gm.get(vk);
                if (!m) { m = { n: 0, buckets: {} }; gm.set(vk, m); }
                m.n++; m.buckets[buckets[cond]] = (m.buckets[buckets[cond]] || 0) + 1;
            }
        }
        /* 帧 voxel（04b CSV） */
        {
            const vk = bg_key_ijk(Math.floor(x / VX), Math.floor(y / VX), Math.floor(z / VZ));
            for (const cond of ["A", "B", "C", "C_ALT"]) {
                const vm = voxMaps[cond];
                let m = vm.get(vk);
                if (!m) { m = { n: 0, buckets: {}, abs: 0, rec: 0 }; vm.set(vk, m); }
                m.n++; m.buckets[buckets[cond]] = (m.buckets[buckets[cond]] || 0) + 1;
                if (matched[cond]) m.abs++;
                if (matched[cond] && !matched.A) m.rec++;
            }
        }
        /* human safety */
        if (framePerson) {
            const dx = x - humanCenter[0], dy = y - humanCenter[1];
            if (dx * dx + dy * dy <= 0.36) {
                framePerson.n++;
                const band = bandOf(z);
                if (band) {
                    const b = framePerson.bands[band] || (framePerson.bands[band] = { n: 0, abs: {} });
                    b.n++;
                    for (const cond of COND_KEYS) if (matched[cond]) b.abs[cond] = (b.abs[cond] || 0) + 1;
                }
            }
        }
        if (proxyClass) {
            const pr = HS.proxies[proxyClass]; pr.n++;
            for (const cond of COND_KEYS) if (matched[cond]) pr.abs[cond] = (pr.abs[cond] || 0) + 1;
        }
        /* focal CSV（含 registration shell 数据） */
        if (isFocal) {
            const cScan = scans.C, aScan = scans.A;
            const cRec = cScan.tier.rec;
            csvPointLines.push([CUR_SID, fi, CUR.frame_slices[fi].seq, j,
                round(x, 4), round(y, 4), round(z, 4), rec.z_band,
                inWd01 ? 1 : 0, inWd02 ? 1 : 0, inFurn ? 1 : 0,
                corrobN === null ? "" : corrobN, proxyClass === null ? "" : proxyClass,
                round(aScan.tier.d), round(scans.TLS.tier.d), round(scans.B.tier.d), round(cScan.tier.d), round(scans.C_ALT.tier.d),
                matched.A ? 1 : 0, matched.TLS ? 1 : 0, matched.B ? 1 : 0, matched.C ? 1 : 0, matched.C_ALT ? 1 : 0,
                (matched.B && !matched.A) ? 1 : 0, (matched.C && !matched.A) ? 1 : 0, (matched.C_ALT && !matched.A) ? 1 : 0,
                (matched.A && !matched.B) ? 1 : 0, (matched.A && !matched.C_ALT) ? 1 : 0,
                states.A, states.B, states.C,
                buckets.A, buckets.B, buckets.C, buckets.C_ALT,
                labels.A, labels.B, labels.C,
                cRec ? round(cRec.x) : "", cRec ? round(cRec.y) : "", cRec ? round(cRec.z) : "",
                cScan.tier.key ? (function () { const ij = bg_decode(cScan.tier.key); return ij[0] + ";" + ij[1] + ";" + ij[2]; })() : "",
                cRec ? round(cRec.occ, 6) : "", cRec ? (cRec.occ >= 0.85 ? "strong" : cRec.occ >= 0.65 ? "supported" : "below") : "",
                (aScan.tier.d !== null && cScan.tier.d !== null) ? round(aScan.tier.d - cScan.tier.d) : "",
                (scans.B.tier.d !== null && cScan.tier.d !== null) ? round(scans.B.tier.d - cScan.tier.d) : "",
                shellBandOf(aScan.tier.d), shellBandOf(cScan.tier.d)].join(","));
        }
    }

    /* 帧 voxel → 04b CSV */
    voxMaps.A.forEach((m, vk) => {
        const ij = bg_decode(vk);
        const mB = voxMaps.B.get(vk), mC = voxMaps.C.get(vk), mCA = voxMaps.C_ALT.get(vk);
        csvVoxelLines.push([CUR_SID, fi, ij[0] + ";" + ij[1] + ";" + ij[2], m.n,
            dominantBucketOf(m.buckets), mB ? dominantBucketOf(mB.buckets) : "",
            mC ? dominantBucketOf(mC.buckets) : "", mCA ? dominantBucketOf(mCA.buckets) : "",
            m.abs, mB ? mB.abs : 0, mC ? mC.abs : 0,
            mB ? mB.rec : 0, mC ? mC.rec : 0, mCA ? mCA.rec : 0].join(","));
    });

    if (framePerson) {
        if (NEAR_FURNITURE_FRAMES.includes(fi)) HS.near[fi] = framePerson; else HS.clean[fi] = framePerson;
    }
    frameRows.push({
        frame_index: fi, frame_seq: CUR.frame_slices[fi].seq,
        n_raw: CUR.frame_slices[fi].count, n_denoise: clean.length / 4,
        n_range_reject: CUR.frame_slices[fi].count - clean.length / 4,
        n_z_reject: sh.nZ, n_bg_match: sh.nBG, n_residual: sh.nRes,
        production_n_fg: prod.n_fg, production_n_dropped: prod.n_dropped,
        conservation_ok: sh.nZ + sh.nBG + sh.nRes === sh.nIn && sh.nRes === prod.n_fg && sh.nZ + sh.nBG === prod.n_dropped,
        point_identity_ok: sh.fg.length === prod.fg_xyzi.length,
        mean_d_C_matched_regAC: dMatchedN ? round(dMatchedSum / dMatchedN) : null,
        conditions: {},
        transitions: frameTrans,
    });
    for (const cond of COND_KEYS) {
        frameRows[frameRows.length - 1].conditions[cond] = {
            absorbed: frameCond[cond].absorbed,
            buckets: Object.assign({}, frameCond[cond].buckets),
            reasons: Object.assign({}, frameCond[cond].reasons),
        };
    }
    if (fi % 20 === 0 || isFocal) log("[r36] frame " + fi + " done (residual " + sh.nRes + ", " + (Date.now() - T0) + "ms)");
}

/* ---- micro-cases / R3.3 A 层 / probe 复现 ---- */
const micro = microCases(onlineMap);
let aLevel = null;
if (!FRAME_SUBSET) {
    const thin = [];
    CUR.frames.forEach(fr => {
        const pts = [];
        for (let k = 0; k < fr.length; k += 4) {
            const z = fr[k + 2];
            if (z < PL.PIPE.ground_keep_below_m || z > PL.PIPE.z_max_m) continue;
            pts.push([fr[k], fr[k + 1], z]);
        }
        const stride = Math.max(1, Math.floor(pts.length / 3000));
        for (let i = 0; i < pts.length; i += stride) thin.push(pts[i]);
    });
    let hit = 0;
    for (const p of thin) { const r = scanTierCells(refMapObj.voxels, p[0], p[1], p[2], OCC_MIN, false); if (r.d !== null && r.d < MATCH_R) hit++; }
    aLevel = { n: thin.length, none_center: round(hit / thin.length, 6), expected: 0.7796, pass: Math.abs(hit / thin.length - 0.7796) <= 0.0005 };
    log("[r36] R3.3 A-layer check (ALL thinned, occ>=0.5, none/center): " + aLevel.none_center + " (expect 0.7796) → " + (aLevel.pass ? "PASS" : "FAIL"));
}
const probeChecks = [];
if (!FRAME_SUBSET) {
    for (const [fi, cx, cy, half, expectHit, expectN] of [[10, 1.45, 0.85, 0.80, 1365, 1564], [55, 1.45, 0.85, 0.80, 621, 3190], [160, 1.45, 0.85, 0.80, 1024, 2429]]) {
        const pts = clusterNear(fi, cx, cy, half);
        let hit = 0;
        for (const p of pts) { const r = scanTierCells(refMapObj.voxels, p[0], p[1], p[2], OCC_MIN, false); if (r.d !== null && r.d < MATCH_R) hit++; }
        const pass = hit === expectHit && pts.length === expectN;
        probeChecks.push({ frame: fi, n: pts.length, center_hits: hit, expected_hits: expectHit, expected_n: expectN, pass: pass });
        log("[r36] probe check f" + fi + ": n=" + pts.length + " center=" + hit + " (expect n=" + expectN + " center=" + expectHit + ") → " + (pass ? "PASS" : "FAIL"));
    }
}

/* ---- conservation ---- */
const conservation = {
    frames: frameRows.length,
    all_conservation_ok: frameRows.every(r => r.conservation_ok),
    totals: {
        n_raw: frameRows.reduce((a, r) => a + r.n_raw, 0),
        n_denoise: frameRows.reduce((a, r) => a + r.n_denoise, 0),
        n_range_reject: frameRows.reduce((a, r) => a + r.n_range_reject, 0),
        n_z_reject: frameRows.reduce((a, r) => a + r.n_z_reject, 0),
        n_bg_match: frameRows.reduce((a, r) => a + r.n_bg_match, 0),
        n_residual: frameRows.reduce((a, r) => a + r.n_residual, 0),
    },
};
conservation.totals_ok = conservation.totals.n_raw === conservation.totals.n_denoise + conservation.totals.n_range_reject
    && conservation.totals.n_denoise === conservation.totals.n_z_reject + conservation.totals.n_bg_match + conservation.totals.n_residual;
const partitionOk = frameRows.every(r => Object.values(r.conditions.B.buckets).reduce((a, b) => a + b, 0) === r.n_residual)
    && frameRows.every(r => Object.values(r.conditions.A.buckets).reduce((a, b) => a + b, 0) === r.n_residual)
    && frameRows.every(r => Object.values(r.conditions.C.buckets).reduce((a, b) => a + b, 0) === r.n_residual);

/* ---- 分组 finalize ---- */
const groupsOut = {};
for (const g of Object.keys(groups)) {
    const f = aggFinalize6(groups[g]);
    /* voxel 级（A/B/C/C_ALT） */
    f.voxel = {};
    for (const cond of ["A", "B", "C", "C_ALT"]) {
        const rows = {};
        groupVoxel[g][cond].forEach(v => { const dom = dominantBucketOf(v.buckets); rows[dom] = (rows[dom] || 0) + 1; });
        const t = Object.values(rows).reduce((a, b) => a + b, 0);
        const share = {};
        for (const k in rows) share[k] = round(rows[k] / (t || 1));
        f.voxel[cond] = { voxels: t, bucket_counts: rows, bucket_share: share };
    }
    groupsOut[g] = f;
}

/* ---- r7 逐值复现门 ---- */
function countMapEq(a, b) {
    const keys = new Set([...Object.keys(a || {}), ...Object.keys(b || {})]);
    for (const k of keys) if ((a && a[k] || 0) !== (b && b[k] || 0)) return false;
    return true;
}
const r35Gate = { available: !!R35, pass: true, mismatches: [] };
function gateCheck(name, ok, detail) { if (!ok && r35Gate.mismatches.length < 40) r35Gate.mismatches.push({ name: name, detail: detail }); r35Gate.pass = r35Gate.pass && ok; }
if (R35) {
    gateCheck("conservation.totals", JSON.stringify(R35.conservation.totals) === JSON.stringify(conservation.totals),
        { r36: conservation.totals, r35: R35.conservation.totals });
    for (const g of Object.keys(groups)) {
        const A = groupsOut[g], B = R35.groups[g];
        gateCheck(g + ".residual_points", A.residual_points === B.residual_points, { r36: A.residual_points, r35: B.residual_points });
        for (const cond of ["B"]) {
            const a = A.conditions[cond], b = B;
            gateCheck(g + ".bucket_counts", countMapEq(a.bucket_counts, b.bucket_counts), { r36: a.bucket_counts, r35: b.bucket_counts });
            gateCheck(g + ".reason_counts", countMapEq(a.reason_counts, b.reason_counts), { r36: a.reason_counts, r35: b.reason_counts });
            gateCheck(g + ".matched_ref", a.absorbed === (b.matched_ref || {}).icp && true, { r36: a.absorbed, r35: b.matched_ref });
        }
        const vB = A.voxel.B;
        gateCheck(g + ".voxels", vB.voxels === B.voxels, { r36: vB.voxels, r35: B.voxels });
        gateCheck(g + ".voxel_bucket_counts", countMapEq(vB.bucket_counts, B.voxel_bucket_counts), { r36: vB.bucket_counts, r35: B.voxel_bucket_counts });
    }
    const r35Frames = R35.frames;
    gateCheck("frames.length", r35Frames.length === frameRows.length, { r36: frameRows.length, r35: r35Frames.length });
    for (let i = 0; i < Math.min(r35Frames.length, frameRows.length); i++) {
        const a = frameRows[i], b = r35Frames[i];
        if (a.frame_index !== b.frame_index || a.n_residual !== b.n_residual || a.n_z_reject !== b.n_z_reject || a.n_bg_match !== b.n_bg_match
            || a.n_denoise !== b.n_denoise || !countMapEq(a.conditions.B.buckets, b.attribution_icp.bucket_counts)
            || !countMapEq(a.conditions.B.reasons, b.attribution_icp.reason_counts)) {
            gateCheck("frame[" + i + "]", false, { r36: { fi: a.frame_index, n_res: a.n_residual, buckets: a.conditions.B.buckets }, r35: { fi: b.frame_index, n_res: b.n_residual, buckets: b.attribution_icp.bucket_counts } });
            break;
        }
        if (a.conditions.B.absorbed !== b.attribution_icp.matched_ref.icp || (a.conditions.A.absorbed !== b.attribution_icp.matched_ref.none) || (a.conditions.TLS.absorbed !== b.attribution_icp.matched_ref.tls)) {
            gateCheck("frame[" + i + "].matched_ref", false, { r36: { A: a.conditions.A.absorbed, TLS: a.conditions.TLS.absorbed, B: a.conditions.B.absorbed }, r35: b.attribution_icp.matched_ref });
            break;
        }
    }
    log("[r36] r35 gate: " + (r35Gate.pass ? "PASS" : "FAIL (" + r35Gate.mismatches.length + " mismatches)"));
    if (!r35Gate.pass) for (const m of r35Gate.mismatches.slice(0, 5)) log("  - " + m.name + ": " + JSON.stringify(m.detail));
}

/* ---- checks 汇总 ---- */
const checks = [];
function addCheck(name, pass, detail) { checks.push({ name: name, pass: pass, detail: detail }); return pass; }
let allPass = true;
allPass = addCheck("G0_baseline_point_identity", baseline.point_mismatch_points === 0 && baseline.count_mismatch_frames === 0,
    { frames: baseline.frames_compared, point_mismatch: baseline.point_mismatch_points, count_mismatch_frames: baseline.count_mismatch_frames }) && allPass;
allPass = addCheck("G0_micro_cases", micro.pass === true, micro) && allPass;
allPass = addCheck("conservation", conservation.all_conservation_ok && conservation.totals_ok && baseline.conservation_fail_frames === 0, conservation) && allPass;
allPass = addCheck("label_partition_equals_residual", partitionOk, null) && allPass;
allPass = addCheck("self_check_violations_zero", baseline.self_check_violations === 0, { n: baseline.self_check_violations }) && allPass;
allPass = addCheck("online_map_replica_equivalence", eqChk.pass, eqChk) && allPass;
allPass = addCheck("icp_rerun_repro", icp.pass, { euler: { roll: round(icp.eu.roll), pitch: round(icp.eu.pitch), yaw: round(icp.eu.yaw) }, t: icp.t.map(v => round(v, 5)), iters: icp.iters }) && allPass;
allPass = addCheck("ref_map_counts_5286_3707", refTotal === 5286 && refOcc05 === 3707, { total: refTotal, occ_ge_05: refOcc05 }) && allPass;
allPass = addCheck("ref_session_online_map_2063", refSessionOnline.size === 2063, { size: refSessionOnline.size }) && allPass;
if (aLevel) allPass = addCheck("r33_A_level_07796", aLevel.pass, aLevel) && allPass;
for (const pc of probeChecks) allPass = addCheck("probe_f" + pc.frame + "_n" + pc.expected_n + "_center" + pc.expected_hits, pc.pass, pc) && allPass;
if (R35) allPass = addCheck("r35_baseline_reproduction", r35Gate.pass, r35Gate.mismatches.slice(0, 10)) && allPass;
allPass = addCheck("C_primary_repro_expected", C_QA.c_primary_match, { euler: { roll: round(cPrimary.eu.roll), pitch: round(cPrimary.eu.pitch), yaw: round(cPrimary.eu.yaw) }, t: cPrimary.t.map(v => round(v, 5)), expect: C_EXPECT }) && allPass;
allPass = addCheck("C_init_robustness", C_QA.c_init_robust, { fromIdentity: { roll: round(cPrimary.eu.roll, 4), pitch: round(cPrimary.eu.pitch, 4) }, fromB: { roll: round(cBchk.eu.roll, 4), pitch: round(cBchk.eu.pitch, 4) } }) && allPass;
allPass = addCheck("C_holdout_consistency", C_QA.holdout.fit_even_eval_odd.p50 <= 0.030 && C_QA.holdout.fit_odd_eval_even.p50 <= 0.030, C_QA.holdout) && allPass;
const shaAfter = inputSHAs();
const inputsUnchanged = JSON.stringify(SHA_BEFORE) === JSON.stringify(shaAfter);
allPass = addCheck("inputs_unchanged", inputsUnchanged, null) && allPass;
const mtimeUnchanged = JSON.stringify(MTIME_BEFORE) === JSON.stringify(productionMTimes());
allPass = addCheck("production_mtime_unchanged", mtimeUnchanged, null) && allPass;

/* ---- 输出对象 ---- */
const stats = {
    tool: "W03-R3.6 / registration causality + shared-frame validation (offline, read-only)",
    mode: DIGEST_ONLY ? "digest-only" : FRAME_SUBSET ? "subset" : "full",
    node: process.version,
    provenance: {
        sha_before: SHA_BEFORE, sha_after: shaAfter, inputs_unchanged: inputsUnchanged,
        transforms: { cur: { sid: CUR_SID, job: CUR.tf.job, transform_id: CUR.tf.transform_id },
                      ref: { sid: REF_SID, job: REF.tf.job, transform_id: REF.tf.transform_id } },
    },
    conditions: {
        A: { name: "production/current (none)", R: COND_TF.A.R, t: COND_TF.A.t },
        B: { name: "R3.2/R3.5 fixed ICP (cur->ref)", R: R_Bc2r, t: t_Bc2r.map(v => round(v, 8)), icp_ref2cur: { euler: { roll: round(icp.eu.roll), pitch: round(icp.eu.pitch), yaw: round(icp.eu.yaw) }, t: icp.t.map(v => round(v, 6)), iters: icp.iters } },
        C: { name: "static-structure point-to-plane oracle-like (cur->ref)", R: cPrimary.R, t: cPrimary.t.map(v => round(v, 8)), euler: { roll: round(cPrimary.eu.roll), pitch: round(cPrimary.eu.pitch), yaw: round(cPrimary.eu.yaw) }, iters: cPrimary.iters, fit: "curFine(strong,0.06) -> refFine(occ>=0.9,0.06), normals 0.10, trimmed ppICP 5-scale" },
        C_ALT: { name: "second basin (init=tls)", R: cAlt.R, t: cAlt.t.map(v => round(v, 8)), euler: { roll: round(cAlt.eu.roll), pitch: round(cAlt.eu.pitch), yaw: round(cAlt.eu.yaw) }, iters: cAlt.iters },
        TLS: { name: "tls-direct (aux)", R: R_tls, t: [0, 0, 0] },
    },
    c_registration_qa: C_QA,
    params: { match_radius: MATCH_R, occ_min: OCC_MIN, voxel_xy: VX, voxel_z: VZ, neighborhood: "3x3x3",
              conditions: COND_KEYS, z_range: [PL.PIPE.ground_keep_below_m, PL.PIPE.z_max_m],
              focal_frames: FOCAL_FRAMES, problem_frames: PROBLEM_FRAMES, clean_frames: CLEAN_FRAMES,
              near_furniture_frames: NEAR_FURNITURE_FRAMES, proxy_frames: PROXY_FRAMES },
    conservation: conservation,
    baseline: baseline,
    micro: micro,
    groups: groupsOut,
    frames: frameRows,
    human_safety: HS,
    person_centers: PERSON_CENTER,
    checks: checks,
    r35_gate: r35Gate,
    outputs: {},
};
log("[r36] writing CSVs ...");
stats.outputs.point_csv_sha256 = sha256_buf(Buffer.from(csvPointLines.join("\n") + "\n", "utf8"));
stats.outputs.voxel_csv_sha256 = sha256_buf(Buffer.from(csvVoxelLines.join("\n") + "\n", "utf8"));
log("[r36] point_csv_sha256=" + stats.outputs.point_csv_sha256);
log("[r36] voxel_csv_sha256=" + stats.outputs.voxel_csv_sha256);

/* ---- group 速览 ---- */
for (const g of ["ALL", "WD01", "WD02", "PROBLEM", "CLEAN", "NEAR_FURN"]) {
    const A = groupsOut[g];
    log("[r36] group " + g + " n=" + A.residual_points
        + " | absorb A/B/C/C_ALT=" + A.conditions.A.absorbed + "/" + A.conditions.B.absorbed + "/" + A.conditions.C.absorbed + "/" + A.conditions.C_ALT.absorbed
        + " | res B=" + A.conditions.B.residual + " C=" + A.conditions.C.residual
        + " | buckets B=" + JSON.stringify(A.conditions.B.bucket_counts)
        + " | states A=" + JSON.stringify(A.states.A)
        + " | C=" + JSON.stringify(A.states.C));
}

/* ---- digest + 写出 ---- */
const digestObj = Object.assign({}, stats);
delete digestObj.mode;
const digest = sha256_buf(JSON.stringify(digestObj));
log("[r36] DIGEST=" + digest + " (mode-independent)");
log("[r36] CHECK " + (allPass ? "ALL PASS" : "SOME FAILED"));
if (DIGEST_ONLY) {
    log("[r36] digest-only run complete; elapsed=" + (Date.now() - T0) + "ms");
    process.exitCode = allPass ? 0 : 1;
} else {
    stats.generated = new Date().toISOString();
    stats.elapsed_ms = Date.now() - T0;
    stats.digest = digest;
    fs.writeFileSync(path.join(OUTDIR, "03_results.json"), JSON.stringify(stats, null, 1) + "\n");
    fs.writeFileSync(path.join(OUTDIR, "04_point_attribution.csv"), csvPointLines.join("\n") + "\n");
    fs.writeFileSync(path.join(OUTDIR, "04b_voxel_transitions.csv"), csvVoxelLines.join("\n") + "\n");
    log("[r36] wrote 03/04/04b to " + OUTDIR);
    fs.writeFileSync(path.join(OUTDIR, "13_tool_run.log"), L.join("\n") + "\n");
    process.exitCode = allPass ? 0 : 1;
}

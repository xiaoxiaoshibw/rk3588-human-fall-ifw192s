/* ============================================================================
 * W03-R3.5 Step 0 — Residual Attribution Tool（离线只读诊断；production 零改动）
 *
 * 唯一目标：对 `extract_foreground()` 之后留下的 residual 点做离线归因（点级 + voxel 级），
 * 回答「错在哪里」，不实现任何 matcher 变体、不改任何 production 文件/阈值。
 *
 * 依据：docs/human_capture/evidence/2026-10-06_hrw03_r6/02_attribution_design.md
 *   - G0：BASELINE_A shadow 必须与 production `extract_foreground()+_bg_match()` 逐点等价；
 *   - 守恒：N_DENOISE = N_Z_REJECT + N_BG_MATCH + N_RESIDUAL（并 N_RAW = N_DENOISE + N_RANGE_REJECT）；
 *   - taxonomy：XY_MATCH_Z_FAIL / Z_MATCH_XY_FAIL / DISTANCE_OVER_GATE / REFERENCE_HOLE /
 *     TIER_REJECT / NO_REFERENCE_NEIGHBOR / UNKNOWN（互斥主因 + secondary；MATCHED_REF_ICP 为非失败类）；
 *   - stats-preserving 在线 map 复刻（hits/occ/jit/tier），与 PL.build_static_map 等价门；
 *   - registration 三档 {none,tls,icp}（ICP 仅为固定实验条件，非真值）。
 *
 * 禁用（本工单 §12）：B XY/Z、C AABB、D fusion、E 组装；connectivity/UI/Tracker/cleanup/leveling 一行不改；
 *   radius/occ/tier/reference builder/阈值一律不动。本脚本只读文件、只写指定 evidence 目录。
 *
 * 用法：
 *   node 10_r35_attribution.js                                   # 全量（165 帧）→ 02/03/04 + 11_tool_run.log
 *   node 10_r35_attribution.js --frames=10,30,55 --outdir=<dir>  # 调试子集
 *   node 10_r35_attribution.js --digest-only                     # 确定性复跑（只打印 digest，不写文件）
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
    for (const a of ARGV) if (a.startsWith("--" + name + "=")) return a.slice(name.length + 3);
    return ARGV.includes("--" + name) ? true : dflt;
}
const OUTDIR = arg("outdir", HERE);
const DIGEST_ONLY = arg("digest-only", false);
const FRAME_SUBSET = arg("frames", null) ? String(arg("frames", "")).split(",").map(v => parseInt(v, 10)) : null;

const CUR_SID = "cap_20261002_223757";
const REF_SID = "cap_20261004_203349";
const OCC_MIN = PL.PIPE.bg_ref_occ_min;                  // 0.5（v1 候选，未标定；不改）
const MATCH_R = PL.PIPE.bg_match_radius;                 // 0.12（production）
const VX = PL.PIPE.bg_voxel_xy, VZ = PL.PIPE.bg_voxel_z; // 0.15 / 0.12
const R2 = MATCH_R * MATCH_R;
const ICP_SAVED = { roll: 1.7476, pitch: -0.2818, yaw: -2.3924, t: [0.0182, 0.031, 0.0012] }; // R3.2/11_r33 复现基准

const FOCAL_FRAMES = [2, 10, 30, 42, 55, 63, 65, 80, 85, 90, 92, 95, 99, 123, 146, 150, 155, 160];
const PROBLEM_FRAMES = [10, 30, 55, 150, 155, 160];
const CLEAN_FRAMES = [63, 65, 80, 85, 90, 92, 95, 99, 123, 146];
const NEAR_FURNITURE_FRAMES = [55, 150, 155, 160];
const PROXY_FRAMES = [10, 30, 55, 150, 155, 160];        // f55 族 + f10/f30 sanity
/* 「裸站点」旁观帧：受试者已离开站点（f59–142 站点块稳定=250），站点只剩固定结构； */
const CORROB_FRAMES = [63, 80, 92, 123];
const FURNITURE_XY = { x: 1.45, y: 0.85 };
const WD01_XY = { x: 3.50, y: -0.76 };
const WD02_REPS = [{ x: 10.75, y: 4.25 }, { x: 10.25, y: -1.75 }, { x: 10.50, y: 5.50 }];

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
function sha256_buf(b) { return crypto.createHash("sha256").update(b).digest("hex"); }
function sha256_file(p) { return sha256_buf(fs.readFileSync(p)); }
function sha256_file_canon(p) {
    const b = fs.readFileSync(p);
    return sha256_buf(Buffer.from(b.toString("latin1").replace(/\r\n/g, "\n").replace(/\r/g, "\n"), "latin1"));
}

/* ---- 3×3 矩阵 / Jacobi / 小角解（与 11_r33_ab.js 同款逐行复用） ---- */
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

/* ---- 会话加载（console 同口径：TLS → denoise） ---- */
function resolve_transform(sid) {
    const LV = path.join(REPO, "captures", "leveled");
    if (!fs.existsSync(LV)) return null;
    let best = null;
    for (const job of fs.readdirSync(LV)) {
        const jd = path.join(LV, job);
        const tfPath = path.join(jd, "tls", "transform.json");
        const rpPath = path.join(jd, "report.json");
        if (!fs.existsSync(tfPath) || !fs.existsSync(rpPath)) continue;
        let report, tr;
        try { report = JSON.parse(fs.readFileSync(rpPath, "utf8")); tr = JSON.parse(fs.readFileSync(tfPath, "utf8")); }
        catch (e) { continue; }
        if (report.sid !== sid || report.recommended !== "tls") continue;
        if (!tr || !tr.R || !tr.t) continue;
        const mt = fs.statSync(jd).mtimeMs;
        if (!best || mt > best.mtime) best = { mtime: mt, R: tr.R, t: tr.t, job: job, transform_id: tr.transform_id, tf_path: tfPath };
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

/* ---------------------------------------------------------------------------
 * stats-preserving 在线 map 复刻（与 PL.build_static_map 同序同算式；只加保留字段）
 * ------------------------------------------------------------------------- */
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

/* ---------------------------------------------------------------------------
 * shadow 求值器（§四.2 / §三）
 * ------------------------------------------------------------------------- */
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

/* ---------------------------------------------------------------------------
 * micro-cases（G0：恰在门限 / 跨格边界 / ±1 边界 / z 裁剪边界）
 * ------------------------------------------------------------------------- */
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
    /* C1 手工 map：单体素，各轴 ±(r∓ε)、对角、±2 格 */
    {
        const ix = 100, iy = 100, iz = 10;
        const key = bg_key_ijk(ix, iy, iz);
        const cx = ix * VX + VX / 2, cy = iy * VX + VX / 2, cz = iz * VZ + VZ / 2;
        const map = new Map([[key, { x: cx, y: cy, z: cz, hits: 9, tier: "strong" }]]);
        const e = 1e-6, diagIn = (MATCH_R / Math.sqrt(3)) * (1 - 1e-9), diagOut = (MATCH_R / Math.sqrt(3)) * (1 + 1e-9);
        const pts = [
            [cx + MATCH_R - e, cy, cz], [cx - MATCH_R + e, cy, cz],      /* 0,1 inside */
            [cx + MATCH_R + e, cy, cz], [cx - MATCH_R - e, cy, cz],      /* 2,3 outside */
            [cx, cy + MATCH_R - e, cz], [cx, cy - MATCH_R + e, cz],      /* 4,5 inside */
            [cx, cy, cz + MATCH_R - e], [cx, cy, cz - MATCH_R + e],      /* 6,7 inside (z axis) */
            [cx, cy, cz + MATCH_R + e], [cx, cy, cz - MATCH_R - e],      /* 8,9 outside */
            [cx + diagIn, cy + diagIn, cz + diagIn],                     /* 10 inside */
            [cx + diagOut, cy + diagOut, cz + diagOut],                  /* 11 outside */
            [50, 50, 1.26],                                              /* 12 ±2 格以外 */
        ];
        const outcomes = [1, 1, 2, 2, 1, 1, 1, 1, 2, 2, 1, 2, 2];
        ok = runCase("C1_handcrafted_single_voxel_radius_and_cells", pts, map, outcomes) && ok;
    }
    /* C2 手工 map：z 裁剪边界（空 map） */
    {
        const map = new Map();
        const pts = [[50, 50, 0.10], [50, 50, 0.10 - 1e-9], [50, 50, 2.50], [50, 50, 2.50 + 1e-9], [50, 50, 1.00]];
        const outcomes = [2, 0, 2, 0, 2];
        ok = runCase("C2_workspace_z_boundary", pts, map, outcomes) && ok;
    }
    /* C3 真实在线 map：孤立 strong 体素 + 三轴 ±(r∓ε) */
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

/* ---------------------------------------------------------------------------
 * 主流程
 * ------------------------------------------------------------------------- */
const T0 = Date.now();
log("[r35] W03-R3.5 residual attribution tool");
log("[r35] repo=" + REPO);
log("[r35] node=" + process.version + "  mode=" + (DIGEST_ONLY ? "digest-only" : FRAME_SUBSET ? "subset:" + FRAME_SUBSET.join(",") : "full"));
log("[r35] production source (human_pipe_lib.js) canonical=" + sha256_file_canon(path.join(RP, "human_pipe_lib.js")));

function inputSHAs() {
    const s = {};
    for (const f of ["human_pipe_lib.js", "human_replay_lib.js", "human_pipe_lib.test.js"]) {
        const p = path.join(RP, f);
        s[f] = { raw: sha256_file(p), canonical: sha256_file_canon(p) };
    }
    s[REF_SID + ":meta"] = sha256_file(path.join(REPO, "captures", "remote", REF_SID, "meta.json"));
    s[REF_SID + ":points"] = sha256_file(path.join(REPO, "captures", "remote", REF_SID, "points.bin"));
    s[CUR_SID + ":meta"] = sha256_file(path.join(REPO, "captures", "remote", CUR_SID, "meta.json"));
    s[CUR_SID + ":points"] = sha256_file(path.join(REPO, "captures", "remote", CUR_SID, "points.bin"));
    return s;
}
const SHA_BEFORE = inputSHAs();

log("[r35] loading reference " + REF_SID + " ...");
const REF = load_leveled_denoised(REF_SID);
log("[r35] loading current  " + CUR_SID + " ...");
const CUR = load_leveled_denoised(CUR_SID);
if (!CUR.tf || !REF.tf) { console.error("[r35] FATAL: missing tls transform"); process.exit(2); }
const N_CUR = CUR.frames.length, N_REF = REF.frames.length;

log("[r35] building maps ...");
const onlineMap = PL.build_static_map(CUR.frames, { drop_ground: true });
const onlineStats = build_static_map_stats(CUR.frames, { drop_ground: true });
const refMapObj = PL.build_reference_map(REF.frames);
const refMap2Obj = PL.build_reference_map(REF.frames, { hit_min_pts: 2 });
const refSessionOnline = PL.build_static_map(REF.frames, { drop_ground: true });
const curMap1Obj = PL.build_reference_map(CUR.frames);

/* G0: stats 复刻等价门 */
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
log("[r35] G0 online-map replica equivalence: " + (eqChk.pass ? "PASS" : "FAIL " + eqChk.first_bad) + "  (size=" + eqChk.size_prod + ")");
let strong = 0, supported = 0;
onlineMap.forEach(rec => { if (rec.tier === "strong") strong++; else supported++; });
let refTotal = 0, refOcc05 = 0, refSparseNotOnline = 0, refNever2 = 0;
refMapObj.voxels.forEach((rec, key) => {
    refTotal++;
    if (rec.occ >= OCC_MIN) { refOcc05++;
        if (!onlineStats.tiers.has(key)) {
            if (rec.pts_per_frame < 2) refSparseNotOnline++;
            if (!refMap2Obj.voxels.has(key)) refNever2++;
        }
    }
});
let refSessStrong = 0;
refSessionOnline.forEach(rec => { if (rec.tier === "strong") refSessStrong++; });
log("[r35] online current: " + onlineMap.size + " (strong " + strong + " / supported " + supported + ")");
log("[r35] online REF-session (预期 2063): " + refSessionOnline.size + " (strong " + refSessStrong + " / supported " + (refSessionOnline.size - refSessStrong) + ")");
log("[r35] reference map (预期 5286 / occ>=0.5→3707): " + refTotal + " / " + refOcc05 + "  (稀疏未在线 " + refSparseNotOnline + " / 从未≥2 " + refNever2 + ")");

/* ICP 复跑（R3.2/11_r33 同款；CHECK） */
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
    function eulerFromR(R) {
        const pitch = Math.asin(Math.max(-1, Math.min(1, -R[6])));
        const roll = Math.atan2(R[7], R[8]);
        const yaw = Math.atan2(R[3], R[0]);
        return { roll: roll * 180 / Math.PI, pitch: pitch * 180 / Math.PI, yaw: yaw * 180 / Math.PI };
    }
    const eu = eulerFromR(R_icp);
    const pass = Math.abs(eu.roll - ICP_SAVED.roll) <= 0.02 && Math.abs(eu.pitch - ICP_SAVED.pitch) <= 0.02
        && Math.abs(eu.yaw - ICP_SAVED.yaw) <= 0.02 && Math.abs(t_icp[0] - ICP_SAVED.t[0]) <= 0.002
        && Math.abs(t_icp[1] - ICP_SAVED.t[1]) <= 0.002 && Math.abs(t_icp[2] - ICP_SAVED.t[2]) <= 0.002;
    log("[r35] ICP rerun iters=" + iters + " roll=" + round(eu.roll, 4) + " pitch=" + round(eu.pitch, 4) + " yaw=" + round(eu.yaw, 4)
        + " t=[" + t_icp.map(v => round(v, 4)).join(",") + "] vs saved " + JSON.stringify(ICP_SAVED) + " → " + (pass ? "CHECK PASS" : "CHECK FAIL"));
    return { R: R_icp, t: t_icp, eu: eu, iters: iters, pass: pass };
})();

/* registration 三档 */
const R_ref = REF.tf.R.flat ? REF.tf.R.flat() : REF.tf.R;
const R_cur = CUR.tf.R.flat ? CUR.tf.R.flat() : CUR.tf.R;
const R_direct = m3.mul(R_cur, m3.t(R_ref));
const R_direct_t = m3.t(R_direct);
const R_icp_t = m3.t(icp.R);
function alignPoint(mode, x, y, z) {
    if (mode === "none") return [x, y, z];
    if (mode === "tls") return m3.apply(R_direct_t, x, y, z);
    return m3.apply(R_icp_t, x - icp.t[0], y - icp.t[1], z - icp.t[2]);
}
const REF_MODES = ["none", "tls", "icp"];

/* corroboration index（f55 族 proxy） */
log("[r35] building corroboration index from frames " + CORROB_FRAMES.join(",") + " ...");
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

/* 汇总器 */
function newAgg() {
    return { n: 0, reasons: {}, buckets: {}, matched: { none: 0, tls: 0, icp: 0 }, online_matched: 0,
             trans: {}, d_icp: [], d_icp_unmatched: [], d_icp_matched: [], d_none: [],
             adx: [], ady: [], adz: [], dxy: [], shell: { IN: 0, SHELL: 0, OVER: 0, ABSENT: 0 },
             zband: {}, proxy: {}, corrob: {} };
}
function aggAdd(a, rec) {
    a.n++;
    a.reasons[rec.reason_primary] = (a.reasons[rec.reason_primary] || 0) + 1;
    a.buckets[rec.bucket] = (a.buckets[rec.bucket] || 0) + 1;
    if (rec.matched_ref_none) a.matched.none++;
    if (rec.matched_ref_tls) a.matched.tls++;
    if (rec.matched_ref_icp) a.matched.icp++;
    if (rec.matched_online) a.online_matched++;
    const tk = (rec.matched_ref_none ? "1" : "0") + (rec.matched_ref_tls ? "1" : "0") + (rec.matched_ref_icp ? "1" : "0");
    a.trans[tk] = (a.trans[tk] || 0) + 1;
    if (rec.nearest_ref_d !== null) { a.d_icp.push(rec.nearest_ref_d); (rec.matched_ref_icp ? a.d_icp_matched : a.d_icp_unmatched).push(rec.nearest_ref_d); }
    if (rec.nearest_ref_d_none !== null) a.d_none.push(rec.nearest_ref_d_none);
    if (rec.shell_band) a.shell[rec.shell_band]++;
    if (!rec.matched_ref_icp && rec.nearest_ref_d !== null) {
        a.adx.push(Math.abs(rec.nearest_ref_dx)); a.ady.push(Math.abs(rec.nearest_ref_dy)); a.adz.push(Math.abs(rec.nearest_ref_dz));
        a.dxy.push(Math.hypot(rec.nearest_ref_dx, rec.nearest_ref_dy));
    }
    a.zband[rec.z_band] = (a.zband[rec.z_band] || 0) + 1;
    if (rec.proxy_class) a.proxy[rec.proxy_class] = (a.proxy[rec.proxy_class] || 0) + 1;
    if (rec.corrob_n !== null) a.corrob[rec.corrob_n] = (a.corrob[rec.corrob_n] || 0) + 1;
}
function aggFinalize(a) {
    const share = {};
    for (const k in a.reasons) share[k] = round(a.reasons[k] / a.n);
    const bshare = {};
    for (const k in a.buckets) bshare[k] = round(a.buckets[k] / a.n);
    const shellShare = {};
    const totShell = a.shell.IN + a.shell.SHELL + a.shell.OVER + a.shell.ABSENT;
    for (const k in a.shell) shellShare[k] = round(a.shell[k] / (totShell || 1));
    const transShare = {};
    for (const k in a.trans) transShare[k] = round(a.trans[k] / a.n);
    return {
        residual_points: a.n,
        reason_counts: Object.assign({}, a.reasons),
        reason_share: share,
        bucket_counts: Object.assign({}, a.buckets),
        bucket_share: bshare,
        matched_ref: { none: a.matched.none, tls: a.matched.tls, icp: a.matched.icp,
                       rate_none: round(a.matched.none / (a.n || 1)), rate_tls: round(a.matched.tls / (a.n || 1)), rate_icp: round(a.matched.icp / (a.n || 1)) },
        matched_online_selfcheck: a.online_matched,
        transition_counts: Object.assign({}, a.trans),
        transition_share: transShare,
        d_icp_all: quantiles(a.d_icp),
        d_icp_unmatched: quantiles(a.d_icp_unmatched),
        d_icp_matched: quantiles(a.d_icp_matched),
        d_none_all: quantiles(a.d_none),
        absdx_unmatched: quantiles(a.adx),
        absdy_unmatched: quantiles(a.ady),
        absdz_unmatched: quantiles(a.adz),
        dxy_unmatched: quantiles(a.dxy),
        shell_counts: Object.assign({}, a.shell),
        shell_share: shellShare,
        zband: Object.assign({}, a.zband),
        proxy_class: Object.assign({}, a.proxy),
        corrob_n: Object.assign({}, a.corrob),
    };
}

/* ---- 主循环 ---- */
const frameRows = [];
const groups = { ALL: newAgg(), WD01: newAgg(), WD02: newAgg(), PROBLEM: newAgg(), CLEAN: newAgg(), NEAR_FURN: newAgg() };
const groupVoxel = { ALL: new Map(), WD01: new Map(), WD02: new Map(), PROBLEM: new Map(), CLEAN: new Map(), NEAR_FURN: new Map() };
const GROUP_PRED = {
    ALL: (fi, r) => true,
    WD01: (fi, r) => r.in_wd01,
    WD02: (fi, r) => r.in_wd02,
    PROBLEM: (fi, r) => PROBLEM_FRAMES.includes(fi),
    CLEAN: (fi, r) => CLEAN_FRAMES.includes(fi),
    NEAR_FURN: (fi, r) => NEAR_FURNITURE_FRAMES.includes(fi) && r.in_furn,
};
const csvPointLines = [];
const csvVoxelLines = [];
const csvPointHeader = ["session_id", "frame_index", "frame_seq", "point_id", "x", "y", "z", "production_result", "z_band",
    "reason_primary", "reason_secondary", "reason_online_view", "reason_ref_icp", "reason_ref_none", "reason_ref_tls",
    "matched_online", "matched_ref_none", "matched_ref_tls", "matched_ref_icp", "registration_recovered", "registration_sensitive",
    "nearest_reference_distance", "nearest_reference_d_xy", "nearest_reference_dx", "nearest_reference_dy", "nearest_reference_dz",
    "nearest_reference_voxel", "nearest_reference_occ", "nearest_reference_obs", "nearest_reference_jit", "nearest_reference_pts_per_frame", "nearest_reference_tier",
    "nearest_reference_distance_none", "shell_band", "reference_missing", "matcher_geometry_sensitive", "box_d_min_icp",
    "d_online", "online_stats_any", "online_max_hits", "online_max_occ2", "online_occ1_max",
    "ref_any_cells_27", "ref_max_occ_any", "ref2_max_occ", "bucket",
    "in_wd01_region", "in_wd02_proxy", "in_furniture_window", "corrob_n", "proxy_class"];
csvPointLines.push(csvPointHeader.join(","));
const csvVoxelHeader = ["session_id", "frame_index", "voxel_ix_iy_iz", "point_count", "dominant_reason", "reason_hist",
    "z_min", "z_max", "x_range", "y_range", "matched_ref_icp_count"];
csvVoxelLines.push(csvVoxelHeader.join(","));

const baseline = { frames_compared: 0, count_mismatch_frames: 0, point_mismatch_points: 0, conservation_fail_frames: 0, self_check_violations: 0 };
const micro = microCases(onlineMap);
/* f10 站点块（0.8–1.3m，非静态 corrob=0）坐标：用于 reference 污染度量 */
const stationBlockF10 = [];
const OK_LABELS = ["MATCHED_REF_ICP", "XY_MATCH_Z_FAIL", "Z_MATCH_XY_FAIL", "DISTANCE_OVER_GATE", "REFERENCE_HOLE", "TIER_REJECT", "NO_REFERENCE_NEIGHBOR", "UNKNOWN"];
const OK_BUCKETS = ["REFERENCE_ABSORB", "REGISTRATION", "REFERENCE_MISSING", "MATCHER_GEOMETRY", "SPARSE_GATE", "OTHER"];
function dominantOf(reasons) {
    let best = null, bn = -1;
    for (const r of OK_LABELS) { const c = reasons[r] || 0; if (c > bn) { bn = c; best = r; } }
    return bn > 0 ? best : null;
}
function dominantBucketOf(buckets) {
    let best = null, bn = -1;
    for (const b of OK_BUCKETS) { const c = buckets[b] || 0; if (c > bn) { bn = c; best = b; } }
    return bn > 0 ? best : null;
}

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
    const agg = newAgg();
    const frameRow = {
        frame_index: fi, frame_seq: CUR.frame_slices[fi].seq,
        n_raw: CUR.frame_slices[fi].count, n_denoise: clean.length / 4,
        n_range_reject: CUR.frame_slices[fi].count - clean.length / 4,
        n_z_reject: sh.nZ, n_bg_match: sh.nBG, n_residual: sh.nRes,
        production_n_fg: prod.n_fg, production_n_dropped: prod.n_dropped,
        conservation_ok: sh.nZ + sh.nBG + sh.nRes === sh.nIn && sh.nRes === prod.n_fg && sh.nZ + sh.nBG === prod.n_dropped,
        point_identity_ok: sh.fg.length === prod.fg_xyzi.length,
        mean_d_icp_matched: null,
        voxel_dominant: null,
    };
    const voxMap = new Map();
    const pointRecs = [];
    let dMatchedSum = 0, dMatchedN = 0;

    for (let j = 0; j < sh.resIdx.length; j++) {
        const pi = sh.resIdx[j];
        const k4 = pi * 4;
        const x = clean[k4], y = clean[k4 + 1], z = clean[k4 + 2];
        /* online 视角（生产语义自检：residual 不应命中） */
        const oT = scanTierCells(onlineMap, x, y, z, 0, false);
        const matchedOnline = oT.d !== null && oT.d < MATCH_R;
        const oStats = scanAnyCells(onlineStats.stats, x, y, z, "hits");
        const o1 = scanAnyCells(curMap1Obj.voxels, x, y, z, "occ");
        /* registration 三档 ref 视角 */
        const scans = {};
        for (const mode of REF_MODES) {
            const q = alignPoint(mode, x, y, z);
            scans[mode] = { tier: scanTierCells(refMapObj.voxels, q[0], q[1], q[2], OCC_MIN, mode === "icp"),
                            any: scanAnyCells(refMapObj.voxels, q[0], q[1], q[2], "occ"),
                            any2: mode === "icp" ? scanAnyCells(refMap2Obj.voxels, q[0], q[1], q[2], "occ") : null };
        }
        const mNone = scans.none.tier.d !== null && scans.none.tier.d < MATCH_R;
        const mTls = scans.tls.tier.d !== null && scans.tls.tier.d < MATCH_R;
        const mIcp = scans.icp.tier.d !== null && scans.icp.tier.d < MATCH_R;
        let onlineLabel;
        if (matchedOnline) onlineLabel = "MATCHED";
        else if (oT.d !== null) onlineLabel = axisLabel(oT.dx, oT.dy, oT.dz);
        else if (oStats.any) onlineLabel = "TIER_REJECT";
        else onlineLabel = "NO_REFERENCE_NEIGHBOR";
        function refLabelOf(s) {
            if (s.tier.d !== null && s.tier.d < MATCH_R) return "MATCHED";
            if (s.tier.d !== null) return axisLabel(s.tier.dx, s.tier.dy, s.tier.dz);
            if (s.any.any) return "REFERENCE_HOLE";
            return "NO_REFERENCE_NEIGHBOR";
        }
        const refL = { none: refLabelOf(scans.none), tls: refLabelOf(scans.tls), icp: refLabelOf(scans.icp) };
        /* 主因（fused @ icp；02 §3 判定顺序） */
        let primary;
        if (mIcp) primary = "MATCHED_REF_ICP";
        else if (scans.icp.tier.d !== null) primary = axisLabel(scans.icp.tier.dx, scans.icp.tier.dy, scans.icp.tier.dz);
        else if (scans.icp.any.any) primary = "REFERENCE_HOLE";
        else if (oStats.any) primary = "TIER_REJECT";
        else primary = "NO_REFERENCE_NEIGHBOR";
        let bucket;
        if (primary === "MATCHED_REF_ICP") bucket = mNone ? "REFERENCE_ABSORB" : "REGISTRATION";
        else if (primary === "XY_MATCH_Z_FAIL" || primary === "Z_MATCH_XY_FAIL" || primary === "DISTANCE_OVER_GATE") bucket = "MATCHER_GEOMETRY";
        else if (primary === "REFERENCE_HOLE" || primary === "NO_REFERENCE_NEIGHBOR") bucket = "REFERENCE_MISSING";
        else if (primary === "TIER_REJECT") bucket = (o1.max !== null && o1.max >= PL.PIPE.bg_occ_supported) ? "SPARSE_GATE" : "REFERENCE_MISSING";
        else bucket = "OTHER";
        const secondary = [];
        if (onlineLabel !== primary && onlineLabel !== "MATCHED") secondary.push("online=" + onlineLabel);
        for (const mode of REF_MODES) if (refL[mode] !== primary && refL[mode] !== "MATCHED") secondary.push("ref_" + mode + "=" + refL[mode]);
        const t = scans.icp.tier;
        const nearestRefD = t.d;
        const nearestRefDxy = t.d !== null ? Math.hypot(t.dx, t.dy) : null;
        const refVoxelStr = t.rec ? (function () { const ij = bg_decode(t.key); return ij[0] + ";" + ij[1] + ";" + ij[2]; })() : null;
        const refTierClass = t.rec ? (t.rec.occ >= 0.85 ? "strong" : t.rec.occ >= 0.65 ? "supported" : "below") : null;
        const shellBand = t.d === null ? "ABSENT" : t.d < MATCH_R ? "IN" : t.d < 2 * MATCH_R ? "SHELL" : "OVER";
        const corrobN = doProxy ? CORROB.corrobCount(fi, x, y, z) : null;
        const proxyClass = corrobN === null ? null : (corrobN >= 2 ? "STATIC_STATION" : corrobN === 0 ? "NON_STATIC" : "AMBIGUOUS");
        const inWd01 = Math.hypot(x - WD01_XY.x, y - WD01_XY.y) <= 0.9;
        const inWd02 = Math.hypot(x, y) > 8 || WD02_REPS.some(r => Math.hypot(x - r.x, y - r.y) <= 1.5);
        const inFurn = Math.hypot(x - FURNITURE_XY.x, y - FURNITURE_XY.y) <= 0.6;
        const rec = {
            x: x, y: y, z: z, z_band: zBandOf(z),
            reason_primary: primary, reason_secondary: secondary.join("|"),
            reason_online_view: onlineLabel, reason_ref_icp: refL.icp, reason_ref_none: refL.none, reason_ref_tls: refL.tls,
            matched_online: matchedOnline, matched_ref_none: mNone, matched_ref_tls: mTls, matched_ref_icp: mIcp,
            registration_recovered: mIcp && !mNone, registration_sensitive: mIcp !== mNone,
            nearest_ref_d: nearestRefD, nearest_ref_d_none: scans.none.tier.d,
            nearest_ref_dx: t.dx, nearest_ref_dy: t.dy, nearest_ref_dz: t.dz,
            nearest_ref_voxel: refVoxelStr, nearest_ref_occ: t.rec ? round(t.rec.occ, 6) : null,
            nearest_ref_obs: t.rec ? t.rec.obs : null, nearest_ref_jit: t.rec ? round(t.rec.jit, 6) : null,
            nearest_ref_ppf: t.rec ? round(t.rec.pts_per_frame, 6) : null, nearest_ref_tier: refTierClass,
            shell_band: shellBand, reference_missing: t.d === null, matcher_geometry_sensitive: t.d !== null && t.d >= MATCH_R,
            box_d_icp: scans.icp.tier.boxd === undefined ? null : scans.icp.tier.boxd,
            d_online: oT.d, online_stats_any: oStats.any, online_max_hits: oStats.max,
            online_max_occ2: oStats.max !== null ? round(oStats.max / N_CUR, 6) : null,
            online_occ1_max: o1.max,
            ref_any_cells: scans.icp.any.cells, ref_max_occ_any: scans.icp.any.max,
            ref2_max_occ: scans.icp.any2 ? scans.icp.any2.max : null,
            bucket: bucket,
            in_wd01: inWd01, in_wd02: inWd02, in_furn: inFurn,
            corrob_n: corrobN, proxy_class: proxyClass,
        };
        if (matchedOnline) baseline.self_check_violations++;
        if (fi === 10 && inFurn && corrobN === 0 && z >= 0.8 && z < 1.3) stationBlockF10.push([x, y, z]);
        aggAdd(agg, rec);
        pointRecs.push({ rec: rec, pi: pi });
        if (mIcp && nearestRefD !== null) { dMatchedSum += nearestRefD; dMatchedN++; }
        if (isFocal) {
            csvPointLines.push([CUR_SID, fi, frameRow.frame_seq, j,
                round(x, 4), round(y, 4), round(z, 4), "RESIDUAL", rec.z_band,
                rec.reason_primary, rec.reason_secondary, rec.reason_online_view, rec.reason_ref_icp, rec.reason_ref_none, rec.reason_ref_tls,
                rec.matched_online ? 1 : 0, rec.matched_ref_none ? 1 : 0, rec.matched_ref_tls ? 1 : 0, rec.matched_ref_icp ? 1 : 0,
                rec.registration_recovered ? 1 : 0, rec.registration_sensitive ? 1 : 0,
                round(rec.nearest_ref_d), round(nearestRefDxy), round(rec.nearest_ref_dx), round(rec.nearest_ref_dy), round(rec.nearest_ref_dz),
                rec.nearest_ref_voxel, rec.nearest_ref_occ, rec.nearest_ref_obs, rec.nearest_ref_jit, rec.nearest_ref_ppf, rec.nearest_ref_tier,
                round(rec.nearest_ref_d_none), rec.shell_band, rec.reference_missing ? 1 : 0, rec.matcher_geometry_sensitive ? 1 : 0, round(rec.box_d_icp),
                round(rec.d_online), rec.online_stats_any ? 1 : 0, rec.online_max_hits, rec.online_max_occ2, rec.online_occ1_max,
                rec.ref_any_cells, rec.ref_max_occ_any, rec.ref2_max_occ,
                rec.bucket, rec.in_wd01 ? 1 : 0, rec.in_wd02 ? 1 : 0, rec.in_furn ? 1 : 0,
                rec.corrob_n === null ? "" : rec.corrob_n, rec.proxy_class === null ? "" : rec.proxy_class].join(","));
        }
        aggAdd(groups.ALL, rec);
        if (PROBLEM_FRAMES.includes(fi)) aggAdd(groups.PROBLEM, rec);
        if (CLEAN_FRAMES.includes(fi)) aggAdd(groups.CLEAN, rec);
        if (NEAR_FURNITURE_FRAMES.includes(fi) && inFurn) aggAdd(groups.NEAR_FURN, rec);
        if (inWd01) aggAdd(groups.WD01, rec);
        if (inWd02) aggAdd(groups.WD02, rec);
        /* voxel 聚合（本帧，全点） */
        const vk = bg_key_ijk(Math.floor(x / VX), Math.floor(y / VX), Math.floor(z / VZ));
        let v = voxMap.get(vk);
        if (!v) { v = { n: 0, reasons: {}, buckets: {}, zmin: z, zmax: z, xmin: x, xmax: x, ymin: y, ymax: y, mIcp: 0 }; voxMap.set(vk, v); }
        v.n++; v.reasons[rec.reason_primary] = (v.reasons[rec.reason_primary] || 0) + 1;
        v.buckets[rec.bucket] = (v.buckets[rec.bucket] || 0) + 1;
        if (z < v.zmin) v.zmin = z; if (z > v.zmax) v.zmax = z;
        if (x < v.xmin) v.xmin = x; if (x > v.xmax) v.xmax = x;
        if (y < v.ymin) v.ymin = y; if (y > v.ymax) v.ymax = y;
        if (rec.matched_ref_icp) v.mIcp++;
    }

    /* 本帧 voxel 输出 + 帧级 dominant 直方图 */
    const frameVoxHist = {}, frameVoxBucketHist = {};
    voxMap.forEach((v, vk) => {
        const dom = dominantOf(v.reasons);
        const domB = dominantBucketOf(v.buckets);
        frameVoxHist[dom] = (frameVoxHist[dom] || 0) + 1;
        frameVoxBucketHist[domB] = (frameVoxBucketHist[domB] || 0) + 1;
        const ij = bg_decode(vk);
        csvVoxelLines.push([CUR_SID, fi, ij[0] + ";" + ij[1] + ";" + ij[2], v.n, dom,
            Object.keys(v.reasons).map(k => k + ":" + v.reasons[k]).join("|"),
            round(v.zmin), round(v.zmax), round(v.xmax - v.xmin), round(v.ymax - v.ymin), v.mIcp].join(","));
    });
    /* 分组 voxel：只用组内点（pointRecs 二遍）；同时累计 label 与 bucket dominant */
    for (const g of Object.keys(GROUP_PRED)) {
        const pred = GROUP_PRED[g];
        const seen = new Map();
        for (const pr of pointRecs) {
            if (!pred(fi, pr.rec)) continue;
            const vk = bg_key_ijk(Math.floor(pr.rec.x / VX), Math.floor(pr.rec.y / VX), Math.floor(pr.rec.z / VZ));
            let m = seen.get(vk); if (!m) { m = { labels: {}, buckets: {} }; seen.set(vk, m); }
            m.labels[pr.rec.reason_primary] = (m.labels[pr.rec.reason_primary] || 0) + 1;
            m.buckets[pr.rec.bucket] = (m.buckets[pr.rec.bucket] || 0) + 1;
        }
        seen.forEach((m, vk) => groupVoxel[g].set(fi + "|" + vk, { label: dominantOf(m.labels), bucket: dominantBucketOf(m.buckets) }));
    }

    frameRow.voxel_dominant = frameVoxHist;
    frameRow.voxel_bucket = frameVoxBucketHist;
    frameRow.mean_d_icp_matched = dMatchedN ? round(dMatchedSum / dMatchedN) : null;
    frameRows.push({ fi: fi, row: frameRow, agg: agg });
    if (fi % 20 === 0 || isFocal) log("[r35] frame " + fi + " done (residual " + sh.nRes + ", " + (Date.now() - T0) + "ms)");
}

/* 帧级 finalize */
const framesOut = [];
for (const fr of frameRows) {
    const o = Object.assign({}, fr.row);
    o.attribution_icp = aggFinalize(fr.agg);
    framesOut.push(o);
}

/* 分组 finalize */
const groupsOut = {};
for (const g of Object.keys(groups)) {
    const f = aggFinalize(groups[g]);
    const rows = {}, rowsB = {};
    groupVoxel[g].forEach(v => {
        rows[v.label] = (rows[v.label] || 0) + 1;
        rowsB[v.bucket] = (rowsB[v.bucket] || 0) + 1;
    });
    const t = Object.values(rows).reduce((a, b) => a + b, 0);
    const share = {}, shareB = {};
    for (const k in rows) share[k] = round(rows[k] / (t || 1));
    for (const k in rowsB) shareB[k] = round(rowsB[k] / (t || 1));
    f.voxel_dominant_counts = rows;
    f.voxel_dominant_share = share;
    f.voxel_bucket_counts = rowsB;
    f.voxel_bucket_share = shareB;
    f.voxels = t;
    groupsOut[g] = f;
}

const conservation = {
    frames: framesOut.length,
    all_conservation_ok: framesOut.every(r => r.conservation_ok),
    totals: {
        n_raw: framesOut.reduce((a, r) => a + r.n_raw, 0),
        n_denoise: framesOut.reduce((a, r) => a + r.n_denoise, 0),
        n_range_reject: framesOut.reduce((a, r) => a + r.n_range_reject, 0),
        n_z_reject: framesOut.reduce((a, r) => a + r.n_z_reject, 0),
        n_bg_match: framesOut.reduce((a, r) => a + r.n_bg_match, 0),
        n_residual: framesOut.reduce((a, r) => a + r.n_residual, 0),
    },
};
conservation.totals_ok = conservation.totals.n_raw === conservation.totals.n_denoise + conservation.totals.n_range_reject
    && conservation.totals.n_denoise === conservation.totals.n_z_reject + conservation.totals.n_bg_match + conservation.totals.n_residual;
const partitionOk = framesOut.every(r => Object.values(r.attribution_icp.reason_counts).reduce((a, b) => a + b, 0) === r.n_residual);

/* ---- f10 站点块（非静态）在 reference 中的对应格：reference 污染度量 ---- */
const stationContamination = (function () {
    let winCells = 0, blockCells = 0, occSum = 0;
    refMapObj.voxels.forEach(rec => {
        const xy = Math.hypot(rec.x - FURNITURE_XY.x, rec.y - FURNITURE_XY.y);
        if (xy > 0.6) return;
        winCells++;
        if (rec.occ < OCC_MIN) return;
        if (rec.z < 0.8 || rec.z >= 1.3) return;
        blockCells++;
        occSum += rec.occ;
    });
    /* 点侧：f10 非静态块点中，±1 邻域内存在 occ>=0.5 参考体素且形心距 ≤0.05m 的比例 */
    let withRef = 0;
    for (const p of stationBlockF10) {
        const s = scanTierCells(refMapObj.voxels, p[0], p[1], p[2], OCC_MIN, false);
        if (s.d !== null && s.d <= 0.05) withRef++;
    }
    const out = { f10_non_static_block_points: stationBlockF10.length,
                  ref_cells_window_total: winCells,
                  ref_cells_blockband_occ_ge_05: blockCells,
                  f10_non_static_points_with_ref_within_0_05m: withRef,
                  fraction: stationBlockF10.length ? round(withRef / stationBlockF10.length, 4) : null,
                  ref_block_mean_occ: blockCells ? round(occSum / blockCells, 4) : null };
    log("[r35] station contamination: f10 non-static block pts=" + stationBlockF10.length
        + "  with ref cell(occ>=0.5) <=0.05m: " + withRef + " (" + out.fraction + ")"
        + "  ref blockband cells=" + blockCells + " mean occ=" + out.ref_block_mean_occ);
    return out;
})();

/* R3.3 A 层 CHECK（复现 0.7796） */
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
    log("[r35] R3.3 A-layer check (ALL thinned, occ>=0.5, none/center): " + aLevel.none_center + " (expect 0.7796) → " + (aLevel.pass ? "PASS" : "FAIL"));
}

/* probe 复现 CHECK */
const probeChecks = [];
if (!FRAME_SUBSET) {
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
    for (const [fi, cx, cy, half, expectHit, expectN] of [[10, 1.45, 0.85, 0.80, 1365, 1564], [55, 1.45, 0.85, 0.80, 621, 3190], [160, 1.45, 0.85, 0.80, 1024, 2429]]) {
        const pts = clusterNear(fi, cx, cy, half);
        let hit = 0;
        for (const p of pts) { const r = scanTierCells(refMapObj.voxels, p[0], p[1], p[2], OCC_MIN, false); if (r.d !== null && r.d < MATCH_R) hit++; }
        const pass = hit === expectHit && pts.length === expectN;
        probeChecks.push({ frame: fi, n: pts.length, center_hits: hit, expected_hits: expectHit, expected_n: expectN, pass: pass });
        log("[r35] probe check f" + fi + ": n=" + pts.length + " center=" + hit + " (expect n=" + expectN + " center=" + expectHit + ") → " + (pass ? "PASS" : "FAIL"));
    }
}

/* checks 汇总 */
const checks = [];
function addCheck(name, pass, detail) { checks.push({ name: name, pass: pass, detail: detail }); return pass; }
let allPass = true;
allPass = addCheck("G0_baseline_point_identity", baseline.point_mismatch_points === 0 && baseline.count_mismatch_frames === 0,
    { frames: baseline.frames_compared, point_mismatch: baseline.point_mismatch_points, count_mismatch_frames: baseline.count_mismatch_frames }) && allPass;
allPass = addCheck("G0_micro_cases", micro.pass === true, micro) && allPass;
allPass = addCheck("conservation", conservation.all_conservation_ok && conservation.totals_ok, conservation) && allPass;
allPass = addCheck("label_partition_equals_residual", partitionOk, null) && allPass;
allPass = addCheck("self_check_violations_zero", baseline.self_check_violations === 0, { n: baseline.self_check_violations }) && allPass;
allPass = addCheck("online_map_replica_equivalence", eqChk.pass, eqChk) && allPass;
allPass = addCheck("icp_rerun_repro", icp.pass, { euler: icp.eu, t: icp.t, iters: icp.iters }) && allPass;
allPass = addCheck("ref_map_counts_5286_3707", refTotal === 5286 && refOcc05 === 3707, { total: refTotal, occ_ge_05: refOcc05, sparse_not_online: refSparseNotOnline, never_ge2: refNever2 }) && allPass;
allPass = addCheck("ref_session_online_map_2063", refSessionOnline.size === 2063, { size: refSessionOnline.size }) && allPass;
if (aLevel) allPass = addCheck("r33_A_level_07796", aLevel.pass, aLevel) && allPass;
for (const pc of probeChecks) allPass = addCheck("probe_f" + pc.frame + "_n" + pc.expected_n + "_center" + pc.expected_hits, pc.pass, pc) && allPass;
const shaAfter = inputSHAs();
const inputsUnchanged = JSON.stringify(SHA_BEFORE) === JSON.stringify(shaAfter);
allPass = addCheck("inputs_unchanged", inputsUnchanged, null) && allPass;

/* 输出 */
const stats = {
    tool: "W03-R3.5 / Step-0 residual attribution (offline, read-only)",
    mode: DIGEST_ONLY ? "digest-only" : FRAME_SUBSET ? "subset" : "full",
    node: process.version,
    provenance: {
        sha_before: SHA_BEFORE, sha_after: shaAfter, inputs_unchanged: inputsUnchanged,
        transforms: { cur: { sid: CUR_SID, job: CUR.tf.job, transform_id: CUR.tf.transform_id },
                      ref: { sid: REF_SID, job: REF.tf.job, transform_id: REF.tf.transform_id } },
    },
    params: { match_radius: MATCH_R, occ_min: OCC_MIN, voxel_xy: VX, voxel_z: VZ, neighborhood: "3x3x3",
              registration_modes: REF_MODES, z_range: [PL.PIPE.ground_keep_below_m, PL.PIPE.z_max_m],
              focal_frames: FOCAL_FRAMES, problem_frames: PROBLEM_FRAMES, clean_frames: CLEAN_FRAMES,
              near_furniture_frames: NEAR_FURNITURE_FRAMES, corrob_frames: CORROB_FRAMES, proxy_frames: PROXY_FRAMES,
              furniture_xy: FURNITURE_XY, wd01_xy: WD01_XY, wd02_reps: WD02_REPS,
              bucket_rule_note: "REGISTRATION = ref(occ>=0.5)@icp matched 且 @none 未匹配；REFERENCE_ABSORB = @none 也匹配；SPARSE_GATE = TIER_REJECT 且邻域 online occ(>=1) max >= 0.65；REFERENCE_MISSING = 其余 REFERENCE_HOLE/NO_REFERENCE_NEIGHBOR/低可见 TIER_REJECT；MATCHER_GEOMETRY = 有 ref tier 体素但 d>=r",
              proxy_rule_note: "corrob_n = 与裸站点旁观帧 {63,80,92,123} 中 ≥2 帧残差点在 0.10m 内的帧数；>=2 STATIC_STATION / 1 AMBIGUOUS / 0 NON_STATIC",
              voxel_dominant_rule: "voxel 主导 label/bucket = 组内(或帧内)点计数最大者；并列按 OK_LABELS / OK_BUCKETS 固定顺序取先出现者" },
    sessions: { cur: { sid: CUR_SID, frames: N_CUR }, ref: { sid: REF_SID, frames: N_REF } },
    maps: { online_cur: { total: onlineMap.size, strong: strong, supported: supported },
            online_ref_session: { total: refSessionOnline.size, strong: refSessStrong },
            ref: { total: refTotal, occ_ge_05: refOcc05, sparse_not_online: refSparseNotOnline, never_ge2: refNever2 },
            cur_occ1_gate: { total: curMap1Obj.voxels.size } },
    icp: { iters: icp.iters, euler_deg: icp.eu, t: icp.t.map(v => round(v)), saved: ICP_SAVED, pass: icp.pass },
    station_contamination: stationContamination,
    baseline: baseline, conservation: conservation, micro_cases: micro, checks: checks,
    frames: framesOut, groups: groupsOut,
};
/* digest：(不含 mode/generated/elapsed) 的规范化指纹，用于跨 run 确定性复现（Check 4） */
const digestObj = Object.assign({}, stats);
delete digestObj.mode;
const digest = sha256_buf(JSON.stringify(digestObj));
log("[r35] DIGEST=" + digest + " (mode-independent)");
log("[r35] CHECK " + (allPass ? "ALL PASS" : "SOME FAILED"));
if (DIGEST_ONLY) {
    log("[r35] digest-only run complete; elapsed=" + (Date.now() - T0) + "ms");
    process.exitCode = allPass ? 0 : 1;
} else {
    stats.generated = new Date().toISOString();
    stats.elapsed_ms = Date.now() - T0;
    stats.digest = digest;
    fs.writeFileSync(path.join(OUTDIR, "02_attribution_results.json"), JSON.stringify(stats, null, 1) + "\n");
    fs.writeFileSync(path.join(OUTDIR, "03_attribution_points.csv"), csvPointLines.join("\n") + "\n");
    fs.writeFileSync(path.join(OUTDIR, "04_attribution_voxels.csv"), csvVoxelLines.join("\n") + "\n");
    log("[r35] wrote 02/03/04 to " + OUTDIR);
    fs.writeFileSync(path.join(OUTDIR, "11_tool_run.log"), L.join("\n") + "\n");
    process.exitCode = allPass ? 0 : 1;
}

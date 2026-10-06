/* W03-R3.3 Voxel-AABB Matcher Controlled AB — READ-ONLY evidence script（生产零改动）。
 *
 * 唯一问题（用户 2026-10-06 评审）：固定相同 registration 条件下，center-distance → AABB-distance
 *   额外改善多少？
 *
 * 控制变量：reference（R3.1 builder occ≥0.5，WD01 桥接另用 occ≥0.9）、current frames（223757 leveled+denoised）、
 *   3×3×3 邻域、半径 0.12m —— 全固定。只变 matcher 几何：
 *   M0 center : min |p − 占用格形心| < 0.12
 *   M1 aabb   : min d(p, 占用格 AABB) < 0.12（点落在占用格内 → d=0）
 *   M1c contain: d(p, AABB) == 0（诊断对照）
 * registration 条件：none / tls（R_direct=R_cur·R_refᵀ，辅助）/ icp（复跑 R3.2 ICP，先 CHECK 复现）。
 *
 * 测试集：WD01（f2/f42/f150 簇点，R3.0 同款提取）/ WD02（代表区圆盘 + range>8）/ known-static（受试者双盘排除
 *   + corr-enriched）/ ALL（复现 R3.2 A 层 0.7796 自检）/ HP01・HP03（受试者簇 → retention）；HP02 NOT_RUN。
 *
 * 禁用：不接 production、不改 matcher 半径/邻域、不碰 human_pipe_lib.js、不采集/部署/commit。
 *
 * 用法: node 11_r33_ab.js
 */
"use strict";
const fs = require("fs");
const path = require("path");
const crypto = require("crypto");
const HERE = __dirname;
const REPO = path.resolve(HERE, "..", "..", "..", "..");
const RP = path.join(REPO, "pc_apps", "human_replay");
const RL = require(path.join(RP, "human_replay_lib.js"));
const PL = require(path.join(RP, "human_pipe_lib.js"));

const REF_SID = "cap_20261004_203349";
const CUR_SID = "cap_20261002_223757";
const OCC_PRIMARY = 0.5;             /* R3.1 候选入口阈值（生产候选） */
const OCC_BRIDGE = 0.9;              /* R3.2 D/C 层口径（0.854/0.991 对照用） */
const MATCH_R = 0.12;                /* 两 matcher 同一阈值（apples-to-apples） */

/* R3.2 ICP 复现对照（07_r32_stats.json C_icp） */
const ICP_SAVED = { roll: 1.7476, pitch: -0.2818, yaw: -2.3924, t: [0.0182, 0.031, 0.0012] };

/* ---- 背景体素整数键（与生产 key_bg 同源） ---- */
const BG_BASE = 8192, BG_OFF = 4096;
function bg_key_ijk(ix, iy, iz) { return ((ix + BG_OFF) * BG_BASE + (iy + BG_OFF)) * BG_BASE + (iz + BG_OFF); }

/* ---- 3×3 矩阵（行主序） ---- */
const m3 = {
    mul(A, B) {
        const o = new Array(9).fill(0);
        for (let i = 0; i < 3; i++) for (let j = 0; j < 3; j++)
            for (let k = 0; k < 3; k++) o[3 * i + j] += A[3 * i + k] * B[3 * k + j];
        return o;
    },
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

/* ---- Jacobi 对称特征分解（R3.2 同款，探针已 PASS） ---- */
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
            for (let k = 0; k < n; k++) {
                const akp = A[k][p], akq = A[k][q];
                A[k][p] = c * akp - s * akq; A[k][q] = s * akp + c * akq;
            }
            for (let k = 0; k < n; k++) {
                const apk = A[p][k], aqk = A[q][k];
                A[p][k] = c * apk - s * aqk; A[q][k] = s * apk + c * aqk;
            }
            for (let k = 0; k < n; k++) {
                const vkp = V[k][p], vkq = V[k][q];
                V[k][p] = c * vkp - s * vkq; V[k][q] = s * vkp + c * vkq;
            }
        }
    }
    const vals = [], vecs = [];
    for (let i = 0; i < n; i++) { vals.push(A[i][i]); vecs.push(V.map(r => r[i])); }
    return { vals: vals, vecs: vecs };
}

/* ---- R3.2 同款小角度解（Jacobi 伪逆；探针 PASS） ---- */
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

/* ---- 体素空间哈希（ICP 对应搜索） ---- */
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

function pct(sorted, q) {
    if (!sorted.length) return null;
    return sorted[Math.min(sorted.length - 1, Math.ceil(q * sorted.length) - 1)];
}
function round(v, d) { return v === null || v === undefined || !isFinite(v) ? null : +v.toFixed(d === undefined ? 4 : d); }
function ratio(a, b) { return b ? round(a / b, 4) : null; }
function dist2d(ax, ay, bx, by) { const dx = ax - bx, dy = ay - by; return Math.sqrt(dx * dx + dy * dy); }

/* ---- console 同款加载：TLS transform → apply_Rt → denoise ---- */
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
        if (!best || mt > best.mtime) best = { mtime: mt, R: tr.R, t: tr.t, job: job, transform_id: tr.transform_id };
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
    return { dir: dir, meta: meta, frames: ded, tf: tf };
}
function sha256_file(p) { return crypto.createHash("sha256").update(fs.readFileSync(p)).digest("hex"); }

/* ================================================================== */
const t0 = Date.now();
console.log("[r33] loading reference " + REF_SID + " ...");
const REF = load_leveled_denoised(REF_SID);
console.log("[r33] loading current  " + CUR_SID + " ...");
const CUR = load_leveled_denoised(CUR_SID);

const refMap = PL.build_reference_map(REF.frames);
const CUR_ONLINE = PL.build_static_map(CUR.frames, { drop_ground: true });

/* 参考体素计数（两阈值） */
let nRef05 = 0, nRef09 = 0;
refMap.voxels.forEach(rec => { if (rec.occ >= OCC_PRIMARY) nRef05++; if (rec.occ >= OCC_BRIDGE) nRef09++; });

/* ---- ICP 复跑（R3.2 同款；先 CHECK 复现） ---- */
const refRecs09 = [];
refMap.voxels.forEach((rec, key) => { if (rec.occ >= OCC_BRIDGE) refRecs09.push({ x: rec.x, y: rec.y, z: rec.z, occ: rec.occ, key: key }); });
const tgt = [];
CUR_ONLINE.forEach((rec, key) => { if (rec.tier === "strong") tgt.push({ x: rec.x, y: rec.y, z: rec.z, key: key }); });
const tgtIdx = build_vox_index(tgt, 0.28);

let R_icp = [1, 0, 0, 0, 1, 0, 0, 0, 1], t_icp = [0, 0, 0];
const INLIER = 0.25;
let icpIters = 0;
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
    const Rtot = m3.mul(Rn, R_icp);
    const Rnt = m3.apply(Rn, t_icp[0], t_icp[1], t_icp[2]);
    t_icp = [Rnt[0] + tNew[0], Rnt[1] + tNew[1], Rnt[2] + tNew[2]];
    R_icp = Rtot;
    P = transformSrc(refRecs09);
    icpIters = iter + 1;
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
const icpCheckPass = Math.abs(eu.roll - ICP_SAVED.roll) <= 0.02 && Math.abs(eu.pitch - ICP_SAVED.pitch) <= 0.02
    && Math.abs(eu.yaw - ICP_SAVED.yaw) <= 0.02 && Math.abs(t_icp[0] - ICP_SAVED.t[0]) <= 0.002
    && Math.abs(t_icp[1] - ICP_SAVED.t[1]) <= 0.002 && Math.abs(t_icp[2] - ICP_SAVED.t[2]) <= 0.002;
console.log("[r33] ICP rerun iters=" + icpIters + " roll=" + round(eu.roll) + " pitch=" + round(eu.pitch)
    + " yaw=" + round(eu.yaw) + " t=[" + t_icp.map(v => round(v)).join(",") + "]  vs R3.2 saved "
    + JSON.stringify(ICP_SAVED) + " → " + (icpCheckPass ? "CHECK PASS" : "CHECK FAIL"));

/* ---- registration 条件 ---- */
const R_ref = REF.tf.R.flat ? REF.tf.R.flat() : REF.tf.R;
const R_cur = CUR.tf.R.flat ? CUR.tf.R.flat() : CUR.tf.R;
const R_direct = m3.mul(R_cur, m3.t(R_ref));     /* ref leveled → cur leveled（R3.2 sanity 同款，无平移） */
const R_direct_t = m3.t(R_direct);
const R_icp_t = m3.t(R_icp);
function applyAlign(mode, p) {
    if (mode === "none") return p;
    if (mode === "tls") { const q = m3.apply(R_direct_t, p.x, p.y, p.z); return { x: q[0], y: q[1], z: q[2] }; }
    /* icp: p' = Rᵀ(p − t)，把 current 点转入 reference 系（与「变换 reference」数学等价） */
    const q = m3.apply(R_icp_t, p.x - t_icp[0], p.y - t_icp[1], p.z - t_icp[2]);
    return { x: q[0], y: q[1], z: q[2] };
}
const ALIGN_MODES = ["none", "tls", "icp"];

/* ---- matcher 核心：一次 3×3×3 扫描同时得 center 距与 AABB 距 ---- */
const VX = PL.PIPE.bg_voxel_xy, VZ = PL.PIPE.bg_voxel_z;
function scanRef(occMin, px, py, pz) {
    const vox = refMap.voxels;
    const ix = Math.floor(px / VX), iy = Math.floor(py / VX), iz = Math.floor(pz / VZ);
    let d0 = Infinity, d1 = Infinity;
    for (let a = -1; a <= 1; a++) for (let b = -1; b <= 1; b++) for (let c = -1; c <= 1; c++) {
        const rec = vox.get(bg_key_ijk(ix + a, iy + b, iz + c));
        if (!rec || rec.occ < occMin) continue;
        const dx = rec.x - px, dy = rec.y - py, dz = rec.z - pz;
        const c2 = dx * dx + dy * dy + dz * dz;
        if (c2 < d0) d0 = c2;
        /* 占用格 AABB：格 (ix+a, iy+b, iz+c) 的 box 范围 */
        const bx = (ix + a) * VX, by = (iy + b) * VX, bz = (iz + c) * VZ;
        const ex = Math.max(bx - px, 0, px - (bx + VX));
        const ey = Math.max(by - py, 0, py - (by + VX));
        const ez = Math.max(bz - pz, 0, pz - (bz + VZ));
        const b2 = ex * ex + ey * ey + ez * ez;
        if (b2 < d1) d1 = b2;
    }
    return { d0: d0 === Infinity ? null : Math.sqrt(d0), d1: d1 === Infinity ? null : Math.sqrt(d1) };
}

/* 单集合 × 3 registration × 3 matcher 指标 */
function evalSet(pts, occMin) {
    const out = { n: pts.length };
    for (const mode of ALIGN_MODES) {
        let hitC = 0, hitA = 0, hitAc = 0;
        const ds0 = [], ds1 = [];
        for (const p of pts) {
            const q = applyAlign(mode, p);
            const r = scanRef(occMin, q.x, q.y, q.z);
            if (r.d0 !== null) { ds0.push(r.d0); if (r.d0 < MATCH_R) hitC++; }
            if (r.d1 !== null) { ds1.push(r.d1); if (r.d1 < MATCH_R) hitA++; if (r.d1 === 0) hitAc++; }
        }
        const s0 = ds0.slice().sort((a, b) => a - b), s1 = ds1.slice().sort((a, b) => a - b);
        out[mode] = { center: ratio(hitC, pts.length), aabb: ratio(hitA, pts.length), aabb_contain: ratio(hitAc, pts.length),
                      d0_50: round(pct(s0, 0.5)), d0_95: round(pct(s0, 0.95)),
                      d1_50: round(pct(s1, 0.5)), d1_95: round(pct(s1, 0.95)) };
    }
    return out;
}

/* ---- current 工作空间薄点（R3.2 同款抽稀：每帧 ≤3000） ---- */
const curPtsByFrame = [];
CUR.frames.forEach(fr => {
    const pts = [];
    for (let k = 0; k < fr.length; k += 4) {
        const z = fr[k + 2];
        if (z < PL.PIPE.ground_keep_below_m || z > PL.PIPE.z_max_m) continue;
        pts.push({ x: fr[k], y: fr[k + 1], z: z });
    }
    const stride = Math.max(1, Math.floor(pts.length / 3000));
    const thin = [];
    for (let i = 0; i < pts.length; i += stride) thin.push(pts[i]);
    curPtsByFrame.push(thin);
});
const allCurThin = [];
for (const pts of curPtsByFrame) allCurThin.push(...pts);

/* ---- 测试集 1：WD01 簇点（R3.0/R3.2 同款管道） ---- */
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
    if (bestCi < 0) return [];
    const keys = new Set(rawC[bestCi].keys);
    const pts = [];
    for (let k = 0; k < iso.xyzi.length; k += 4) {
        const x = iso.xyzi[k], y = iso.xyzi[k + 1], z = iso.xyzi[k + 2];
        if (keys.has(PL.key_vox(x, y))) pts.push({ x: x, y: y, z: z });
    }
    return pts;
}
const WD01_FRAMES = [2, 42, 150];
const wd01PerFrame = {}, wd01Pooled = [];
for (const fi of WD01_FRAMES) {
    const pts = clusterNear(fi, 3.50, -0.76, 0.50);
    wd01PerFrame["f" + fi] = pts;
    wd01Pooled.push(...pts);
}
console.log("[r33] WD01 cluster n per frame: " + WD01_FRAMES.map(fi => "f" + fi + "=" + wd01PerFrame["f" + fi].length).join(" "));

/* ---- 测试集 2：WD02（代表区圆盘并集 + range>8 对照） ---- */
const WD02_REPS = [{ x: 10.75, y: 4.25 }, { x: 10.25, y: -1.75 }, { x: 10.50, y: 5.50 }];
const wd02Disk = allCurThin.filter(p => WD02_REPS.some(r => dist2d(p.x, p.y, r.x, r.y) <= 1.5));
const wd02Range8 = allCurThin.filter(p => Math.hypot(p.x, p.y) > 8.0);

/* ---- 测试集 3：known-static（受试者双盘排除 + corr-enriched） ---- */
const SUBJ = [{ cx: 1.45, cy: 0.85 }, { cx: 1.52, cy: -0.40 }];   /* R3.0 轨迹两驻点，r=1.2 覆盖全程 */
const knownStatic = allCurThin.filter(p => !SUBJ.some(s => dist2d(p.x, p.y, s.cx, s.cy) < 1.2));
/* corr-enriched：no-align 下 reference 邻域 ≤0.5m（registration 无关的选择，条件固定） */
const knownStaticCorr = knownStatic.filter(p => { const r = scanRef(OCC_PRIMARY, p.x, p.y, p.z); return r.d0 !== null && r.d0 <= 0.5; });

/* ---- 测试集 4：HP01 / HP03（受试者簇 → retention = 1 − match）
 * HP01 分段（R3.0 轨迹 + _probe_hp_cluster.js 实测）：
 *   stand_clean: f80/85/90 站在视线上 (1.52,−0.40)，簇纯人（w 0.18–0.28m，reference 附近无结构）
 *   walk_clean : f63/65/146 行走穿越，簇纯人（h 1.69–1.78、upcos≈1.0）
 *   near_furniture（flagged）: f150/155/160 走过 (1.45,0.85) 静态物旁，簇与静态结构合并/贴邻 —— 只作最坏贴邻参考
 *   f10/30/55 的簇与 (1.45,0.85) 静态物（~1.2m 高、reference 内密集）合并 ≈90% 静态点，不进 retention 口径。 ---- */
const HP01_STAND = [[80, 1.52, -0.40, 0.80], [85, 1.52, -0.40, 0.80], [90, 1.52, -0.40, 0.80]];
const HP01_WALK = [[63, 1.41, 0.06, 0.50], [65, 1.46, -0.11, 0.50], [146, 1.29, -0.17, 0.50]];
const HP01_NEAR = [[150, 1.46, 0.30, 0.50], [155, 1.57, 0.65, 0.50], [160, 1.60, 0.78, 0.50]];
const HP03_FRAMES = [[92, 1.52, -0.40, 0.80], [95, 1.52, -0.40, 0.80], [99, 1.52, -0.40, 0.80], [123, 1.52, -0.40, 0.80]];
function extractFrames(list) {
    const pooled = [], per = {};
    for (const [fi, cx, cy, half] of list) { const pts = clusterNear(fi, cx, cy, half); per["f" + fi] = pts.length; pooled.push(...pts); }
    return { pooled: pooled, per: per };
}
const hp01Stand = extractFrames(HP01_STAND), hp01Walk = extractFrames(HP01_WALK);
const hp01Near = extractFrames(HP01_NEAR), hp03 = extractFrames(HP03_FRAMES);
console.log("[r33] HP01 stand n: " + JSON.stringify(hp01Stand.per) + "  walk: " + JSON.stringify(hp01Walk.per)
    + "  near: " + JSON.stringify(hp01Near.per) + "  HP03: " + JSON.stringify(hp03.per));

/* ---- 评估 ---- */
const tEval = Date.now();
const sets = {};
sets.wd01_pooled_occ05 = evalSet(wd01Pooled, OCC_PRIMARY);
sets.wd01_pooled_occ09 = evalSet(wd01Pooled, OCC_BRIDGE);
for (const fi of WD01_FRAMES) {
    sets["wd01_f" + fi + "_occ05"] = evalSet(wd01PerFrame["f" + fi], OCC_PRIMARY);
    sets["wd01_f" + fi + "_occ09"] = evalSet(wd01PerFrame["f" + fi], OCC_BRIDGE);
}
sets.wd02_disks_occ05 = evalSet(wd02Disk, OCC_PRIMARY);
sets.wd02_range_gt8_occ05 = evalSet(wd02Range8, OCC_PRIMARY);
sets.known_static_occ05 = evalSet(knownStatic, OCC_PRIMARY);
sets.known_static_corr_occ05 = evalSet(knownStaticCorr, OCC_PRIMARY);
sets.all_points_occ05 = evalSet(allCurThin, OCC_PRIMARY);
sets.hp01_stand_occ05 = evalSet(hp01Stand.pooled, OCC_PRIMARY);
sets.hp01_walk_occ05 = evalSet(hp01Walk.pooled, OCC_PRIMARY);
sets.hp01_near_furniture_occ05 = evalSet(hp01Near.pooled, OCC_PRIMARY);
sets.hp03_lying_occ05 = evalSet(hp03.pooled, OCC_PRIMARY);
console.log("[r33] eval done in " + (Date.now() - tEval) + "ms");

/* ---- CHECK：复现 R3.2 关键数字 ---- */
const checks = [];
function check(name, got, expected, tol) {
    const pass = got !== null && Math.abs(got - expected) <= tol;
    checks.push({ name: name, got: got, expected: expected, tol: tol, pass: pass });
    console.log("[r33] CHECK " + name + ": got=" + got + " expected=" + expected + " → " + (pass ? "PASS" : "FAIL"));
    return pass;
}
check("A层 ALL occ0.5 none/center == 0.7796", sets.all_points_occ05.none.center, 0.7796, 0.0005);
check("D层 f42 occ0.9 none/center == 0.8537", sets.wd01_f42_occ09.none.center, 0.8537, 0.0005);
check("D层 f42 occ0.9 icp/center == 0.9906", sets.wd01_f42_occ09.icp.center, 0.9906, 0.0005);
const checksPass = icpCheckPass && checks.every(c => c.pass);

/* ---- 输出 ---- */
const stats = {
    generated: new Date().toISOString(),
    ref_sid: REF_SID, cur_sid: CUR_SID,
    inputs: {
        ref_meta: sha256_file(path.join(REF.dir, "meta.json")),
        ref_points: sha256_file(path.join(REF.dir, "points.bin")),
        cur_meta: sha256_file(path.join(CUR.dir, "meta.json")),
        cur_points: sha256_file(path.join(CUR.dir, "points.bin")),
        human_pipe_lib: sha256_file(path.join(RP, "human_pipe_lib.js")),
    },
    params: { match_radius: MATCH_R, occ_primary: OCC_PRIMARY, occ_bridge: OCC_BRIDGE,
              voxel_xy: VX, voxel_z: VZ, neighborhood: "3x3x3", align_modes: ALIGN_MODES },
    tls: {
        ref: { job: REF.tf.job, transform_id: REF.tf.transform_id },
        cur: { job: CUR.tf.job, transform_id: CUR.tf.transform_id },
    },
    ref_voxels: { occ_ge_05: nRef05, occ_ge_09: nRef09 },
    icp_rerun: { iters: icpIters, roll: round(eu.roll), pitch: round(eu.pitch), yaw: round(eu.yaw),
                 t: t_icp.map(v => round(v)), saved: ICP_SAVED, pass: icpCheckPass },
    checks: checks,
    test_sets: {
        wd01: { frames: WD01_FRAMES, per_frame_n: Object.fromEntries(WD01_FRAMES.map(fi => ["f" + fi, wd01PerFrame["f" + fi].length])),
                pooled_n: wd01Pooled.length },
        wd02: { reps: WD02_REPS, disks_n: wd02Disk.length, range_gt8_n: wd02Range8.length },
        known_static: { subject_disks: SUBJ, radius: 1.2, excl_subject_n: knownStatic.length, corr_enriched_n: knownStaticCorr.length },
        all_points_n: allCurThin.length,
        hp01_stand: { frames: HP01_STAND.map(v => v[0]), windows: HP01_STAND, per_frame_n: hp01Stand.per, pooled_n: hp01Stand.pooled.length },
        hp01_walk: { frames: HP01_WALK.map(v => v[0]), windows: HP01_WALK, per_frame_n: hp01Walk.per, pooled_n: hp01Walk.pooled.length },
        hp01_near_furniture: { frames: HP01_NEAR.map(v => v[0]), windows: HP01_NEAR, per_frame_n: hp01Near.per, pooled_n: hp01Near.pooled.length,
                               note: "FLAGGED: 簇与 (1.45,0.85) 静态物合并/贴邻（R3.0 轨迹 f146–164 回程）；只作最坏贴邻参考，不作纯 retention 口径" },
        hp03_lying: { frames: HP03_FRAMES.map(v => v[0]), windows: HP03_FRAMES, per_frame_n: hp03.per, pooled_n: hp03.pooled.length },
        hp01_merged_excluded: { frames: [10, 30, 55], note: "簇与 (1.45,0.85) 静态物 ≈90% 合并（_probe_hp_cluster.js），不进 retention 口径" },
        hp02: { status: "NOT_RUN", reason: "本地无真人弯腰数据（synth_bend_v1 为合成场景，不适用跨会话 match）；待 W04/采集授权" },
    },
    sets: sets,
    elapsed_ms: Date.now() - t0,
};
fs.writeFileSync(path.join(HERE, "12_r33_stats.json"), JSON.stringify(stats, null, 1) + "\n");

/* ---- 日志 + 矩阵 ---- */
const L = [];
function log(s) { L.push(s); console.log(s); }
function row(name, s) {
    const a = s.none, b = s.icp, t = s.tls;
    log("   " + name.padEnd(26) + " n=" + String(s.n).padStart(6)
        + " | none: C=" + a.center + " A=" + a.aabb + " (c=" + a.aabb_contain + ")"
        + " | tls: C=" + t.center + " A=" + t.aabb
        + " | icp: C=" + b.center + " A=" + b.aabb + " (c=" + b.aabb_contain + ")"
        + " | Δicp=" + (b.aabb !== null && b.center !== null ? round(b.aabb - b.center) : null));
}
log("== W03-R3.3 Center vs AABB AB（coverage@0.12；HP = match，retention = 1−match） ==");
log("   reference occ≥0.5 = " + nRef05 + " voxels（桥接 occ≥0.9 = " + nRef09 + "）；ICP rerun " + (icpCheckPass ? "OK" : "FAIL"));
log("");
log("-- WD01（occ≥0.5；主口径）");
row("WD01 pooled", sets.wd01_pooled_occ05);
for (const fi of WD01_FRAMES) row("WD01 f" + fi, sets["wd01_f" + fi + "_occ05"]);
log("-- WD01（occ≥0.9；R3.2 0.854/0.991 桥接）");
row("WD01 pooled", sets.wd01_pooled_occ09);
for (const fi of WD01_FRAMES) row("WD01 f" + fi, sets["wd01_f" + fi + "_occ09"]);
log("-- WD02");
row("WD02 disks(1.5m)", sets.wd02_disks_occ05);
row("WD02 range>8m", sets.wd02_range_gt8_occ05);
log("-- known-static / ALL");
row("known-static", sets.known_static_occ05);
row("known-static corr", sets.known_static_corr_occ05);
row("ALL points", sets.all_points_occ05);
log("-- HP（match，越低越好 = retained；retention = 1 − match）");
row("HP01 stand (clean)", sets.hp01_stand_occ05);
row("HP01 walk (clean)", sets.hp01_walk_occ05);
row("HP01 near-furn (flag)", sets.hp01_near_furniture_occ05);
row("HP03 lying", sets.hp03_lying_occ05);
log("   HP02 = NOT_RUN（无真人弯腰数据）；near-furn = 簇与静态物合并/贴邻，仅最坏贴邻参考");
log("");
log("== 自检 ==");
for (const c of checks) log("   " + (c.pass ? "PASS" : "FAIL") + "  " + c.name + "  (got " + c.got + ")");
log("elapsed=" + stats.elapsed_ms + "ms");
fs.writeFileSync(path.join(HERE, "13_r33_run.log"), L.join("\n") + "\n");

if (!checksPass) { console.error("[r33] CHECK FAILED — 见 13_r33_run.log"); process.exitCode = 1; }

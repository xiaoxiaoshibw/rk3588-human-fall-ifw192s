/* W03-R3.2 Cross-Session Match Audit — READ-ONLY evidence script（生产零改动）。
 *
 * 口径：与 console 一致 —— reference/current 各自 TLS transform → apply_Rt → denoise →
 *   reference map（R3.1 builder，occ≥0.5 入图）/ 在线 map（build_static_map）。
 * 三层审计（见 05_r32_audit_plan.md）：
 *   A. reference ↔ current 点级匹配（现行 0.12m 半径 + 3×3×3 邻域规则不变，按区域分组）
 *   B. 未匹配点距离误差空间分桶（range / x / y / z / azimuth → 判 angle vs translation）
 *   C. 跨会话刚体残差 ICP（小角度线性化，Jacobi 齐次解 4×4，before/after 匹配率对比）
 *   D. WD01 定点验证（f42 ci1 957 点 → reference 最近邻距离分布 / coverage / after-ICP d50）
 *
 * 依据：W03-R3 验收规范 §3 R3.2；R3.0 实测 Δroll≈2.58°（job c9712aca roll -2.948° vs 6bc5aabf -0.366°）。
 * 禁用：不接 reference 到 production、不改 matcher 半径、不做 AABB、不碰 HUMAN_SHAPE/Tracker。
 *
 * 用法: node 06_r32_audit.js
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
const REF_OCC_MIN = 0.5;             /* R3.1 候选入口阈值（无删除权） */
const MATCH_R = 0.12;                /* 现行 matcher 半径（审计不改） */
const MATCH_R2 = MATCH_R * MATCH_R;

/* ---- 背景体素整数键（与生产 key_bg 同源） ---- */
const BG_BASE = 8192, BG_OFF = 4096;
function bg_key_ijk(ix, iy, iz) { return ((ix + BG_OFF) * BG_BASE + (iy + BG_OFF)) * BG_BASE + (iz + BG_OFF); }
function bg_decode(key) {
    let iz = key % BG_BASE; key = (key - iz) / BG_BASE;
    const iy = key % BG_BASE;
    return [(key - iy) / BG_BASE - BG_OFF, iy - BG_OFF, iz - BG_OFF];
}

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
        /* 反对称小向量 → 旋转矩阵（Rodrigues 精确式，不限小角度） */
        const th = Math.hypot(a[0], a[1], a[2]);
        if (th < 1e-12) return [1, 0, 0, 0, 1, 0, 0, 0, 1];
        const x = a[0] / th, y = a[1] / th, z = a[2] / th, c = Math.cos(th), s = Math.sin(th), C = 1 - c;
        return [c + x * x * C, x * y * C - z * s, x * z * C + y * s,
                y * x * C + z * s, c + y * y * C, y * z * C - x * s,
                z * x * C - y * s, z * y * C + x * s, c + z * z * C];
    },
};

/* ---- Jacobi 对称特征分解（≤6×6，探针 _svd_probe.js 已 PASS 2° roll） ---- */
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

/* ---- 小角度齐次解：未知 [a1,a2,a3,d,e,f]，方程 rows = [[0,-z,y,dx],[z,0,-x,dy],[-y,x,0,dz]] ----
 * 3×3 正常方程 M a = b（旋转部分），平移 t = μ_target - R_total·μ_source（质心解析）。 */
function solveSmallAngle(pairs) {
    /* 未知 a = [a1,a2,a3]（弧度小角向量），方程 [p]×·a ≈ q - p（[p]× 是 p 的反对称阵）。
     * 3×3 正常方程 M·a = b，M = Σ [p]×ᵀ[p]×。用 Jacobi 伪逆（对 M 特征分解，截断小特征值）。 */
    const H = [], rhs = [];
    for (const pr of pairs) {
        const [x, y, z] = pr.p, [qx, qy, qz] = pr.q;
        /* p 经当前累计 R 变换后的坐标（调用方传入已变换 p） */
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
    /* 按特征值排序取最大三个 + 阈值截断（M 正定且通常非奇异） */
    const ord = [0, 1, 2].sort((i, j) => e3.vals[j] - e3.vals[i]);
    const lamMax = e3.vals[ord[0]];
    const a = [0, 0, 0];
    for (const i of ord) {
        const lam = e3.vals[i];
        if (lam < lamMax * 1e-10 || lam < 1e-18) continue;   /* 截断 */
        const v = e3.vecs[i];
        const dot = v[0] * b[0] + v[1] * b[1] + v[2] * b[2];
        for (let j = 0; j < 3; j++) a[j] += (dot / lam) * v[j];
    }
    return a;
}

/* ---- 体素空间哈希（nearest-neighbor / 邻域查询） ---- */
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
    const n = Math.max(1, Math.ceil(maxR / idx.cell));     /* cell < maxR 时至少看 3×3×3 */
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

/* ---- 分位数 ---- */
function pct(sorted, q) {
    if (!sorted.length) return null;
    return sorted[Math.min(sorted.length - 1, Math.ceil(q * sorted.length) - 1)];
}
function round(v, d) { return v === null || v === undefined || !isFinite(v) ? null : +v.toFixed(d === undefined ? 4 : d); }
function mean(a) { return a.length ? a.reduce((s, v) => s + v, 0) / a.length : null; }

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
console.log("[r32] loading reference " + REF_SID + " ...");
const REF = load_leveled_denoised(REF_SID);
console.log("[r32] loading current  " + CUR_SID + " ...");
const CUR = load_leveled_denoised(CUR_SID);

const refMap = PL.build_reference_map(REF.frames);
const online = PL.build_static_map(CUR.frames, { drop_ground: true });

/* reference 入图体素（occ≥0.5），形心数组 */
const refRecs = [];
refMap.voxels.forEach((rec, key) => { if (rec.occ >= REF_OCC_MIN) refRecs.push({ x: rec.x, y: rec.y, z: rec.z, occ: rec.occ, key: key }); });
const refIdx = build_vox_index(refRecs, 0.28);

/* current 工作空间点（逐帧抽稀：每帧最多取 3000 个，避免 500 万点 O(n²)） */
const curPtsByFrame = [];
CUR.frames.forEach((fr, fi) => {
    const pts = [];
    for (let k = 0; k < fr.length; k += 4) {
        const z = fr[k + 2];
        if (z < PL.PIPE.ground_keep_below_m || z > PL.PIPE.z_max_m) continue;
        pts.push({ x: fr[k], y: fr[k + 1], z: z });
    }
    /* 均匀抽稀 */
    const stride = Math.max(1, Math.floor(pts.length / 3000));
    const thin = [];
    for (let i = 0; i < pts.length; i += stride) thin.push(pts[i]);
    curPtsByFrame.push(thin);
});

/* 区域窗口（leveled, m） */
const WD01 = { cx: 3.50, cy: -0.76, half: 0.50 };
const HP_RANGE = [3.0, 8.0];          /* 活动目标大致 range（leveled） */
function inW(p, W) { return Math.abs(p.x - W.cx) <= W.half && Math.abs(p.y - W.cy) <= W.half; }
function regionOf(p) {
    if (inW(p, WD01)) return "WD01";
    const r = Math.hypot(p.x, p.y);
    if (r > 5.0) return "FAR";           /* 远场（含 WD02 类稀疏面） */
    if (r >= HP_RANGE[0] && r <= HP_RANGE[1]) return "NEAR";
    return "MID";
}

/* ---- A 层：点级匹配（现行规则：3×3×3 邻域 + 形心距 < 0.12），分组统计 ---- */
const groups = {};
function group(name) {
    if (!groups[name]) groups[name] = { n: 0, exact: 0, nb: 0, match: 0, d: [] };
    return groups[name];
}
const gAll = group("ALL");

for (const pts of curPtsByFrame) {
    for (const p of pts) {
        const reg = regionOf(p);
        const G = group(reg);
        /* 现行规则：3×3×3 邻域里任一 reference 形心距 < 0.12 即吸收 */
        const ix = Math.floor(p.x / PL.PIPE.bg_voxel_xy), iy = Math.floor(p.y / PL.PIPE.bg_voxel_xy),
              iz = Math.floor(p.z / PL.PIPE.bg_voxel_z);
        let exact = false, nb = false, bestD2 = Infinity;
        for (let a = -1; a <= 1; a++) for (let b = -1; b <= 1; b++) for (let c = -1; c <= 1; c++) {
            const kk = bg_key_ijk(ix + a, iy + b, iz + c);
            const rec = refMap.voxels.get(kk);
            if (!rec || rec.occ < REF_OCC_MIN) continue;
            if (!a && !b && !c) exact = true;
            nb = true;
            const dx = rec.x - p.x, dy = rec.y - p.y, dz = rec.z - p.z, d2 = dx * dx + dy * dy + dz * dz;
            if (d2 < bestD2) bestD2 = d2;
        }
        const d = bestD2 < Infinity ? Math.sqrt(bestD2) : null;
        const hit = d !== null && d < MATCH_R;
        G.n++; gAll.n++;
        if (exact) { G.exact++; gAll.exact++; }
        if (nb) { G.nb++; gAll.nb++; }
        if (d !== null) { G.d.push(d); gAll.d.push(d); }
        if (hit) { G.match++; gAll.match++; }
    }
}

/* ---- B 层：距离误差空间分桶（向量化，先把每点的邻域最近距离算一遍，再按维度分桶） ---- */
function rangeBin(p) { const r = Math.hypot(p.x, p.y); return r < 1 ? "0-1" : r < 2 ? "1-2" : r < 3 ? "2-3" : r < 4 ? "3-4" : r < 6 ? "4-6" : r < 8 ? "6-8" : "8+"; }
function xBin(p) { return (Math.floor(p.x / 1) * 1) + ".." + (Math.floor(p.x / 1) * 1 + 1); }
function yBin(p) { return (Math.floor(p.y / 1) * 1) + ".." + (Math.floor(p.y / 1) * 1 + 1); }
function zBin(p) { return p.z < 0.5 ? "0-0.5" : p.z < 1.0 ? "0.5-1" : p.z < 1.5 ? "1-1.5" : p.z < 2.0 ? "1.5-2" : "2+"; }
function azBin(p) { const a = Math.atan2(p.y, p.x) * 180 / Math.PI; return (Math.floor(a / 30) * 30) + ".." + (Math.floor(a / 30) * 30 + 30); }

const allCurThin = [];
for (const pts of curPtsByFrame) allCurThin.push(...pts);

/* 向量化：构造 (binKey, dmin, hit) 三元组数组，五个维度共算一次邻域 */
const refKeySet = new Set();
refMap.voxels.forEach((rec, key) => { if (rec.occ >= REF_OCC_MIN) refKeySet.add(key); });
function computeB() {
    const dims = [
        { name: "by_range", fn: rangeBin },
        { name: "by_x", fn: xBin },
        { name: "by_y", fn: yBin },
        { name: "by_z", fn: zBin },
        { name: "by_azimuth", fn: azBin },
    ];
    const bins = {};
    for (const d of dims) bins[d.name] = new Map();
    for (const p of allCurThin) {
        const ix = Math.floor(p.x / PL.PIPE.bg_voxel_xy), iy = Math.floor(p.y / PL.PIPE.bg_voxel_xy),
              iz = Math.floor(p.z / PL.PIPE.bg_voxel_z);
        /* 快速路径：exact cell 在 refKeySet 且其形心距 < 0.12 时，多数体素即命中（仍会进邻域求精确 d） */
        let bestD2 = Infinity, nb = false;
        for (let a = -1; a <= 1; a++) for (let b = -1; b <= 1; b++) for (let c = -1; c <= 1; c++) {
            const rec = refMap.voxels.get(bg_key_ijk(ix + a, iy + b, iz + c));
            if (!rec || rec.occ < REF_OCC_MIN) continue;
            nb = true;
            const dx = rec.x - p.x, dy = rec.y - p.y, dz = rec.z - p.z, d2 = dx * dx + dy * dy + dz * dz;
            if (d2 < bestD2) bestD2 = d2;
        }
        for (const dim of dims) {
            const k = dim.fn(p);
            let bin = bins[dim.name].get(k);
            if (!bin) { bin = { n: 0, with_nb: 0, hit: 0, d: [] }; bins[dim.name].set(k, bin); }
            bin.n++;
            if (!nb) continue;
            const d = Math.sqrt(bestD2);
            bin.with_nb++; bin.d.push(d);
            if (d < MATCH_R) bin.hit++;
        }
    }
    const out = {};
    for (const dim of dims) {
        out[dim.name] = [...bins[dim.name].entries()].sort((a, b2) => a[0] < b2[0] ? -1 : 1).map(([k, b]) => {
            const ds = b.d.slice().sort((x, y) => x - y);
            return { bin: k, n: b.n, with_nb: b.with_nb,
                     match_ratio: round(b.with_nb ? b.hit / b.with_nb : null, 4),
                     d50: round(pct(ds, 0.5)), d95: round(pct(ds, 0.95)) };
        });
    }
    return out;
}
const B = computeB();

/* ---- C 层：ICP（source = reference 高置信形心，target = current 在线 strong 形心） ---- */
const src = refRecs.filter(r => r.occ >= 0.9);
const tgt = [];
online.forEach((rec, key) => { if (rec.tier === "strong") tgt.push({ x: rec.x, y: rec.y, z: rec.z, key: key }); });
const tgtIdx = build_vox_index(tgt, 0.28);

let R = [1, 0, 0, 0, 1, 0, 0, 0, 1], t = [0, 0, 0];
const INLIER = 0.25;
const icpLog = [];
function transformSrc(P) {
    return src.map(p => {
        const q = m3.apply(R, p.x, p.y, p.z);
        return { x: q[0] + t[0], y: q[1] + t[1], z: q[2] + t[2], occ: p.occ };
    });
}
let P = transformSrc();
for (let iter = 0; iter < 50; iter++) {
    const pairs = [];
    for (const p of P) {
        const hit = nn_query(tgtIdx, p.x, p.y, p.z, INLIER);
        if (hit) pairs.push({ p: [p.x, p.y, p.z], q: [hit.rec.x, hit.rec.y, hit.rec.z], d: hit.d });
    }
    if (pairs.length < 20) break;
    /* 小角度解（对当前 P）：方程 H·a = q-p 中 H=[p]× = -[a×p]，解的 a_est = -a_true，取反 */
    const aEst = solveSmallAngle(pairs);
    const a = aEst.map(v => -v);
    /* 平移：t = μq - R_new·μp */
    const mup = [0, 0, 0], muq = [0, 0, 0];
    for (const pr of pairs) { for (let i = 0; i < 3; i++) { mup[i] += pr.p[i]; muq[i] += pr.q[i]; } }
    for (let i = 0; i < 3; i++) { mup[i] /= pairs.length; muq[i] /= pairs.length; }
    const Rn = m3.rodrigues(a);
    const Rmup = m3.apply(Rn, mup[0], mup[1], mup[2]);
    const tNew = [muq[0] - Rmup[0], muq[1] - Rmup[1], muq[2] - Rmup[2]];
    /* 累计：先旋转再平移 → total 变换为 q ≈ Rn·(R·p+t)+tNew = Rn·R·p + (Rn·t + tNew) */
    const Rtot = m3.mul(Rn, R);
    const Rnt = m3.apply(Rn, t[0], t[1], t[2]);
    const ttot = [Rnt[0] + tNew[0], Rnt[1] + tNew[1], Rnt[2] + tNew[2]];
    R = Rtot; t = ttot;
    P = transformSrc();
    /* 当前 RMS */
    let rms = 0; for (const pr of pairs) rms += pr.d * pr.d; rms = Math.sqrt(rms / pairs.length);
    const rotDeg = Math.hypot(a[0], a[1], a[2]) * 180 / Math.PI;
    icpLog.push({ iter: iter, pairs: pairs.length, incRot_deg: round(rotDeg, 5), rms: round(rms, 5),
                  t: [round(t[0], 5), round(t[1], 5), round(t[2], 5)] });
    if (rotDeg < 1e-3 && Math.hypot(tNew[0], tNew[1], tNew[2]) < 1e-4) break;
}

/* 提取欧拉角（先 roll/pitch/yaw 顺序不重要——审计只看量级） */
function eulerFromR(R) {
    const pitch = Math.asin(Math.max(-1, Math.min(1, -R[6])));
    const roll = Math.atan2(R[7], R[8]);
    const yaw = Math.atan2(R[3], R[0]);
    return { roll: roll * 180 / Math.PI, pitch: pitch * 180 / Math.PI, yaw: yaw * 180 / Math.PI };
}
const eu = eulerFromR(R);

/* before / after 点级匹配率（全部 current 薄点） */
function matchStats(Psrc) {
    const idx = build_vox_index(Psrc, 0.28);
    let n = 0, hit = 0, noNb = 0;
    const dists = [];
    for (const p of allCurThin) {
        n++;
        const hitR = nn_query(idx, p.x, p.y, p.z, MATCH_R);
        if (hitR) { hit++; dists.push(hitR.d); }
        else {
            const nb = nn_query(idx, p.x, p.y, p.z, 0.5);
            if (!nb) noNb++;
            else dists.push(nb.d);
        }
    }
    const ds = dists.slice().sort((a, b) => a - b);
    return { n: n, match_ratio: round(hit / n, 4), no_neighbor: noNb,
             d50: round(pct(ds, 0.5)), d95: round(pct(ds, 0.95)) };
}
const before = matchStats(src);
const after = matchStats(P);

/* ---- D 层：WD01 定点验证（R3.0 f42 ci1 的 957 点 → reference 最近邻） ---- */
/* f42 的 WD01 簇：复刻 R3.0 管道（denoise → extract_foreground 用 CURRENT 在线 map → cluster_voxels
 *   → 取窗口内最大簇的 keys → 用 keys 反查簇点）。f2/f150 用窗口近似（与 R3.0 同帧段同一物体）。
 *   注意：这里不动 reference，只重建 CURRENT 自己的在线 map，口径与 R3.0 完全一致。 */
const CUR_ONLINE = PL.build_static_map(CUR.frames, { drop_ground: true });
function wd01ClusterPoints(frameIdx) {
    const fr = CUR.frames[frameIdx];
    const fg = PL.extract_foreground(fr, CUR_ONLINE);
    const iso = PL.cleanup_isolated_fg(fg.fg_xyzi);
    const rawC = PL.cluster_voxels(PL.voxelize(iso.xyzi));
    /* 找窗口内最大簇 */
    let bestCi = -1, bestN = 0;
    for (let ci = 0; ci < rawC.length; ci++) {
        const f = PL.cluster_features(rawC[ci]);
        if (!f.ok) continue;
        if (Math.abs(f.cx - WD01.cx) <= WD01.half && Math.abs(f.cy - WD01.cy) <= WD01.half && f.n > bestN) { bestN = f.n; bestCi = ci; }
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
function wd01Dist(Psrc) {
    const idx = build_vox_index(Psrc, 0.28);
    const rows = {};
    for (const fi of [2, 42, 150]) {
        const pts = wd01ClusterPoints(fi);
        const dists = [];
        for (const p of pts) {
            const hit = nn_query(idx, p.x, p.y, p.z, 1.0);
            if (hit) dists.push(hit.d);
        }
        const ds = dists.slice().sort((a, b) => a - b);
        const cov12 = dists.filter(d => d < MATCH_R).length, cov20 = dists.filter(d => d < 0.20).length;
        rows["f" + fi] = { n: pts.length, coverage012: round(pts.length ? cov12 / pts.length : null, 4),
                           coverage020: round(pts.length ? cov20 / pts.length : null, 4),
                           d50: round(pct(ds, 0.5)), d95: round(pct(ds, 0.95)), dmax: round(ds.length ? ds[ds.length - 1] : null) };
    }
    return rows;
}
const wd01Before = wd01Dist(src);
const wd01After = wd01Dist(P);

/* ---- 汇总分组指标 ---- */
function groupRow(name, G) {
    const ds = G.d.slice().sort((a, b) => a - b);
    return { region: name, n: G.n,
             exact_hit_ratio: round(G.exact / G.n, 4),
             neighbor_hit_ratio: round(G.nb / G.n, 4),
             match_ratio: round(G.match / G.n, 4),
             d50: round(pct(ds, 0.5)), d95: round(pct(ds, 0.95)),
             dmax: round(ds.length ? ds[ds.length - 1] : null) };
}
const A = ["WD01", "NEAR", "MID", "FAR", "ALL"].filter(k => groups[k]).map(k => groupRow(k, groups[k]));

/* TLS 双侧参数（对照） */
const tls = {
    ref: REF.tf ? { job: REF.tf.job, transform_id: REF.tf.transform_id,
                    pitch_deg: null, roll_deg: null, tz: REF.tf.t[2] } : null,
    cur: CUR.tf ? { job: CUR.tf.job, transform_id: CUR.tf.transform_id,
                    pitch_deg: null, roll_deg: null, tz: CUR.tf.t[2] } : null,
};
function fillAngles(side) {
    if (!side) return;
    const p = path.join(REPO, "captures", "leveled", side.job, "tls", "transform.json");
    const tr = JSON.parse(fs.readFileSync(p, "utf8"));
    side.pitch_deg = tr.pitch_deg; side.roll_deg = tr.roll_deg;
}
fillAngles(tls.ref); fillAngles(tls.cur);

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
    tls: tls,
    expected_drift_m_at_3m: round(Math.abs(((tls.ref && tls.ref.roll_deg) || 0) - ((tls.cur && tls.cur.roll_deg) || 0)) * Math.PI / 180 * 3, 4),
    params: { ref_occ_min: REF_OCC_MIN, match_radius: MATCH_R, bg_voxel_xy: PL.PIPE.bg_voxel_xy, bg_voxel_z: PL.PIPE.bg_voxel_z },
    ref: { total_voxels: refMap.voxels.size, at_occ_ge_05: refRecs.length, at_occ_ge_09: src.length },
    online_cur: { strong: tgt.length },
    A_groups: A,
    B_bucket_miss: B,
    C_icp: {
        inlier_m: INLIER, iters: icpLog.length, log: icpLog.slice(-6),
        rot_after_deg: { roll: round(eu.roll, 4), pitch: round(eu.pitch, 4), yaw: round(eu.yaw, 4) },
        t: [round(t[0], 4), round(t[1], 4), round(t[2], 4)],
        known_tls_droll_deg: round(((tls.ref && tls.ref.roll_deg) || 0) - ((tls.cur && tls.cur.roll_deg) || 0), 4),
        before: before, after: after,
    },
    D_wd01: { window: { cx: WD01.cx, cy: WD01.cy, half: WD01.half },
              before: wd01Before, after: wd01After },
    elapsed_ms: Date.now() - t0,
};
fs.writeFileSync(path.join(HERE, "07_r32_stats.json"), JSON.stringify(stats, null, 1) + "\n");

/* ---- 日志 ---- */
const L = [];
function log(s) { L.push(s); console.log(s); }
log("[r32] ref " + REF_SID + " (job " + tls.ref.job.slice(0, 8) + " pitch " + tls.ref.pitch_deg.toFixed(2)
    + " roll " + tls.ref.roll_deg.toFixed(2) + ") ref voxels occ>=0.5 = " + refRecs.length + " (>=0.9 = " + src.length + ")");
log("[r32] cur " + CUR_SID + " (job " + tls.cur.job.slice(0, 8) + " pitch " + tls.cur.pitch_deg.toFixed(2)
    + " roll " + tls.cur.roll_deg.toFixed(2) + ") online strong = " + tgt.length);
log("[r32] TLS Δroll = " + stats.C_icp.known_tls_droll_deg + "° → 3m 处漂移 ≈ " + stats.expected_drift_m_at_3m + " m");
log("");
log("== A. 基础匹配（现行 0.12m 规则） ==");
for (const r of A) log("   " + r.region.padEnd(5) + " n=" + String(r.n).padStart(6)
    + "  exact=" + r.exact_hit_ratio + "  nb=" + r.neighbor_hit_ratio + "  match=" + r.match_ratio
    + "  d50=" + r.d50 + "  d95=" + r.d95 + "  dmax=" + r.dmax);
log("");
log("== B. 距离误差分桶（match_ratio / d50 / d95） ==");
for (const dim of ["by_range", "by_x", "by_y", "by_z", "by_azimuth"]) {
    log("-- " + dim);
    for (const b of B[dim]) log("   " + String(b.bin).padEnd(9) + " n=" + String(b.n).padStart(6)
        + "  with_nb=" + String(b.with_nb).padStart(6) + "  match=" + b.match_ratio
        + "  d50=" + b.d50 + "  d95=" + b.d95);
}
log("");
log("== C. ICP 跨会话刚体残差 ==");
log("   iters=" + icpLog.length + "  inlier=" + INLIER + "m");
for (const row of icpLog.slice(-6)) log("   iter " + row.iter + "  pairs=" + row.pairs
    + "  incRot=" + row.incRot_deg + "°  rms=" + row.rms + "  t=" + row.t.join(","));
log("   估计累计旋转（度）: roll=" + stats.C_icp.rot_after_deg.roll
    + "  pitch=" + stats.C_icp.rot_after_deg.pitch + "  yaw=" + stats.C_icp.rot_after_deg.yaw);
log("                  平移（m）: " + stats.C_icp.t.join(", "));
log("   TLS 口径 Δroll = " + stats.C_icp.known_tls_droll_deg + "°");
log("   before: match=" + before.match_ratio + "  d50=" + before.d50 + "  d95=" + before.d95);
log("   after : match=" + after.match_ratio + "  d50=" + after.d50 + "  d95=" + after.d95);
log("");
log("== D. WD01 定点验证 ==");
for (const k of Object.keys(wd01Before)) {
    const b0 = wd01Before[k], a0 = wd01After[k];
    log("   " + k + "  n=" + b0.n
        + "  before cov@0.12=" + b0.coverage012 + " d50=" + b0.d50 + " d95=" + b0.d95
        + " | after cov@0.12=" + a0.coverage012 + " d50=" + a0.d50 + " d95=" + a0.d95);
}
log("");
log("== 决策树走向 ==");
const recovered = after.match_ratio > before.match_ratio * 1.4 && after.d50 !== null && before.d50 !== null && after.d50 < before.d50 * 0.6;
log(recovered
    ? "   alignment 后明显恢复（match×" + round(after.match_ratio / before.match_ratio, 2) + "，d50→" + after.d50 + "）→ 优先修 session alignment，暂不进入 R3.3 matcher 改动。"
    : "   alignment 后未显著恢复 → 才可能需要 R3.3 matcher geometry；详见 09_r32_summary.md。");
log("elapsed=" + stats.elapsed_ms + "ms");

fs.writeFileSync(path.join(HERE, "08_r32_run.log"), L.join("\n") + "\n");

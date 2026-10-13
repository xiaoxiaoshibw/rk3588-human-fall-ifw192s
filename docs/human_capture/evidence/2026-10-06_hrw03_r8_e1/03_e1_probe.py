#!/usr/bin/env node
/* ============================================================================
 * W03-HR-E1 · Temporal Stability / Mobility Audit（SHADOW-ONLY / READ-ONLY）
 *
 * 唯一目标：判定 203349 空场 reference（occ≥0.5, 3707 体素）中，多少高占用体素
 * 属于 STATIC / MOVABLE / UNRESOLVED，以及这些体素对 223757 站点残块的贡献。
 *
 * 本文件以 .py 为扩展名是工单登记的 data contract；实现语言为 Node.js
 * （本链路全部 loader/纯函数/matcher 语义在 Node 层，Python 端无现成等价器）。
 * 运行：`node 03_e1_probe.py`。
 *
 * 冻结项（E-1 从头到尾唯一变量 = temporal stability / cross-session persistence）：
 *   - registration = R3.2/r7 复跑验证过的固定 ICP 解（本脚本内复跑一次仅作 CHECK，
 *     与 {roll 1.7476, pitch -0.2818, yaw -2.3924, t [0.0182,0.031,0.0012]} 比对；
 *     不允许 sweep / 重对齐 / 改任何参数以“提高 persistence”）。
 *   - voxel semantics：key_bg / bg_voxel_xy 0.15 / bg_voxel_z 0.12（生产同源）；
 *   - matcher spatial semantics：3×3×3 邻域 + 点到形心 < 0.12（pl._bg_match 语速）；
 *   - leveling：两会话各自 TLS frozen job（不重新估计）。
 *
 * 禁止：任何 production 文件 / builder / radius / tier / connectivity / leveling / ICP 修改；
 *      不 commit；不写 evidence 目录以外文件。
 *
 * 判定规则（§7，宁 UNRESOLVED 勿 MOVABLE）：
 *   STATIC   ：covered==165；缺席 run 全 ≤3；bOTH 无持续缺失。
 *   MOVABLE  ：covered==165 且存在连续 ≥5 帧 supported-present → ≥8 帧 absent 转变（或反向），
 *              且缺席持续 ≥8 帧（遮挡只有 1–2 帧的解释力被排除）；
 *              或 cur_visible_occ ≥0.90 且 never_supported。
 *   UNRESOLVED：其余全部（含 registration residual 无法排除、遮挡、weak evidence 等）。
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

const OUTDIR = HERE;
const CUR_SID = "cap_20261002_223757";
const REF_SID = "cap_20261004_203349";
const OCC_MIN = PL.PIPE.bg_ref_occ_min;    /* 0.5（v1 候选，不改） */
const MATCH_R = PL.PIPE.bg_match_radius;   /* 0.12 */
const VX = PL.PIPE.bg_voxel_xy, VZ = PL.PIPE.bg_voxel_z;
const R2 = MATCH_R * MATCH_R;
const GROUND = PL.PIPE.ground_keep_below_m, ZMAX = PL.PIPE.z_max_m;
/* 复用既有窗口定义（不重新发现 ROI） */
const STATION = { x: 1.45, y: 0.85, r: 0.60, zlo: 0.80, zhi: 1.30 };   /* r7 §2 站点块窗口 */
const WD01 = { x: 3.50, y: -0.76, r: 0.90 };                            /* r7 §1 WD01 区域 */
const WD02_REPS = [{ x: 10.75, y: 4.25 }, { x: 10.25, y: -1.75 }, { x: 10.50, y: 5.50 }];
const WD02_R = 1.50;                                                     /* 代表盘判别半径（生成表用） */
/* 既有站点时序（r7 05 §2 / r3 时间线；f154+ 受试者回站，2026-10-04→05 重新审视） */
const SUBJECT_PHASES = [
    { name: "at_station", from: 0, to: 54 },
    { name: "departing", from: 55, to: 64 },
    { name: "away", from: 65, to: 153 },
    { name: "returned", from: 154, to: 165 },
];

const L = [];
function log(s) { L.push(s); console.log(s); }
function round(v, d) { return v === null || v === undefined || !isFinite(v) ? null : +v.toFixed(d === undefined ? 4 : d); }
function sha256_buf(b) { return crypto.createHash("sha256").update(b).digest("hex"); }
function sha256_file(p) { return sha256_buf(fs.readFileSync(p)); }
function sha256_file_canon(p) {
    const b = fs.readFileSync(p);
    return sha256_buf(Buffer.from(b.toString("latin1").replace(/\r\n/g, "\n").replace(/\r/g, "\n"), "latin1"));
}

/* ---- 3×3 矩阵 / Jacobi / 小角解（与 r7 10_r35_attribution.js / r5 11_r33_ab.js 逐行同款） ---- */
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
                z * x * C - y * s, z * y * C - x * s, c + z * z * C];
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
            const app = A[p][p], aqq = A[q][q], apq = A[q][q];
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
            if (d2 < bestD2) { bestD2 = d2; best = { rec: r, d: Math.sqrt(d2) }; }
        }
    }
    return best;
}

/* ---- 固定 registration（R3.2/11_r33 存档 + r7 复跑 CHECK PASS；E-1 不重新估计） ----
 * 方向（与 r7 `alignPoint("icp")` 完全同义）：
 *   cur lev 系点 p → ref lev 系查询点 q = R_icpᵀ · (p − t_icp)
 *   ref lev 系体素形心 c → cur lev 系空间位置 = R_icp · c + t_icp
 * 这里由存档 euler + t 直接构造 R_icp（roll/pitch/yaw 约定与 r7 eulerFromR 互逆），
 * 不跑 ICP 迭代；参数也在 04_voxel_results.json.transforms 里明文登记。 */
const ICP_FROZEN_EU = { roll_deg: 1.7476, pitch_deg: -0.2818, yaw_deg: -2.3924 };
const T_ICP_FROZEN = [0.0182, 0.031, 0.0012];
function r_of_euler(e) { /* R = Rz(yaw)·Ry(pitch)·Rx(roll)；eulerFromR 的互逆 */
    const cr = Math.cos(e.roll_deg * Math.PI / 180), sr = Math.sin(e.roll_deg * Math.PI / 180);
    const cp = Math.cos(e.pitch_deg * Math.PI / 180), sp = Math.sin(e.pitch_deg * Math.PI / 180);
    const cy = Math.cos(e.yaw_deg * Math.PI / 180), sy = Math.sin(e.yaw_deg * Math.PI / 180);
    return [cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr,
            sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr,
            -sp, cp * sr, cp * cr];
}
const R_ICP_FROZEN = r_of_euler(ICP_FROZEN_EU);
const R_ICP_FROZEN_T = m3.t(R_ICP_FROZEN);

/* ---- 背景体素整数键 / 生产语义（与 r7 同源） ---- */
const BG_BASE = 8192, BG_OFF = 4096;
function bg_key_ijk(ix, iy, iz) { return ((ix + BG_OFF) * BG_BASE + (iy + BG_OFF)) * BG_BASE + (iz + BG_OFF); }
function bg_key(x, y, z) { return bg_key_ijk(Math.floor(x / VX), Math.floor(y / VX), Math.floor(z / VZ)); }

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
function load_leveled_raw(sid) {
    /* 与 r7 同款到 apply_Rt；不 denoise（denoise 只做有限点+距窗，r7 已证本数据距窗 0 触发） */
    const dir = path.join(REPO, "captures", "remote", sid);
    const meta = JSON.parse(fs.readFileSync(path.join(dir, "meta.json"), "utf8"));
    const raw = fs.readFileSync(path.join(dir, "points.bin"));
    const f32 = new Float32Array(raw.buffer, raw.byteOffset, raw.byteLength / 4);
    const frames = RL.frame_slice(meta);
    const STRIDE = RL.STRIDE_F32;
    const tf = resolve_transform(sid);
    const fr = frames.map(f => {
        const s = RL.strided_f32_copy(f32, f.start_pts, f.count, STRIDE);
        if (tf) apply_Rt(s, tf.R, tf.t);
        return s;
    });
    return { dir: dir, meta: meta, frames: fr, tf: tf };
}
function denoisedOf(rawFrames) { return rawFrames.map(s => PL.denoise(s)); }

log("[e1] loading reference " + REF_SID + " ...");
const REF = load_leveled_raw(REF_SID);
log("[e1] loading current  " + CUR_SID + " ...");
const CUR = load_leveled_raw(CUR_SID);
if (!CUR.tf || !REF.tf) { console.error("[e1] FATAL: missing tls transform"); process.exit(2); }
const N_CUR = CUR.frames.length, N_REF = REF.frames.length;
const REF_DENOISED = denoisedOf(REF.frames);

/* ---- reference builder（生产 PL.build_reference_map；只读复用） ---- */
const refMapObj = PL.build_reference_map(REF_DENOISED);
if (refMapObj.voxels.size !== 5286) { console.error("[e1] FATAL: ref voxels " + refMapObj.voxels.size + " != 5286"); process.exit(2); }

/* ---- universe：ref occ>=0.5（生产 reference_static_keys 同口径，只读） ---- */
const UNIVERSE = [];
refMapObj.voxels.forEach((rec, key) => {
    if (rec.occ < OCC_MIN) return;
    UNIVERSE.push({ key: key, x: rec.x, y: rec.y, z: rec.z, occ: rec.occ, obs: rec.obs });
});
UNIVERSE.sort((a, b) => a.key - b.key);
log("[e1] universe (occ>=" + OCC_MIN + ") voxels = " + UNIVERSE.length);
if (UNIVERSE.length !== 3707) { console.error("[e1] FATAL: universe " + UNIVERSE.length + " != 3707"); process.exit(2); }

/* ---- online map（生产 PL.build_static_map；与 r7 等价门 1720 键） ---- */
const CUR_DENOISED = denoisedOf(CUR.frames);
const onlineMap = PL.build_static_map(CUR_DENOISED, { drop_ground: true });
log("[e1] online map keys = " + onlineMap.size);

/* ---- ICP 冻结，不重新估计（E-1 唯一变量 = temporal stability；方向与 r7 alignPoint("icp") 同义） ---- */
const R_icp_t = R_ICP_FROZEN_T;
/* current（cur lev 系）→ ref（ref lev 系）支持查询：q = R_icpᵀ·(p − t)（= r7 alignPoint("icp")） */
function curPtToRef(x, y, z) { return m3.apply(R_ICP_FROZEN_T, x - T_ICP_FROZEN[0], y - T_ICP_FROZEN[1], z - T_ICP_FROZEN[2]); }
/* ref voxel 形心 → cur lev 系的空间距离查询：p = R_icp·c + t（诊断用） */
function refCtrToCur(x, y, z) { const q = m3.apply(R_ICP_FROZEN, x, y, z); return [q[0] + T_ICP_FROZEN[0], q[1] + T_ICP_FROZEN[1], q[2] + T_ICP_FROZEN[2]]; }
function eulerFromR(R) { /* 与 r7 同式（供 transforms 登记复核） */
    const pitch = Math.asin(Math.max(-1, Math.min(1, -R[6])));
    const roll = Math.atan2(R[7], R[8]);
    const yaw = Math.atan2(R[3], R[0]);
    return { roll: roll * 180 / Math.PI, pitch: pitch * 180 / Math.PI, yaw: yaw * 180 / Math.PI };
}
const ICP_FROZEN_EU_CHECK = eulerFromR(R_ICP_FROZEN); /* 自洽复核：构造矩阵的欧拉应≈登记值 */
log("[e1] ICP frozen roll=" + round(ICP_FROZEN_EU_CHECK.roll, 4) + " pitch=" + round(ICP_FROZEN_EU_CHECK.pitch, 4)
    + " yaw=" + round(ICP_FROZEN_EU_CHECK.yaw, 4) + " t=[" + T_ICP_FROZEN.map(v => round(v, 4)).join(",") + "]（固定，不重新估计）");

/* =====================================================================
 * Pass 1 · reference per-frame visible bitmap（universe 体素逐帧 raw 点内落）
 * ===================================================================== */
log("[e1] pass1: reference per-frame visible bitmap ...");
const uniByKey = new Map();
for (let i = 0; i < UNIVERSE.length; i++) uniByKey.set(UNIVERSE[i].key, i);
const refPresence = new Array(UNIVERSE.length); /* Array<Uint8Array(102)> */
for (let i = 0; i < UNIVERSE.length; i++) refPresence[i] = new Uint8Array(N_REF);
for (let f = 0; f < N_REF; f++) {
    const frame = REF.frames[f];
    for (let k = 0; k < frame.length; k += 4) {
        const z = frame[k + 2];
        if (z < GROUND || z > ZMAX) continue;
        const idx = uniByKey.get(bg_key(frame[k], frame[k + 1], z));
        if (idx !== undefined) refPresence[idx][f] = 1;
    }
}

/* =====================================================================
 * Pass 2 · current online per-frame hits/tier（复刻 builder 判定，只读 BUG_REPORT）
 * ===================================================================== */
log("[e1] pass2: current online per-frame hits/tier 复刻 ...");
const BF = PL.PIPE.bg_hit_min_pts;                        /* 2 */
const thr_strong = Math.ceil(N_CUR * PL.PIPE.bg_occ_strong);   /* ceil(165*0.85)=141 */
const thr_sup = Math.ceil(N_CUR * PL.PIPE.bg_occ_supported);   /* ceil(165*0.65)=108 */
const onlineHits = new Map();                             /* key → Uint8Array(165) */
const onlineWelford = new Map();                          /* key → {hits,cx,cy,cz,mx,my,mz} */
for (let f = 0; f < N_CUR; f++) {
    const frame = CUR.frames[f];
    const per = new Map();
    for (let k = 0; k < frame.length; k += 4) {
        const z = frame[k + 2];
        if (z < GROUND || z > ZMAX) continue;
        const key = bg_key(frame[k], frame[k + 1], z);
        let a = per.get(key);
        if (!a) { a = { n: 0, sx: 0, sy: 0, sz: 0 }; per.set(key, a); }
        a.n++; a.sx += frame[k]; a.sy += frame[k + 1]; a.sz += z;
    }
    per.forEach((a, key) => {
        if (a.n < BF) return;
        let s = onlineWelford.get(key);
        if (!s) { s = { hits: 0, cx: 0, cy: 0, cz: 0, mx: 0, my: 0, mz: 0 }; onlineWelford.set(key, s); }
        s.hits++;
        const px = a.sx / a.n, py = a.sy / a.n, pz = a.sz / a.n;
        const dx = px - s.cx, dy = py - s.cy, dz = pz - s.cz;
        s.cx += dx / s.hits; s.mx += dx * (px - s.cx);
        s.cy += dy / s.hits; s.my += dy * (py - s.cy);
        s.cz += dz / s.hits; s.mz += dz * (pz - s.cz);
    });
    per.forEach((a, key) => {
        if (a.n < BF) return;
        let h = onlineHits.get(key);
        if (!h) { h = new Uint8Array(N_CUR); onlineHits.set(key, h); }
        h[f] = 1;
    });
}
/* tier 判定（与生产 build_static_map 同序：strong 先行，supported 依赖 strong 邻域） */
const strongSet = new Set();
onlineWelford.forEach((s, key) => { if (s.hits >= thr_strong) strongSet.add(key); });
const onlineTierArr = new Map(); /* key → Uint8Array(165) : 0 none / 1 supported / 2 strong */
onlineWelford.forEach((s, key) => {
    const arr = new Uint8Array(N_CUR);
    const isStrong = s.hits >= thr_strong;
    let isSup = false;
    if (!isStrong && s.hits >= thr_sup) {
        const jit = Math.sqrt(Math.max(s.mx, s.my, s.mz) / s.hits);
        if (jit <= PL.PIPE.bg_jitter_max) {
            let nb = 0;
            const iz = key % BG_BASE; let k1 = (key - iz) / BG_BASE;
            const iy = k1 % BG_BASE; const ix = (k1 - iy) / BG_BASE - BG_OFF;
            const iyy = iy - BG_OFF, izz = iz - BG_OFF;
            for (let a = -1; a <= 1 && nb < PL.PIPE.bg_neighbor_min; a++)
                for (let b = -1; b <= 1 && nb < PL.PIPE.bg_neighbor_min; b++)
                    for (let c = -1; c <= 1 && nb < PL.PIPE.bg_neighbor_min; c++)
                        if ((a || b || c) && strongSet.has(bg_key_ijk(ix + a, iyy + b, izz + c))) nb++;
            if (nb >= PL.PIPE.bg_neighbor_min) isSup = true;
        }
    }
    if (isStrong) { const h = onlineHits.get(key); for (let f = 0; f < N_CUR; f++) if (h[f]) arr[f] = 2; }
    else if (isSup) { const h = onlineHits.get(key); for (let f = 0; f < N_CUR; f++) if (h[f]) arr[f] = 1; }
    onlineTierArr.set(key, arr);
});
/* 等价门：复刻 tier == 生产 build_static_map 逐键（0 mismatch） */
let tierMismatch = 0;
onlineMap.forEach((rec, key) => {
    const h = onlineHits.get(key);
    const nObs = h ? h.reduce((a, b) => a + b, 0) : 0;
    if (nObs !== rec.hits) { tierMismatch++; return; }
    const ta = onlineTierArr.get(key);
    const prodTierN = rec.tier === "strong" ? 2 : 1;
    let maxT = 0; for (let f = 0; f < N_CUR; f++) if (ta[f] > maxT) maxT = ta[f];
    if (maxT !== prodTierN) tierMismatch++;
});
onlineWelford.forEach((s, key) => {
    const inProd = onlineMap.has(key);
    const h = onlineHits.get(key); const nObs = h ? h.reduce((a, b) => a + b, 0) : 0;
    const isStrong = nObs >= thr_strong;
    const ta = onlineTierArr.get(key);
    let maxT = 0; if (ta) for (let f = 0; f < N_CUR; f++) if (ta[f] > maxT) maxT = ta[f];
    if ((maxT > 0) !== inProd) tierMismatch++;
});
log("[e1] online tier 复刻等价门 mismatch = " + tierMismatch);

/* =====================================================================
 * Pass 3 · current-visible bitmap（universe 体素逐帧在 223757 raw 点内落，经 frozen registration）
 * ===================================================================== */
log("[e1] pass3: current visible bitmap（R_icpᵀ·(p−t) 查询 ref 键）...");
const curVisible = new Array(UNIVERSE.length);
for (let i = 0; i < UNIVERSE.length; i++) curVisible[i] = new Uint8Array(N_CUR);
for (let f = 0; f < N_CUR; f++) {
    const frame = CUR.frames[f];
    for (let k = 0; k < frame.length; k += 4) {
        const z = frame[k + 2];
        if (z < GROUND || z > ZMAX) continue;
        const q = curPtToRef(frame[k], frame[k + 1], z);
        const idx = uniByKey.get(bg_key(q[0], q[1], q[2]));
        if (idx !== undefined) curVisible[idx][f] = 1;
    }
}

/* =====================================================================
 * Pass 4 · 逐 universe 体素：occ 级支持查询 + 距离诊断 + 标签
 * ===================================================================== */
log("[e1] pass4: per-voxel 支持/距离/标签 ...");
const NB = [[0, 0, 0]];
for (let a = -1; a <= 1; a++) for (let b = -1; b <= 1; b++) for (let c = -1; c <= 1; c++) if (a || b || c) NB.push([a, b, c]);

function stateInRef(p, fi, frameOnlineTier, frameHitArr) {
    /* p = ref lev 系查询点；生产 _bg_match 语速：±1 格 + 点到形心 < r；帧 fi 的支持判定要求该键在该帧 hits>0 */
    const ix = Math.floor(p[0] / VX), iy = Math.floor(p[1] / VX), iz = Math.floor(p[2] / VZ);
    let zrej = false;
    for (let a = -1; a <= 1; a++) for (let b = -1; b <= 1; b++) for (let c = -1; c <= 1; c++) {
        const key = bg_key_ijk(ix + a, iy + b, iz + c);
        const tier = frameOnlineTier.get(key);
        if (!tier) continue;
        const s = onlineWelford.get(key);
        if (!s) continue;
        const q = curPtToRef(s.cx, s.cy, s.cz); /* current（cur lev）→ ref lev，与查询点同系 */
        const dx = q[0] - p[0], dy = q[1] - p[1], dz = q[2] - p[2];
        if (dx * dx + dy * dy + dz * dz < R2) {
            const h = frameHitArr.get(key);
            if (h && h[fi]) return 2;
            return 1;
        }
        zrej = true;
    }
    return zrej ? 1 : 0;
}

function nearestInsideDist(p, frameOnlineTier) {
    const ix = Math.floor(p[0] / VX), iy = Math.floor(p[1] / VX), iz = Math.floor(p[2] / VZ);
    let best = null;
    for (let a = -1; a <= 1; a++) for (let b = -1; b <= 1; b++) for (let c = -1; c <= 1; c++) {
        const key = bg_key_ijk(ix + a, iy + b, iz + c);
        const tier = frameOnlineTier.get(key);
        if (!tier) continue;
        const s = onlineWelford.get(key);
        if (!s) continue;
        const q = curPtToRef(s.cx, s.cy, s.cz);
        const d = Math.hypot(q[0] - p[0], q[1] - p[1], q[2] - p[2]);
        if (best === null || d < best) best = d;
    }
    return best;
}
function nearestAnyDistCur(p, onlineArrList) {
    let best = null;
    for (const rec of onlineArrList) {
        const d = Math.hypot(rec.q[0] - p[0], rec.q[1] - p[1], rec.q[2] - p[2]);
        if (best === null || d < best) best = d;
    }
    return best;
}

const onlineArrList = [];
onlineWelford.forEach((s, key) => {
    if (!onlineMap.has(key)) return;
    onlineArrList.push({ key: key, q: curPtToRef(s.cx, s.cy, s.cz) });
});

function runBoundaries(bits, n) {
    let first = -1, last = -1, trans = 0, longestOn = 0, longestOff = 0, cur = 0;
    for (let f = 0; f < n; f++) {
        if (bits[f]) { if (first < 0) first = f; last = f; cur++; if (cur > longestOn) longestOn = cur; }
        else { if (f > 0 && bits[f - 1]) trans++; cur = 0; }
    }
    cur = 0;
    for (let f = 0; f < n; f++) {
        if (!bits[f]) { cur++; if (cur > longestOff) longestOff = cur; }
        else cur = 0;
    }
    return { first_seen: first, last_seen: last, transitions: trans, longest_on: longestOn, longest_off: longestOff };
}
function phaseOf(f) {
    for (const ph of SUBJECT_PHASES) if (f >= ph.from && f < ph.to) return ph.name;
    return "unknown";
}
function bitsToStr(bits, n) { let s = ""; for (let f = 0; f < n; f++) s += bits[f] ? "1" : "0"; return s; }

const UDP = []; /* 逐体素记录（universe order） */
for (let i = 0; i < UNIVERSE.length; i++) {
    const u = UNIVERSE[i];
    const refBits = refPresence[i];
    const refRB = runBoundaries(refBits, N_REF);
    const curVisBits = curVisible[i];
    const curVisRB = runBoundaries(curVisBits, N_CUR);
    const cur_vis_hits = curVisBits.reduce((a, b) => a + b, 0);

    /* ref 体素形心在 ref lev 系的距离诊断（±1 邻域 / 全场） */
    const d_v_inside = nearestInsideDist([u.x, u.y, u.z], onlineTierArr);
    const d_v_any = nearestAnyDistCur([u.x, u.y, u.z], onlineArrList);

    /* 覆盖判定（§7 STATIC/MOVABLE 的 conservativeness 前提） */
    let dgeo_cov;
    if (d_v_any === null) dgeo_cov = null;           /* ±整体不可信（近无 online 记录） */
    else if (d_v_any <= MATCH_R) dgeo_cov = "in";
    else if (d_v_any <= 2 * MATCH_R) dgeo_cov = "shell";
    else dgeo_cov = "far";
    const covered = dgeo_cov === "in" ? N_CUR : 0;

    /* 逐帧支持状态：0 缺席 / 1 不确定（有 tier 记录但帧 hits=0 或距离≠命中）/ 2 支持 */
    const supState = new Uint8Array(N_CUR);
    let supHits = 0, indecisive = 0, absent = 0, absentRunMax = 0, supRunMax = 0, curSupRun = 0;
    let transSupToAbsent = 0, transAbsentToSup = 0, prevSup = null;
    let curAbsRun = 0;
    for (let f = 0; f < N_CUR; f++) {
        const st = stateInRef([u.x, u.y, u.z], f, onlineTierArr, onlineHits);
        supState[f] = st;
        if (st === 2) {
            supHits++; curSupRun++; if (curSupRun > supRunMax) supRunMax = curSupRun;
            if (curAbsRun > 0) curAbsRun = 0;
            if (prevSup === 0) transAbsentToSup++;
            prevSup = 2;
        } else if (st === 1) {
            indecisive++; curAbsRun++; if (curAbsRun > absentRunMax) absentRunMax = curAbsRun;
            if (curSupRun > 0) curSupRun = 0;
            prevSup = 1;
        } else {
            absent++; curAbsRun++; if (curAbsRun > absentRunMax) absentRunMax = curAbsRun;
            if (curSupRun > 0) curSupRun = 0;
            if (prevSup === 2) transSupToAbsent++;
            prevSup = 0;
        }
    }
    const cur_occ_supported = supHits / N_CUR;

    /* 相位化转变分析 */
    const phasesPresent = { at_station: 0, departing: 0, away: 0, returned: 0 };
    const phasesCnt = { at_station: 0, departing: 0, away: 0, returned: 0 };
    for (let f = 0; f < N_CUR; f++) {
        const ph = phaseOf(f);
        if (phasesCnt[ph] === undefined) continue;
        phasesCnt[ph]++;
        if (supState[f] === 2) phasesPresent[ph]++;
    }
    const phaseSupFrac = {};
    for (const ph of SUBJECT_PHASES) {
        const n = ph.name;
        phaseSupFrac[n] = phasesCnt[n] ? round(phasesPresent[n] / phasesCnt[n], 4) : null;
    }

    /* ---- 标签（§7；covered 前提不满足 → UNRESOLVED） ---- */
    let label = "UNRESOLVED", rule = "";
    const visPersist = cur_vis_hits / N_CUR >= 0.90;
    if (covered === N_CUR) {
        const longestAbs = absentRunMax, longestSup = supRunMax;
        if (absentRunMax <= 3 && supHits >= N_CUR - 3) { label = "STATIC"; rule = "S1:no_absence_run"; }
        else {
            /* 明确持续转变：≥5 sup → ≥8 absent（或反向）；或可见但从不被支持 */
            const hasClearTrans = (transSupToAbsent + transAbsentToSup) >= 1 && supRunMax >= 5 && absentRunMax >= 8;
            if (hasClearTrans) { label = "MOVABLE"; rule = "M1:sustained_transition"; }
            else if (supHits === 0 && visPersist) { label = "MOVABLE"; rule = "M2:visible_never_supported"; }
            else { label = "UNRESOLVED"; rule = "U1:weak_temporal"; }
        }
    } else {
        label = "UNRESOLVED";
        rule = dgeo_cov === null ? "U0:no_online_nearby" : "U2:coverage_" + dgeo_cov;
    }

    /* 区域归属 */
    let region = "OTHER";
    const dxyStation = Math.hypot(u.x - STATION.x, u.y - STATION.y);
    if (dxyStation <= STATION.r && u.z >= STATION.zlo && u.z < STATION.zhi) region = "STATION_BLOCK";
    else if (dxyStation <= STATION.r && u.z < STATION.zhi) region = "STATION_ZONE";
    const dxyWd01 = Math.hypot(u.x - WD01.x, u.y - WD01.y);
    if (dxyWd01 <= WD01.r) region = "WD01";
    let wd02 = false;
    for (const rp of WD02_REPS) if (Math.hypot(u.x - rp.x, u.y - rp.y) <= WD02_R) { wd02 = true; break; }
    if (wd02) region = "WD02";

    UDP.push({
        idx: i, key: u.key, x: round(u.x, 4), y: round(u.y, 4), z: round(u.z, 4),
        occ: round(u.occ, 4), obs: u.obs,
        ref_first_seen: refRB.first_seen, ref_last_seen: refRB.last_seen,
        ref_transitions: refRB.transitions, ref_longest_on: refRB.longest_on, ref_longest_off: refRB.longest_off,
        cur_vis_hits: cur_vis_hits, cur_vis_occ: round(cur_vis_hits / N_CUR, 4),
        cur_sup_hits: supHits, cur_occ_supported: round(cur_occ_supported, 4),
        longest_sup_run: supRunMax, longest_absent_run: absentRunMax,
        sup_to_absent: transSupToAbsent, absent_to_sup: transAbsentToSup,
        phase_sup_frac: phaseSupFrac,
        d_v_inside: d_v_inside === null ? null : round(d_v_inside, 4),
        d_v_any: d_v_any === null ? null : round(d_v_any, 4),
        dgeo_cov: dgeo_cov, covered: covered,
        region: region, label: label, rule: rule,
        ref_present_bmp: bitsToStr(refBits, N_REF),
        cur_visible_bmp: bitsToStr(curVisBits, N_CUR),
        cur_supported_bmp: (function () { let s = ""; for (let f = 0; f < N_CUR; f++) s += supState[f] === 2 ? "1" : "0"; return s; })(),
    });
}

/* =====================================================================
 * 站点残块点的 reference 归因（f10/f30，既有点级窗口定义）
 * ===================================================================== */
log("[e1] station residual point 归因（f10/f30）...");
const WIN = STATION;
const stationPointRows = [];
for (const fFixed of [10, 30]) {
    const frame = CUR.frames[fFixed];
    const sh = (function () { /* 等价 residual（同 r7 G0 passport）：调 PL.extract_foreground 拿 fg 点身份 */
        const prod = PL.extract_foreground(PL.denoise(frame), onlineMap);
        return prod.fg_xyzi;
    })();
    const blockIdx = [];
    for (let k = 0; k < sh.length; k += 4) {
        const x = sh[k], y = sh[k + 1], z = sh[k + 2];
        if (Math.hypot(x - WIN.x, y - WIN.y) <= WIN.r && z >= WIN.zlo && z < WIN.zhi) blockIdx.push([x, y, z]);
    }
    for (const p of blockIdx) {
        const q = curPtToRef(p[0], p[1], p[2]);
        const cand = [];
        for (let i = 0; i < UDP.length; i++) {
            const d = Math.hypot(UDP[i].x - q[0], UDP[i].y - q[1], UDP[i].z - q[2]);
            if (d < 0.05) cand.push({ i: i, d: d });
        }
        cand.sort((a, b) => a.d - b.d);
        if (cand.length) {
            const v = UDP[cand[0].i];
            stationPointRows.push({ f: fFixed, d: round(cand[0].d, 4), label: v.label, region: v.region,
                cur_occ_supported: v.cur_occ_supported, longest_absent_run: v.longest_absent_run });
        } else {
            stationPointRows.push({ f: fFixed, d: null, label: "NO_REF_VOXEL", region: null, cur_occ_supported: null, longest_absent_run: null });
        }
    }
}
const stationPointTotal = stationPointRows.length;
const stationPointLbl = { STATIC: 0, MOVABLE: 0, UNRESOLVED: 0, NO_REF_VOXEL: 0 };
for (const r of stationPointRows) stationPointLbl[r.label === "NO_REF_VOXEL" ? "NO_REF_VOXEL" : r.label]++;

/* =====================================================================
 * 聚合 + 守恒 + digest
 * ===================================================================== */
const labelTotal = { STATIC: 0, MOVABLE: 0, UNRESOLVED: 0 };
for (const v of UDP) labelTotal[v.label]++;
const regionTable = {};
for (const rg of ["STATION_BLOCK", "STATION_ZONE", "WD01", "WD02", "OTHER"]) {
    const rows = UDP.filter(v => v.region === rg);
    const t = { total: rows.length, STATIC: 0, MOVABLE: 0, UNRESOLVED: 0,
                point_w: { STATIC: 0, MOVABLE: 0, UNRESOLVED: 0, n: 0 } };
    for (const v of rows) {
        t[v.label]++;
        const w = v.obs; /* voxel 点权 = 参考帧命中点数（pt-density 守恒口径） */
        t.point_w[v.label] += w; t.point_w.n += w;
    }
    regionTable[rg] = t;
}

const summaryCore = {
    ticket: "HR-W03 E-1 temporal stability / mobility audit",
    universe_voxels: UDP.length,
    ref_occ_min: OCC_MIN,
    match_radius: MATCH_R,
    voxel_xy: VX, voxel_z: VZ,
    icp_frozen: { eu: ICP_FROZEN_EU, t: T_ICP_FROZEN, source: "R3.2/11_r33 + r7 CHECK PASS（冻结，E-1 不重新估计）" },
    online_tier_replica_mismatch: tierMismatch,
    labels: labelTotal,
    label_fracs: {
        STATIC: round(labelTotal.STATIC / UDP.length, 4),
        MOVABLE: round(labelTotal.MOVABLE / UDP.length, 4),
        UNRESOLVED: round(labelTotal.UNRESOLVED / UDP.length, 4),
    },
    regions: {},
    station_block_points: { total: stationPointTotal, labels: stationPointLbl },
};
for (const rg of ["STATION_BLOCK", "STATION_ZONE", "WD01", "WD02", "OTHER"]) {
    const t = regionTable[rg];
    summaryCore.regions[rg] = {
        total: t.total,
        vx_STATIC: t.STATIC, vx_MOVABLE: t.MOVABLE, vx_UNRESOLVED: t.UNRESOLVED,
        vx_fracs: t.total ? { STATIC: round(t.STATIC / t.total, 4), MOVABLE: round(t.MOVABLE / t.total, 4), UNRESOLVED: round(t.UNRESOLVED / t.total, 4) } : null,
        pw_STATIC: t.point_w.STATIC, pw_MOVABLE: t.point_w.MOVABLE, pw_UNRESOLVED: t.point_w.UNRESOLVED, pw_total: t.point_w.n,
        pw_fracs: t.point_w.n ? { STATIC: round(t.point_w.STATIC / t.point_w.n, 4), MOVABLE: round(t.point_w.MOVABLE / t.point_w.n, 4), UNRESOLVED: round(t.point_w.UNRESOLVED / t.point_w.n, 4) } : null,
    };
}
const digest = sha256_buf(Buffer.from(JSON.stringify(summaryCore), "utf8"));

const movables = UDP.filter(v => v.label === "MOVABLE").map(v => ({
    key: v.key, x: v.x, y: v.y, z: v.z, region: v.region, occ: v.occ,
    cur_sup_hits: v.cur_sup_hits, longest_absent_run: v.longest_absent_run, rule: v.rule,
}));

fs.writeFileSync(path.join(OUTDIR, "04_voxel_results.json"), JSON.stringify({
    generated_utc: new Date().toISOString(),
    inputs: {
        "pc_apps/human_replay/human_pipe_lib.js": { raw: sha256_file(path.join(RP, "human_pipe_lib.js")), canonical: sha256_file_canon(path.join(RP, "human_pipe_lib.js")) },
        "pc_apps/human_replay/human_replay_lib.js": { raw: sha256_file(path.join(RP, "human_replay_lib.js")), canonical: sha256_file_canon(path.join(RP, "human_replay_lib.js")) },
        "captures/remote/cap_20261002_223757/meta.json": sha256_file(path.join(REPO, "captures", "remote", CUR_SID, "meta.json")),
        "captures/remote/cap_20261002_223757/points.bin": sha256_file(path.join(REPO, "captures", "remote", CUR_SID, "points.bin")),
        "captures/remote/cap_20261004_203349/meta.json": sha256_file(path.join(REPO, "captures", "remote", REF_SID, "meta.json")),
        "captures/remote/cap_20261004_203349/points.bin": sha256_file(path.join(REPO, "captures", "remote", REF_SID, "points.bin")),
    },
    transforms: {
        cur_tls_job: CUR.tf.job, cur_tls_transform_id: CUR.tf.transform_id, cur_tls_sha: sha256_file(CUR.tf.tf_path),
        ref_tls_job: REF.tf.job, ref_tls_transform_id: REF.tf.transform_id, ref_tls_sha: sha256_file(REF.tf.tf_path),
        icp_frozen: { eu: ICP_FROZEN_EU, t: T_ICP_FROZEN, R_flat: R_ICP_FROZEN.map(v => round(v, 6)),
                      source: "R3.2/11_r33 存档 + r7 复跑 CHECK PASS；E-1 不重新估计" },
    },
    summary: summaryCore,
    digest: digest,
    movable_voxels: movables,
    voxels: UDP,
}, null, 1));

fs.writeFileSync(path.join(OUTDIR, "05_station_analysis.json"), JSON.stringify({
    window: STATION,
    frames_probed: [10, 30],
    total_points: stationPointTotal,
    point_labels: stationPointLbl,
    point_fracs: stationPointTotal ? {
        STATIC: round(stationPointLbl.STATIC / stationPointTotal, 4),
        MOVABLE: round(stationPointLbl.MOVABLE / stationPointTotal, 4),
        UNRESOLVED: round(stationPointLbl.UNRESOLVED / stationPointTotal, 4),
        NO_REF_VOXEL: round(stationPointLbl.NO_REF_VOXEL / stationPointTotal, 4),
    } : null,
    voxel_summary: summaryCore.regions,
    points: stationPointRows,
}, null, 1));

fs.writeFileSync(path.join(OUTDIR, "06_run.log"), L.join("\n") + "\n");

console.log("[e1] DONE  universe=" + UDP.length + "  STATIC=" + labelTotal.STATIC + " MOVABLE=" + labelTotal.MOVABLE + " UNRESOLVED=" + labelTotal.UNRESOLVED);
console.log("[e1] icp frozen roll=" + round(ICP_FROZEN_EU_CHECK.roll, 4) + " pitch=" + round(ICP_FROZEN_EU_CHECK.pitch, 4) + " yaw=" + round(ICP_FROZEN_EU_CHECK.yaw, 4)
    + "  tier_mismatch=" + tierMismatch + "  digest=" + digest.slice(0, 16) + "…");
console.log("[e1] station points=" + stationPointTotal + "  " + JSON.stringify(stationPointLbl));

#!/usr/bin/env node
/* ============================================================================
 * W03-HR-R9 · Reference Coverage Attribution（SHADOW-ONLY / READ-ONLY）
 *
 * 唯一目标：判定 E-1 站点残块 1035 / 1875（55.2%）NO_REF_VOXEL 的丢失层——
 *   reference acquisition（raw 未观测）/ reference builder admission（observed 但被 gate 拒）/
 *   registration & spatial correspondence（5 cm 查询找不到）。
 *
 * 与 E-1 的关系：E-1（2026-10-06_hrw03_r8_e1，E-NOT-CONFIRMED）已冻结 mobility hypothesis；
 *   本轮不重开 temporal/mobility，只在同一冻结输入上把 NO_REF_VOXEL 的查询域从
 *   「universe(occ≥0.5) 5cm NN」扩到「全 candidate / 全 raw cell / 逐帧 raw 点（多档半径）」。
 *
 * 冻结项（除「归因查询域」外全部不变；见 00/01/02）：
 *   - registration = R3.2/r7 固定 ICP 解（roll 1.7476 / pitch -0.2818 / yaw -2.3924 /
 *     t [0.0182,0.031,0.0012]），q = R_icpᵀ·(p−t)；不重新估计 / sweep / 重对齐；
 *   - voxel 语义 key_bg 0.15/0.12；builder 语义 PL.build_reference_map / build_static_map；
 *   - 站点/控制区窗口；判定档位 ε ∈ {0.05,0.12,0.36}；SPATIAL 分档 ≤5..30cm。
 *
 * 禁止：任何 production 文件 / matcher / builder / bg_ref_occ_min / registration / ICP /
 *      voxel size / radius / online map / leveling / ROI / human detection 主链修改；
 *      不 commit；不写 evidence 目录以外文件。
 *
 * Taxonomy（02_attribution_design.md §3，先登记后跑）：C0..C7 互斥、优先级自上而下。
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
const E1DIR = path.resolve(HERE, "..", "2026-10-06_hrw03_r8_e1");

const OUTDIR = HERE;
const CUR_SID = "cap_20261002_223757";
const REF_SID = "cap_20261004_203349";
const OCC_MIN = PL.PIPE.bg_ref_occ_min;    /* 0.5（不改，只读） */
const VX = PL.PIPE.bg_voxel_xy, VZ = PL.PIPE.bg_voxel_z;
const GROUND = PL.PIPE.ground_keep_below_m, ZMAX = PL.PIPE.z_max_m;
/* 既有窗口（不重新发现 ROI） */
const STATION = { x: 1.45, y: 0.85, r: 0.60, zlo: 0.80, zhi: 1.30 };
const STATION_ZONE_ZHI = 1.30;
const WD01 = { x: 3.50, y: -0.76, r: 0.90 };
const WD02_REPS = [{ x: 10.75, y: 4.25 }, { x: 10.25, y: -1.75 }, { x: 10.50, y: 5.50 }];
const WD02_R = 1.50;
/* 查询档位（02 §1/§3/§4 冻结） */
const EPS_CLASS = 0.36;                                 /* C0/C1 判定测度 */
const EPS_LIST = [0.05, 0.12, 0.36];                    /* 支持位图档位 */
const SPATIAL_BINS = [0.05, 0.10, 0.15, 0.20, 0.30];    /* cumulative NN 分档 */

const L = [];
function log(s) { L.push(s); console.log(s); }
function round(v, d) { return v === null || v === undefined || !isFinite(v) ? null : +v.toFixed(d === undefined ? 4 : d); }
function sha256_buf(b) { return crypto.createHash("sha256").update(b).digest("hex"); }
function sha256_file(p) { return sha256_buf(fs.readFileSync(p)); }
function sha256_file_canon(p) {
    const b = fs.readFileSync(p);
    return sha256_buf(Buffer.from(b.toString("latin1").replace(/\r\n/g, "\n").replace(/\r/g, "\n"), "latin1"));
}

/* ---- 3×3 矩阵（与 E-1 03_e1_probe.py 同款，冻结） ---- */
const m3 = {
    t(A) { return [A[0], A[3], A[6], A[1], A[4], A[7], A[2], A[5], A[8]]; },
    apply(A, x, y, z) { return [A[0] * x + A[1] * y + A[2] * z, A[3] * x + A[4] * y + A[5] * z, A[6] * x + A[7] * y + A[8] * z]; },
};

/* ---- 固定 registration（与 E-1 完全同一份；不重新估计） ---- */
const ICP_FROZEN_EU = { roll_deg: 1.7476, pitch_deg: -0.2818, yaw_deg: -2.3924 };
const T_ICP_FROZEN = [0.0182, 0.031, 0.0012];
function r_of_euler(e) {
    const cr = Math.cos(e.roll_deg * Math.PI / 180), sr = Math.sin(e.roll_deg * Math.PI / 180);
    const cp = Math.cos(e.pitch_deg * Math.PI / 180), sp = Math.sin(e.pitch_deg * Math.PI / 180);
    const cy = Math.cos(e.yaw_deg * Math.PI / 180), sy = Math.sin(e.yaw_deg * Math.PI / 180);
    return [cy * cp, cy * sp * sr - sy * cr, cy * sp * cr + sy * sr,
            sy * cp, sy * sp * sr + cy * cr, sy * sp * cr - cy * sr,
            -sp, cp * sr, cp * cr];
}
const R_ICP_FROZEN = r_of_euler(ICP_FROZEN_EU);
const R_ICP_FROZEN_T = m3.t(R_ICP_FROZEN);

const BG_BASE = 8192, BG_OFF = 4096;
function bg_key_ijk(ix, iy, iz) { return ((ix + BG_OFF) * BG_BASE + (iy + BG_OFF)) * BG_BASE + (iz + BG_OFF); }
function bg_key(x, y, z) { return bg_key_ijk(Math.floor(x / VX), Math.floor(y / VX), Math.floor(z / VZ)); }
function bg_decode(key) { const iz = key % BG_BASE; let k1 = (key - iz) / BG_BASE; const iy = k1 % BG_BASE; return [(k1 - iy) / BG_BASE - BG_OFF, iy - BG_OFF, iz - BG_OFF]; }

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

log("[r9] loading reference " + REF_SID + " ...");
const REF = load_leveled_raw(REF_SID);
log("[r9] loading current  " + CUR_SID + " ...");
const CUR = load_leveled_raw(CUR_SID);
if (!CUR.tf || !REF.tf) { console.error("[r9] FATAL: missing tls transform"); process.exit(2); }
const N_CUR = CUR.frames.length, N_REF = REF.frames.length;
const REF_DENOISED = denoisedOf(REF.frames);
const CUR_DENOISED = denoisedOf(CUR.frames);

/* ---- reference builder（生产 PL.build_reference_map；只读复用） ---- */
const refMapObj = PL.build_reference_map(REF_DENOISED);
if (refMapObj.voxels.size !== 5286) { console.error("[r9] FATAL: ref voxels " + refMapObj.voxels.size + " != 5286"); process.exit(2); }
/* universe = occ>=0.5（E-1 同口径；与 reference_static_keys(ref,0.5) 完全同式） */
const UNIVERSE = [];
refMapObj.voxels.forEach((rec, key) => { if (rec.occ < OCC_MIN) return; UNIVERSE.push({ key: key, x: rec.x, y: rec.y, z: rec.z, occ: rec.occ, obs: rec.obs }); });
if (UNIVERSE.length !== 3707) { console.error("[r9] FATAL: universe " + UNIVERSE.length + " != 3707"); process.exit(2); }
/* ref 全 candidate（5286；不筛 occ） */
const refCandidate = [];
refMapObj.voxels.forEach((rec, key) => { refCandidate.push({ key: key, x: rec.x, y: rec.y, z: rec.z, occ: rec.occ, obs: rec.obs }); });

/* ---- online map（生产 PL.build_static_map；与 E-1/r7 等价门 1720 键） ---- */
const onlineMap = PL.build_static_map(CUR_DENOISED, { drop_ground: true });
if (onlineMap.size !== 1720) { console.error("[r9] FATAL: online map keys " + onlineMap.size + " != 1720"); process.exit(2); }
log("[r9] equivalence reuse gates: ref=5286 universe=3707 online=1720  PASS");

/* ---- ICP 冻结查询（与 E-1 同义） ---- */
function curPtToRef(x, y, z) { return m3.apply(R_ICP_FROZEN_T, x - T_ICP_FROZEN[0], y - T_ICP_FROZEN[1], z - T_ICP_FROZEN[2]); }

/* =====================================================================
 * 逐帧原始整数观测（hot-cell）——支持位图 / raw cell / occ 一致性自检的数据源
 * refOccByCell[key] = {obs:满足 hit_min=1 的帧数, pts:累计点数, rawPts:全部原始点数}
 * ===================================================================== */
log("[r9] pass0: per-frame raw integer cell stats ...");
const refOccByCell = new Map();
const refFrameCellSets = [];
for (let f = 0; f < N_REF; f++) {
    const frame = REF_DENOISED[f], per = new Map();
    for (let k = 0; k < frame.length; k += 4) {
        const z = frame[k + 2];
        if (z < GROUND || z > ZMAX) continue;
        const key = bg_key(frame[k], frame[k + 1], z);
        per.set(key, (per.get(key) || 0) + 1);
    }
    refFrameCellSets.push(new Set(per.keys()));
    per.forEach((n, key) => {
        let s = refOccByCell.get(key);
        if (!s) { s = { obs: 0, pts: 0, rawPts: 0 }; refOccByCell.set(key, s); }
        if (n >= 1) { s.obs++; s.pts += n; }
        s.rawPts += n;
    });
}
let curOccByCell = null; /* current per-frame 计数值对此处无用，仅 ref 需要 */

/* ---- 一致性自检 A：由原始整数位图重算 occ 必须 == build_reference_map 的 rec.obs（hit_min=1） ---- */
let occSelfCheckMismatch = 0;
refMapObj.voxels.forEach((rec, key) => {
    const s = refOccByCell.get(key);
    if (!s || s.obs !== rec.obs) occSelfCheckMismatch++;
});
refOccByCell.forEach((s, key) => { if (!refMapObj.voxels.has(key)) occSelfCheckMismatch++; });
if (occSelfCheckMismatch !== 0) { console.error("[r9] FATAL: occ self-check mismatch=" + occSelfCheckMismatch); process.exit(2); }
log("[r9] occ self-check recompute == build_reference_map.obs  PASS (mismatch=0)");

/* ---- rawCell 全集（union 102 帧，hit_min=1 口径 = candidate 键集） ---- */
const rawCellSet = new Set(refOccByCell.keys());

/* =====================================================================
 * 一致性自检 B：ref raw 点应几乎全部落进某个 candidate（only 量化边界可到邻格）
 * ===================================================================== */
let rawInsideCand = 0, rawOutsideCand = 0, rawWSKept = 0;
for (let f = 0; f < N_REF; f++) {
    const frame = REF_DENOISED[f];
    for (let k = 0; k < frame.length; k += 4) {
        const z = frame[k + 2];
        if (z < GROUND || z > ZMAX) continue;
        rawWSKept++;
        if (rawCellSet.has(bg_key(frame[k], frame[k + 1], z))) rawInsideCand++; else rawOutsideCand++;
    }
}
log("[r9] ref raw points in WS=" + rawWSKept + "  in rawCell=" + rawInsideCand + "  outside=" + rawOutsideCand);

/* =====================================================================
 * 支持位图 refFrameBits[ε][cellKey] = Uint8Array(102)，帧 f 在 cell 的 ε 3×3×3 邻域 ≥1 raw 点
 * ===================================================================== */
log("[r9] pass1: support bitmaps eps=" + EPS_LIST.join("/") + " ...");
const refFrameBits = {};
for (const EPS of EPS_LIST) {
    const n = Math.max(1, Math.ceil(EPS / VX));
    const nz = Math.max(1, Math.ceil(EPS / VZ));
    const map = new Map();
    for (let f = 0; f < N_REF; f++) {
        for (const key of refFrameCellSets[f]) {
            const [ix, iy, iz] = bg_decode(key);
            for (let a = -n; a <= n; a++) for (let b = -n; b <= n; b++) for (let c = -nz; c <= nz; c++) {
                const ck = bg_key_ijk(ix + a, iy + b, iz + c);
                let arr = map.get(ck);
                if (!arr) { arr = new Uint8Array(N_REF); map.set(ck, arr); }
                arr[f] = 1;
            }
        }
    }
    refFrameBits[EPS] = map;
}

/* ---- k×cell 空间 NN index（cell = 0.05），每 cell 一个 uniformgrid ---- */
const CELL = 0.05;
function buildPtsIndex() { const m = new Map(); return m; }
function idxInsert(map, x, y, z, tag) {
    const k = Math.floor(x / CELL) + "," + Math.floor(y / CELL) + "," + Math.floor(z / CELL);
    let a = map.get(k); if (!a) { a = []; map.set(k, a); }
    a.push({ x: x, y: y, z: z, tag: tag });
}
function nnWithin(map, x, y, z, maxR) {
    const n = Math.max(1, Math.ceil(maxR / CELL));
    const ix = Math.floor(x / CELL), iy = Math.floor(y / CELL), iz = Math.floor(z / CELL);
    let best = null, bestD2 = maxR * maxR;
    for (let a = -n; a <= n; a++) for (let b = -n; b <= n; b++) for (let c = -n; c <= n; c++) {
        const arr = map.get((ix + a) + "," + (iy + b) + "," + (iz + c));
        if (!arr) continue;
        for (const r of arr) {
            const dx = r.x - x, dy = r.y - y, dz = r.z - z, d2 = dx * dx + dy * dy + dz * dz;
            if (d2 < bestD2) { bestD2 = d2; best = { d: Math.sqrt(d2), tag: r.tag }; }
        }
    }
    return best;
}
/* universe / refCandidate / refRaw(union) 三个查询域索引 */
log("[r9] pass2: spatial NN indexes ...");
const idxUniverse = buildPtsIndex();
for (const u of UNIVERSE) idxInsert(idxUniverse, u.x, u.y, u.z, u);
const idxCand = buildPtsIndex();
for (const c of refCandidate) idxInsert(idxCand, c.x, c.y, c.z, c);
const idxRefRaw = buildPtsIndex();
for (let f = 0; f < N_REF; f++) {
    const frame = REF_DENOISED[f];
    for (let k = 0; k < frame.length; k += 4) {
        const z = frame[k + 2];
        if (z < GROUND || z > ZMAX) continue;
        idxInsert(idxRefRaw, frame[k], frame[k + 1], z, f);
    }
}

/* ---- rawCell / refCandidate 的「key 空间 3×3×3」NN（测 key 距离，供 d_cell/d_cand ε 判定） ---- */
function keySetNNWithin(set, q, eps) {
    const ix = Math.floor(q[0] / VX), iy = Math.floor(q[1] / VX), iz = Math.floor(q[2] / VZ);
    const n = Math.max(1, Math.ceil(eps / VX)), nz = Math.max(1, Math.ceil(eps / VZ));
    let bestD = null;
    for (let a = -n; a <= n; a++) for (let b = -n; b <= n; b++) for (let c = -nz; c <= nz; c++) {
        const key = bg_key_ijk(ix + a, iy + b, iz + c);
        if (!set.has(key)) continue;
        const [jx, jy, jz] = bg_decode(key);
        /* query→cell 最小欧氏距离（cell 为轴对齐盒） */
        const x0 = jx * VX, x1 = x0 + VX, y0 = jy * VX, y1 = y0 + VX, z0 = jz * VZ, z1 = z0 + VZ;
        const dx = q[0] < x0 ? x0 - q[0] : (q[0] > x1 ? q[0] - x1 : 0);
        const dy = q[1] < y0 ? y0 - q[1] : (q[1] > y1 ? q[1] - y1 : 0);
        const dz = q[2] < z0 ? z0 - q[2] : (q[2] > z1 ? q[2] - z1 : 0);
        const d = Math.hypot(dx, dy, dz);
        if (bestD === null || d < bestD) bestD = d;
    }
    return bestD;
}

/* =====================================================================
 * 站点残块点集（与 E-1 完全同式生成：f10/f30 + PL.extract_foreground 身份 + 站点窗口）
 * ===================================================================== */
log("[r9] pass3: station residual point set (f10/f30) ...");
const residualPoints = [];
for (const fFixed of [10, 30]) {
    const frame = CUR.frames[fFixed];
    const prod = PL.extract_foreground(PL.denoise(frame), onlineMap);
    const sh = prod.fg_xyzi;
    for (let k = 0; k < sh.length; k += 4) {
        const x = sh[k], y = sh[k + 1], z = sh[k + 2];
        if (Math.hypot(x - STATION.x, y - STATION.y) <= STATION.r && z >= STATION.zlo && z < STATION.zhi) {
            residualPoints.push({ f: fFixed, x: x, y: y, z: z, q: curPtToRef(x, y, z) });
        }
    }
}
if (residualPoints.length !== 1875) { console.error("[r9] FATAL: residual points " + residualPoints.length + " != 1875"); process.exit(2); }

/* ---- universe 5cm 归因（复刻 E-1 标签：NO_REF_VOXEL / 其它） ---- */
const stationLbl = { UNRESOLVED: 0, NO_REF_VOXEL: 0, OTHER: 0 };
const noRefPoints = [];
for (const p of residualPoints) {
    const hits = nnWithin(idxUniverse, p.q[0], p.q[1], p.q[2], 0.05);
    if (hits) stationLbl.UNRESOLVED++; else { stationLbl.NO_REF_VOXEL++; noRefPoints.push(p); }
}
if (stationLbl.UNRESOLVED !== 840 || stationLbl.NO_REF_VOXEL !== 1035) {
    console.error("[r9] FATAL: station label reuse mismatch " + JSON.stringify(stationLbl) + " != {UNRESOLVED:840,NO_REF_VOXEL:1035}");
    process.exit(2);
}
log("[r9] equivalence reuse: station residual 1875 → UNRESOLVED=840 NO_REF_VOXEL=1035  PASS");

/* ---- 与 E-1 站点残块点集 digest 复比对 ---- */
const e1Station = JSON.parse(fs.readFileSync(path.join(E1DIR, "05_station_analysis.json"), "utf8"));
const e1Pts = e1Station.points.map(r => [r.f, r.label]);
const r9Pts = [];
for (const p of residualPoints) {
    const hits = nnWithin(idxUniverse, p.q[0], p.q[1], p.q[2], 0.05);
    r9Pts.push([p.f, hits ? "UNRESOLVED" : "NO_REF_VOXEL"]);
}
const e1Digest = sha256_buf(Buffer.from(JSON.stringify(e1Pts), "utf8"));
const r9Digest = sha256_buf(Buffer.from(JSON.stringify(r9Pts), "utf8"));
log("[r9] station residual label-sequence digest: e1=" + e1Digest.slice(0, 16) + " r9=" + r9Digest.slice(0, 16));
if (e1Pts.length !== r9Pts.length) { console.error("[r9] FATAL: e1/r9 station point count mismatch"); process.exit(2); }

/* =====================================================================
 * 控制区残点 corpus（工单 §9 对照：同一 onlineMap/extract_foreground 链、同样 1875 之外的全 f10/f30 前景残点）
 * ===================================================================== */
function regionOfCur(x, y, z) {
    const dS = Math.hypot(x - STATION.x, y - STATION.y);
    if (dS <= STATION.r && z >= STATION.zlo && z < STATION.zhi) return "STATION_BLOCK";
    if (dS <= STATION.r && z < STATION_ZONE_ZHI) return "STATION_ZONE";
    if (Math.hypot(x - WD01.x, y - WD01.y) <= WD01.r) return "WD01";
    for (const rp of WD02_REPS) if (Math.hypot(x - rp.x, y - rp.y) <= WD02_R) return "WD02";
    return "OTHER";
}
const controlByRegion = { STATION_ZONE: [], WD01: [], WD02: [], OTHER: [] };
for (const fFixed of [10, 30]) {
    const frame = CUR.frames[fFixed];
    const prod = PL.extract_foreground(PL.denoise(frame), onlineMap);
    const sh = prod.fg_xyzi;
    for (let k = 0; k < sh.length; k += 4) {
        const x = sh[k], y = sh[k + 1], z = sh[k + 2];
        const rg = regionOfCur(x, y, z);
        if (rg === "STATION_BLOCK") continue;
        const q = curPtToRef(x, y, z);
        if (!nnWithin(idxUniverse, q[0], q[1], q[2], 0.05)) {
            if (controlByRegion[rg]) controlByRegion[rg].push({ f: fFixed, x: x, y: y, z: z, q: q });
        }
    }
}
for (const rg of ["STATION_ZONE", "WD01", "WD02", "OTHER"]) log("[r9] control NO_REF_VOXEL in " + rg + " = " + controlByRegion[rg].length);

/* =====================================================================
 * 核心：逐点 attribution
 * ===================================================================== */
function attribPoint(p) {
    const q = p.q;
    /* d_raw / min frame */
    const rawNN = nnWithin(idxRefRaw, q[0], q[1], q[2], 0.60);
    const d_raw = rawNN ? rawNN.d : null;
    const minFrame = rawNN ? rawNN.tag : -1;
    /* d_cand（universe 5cm 无 → 这里在全 candidate 找） */
    const candNN = nnWithin(idxCand, q[0], q[1], q[2], 0.60);
    const d_cand = candNN ? candNN.d : null;
    const bestOcc = candNN ? candNN.tag.occ : null;
    const bestKey = candNN ? candNN.tag.key : null;
    /* d_cell（ref 全 raw cell 的 key 空间 NN） */
    const d_cell = keySetNNWithin(rawCellSet, q, 0.60);
    /* 支持帧数 / occ / Focc */
    const ck = bg_key(q[0], q[1], q[2]);
    const support = {}, focc = {};
    for (const EPS of EPS_LIST) {
        const arr = refFrameBits[EPS].get(ck);
        let F = 0;
        if (arr) for (let f = 0; f < N_REF; f++) F += arr[f];
        support[EPS] = F; focc[EPS] = round(F / N_REF, 4);
    }
    /* closest-observed-cell occupancy（d_cell ≤ 0.36 时，最近被观测 cell 在 candidate 里的 occ） */
    let closeCellOcc = null;
    if (d_cell !== null && d_cell <= EPS_CLASS) {
        /* 找最近被观测 cell 的 key，取其 candidate occ */
        const ix = Math.floor(q[0] / VX), iy = Math.floor(q[1] / VX), iz = Math.floor(q[2] / VZ);
        const n = 3, nz = 3; let bo = null, bd = null;
        for (let a = -n; a <= n; a++) for (let b = -n; b <= n; b++) for (let c = -nz; c <= nz; c++) {
            const key = bg_key_ijk(ix + a, iy + b, iz + c);
            if (!rawCellSet.has(key)) continue;
            const [jx, jy, jz] = bg_decode(key);
            const x0 = jx * VX, x1 = x0 + VX, y0 = jy * VX, y1 = y0 + VX, z0 = jz * VZ, z1 = z0 + VZ;
            const dx = q[0] < x0 ? x0 - q[0] : (q[0] > x1 ? q[0] - x1 : 0);
            const dy = q[1] < y0 ? y0 - q[1] : (q[1] > y1 ? q[1] - y1 : 0);
            const dz = q[2] < z0 ? z0 - q[2] : (q[2] > z1 ? q[2] - z1 : 0);
            const d = Math.hypot(dx, dy, dz);
            if (bd === null || d < bd) { bd = d; const rec = refMapObj.voxels.get(key); bo = rec ? rec.occ : null; }
        }
        closeCellOcc = bo;
    }
    /* z gate 诊断 */
    const zGate = (q[2] < GROUND) ? "below_ground" : (q[2] > ZMAX ? "above_zmax" : "in_ws");
    return { f: p.f, d_raw: d_raw === null ? null : round(d_raw, 4), min_frame: minFrame,
             d_cand: d_cand === null ? null : round(d_cand, 4), best_occ: bestOcc === null ? null : round(bestOcc, 4),
             d_cell: d_cell === null ? null : round(d_cell, 4), close_cell_occ: closeCellOcc === null ? null : round(closeCellOcc, 4),
             F0_05: support[0.05], F0_12: support[0.12], Focc0_36: focc[0.36], zgate: zGate,
             _bestKey: bestKey, _ck: ck };
}

function classify(m) {
    if (m.Focc0_36 === 0) return "C0_NO_RAW_SUPPORT";
    if (m.d_cell !== null && m.d_cell <= EPS_CLASS && m.close_cell_occ !== null && m.close_cell_occ < OCC_MIN) return "C1_LOW_OCC_REJECT";
    if (m.d_cand !== null && m.d_cand <= EPS_CLASS && m.best_occ >= OCC_MIN && m.d_cand > 0.05) return "C2_OTHER_NEAR_CANDIDATE";
    if (m.d_cell !== null && m.d_cell <= EPS_CLASS && m.close_cell_occ !== null && m.close_cell_occ >= OCC_MIN) return "C3_OTHER_BUILDER_REJECT";
    if (m.d_raw === null) return "C6_FAR_OR_NO_CORRESPONDENCE";
    if (m.d_raw > 0.05 && m.d_raw <= 0.10) return "C4_OFFSET_5_10CM";
    if (m.d_raw > 0.10 && m.d_raw <= 0.30) return "C5_OFFSET_10_30CM";
    if (m.d_raw > 0.30) return "C6_FAR_OR_NO_CORRESPONDENCE";
    if (m.d_raw <= 0.05) return "C7_UNRESOLVED";
    return "C7_UNRESOLVED";
}
const CLASSES = ["C0_NO_RAW_SUPPORT", "C1_LOW_OCC_REJECT", "C2_OTHER_NEAR_CANDIDATE", "C3_OTHER_BUILDER_REJECT",
                 "C4_OFFSET_5_10CM", "C5_OFFSET_10_30CM", "C6_FAR_OR_NO_CORRESPONDENCE", "C7_UNRESOLVED"];

function attribCorpus(pts) {
    const rows = pts.map(p => { const m = attribPoint(p); m.cls = classify(m); return m; });
    const counts = {}; for (const c of CLASSES) counts[c] = 0;
    for (const r of rows) counts[r.cls]++;
    return { rows: rows, counts: counts, n: pts.length };
}

log("[r9] pass4: attribution over 1035 NO_REF_VOXEL ...");
const stationAttrib = attribCorpus(noRefPoints);

/* ---- unique current-voxel weighting（current lev 3D 前景 key 去重；obs weight=组内点数） ---- */
function uniqueVoxelAttrib(rows, pts) {
    const groups = new Map();
    for (let i = 0; i < pts.length; i++) {
        const p = pts[i];
        const k = bg_key(p.x, p.y, p.z);
        if (!groups.has(k)) groups.set(k, []);
        groups.get(k).push(i);
    }
    const vCount = {}; for (const c of CLASSES) vCount[c] = 0;
    const oCount = {}; for (const c of CLASSES) oCount[c] = 0;
    let obsTotal = 0;
    groups.forEach(idxs => {
        const cls = rows[idxs[0]].cls; /* 同 voxel 内分类一致（同 3D 量化） */
        vCount[cls]++;
        oCount[cls] += idxs.length; obsTotal += idxs.length;
    });
    return { n_voxel: groups.size, voxel_counts: vCount, obs_counts: oCount, obs_total: obsTotal };
}
const stationUV = uniqueVoxelAttrib(stationAttrib.rows, noRefPoints);

/* ---- C1 occ 直方图 + threshold-near 子带 ---- */
const occHist = { "0-0.1": 0, "0.1-0.2": 0, "0.2-0.3": 0, "0.3-0.4": 0, "0.4-0.45": 0, "0.45-0.5": 0 };
let c1ThresholdNear = 0;
for (const r of stationAttrib.rows) {
    if (r.cls !== "C1_LOW_OCC_REJECT") continue;
    const o = r.close_cell_occ;
    if (o < 0.1) occHist["0-0.1"]++; else if (o < 0.2) occHist["0.1-0.2"]++; else if (o < 0.3) occHist["0.2-0.3"]++;
    else if (o < 0.4) occHist["0.3-0.4"]++; else if (o < 0.45) occHist["0.4-0.45"]++; else occHist["0.45-0.5"]++;
    if (o >= 0.45 && o < 0.5) c1ThresholdNear++;
}

/* ---- SPATIAL_OFFSET cumulative NN（universe / refCandidate / refRaw 三域 × 三权重） ---- */
const DOMAINS = { universe: idxUniverse, refCandidate: idxCand, refRaw: idxRefRaw };
function cumNN(pts) {
    const out = {};
    for (const name of Object.keys(DOMAINS)) {
        const idx = DOMAINS[name];
        const cum = {}; for (const b of SPATIAL_BINS) cum[b] = 0; let gt30 = 0;
        for (const p of pts) {
            const hit = nnWithin(idx, p.q[0], p.q[1], p.q[2], 0.60);
            const d = hit ? hit.d : null;
            if (d === null) { gt30++; continue; }
            if (d <= 0.05) cum[0.05]++; else if (d <= 0.10) cum[0.10]++;
            else if (d <= 0.15) cum[0.15]++; else if (d <= 0.20) cum[0.20]++;
            else if (d <= 0.30) cum[0.30]++; else gt30++;
        }
        /* cumulative */
        const cumCum = {}; let acc = 0;
        for (const b of SPATIAL_BINS) { acc += cum[b]; cumCum[b] = acc; }
        out[name] = { bins: { "<=5": cum[0.05], "5-10": cum[0.10], "10-15": cum[0.15], "20-30_resume": cum[0.20], "20-30": cum[0.30], ">30_or_none": gt30 },
                      cumulative: { "<=5": cumCum[0.05], "<=10": cumCum[0.10], "<=15": cumCum[0.15], "<=20": cumCum[0.20], "<=30": cumCum[0.30], ">30_or_none": gt30 },
                      n: pts.length };
    }
    return out;
}
const spatialPt = cumNN(noRefPoints);
function uniqueVoxelPts() {
    const seen = new Set(), out = [];
    for (const p of noRefPoints) { const k = bg_key(p.x, p.y, p.z); if (!seen.has(k)) { seen.add(k); out.push(p); } }
    return out;
}
const uvPts = uniqueVoxelPts();
const spatialVx = cumNN(uvPts);
/* obs-weighted = 每个 unique voxel 按其组内点数重复 */
const obsPts = [];
{
    const groups = new Map();
    for (const p of noRefPoints) { const k = bg_key(p.x, p.y, p.z); if (!groups.has(k)) groups.set(k, p); }
    /* obs weighting ≡ point-weighted on noRefPoints（因为同 voxel 全同距离），直接用 point 结果 */
}
const spatialObs = spatialPt; /* 语义同 point（obs 加权 = 点级重复） */

/* =====================================================================
 * 控制区 attribution（对照）
 * ===================================================================== */
log("[r9] pass5: control region attribution ...");
const controlAttrib = {};
for (const rg of ["STATION_ZONE", "WD01", "WD02", "OTHER"]) {
    if (controlByRegion[rg].length === 0) { controlAttrib[rg] = null; continue; }
    const a = attribCorpus(controlByRegion[rg]);
    controlAttrib[rg] = { n: a.n, counts: a.counts,
        fracs: Object.fromEntries(CLASSES.map(c => [c, a.n ? round(a.counts[c] / a.n, 4) : null])) };
}

/* =====================================================================
 * 守恒 / digest / 输出
 * ===================================================================== */
const stCounts = stationAttrib.counts;
const stSum = CLASSES.reduce((a, c) => a + stCounts[c], 0);
const uvSum = CLASSES.reduce((a, c) => a + stationUV.voxel_counts[c], 0);
const uvObsSum = CLASSES.reduce((a, c) => a + stationUV.obs_counts[c], 0);
if (stSum !== 1035) { console.error("[r9] FATAL: point conservation " + stSum + " != 1035"); process.exit(2); }
if (uvSum !== stationUV.n_voxel) { console.error("[r9] FATAL: voxel conservation"); process.exit(2); }
if (uvObsSum !== 1035) { console.error("[r9] FATAL: obs conservation"); process.exit(2); }
log("[r9] conservation: point 1035 PASS / unique-voxel " + stationUV.n_voxel + " PASS / obs 1035 PASS");

const summaryCore = {
    ticket: "HR-W03 R9 reference coverage attribution",
    e1_digest_recheck: { e1_station_label_seq: e1Digest.slice(0, 16), r9_station_label_seq: r9Digest.slice(0, 16), equal: e1Digest === r9Digest, e1_summary_digest: e1Station && JSON.parse(fs.readFileSync(path.join(E1DIR, "04_voxel_results.json"), "utf8")).digest.slice(0, 16) },
    ref_voxels: refMapObj.voxels.size, universe_voxels: UNIVERSE.length, online_keys: onlineMap.size,
    occ_selfcheck_mismatch: occSelfCheckMismatch,
    ref_raw_in_ws: rawWSKept, ref_raw_in_rawcell: rawInsideCand, ref_raw_outside: rawOutsideCand,
    station_no_ref_voxel: 1035,
    station_point_counts: stCounts,
    station_point_fracs: Object.fromEntries(CLASSES.map(c => [c, round(stCounts[c] / 1035, 4)])),
    station_unique_voxel: { n: stationUV.n_voxel, counts: stationUV.voxel_counts, obs_counts: stationUV.obs_counts },
    c1_threshold_near_045_05: c1ThresholdNear,
    c1_occ_hist: occHist,
    regions: { STATION_BLOCK: { n: 1035, counts: stCounts } },
    controls: controlAttrib,
    eps_class: EPS_CLASS, spatial_bins: SPATIAL_BINS,
};
const digest = sha256_buf(Buffer.from(JSON.stringify(summaryCore), "utf8"));

const scrub = r => ({ f: r.f, cls: r.cls, d_raw: r.d_raw, min_frame: r.min_frame, d_cand: r.d_cand, best_occ: r.best_occ,
                      d_cell: r.d_cell, close_cell_occ: r.close_cell_occ, F0_05: r.F0_05, F0_12: r.F0_12, Focc0_36: r.Focc0_36, zgate: r.zgate });

fs.writeFileSync(path.join(OUTDIR, "04_raw_support_results.json"), JSON.stringify({
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
        icp_frozen: { eu: ICP_FROZEN_EU, t: T_ICP_FROZEN, R_flat: R_ICP_FROZEN.map(v => round(v, 6)), source: "R3.2/11_r33 存档 + r7 CHECK PASS（冻结，R9 不重新估计）" },
    },
    summary: summaryCore,
    digest: digest,
    points: stationAttrib.rows.map(scrub),
}, null, 1));
fs.writeFileSync(path.join(OUTDIR, "05_builder_attribution.json"), JSON.stringify({
    generated_utc: new Date().toISOString(),
    builder_gates: { voxel_xy: VX, voxel_z: VZ, ground: GROUND, zmax: ZMAX, ref_hit_min_pts: PL.PIPE.bg_ref_hit_min_pts, ref_occ_min: OCC_MIN,
                     tiers_in_reference_builder: "none", jitter_gate_in_reference_builder: "none (diagnostic only)", neighbor_gate_in_reference_builder: "none" },
    station_point_counts: stCounts,
    station_point_fracs: Object.fromEntries(CLASSES.map(c => [c, round(stCounts[c] / 1035, 4)])),
    station_unique_voxel: { n: stationUV.n_voxel, counts: stationUV.voxel_counts, fracs: Object.fromEntries(CLASSES.map(c => [c, round(stationUV.voxel_counts[c] / stationUV.n_voxel, 4)])) },
    c1_occ_hist: occHist, c1_threshold_near_045_05: c1ThresholdNear,
    controls: controlAttrib,
    digest: digest,
}, null, 1));
fs.writeFileSync(path.join(OUTDIR, "06_spatial_offset_analysis.json"), JSON.stringify({
    generated_utc: new Date().toISOString(),
    query_domains: ["universe", "refCandidate", "refRaw"],
    weightings: { point_weighted: "1035 逐点", voxel_weighted: "unique current-voxel " + uvPts.length, obs_weighted: "= point-weighted（同 voxel 同距离）" },
    point_weighted: spatialPt,
    voxel_weighted: spatialVx,
    obs_weighted: spatialObs,
    digest: digest,
}, null, 1));
fs.writeFileSync(path.join(OUTDIR, "06_run.log"), L.join("\n") + "\n");

console.log("[r9] DONE  station 1035 → " + CLASSES.map(c => c.split("_")[0] + "=" + stCounts[c]).join(" "));
console.log("[r9] digest=" + digest.slice(0, 16) + "  unique_voxel=" + stationUV.n_voxel + "  c1_near045=" + c1ThresholdNear);
for (const rg of ["STATION_ZONE", "WD01", "WD02", "OTHER"]) if (controlAttrib[rg]) console.log("[r9]   ctrl " + rg + " n=" + controlAttrib[rg].n + " " + JSON.stringify(controlAttrib[rg].fracs));

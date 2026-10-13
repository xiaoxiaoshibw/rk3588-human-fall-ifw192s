/* ============================================================================
 * W03-R3.6 预研探针（非交付物）：为条件 C 选型收集 registration 内部指标。
 * 只读输入；不评估 WD01/WD02 residual；不使用 matcher 输出反推 transform。
 * 运行：node _recon_c_probe.js
 * ========================================================================== */
"use strict";
const fs = require("fs");
const path = require("path");
const HERE = __dirname;
const REPO = path.resolve(HERE, "..", "..", "..", "..");
const RP = path.join(REPO, "pc_apps", "human_replay");
const RL = require(path.join(RP, "human_replay_lib.js"));
const PL = require(path.join(RP, "human_pipe_lib.js"));

const CUR_SID = "cap_20261002_223757";
const REF_SID = "cap_20261004_203349";
const VX = PL.PIPE.bg_voxel_xy, VZ = PL.PIPE.bg_voxel_z;

function log(s) { console.log(s); }

/* ---- 会话加载（console 同口径：TLS → denoise；与 r7 工具同源） ---- */
function resolve_transform(sid) {
    const LV = path.join(REPO, "captures", "leveled");
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
    const tf = resolve_transform(sid);
    const ded = frames.map(f => {
        const s = RL.strided_f32_copy(f32, f.start_pts, f.count, RL.STRIDE_F32);
        if (tf) apply_Rt(s, tf.R, tf.t);
        return PL.denoise(s);
    });
    return { frames: ded, tf: tf, slices: frames };
}

/* ---- 3×3 / 小角解（r7 同源） ---- */
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
function eulerFromR(R) {
    const pitch = Math.asin(Math.max(-1, Math.min(1, -R[6])));
    const roll = Math.atan2(R[7], R[8]);
    const yaw = Math.atan2(R[3], R[0]);
    return { roll: roll * 180 / Math.PI, pitch: pitch * 180 / Math.PI, yaw: yaw * 180 / Math.PI };
}
function quant(vals, q) { if (!vals.length) return null; const s = vals.slice().sort((a, b) => a - b); return +s[Math.min(s.length - 1, Math.floor(q * s.length))].toFixed(4); }

/* ---- 通用 trimmed ICP（cur→ref；多尺度；确定性） ---- */
function icpTrimmed(src, tgt, R0, t0, sched) {
    let R = R0.slice(), t = t0.slice();
    const tgtIdx = build_vox_index(tgt, 0.28);
    let P = src;
    const stats = [];
    for (const sc of sched) {
        for (let iter = 0; iter < sc.iters; iter++) {
            const pairs = [];
            for (const p of P) {
                const q = m3.apply(R, p.x, p.y, p.z);
                const hit = nn_query(tgtIdx, q[0] + t[0], q[1] + t[1], q[2] + t[2], sc.inlier);
                if (hit) pairs.push({ p: [q[0] + t[0], q[1] + t[1], q[2] + t[2]], q: [hit.rec.x, hit.rec.y, hit.rec.z], d: hit.d });
            }
            if (pairs.length < 20) { stats.push({ scale: sc.cell, iter: iter, pairs: pairs.length, stop: "pairs<20" }); break; }
            pairs.sort((a, b) => a.d - b.d);
            const keep = pairs.slice(0, Math.max(20, Math.floor(pairs.length * sc.keep)));
            const aEst = solveSmallAngle(keep).map(v => -v);
            const mup = [0, 0, 0], muq = [0, 0, 0];
            for (const pr of keep) { for (let i = 0; i < 3; i++) { mup[i] += pr.p[i]; muq[i] += pr.q[i]; } }
            for (let i = 0; i < 3; i++) { mup[i] /= keep.length; muq[i] /= keep.length; }
            const Rn = m3.rodrigues(aEst);
            const Rmup = m3.apply(Rn, mup[0], mup[1], mup[2]);
            const tNew = [muq[0] - Rmup[0], muq[1] - Rmup[1], muq[2] - Rmup[2]];
            R = m3.mul(Rn, R);
            const Rnt = m3.apply(Rn, t[0], t[1], t[2]);
            t = [Rnt[0] + tNew[0], Rnt[1] + tNew[1], Rnt[2] + tNew[2]];
            const rotDeg = Math.hypot(aEst[0], aEst[1], aEst[2]) * 180 / Math.PI;
            const moved = Math.hypot(tNew[0], tNew[1], tNew[2]);
            let rms = 0;
            for (const k of keep) { const q = m3.apply(Rn, k.p[0], k.p[1], k.p[2]); rms += (q[0] + tNew[0] - k.q[0]) ** 2 + (q[1] + tNew[1] - k.q[1]) ** 2 + (q[2] + tNew[2] - k.q[2]) ** 2; }
            rms = Math.sqrt(rms / keep.length);
            stats.push({ scale: sc.cell, iter: iter, pairs: pairs.length, keep: keep.length, rotDeg: +rotDeg.toFixed(5), tMove: +moved.toFixed(5), rms: +rms.toFixed(5) });
            if (rotDeg < 1e-4 && moved < 1e-4) { stats.push({ scale: sc.cell, converged: true }); break; }
        }
    }
    return { R: R, t: t, stats: stats };
}

/* ---- main ---- */
const t0 = Date.now();
log("[recon] loading sessions ...");
const REF = load_leveled_denoised(REF_SID), CUR = load_leveled_denoised(CUR_SID);
log("[recon] REF frames=" + REF.frames.length + " tf=" + REF.tf.job + "  CUR frames=" + CUR.frames.length + " tf=" + CUR.tf.job);
const onlineMap = PL.build_static_map(CUR.frames, { drop_ground: true });
const refMapObj = PL.build_reference_map(REF.frames);
let curStrong = 0, curSup = 0;
onlineMap.forEach(r => { if (r.tier === "strong") curStrong++; else curSup++; });
let refTot = 0, ref90 = 0, ref80 = 0;
refMapObj.voxels.forEach(r => { refTot++; if (r.occ >= 0.9) ref90++; if (r.occ >= 0.8) ref80++; });
log("[recon] onlineMap=" + onlineMap.size + " (strong " + curStrong + "/sup " + curSup + ")  refMap=" + refTot + " (occ>=0.9 " + ref90 + ", occ>=0.8 " + ref80 + ")");

/* 细静态点集：生产体素 static 集合内 -> cell 重分箱形心 */
function fineStatic(frames, staticSet, cell) {
    const m = new Map(), inv = 1 / cell;
    for (const fr of frames) {
        for (let k = 0; k < fr.length; k += 4) {
            const x = fr[k], y = fr[k + 1], z = fr[k + 2];
            const key = PL.key_bg(x, y, z);
            if (!staticSet.has(key)) continue;
            const kk = Math.floor(x * inv) + "," + Math.floor(y * inv) + "," + Math.floor(z * inv);
            let a = m.get(kk); if (!a) { a = { n: 0, sx: 0, sy: 0, sz: 0 }; m.set(kk, a); }
            a.n++; a.sx += x; a.sy += y; a.sz += z;
        }
    }
    const out = [];
    m.forEach(a => out.push({ x: a.sx / a.n, y: a.sy / a.n, z: a.sz / a.n, n: a.n }));
    return out;
}
const refSet = new Set(); refMapObj.voxels.forEach((r, key) => { if (r.occ >= 0.9) refSet.add(key); });
const curSet = new Set(); onlineMap.forEach((r, key) => { if (r.tier === "strong") curSet.add(key); });
for (const cell of [0.10, 0.06]) {
    const rf = fineStatic(REF.frames, refSet, cell), cf = fineStatic(CUR.frames, curSet, cell);
    log("[recon] cell " + cell + ": refFine=" + rf.length + "  curFine=" + cf.length);
    if (cell === 0.06) {
        /* 静止结构 XY 粗视图（0.75m bin）；字符 = 点数对数 */
        function ascii(pts, label) {
            let xmin = 1e9, xmax = -1e9, ymin = 1e9, ymax = -1e9;
            for (const p of pts) { if (p.x < xmin) xmin = p.x; if (p.x > xmax) xmax = p.x; if (p.y < ymin) ymin = p.y; if (p.y > ymax) ymax = p.y; }
            const B = 0.75, W = Math.ceil((xmax - xmin) / B) + 1, H = Math.ceil((ymax - ymin) / B) + 1;
            const g = new Array(W * H).fill(0);
            for (const p of pts) {
                const ix = Math.min(W - 1, Math.floor((p.x - xmin) / B)), iy = Math.min(H - 1, Math.floor((p.y - ymin) / B));
                g[iy * W + ix]++;
            }
            log("[recon] " + label + " x[" + xmin.toFixed(1) + "," + xmax.toFixed(1) + "] y[" + ymin.toFixed(1) + "," + ymax.toFixed(1) + "]  bin=" + B + "m  (top=y_max down)");
            const chars = " .:-=+*#%@";
            for (let iy = H - 1; iy >= 0; iy--) {
                let row = "";
                for (let ix = 0; ix < W; ix++) { const n = g[iy * W + ix]; row += n === 0 ? " " : chars[Math.min(9, 1 + Math.floor(Math.log2(n + 1)))]; }
                log("[recon] |" + row + "|");
            }
        }
        ascii(rf, "REF-fine (" + REF_SID + ")");
        ascii(cf, "CUR-fine (" + CUR_SID + ")");
    }
}

/* ---- ICP-B 复跑（r5/r7 同款；作为对照，不是最终 C） ---- */
const ref90recs = []; refMapObj.voxels.forEach((r, key) => { if (r.occ >= 0.9) ref90recs.push({ x: r.x, y: r.y, z: r.z }); });
const curStrongRecs = []; onlineMap.forEach(r => { if (r.tier === "strong") curStrongRecs.push({ x: r.x, y: r.y, z: r.z }); });
function icpB() { // ref->cur, 与 R3.2 同款：identity 初始、inlier 0.25、不裁剪
    let R = [1, 0, 0, 0, 1, 0, 0, 0, 1], t = [0, 0, 0];
    const tgt = curStrongRecs, tgtIdx = build_vox_index(tgt, 0.28);
    for (let iter = 0; iter < 50; iter++) {
        const pairs = [];
        for (const p of ref90recs) {
            const q = m3.apply(R, p.x, p.y, p.z);
            const hit = nn_query(tgtIdx, q[0] + t[0], q[1] + t[1], q[2] + t[2], 0.25);
            if (hit) pairs.push({ p: [q[0] + t[0], q[1] + t[1], q[2] + t[2]], q: [hit.rec.x, hit.rec.y, hit.rec.z] });
        }
        if (pairs.length < 20) break;
        const aEst = solveSmallAngle(pairs).map(v => -v);
        const mup = [0, 0, 0], muq = [0, 0, 0];
        for (const pr of pairs) { for (let i = 0; i < 3; i++) { mup[i] += pr.p[i]; muq[i] += pr.q[i]; } }
        for (let i = 0; i < 3; i++) { mup[i] /= pairs.length; muq[i] /= pairs.length; }
        const Rn = m3.rodrigues(aEst); const Rmup = m3.apply(Rn, mup[0], mup[1], mup[2]);
        const tNew = [muq[0] - Rmup[0], muq[1] - Rmup[1], muq[2] - Rmup[2]];
        R = m3.mul(Rn, R);
        const Rnt = m3.apply(Rn, t[0], t[1], t[2]);
        t = [Rnt[0] + tNew[0], Rnt[1] + tNew[1], Rnt[2] + tNew[2]];
        if (Math.hypot(aEst[0], aEst[1], aEst[2]) * 180 / Math.PI < 1e-3 && Math.hypot(tNew[0], tNew[1], tNew[2]) < 1e-4) break;
    }
    return { R, t };
}
const B = icpB(); // ref->cur
const euB = eulerFromR(B.R);
log("[recon] ICP-B ref->cur: euler=" + JSON.stringify({ roll: +euB.roll.toFixed(4), pitch: +euB.pitch.toFixed(4), yaw: +euB.yaw.toFixed(4) }) + " t=[" + B.t.map(v => +v.toFixed(4)).join(",") + "]");

/* tls-direct（cur->ref）R = (R_cur R_ref^T)^T */
const R_ref = REF.tf.R.flat ? REF.tf.R.flat() : REF.tf.R;
const R_cur = CUR.tf.R.flat ? CUR.tf.R.flat() : CUR.tf.R;
const R_direct = m3.mul(R_cur, m3.t(R_ref));
const R_tls = m3.t(R_direct);
log("[recon] tls-direct cur->ref: euler=" + JSON.stringify((() => { const e = eulerFromR(R_tls); return { roll: +e.roll.toFixed(4), pitch: +e.pitch.toFixed(4), yaw: +e.yaw.toFixed(4) }; })()));

/* ---- C 候选：细静态集 trimmed 多尺度 ICP（cur->ref）---- */
function runC(tag, R0, t0, rf, cf) {
    const sched = [
        { cell: 0.30, inlier: 0.40, keep: 0.7, iters: 30 },
        { cell: 0.20, inlier: 0.25, keep: 0.6, iters: 30 },
        { cell: 0.15, inlier: 0.15, keep: 0.5, iters: 30 },
        { cell: 0.10, inlier: 0.10, keep: 0.5, iters: 30 },
        { cell: 0.08, inlier: 0.07, keep: 0.5, iters: 30 },
    ];
    const r = icpTrimmed(cf, rf, R0, t0, sched);
    const eu = eulerFromR(r.R);
    // 收敛诊断：最后 3 条
    const tail = r.stats.slice(-3).map(s => s.rms !== undefined ? ("it rms=" + s.rms + " rot=" + s.rotDeg) : JSON.stringify(s));
    log("[recon] C(" + tag + ") cur->ref: euler=" + JSON.stringify({ roll: +eu.roll.toFixed(4), pitch: +eu.pitch.toFixed(4), yaw: +eu.yaw.toFixed(4) })
        + " t=[" + r.t.map(v => +v.toFixed(4)).join(",") + "]  last=" + tail.join(" | "));
    // holdout：src 对半（按索引奇偶），transform 拟合于全量，评估两半 NN 距离分布
    function nnStats(pts, idx) {
        const ds = [];
        for (const p of pts) { const q = m3.apply(r.R, p.x, p.y, p.z); const hit = nn_query(idx, q[0] + r.t[0], q[1] + r.t[1], q[2] + r.t[2], 0.30); if (hit) ds.push(hit.d); }
        return { n: pts.length, hit: ds.length, p50: quant(ds, 0.5), p90: quant(ds, 0.9), p99: quant(ds, 0.99) };
    }
    const rf06 = rf, cf06 = cf; // 传入即 0.06 集
    const idxR = build_vox_index(rf06, 0.28);
    const even = cf06.filter((_, i) => i % 2 === 0), odd = cf06.filter((_, i) => i % 2 === 1);
    log("[recon] C(" + tag + ") cur->ref holdout: even=" + JSON.stringify(nnStats(even, idxR)) + " odd=" + JSON.stringify(nnStats(odd, idxR)));
    // 反向：ref 点用逆变换测 cur
    const Rinv = m3.t(r.R), tinv = m3.apply(Rinv, -r.t[0], -r.t[1], -r.t[2]);
    const idxC = build_vox_index(cf06, 0.28);
    const dsRev = [];
    for (const p of rf06) { const q = m3.apply(Rinv, p.x, p.y, p.z); const hit = nn_query(idxC, q[0] + tinv[0], q[1] + tinv[1], q[2] + tinv[2], 0.30); if (hit) dsRev.push(hit.d); }
    log("[recon] C(" + tag + ") ref->cur reverse: n=" + rf06.length + " hit=" + dsRev.length + " p50=" + quant(dsRev, 0.5) + " p90=" + quant(dsRev, 0.9));
    return r;
}
const cf06 = fineStatic(CUR.frames, curSet, 0.06), rf06 = fineStatic(REF.frames, refSet, 0.06);
const C_tls = runC("init=tls", R_tls, [0, 0, 0], rf06, cf06);
const C_id = runC("init=identity", [1, 0, 0, 0, 1, 0, 0, 0, 1], [0, 0, 0], rf06, cf06);
const R_icp_c2r = m3.t(B.R), t_icp_c2r = m3.apply(R_icp_c2r, -B.t[0], -B.t[1], -B.t[2]);
const C_B = runC("init=B", R_icp_c2r, t_icp_c2r, rf06, cf06);

/* none/tls/B/C 下 curFine->refFine 的 NN 统计（对齐质量；非 residual 指标） */
function alignStats(tag, R, t, pts, idx) {
    const ds = [];
    for (const p of pts) { const q = m3.apply(R, p.x, p.y, p.z); const hit = nn_query(idx, q[0] + t[0], q[1] + t[1], q[2] + t[2], 0.30); if (hit) ds.push(hit.d); }
    log("[recon] align NN (" + tag + "): n=" + pts.length + " hit=" + ds.length + " p50=" + quant(ds, 0.5) + " p90=" + quant(ds, 0.9) + " p99=" + quant(ds, 0.99));
}
const idxRef = build_vox_index(rf06, 0.28);
const I3 = [1, 0, 0, 0, 1, 0, 0, 0, 1];
alignStats("none", I3, [0, 0, 0], cf06, idxRef);
alignStats("tls", R_tls, [0, 0, 0], cf06, idxRef);
alignStats("B", R_icp_c2r, t_icp_c2r, cf06, idxRef);
alignStats("C(tls)", C_tls.R, C_tls.t, cf06, idxRef);
log("[recon] done in " + ((Date.now() - t0) / 1000).toFixed(1) + "s");

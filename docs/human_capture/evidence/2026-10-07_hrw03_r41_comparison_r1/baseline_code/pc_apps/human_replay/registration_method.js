/* Offline only. Mathematical bodies copied unchanged from R3.6 10_r36_registration.js.
 * fixedICP accepts explicit initial conditions for diagnostic refits; default unchanged.
 * No production consumers. No parameter tuning. */
"use strict";
const PL = require("./human_pipe_lib.js");
function log(s) { if (process.env.REG_VERBOSE) console.log(s); }
function round(v, d=4) { return +v.toFixed(d); }
const ICP_SAVED = {roll:1.7476,pitch:-0.2818,yaw:-2.3924,t:[0.0182,0.031,0.0012]};
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

function fixedICP(onlineMap, refMapObj, R0 = I3, t0 = [0, 0, 0]) {
    const refRecs09 = [];
    refMapObj.voxels.forEach((rec, key) => { if (rec.occ >= 0.9) refRecs09.push({ x: rec.x, y: rec.y, z: rec.z, occ: rec.occ, key: key }); });
    const tgt = [];
    onlineMap.forEach((rec, key) => { if (rec.tier === "strong") tgt.push({ x: rec.x, y: rec.y, z: rec.z, key: key }); });
    const tgtIdx = build_vox_index(tgt, 0.28);
    let R_icp = R0.slice(), t_icp = t0.slice();
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
}


module.exports = {m3,jacobi_eig,eulerFromR,build_vox_index,nn_query,fineStatic,estimateNormals,ppICP,normalResiduals,PP_SCHED,I3,fixedICP};

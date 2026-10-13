/* ============================================================================
 * W03-R3.6 预研探针 v2（非交付物）：point-to-plane 精配准 + held-out 验证。
 * 只读；只使用高置信静态结构；不使用 matcher/residual 指标。
 * 运行：node _recon_c2_probe.js
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

function log(s) { console.log(s); }

/* ---- 加载（与 r7 同源） ---- */
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
    return { frames: ded, tf: tf };
}

/* ---- 线代 ---- */
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
function solve6(M, b) { // Gaussian elimination w/ partial pivoting; null if singular
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
function quant(vals, q) { if (!vals.length) return null; const s = vals.slice().sort((a, b) => a - b); return +s[Math.min(s.length - 1, Math.floor(q * s.length))].toFixed(4); }

/* ---- 索引/最近邻 ---- */
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

/* ---- 静态细集 + 法向 ---- */
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
    const n = Math.max(1, Math.ceil(radius / radius));
    const R2 = radius * radius;
    for (const p of pts) {
        const ix = Math.floor(p.x / radius), iy = Math.floor(p.y / radius), iz = Math.floor(p.z / radius);
        let nbr = [];
        for (let a = -1; a <= 1; a++) for (let b = -1; b <= 1; b++) for (let c = -1; c <= 1; c++) {
            const arr = idx.map.get((ix + a) + "," + (iy + b) + "," + (iz + c));
            if (!arr) continue;
            for (const r of arr) {
                const dx = r.x - p.x, dy = r.y - p.y, dz = r.z - p.z;
                if (dx * dx + dy * dy + dz * dz <= R2) nbr.push(r);
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

/* ---- point-to-plane ICP（src->tgt；tgt 需有法向） ---- */
function ppICP(src, tgtIdx, R0, t0, sched, tag) {
    let R = R0.slice(), t = t0.slice();
    const out = [];
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
                pairs.push({ X, Y, Z, r, q: hit.rec, d: hit.d });
            }
            if (pairs.length < 30) { out.push({ scale: sc.inlier, stop: "pairs<30", pairs: pairs.length }); break; }
            pairs.sort((a, b) => Math.abs(a.r) - Math.abs(b.r));
            const keep = pairs.slice(0, Math.max(30, Math.floor(pairs.length * sc.keep)));
            const M = [], b = [];
            for (let i = 0; i < 6; i++) { M.push(new Array(6).fill(0)); b.push(0); }
            for (const pr of keep) {
                const nx = pr.q.nx, ny = pr.q.ny, nz = pr.q.nz;
                // w = p x n
                const wx = pr.Y * nz - pr.Z * ny, wy = pr.Z * nx - pr.X * nz, wz = pr.X * ny - pr.Y * nx;
                const row = [wx, wy, wz, nx, ny, nz];
                const rhs = nx * (pr.q.x - pr.X) + ny * (pr.q.y - pr.Y) + nz * (pr.q.z - pr.Z);
                for (let i = 0; i < 6; i++) { for (let j = 0; j < 6; j++) M[i][j] += row[i] * row[j]; b[i] += row[i] * rhs; }
            }
            const x = solve6(M, b);
            if (!x) { out.push({ scale: sc.inlier, stop: "singular" }); break; }
            const a = [x[0], x[1], x[2]], dt = [x[3], x[4], x[5]];
            const Rn = m3.rodrigues(a);
            const Rmup = m3.apply(Rn, t[0], t[1], t[2]);
            t = [Rmup[0] + dt[0], Rmup[1] + dt[1], Rmup[2] + dt[2]];
            R = m3.mul(Rn, R);
            const rotDeg = Math.hypot(a[0], a[1], a[2]) * 180 / Math.PI;
            let med = keep.map(pr => Math.abs(pr.r)).sort((u, v) => u - v);
            out.push({ scale: sc.inlier, iter, pairs: pairs.length, kept: keep.length,
                       rotDeg: +rotDeg.toFixed(5), dtmm: +(Math.hypot(dt[0], dt[1], dt[2]) * 1000).toFixed(2),
                       medAbsRmm: +(med[Math.floor(med.length / 2)] * 1000).toFixed(2),
                       p90AbsRmm: +(med[Math.floor(med.length * 0.9)] * 1000).toFixed(2) });
            if (rotDeg < 5e-5 && Math.hypot(dt[0], dt[1], dt[2]) < 5e-5) { out.push({ scale: sc.inlier, converged: true }); break; }
        }
    }
    const eu = eulerFromR(R);
    const tail = out.slice(-2).map(s => JSON.stringify(s)).join(" | ");
    log("[c2] " + tag + ": euler=" + JSON.stringify({ roll: +eu.roll.toFixed(4), pitch: +eu.pitch.toFixed(4), yaw: +eu.yaw.toFixed(4) })
        + " t=[" + t.map(v => +v.toFixed(4)).join(",") + "]  tail=" + tail);
    return { R, t, stats: out };
}

/* ---- 评估：法向残差分布（held-out）---- */
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
function reportRes(tag, rs) {
    log("[c2] eval " + tag + ": n=" + rs.length + " |r| p50=" + quant(rs, 0.5) + " p90=" + quant(rs, 0.9) + " p99=" + quant(rs, 0.99));
}

/* ---- main ---- */
const t0 = Date.now();
log("[c2] loading ...");
const REF = load_leveled_denoised(REF_SID), CUR = load_leveled_denoised(CUR_SID);
const onlineMap = PL.build_static_map(CUR.frames, { drop_ground: true });
const refMapObj = PL.build_reference_map(REF.frames);
const refSet = new Set(); refMapObj.voxels.forEach((r, k) => { if (r.occ >= 0.9) refSet.add(k); });
const curSet = new Set(); onlineMap.forEach((r, k) => { if (r.tier === "strong") curSet.add(k); });
const cf = fineStatic(CUR.frames, curSet, 0.06);
const rf = fineStatic(REF.frames, refSet, 0.06);
log("[c2] fine: cur=" + cf.length + " ref=" + rf.length);
estimateNormals(rf, 0.10);
const nrmOk = rf.filter(p => p.nx !== null).length;
log("[c2] ref normals ok=" + nrmOk + "/" + rf.length);
const idxR = build_vox_index(rf, 0.10);

const R_ref = REF.tf.R.flat ? REF.tf.R.flat() : REF.tf.R;
const R_cur = CUR.tf.R.flat ? CUR.tf.R.flat() : CUR.tf.R;
const R_tls = m3.t(m3.mul(R_cur, m3.t(R_ref)));
const R_icpB = m3.t([1.7476 * 0 + 1, 0, 0, 0, 1, 0, 0, 0, 1]); // placeholder
/* B 的 cur->ref：由 euler ZYX(1.7476,-0.2818,-2.3924) 构造 ref->cur 再转置 */
function Rzyx(rollDeg, pitchDeg, yawDeg) {
    const r = rollDeg * Math.PI / 180, p = pitchDeg * Math.PI / 180, y = yawDeg * Math.PI / 180;
    const Rx = [1, 0, 0, 0, Math.cos(r), -Math.sin(r), 0, Math.sin(r), Math.cos(r)];
    const Ry = [Math.cos(p), 0, Math.sin(p), 0, 1, 0, -Math.sin(p), 0, Math.cos(p)];
    const Rz = [Math.cos(y), -Math.sin(y), 0, Math.sin(y), Math.cos(y), 0, 0, 0, 1];
    return m3.mul(Rz, m3.mul(Ry, Rx));
}
const R_B_ref2cur = Rzyx(1.7476, -0.2818, -2.3924);
const t_B_ref2cur = [0.0182, 0.031, 0.0012];
const R_B = m3.t(R_B_ref2cur);
const t_B = m3.apply(R_B, -t_B_ref2cur[0], -t_B_ref2cur[1], -t_B_ref2cur[2]);

/* 三个初值下的 p2plane 收敛 */
const sched = [
    { inlier: 0.30, keep: 0.70, iters: 25, stride: 5 },
    { inlier: 0.20, keep: 0.60, iters: 25, stride: 3 },
    { inlier: 0.15, keep: 0.50, iters: 25, stride: 2 },
    { inlier: 0.10, keep: 0.50, iters: 25, stride: 1 },
    { inlier: 0.08, keep: 0.60, iters: 25, stride: 1 },
];
const C_tls = ppICP(cf, idxR, R_tls, [0, 0, 0], sched, "pp init=tls");
const C_id = ppICP(cf, idxR, [1, 0, 0, 0, 1, 0, 0, 0, 1], [0, 0, 0], sched, "pp init=identity");
const C_B = ppICP(cf, idxR, R_B, t_B, sched, "pp init=B");

/* 评估（同一集合上对比 none/tls/B 与三个 pp 解） */
for (const [tag, R, t] of [["none", [1, 0, 0, 0, 1, 0, 0, 0, 1], [0, 0, 0]], ["tls", R_tls, [0, 0, 0]],
                           ["B", R_B, t_B], ["C(tls)", C_tls.R, C_tls.t], ["C(id)", C_id.R, C_id.t], ["C(B)", C_B.R, C_B.t]]) {
    reportRes(tag, normalResiduals(cf, idxR, R, t, 0.30));
}
/* held-out：even 拟合（自 C(tls) 与 C(B) 初值），odd 评估 */
const even = cf.filter((_, i) => i % 2 === 0), odd = cf.filter((_, i) => i % 2 === 1);
for (const [tag, R0, t0] of [["ppEven(init=tls)", R_tls, [0, 0, 0]], ["ppEven(init=B)", R_B, t_B]]) {
    const rr = ppICP(even, idxR, R0, t0, sched, tag + " fit-even");
    reportRes(tag + " eval-odd", normalResiduals(odd, idxR, rr.R, rr.t, 0.30));
}
log("[c2] done in " + ((Date.now() - t0) / 1000).toFixed(1) + "s");

/* _svd_probe.js — Jacobi 伪逆（3×3 对称 M）小角度解探针。真值 roll=2°、100 点、1mm 噪声。 */
"use strict";
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
function matmul(A, B) { /* 3×3 */
    const o = [[0, 0, 0], [0, 0, 0], [0, 0, 0]];
    for (let i = 0; i < 3; i++) for (let j = 0; j < 3; j++) for (let k = 0; k < 3; k++) o[i][j] += A[i][k] * B[k][j];
    return o;
}
function rodrigues(a) {
    const th = Math.hypot(a[0], a[1], a[2]);
    if (th < 1e-12) return [[1, 0, 0], [0, 1, 0], [0, 0, 1]];
    const x = a[0] / th, y = a[1] / th, z = a[2] / th, c = Math.cos(th), s = Math.sin(th), C = 1 - c;
    return [[c + x * x * C, x * y * C - z * s, x * z * C + y * s],
            [y * x * C + z * s, c + y * y * C, y * z * C - x * s],
            [z * x * C - y * s, z * y * C + x * s, c + z * z * C]];
}
function applyR(R, p) {
    return [R[0][0] * p[0] + R[0][1] * p[1] + R[0][2] * p[2],
            R[1][0] * p[0] + R[1][1] * p[1] + R[1][2] * p[2],
            R[2][0] * p[0] + R[2][1] * p[1] + R[2][2] * p[2]];
}
/* 真值 roll=2°、100 点、1mm 噪声；ref = Rz(roll)·cur（source=cur, target=ref） */
const roll = 2 * Math.PI / 180, c = Math.cos(roll), s = Math.sin(roll);
let seed = 42;
function rnd() { seed = (seed * 1103515245 + 12345) & 0x7fffffff; return seed / 0x7fffffff; }
const cur = [], ref = [];
for (let i = 0; i < 100; i++) {
    const x = 2 + 4 * rnd(), y = -3 + 6 * rnd(), z = 0.1 + 2 * rnd();
    const p = [x, y, z];
    const q = [c * x - s * y + 0.001 * (rnd() - 0.5), s * x + c * y + 0.001 * (rnd() - 0.5), z + 0.001 * (rnd() - 0.5)];
    cur.push(p); ref.push(q);
}
/* ICP 一轮 */
const pairs = cur.map((p, i) => ({ p: p, q: ref[i] }));
const aEst = solveSmallAngle(pairs);
/* 符号修正：方程 H·a = q-p 中 H = [p]× = -[a×p 方向]，解的 a_est = -a_true，取反 */
const a = aEst.map(v => -v);
const Rn = rodrigues(a);
const mup = [0, 0, 0], muq = [0, 0, 0];
for (const pr of pairs) for (let i = 0; i < 3; i++) { mup[i] += pr.p[i]; muq[i] += pr.q[i]; }
for (let i = 0; i < 3; i++) { mup[i] /= pairs.length; muq[i] /= pairs.length; }
const Rmup = applyR(Rn, mup);
const t = [muq[0] - Rmup[0], muq[1] - Rmup[1], muq[2] - Rmup[2]];
console.log("[probe] true roll(rad)=", roll.toFixed(6));
console.log("[probe] est |a|(rad)= ", Math.hypot(a[0], a[1], a[2]).toFixed(6));
console.log("[probe] est t =        ", t.map(v => +v.toFixed(5)));
console.log("[probe] Rn[1][0] (sin) =", Rn[1][0].toFixed(6), " 真值 sin(2°)=", s.toFixed(6));
const err = Math.abs(Math.hypot(a[0], a[1], a[2]) - roll);
console.log("[probe] |err|=", err.toExponential(2), err < 0.001 ? "PASS" : "FAIL");
process.exit(err < 0.001 ? 0 : 1);

"use strict";
/* 诊断 v2：桌子"救回点"与空场模板 233658 的精确对照（只读；口径同 visual r1）。
 * desk 集 = 帧 0 内、桌子圆柱内、在线命中且参考无支持（= 视图里链判非人的救回点，逐点核实其在线/参考条件）。
 * 对照：模板原始点（54 帧并集）与模板体素（occ≥0.5）：同区域有没有、差多少、r=0.12/0.15/0.20/0.25 命中率爬坡。
 * 另打印 0.1m 2D 密度图（模板观测 vs 桌子救回 vs 参考体素）以直观看形状/偏移。 */
const fs = require("fs"), path = require("path");
const ROOT = path.resolve(__dirname, "../../../..");
const PL = require(path.join(ROOT, "pc_apps/human_replay/human_pipe_lib.js"));
const R = require(path.join(ROOT, "pc_apps/human_replay/registration.js"));
const M = require(path.join(ROOT, "pc_apps/human_replay/registration_method.js"));

const REF = "cap_20261007_233658", REFJOB = "3c793d7bda0f4ced86b20ac8076e7b0e";
const S = { sid: "cap_20261007_215540", job: "21666bec7e7b44b2bdbbaa790bf4501b" };
const R2M = PL.PIPE.bg_match_radius ** 2;
function hit(map, x, y, z) {   /* 返回命中记录或 null（同 _bg_match_rec） */
    const ix = Math.floor(x / PL.PIPE.bg_voxel_xy), iy = Math.floor(y / PL.PIPE.bg_voxel_xy), iz = Math.floor(z / PL.PIPE.bg_voxel_z);
    for (let a = -1; a <= 1; a++) for (let b = -1; b <= 1; b++) for (let c = -1; c <= 1; c++) {
        const rec = map.get(((ix + a + 4096) * 8192 + (iy + b + 4096)) * 8192 + (iz + c + 4096));
        if (!rec) continue;
        const dx = rec.x - x, dy = rec.y - y, dz = rec.z - z;
        if (dx * dx + dy * dy + dz * dz < R2M) return rec;
    }
    return null;
}
function stats(dl) { dl = dl.slice().sort((a, b) => a - b); const g = p => dl[Math.min(dl.length - 1, Math.floor(dl.length * p))]; return { n: dl.length, min: dl[0], p10: g(.1), p50: g(.5), p90: g(.9), max: dl[dl.length - 1] }; }
const mm = v => (v === Infinity ? "∞" : (v * 1000).toFixed(0) + "mm");

const reg = JSON.parse(fs.readFileSync(path.join(ROOT, "captures/registration", S.sid + "__to__" + REF, "registration.json"), "utf8"));
const Rm = reg.rotation_row_major.flat(), t = reg.translation_m;
const raw = R.loadFrames(ROOT, S.sid, R.levelingBinding(ROOT, S.sid, S.job), false).frames;
const clouds = raw.map(buf => { const c = buf.slice(); for (let i = 0; i < c.length; i += 4) { const q = M.m3.apply(Rm, c[i], c[i + 1], c[i + 2]); for (let j = 0; j < 3; j++) c[i + j] = q[j] + t[j]; } return c; });
const clean = clouds.map(PL.denoise);
const online = PL.build_static_map(clean);
const refRaw = R.loadFrames(ROOT, REF, R.levelingBinding(ROOT, REF, REFJOB), false).frames;
const refkeys = new Map([...PL.build_reference_map(refRaw.map(PL.denoise)).voxels].filter(([, v]) => v.occ >= PL.PIPE.bg_ref_occ_min));

function rescuedIn(cx, cy, r, zlo, zhi, frame) {
    const out = []; const c0 = clouds[frame];
    for (let k = 0; k < c0.length; k += 4) {
        const x = c0[k], y = c0[k + 1], z = c0[k + 2];
        if (Math.hypot(x - cx, y - cy) > r || z < zlo || z > zhi) continue;
        const rr = x * x + y * y + z * z;
        if (!isFinite(rr) || rr < PL.PIPE.range_min_m ** 2 || rr > PL.PIPE.range_max_m ** 2) continue;
        const on = hit(online, x, y, z);
        if (!on) continue;                             /* 非在线持久 */
        if (hit(refkeys, x, y, z)) continue;           /* 参考直接命中（被参考删） */
        if (hit(refkeys, on.x, on.y, on.z)) continue;  /* 在线∧参考支持（被支持删） */
        out.push(x, y, z);
    }
    return out;
}

const DESK = { cx: 2.19, cy: 1.25, r: 0.7, zlo: 0.05, zhi: 1.45 };
const desk = rescuedIn(DESK.cx, DESK.cy, DESK.r, DESK.zlo, DESK.zhi, 0);
let dxs = 0, dys = 0, dzs = 0;
for (let k = 0; k < desk.length; k += 3) { dxs += desk[k]; dys += desk[k + 1]; dzs += desk[k + 2]; }
const dcy = { x: dxs / (desk.length / 3), y: dys / (desk.length / 3), z: dzs / (desk.length / 3) };
console.log(`桌子救回点（f0）：n=${desk.length / 3} 形心=(${dcy.x.toFixed(3)}, ${dcy.y.toFixed(3)}, ${dcy.z.toFixed(3)})`);

/* 模板原始点（54 帧并集）在桌子形心附近——宽窄两个圈都看 */
for (const r of [0.45, 0.9]) {
    let n = 0, sx = 0, sy = 0, sz = 0, zmin = Infinity, zmax = -Infinity;
    for (const c0 of refRaw) for (let k = 0; k < c0.length; k += 4) {
        const x = c0[k], y = c0[k + 1], z = c0[k + 2];
        if (Math.hypot(x - dcy.x, y - dcy.y) > r) continue;
        n++; sx += x; sy += y; sz += z; if (z < zmin) zmin = z; if (z > zmax) zmax = z;
    }
    console.log(`模板原始点 r=${r}m：n=${n}` + (n ? ` 形心=(${(sx / n).toFixed(3)}, ${(sy / n).toFixed(3)}, ${(sz / n).toFixed(3)}) z∈[${zmin.toFixed(2)},${zmax.toFixed(2)}]` : " —— 空"));
}

/* 桌子点 → 最近模板原始点距离（0.05m 网格，4 格壳=0.2m） */
const CELL = 0.05, INV = 1 / CELL, grid = new Map();
for (const c0 of refRaw) for (let k = 0; k < c0.length; k += 4) {
    const gx = Math.floor(c0[k] * INV), gy = Math.floor(c0[k + 1] * INV), gz = Math.floor(c0[k + 2] * INV);
    const key = gx + "," + gy + "," + gz; let a = grid.get(key); if (!a) grid.set(key, a = []); a.push(c0[k], c0[k + 1], c0[k + 2]);
}
const nn = [];
const step = 3 * Math.max(1, Math.floor(desk.length / 3 / 600));
for (let k = 0; k < desk.length; k += step) {
    const x = desk[k], y = desk[k + 1], z = desk[k + 2];
    const gx = Math.floor(x * INV), gy = Math.floor(y * INV), gz = Math.floor(z * INV);
    let best = Infinity;
    for (let s = 1; s <= 4 && best === Infinity; s++)
        for (let a = -s; a <= s; a++) for (let b = -s; b <= s; b++) for (let c = -s; c <= s; c++) {
            if (Math.max(Math.abs(a), Math.abs(b), Math.abs(c)) !== s) continue;
            const arr = grid.get((gx + a) + "," + (gy + b) + "," + (gz + c));
            if (!arr) continue;
            for (let q = 0; q < arr.length; q += 3) { const dx = arr[q] - x, dy = arr[q + 1] - y, dz = arr[q + 2] - z; const d = Math.sqrt(dx * dx + dy * dy + dz * dz); if (d < best) best = d; }
        }
    nn.push(best);
}
const s1 = stats(nn);
console.log(`桌子点→最近模板原始点：n=${s1.n} min=${mm(s1.min)} p10=${mm(s1.p10)} 中位=${mm(s1.p50)} p90=${mm(s1.p90)} max=${mm(s1.max)}`);
for (const rr of [0.12, 0.15, 0.20, 0.25, 0.30]) console.log(`  ≤${(rr * 100).toFixed(0)}cm 占比：${(100 * nn.filter(d => d <= rr).length / nn.length).toFixed(1)}%`);

/* 桌子点 → 最近参考体素（refkeys）距离：确认它们确实在体素 12cm 之外，并给爬坡 */
const arr2 = [...refkeys.values()];
const nn2 = [];
for (let k = 0; k < desk.length; k += step) {
    const x = desk[k], y = desk[k + 1], z = desk[k + 2];
    let best = Infinity;
    for (const v of arr2) { const ddx = v.x - x, ddy = v.y - y, ddz = v.z - z; const d2 = ddx * ddx + ddy * ddy + ddz * ddz; if (d2 < best) best = d2; }
    nn2.push(Math.sqrt(best));
}
const s2 = stats(nn2);
console.log(`桌子点→最近参考体素（形心）：min=${mm(s2.min)} p10=${mm(s2.p10)} 中位=${mm(s2.p50)} p90=${mm(s2.p90)}`);
for (const rr of [0.15, 0.20, 0.25, 0.30]) console.log(`  ≤${(rr * 100).toFixed(0)}cm 占比：${(100 * nn2.filter(d => d <= rr).length / nn2.length).toFixed(1)}%`);

/* 对照：人团（额外地确认模板确实没有"人"） */
const PER = { cx: 2.11, cy: -0.52, r: 0.55, zlo: 0.10, zhi: 2.30 };
const per = rescuedIn(PER.cx, PER.cy, PER.r, PER.zlo, PER.zhi, 0);
console.log(`\n对照人团（f0）：救回 n=${per.length / 3}；模板原始点在 0.9m 圈内 n=` + (() => { let n = 0; for (const c0 of refRaw) for (let k = 0; k < c0.length; k += 4) { if (Math.hypot(c0[k] - PER.cx, c0[k + 1] - PER.cy) <= 0.9) n++; } return n; })());

/* 0.1m 密度图：区域 x∈[1.6,2.9], y∈[0.4,2.1]，行=y 从大到小 */
function densityMap(points, label, pick) {
    const X0 = 1.6, X1 = 2.9, Y0 = 0.4, Y1 = 2.1, C = 0.1;
    const W = Math.round((X1 - X0) / C), H = Math.round((Y1 - Y0) / C);
    const grids = Array.from({ length: H }, () => new Float64Array(W));
    for (let k = 0; k < points.length; k += 3) {
        const gx = Math.floor((points[k] - X0) / C), gy = Math.floor((points[k + 1] - Y0) / C);
        if (gx >= 0 && gx < W && gy >= 0 && gy < H) grids[gy][gx]++;
    }
    console.log(`\n密度图 · ${label}（格=0.1m，数字=每格点数上限 9/G+#）`);
    for (let gy = H - 1; gy >= 0; gy--) {
        let row = "";
        for (let gx = 0; gx < W; gx++) { const v = grids[gy][gx]; row += v === 0 ? "." : v < 10 ? String(v) : v < 100 ? "+" : "#"; }
        console.log(row);
    }
    console.log("x 轴: 左=" + X0 + " 右=" + X1 + "；y 轴: 上=" + Y1.toFixed(1) + " 下=" + Y0);
}
const refPtsAll = [];
for (const c0 of refRaw) for (let k = 0; k < c0.length; k += 4) refPtsAll.push(c0[k], c0[k + 1], 0);
densityMap(refPtsAll, "模板 233658 原始点（54 帧并集）");
densityMap(desk, "桌子救回点（f0）");
const rvPts = []; for (const v of arr2) rvPts.push(v.x, v.y, 0);
densityMap(rvPts, "参考体素 occ≥0.5（形心投影）");
console.log("\ndone.");

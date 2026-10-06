/* CL-01 · 09_ab_shadow_impl.js — connectivity shadow 实现（A/B/C/D），production 零改动。
 *
 * A: XY 0.15 柱 + 4 邻（production 复刻；带与 PL.cluster_voxels 的等价性自检）
 * B: XY 0.15 柱 + 8 邻
 * C: XYZ 0.15³ cell + 26 邻（shadow 自有 key，绝不复用 key_bg/0.12z）
 * D: XY 0.15 柱 + 4 邻 + 垂直兼容门（Z occupancy bin，minGap ≤ G；G sweep {0,0.15,0.30,0.45}）
 *
 * 设计契约见 08_ab_plan.md。本文件可独立执行（node 09_ab_shadow_impl.js）做自检。
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

const VXY = PL.PIPE.voxel_m;          /* 0.15 */
const VZ_3D = 0.15;                   /* C 的显式 3D 粒度（isotropic；非 bg 的 0.12） */

/* ---------------- 会话加载（与第一阶段同源） ---------------- */
function resolveTransform(sid) {
    const LV = path.join(REPO, "captures", "leveled");
    let best = null;
    for (const job of fs.readdirSync(LV)) {
        const jd = path.join(LV, job);
        const tfPath = path.join(jd, "tls", "transform.json"), rpPath = path.join(jd, "report.json");
        if (!fs.existsSync(tfPath) || !fs.existsSync(rpPath)) continue;
        let report, tr;
        try { report = JSON.parse(fs.readFileSync(rpPath, "utf8")); tr = JSON.parse(fs.readFileSync(tfPath, "utf8")); } catch (e) { continue; }
        if (report.sid !== sid || report.recommended !== "tls" || !tr || !tr.R || !tr.t) continue;
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
function loadLeveledDenoised(sid) {
    const dir = path.join(REPO, "captures", "remote", sid);
    const meta = JSON.parse(fs.readFileSync(path.join(dir, "meta.json"), "utf8"));
    const raw = fs.readFileSync(path.join(dir, "points.bin"));
    const f32 = new Float32Array(raw.buffer, raw.byteOffset, raw.byteLength / 4);
    const frames = RL.frame_slice(meta), STRIDE = RL.STRIDE_F32, tf = resolveTransform(sid);
    const ded = frames.map(f => {
        const s = RL.strided_f32_copy(f32, f.start_pts, f.count, STRIDE);
        if (tf) apply_Rt(s, tf.R, tf.t);
        return PL.denoise(s);
    });
    return { dir: dir, meta: meta, frames: ded, tf: tf };
}
function sha256File(p) { return crypto.createHash("sha256").update(fs.readFileSync(p)).digest("hex"); }

/* ---------------- 邻接偏移 ---------------- */
const NB4 = [[1, 0], [-1, 0], [0, 1], [0, -1]];
const NB8 = [[1, 0], [-1, 0], [0, 1], [0, -1], [1, 1], [1, -1], [-1, 1], [-1, -1]];
const NB26 = (() => { const a = []; for (let dx = -1; dx <= 1; dx++) for (let dy = -1; dy <= 1; dy++) for (let dz = -1; dz <= 1; dz++) if (dx || dy || dz) a.push([dx, dy, dz]); return a; })();

/* ---------------- 通用图构建 + BFS（variant 唯一变量） ----------------
 * pts: Float32Array[x,y,z,i]
 * variant: "A" | "B" | "C" | "D"；G（米）仅 D 用。
 * 返回 { comps, pointComp, nNodes, keysOfComp ... }；comps 未过滤（raw），调用方按 min_voxels 过滤。
 */
function build(points, variant, G) {
    const nPts = points.length / 4;
    const keyIdx = new Map(), nodeKey = [], nodeN = [], nodeBins = [], nodeIX = [], nodeIY = [], nodeIZ = [];
    const pointNode = new Int32Array(nPts);
    for (let p = 0, i = 0; p < points.length; p += 4, i++) {
        const x = points[p], y = points[p + 1], z = points[p + 2];
        const ix = Math.floor(x / VXY), iy = Math.floor(y / VXY);
        const key = variant === "C" ? ix + "," + iy + "," + Math.floor(z / VZ_3D) : ix + "," + iy;
        let idx = keyIdx.get(key);
        if (idx === undefined) {
            idx = nodeKey.length;
            keyIdx.set(key, idx); nodeKey.push(key);
            nodeN.push(0); nodeBins.push(null); nodeIX.push(ix); nodeIY.push(iy); nodeIZ.push(variant === "C" ? Math.floor(z / VZ_3D) : 0);
        }
        nodeN[idx]++;
        if (variant === "D") {
            let b = nodeBins[idx]; if (!b) { b = nodeBins[idx] = new Set(); }
            b.add(Math.floor(z / VXY));
        }
        pointNode[i] = idx;
    }
    const n = nodeKey.length;

    const gatePass = (ai, bi) => {          /* D: minBinDiff*0.15 ≤ G */
        const ba = nodeBins[ai], bb = nodeBins[bi];
        let best = Infinity;
        ba.forEach(v => { bb.forEach(w => { const d = v > w ? v - w : w - v; if (d < best) best = d; }); });
        return best * VXY <= G + 1e-9;
    };
    const neighbors = (idx) => {
        const out = [];
        const ix = nodeIX[idx], iy = nodeIY[idx], iz = nodeIZ[idx];
        if (variant === "A" || variant === "D") {
            for (const [dx, dy] of NB4) {
                const j = keyIdx.get((ix + dx) + "," + (iy + dy));
                if (j !== undefined && (variant !== "D" || gatePass(idx, j))) out.push(j);
            }
        } else if (variant === "B") {
            for (const [dx, dy] of NB8) {
                const j = keyIdx.get((ix + dx) + "," + (iy + dy));
                if (j !== undefined) out.push(j);
            }
        } else {
            for (const [dx, dy, dz] of NB26) {
                const j = keyIdx.get((ix + dx) + "," + (iy + dy) + "," + (iz + dz));
                if (j !== undefined) out.push(j);
            }
        }
        return out;
    };

    const visited = new Uint8Array(n), compOf = new Int32Array(n).fill(-1);
    const comps = [];
    for (let s = 0; s < n; s++) {
        if (visited[s]) continue;
        const stack = [s]; visited[s] = 1;
        const nodes = [s];
        while (stack.length) {
            const cur = stack.pop();
            for (const j of neighbors(cur)) if (!visited[j]) { visited[j] = 1; stack.push(j); nodes.push(j); }
        }
        const ci = comps.length;
        for (const nd of nodes) compOf[nd] = ci;
        comps.push(nodes);
    }

    /* 点级 bbox/统计 */
    const comp = comps.map((nodes, ci) => ({ id: ci, nodes: nodes, n_points: 0, n_nodes: nodes.length,
        min_x: Infinity, max_x: -Infinity, min_y: Infinity, max_y: -Infinity, min_z: Infinity, max_z: -Infinity }));
    const pointComp = new Int32Array(nPts).fill(-1);
    for (let p = 0, i = 0; p < points.length; p += 4, i++) {
        const nd = pointNode[i], ci = compOf[nd], c = comp[ci];
        pointComp[i] = ci;
        c.n_points++;
        const x = points[p], y = points[p + 1], z = points[p + 2];
        if (x < c.min_x) c.min_x = x; if (x > c.max_x) c.max_x = x;
        if (y < c.min_y) c.min_y = y; if (y > c.max_y) c.max_y = y;
        if (z < c.min_z) c.min_z = z; if (z > c.max_z) c.max_z = z;
    }
    return { variant: variant, G: G === undefined ? null : G, comps: comp, pointComp: pointComp, pointNode: pointNode,
             nNodes: n, nodeKey: nodeKey, nodeN: nodeN, nodeBins: variant === "D" ? nodeBins : null,
             nodeIX: nodeIX, nodeIY: nodeIY, nodeIZ: nodeIZ };
}

/* raw 分量 → filtered（min_voxels 作用于节点数） */
const MIN_VOXELS = PL.PIPE.cluster_min_voxels;
function filtered(r) {
    const keep = r.comps.filter(c => c.nodes.length >= MIN_VOXELS);
    const discarded = r.comps.filter(c => c.nodes.length < MIN_VOXELS);
    return { comps: keep, discarded: discarded,
             discarded_points: discarded.reduce((a, c) => a + c.n_points, 0),
             raw_count: r.comps.length, filtered_count: keep.length, fragment_count: discarded.length };
}

/* ---- A 的 production 等价性自检 ---- */
function equivalenceCheck(points) {
    const r = build(points, "A");
    const mineFiltered = filtered(r);
    const vox = PL.voxelize(points);
    const prod = PL.cluster_voxels(vox);
    const sig = list => list.map(c => (c.keys ? c.keys.length : c.n_nodes) + ":" + (c.acc ? c.acc.n : c.n_points))
        .sort().join("|");
    const sameFiltered = mineFiltered.filtered_count === prod.length && sig(mineFiltered.comps) === sig(prod);
    /* raw 对照：临时 min=1（运行时，不改文件） */
    const saved = PL.PIPE.cluster_min_voxels; PL.PIPE.cluster_min_voxels = 1;
    let prodRaw;
    try { prodRaw = PL.cluster_voxels(vox); } finally { PL.PIPE.cluster_min_voxels = saved; }
    const sameRaw = r.comps.length === prodRaw.length && sig(r.comps) === sig(prodRaw);
    return { same: sameFiltered && sameRaw, filtered: sameFiltered, raw: sameRaw,
             mine: { raw: r.comps.length, filtered: mineFiltered.filtered_count },
             prod: { raw: prodRaw.length, filtered: prod.length } };
}

/* ---- 通用 cut/articulation（对某 component 的节点 key 集合） ---- */
function cutAnalysis(nodeKeyList, adjKeysFn, maxV) {
    const set = new Set(nodeKeyList);
    if (set.size > (maxV || 700)) return { skipped: true, V: set.size };
    let edges = 0, boundary = 0;
    const deg = new Map();
    set.forEach(k => {
        let d = 0; for (const nk of adjKeysFn(k)) if (set.has(nk)) d++;
        deg.set(k, d); edges += d; if (d < 4) boundary++;
    });
    const cuts = [];
    for (const k of set) {
        const rest = new Set(set); rest.delete(k);
        const seen = new Set(); const sizes = []; let comps = 0;
        for (const seed of rest) {
            if (seen.has(seed)) continue;
            comps++; const q = [seed]; seen.add(seed); let cnt = 0;
            while (q.length) {
                const cur = q.pop(); cnt++;
                for (const nk of adjKeysFn(cur)) if (rest.has(nk) && !seen.has(nk)) { seen.add(nk); q.push(nk); }
            }
            sizes.push(cnt);
            if (comps > 2) break;
        }
        if (comps > 1) { sizes.sort((a, b) => a - b);
            cuts.push({ key: k, deg: deg.get(k), parts: sizes, min_part_frac: +(sizes[0] / (set.size - 1)).toFixed(4) }); }
    }
    return { skipped: false, V: set.size, E: edges / 2, boundary: boundary,
             cut_count: cuts.length, bridge_fraction: +(cuts.length / set.size).toFixed(4), cuts: cuts };
}

/* ---- 跨“节点标记”的边统计（articulation/contact 辅助；edge 只计一次） ---- */
function crossEdges(r, nodeFlag) {
    const variant = r.variant, G = r.G;
    const keyIdx = new Map();
    for (let i = 0; i < r.nodeKey.length; i++) keyIdx.set(r.nodeKey[i], i);
    const gate = (ai, bi) => {
        const ba = r.nodeBins[ai], bb = r.nodeBins[bi];
        let best = Infinity;
        ba.forEach(v => { bb.forEach(w => { const d = v > w ? v - w : w - v; if (d < best) best = d; }); });
        return best * VXY <= G + 1e-9;
    };
    let edges = 0, cross = 0;
    const seen = new Set();
    for (let i = 0; i < r.nodeKey.length; i++) {
        const ix = r.nodeIX[i], iy = r.nodeIY[i], iz = r.nodeIZ[i];
        const offs = variant === "C" ? NB26 : variant === "B" ? NB8 : NB4;
        for (const [dx, dy, dz] of offs) {
            const key = variant === "C" ? (ix + dx) + "," + (iy + dy) + "," + (iz + (dz || 0)) : (ix + dx) + "," + (iy + dy);
            const j = keyIdx.get(key);
            if (j === undefined) continue;
            const a = i < j ? i : j, b = i < j ? j : i;
            const h = a + "_" + b;
            if (seen.has(h)) continue;
            seen.add(h);
            if (variant === "D" && !gate(a, b)) continue;
            edges++;
            if (nodeFlag[a] !== nodeFlag[b]) cross++;
        }
    }
    return { edges: edges, cross: cross };
}

/* ================== 自检（synthetic micro cases） ================== */
function cellPts(ix, iy, z0, z1, n, seed) {
    let a = seed >>> 0;
    const R = () => { a = (a + 0x6D2B79F5) | 0; let z = Math.imul(a ^ (a >>> 15), 1 | a);
        z = (z + Math.imul(z ^ (z >>> 7), 61 | z)) ^ z; return ((z ^ (z >>> 14)) >>> 0) / 4294967296; };
    const cx = (ix + 0.5) * VXY, cy = (iy + 0.5) * VXY, o = new Float32Array(n * 4);
    for (let i = 0; i < n; i++) { o[i * 4] = cx + (R() - 0.5) * 0.10; o[i * 4 + 1] = cy + (R() - 0.5) * 0.10;
        o[i * 4 + 2] = z0 + (z1 - z0) * R(); o[i * 4 + 3] = 80; }
    return o;
}
function concatBufs() { let t = 0; for (const b of arguments) t += b.length; const o = new Float32Array(t); let off = 0; for (const b of arguments) { o.set(b, off); off += b.length; } return o; }

if (require.main === module) {
    let pass = 0, fail = 0;
    const t = (name, cond, detail) => { if (cond) { pass++; console.log("ok  " + name + (detail ? "  [" + detail + "]" : "")); }
        else { fail++; console.log("FAIL " + name + "  [" + detail + "]"); } };
    /* A 等价性：真实小场景 + 合成场景 */
    const scenes = {
        twoCols: concatBufs(cellPts(0, 0, 0.9, 1.2, 10, 3), cellPts(1, 0, 0.9, 1.2, 10, 4)),
        zFar: concatBufs(cellPts(10, 10, 0.3, 0.5, 20, 1), cellPts(10, 10, 1.8, 2.0, 20, 2)),
        bridge: concatBufs(cellPts(0, 0, 0.3, 1.8, 40, 7), cellPts(2, 0, 0.3, 1.8, 40, 8), cellPts(1, 0, 0.15, 0.25, 3, 9)),
        diag: concatBufs(cellPts(0, 0, 0.9, 1.2, 10, 60), cellPts(1, 1, 0.9, 1.2, 10, 61)),
    };
    for (const [nm, pts] of Object.entries(scenes)) {
        const eq = equivalenceCheck(pts);
        t("A 等价 production [" + nm + "]", eq.same, JSON.stringify(eq));
    }
    /* 变体语义快照 */
    const c = (pts, v, G) => build(pts, v, G).comps.length;
    const zFar = scenes.zFar, two = scenes.twoCols, br = scenes.bridge, dg = scenes.diag;
    t("Case A 同柱异 Z: A=1, C=2, D=1", c(zFar, "A") === 1 && c(zFar, "C") === 2 && c(zFar, "D", 0.30) === 1,
        "A=" + c(zFar, "A") + " C=" + c(zFar, "C") + " D=" + c(zFar, "D", 0.30));
    t("Case B 相邻+Z 重叠: A=B=C=D=1", c(two, "A") === 1 && c(two, "B") === 1 && c(two, "C") === 1 && c(two, "D", 0.30) === 1,
        [c(two, "A"), c(two, "B"), c(two, "C"), c(two, "D", 0.30)].join(","));
    t("Case D bridge: A=1；D-G0 断桥=3（桥自身成 1 节点）；D-G0.15 保桥=1",
        c(br, "A") === 1 && c(br, "D", 0) === 3 && c(br, "D", 0.15) === 1,
        "A=" + c(br, "A") + " D0=" + c(br, "D", 0) + " D15=" + c(br, "D", 0.15));
    t("Case G 对角: A=2, B=1, C=1, D=2",
        c(dg, "A") === 2 && c(dg, "B") === 1 && c(dg, "C") === 1 && c(dg, "D", 0.30) === 2,
        [c(dg, "A"), c(dg, "B"), c(dg, "C"), c(dg, "D", 0.30)].join(","));
    console.log("\n" + pass + " passed, " + fail + " failed");
    process.exit(fail ? 1 : 0);
}

module.exports = {
    PL, RL,
    VXY, VZ_3D, MIN_VOXELS, NB4, NB8, NB26,
    resolveTransform, apply_Rt, loadLeveledDenoised, sha256File,
    build, filtered, equivalenceCheck, cutAnalysis, crossEdges,
    cellPts, concatBufs,
};

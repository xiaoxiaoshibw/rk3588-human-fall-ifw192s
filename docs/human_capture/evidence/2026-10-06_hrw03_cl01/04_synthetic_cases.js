/* CL-01 · 04_synthetic_cases.js — foreground clustering baseline semantics 合成审计
 *
 * 目的（只读）：用最小合成场景证明当前 production `cluster_voxels` 的 connectivity 语义：
 *   - voxel key 仅 X/Y（0.15m 柱）；Z 不参与 key、不参与连边
 *   - 邻接 = XY 4 邻（von Neumann），非 8/26
 *   - 无 radius 邻接、无形态学、无小簇合并、无 post-merge
 *   - 桥接（单低点/单 cell）如何把两个结构并成一个 component
 *
 * 不实现任何变体（B/C/D 在只读审计完成后才做）。只调用 production 函数：
 *   PL.voxelize / PL.key_vox / PL.cluster_voxels（PIPE.cluster_min_voxels 运行时临时改 1 以看原始分量，
 *   不改文件；恢复后对照 production 过滤）。
 *
 * 用法: node 04_synthetic_cases.js   → 04_synthetic_cases.log（stdout 即日志）
 */
"use strict";
const path = require("path");
const fs = require("fs");
const RP = path.resolve(__dirname, "..", "..", "..", "..", "pc_apps", "human_replay");
const PL = require(path.join(RP, "human_pipe_lib.js"));

const V = PL.PIPE.voxel_m;   /* 0.15 */
let passed = 0, failed = 0;
const L = [];
function log(s) { L.push(s); console.log(s); }
function check(name, cond, detail) {
    if (cond) { passed++; log("  PASS  " + name + (detail ? "  [" + detail + "]" : "")); }
    else { failed++; log("  FAIL  " + name + (detail ? "  [" + detail + "]" : "")); }
}

/* ---- 点构造：XY cell (ix,iy) 内、z 区间 [z0,z1] 的 n 个点（确定性伪随机） ---- */
function prng(seed) {
    let a = seed >>> 0;
    return () => { a = (a + 0x6D2B79F5) | 0; let z = Math.imul(a ^ (a >>> 15), 1 | a);
        z = (z + Math.imul(z ^ (z >>> 7), 61 | z)) ^ z; return ((z ^ (z >>> 14)) >>> 0) / 4294967296; };
}
function colPts(ix, iy, z0, z1, n, seed) {
    const R = prng(seed === undefined ? (ix * 131 + iy * 17 + 7) : seed);
    const cx = (ix + 0.5) * V, cy = (iy + 0.5) * V, o = new Float32Array(n * 4);
    for (let i = 0; i < n; i++) {
        o[i * 4] = cx + (R() - 0.5) * 0.10;
        o[i * 4 + 1] = cy + (R() - 0.5) * 0.10;
        o[i * 4 + 2] = z0 + (z1 - z0) * R();
        o[i * 4 + 3] = 80;
    }
    return o;
}
function concat() {
    let total = 0; for (const b of arguments) total += b.length;
    const out = new Float32Array(total); let off = 0;
    for (const b of arguments) { out.set(b, off); off += b.length; }
    return out;
}

/* ---- 原始连通分量（临时把 min_voxels 降到 1，运行时共存，不动文件） ---- */
function rawComponents(vox) {
    const saved = PL.PIPE.cluster_min_voxels;
    PL.PIPE.cluster_min_voxels = 1;
    try { return PL.cluster_voxels(vox); } finally { PL.PIPE.cluster_min_voxels = saved; }
}
function cBrief(c) {
    const a = c.acc;
    return { vox: c.keys.length, pts: a.n, zmin: +a.zmin.toFixed(2), zmax: +a.zmax.toFixed(2) };
}
function summarize(comps) { return JSON.stringify(comps.map(cBrief)); }

/* ---- 4 邻 degree（对某 cell 在 voxel 图内） ---- */
function degree4(vox, k) {
    const ij = k.split(","), ix = +ij[0], iy = +ij[1];
    return [((ix - 1) + "," + iy), ((ix + 1) + "," + iy), (ix + "," + (iy - 1)), (ix + "," + (iy + 1))]
        .filter(nk => vox.has(nk)).length;
}
/* ---- removal probe：删掉指定 cell 的点后重新聚类 ---- */
function removeCellsAndCluster(pts, cells) {
    const drop = new Set(cells);
    const out = [];
    for (let i = 0; i < pts.length; i += 4) {
        if (drop.has(PL.key_vox(pts[i], pts[i + 1]))) continue;
        out.push(pts[i], pts[i + 1], pts[i + 2], pts[i + 3]);
    }
    return rawComponents(PL.voxelize(new Float32Array(out)));
}

log("== CL-01 synthetic micro-cases（baseline production semantics） ==");
log("voxel_m=" + V + "  cluster_min_voxels(prod)=" + PL.PIPE.cluster_min_voxels
    + "  key_vox 仅 XY；cluster_voxels XY 4 邻");
log("");

/* ---------------- Case A：XY 相同 / Z 相差明显 ---------------- */
{
    log("[Case A] 同 XY cell、Z 远离 (0.3–0.5 vs 1.8–2.0)");
    const pts = concat(colPts(10, 10, 0.3, 0.5, 20, 1), colPts(10, 10, 1.8, 2.0, 20, 2));
    const vox = PL.voxelize(pts);
    const kA = PL.key_vox(10.075, 10.075);
    check("key_vox 不区分 Z（两点同一键）", vox.size === 1, "voxel 数=" + vox.size + " key=" + kA);
    const raw = rawComponents(vox);
    check("原始分量 = 1（同柱必同簇）", raw.length === 1, summarize(raw));
    check("acc.zmin/zmax 横跨两结构（Z 只作统计）",
        Math.abs(raw[0].acc.zmin - 0.3) < 0.05 && Math.abs(raw[0].acc.zmax - 2.0) < 0.05, summarize(raw));
    const prod = PL.cluster_voxels(vox);
    check("production min_voxels=3 下该单柱体素被整簇丢弃（不显示）", prod.length === 0, "clusters=" + prod.length);
}

/* ---------------- Case B：XY 相邻 / Z overlap ---------------- */
{
    log("[Case B] XY 相邻 cell (0,0)+(1,0)、Z 重叠 [0.9,1.2]");
    const pts = concat(colPts(0, 0, 0.9, 1.2, 10, 3), colPts(1, 0, 0.9, 1.2, 10, 4));
    const raw = rawComponents(PL.voxelize(pts));
    check("原始分量 = 1（4 邻正常连通）", raw.length === 1, summarize(raw));
}

/* ---------------- Case C：XY 相邻 / Z 不 overlap ---------------- */
{
    log("[Case C] XY 相邻 cell (0,0)+(1,0)、Z 完全不重叠 ([0.2,0.5] vs [1.5,1.8])");
    const pts = concat(colPts(0, 0, 0.2, 0.5, 10, 5), colPts(1, 0, 1.5, 1.8, 10, 6));
    const vox = PL.voxelize(pts);
    const raw = rawComponents(vox);
    check("基线仍然并成 1 个分量（Z 被完全忽略 → VERTICAL_ALIAS 机理）", raw.length === 1, summarize(raw));
    const zc = vox.get(PL.key_vox(0.075, 0.075)), zh = vox.get(PL.key_vox(0.075 + V, 0.075));
    check("两个 voxel 的 Z 区间实为互不重叠（0.2–0.5 vs 1.5–1.8）却同簇",
        zc.zmax < zh.zmin, "低柱 zmax=" + zc.zmax.toFixed(2) + " 高柱 zmin=" + zh.zmin.toFixed(2));
    check("合并后簇 acc 的 zmin/zmax 横跨 [0.2,1.8]",
        Math.abs(raw[0].acc.zmin - 0.2) < 0.03 && Math.abs(raw[0].acc.zmax - 1.8) < 0.03, summarize(raw));
}

/* ---------------- Case D：只有一个低层 bridge voxel ---------------- */
{
    log("[Case D] 两根竖直柱 (0,*) 与 (3,*)（各 2×2 cells），唯一低层 bridge cell (2,0) z≈0.2");
    const mkCol = (bx, seed) => concat(colPts(bx, 0, 0.3, 1.8, 40, seed), colPts(bx + 1, 0, 0.3, 1.8, 40, seed + 1),
                                       colPts(bx, 1, 0.3, 1.8, 40, seed + 2), colPts(bx + 1, 1, 0.3, 1.8, 40, seed + 3));
    const b = colPts(2, 0, 0.15, 0.25, 3, 9);
    const all = concat(mkCol(0, 7), mkCol(3, 17), b);
    const vox = PL.voxelize(all);
    const raw = rawComponents(vox);
    check("基线 = 1 个分量（bridge 合并）", raw.length === 1, summarize(raw));
    const kb = PL.key_vox(0.375, 0.075);
    const deg = degree4(vox, kb);
    check("bridge voxel 4 邻 degree = 2（左柱 + 右柱）", deg === 2, "degree=" + deg);
    const split = removeCellsAndCluster(all, [kb]);
    check("删 bridge voxel 后 = 2 个分量（自然分裂）", split.length === 2, summarize(split));
    check("两侧柱体素仍 ≥3（分裂后均过 production 过滤）",
        split.every(c => c.keys.length >= 3), summarize(split));
}

/* ---------------- Case E：人体竖直连续柱体 ---------------- */
{
    log("[Case E] 人体形 4 柱 (0,0)(1,0)(0,1)(1,1)，Z 连续 [0.15,1.85]");
    const cells = [[0, 0], [1, 0], [0, 1], [1, 1]];
    const bufs = cells.map(([ix, iy], i) => colPts(ix, iy, 0.15, 1.85, 60, 20 + i));
    const all = concat(...bufs);
    const raw = rawComponents(PL.voxelize(all));
    check("原始分量 = 1（人体自身不得被拆）", raw.length === 1, summarize(raw));
    check("zmin≈0.15 / zmax≈1.85（身高保留）",
        Math.abs(raw[0].acc.zmin - 0.15) < 0.03 && Math.abs(raw[0].acc.zmax - 1.85) < 0.03, summarize(raw));
}

/* ---------------- Case F：人体旁边静态家具（间隔 / 桥接 / 贴邻） ---------------- */
{
    log("[Case F] 人体 (0,0)(1,0)(0,1)(1,1) z[0.15,1.85] + 家具 (3,0)(4,0)(3,1)(4,1) z[0.3,1.5]");
    const person = concat(colPts(0, 0, 0.15, 1.85, 60, 30), colPts(1, 0, 0.15, 1.85, 60, 31),
                          colPts(0, 1, 0.15, 1.85, 60, 32), colPts(1, 1, 0.15, 1.85, 60, 33));
    const furn = concat(colPts(3, 0, 0.3, 1.5, 60, 40), colPts(4, 0, 0.3, 1.5, 60, 41),
                        colPts(3, 1, 0.3, 1.5, 60, 42), colPts(4, 1, 0.3, 1.5, 60, 43));
    const gap = concat(person, furn);                    /* (2,*) 空 → 0.15m XY 间隙 */
    const rawGap = rawComponents(PL.voxelize(gap));
    check("F1 有间隙（cell (2,*) 空）：2 个分量（人/家具分开）", rawGap.length === 2, summarize(rawGap));

    const bridge = concat(gap, colPts(2, 0, 0.15, 0.25, 3, 50));   /* 1 个残留低点 cell */
    const voxB = PL.voxelize(bridge);
    const rawBridge = rawComponents(voxB);
    check("F2 加 1 个低层残留 cell (2,0)：并回 1 个分量（BRIDGE_MERGE）", rawBridge.length === 1, summarize(rawBridge));
    const kb = PL.key_vox(0.375, 0.075);
    check("bridge degree=2", degree4(voxB, kb) === 2, "degree=" + degree4(voxB, kb));
    const split = removeCellsAndCluster(bridge, [kb]);
    check("删该 1 cell → 2 个分量", split.length === 2, summarize(split));

    const adjacent = concat(person, concat(colPts(2, 0, 0.3, 1.5, 60, 51), colPts(2, 1, 0.3, 1.5, 60, 52),
                                           colPts(3, 0, 0.3, 1.5, 60, 53), colPts(3, 1, 0.3, 1.5, 60, 54)));
    const rawAdj = rawComponents(PL.voxelize(adjacent));
    check("F3 家具直接贴到相邻 cell（无间隙、无残留点）：仍 1 个分量（XY 邻接即合并）",
        rawAdj.length === 1, summarize(rawAdj));
}

/* ---------------- 对照 G：对角 XY（4 邻 vs 8 邻的差别面） ---------------- */
{
    log("[G] 对角 cell (0,0)+(1,1)、Z 重叠");
    const pts = concat(colPts(0, 0, 0.9, 1.2, 10, 60), colPts(1, 1, 0.9, 1.2, 10, 61));
    const raw = rawComponents(PL.voxelize(pts));
    check("基线（XY 4 邻）= 2 个分量（对角不连）", raw.length === 2, summarize(raw));
}

/* ---------------- 对照 H：一格空隙（hops 语义） ---------------- */
{
    log("[H] cell (0,0) 与 (2,0)（中间空 1 cell = 0.15m 间隙）");
    const pts = concat(colPts(0, 0, 0.9, 1.2, 10, 70), colPts(2, 0, 0.9, 1.2, 10, 71));
    const raw = rawComponents(PL.voxelize(pts));
    check("基线 = 2 个分量（无 hops>1；PIPE.cluster_neighbor_hops 为死参数，全仓无读取）",
        raw.length === 2, summarize(raw));
}

log("");
log("== 自检: " + passed + " passed, " + failed + " failed ==");
fs.writeFileSync(path.join(__dirname, "04_synthetic_cases.log"), L.join("\n") + "\n");
process.exit(failed ? 1 : 0);

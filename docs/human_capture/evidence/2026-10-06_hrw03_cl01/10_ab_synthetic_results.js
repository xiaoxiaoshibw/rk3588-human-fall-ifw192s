/* CL-01 · 10_ab_synthetic_results.js — synthetic A–H × 全 variant（A/B/C/D0/D15/D30/D45）
 * 复刻第一阶段 04 的场景；期望值 = 08_ab_plan.md §2 的语义预测。
 * 输出：10_ab_synthetic_results.json / .log（stdout 即 log）。
 */
"use strict";
const fs = require("fs");
const path = require("path");
const X = require(path.join(__dirname, "09_ab_shadow_impl.js"));

const variants = [["A"], ["B"], ["C"], ["D", 0], ["D", 0.15], ["D", 0.30], ["D", 0.45]];
const vname = v => v[1] === undefined ? v[0] : v[0] + "-G" + v[1].toFixed(2);
const concat = X.concatBufs, cellPts = X.cellPts;
const cf = (cells, z0, z1, n, seed) => { const bufs = []; let i = 0; for (const [ix, iy] of cells) bufs.push(cellPts(ix, iy, z0, z1, n, seed + (i++))); return concat(...bufs); };

const P4 = [[0, 0], [1, 0], [0, 1], [1, 1]];
const F4 = [[3, 0], [4, 0], [3, 1], [4, 1]];
const F4b = [[2, 0], [3, 0], [2, 1], [3, 1]];

const cases = [
    { id: "A", desc: "同 XY cell、Z 分离 (0.3–0.5 vs 1.8–2.0)",
      pts: concat(cellPts(10, 10, 0.3, 0.5, 20, 1), cellPts(10, 10, 1.8, 2.0, 20, 2)),
      expect: { A: 1, B: 1, C: 2, "D-G0.00": 1, "D-G0.15": 1, "D-G0.30": 1, "D-G0.45": 1 } },
    { id: "B", desc: "XY 相邻、Z 重叠 [0.9,1.2]",
      pts: concat(cellPts(0, 0, 0.9, 1.2, 20, 3), cellPts(1, 0, 0.9, 1.2, 20, 4)),
      expect: { A: 1, B: 1, C: 1, "D-G0.00": 1, "D-G0.15": 1, "D-G0.30": 1, "D-G0.45": 1 } },
    { id: "C", desc: "XY 相邻、Z 完全不重叠 (0.2–0.5 vs 1.5–1.8)",
      pts: concat(cellPts(0, 0, 0.2, 0.5, 20, 5), cellPts(1, 0, 1.5, 1.8, 20, 6)),
      expect: { A: 1, B: 1, C: 2, "D-G0.00": 2, "D-G0.15": 2, "D-G0.30": 2, "D-G0.45": 2 } },
    { id: "D", desc: "2×2 块 + 2×2 块 + 唯一低层 bridge cell (2,0) z≈0.2",
      pts: concat(cf([[0, 0], [1, 0], [0, 1], [1, 1]], 0.3, 1.8, 40, 7),
                  cf([[3, 0], [4, 0], [3, 1], [4, 1]], 0.3, 1.8, 40, 17),
                  cellPts(2, 0, 0.15, 0.25, 3, 9)),
      expect: { A: 1, B: 1, C: 1, "D-G0.00": 3, "D-G0.15": 1, "D-G0.30": 1, "D-G0.45": 1 } },
    { id: "E", desc: "人体形 4 柱、Z 连续 [0.15,1.85]",
      pts: cf(P4, 0.15, 1.85, 60, 20),
      expect: { A: 1, B: 1, C: 1, "D-G0.00": 1, "D-G0.15": 1, "D-G0.30": 1, "D-G0.45": 1 } },
    { id: "F1", desc: "人体 + 家具（间隔 1 cell）",
      pts: concat(cf(P4, 0.15, 1.85, 60, 30), cf(F4, 0.3, 1.5, 60, 40)),
      expect: { A: 2, B: 2, C: 2, "D-G0.00": 2, "D-G0.15": 2, "D-G0.30": 2, "D-G0.45": 2 } },
    { id: "F2", desc: "人体 + 家具 + 1 个低层残留 cell（bridge）",
      pts: concat(cf(P4, 0.15, 1.85, 60, 30), cf(F4, 0.3, 1.5, 60, 40), cellPts(2, 0, 0.15, 0.25, 3, 50)),
      expect: { A: 1, B: 1, C: 1, "D-G0.00": 2, "D-G0.15": 1, "D-G0.30": 1, "D-G0.45": 1 } },
    { id: "F3", desc: "人体 + 家具直接贴邻（无间隙）",
      pts: concat(cf(P4, 0.15, 1.85, 60, 30), cf(F4b, 0.3, 1.5, 60, 51)),
      expect: { A: 1, B: 1, C: 1, "D-G0.00": 1, "D-G0.15": 1, "D-G0.30": 1, "D-G0.45": 1 } },
    { id: "G", desc: "对角 cell（4 邻不连）",
      pts: concat(cellPts(0, 0, 0.9, 1.2, 20, 60), cellPts(1, 1, 0.9, 1.2, 20, 61)),
      expect: { A: 2, B: 1, C: 1, "D-G0.00": 2, "D-G0.15": 2, "D-G0.30": 2, "D-G0.45": 2 } },
    { id: "H", desc: "间隔 1 cell（0.15m 空隙）",
      pts: concat(cellPts(0, 0, 0.9, 1.2, 20, 70), cellPts(2, 0, 0.9, 1.2, 20, 71)),
      expect: { A: 2, B: 2, C: 2, "D-G0.00": 2, "D-G0.15": 2, "D-G0.30": 2, "D-G0.45": 2 } },
];

const L = [];
const log = s => { L.push(s); console.log(s); };
log("== CL-01 synthetic A–H × connectivity variants ==");
log("A/B/D 节点=XY 0.15 柱；C 节点=XYZ 0.15^3；min_voxels=3（filtered）；期望值见 08 计划 §2 / 本脚本 expect");
log("");

let allPass = true;
const out = { generated: new Date().toISOString(), unit: "raw components（未过滤）",
              variants: variants.map(vname), cases: [] };
for (const cs of cases) {
    const row = { id: cs.id, desc: cs.desc, expect: cs.expect, results: {} };
    const cells = [];
    for (const v of variants) {
        const r = X.build(cs.pts, v[0], v[1]);
        const f = X.filtered(r);
        const raw = r.comps.length, filt = f.filtered_count;
        const largest = r.comps.reduce((m, c) => Math.max(m, c.n_points), 0);
        row.results[vname(v)] = { raw: raw, filtered: filt, discarded: f.discarded_points,
            largest_pts: largest, n_nodes: r.nNodes };
        const exp = cs.expect[vname(v)];
        const ok = raw === exp;
        if (!ok) allPass = false;
        cells.push(vname(v) + "=" + raw + (ok ? "" : "(exp " + exp + "!)") + (filt !== raw ? " filt" + filt : ""));
    }
    row.pass = Object.keys(cs.expect).every(k => row.results[k].raw === cs.expect[k]);
    out.cases.push(row);
    log("[" + cs.id + "] " + cs.desc);
    log("   " + cells.join("  "));
}
out.all_pass = allPass;
log("");
log("== " + (allPass ? "ALL EXPECTED MATCH" : "EXPECTATION MISMATCH（见上！）") + " ==");
fs.writeFileSync(path.join(__dirname, "10_ab_synthetic_results.json"), JSON.stringify(out, null, 1) + "\n");
fs.writeFileSync(path.join(__dirname, "10_ab_synthetic_results.log"), L.join("\n") + "\n");
process.exit(allPass ? 0 : 1);

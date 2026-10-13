/* W03-R3.6 分析提取（只读 03_results.json；用于 05/06 文档） */
"use strict";
const fs = require("fs");
const path = require("path");
const R = JSON.parse(fs.readFileSync(path.join(__dirname, "03_results.json"), "utf8"));
const out = [];
function p(s) { out.push(s); console.log(s); }
const pctf = v => v === null || v === undefined ? "-" : (100 * v).toFixed(1) + "%";

p("# A) group summary (point-level)");
for (const g of ["ALL", "WD01", "WD02", "PROBLEM", "CLEAN", "NEAR_FURN"]) {
    const G = R.groups[g];
    const c = G.conditions;
    p(g + " n=" + G.residual_points);
    for (const k of ["A", "TLS", "B", "C", "C_ALT"]) {
        p("  " + k.padEnd(6) + " absorb=" + c[k].absorbed + " (" + pctf(c[k].absorbed_share) + ") residual=" + c[k].residual
            + " (" + pctf(c[k].residual_share) + ") buckets=" + JSON.stringify(c[k].bucket_counts));
    }
    p("  gain B: " + JSON.stringify(G.gain.B) + "  C: " + JSON.stringify(G.gain.C) + "  C_ALT: " + JSON.stringify(G.gain.C_ALT));
    p("  recovery: " + JSON.stringify(G.recovery));
    p("  states A=" + JSON.stringify(G.states.A) + " B=" + JSON.stringify(G.states.B));
    p("  trans A2B=" + JSON.stringify(G.transitions.A2B));
    p("  trans B2C=" + JSON.stringify(G.transitions.B2C));
    p("  voxel shares: A=" + JSON.stringify(G.voxel.A.bucket_share));
    p("  voxel shares: B=" + JSON.stringify(G.voxel.B.bucket_share));
    p("  voxel shares: C=" + JSON.stringify(G.voxel.C.bucket_share));
    p("  voxel counts: A dots=" + G.voxel.A.voxels + " B=" + G.voxel.B.voxels + " C=" + G.voxel.C.voxels);
}
p("");
p("# B) human safety — near furniture frames (station window r<=0.6)");
for (const fi of ["55", "150", "155", "160"]) {
    const H = R.human_safety.near[fi];
    if (!H) continue;
    p("f" + fi + " center=[" + H.center + "] n_window=" + H.n);
    for (const band of ["z>=1.2", "0.8-1.2", "0.3-0.8"]) {
        const b = H.bands[band];
        if (!b) { p("  " + band + ": none"); continue; }
        p("  " + band + " n=" + b.n + " abs A/B/C/C_ALT=" + JSON.stringify(b.abs) + " rates=" + ["A", "B", "C", "C_ALT"].map(k => b.n ? ((100 * (b.abs[k] || 0) / b.n).toFixed(1) + "%") : "-").join("/"));
    }
}
p("");
p("# B2) clean controls (person windows)");
for (const fi of Object.keys(R.human_safety.clean)) {
    const H = R.human_safety.clean[fi];
    if (!H) continue;
    const parts = [];
    for (const band of ["z>=1.2", "0.8-1.2", "0.3-0.8"]) {
        const b = H.bands[band];
        if (b) parts.push(band + " n=" + b.n + " abs=" + JSON.stringify(b.abs));
    }
    p("f" + fi + " center=[" + H.center + "] n=" + H.n + " | " + parts.join(" | "));
}
p("");
p("# B3) proxy classes (PROXY_FRAMES [10,30,55,150,155,160])");
for (const cls of Object.keys(R.human_safety.proxies)) {
    const pr = R.human_safety.proxies[cls];
    p(cls + " n=" + pr.n + " abs A/B/C/C_ALT=" + JSON.stringify(pr.abs) + " rates=" + ["A", "B", "C", "C_ALT"].map(k => pr.n ? ((100 * (pr.abs[k] || 0) / pr.n).toFixed(1) + "%") : "-").join("/"));
}
p("");
p("# C) focal frames absorb A/B/C/C_ALT (n_residual, absorb, absorb%)");
const focus = [2, 10, 30, 42, 55, 63, 65, 80, 85, 90, 92, 95, 99, 123, 146, 150, 155, 160];
for (const fr of R.frames) {
    if (!focus.includes(fr.frame_index)) continue;
    const c = fr.conditions;
    const f = k => c[k].absorbed + "(" + (100 * c[k].absorbed / fr.n_residual).toFixed(1) + "%)";
    p("f" + String(fr.frame_index).padEnd(3) + " n=" + String(fr.n_residual).padEnd(5) + " A=" + f("A") + " B=" + f("B") + " C=" + f("C") + " C_ALT=" + f("C_ALT") + " TLS=" + f("TLS"));
}
p("");
p("# D) C registration QA");
p(JSON.stringify(R.c_registration_qa, null, 1));
p("");
p("# E) checks");
for (const c of R.checks) p((c.pass ? "PASS  " : "FAIL  ") + c.name);
p("# digest=" + R.digest);

/* ---- F) WD02 spatial descriptives（focal CSV；供 S7 空间吻合检查） ---- */
p("");
p("# F) WD02 spatial descriptives (focal frames CSV)");
{
    const csv = fs.readFileSync(path.join(__dirname, "04_point_attribution.csv"), "utf8").split("\n");
    const head = csv[0].split(",");
    const col = {};
    head.forEach((h, i) => col[h] = i);
    const pts = [];
    for (let i = 1; i < csv.length; i++) {
        const f = csv[i].split(",");
        if (f.length < head.length) continue;
        if (f[col.in_wd02_proxy] !== "1") continue;
        pts.push(f);
    }
    const num = (f, k) => f[col[k]] === "" ? null : parseFloat(f[col[k]]);
    const q = (arr, t) => { const s = arr.filter(v => v !== null).sort((a, b) => a - b); return s.length ? s[Math.min(s.length - 1, Math.floor(t * s.length))].toFixed(4) : "-"; };
    const recC = pts.filter(f => f[col.recover_C] === "1");
    const recB = pts.filter(f => f[col.recover_B] === "1");
    p("WD02 focal rows=" + pts.length + " recover_B=" + recB.length + " recover_C=" + recC.length);
    const dA = recC.map(f => num(f, "d_A"));
    const dC = recC.map(f => num(f, "d_C"));
    const del = recC.map(f => num(f, "delta_d_AC"));
    p("recover_C: d_A p10/p50/p90=" + q(dA, 0.1) + "/" + q(dA, 0.5) + "/" + q(dA, 0.9)
        + "  d_C p50=" + q(dC, 0.5) + "  delta_AC p50=" + q(del, 0.5));
    const shellA = { IN: 0, SHELL: 0, OVER: 0, ABSENT: 0 };
    for (const f of pts) shellA[f[col.shell_A]]++;
    p("all WD02 shell_A=" + JSON.stringify(shellA));
    const shellRec = { IN: 0, SHELL: 0, OVER: 0, ABSENT: 0 };
    for (const f of recC) shellRec[f[col.shell_A]]++;
    p("recover_C shell_A=" + JSON.stringify(shellRec));
    const azShare = (arr) => {
        const sec = [0, 0, 0, 0];
        for (const f of arr) {
            const x = parseFloat(f[col.x]), y = parseFloat(f[col.y]);
            let a = Math.atan2(y, x) * 180 / Math.PI;
            if (a < 0) a += 360;
            sec[Math.min(3, Math.floor(a / 90))]++;
        }
        return sec.map(v => (100 * v / (arr.length || 1)).toFixed(1) + "%").join("/");
    };
    p("azimuth 0-90/90-180/180-270/270-360: WD02 all=" + azShare(pts) + "  recover_C=" + azShare(recC));
}

/* ---- G) residual voxel counts（04b；体素中心区域判定） ---- */
p("");
p("# G) residual voxel counts (04b CSV; voxel centroid region)");
{
    const csv = fs.readFileSync(path.join(__dirname, "04b_voxel_transitions.csv"), "utf8").split("\n");
    const inWd01 = (x, y) => Math.hypot(x - 3.50, y + 0.76) <= 0.9;
    const inWd02 = (x, y) => Math.hypot(x, y) > 8 || [[10.75, 4.25], [10.25, -1.75], [10.50, 5.50]].some(r => Math.hypot(x - r[0], y - r[1]) <= 1.5);
    const regions = { ALL: () => true, WD01: inWd01, WD02: inWd02 };
    const stat = {};
    for (const rg of Object.keys(regions)) stat[rg] = { cells: 0, res: { A: 0, B: 0, C: 0, C_ALT: 0 } };
    for (let i = 1; i < csv.length; i++) {
        const f = csv[i].split(",");
        if (f.length < 14) continue;
        const ij = f[2].split(";").map(Number);
        const x = (ij[0] + 0.5) * 0.15, y = (ij[1] + 0.5) * 0.15;
        const n = +f[3], aA = +f[8], aB = +f[9], aC = +f[10];
        for (const rg of Object.keys(regions)) {
            if (!regions[rg](x, y)) continue;
            stat[rg].cells++;
            if (n - aA >= 1) stat[rg].res.A++;
            if (n - aB >= 1) stat[rg].res.B++;
            if (n - aC >= 1) stat[rg].res.C++;
        }
    }
    for (const rg of Object.keys(stat)) {
        const s = stat[rg];
        p(rg + " cells=" + s.cells + " residual_voxels A/B/C=" + s.res.A + "/" + s.res.B + "/" + s.res.C
            + " (" + [s.res.A, s.res.B, s.res.C].map(v => (100 * v / (s.cells || 1)).toFixed(1) + "%").join("/") + ")");
    }
}


fs.writeFileSync(path.join(__dirname, "_r36_analyze.log"), out.join("\n") + "\n");

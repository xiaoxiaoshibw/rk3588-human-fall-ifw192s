/* CL-01 · 11_ab_real_frame_results.js — 全 165 帧 + 重点帧 A/B/C/D shadow AB 统计。
 *
 * 固定：session/leveled/denoise/extract_foreground/cleanup/参数/下游函数（见 08_ab_plan.md）。
 * 唯一变量：build(pts, variant, G) 的 connectivity。
 * 输出：11_ab_real_frame_results.json / .log、12_ab_debug_data.json。
 */
"use strict";
const fs = require("fs");
const path = require("path");
const X = require(path.join(__dirname, "09_ab_shadow_impl.js"));
const PL = X.PL;
const REPO = path.resolve(__dirname, "..", "..", "..", "..");
const HERE = __dirname;

const CUR_SID = "cap_20261002_223757";
const REF_SID = "cap_20261004_203349";
const OCC = 0.5, MATCH_R = 0.12;

const VARIANTS = [["A"], ["B"], ["C"], ["D", 0], ["D", 0.15], ["D", 0.30], ["D", 0.45]];
const VN = v => v[1] === undefined ? v[0] : v[0] + "-G" + v[1].toFixed(2);
const VAR_NAMES = VARIANTS.map(VN);
const D_CANDS = ["D-G0.00", "D-G0.15", "D-G0.30", "D-G0.45"];

const L = [];
const log = s => { L.push(s); console.log(s); };

/* ---------------- 加载 ---------------- */
console.log("[ab] loading " + REF_SID + " ...");
const REF = X.loadLeveledDenoised(REF_SID);
console.log("[ab] loading " + CUR_SID + " ...");
const CUR = X.loadLeveledDenoised(CUR_SID);
const refMap = PL.build_reference_map(REF.frames);
const ONLINE = PL.build_static_map(CUR.frames, { drop_ground: true });

const BG_BASE = 8192, BG_OFF = 4096;
const bgk = (ix, iy, iz) => ((ix + BG_OFF) * BG_BASE + (iy + BG_OFF)) * BG_BASE + (iz + BG_OFF);
const VX = PL.PIPE.bg_voxel_xy, VZ = PL.PIPE.bg_voxel_z;
function refScan(px, py, pz) {
    const ix = Math.floor(px / VX), iy = Math.floor(py / VX), iz = Math.floor(pz / VZ);
    let d0 = Infinity, d1 = Infinity;
    for (let a = -1; a <= 1; a++) for (let b = -1; b <= 1; b++) for (let c = -1; c <= 1; c++) {
        const rec = refMap.voxels.get(bgk(ix + a, iy + b, iz + c));
        if (!rec || rec.occ < OCC) continue;
        const dx = rec.x - px, dy = rec.y - py, dz = rec.z - pz;
        const c2 = dx * dx + dy * dy + dz * dz; if (c2 < d0) d0 = c2;
        const bx = (ix + a) * VX, by = (iy + b) * VX, bz = (iz + c) * VZ;
        const ex = Math.max(bx - px, 0, px - (bx + VX)), ey = Math.max(by - py, 0, py - (by + VX)), ez = Math.max(bz - pz, 0, pz - (bz + VZ));
        const b2 = ex * ex + ey * ey + ez * ez; if (b2 < d1) d1 = b2;
    }
    return { d0: d0 === Infinity ? null : Math.sqrt(d0), d1: d1 === Infinity ? null : Math.sqrt(d1) };
}

const hr = () => process.hrtime.bigint();
const msf = (a, b) => Number(b - a) / 1e6;

/* ---------------- 每帧公共前景（共享段） ---------------- */
function foreground(fi) {
    const t0 = hr();
    const fg = PL.extract_foreground(CUR.frames[fi], ONLINE);
    const iso = PL.cleanup_isolated_fg(fg.fg_xyzi);
    return { pts: iso.xyzi, n_fg: fg.n_fg, n_cleanup: iso.xyzi.length / 4, shared_ms: msf(t0, hr()) };
}

/* ---------------- 差分事件（raw 分区） ---------------- */
function diffEvents(rA, rX) {
    const n = rA.pointComp.length;
    const perA = new Map(), perX = new Map();
    for (let p = 0; p < n; p++) {
        const a = rA.pointComp[p], x = rX.pointComp[p];
        let ma = perA.get(a); if (!ma) { ma = new Map(); perA.set(a, ma); } ma.set(x, (ma.get(x) || 0) + 1);
        let mx = perX.get(x); if (!mx) { mx = new Map(); perX.set(x, mx); } mx.set(a, (mx.get(a) || 0) + 1);
    }
    const splits = [], merges = [];
    perA.forEach((m, a) => {
        const ca = rA.comps[a];
        if (ca.n_points < 20) return;
        const parts = [...m.entries()].sort((u, w) => w[1] - u[1]);
        if (parts.length >= 2 && parts[1][1] >= 0.10 * ca.n_points) {
            const p1 = rX.comps[parts[0][0]], p2 = rX.comps[parts[1][0]];
            splits.push({ a: a, total: ca.n_points,
                parts: parts.slice(0, 3).map(([xId, cnt]) => ({ x: xId, share: +(cnt / ca.n_points).toFixed(3),
                    z: [+rX.comps[xId].min_z.toFixed(2), +rX.comps[xId].max_z.toFixed(2)] })),
                zdisjoint: (p1.max_z < p2.min_z) || (p2.max_z < p1.min_z) });
        }
    });
    perX.forEach((m, x) => {
        const cx = rX.comps[x];
        if (cx.n_points < 20) return;
        const src = [...m.entries()].sort((u, w) => w[1] - u[1]);
        if (src.length >= 2 && src[1][1] >= 0.10 * cx.n_points) {
            merges.push({ x: x, total: cx.n_points,
                src: src.slice(0, 3).map(([aId, cnt]) => ({ a: aId, share: +(cnt / cx.n_points).toFixed(3) })) });
        }
    });
    return { splits: splits, merges: merges };
}

/* ---------------- warmup + 全帧聚合 ---------------- */
const WARM = [0, 5, 10];
for (const fi of WARM) {
    const fg = foreground(fi);
    for (const v of VARIANTS) X.build(fg.pts, v[0], v[1]);
    PL.cluster_voxels(PL.voxelize(fg.pts));
}
log("== CL-01 connectivity shadow AB：全 165 帧 ==");
log("variants: " + VAR_NAMES.join(" / "));
log("");

const agg = {};
for (const vn of VAR_NAMES) agg[vn] = { frames: 0, raw_total: 0, filtered_total: 0, frag_total: 0, discarded_total: 0,
    kept_total: 0, largest_ratio_sum: 0, largest_pts_max: 0, raw_pts_max: 0,
    split_events: 0, split_points: 0, zdisjoint_events: 0, zdisjoint_points: 0, split_tall_events: 0,
    merge_events: 0, merge_points: 0, merge_tall_events: 0, rt_cluster: [], rt_total: [] };
const perFrame = [];
const eqMismatch = [];

let N_FRAMES = CUR.frames.length;
for (let fi = 0; fi < N_FRAMES; fi++) {
    const fg = foreground(fi);
    const pts = fg.pts, nPts = pts.length / 4;
    const tallP = new Uint8Array(nPts);
    for (let i = 0; i < nPts; i++) tallP[i] = nPts && pts[i * 4 + 2] > 1.45 ? 1 : 0;

    /* A 复刻自检（含 raw/filtered 对照） */
    const eq = X.equivalenceCheck(pts);
    if (!eq.same) eqMismatch.push({ fi: fi, eq: eq });

    const row = { fi: fi, fg: nPts, shared_ms: +fg.shared_ms.toFixed(3), v: {} };
    const runs = {};
    for (const v of VARIANTS) {
        const vn = VN(v);
        const t0 = hr();
        const r = X.build(pts, v[0], v[1]);
        const f = X.filtered(r);
        const t1 = hr();
        runs[vn] = { r: r, f: f };

        const compTall = new Uint32Array(r.comps.length);
        for (let i = 0; i < nPts; i++) if (tallP[i]) compTall[r.pointComp[i]]++;
        row.v[vn] = { raw: r.comps.length, filtered: f.filtered_count, frag: f.fragment_count,
            discarded: f.discarded_points, largest: f.comps.reduce((m, c) => Math.max(m, c.n_points), 0),
            ms: +msf(t0, t1).toFixed(3) };
        const A = agg[vn];
        A.frames++;
        A.raw_total += r.comps.length; A.filtered_total += f.filtered_count;
        A.frag_total += f.fragment_count; A.discarded_total += f.discarded_points;
        A.kept_total += nPts - f.discarded_points;
        A.largest_ratio_sum += row.v[vn].largest / nPts;
        A.largest_pts_max = Math.max(A.largest_pts_max, row.v[vn].largest);
        A.rt_cluster.push(msf(t0, t1));
        A.rt_total.push(fg.shared_ms + msf(t0, t1));
        row.v[vn].compTall = compTall;                    /* 供差分使用（内部字段，输出前删除） */
    }
    /* 差分（X vs A） */
    if (runs.A) {
        for (const v of VARIANTS) {
            const vn = VN(v);
            if (vn === "A") continue;
            const d = diffEvents(runs.A.r, runs[vn].r);
            row.v[vn].split_events = d.splits.length;
            row.v[vn].merge_events = d.merges.length;
            const A = agg[vn];
            for (const s of d.splits) {
                A.split_events++; A.split_points += s.total;
                if (s.zdisjoint) { A.zdisjoint_events++; A.zdisjoint_points += s.total; }
                if (row.v.A.compTall[s.a] >= 20) A.split_tall_events++;
            }
            for (const m of d.merges) {
                A.merge_events++; A.merge_points += m.total;
                if (row.v[vn].compTall && row.v[vn].compTall[m.x] >= 20) A.merge_tall_events++;
            }
        }
    }
    for (const vn of VAR_NAMES) delete row.v[vn].compTall;
    perFrame.push(row);
    if ((fi + 1) % 55 === 0) console.log("[ab]   " + (fi + 1) + "/" + N_FRAMES);
}

function pct(a, q) { if (!a.length) return null; const s = a.slice().sort((x, y) => x - y); return s[Math.min(s.length - 1, Math.ceil(q * s.length) - 1)]; }
function rtStats(a) { return { mean: +(a.reduce((x, y) => x + y, 0) / a.length).toFixed(3), p50: +pct(a, .5).toFixed(3),
    p95: +pct(a, .95).toFixed(3), max: +Math.max.apply(null, a).toFixed(3) }; }

/* ---------------- 基线复刻对照（vs 第一阶段 06/07） ---------------- */
const audit = JSON.parse(fs.readFileSync(path.join(HERE, "06_cluster_stats.json"), "utf8"));
const baseA = agg.A;
const baseRep = {
    raw_mean: +(baseA.raw_total / baseA.frames).toFixed(2), audit_raw_mean: audit.aggregate.cluster_counts.raw_mean,
    filtered_mean: +(baseA.filtered_total / baseA.frames).toFixed(2), audit_filtered_mean: audit.aggregate.cluster_counts.prod_mean,
    frag_total: baseA.frag_total, audit_frag_total: audit.aggregate.cluster_counts.fragments_total,
    pass: Math.abs(baseA.raw_total / baseA.frames - audit.aggregate.cluster_counts.raw_mean) <= 0.01
        && Math.abs(baseA.filtered_total / baseA.frames - audit.aggregate.cluster_counts.prod_mean) <= 0.05
        && baseA.frag_total === audit.aggregate.cluster_counts.fragments_total,
};
log("baseline A 复刻: raw_mean=" + baseRep.raw_mean + " (audit " + baseRep.audit_raw_mean + "), filtered_mean="
    + baseRep.filtered_mean + " (audit " + baseRep.audit_filtered_mean + "), frag=" + baseRep.frag_total
    + " (audit " + baseRep.audit_frag_total + ") → " + (baseRep.pass ? "PASS" : "FAIL"));
log("A 等价 production（逐帧 raw+filtered 分区）: " + (eqMismatch.length === 0 ? "PASS" : "FAIL(" + eqMismatch.length + ")"));
log("");

/* ---------------- 重点帧详细 ---------------- */
const PROXY = { 55: [1.47, 0.64, "merged"], 150: [1.46, 0.30, "merged"], 155: [1.57, 0.65, "merged"], 160: [1.60, 0.78, "merged"],
    63: [1.41, 0.06, "human"], 65: [1.46, -0.11, "human"], 80: [1.52, -0.40, "human"], 85: [1.52, -0.40, "human"],
    90: [1.52, -0.40, "human"], 92: [1.52, -0.40, "human"], 95: [1.52, -0.40, "human"], 99: [1.52, -0.40, "human"],
    123: [1.52, -0.40, "human"], 146: [1.29, -0.17, "human"],
    2: [3.50, -0.76, "static"], 42: [3.50, -0.76, "static"], 10: [1.45, 0.85, "static"], 30: [1.45, 0.85, "static"] };

const fragTop = perFrame.slice().sort((a, b) => (b.v ? b.v.A.frag : 0) - (a.v ? a.v.A.frag : 0)).slice(0, 3).map(r => r.fi);
log("fragment-heavy top3: " + fragTop.join(", "));
const DETAIL = [2, 10, 30, 42, 55, 63, 65, 80, 85, 90, 92, 95, 99, 123, 146, 150, 155, 160];
for (const fi of fragTop) if (!DETAIL.includes(fi)) DETAIL.push(fi);
const KIND = {}; for (const [k, v] of Object.entries(PROXY)) KIND[k] = v[2];
for (const fi of fragTop) if (!KIND[fi]) KIND[fi] = "frag";

function adjKeysFn(r, vn) {
    const keyIdx = new Map();
    for (let i = 0; i < r.nodeKey.length; i++) keyIdx.set(r.nodeKey[i], i);
    const gate = (ai, bi) => {
        const ba = r.nodeBins[ai], bb = r.nodeBins[bi];
        let best = Infinity;
        ba.forEach(x => { bb.forEach(y => { const d = x > y ? x - y : y - x; if (d < best) best = d; }); });
        return best * X.VXY <= r.G + 1e-9;
    };
    const isD = vn.startsWith("D");
    return (key) => {
        const parts = key.split(",").map(Number);
        const ix = parts[0], iy = parts[1], iz = parts[2];
        const offs = vn === "C" ? X.NB26 : vn === "B" ? X.NB8 : X.NB4;
        const out = [];
        for (const [dx, dy, dz] of offs) {
            const nk = vn === "C" ? (ix + dx) + "," + (iy + dy) + "," + (iz + (dz || 0)) : (ix + dx) + "," + (iy + dy);
            const j = keyIdx.get(nk);
            if (j === undefined) continue;
            const i0 = keyIdx.get(key);
            if (isD && !gate(i0, j)) continue;
            out.push(nk);
        }
        return out;
    };
}

function buildAccAndKeys(pts, pointComp, ci) {
    let n = 0, sx = 0, sy = 0, sz = 0, sxx = 0, syy = 0, szz = 0, sxy = 0, sxz = 0, syz = 0, zmin = Infinity, zmax = -Infinity;
    const keys = new Set(); const outPts = [];
    for (let i = 0, p = 0; p < pts.length; p += 4, i++) {
        if (pointComp[i] !== ci) continue;
        const x = pts[p], y = pts[p + 1], z = pts[p + 2];
        n++; sx += x; sy += y; sz += z; sxx += x * x; syy += y * y; szz += z * z;
        sxy += x * y; sxz += x * z; syz += y * z;
        if (z < zmin) zmin = z; if (z > zmax) zmax = z;
        keys.add(PL.key_vox(x, y));
        outPts.push(x, y, z, pts[p + 3]);
    }
    return { n: n, acc: { n: n, sx: sx, sy: sy, sz: sz, sxx: sxx, syy: syy, szz: szz, sxy: sxy, sxz: sxz, syz: syz, zmin: zmin, zmax: zmax },
             keys: [...keys], pts: new Float32Array(outPts) };
}

const detail = [];
for (const fi of DETAIL) {
    const fg = foreground(fi);
    const pts = fg.pts, nPts = pts.length / 4;
    const kind = KIND[fi] || "frag";
    const proxy = PROXY[fi];
    const dRow = { fi: fi, kind: kind, proxy: proxy ? [proxy[0], proxy[1]] : null, fg: nPts, variants: {} };
    const rA = X.build(pts, "A");
    for (const v of VARIANTS) {
        const vn = VN(v);
        const t0 = hr();
        const r = X.build(pts, v[0], v[1]);
        const t1 = hr();
        const f = X.filtered(r);
        /* fake acc for filtered comps: acc 由 buildAccAndKeys 生成 */
        const rows = [];
        let proxyTotal = 0, proxyByComp = new Map();
        const compProxy = new Uint32Array(r.comps.length), compUpper = new Uint32Array(r.comps.length),
              compRef = new Uint32Array(r.comps.length), compRefN = new Uint32Array(r.comps.length);
        const upperThr = 1.35;
        for (let i = 0, p = 0; p < pts.length; p += 4, i++) {
            const x = pts[p], y = pts[p + 1], z = pts[p + 2], ci = r.pointComp[i];
            if (z > upperThr) compUpper[ci]++;
            if (proxy) {
                const isProxy = kind === "merged" ? (z > upperThr && Math.hypot(x - proxy[0], y - proxy[1]) <= 0.55)
                    : kind === "human" ? (Math.hypot(x - proxy[0], y - proxy[1]) <= 0.55)
                    : false;
                if (isProxy) { proxyTotal++; compProxy[ci]++; }
            }
            const rr = refScan(x, y, z);
            if (rr.d0 !== null && rr.d0 < MATCH_R) compRef[ci]++;
            if (rr.d0 !== null || rr.d1 !== null) compRefN[ci]++;
        }
        /* person comp（raw） */
        let personRaw = -1, personPtsMax = 0;
        if (proxyTotal > 0) compProxy.forEach((cnt, ci) => { if (cnt > personPtsMax) { personPtsMax = cnt; personRaw = ci; } });
        /* filtered comp rows + 下游（仅观察） */
        for (const c of f.comps) {
            const pack = buildAccAndKeys(pts, r.pointComp, c.id);
            const cl = { keys: pack.keys, acc: pack.acc };
            const fe = PL.cluster_features(cl);
            let label = "NON_HUMAN", joint = "NON_HUMAN", conf = 0, reasons = ["points<60"], ev = "EVIDENCE_NONE", spread_cv = null, aniso = null;
            if (fe.ok) {
                const cls = PL.classify_human(fe);
                fe.label = cls.label; fe.confidence = cls.confidence; fe.reasons = cls.reasons;
                const extra = PL.evidence_postpass(pack.pts, [cl]).clusters_extra[0];
                const tag = PL.evidence_label(extra);
                fe.evidence_tag = tag;
                label = cls.label; conf = cls.confidence; reasons = cls.reasons; joint = PL.joint_status(fe); ev = tag.label;
                spread_cv = extra.spread_cv === null ? null : +extra.spread_cv.toFixed(3);
                aniso = extra.anisotropy_xy === null ? null : +extra.anisotropy_xy.toFixed(2);
            }
            rows.push({ id: c.id, n_points: c.n_points, n_nodes: c.n_nodes,
                bbox: [+c.min_x.toFixed(2), +c.max_x.toFixed(2), +c.min_y.toFixed(2), +c.max_y.toFixed(2), +c.min_z.toFixed(2), +c.max_z.toFixed(2)],
                ref_frac: pack.n ? +(compRef[c.id] / pack.n).toFixed(3) : null,
                upper_pts: compUpper[c.id], proxy_pts: compProxy[c.id],
                label: label, joint: joint, ev: ev, spread_cv: spread_cv, aniso: aniso, conf: +conf.toFixed(2),
                is_person: c.id === personRaw });
        }
        /* retention / upper split */
        const retention = proxyTotal > 0 ? +(personPtsMax / proxyTotal).toFixed(4) : null;
        const upperComps = [...r.comps].filter(c => compUpper[c.id] >= 20).length;
        /* contact（tall 节点标记） */
        const nodeFlag = new Uint8Array(r.nNodes);
        if (kind !== "static") for (let i = 0, p = 0; p < pts.length; p += 4, i++) if (pts[p + 2] > 1.45) nodeFlag[r.pointNode[i]] = 1;
        const contact = kind !== "static" ? X.crossEdges(r, nodeFlag) : null;
        /* articulation（person comp 或最大 comp，V≤350） */
        let cutTarget = personRaw >= 0 ? personRaw : (f.comps.length ? f.comps.reduce((m, c) => c.n_points > m.n_points ? c : m).id : -1);
        let cut = null;
        if (cutTarget >= 0) {
            const keys = r.comps[cutTarget].nodes.map(i => r.nodeKey[i]);
            if (keys.length <= 350) cut = X.cutAnalysis(keys, adjKeysFn(r, vn), 350);
            else cut = { skipped: true, V: keys.length };
        }
        const diffAB = vn === "A" ? null : diffEvents(rA, r);
        dRow.variants[vn] = { raw: r.comps.length, filtered: f.filtered_count, frag: f.fragment_count,
            discarded: f.discarded_points, ms: +msf(t0, t1).toFixed(3),
            person_raw: personRaw, person_points: personPtsMax, proxy_total: proxyTotal, retention: retention,
            upper_pts: compUpper.reduce((a, b) => a + b, 0), upper_comps: upperComps,
            contact: contact, cut: cut,
            diff: diffAB ? { splits: diffAB.splits.length, merges: diffAB.merges.length,
                    split_pts: diffAB.splits.reduce((a, s) => a + s.total, 0),
                    zdisjoint_pts: diffAB.splits.filter(s => s.zdisjoint).reduce((a, s) => a + s.total, 0),
                    detail: diffAB.splits.slice(0, 4).map(s => ({ a: s.a, total: s.total, zdisjoint: s.zdisjoint, parts: s.parts })) } : null,
            comps: rows };
    }
    detail.push(dRow);
    console.log("[ab] detail f" + fi + " (" + kind + ") done");
}

/* ---------------- D* 选择（08 §2.1 / §6） ---------------- */
function cleanRetMin(vn) {
    const rows = detail.filter(d => d.kind === "human" && d.variants[vn].retention !== null);
    return rows.length ? Math.min(...rows.map(d => d.variants[vn].retention)) : null;
}
const sel = {};
for (const vn of D_CANDS) {
    const A = agg[vn];
    sel[vn] = { clean_ret_min: cleanRetMin(vn),
        frag_ratio: +(A.frag_total / agg.A.frag_total).toFixed(3),
        discarded_ratio: +(A.discarded_total / agg.A.discarded_total).toFixed(3),
        zdisjoint_points: A.zdisjoint_points, split_points: A.split_points,
        rt_p95_ratio: +(rtStats(A.rt_cluster).p95 / rtStats(agg.A.rt_cluster).p95).toFixed(2) };
}
let dStar = null;
for (const vn of D_CANDS) {
    const s = sel[vn];
    if (s.clean_ret_min !== null && s.clean_ret_min >= 0.98 && s.frag_ratio <= 1.5 && s.discarded_ratio <= 1.5 && s.rt_p95_ratio <= 10) {
        if (!dStar || s.zdisjoint_points > sel[dStar].zdisjoint_points
            || (s.zdisjoint_points === sel[dStar].zdisjoint_points && s.split_points < sel[dStar].split_points)) dStar = vn;
    }
}
if (!dStar) {
    /* 全部不满足时取 clean_ret 最高、碎片代价最小者做“最不坏”参考（仍需如实标注 FAIL） */
    let best = null;
    for (const vn of D_CANDS) {
        const s = sel[vn]; if (s.clean_ret_min === null) continue;
        if (!best || (s.clean_ret_min > sel[best].clean_ret_min)) best = vn;
    }
    dStar = best;
}
log("");
log("== D sweep ==");
for (const vn of D_CANDS) log("  " + vn + "  " + JSON.stringify(sel[vn]));
log("D* = " + dStar + (dStar ? "" : "（无合格档位）"));

/* ---------------- 输出 JSON ---------------- */
function aggOut(vn) {
    const A = agg[vn];
    return { raw_mean: +(A.raw_total / A.frames).toFixed(2), filtered_mean: +(A.filtered_total / A.frames).toFixed(2),
        frag_total: A.frag_total, discarded_total: A.discarded_total, kept_total: A.kept_total,
        largest_ratio_mean: +(A.largest_ratio_sum / A.frames).toFixed(4), largest_pts_max: A.largest_pts_max,
        split_events: A.split_events, split_points: A.split_points,
        zdisjoint_events: A.zdisjoint_events, zdisjoint_points: A.zdisjoint_points, split_tall_events: A.split_tall_events,
        merge_events: A.merge_events, merge_points: A.merge_points, merge_tall_events: A.merge_tall_events,
        rt_cluster_ms: rtStats(A.rt_cluster), rt_total_ms: rtStats(A.rt_total) };
}
const out = {
    generated: new Date().toISOString(),
    inputs: { cur_sid: CUR_SID, ref_sid: REF_SID,
        cur_points: X.sha256File(path.join(CUR.dir, "points.bin")), ref_points: X.sha256File(path.join(REF.dir, "points.bin")),
        human_pipe_lib: X.sha256File(path.join(REPO, "pc_apps", "human_replay", "human_pipe_lib.js")),
        ab_impl: X.sha256File(path.join(HERE, "09_ab_shadow_impl.js")) },
    params: { vxy: X.VXY, vz_3d: X.VZ_3D, min_voxels: X.MIN_VOXELS, match_r: MATCH_R, occ: OCC,
        variants: VAR_NAMES, d_candidates: D_CANDS, d_star: dStar },
    baseline_replication: baseRep,
    equivalence: { frames: N_FRAMES, mismatch_count: eqMismatch.length, mismatches: eqMismatch.slice(0, 5) },
    aggregate: Object.fromEntries(VAR_NAMES.map(vn => [vn, aggOut(vn)])),
    d_selection: { sweep: sel, chosen: dStar },
    frames: perFrame,
    detail: detail,
};
fs.writeFileSync(path.join(HERE, "11_ab_real_frame_results.json"), JSON.stringify(out, null, 1) + "\n");

/* ---------------- 日志摘要 ---------------- */
log("");
log("== 聚合（165 帧；差分 = X vs A raw） ==");
for (const vn of VAR_NAMES) {
    const a = aggOut(vn);
    log("  " + vn.padEnd(8) + " raw " + a.raw_mean + "  filt " + a.filtered_mean + "  frag " + a.frag_total
        + "  discPts " + a.discarded_total + "  largest% " + (a.largest_ratio_mean * 100).toFixed(1)
        + " | split " + a.split_events + "(" + a.split_points + "pts, zdisj " + a.zdisjoint_events + "/" + a.zdisjoint_points + ")"
        + " merge " + a.merge_events + "(" + a.merge_points + "pts)"
        + " | ms cluster mean " + a.rt_cluster_ms.mean + " p95 " + a.rt_cluster_ms.p95 + " max " + a.rt_cluster_ms.max);
}
log("");
log("== 重点帧 retention / person-comp ==");
for (const d of detail) {
    const parts = [];
    for (const vn of ["A", "B", "C", dStar]) {
        if (!vn) continue;
        const q = d.variants[vn];
        parts.push(vn + ": ret=" + q.retention + " personPts=" + q.person_points + "/" + q.proxy_total
            + " upperComps=" + q.upper_comps + " filt=" + q.filtered_count + (q.diff ? " split=" + q.diff.splits + "(" + q.diff.split_pts + "pts,z" + q.diff.zdisjoint_pts + ")" : ""));
    }
    log("  f" + d.fi + " [" + d.kind + "] " + parts.join(" | "));
}
log("");
log("== D* = " + dStar + " 选择依据 ==");
if (dStar) log("  " + JSON.stringify(sel[dStar]));

/* ---------------- debug data（选定 D* 后重跑 debug 帧） ---------------- */
const DEBUG_FRAMES = [10, 30, 55, 63, 80, 92, 146, 150, 155, 160];
const dStarG = dStar ? +dStar.split("-G")[1] : 0.30;   /* D 全部不合格时，仅为可视化取最不利档 0.30 并如实标注 */
const dbg = { generated: out.generated, d_star: dStar || "D-G0.30(fallback)", d_g: dStarG,
    note: "flags: ref=reference(occ≥0.5,d<0.12) 命中；tall=z>1.45；proxy=人体/合并代理圆柱；compId 为 raw 分区",
    frames: [] };
for (const fi of DEBUG_FRAMES) {
    const fg = foreground(fi);
    const pts = fg.pts, nPts = pts.length / 4;
    const proxy = PROXY[fi];
    const P = [], F_ref = [], F_tall = [], F_proxy = [];
    for (let i = 0, p = 0; p < pts.length; p += 4, i++) {
        const x = pts[p], y = pts[p + 1], z = pts[p + 2];
        P.push([+x.toFixed(3), +y.toFixed(3), +z.toFixed(3)]);
        const rr = refScan(x, y, z);
        F_ref.push(rr.d0 !== null && rr.d0 < MATCH_R ? 1 : 0);
        F_tall.push(z > 1.45 ? 1 : 0);
        F_proxy.push(proxy ? (Math.hypot(x - proxy[0], y - proxy[1]) <= 0.55 ? 1 : 0) : 0);
    }
    const variants = {}, compStats = {};
    for (const [vn, vv] of [["A", ["A"]], ["B", ["B"]], ["C", ["C"]], ["D*", ["D", dStarG]]]) {
        const r = X.build(pts, vv[0], vv[1]);
        const f = X.filtered(r);
        const ids = new Int32Array(nPts);
        for (let i = 0; i < nPts; i++) ids[i] = r.pointComp[i];
        variants[vn] = Array.from(ids);
        const dRow = detail.find(d => d.fi === fi);
        const detailKey = vn === "D*" ? dStar : vn;
        const rows = dRow && detailKey && dRow.variants[detailKey] ? dRow.variants[detailKey].comps : [];
        compStats[vn] = rows.map(c => ({ id: c.id, n: c.n_points, nodes: c.n_nodes, bbox: c.bbox,
            label: c.label, joint: c.joint, ev: c.ev, ref: c.ref_frac, up: c.upper_pts }));
    }
    dbg.frames.push({ fi: fi, kind: KIND[fi] || "frag", proxy: proxy ? [proxy[0], proxy[1]] : null,
        points: P, ref: F_ref.join(""), tall: F_tall.join(""), proxyFlag: F_proxy.join(""),
        variants: variants, comps: compStats });
    console.log("[ab] debug data f" + fi);
}
fs.writeFileSync(path.join(HERE, "12_ab_debug_data.json"), JSON.stringify(dbg) + "\n");
fs.writeFileSync(path.join(HERE, "11_ab_real_frame_results.log"), L.join("\n") + "\n");
console.log("[ab] wrote 11_ab_real_frame_results.json/.log + 12_ab_debug_data.json");

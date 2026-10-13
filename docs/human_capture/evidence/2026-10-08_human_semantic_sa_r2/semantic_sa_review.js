"use strict";
/* S-A+ 独立复核（P1）：数据驱动选样 + 冻结阈值 + 留出验证。
 * 负样本 = 空场(233658)全部结构分量 + 四段中不含人的结构分量（自动选样，不手挑）；
 * 正样本 = 四段人体圆柱（仅作稳定性参考，不参与阈值调整）。
 * 阈值冻结自 r1（semantic_sa.js TH）。只读；wx 独占。 */
const fs = require("fs"), path = require("path"), crypto = require("crypto");
const ROOT = path.resolve(__dirname, "../../../..");
const PL = require(path.join(ROOT, "pc_apps/human_replay/human_pipe_lib.js"));
const R = require(path.join(ROOT, "pc_apps/human_replay/registration.js"));

const TH = { h_hdr: 0.10, w_max: 0.30, w_min: 0.06, c_min: 0.05, c_slab: 0.05, w_slab: 0.25, t_wide: 0.15,
    l_dmin: 0.08, l_dmax: 0.40, l_col: 0.10, a_hdr: 0.08, o_arm: 0.25, center_max: 0.20,
    min_pts: 400, min_bands: 3 };
const H_MIN = 0.10, VOX = 0.15, MIN_COMP_PTS = 400, MIN_FRAME_PTS = 200;

function leveling(root, sid, job) {
    try { return R.levelingBinding(root, sid, job); }
    catch (e) {
        const dir = path.join(root, "captures/leveled", job);
        const tf = JSON.parse(fs.readFileSync(path.join(dir, "tls/transform.json"), "utf8"));
        const report = JSON.parse(fs.readFileSync(path.join(dir, "report.json"), "utf8"));
        if (report.sid !== sid || tf.estimator !== "tls") throw e;
        return { tf };
    }
}
const _frames = {};
const framesOf = (sid, job) => _frames[sid] || (_frames[sid] = R.loadFrames(ROOT, sid, leveling(ROOT, sid, job)).frames);

function sub(pts, pred) {
    const xs = [], ys = [], zs = [];
    for (let i = 0; i < pts.length; i += 3) {
        const x = pts[i], y = pts[i + 1], z = pts[i + 2];
        if (pred(x, y, z)) { xs.push(x); ys.push(y); zs.push(z); }
    }
    const n = xs.length;
    const mean = a => a.reduce((s, v) => s + v, 0) / a.length;
    const std = a => { const m = mean(a); return Math.sqrt(a.reduce((s, v) => s + (v - m) ** 2, 0) / a.length); };
    return { xs, ys, zs, n, sx: n ? std(xs) : 0, sy: n ? std(ys) : 0, cx: n ? mean(xs) : 0, cy: n ? mean(ys) : 0 };
}
function kmeans1d(v) {
    const sorted = v.slice().sort((a, b) => a - b);
    let a = sorted[Math.floor(0.25 * v.length)], b = sorted[Math.floor(0.75 * v.length)];
    let la = v.map(() => true);
    for (let it = 0; it < 25; it++) {
        la = v.map(t => Math.abs(t - a) < Math.abs(t - b));
        const A = v.filter((_, i) => la[i]), B = v.filter((_, i) => !la[i]);
        if (!A.length || !B.length) break;
        a = A.reduce((s, t) => s + t, 0) / A.length;
        b = B.reduce((s, t) => s + t, 0) / B.length;
    }
    const A = v.filter((_, i) => la[i]), B = v.filter((_, i) => !la[i]);
    if (!A.length || !B.length) return null;
    const mean = a2 => a2.reduce((s, t) => s + t, 0) / a2.length;
    const sd = a2 => { const m = mean(a2); return Math.sqrt(a2.reduce((s, t) => s + (t - m) ** 2, 0) / a2.length); };
    return { d: Math.abs(a - b), bal: Math.min(A.length, B.length) / v.length, col: (sd(A) + sd(B)) / 2 };
}
function feats(pts) {  /* 与 r1 完全一致（冻结） */
    const n = pts.length / 3;
    if (n < TH.min_pts) return { ok: false, reason: "POINTS_LOW", n };
    let zmax = -1e9, zmin = 1e9;
    for (let i = 0; i < n; i++) { const z = pts[3 * i + 2]; if (z > zmax) zmax = z; if (z < zmin) zmin = z; }
    const tor = sub(pts, (x, y, z) => z >= 0.7 && z < 1.4);
    if (tor.n < 100) return { ok: false, reason: "TORSO_LOW", n };
    const w_torso = Math.max(tor.sx, tor.sy);
    const sv = [];
    for (let lo = 0.2; lo < 1.2; lo += 0.1) {
        const b = sub(pts, (x, y, z) => z >= lo && z < lo + 0.1);
        if (b.n >= 15) sv.push(b.sy);
    }
    const cv = sv.length >= 5 ? (() => { const m = sv.reduce((s, v) => s + v, 0) / sv.length; return Math.sqrt(sv.reduce((s, v) => s + (v - m) ** 2, 0) / sv.length) / m; })() : null;
    const legs = sub(pts, (x, y, z) => z >= 0.15 && z < 0.6);
    let legD = null, legCol = null, legsOK = false;
    if (legs.n >= 80) {
        const mx = legs.cx, my = legs.cy;
        const cxx = legs.xs.reduce((s, x) => s + (x - mx) ** 2, 0) / legs.n;
        const cyy = legs.ys.reduce((s, y) => s + (y - my) ** 2, 0) / legs.n;
        const cxy = legs.xs.reduce((s, x, i) => s + (x - mx) * (legs.ys[i] - my), 0) / legs.n;
        const th = 0.5 * Math.atan2(2 * cxy, cxx - cyy);
        const proj = legs.xs.map((x, i) => (x - mx) * Math.cos(th) + (legs.ys[i] - my) * Math.sin(th));
        const km = kmeans1d(proj);
        if (km) { legD = km.d; legCol = km.col;
            legsOK = (km.d >= TH.l_dmin && km.d <= TH.l_dmax && km.col <= TH.l_col) || km.col <= TH.l_col * 0.8; }
    }
    const top = sub(pts, (x, y, z) => z >= zmax - 0.25);
    const topMax = Math.max(top.sx, top.sy);
    const neck = sub(pts, (x, y, z) => z >= zmax - 0.50 && z < zmax - 0.25);
    const neckMax = neck.n >= 15 ? Math.max(neck.sx, neck.sy) : null;
    const off = Math.hypot(top.cx - tor.cx, top.cy - tor.cy);
    let head = false, arm = false;
    if (topMax <= TH.h_hdr && off <= TH.center_max && (neckMax === null || topMax < neckMax)) head = true;
    if (topMax <= TH.a_hdr && off >= TH.o_arm) {
        arm = true;
        const hb = sub(pts, (x, y, z) => z >= zmax - 0.55 && z < zmax - 0.25 && Math.hypot(x - tor.cx, y - tor.cy) <= 0.30);
        if (hb.n >= 50 && Math.max(hb.sx, hb.sy) <= TH.h_hdr) head = true;
    }
    const slab = cv !== null && cv <= TH.c_slab && w_torso >= TH.w_slab;
    const flat = topMax >= TH.t_wide;
    const torso = w_torso <= TH.w_max && w_torso >= TH.w_min && cv !== null && cv >= TH.c_min;
    let semantic, reason;
    if ((head && torso) || (legsOK && torso && !slab && !flat)) { semantic = "HUMAN_EVIDENCE"; reason = "STRUCT_OK"; }
    else if ((slab || flat) && !head && !arm) { semantic = "OBJECT_EVIDENCE"; reason = slab ? "SLAB" : "FLAT_TOP"; }
    else { semantic = "UNKNOWN"; reason = "INSUFFICIENT_OR_CONFLICT"; }
    return { ok: true, n, zmax: +zmax.toFixed(2), w_torso: +w_torso.toFixed(3), cv: cv === null ? null : +cv.toFixed(3),
        legsOK, head, arm, slab, flat, torso, semantic, reason };
}

/* ---- 数据驱动选样：原始场景（z>=0.10）XY 体素连通分量 ---- */
function harvest(sid, job) {
    const frames = framesOf(sid, job);
    const xs = [], ys = [], zs = [], fid = [];
    for (let fi = 0; fi < frames.length; fi++) {
        const f = frames[fi];
        for (let k = 0; k < f.length; k += 4) {
            const z = f[k + 2];
            if (z < H_MIN || z > 2.5) continue;
            xs.push(f[k]); ys.push(f[k + 1]); zs.push(z); fid.push(fi);
        }
    }
    const n = xs.length;
    const buf = new Float32Array(n * 4);
    for (let i = 0; i < n; i++) { buf[i * 4] = xs[i]; buf[i * 4 + 1] = ys[i]; buf[i * 4 + 2] = zs[i]; }
    const cs = PL.cluster_voxels(PL.voxelize(buf));
    const owner = new Map();
    cs.forEach((c, ci) => c.keys.forEach(k => owner.set(k, ci)));
    const comps = cs.map(() => ({ pts: [], fr: [] }));
    for (let i = 0; i < n; i++) {
        const ci = owner.get(PL.key_vox(xs[i], ys[i]));
        if (ci === undefined) continue;
        comps[ci].pts.push(xs[i], ys[i], zs[i]); comps[ci].fr.push(fid[i]);
    }
    return comps.map((c, ci) => {
        const npts = c.pts.length / 3;
        if (npts < MIN_COMP_PTS) return null;
        let sx = 0, sy = 0, zmin = 1e9, zmax = -1e9;
        for (let i = 0; i < c.pts.length; i += 3) {
            sx += c.pts[i]; sy += c.pts[i + 1];
            const z = c.pts[i + 2];
            if (z < zmin) zmin = z; if (z > zmax) zmax = z;
        }
        return { ci, sid, n: npts, cx: +(sx / npts).toFixed(2), cy: +(sy / npts).toFixed(2),
            zmin: +zmin.toFixed(2), zmax: +zmax.toFixed(2), pts: c.pts, fr: c.fr };
    }).filter(Boolean);
}
function perFrameVerdict(comp) {
    const byF = new Map();
    for (let i = 0; i < comp.fr.length; i++) {
        const f = comp.fr[i];
        if (!byF.has(f)) byF.set(f, []);
        byF.get(f).push(i);
    }
    let human = 0, other = 0, unknown = 0, used = 0;
    for (const idx of byF.values()) {
        if (idx.length < MIN_FRAME_PTS) continue;
        const p = [];
        for (const i of idx) p.push(comp.pts[i * 3], comp.pts[i * 3 + 1], comp.pts[i * 3 + 2]);
        const r = feats(p);
        used++;
        const v = r.ok ? r.semantic : "UNKNOWN";
        if (v === "HUMAN_EVIDENCE") human++; else if (v === "OBJECT_EVIDENCE") other++; else unknown++;
    }
    return { used, human, other, unknown,
        any_human: human > 0, majority: used > 0 && human > used / 2,
        whole: feats(comp.pts) };
}

const NEG_SESSIONS = [
    { sid: "cap_20261007_233658", job: "3c793d7bda0f4ced86b20ac8076e7b0e" },   // 空场：全部结构=非人
    { sid: "cap_20261007_215540", job: "21666bec7e7b44b2bdbbaa790bf4501b", person: [2.10, -0.57] },
    { sid: "cap_20261007_215623", job: "a9e1e01fa6644f93aa686daa330a5fcd", person: [2.14, -0.45] },
    { sid: "cap_20261007_215643", job: "e46d035de1b34378b841ca3bc2a1c8f6", person: [2.11, -0.36] },
];
const negComps = [];
for (const s of NEG_SESSIONS) {
    const comps = harvest(s.sid, s.job);
    let kept = 0;
    for (const c of comps) {
        let overlapsPerson = false;
        if (s.person) {
            for (let i = 0; i < c.pts.length; i += 3) {
                if ((c.pts[i] - s.person[0]) ** 2 + (c.pts[i + 1] - s.person[1]) ** 2 <= 0.55 * 0.55 && c.pts[i + 2] < 2.3) { overlapsPerson = true; break; }
            }
        }
        if (overlapsPerson) continue;
        kept++;
        const v = perFrameVerdict(c);
        negComps.push({ sid: s.sid, id: `${s.sid.slice(-6)}:c${c.ci}`, n: c.n, ctr: [c.cx, c.cy], z: [c.zmin, c.zmax],
            used: v.used, human: v.human, other: v.other, unknown: v.unknown, any_human: v.any_human, majority_human: v.majority,
            whole: v.whole.ok ? { semantic: v.whole.semantic, reason: v.whole.reason, cv: v.whole.cv, w: v.whole.w_torso, head: v.whole.head, arm: v.whole.arm, legs: v.whole.legsOK, torso: v.whole.torso, slab: v.whole.slab, flat: v.whole.flat } : v.whole });
        console.log(`NEG ${s.sid.slice(-6)}:c${c.ci} n=${c.n} frames=${v.used} human=${v.human} other=${v.other} unknown=${v.unknown} anyHuman=${v.any_human}`);
    }
    console.log(`  ${s.sid}: components=${comps.length} kept(no-person)=${kept}`);
}

/* 正样本（稳定性参考，非留出） */
const POS = [
    { id: "pos-540", sid: "cap_20261007_215540", job: "21666bec7e7b44b2bdbbaa790bf4501b", c: [2.10, -0.57] },
    { id: "pos-607", sid: "cap_20261007_215607", job: "2ed2cf6a4d2342ebb87f4e7fa68fdf3c", c: [2.13, -0.50] },
    { id: "pos-623", sid: "cap_20261007_215623", job: "a9e1e01fa6644f93aa686daa330a5fcd", c: [2.14, -0.45] },
    { id: "pos-643", sid: "cap_20261007_215643", job: "e46d035de1b34378b841ca3bc2a1c8f6", c: [2.11, -0.36] },
];
const posRows = [];
for (const p of POS) {
    const frames = framesOf(p.sid, p.job);
    const pts = [], fr = [];
    for (let fi = 0; fi < frames.length; fi++) {
        const f = frames[fi];
        for (let k = 0; k < f.length; k += 4) {
            const x = f[k], y = f[k + 1], z = f[k + 2];
            if (z < 0.05 || z > 2.3) continue;
            if ((x - p.c[0]) ** 2 + (y - p.c[1]) ** 2 > 0.55 * 0.55) continue;
            pts.push(x, y, z); fr.push(fi);
        }
    }
    const comp = { pts, fr };
    const v = perFrameVerdict(comp);
    posRows.push({ id: p.id, n: pts.length / 3, used: v.used, human: v.human, other: v.other, unknown: v.unknown,
        any_human: v.any_human, majority_human: v.majority });
    console.log(`POS ${p.id}: n=${pts.length / 3} frames=${v.used} human=${v.human} other=${v.other} unknown=${v.unknown} majorityHuman=${v.majority}`);
}

const anyHumanNeg = negComps.filter(c => c.any_human);
const majHumanNeg = negComps.filter(c => c.majority_human);
const summary = {
    thresholds_frozen_from: "semantic_sa.js r1 (c_slab=0.05)",
    neg_components: negComps.length,
    neg_any_human: anyHumanNeg.length,
    neg_majority_human: majHumanNeg.length,
    neg_any_human_list: anyHumanNeg.map(c => ({ id: c.id, n: c.n, ctr: c.ctr, z: c.z, human_frames: c.human, used: c.used, whole: c.whole })),
    pos_rows: posRows,
};
console.log(`SUMMARY: neg=${summary.neg_components} anyHuman=${summary.neg_any_human} majorityHuman=${summary.neg_majority_human}`);
const write = (n, v) => fs.writeFileSync(path.join(__dirname, n), JSON.stringify(v, null, 2) + "\n", { flag: "wx" });
write("review_results.json", { schema: 1, kind: "human_semantic_sa_review", thresholds: TH, summary, negatives: negComps,
    code_binding: { human_pipe_lib: crypto.createHash("sha256").update(fs.readFileSync(path.join(ROOT, "pc_apps/human_replay/human_pipe_lib.js"))).digest("hex"),
        script: crypto.createHash("sha256").update(fs.readFileSync(__filename)).digest("hex") } });
console.log("done.");

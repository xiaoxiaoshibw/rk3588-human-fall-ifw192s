"use strict";
/* S-A 离线原型：人体结构语义测试（直立/举臂 → 人/非人/不确定）。
 * 依据: docs/human_capture/HUMAN_SEMANTIC_CLASSIFICATION_DRAFT.md §3–§4（阈值为占位，S-A 校准）。
 * 样本: 现有正负样本（四段人×2 姿态 / WD01 / 箱子堆 / 低横条）+ 空场会话逐簇检查。
 * 只读生产代码；输出 wx 独占。ponytail: 复用 levelingBinding/loadFrames；特征=探针逻辑 node 移植。 */
const fs = require("fs"), path = require("path"), crypto = require("crypto");
const ROOT = path.resolve(__dirname, "../../../..");
const PL = require(path.join(ROOT, "pc_apps/human_replay/human_pipe_lib.js"));
const R = require(path.join(ROOT, "pc_apps/human_replay/registration.js"));

const TH = { h_hdr: 0.10, w_max: 0.30, c_min: 0.05, c_slab: 0.05, w_slab: 0.25, t_wide: 0.15,
    l_dmin: 0.08, l_dmax: 0.40, l_col: 0.10, a_hdr: 0.08, o_arm: 0.25, center_max: 0.20,
    min_pts: 400, min_bands: 3 };

function leveling(root, sid, job) {
    try { return R.levelingBinding(root, sid, job); }
    catch (e) {
        const dir = path.join(root, "captures/leveled", job);
        const tf = JSON.parse(fs.readFileSync(path.join(dir, "tls/transform.json"), "utf8"));
        const report = JSON.parse(fs.readFileSync(path.join(dir, "report.json"), "utf8"));
        const manifest = JSON.parse(fs.readFileSync(path.join(dir, "manifest.json"), "utf8"));
        if (report.sid !== sid || tf.estimator !== "tls" || manifest.job_id !== job) throw e;
        return { tf, note: "unchecked recommended (diagnostic only): " + e.message };
    }
}
const _frames = {};
const framesOf = (sid, job) => _frames[sid] || (_frames[sid] = R.loadFrames(ROOT, sid, leveling(ROOT, sid, job)).frames);
function collect(sid, job, sel, zlo, zhi) {
    const out = [];
    for (const f of framesOf(sid, job))
        for (let k = 0; k < f.length; k += 4) {
            const x = f[k], y = f[k + 1], z = f[k + 2];
            if (z < zlo || z > zhi || !sel(x, y)) continue;
            out.push(x, y, z);
        }
    return out;
}
const cyl = (cx, cy, r) => (x, y) => (x - cx) ** 2 + (y - cy) ** 2 <= r * r;
const box = (x0, x1, y0, y1) => (x, y) => x >= x0 && x <= x1 && y >= y0 && y <= y1;

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

function feats(pts) {
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
    let legD = null, legCol = null, legBal = null, legsOK = false;
    if (legs.n >= 80) {
        const mx = legs.cx, my = legs.cy;
        const cxx = legs.xs.reduce((s, x) => s + (x - mx) ** 2, 0) / legs.n;
        const cyy = legs.ys.reduce((s, y) => s + (y - my) ** 2, 0) / legs.n;
        const cxy = legs.xs.reduce((s, x, i) => s + (x - mx) * (legs.ys[i] - my), 0) / legs.n;
        const th = 0.5 * Math.atan2(2 * cxy, cxx - cyy);
        const proj = legs.xs.map((x, i) => (x - mx) * Math.cos(th) + (legs.ys[i] - my) * Math.sin(th));
        const km = kmeans1d(proj);
        if (km) { legD = km.d; legCol = km.col; legBal = km.bal;
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
    const torso = w_torso <= TH.w_max && cv !== null && cv >= TH.c_min;
    let semantic, reason;
    if ((head && torso) || (legsOK && torso && !slab && !flat)) { semantic = "HUMAN_EVIDENCE"; reason = "STRUCT_OK"; }
    else if ((slab || flat) && !head && !arm) { semantic = "OBJECT_EVIDENCE"; reason = slab ? "SLAB" : "FLAT_TOP"; }
    else { semantic = "UNKNOWN"; reason = "INSUFFICIENT_OR_CONFLICT"; }
    return { ok: true, n, zmax: +zmax.toFixed(2), zmin: +zmin.toFixed(2), w_torso: +w_torso.toFixed(3),
        cv: cv === null ? null : +cv.toFixed(3), legsOK, legD: legD === null ? null : +legD.toFixed(3),
        legCol: legCol === null ? null : +legCol.toFixed(3), legBal, topMax: +topMax.toFixed(3),
        off: +off.toFixed(3), neckMax: neckMax === null ? null : +neckMax.toFixed(3),
        head, arm, slab, flat, torso, semantic, reason };
}

const SAMPLES = [
    { id: "pos-540-person-stand", sid: "cap_20261007_215540", job: "21666bec7e7b44b2bdbbaa790bf4501b", sel: cyl(2.10, -0.57, 0.55), z: [0.05, 2.0], expect: "HUMAN" },
    { id: "pos-607-person-armup", sid: "cap_20261007_215607", job: "2ed2cf6a4d2342ebb87f4e7fa68fdf3c", sel: cyl(2.13, -0.50, 0.55), z: [0.05, 2.10], expect: "HUMAN" },
    { id: "pos-623-person-armup", sid: "cap_20261007_215623", job: "a9e1e01fa6644f93aa686daa330a5fcd", sel: cyl(2.14, -0.45, 0.55), z: [0.05, 2.10], expect: "HUMAN" },
    { id: "pos-643-person-stand", sid: "cap_20261007_215643", job: "e46d035de1b34378b841ca3bc2a1c8f6", sel: cyl(2.11, -0.36, 0.55), z: [0.05, 2.0], expect: "HUMAN" },
    { id: "neg-WD01-furniture", sid: "cap_20261002_223757", job: "015df3ff4e9743e38ea2236ea7da2d74", sel: cyl(3.50, -0.76, 0.55), z: [0.05, 2.0], expect: "NOT_HUMAN" },
    { id: "neg-crates", sid: "cap_20261007_215540", job: "21666bec7e7b44b2bdbbaa790bf4501b", sel: box(2.35, 3.30, -1.25, -0.50), z: [0.05, 1.6], expect: "NOT_HUMAN" },
    { id: "neg-low-bar", sid: "cap_20261007_215540", job: "21666bec7e7b44b2bdbbaa790bf4501b", sel: box(3.30, 5.20, -1.30, -0.60), z: [0.05, 0.9], expect: "NOT_HUMAN" },
];

const results = [];
for (const s of SAMPLES) {
    const pts = collect(s.sid, s.job, s.sel, s.z[0], s.z[1]);
    const f = feats(pts);
    const verdict = f.ok ? f.semantic : "UNKNOWN";
    const pass = s.expect === "HUMAN" ? verdict === "HUMAN_EVIDENCE" : verdict !== "HUMAN_EVIDENCE";
    results.push({ ...s, n_points: pts.length / 3, verdict, pass, feats: f });
    console.log(`${pass ? "PASS" : "FAIL"}  ${s.id.padEnd(26)} expect=${s.expect.padEnd(9)} -> ${verdict.padEnd(16)} ` +
        (f.ok ? `head=${f.head} arm=${f.arm} legs=${f.legsOK} torso=${f.torso} slab=${f.slab} flat=${f.flat} cv=${f.cv} w=${f.w_torso}` : f.reason));
}

/* 空场逐簇检查（P 链实例） */
function emptySceneCheck() {
    const sid = "cap_20261007_233658", job = "3c793d7bda0f4ced86b20ac8076e7b0e";
    const frames = framesOf(sid, job);
    const clean = frames.map(PL.denoise);
    const online = PL.build_static_map(clean);
    const counts = {}; let total = 0, human = 0, maxN = 0;
    for (let i = 0; i < frames.length; i++) {
        const fg = PL.extract_foreground(clean[i], online);
        const iso = PL.cleanup_isolated_fg(fg.fg_xyzi);
        const cs = PL.cluster_voxels(PL.voxelize(iso.xyzi)).filter(c => c.acc.n >= PL.PIPE.human_n_min);
        const owner = new Map(); cs.forEach((c, ci) => c.keys.forEach(k => owner.set(k, ci)));
        const ptsPer = cs.map(() => []);
        for (let k = 0; k < iso.xyzi.length; k += 4) {
            const ci = owner.get(PL.key_vox(iso.xyzi[k], iso.xyzi[k + 1]));
            if (ci !== undefined) ptsPer[ci].push(iso.xyzi[k], iso.xyzi[k + 1], iso.xyzi[k + 2]);
        }
        for (const p of ptsPer) {
            total++; maxN = Math.max(maxN, p.length / 3);
            const f = feats(p);
            const tag = f.ok ? f.semantic : "UNKNOWN(" + f.reason + ")";
            counts[tag] = (counts[tag] || 0) + 1;
            if (tag === "HUMAN_EVIDENCE") human++;
        }
    }
    return { sid, frames: frames.length, total_clusters: total, max_cluster_points: maxN, human_evidence: human, counts };
}
const empty = emptySceneCheck();
console.log(`empty-scene: clusters=${empty.total_clusters} human=${empty.human_evidence} counts=${JSON.stringify(empty.counts)}`);

const write = (n, v) => fs.writeFileSync(path.join(__dirname, n), JSON.stringify(v, null, 2) + "\n", { flag: "wx" });
write("semantic_sa_results.json", { schema: 1, kind: "human_semantic_sa_prototype",
    thresholds: TH, samples: results, empty_scene: empty,
    code_binding: { human_pipe_lib: crypto.createHash("sha256").update(fs.readFileSync(path.join(ROOT, "pc_apps/human_replay/human_pipe_lib.js"))).digest("hex"),
        registration: crypto.createHash("sha256").update(fs.readFileSync(path.join(ROOT, "pc_apps/human_replay/registration.js"))).digest("hex"),
        script: crypto.createHash("sha256").update(fs.readFileSync(__filename)).digest("hex") } });
console.log("done. fails=" + results.filter(r => !r.pass).length);

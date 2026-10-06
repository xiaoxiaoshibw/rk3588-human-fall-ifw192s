/* W03-R3.0 bucket report — read-only query over 02_audit_results.jsonl.
 * Usage: node 06_query_buckets.js [sid]
 * Prints persistent XY buckets (0.25m) with median audit stats sorted by frame coverage,
 * then per-frame rows of every green bucket, then a replica-vs-pipeline single-frame self check.
 * Column notes: exact/nb/miss = map availability ratios (distance ignored); d50/d95 = point-to-nearest
 * static centroid (neighbor-hit points only); pv = persistent_voxel_ratio (own-voxel occ >= 0.50);
 * o50/o1 = median own-voxel occupancy under >=2 / >=1 per-frame hit rule; low/jit/nsnb/nohit = share
 * of cluster points whose own voxel failed as occ_low / jitter / no_strong_nb / never-hit(>=2).
 */
"use strict";
const fs = require("fs");
const path = require("path");
const HERE = __dirname;
const REPO = path.resolve(HERE, "..", "..", "..", "..");
const RP = path.join(REPO, "pc_apps", "human_replay");
const RL = require(path.join(RP, "human_replay_lib.js"));
const PL = require(path.join(RP, "human_pipe_lib.js"));
const sid = process.argv[2] || "cap_20261002_223757";

const rows = fs.readFileSync(path.join(HERE, "02_audit_results.jsonl"), "utf8")
    .trim().split("\n").map(JSON.parse).filter(r => r.sid === sid);
const stats = JSON.parse(fs.readFileSync(path.join(HERE, "03_audit_stats.json"), "utf8"));
const S = stats.per_session[sid];

function med(a) { if (!a.length) return null; const s = a.slice().sort((x, y) => x - y); return s[Math.floor((s.length - 1) / 2)]; }
function r(v, d) { return v === null || v === undefined ? "  -  " : ("" + v).slice(0, d === undefined ? 5 : d).padEnd(d === undefined ? 5 : d); }
function keyOf(x, y) { return Math.floor(x / 0.25) + "," + Math.floor(y / 0.25); }
function m(rowVec) { return med(rowVec.filter(v => v !== null)); }

const buckets = new Map();
for (const row of rows) {
    const k = keyOf(row.cx, row.cy);
    if (!buckets.has(k)) buckets.set(k, []);
    buckets.get(k).push(row);
}
const list = [];
buckets.forEach((rws, k) => {
    list.push({
        k, frames: new Set(rws.map(x => x.f)).size,
        n_med: med(rws.map(x => x.n)), n_max: Math.max.apply(null, rws.map(x => x.n)),
        ex: m(rws.map(x => x.bg_exact_hit_ratio)), nbx: m(rws.map(x => x.bg_neighbor_hit_ratio)),
        ms: m(rws.map(x => x.bg_miss_ratio)), d50: m(rws.map(x => x.bg_min_dist_p50)),
        d95: m(rws.map(x => x.bg_min_dist_p95)), pv: m(rws.map(x => x.persistent_voxel_ratio)),
        o50: m(rws.map(x => x.occ_p50)), o1: m(rws.map(x => x.occ1_p50)),
        low: m(rws.map(x => x.why_occ_low)), jit: m(rws.map(x => x.why_jitter)),
        nsnb: m(rws.map(x => x.why_no_strong_nb)), nohit: m(rws.map(x => x.why_no_hits)),
        m15: m(rws.map(x => x.bg_match_r015_ratio)), m20: m(rws.map(x => x.bg_match_r020_ratio)),
        m5: m(rws.map(x => x.centroid_motion_5f)),
        green: rws.filter(x => x.track_confirmed).length,
        joints: rws.reduce((a, x) => { a[x.joint] = (a[x.joint] || 0) + 1; return a; }, {}),
    });
});
list.sort((a, b) => b.frames - a.frames || b.n_max - a.n_max);

console.log("== " + sid + "  frames=" + S.summary.frames + "  map=" + JSON.stringify(S.summary.map)
    + "  cluster_rows=" + rows.length + "  green_rows=" + S.summary.green_rows);
console.log("   bucket    frames n_med n_max | exact nb    miss  | d50   d95   | pv    o50   o1    | low   jit   nsnb  nohit | m5    green joints");
for (const b of list.slice(0, 30)) {
    console.log("   " + b.k.padEnd(9) + r(b.frames, 5) + "  " + r(b.n_med, 5) + " " + r(b.n_max, 5) + " | "
        + r(b.ex) + " " + r(b.nbx) + " " + r(b.ms) + " | " + r(b.d50) + " " + r(b.d95) + " | "
        + r(b.pv) + " " + r(b.o50) + " " + r(b.o1) + " | " + r(b.low) + " " + r(b.jit) + " " + r(b.nsnb) + " " + r(b.nohit)
        + " | " + r(b.m5) + " " + r(b.green, 5) + " " + JSON.stringify(b.joints));
}
console.log("-- rows of green buckets (all frames) --");
for (const b of list.filter(x => x.green > 0)) {
    console.log("   bucket " + b.k);
    for (const row of rows.filter(x => keyOf(x.cx, x.cy) === b.k && x.track_confirmed)) {
        console.log("     f=" + row.f + " ci=" + row.ci + " trk=" + row.track_id + " n=" + row.n
            + " c=(" + row.cx + "," + row.cy + "," + row.cz + ") h=" + row.height_m
            + " nb=" + row.bg_neighbor_hit_ratio + " exact=" + row.bg_exact_hit_ratio
            + " miss=" + row.bg_miss_ratio + " d50=" + row.bg_min_dist_p50 + " d95=" + row.bg_min_dist_p95
            + " pv=" + row.persistent_voxel_ratio + " occ50=" + row.occ_p50 + " occ1=" + row.occ1_p50
            + " why(low/jit/nsnb/nohit)=" + row.why_occ_low + "/" + row.why_jitter + "/" + row.why_no_strong_nb + "/" + row.why_no_hits
            + " m5=" + row.centroid_motion_5f
            + " joint=" + row.joint + " shape=" + row.human_shape);
    }
}

/* 复刻自检：frame_clusters vs 生产 pipeline_frame（同帧同 map，应逐簇一致） */
(function check(sid, frameIdx) {
    const dir = path.join(REPO, "captures", "remote", sid);
    const meta = JSON.parse(fs.readFileSync(path.join(dir, "meta.json"), "utf8"));
    const raw = fs.readFileSync(path.join(dir, "points.bin"));
    const f32 = new Float32Array(raw.buffer, raw.byteOffset, raw.byteLength / 4);
    const frames = RL.frame_slice(meta);
    const STRIDE = RL.STRIDE_F32;
    const ded = frames.map(f => PL.denoise(RL.strided_f32_copy(f32, f.start_pts, f.count, STRIDE)));
    const sm = PL.build_static_map(ded, { drop_ground: true });
    const slice = RL.strided_f32_copy(f32, frames[frameIdx].start_pts, frames[frameIdx].count, STRIDE);
    const prod = PL.pipeline_frame(slice, frameIdx, { static_keys: sm, tracker: new PL.Tracker() });
    /* 复刻（与 01_audit_static_leakage.js 相同步骤） */
    const clean = PL.denoise(slice);
    const fg = PL.extract_foreground(clean, sm);
    const iso = PL.cleanup_isolated_fg(fg.fg_xyzi);
    const rawC = PL.cluster_voxels(PL.voxelize(iso.xyzi));
    const ev = PL.evidence_postpass(iso.xyzi, rawC);
    const mineC = [];
    for (let ci = 0; ci < rawC.length; ci++) {
        const f = PL.cluster_features(rawC[ci]);
        if (!f.ok) continue;
        const c = PL.classify_human(f);
        f.label = c.label; f.evidence = ev.clusters_extra[ci];
        f.evidence_tag = PL.evidence_label(f.evidence); f.joint = PL.joint_status(f);
        mineC.push(f);
    }
    let ok = mineC.length === prod.clusters.length;
    if (ok) for (let i = 0; i < mineC.length; i++) {
        const a = mineC[i], b = prod.clusters[i];
        if (Math.abs(a.cx - b.cx) > 1e-9 || a.n !== b.n || a.joint !== b.joint) { ok = false; break; }
    }
    console.log("-- replica check " + sid + " f" + frameIdx + ": mine=" + mineC.length
        + " pipeline=" + prod.clusters.length + " -> " + (ok ? "IDENTICAL" : "MISMATCH"));
})(sid, sid === "synth_bend_v1" ? 10 : 16);

/* W03-R2.6b 三会话 AB：R2 baseline vs R2.6（旧清理复刻） vs R2.6b（生产 pipeline_frame）
 *
 * before 路径 = 用导出纯函数逐字复刻 R2 的 foreground→cluster 步骤（无清理）；
 * r26 路径   = 同前 + R2.6 旧清理复刻（3D isolated → 立即删，无拓扑保护）；
 * r26b 路径  = 生产 pipeline_frame（拓扑保护型清理）。
 * 输出：04_r26b_ab_results.json（汇总）/ 05_r26b_ab_results.jsonl（逐帧）/
 *       06_frame16_regression.json（golden frame16 对照）。
 * 用法：node 03_r26b_ab.js cap_20261002_223757 synth_bend_v1 cap_20261004_203349
 */
"use strict";
const fs = require("fs");
const path = require("path");
const HERE = __dirname;
const REPO = path.resolve(HERE, "..", "..", "..", "..");
const RP = path.join(REPO, "pc_apps", "human_replay");
const RL = require(path.join(RP, "human_replay_lib.js"));
const PL = require(path.join(RP, "human_pipe_lib.js"));

/* R2.6 旧清理复刻（仅 AB 对照；key 编码常量与生产 key_bg 同源冻结） */
const BG_BASE = 8192, BG_OFF = 4096;
function bg_key_ijk(ix, iy, iz) { return ((ix + BG_OFF) * BG_BASE + (iy + BG_OFF)) * BG_BASE + (iz + BG_OFF); }
function bg_decode(key) {
    let iz = key % BG_BASE; key = (key - iz) / BG_BASE;
    let iy = key % BG_BASE;
    return [(key - iy) / BG_BASE - BG_OFF, iy - BG_OFF, iz - BG_OFF];
}
function cleanup_r26_replica(xyzi) {
    const before = xyzi.length / 4;
    const counts = new Map();
    for (let i = 0; i < xyzi.length; i += 4) {
        const k = PL.key_bg(xyzi[i], xyzi[i + 1], xyzi[i + 2]);
        counts.set(k, (counts.get(k) || 0) + 1);
    }
    const doomed = new Set();
    counts.forEach((n, key) => {
        if (n > 1) return;
        const ij = bg_decode(key);
        for (let a = -1; a <= 1; a++) for (let b = -1; b <= 1; b++) for (let c = -1; c <= 1; c++) {
            if (!a && !b && !c) continue;
            if (counts.has(bg_key_ijk(ij[0] + a, ij[1] + b, ij[2] + c))) return;
        }
        doomed.add(key);
    });
    if (!doomed.size) return { xyzi, removed_points: 0, removed_voxels: 0, after: before };
    const out = [];
    for (let i = 0; i < xyzi.length; i += 4) {
        if (doomed.has(PL.key_bg(xyzi[i], xyzi[i + 1], xyzi[i + 2]))) continue;
        out.push(xyzi[i], xyzi[i + 1], xyzi[i + 2], xyzi[i + 3]);
    }
    return { xyzi: new Float32Array(out), removed_points: before - out.length / 4,
             removed_voxels: doomed.size, after: out.length / 4 };
}

/* R2 的 foreground→cluster 复刻（与 ab_r26.js 同口径） */
function clustersOf(pts, tracker, frameIdx) {
    const rawC = PL.cluster_voxels(PL.voxelize(pts));
    const ev = PL.evidence_postpass(pts, rawC);
    const clusters = [];
    for (let i = 0; i < rawC.length; i++) {
        const f = PL.cluster_features(rawC[i]);
        if (!f.ok) continue;
        const c = PL.classify_human(f);
        f.label = c.label; f.confidence = c.confidence; f.reasons = c.reasons;
        f.evidence = ev.clusters_extra[i];
        f.evidence_tag = PL.evidence_label(f.evidence);
        f.joint = PL.joint_status(f);
        clusters.push(f);
    }
    tracker.tick(frameIdx, clusters);
    return clusters;
}
function uiCounts(clusters) {
    const o = { green: 0, candidate: 0, gray: 0 };
    for (const c of clusters) {
        if (c.joint === "NON_HUMAN") o.gray++;
        else if (c.joint === "HUMAN_CANDIDATE") o.candidate++;
        else o[c.track_confirmed ? "green" : "candidate"]++;
    }
    return o;
}
function pct(sorted, q) {
    if (!sorted.length) return 0;
    return sorted[Math.min(sorted.length - 1, Math.ceil(q * sorted.length) - 1)];
}
function biggest(cl) { return cl.length ? cl.reduce((a, b) => (b.n > a.n ? b : a)) : null; }
function clusterBrief(c) {
    return { cx: +c.cx.toFixed(2), cy: +c.cy.toFixed(2), zmin: +c.zmin.toFixed(2),
             h: +c.height_m.toFixed(2), n: c.n, joint: c.joint,
             tag: c.evidence_tag && c.evidence_tag.label, confirmed: !!c.track_confirmed };
}
const sum = a => a.reduce((x, y) => x + y, 0);

const jsonl = [];
const summaries = [];
let frame16 = null;

function run(sid) {
    const dir = path.join(REPO, "captures", "remote", sid);
    const meta = JSON.parse(fs.readFileSync(path.join(dir, "meta.json"), "utf8"));
    const raw = fs.readFileSync(path.join(dir, "points.bin"));
    const f32 = new Float32Array(raw.buffer, raw.byteOffset, raw.byteLength / 4);
    const frames = RL.frame_slice(meta);
    const STRIDE = RL.STRIDE_F32;
    const ded = frames.map(f => PL.denoise(RL.strided_f32_copy(f32, f.start_pts, f.count, STRIDE)));
    const sm = PL.build_static_map(ded, { drop_ground: true });
    const tb = new PL.Tracker(), tc = new PL.Tracker(), td = new PL.Tracker();

    const tot = { cl: [0, 0, 0], green: [0, 0, 0], cand: [0, 0, 0], gray: [0, 0, 0] };
    const removed26 = [], removed26b = [], fgArr = [];
    let vetoed = 0, preserved = 0, candidates = 0;
    const splitFrames = { r26: [], r26b: [] };       /* cl_after > cl_r2（cleanup-induced split） */
    const internalSplit = [];                        /* 生产诊断 cleanup_split_delta > 0 */
    const newGreenFrames = { r26: [], r26b: [] };    /* green_after > green_r2 */
    const person = { r26: [], r26b: [] };

    for (let i = 0; i < frames.length; i++) {
        const f = frames[i];
        const slice = RL.strided_f32_copy(f32, f.start_pts, f.count, STRIDE);
        const clean = PL.denoise(slice);
        const fg = PL.extract_foreground(clean, sm);

        const cb = clustersOf(fg.fg_xyzi, tb, i);                                  /* R2 */
        const iso26 = cleanup_r26_replica(fg.fg_xyzi);
        const c26 = clustersOf(iso26.xyzi, tc, i);                                 /* R2.6 */
        const r = PL.pipeline_frame(slice, i, { static_keys: sm, tracker: td });   /* R2.6b */
        const ca = r.clusters;

        const ub = uiCounts(cb), u26 = uiCounts(c26), ua = uiCounts(ca);
        tot.cl[0] += cb.length; tot.cl[1] += c26.length; tot.cl[2] += ca.length;
        tot.green[0] += ub.green; tot.green[1] += u26.green; tot.green[2] += ua.green;
        tot.cand[0] += ub.candidate; tot.cand[1] += u26.candidate; tot.cand[2] += ua.candidate;
        tot.gray[0] += ub.gray; tot.gray[1] += u26.gray; tot.gray[2] += ua.gray;

        removed26.push(iso26.removed_points);
        removed26b.push(r.actually_removed_points);
        fgArr.push(fg.n_fg);
        vetoed += r.xy_topology_vetoed;
        preserved += r.xy_cells_preserved_by_other_z;
        candidates += r.isolated_3d_candidates;

        if (c26.length > cb.length) splitFrames.r26.push(i);
        if (ca.length > cb.length) splitFrames.r26b.push(i);
        if (r.cleanup_split_delta > 0) internalSplit.push(i);
        if (u26.green > ub.green) newGreenFrames.r26.push(i);
        if (ua.green > ub.green) newGreenFrames.r26b.push(i);

        const bB = biggest(cb);
        if (bB) {
            const a26 = biggest(c26), a26b = biggest(ca);
            person.r26.push({ f: i, n_before: bB.n, n_after: a26 ? a26.n : 0,
                              ret: a26 ? +(a26.n / bB.n).toFixed(4) : 0 });
            person.r26b.push({ f: i, n_before: bB.n, n_after: a26b ? a26b.n : 0,
                               ret: a26b ? +(a26b.n / bB.n).toFixed(4) : 0 });
        }

        jsonl.push({ sid, f: i, fg: fg.n_fg,
            removed_r26: iso26.removed_points, removed_r26b: r.actually_removed_points,
            cand: r.isolated_3d_candidates, vetoed: r.xy_topology_vetoed,
            preserved_cells: r.xy_cells_preserved_by_other_z,
            cl_r2: cb.length, cl_r26: c26.length, cl_r26b: ca.length,
            split_delta_internal: r.cleanup_split_delta, regression_flag: r.topology_regression,
            green_r2: ub.green, green_r26: u26.green, green_r26b: ua.green,
            cand_r2: ub.candidate, cand_r26: u26.candidate, cand_r26b: ua.candidate,
            gray_r2: ub.gray, gray_r26: u26.gray, gray_r26b: ua.gray });

        if (sid === "cap_20261002_223757" && i === 16) {
            frame16 = { sid, frame: i, fg: fg.n_fg,
                r2: cb.map(clusterBrief), r26: c26.map(clusterBrief), r26b: ca.map(clusterBrief),
                removed_r26: iso26.removed_points, removed_r26b: r.actually_removed_points,
                vetoed: r.xy_topology_vetoed,
                split_r26: c26.length > cb.length, split_r26b: ca.length > cb.length };
        }
    }

    const rs26 = person.r26.map(p => p.ret).sort((a, b) => a - b);
    const rsB = person.r26b.map(p => p.ret).sort((a, b) => a - b);
    const p26 = { frames_before: person.r26.length, frames_after: person.r26.filter(p => p.n_after > 0).length,
                  retention_min: rs26[0], retention_p5: pct(rs26, 0.05), retention_median: pct(rs26, 0.5) };
    const pB = { frames_before: person.r26b.length, frames_after: person.r26b.filter(p => p.n_after > 0).length,
                 retention_min: rsB[0], retention_p5: pct(rsB, 0.05), retention_median: pct(rsB, 0.5) };
    const removedSorted = removed26b.slice().sort((a, b) => a - b);

    const rows = jsonl.filter(x => x.sid === sid);
    const acceptance = {
        cleanup_split_zero: splitFrames.r26b.length === 0 && internalSplit.length === 0,
        cleanup_new_green_zero: newGreenFrames.r26b.length === 0,
    };
    if (sid === "synth_bend_v1") {
        acceptance.person_190_190 = pB.frames_after === pB.frames_before && pB.frames_before === 190;
        acceptance.retention_ge_r26 = pB.retention_min >= p26.retention_min
            && pB.retention_p5 >= p26.retention_p5 && pB.retention_median >= p26.retention_median;
    }
    if (sid === "cap_20261004_203349") {
        acceptance.empty_no_new_cluster = rows.every(x => x.cl_r26b <= x.cl_r2);
        acceptance.empty_no_new_green = rows.every(x => x.green_r26b <= x.green_r2);
        acceptance.empty_no_new_purple = rows.every(x => x.cand_r26b <= x.cand_r2);
    }

    const s = {
        sid, frames: frames.length,
        fg_points: { median: pct(fgArr.slice().sort((a, b) => a - b), 0.5),
                     p95: pct(fgArr.slice().sort((a, b) => a - b), 0.95) },
        totals: { clusters: { r2: tot.cl[0], r26: tot.cl[1], r26b: tot.cl[2] },
                  green: { r2: tot.green[0], r26: tot.green[1], r26b: tot.green[2] },
                  candidate: { r2: tot.cand[0], r26: tot.cand[1], r26b: tot.cand[2] },
                  gray: { r2: tot.gray[0], r26: tot.gray[1], r26b: tot.gray[2] } },
        removed: { r26_total: sum(removed26), r26b_total: sum(removed26b),
                   r26b_median: pct(removedSorted, 0.5), r26b_p95: pct(removedSorted, 0.95),
                   r26b_max: pct(removedSorted, 1),
                   r26b_candidates_total: candidates, r26b_vetoed_total: vetoed,
                   r26b_preserved_cells_total: preserved },
        cleanup_split_frames: { r26: splitFrames.r26, r26b: splitFrames.r26b },
        internal_split_frames_r26b: internalSplit,
        new_green_frames: { r26: newGreenFrames.r26, r26b: newGreenFrames.r26b },
        person_retention: { r26: p26, r26b: pB },
        frame16_check: sid === "cap_20261002_223757" && frame16
            ? { split_r26: frame16.split_r26, split_r26b: frame16.split_r26b,
                r2_clusters: frame16.r2.length, r26_clusters: frame16.r26.length,
                r26b_clusters: frame16.r26b.length } : null,
        acceptance,
    };
    summaries.push(s);
    return s;
}

for (const sid of process.argv.slice(2)) run(sid);

fs.writeFileSync(path.join(HERE, "04_r26b_ab_results.json"), JSON.stringify(summaries, null, 1));
fs.writeFileSync(path.join(HERE, "05_r26b_ab_results.jsonl"), jsonl.map(r => JSON.stringify(r)).join("\n") + "\n");
if (frame16) fs.writeFileSync(path.join(HERE, "06_frame16_regression.json"), JSON.stringify(frame16, null, 1));

for (const s of summaries) {
    console.log(s.sid + "  frames=" + s.frames
        + "  clusters r2/r26/r26b=" + s.totals.clusters.r2 + "/" + s.totals.clusters.r26 + "/" + s.totals.clusters.r26b
        + "  green=" + s.totals.green.r2 + "/" + s.totals.green.r26 + "/" + s.totals.green.r26b
        + "  removed r26/r26b=" + s.removed.r26_total + "/" + s.removed.r26b_total
        + "  vetoed=" + s.removed.r26b_vetoed_total);
    console.log("  acceptance: " + JSON.stringify(s.acceptance));
}

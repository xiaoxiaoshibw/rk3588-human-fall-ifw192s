/* W03-R2.6 三组 AB：R2 baseline vs R2 + 保守孤立前景清理
 *
 * before 路径 = 用导出纯函数逐字复刻 R2 的 foreground→cluster 步骤（清理前），
 * after  路径 = 生产 pipeline_frame（含 R2.6 清理）。
 * 输出：每帧诊断 + 汇总（删除量分位、簇/联合判定/UI 颜色 before/after）。
 *
 * 用法：node ab_r26.js <sid> [sid2 ...]
 */
"use strict";
const fs = require("fs");
const path = require("path");
const REPO = path.resolve(__dirname, "..", "..", "..", "..");
const RP = path.join(REPO, "pc_apps", "human_replay");
const RL = require(path.join(RP, "human_replay_lib.js"));
const PL = require(path.join(RP, "human_pipe_lib.js"));

/* R2 的 foreground→cluster 复刻（无清理）；生产 pipeline_frame 只多一个 cleanup 步 */
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
    const o = { green: 0, candidate: 0, gray: 0, joint: {} };
    for (const c of clusters) {
        o.joint[c.joint] = (o.joint[c.joint] || 0) + 1;
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

function run(sid) {
    const dir = path.join(REPO, "captures", "remote", sid);
    const meta = JSON.parse(fs.readFileSync(path.join(dir, "meta.json"), "utf8"));
    const raw = fs.readFileSync(path.join(dir, "points.bin"));
    const f32 = new Float32Array(raw.buffer, raw.byteOffset, raw.byteLength / 4);
    const frames = RL.frame_slice(meta);
    const STRIDE = RL.STRIDE_F32;
    const ded = frames.map(f => PL.denoise(RL.strided_f32_copy(f32, f.start_pts, f.count, STRIDE)));
    const sm = PL.build_static_map(ded, { drop_ground: true });
    const tb = new PL.Tracker(), ta = new PL.Tracker();

    const perFrame = [];
    const tot = { cl_b: 0, cl_a: 0, g_b: 0, g_a: 0, c_b: 0, c_a: 0, gy_b: 0, gy_a: 0 };
    const person = [];
    for (let i = 0; i < frames.length; i++) {
        const f = frames[i];
        const slice = RL.strided_f32_copy(f32, f.start_pts, f.count, STRIDE);
        const clean = PL.denoise(slice);
        const fg = PL.extract_foreground(clean, sm);
        const cb = clustersOf(fg.fg_xyzi, tb, i);                       /* before */
        const r = PL.pipeline_frame(slice, i, { static_keys: sm, tracker: ta });  /* after */
        const ca = r.clusters;
        const ub = uiCounts(cb), ua = uiCounts(ca);
        tot.cl_b += cb.length; tot.cl_a += ca.length;
        tot.g_b += ub.green; tot.g_a += ua.green;
        tot.c_b += ub.candidate; tot.c_a += ua.candidate;
        tot.gy_b += ub.gray; tot.gy_a += ua.gray;
        perFrame.push({
            f: i,
            fg_before: fg.n_fg, fg_after: r.fg_after_cleanup,
            removed: r.iso_removed_points, ratio: +r.iso_removed_ratio.toFixed(5),
            fg_voxels: r.fg_voxels, removed_voxels: r.iso_removed_voxels,
            clusters_before: cb.length, clusters_after: ca.length,
            green_before: ub.green, green_after: ua.green,
            cand_before: ub.candidate, cand_after: ua.candidate,
            gray_before: ub.gray, gray_after: ua.gray,
        });
        if (cb.length) {
            const bigB = cb.reduce((a, b) => (b.n > a.n ? b : a));
            const bigA = ca.length ? ca.reduce((a, b) => (b.n > a.n ? b : a)) : null;
            person.push({ f: i, n_before: bigB.n, n_after: bigA ? bigA.n : 0,
                          kept: !!bigA, ret: bigA ? +(bigA.n / bigB.n).toFixed(4) : 0 });
        }
    }
    const removed = perFrame.map(p => p.removed).sort((a, b) => a - b);
    const sum = perFrame.reduce((a, p) => a + p.removed, 0);
    const keptFrames = person.filter(p => p.kept).length;
    const rets = person.map(p => p.ret).sort((a, b) => a - b);
    const out = {
        sid, frames: frames.length,
        removed: { total: sum, median: pct(removed, 0.5), p95: pct(removed, 0.95), max: pct(removed, 1),
                   removed_voxels_total: perFrame.reduce((a, p) => a + p.removed_voxels, 0) },
        clusters: { before: tot.cl_b, after: tot.cl_a },
        ui_colors: { green_before: tot.g_b, green_after: tot.g_a,
                     candidate_before: tot.c_b, candidate_after: tot.c_a,
                     gray_before: tot.gy_b, gray_after: tot.gy_a },
        person_clusters: person.length ? {
            frames_with_person_before: person.length,
            frames_with_person_after: keptFrames,
            n_before_median: pct(person.map(p => p.n_before).sort((a, b) => a - b), 0.5),
            n_after_median: pct(person.map(p => p.n_after).sort((a, b) => a - b), 0.5),
            retention_min: rets[0], retention_p5: pct(rets, 0.05), retention_median: pct(rets, 0.5),
        } : null,
        per_frame: perFrame,
    };
    console.log(JSON.stringify(out));
    return out;
}

const results = [];
for (const sid of process.argv.slice(2)) results.push(run(sid));
fs.writeFileSync(path.join(__dirname, "ab_r26_results.json"), JSON.stringify(results, null, 1));

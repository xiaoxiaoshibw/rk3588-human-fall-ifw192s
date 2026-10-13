"use strict";
/* 阶段0 Arm C：空场模板（cap_20261007_233658）保留率诊断。
 * 口径 = S 链形态（既有 R3.x 机制，离线）：registered cloud → 参考图匹配 → 在线图匹配
 *        → cleanup/聚类/判定/跟踪。参考图/配准版本全部记录 SHA。只诊断，不改生产。
 * ponytail: 复用 registration.js 产出的 artifact 与既有 extract/ownership；固定圆柱区域。 */
const fs = require("fs"), path = require("path"), crypto = require("crypto");
const ROOT = path.resolve(__dirname, "../../../..");
const PL = require(path.join(ROOT, "pc_apps/human_replay/human_pipe_lib.js"));
const R = require(path.join(ROOT, "pc_apps/human_replay/registration.js"));
const M = require(path.join(ROOT, "pc_apps/human_replay/registration_method.js"));
const audit = require(path.join(__dirname, "audit_lib.js"));

const REF = "cap_20261007_233658", REFJOB = "3c793d7bda0f4ced86b20ac8076e7b0e";
const SESSIONS = [
    { sid: "cap_20261007_215540", job: "21666bec7e7b44b2bdbbaa790bf4501b", center: [2.10, -0.57] },
    { sid: "cap_20261007_215607", job: "2ed2cf6a4d2342ebb87f4e7fa68fdf3c", center: [2.13, -0.50] },
    { sid: "cap_20261007_215623", job: "a9e1e01fa6644f93aa686daa330a5fcd", center: [2.14, -0.45] },
    { sid: "cap_20261007_215643", job: "e46d035de1b34378b841ca3bc2a1c8f6", center: [2.11, -0.36] },
];
const RADIUS = 0.55, ZLO = 0.05, ZHI = 2.30, R2 = RADIUS * RADIUS;
const shaFile = f => crypto.createHash("sha256").update(fs.readFileSync(f)).digest("hex");
const write = (n, v) => fs.writeFileSync(path.join(__dirname, n), JSON.stringify(v, null, 2) + "\n", { flag: "wx" });
const keyAt = (a, k) => a[k] + "," + a[k + 1] + "," + a[k + 2] + "," + a[k + 3];
const stat = a => { const b = a.slice().sort((x, y) => x - y); return { min: b[0], p50: b[b.length >> 1], max: b[b.length - 1] }; };
function summarizeCluster(c) {
    return { n: c.n, cx: c.cx, cy: c.cy, cz: c.cz, zmin: c.zmin, zmax: c.zmax, height_m: c.height_m,
        width_m: c.width_m, depth_m: c.depth_m, radius_m: c.radius_m, upcos: c.upcos, label: c.label,
        confidence: c.confidence, joint: c.joint, evidence_tag: c.evidence_tag ? c.evidence_tag.label : null,
        reasons: c.reasons, track_id: c.track_id ?? null, track_confirmed: !!c.track_confirmed };
}
const codeBinding = { human_pipe_lib: shaFile(path.join(ROOT, "pc_apps/human_replay/human_pipe_lib.js")),
    registration: shaFile(path.join(ROOT, "pc_apps/human_replay/registration.js")),
    registration_method: shaFile(path.join(ROOT, "pc_apps/human_replay/registration_method.js")),
    audit_lib: shaFile(path.join(__dirname, "audit_lib.js")) };

/* ---- 空场自身复验（P 口径）---- */
{
    const lv = R.levelingBinding(ROOT, REF, REFJOB);
    const frames = R.loadFrames(ROOT, REF, lv).frames;
    const clean = frames.map(PL.denoise);
    const online = PL.build_static_map(clean);
    const tracker = new PL.Tracker();
    const labels = {}, joints = {};
    let maxN = 0, total = 0, confirmedFrames = [];
    for (let i = 0; i < frames.length; i++) {
        const o = PL.pipeline_frame(frames[i], i, { static_keys: online, tracker });
        total += o.clusters.length;
        for (const c of o.clusters) { labels[c.label] = (labels[c.label] || 0) + 1; joints[c.joint] = (joints[c.joint] || 0) + 1; maxN = Math.max(maxN, c.n); }
        if (o.clusters.some(c => c.track_confirmed)) confirmedFrames.push(i);
    }
    if (!fs.existsSync(path.join(__dirname, "empty_scene_check.json"))) {
        write("empty_scene_check.json", { schema: 1, kind: "empty_scene_p_check", sid: REF, job: REFJOB,
            frames: frames.length, clusters_total: total, cluster_label_counts: labels, joint_counts: joints,
            max_cluster_points: maxN, confirmed_cluster_frames: confirmedFrames, code: codeBinding });
        console.log(`empty check ${REF}: clusters_total=${total} labels=${JSON.stringify(labels)} maxN=${maxN} confirmedFrames=${confirmedFrames.length}`);
    } else console.log("empty_scene_check.json 已存在（上一跑产物），复用");
}

/* ---- 参考图 ---- */
const refLevel = R.levelingBinding(ROOT, REF, REFJOB);
const refFrames = R.loadFrames(ROOT, REF, refLevel, true).frames;
const refmap = PL.build_reference_map(refFrames);
const refkeys = new Map([...refmap.voxels].filter(([, v]) => v.occ >= PL.PIPE.bg_ref_occ_min));
console.log(`reference map: voxels=${refmap.voxels.size} keys(occ>=${PL.PIPE.bg_ref_occ_min})=${refkeys.size}`);

for (const s of SESSIONS) {
    const regdir = path.join(ROOT, "captures/registration", `${s.sid}__to__${REF}`);
    const loaded = R.load(regdir, { root: ROOT, source: s.sid, reference: REF });
    console.log(`== ${s.sid}: reg_state=${loaded.state} reasons=${JSON.stringify(loaded.reasons)}`);
    if (loaded.state !== "VALID" && loaded.state !== "DEGRADED") {
        write(`retention_ref_${s.sid}.json`, { schema: 1, kind: "still_person_reference_retention", sid: s.sid,
            reference: REF, registration: { state: loaded.state, reasons: loaded.reasons }, error: "registration not usable" });
        continue;
    }
    const shadow = loaded.state === "DEGRADED";
    const sl = R.levelingBinding(ROOT, s.sid, s.job);
    const raw = R.loadFrames(ROOT, s.sid, sl).frames;
    const clouds = raw.map(buf => R.applyRegistration({ buf, frame: "leveled_session:" + s.sid }, loaded, { shadow }).buf);
    const r = loaded.registration;
    const center = M.m3.apply(r.rotation_row_major, s.center[0], s.center[1], 0).map((v, i) => v + r.translation_m[i]);
    const clean = clouds.map(PL.denoise);
    const online = PL.build_static_map(clean);
    const tracker = new PL.Tracker();
    const rows = [];
    for (let i = 0; i < clouds.length; i++) {
        const s1 = PL.extract_foreground(clean[i], refkeys);
        const f2 = PL.extract_foreground(s1.fg_xyzi, online);
        const setRef = new Set(), setAll = new Set();
        for (let k = 0; k < s1.fg_xyzi.length; k += 4) setRef.add(keyAt(s1.fg_xyzi, k));
        for (let k = 0; k < f2.fg_xyzi.length; k += 4) setAll.add(keyAt(f2.fg_xyzi, k));
        const o = PL.pipeline_frame(f2.fg_xyzi, i, { static_keys: null, tracker });
        const own = audit.ownership(PL, f2.fg_xyzi, o, clouds[i]);
        const mech = { RANGE: 0, GROUND: 0, REFERENCE: 0, ONLINE: 0, CLEANUP: 0 };
        let rawc = 0, refc = 0, allc = 0, cleanc = 0, pCl = 0;
        const byC = new Map();
        const c0 = clouds[i];
        for (let k = 0; k < c0.length; k += 4) {
            const x = c0[k], y = c0[k + 1], z = c0[k + 2];
            const dx = x - center[0], dy = y - center[1];
            if (dx * dx + dy * dy > R2 || z < ZLO || z > ZHI) continue;
            rawc++;
            const rr = x * x + y * y + z * z;
            if (!Number.isFinite(rr) || rr < PL.PIPE.range_min_m ** 2 || rr > PL.PIPE.range_max_m ** 2) { mech.RANGE++; continue; }
            if (z < PL.PIPE.ground_keep_below_m) { mech.GROUND++; continue; }
            if (!setRef.has(keyAt(c0, k))) { mech.REFERENCE++; continue; }
            refc++;
            if (!setAll.has(keyAt(c0, k))) { mech.ONLINE++; continue; }
            allc++;
            const st = own.status[k / 4];
            if (!st.after_cleanup) { mech.CLEANUP++; continue; }
            cleanc++;
            if (st.cluster !== null) { pCl++; byC.set(st.cluster, (byC.get(st.cluster) || 0) + 1); }
        }
        if (!(rawc >= refc && refc >= allc && allc >= cleanc && cleanc >= pCl)) throw new Error("conservation f" + i);
        let top = null;
        for (const [cid, n] of byC) if (!top || n > top.person_points) top = { cluster_index: cid, person_points: n };
        if (top) { const c = o.clusters[top.cluster_index]; top = { cluster_index: top.cluster_index, person_points: top.person_points, foreign_points: c.n - top.person_points, ...summarizeCluster(c) }; }
        rows.push({ i, n_in: o.n_in, n_foreground: o.n_foreground, clusters_after_cleanup: o.clusters_after_cleanup,
            cleanup_split_delta: o.cleanup_split_delta, n_clusters: o.clusters.length,
            person: { raw: rawc, reference_survived: refc, online_survived: allc, cleanup: cleanc, clustered: pCl,
                mechanism: mech, clusters: Object.fromEntries(byC), top },
            tracks: o.tracks.map(t => ({ id: t.id, label: t.label, lost: t.lost, human_confirmed: !!t.human_confirmed, votes: (t.votes || []).join("") })),
            events: o.events });
    }
    const P = rows.map(x => x.person);
    const labels = {}, joints = {}, mechTot = { RANGE: 0, GROUND: 0, REFERENCE: 0, ONLINE: 0, CLEANUP: 0 };
    const tids = new Map(), confirmed = [];
    for (const row of rows) {
        const t = row.person.top, L = t ? t.label : "NONE";
        labels[L] = (labels[L] || 0) + 1;
        if (t) joints[t.joint] = (joints[t.joint] || 0) + 1;
        for (const k in mechTot) mechTot[k] += row.person.mechanism[k];
        if (t && t.track_id !== null) { const v = tids.get(t.track_id) || { first: row.i, last: row.i, frames: 0 }; v.last = row.i; v.frames++; tids.set(t.track_id, v); }
        if (t && t.track_confirmed) confirmed.push(row.i);
    }
    const rawStat = stat(P.map(p => p.raw));
    const summary = { frames: rows.length, person_raw: rawStat,
        reference_survived: stat(P.map(p => p.reference_survived)), online_survived: stat(P.map(p => p.online_survived)),
        cleanup: stat(P.map(p => p.cleanup)), clustered: stat(P.map(p => p.clustered)),
        reference_retention_p50: rawStat.p50 ? stat(P.map(p => p.reference_survived)).p50 / rawStat.p50 : null,
        online_retention_p50: rawStat.p50 ? stat(P.map(p => p.online_survived)).p50 / rawStat.p50 : null,
        label_counts: labels, joint_counts: joints, mechanism_totals: mechTot,
        track_ids: Object.fromEntries(tids), confirmed_frames: confirmed };
    write(`retention_ref_${s.sid}.json`, { schema: 1, kind: "still_person_reference_retention", sid: s.sid,
        reference: REF, reference_job: REFJOB, shadow,
        registration: { state: loaded.state, reasons: loaded.reasons, artifact_id: loaded.artifact_id,
            gate: loaded.diagnostics?.gate?.status, fit_p50: loaded.diagnostics?.residual?.fit?.p50,
            holdout_p50: loaded.diagnostics?.residual?.holdout?.p50,
            n_correspondence: loaded.diagnostics?.support?.n_correspondence, inlier_ratio: loaded.diagnostics?.support?.inlier_ratio },
        person_region: { center_source: s.center, center_reference: center, radius_m: RADIUS },
        refmap: { voxels: refmap.voxels.size, keys: refkeys.size, occ_min: PL.PIPE.bg_ref_occ_min },
        code_binding: codeBinding, summary, frames: rows });
    console.log(`== ${s.sid}: raw p50=${rawStat.p50}  ref_survived p50=${summary.reference_survived.p50} (${(100 * summary.reference_retention_p50).toFixed(1)}%)` +
        `  +online p50=${summary.online_survived.p50} (${(100 * summary.online_retention_p50).toFixed(1)}%)` +
        `  clustered p50=${summary.clustered.p50}  labels=${JSON.stringify(labels)}  confirmed=${confirmed.length}`);
}
console.log("done.");

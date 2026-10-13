"use strict";
/* 2026-10-07 新四段会话 · 现行管线 P 路径逐帧"人体对照"诊断（非验收）。
 *
 * 口径：完全复刻 R39 closeout 的 P 分支 ——
 *   leveled(raw + tls transform) → denoise → build_static_map(全帧) →
 *   逐帧 pipeline_frame(帧, i, {static_keys: online, tracker})。
 * 点级归属：audit_lib.ownership（R39 诊断副本，内部断言簇一致性）。
 * 人体参考区域：前置定位得到的固定圆柱（见 README），不是逐点 GT。
 * ponytail: 固定圆柱代替逐点 GT（有真人 GT 后替换）；不写生产文件；输出独占创建。
 */
const fs = require("fs"), path = require("path"), crypto = require("crypto");
const ROOT = path.resolve(__dirname, "../../../..");
const PL = require(path.join(ROOT, "pc_apps/human_replay/human_pipe_lib.js"));
const R = require(path.join(ROOT, "pc_apps/human_replay/registration.js"));
const audit = require(path.join(__dirname, "audit_lib.js"));

const SESSIONS = [
    { sid: "cap_20261007_215540", job: "21666bec7e7b44b2bdbbaa790bf4501b", center: [2.10, -0.57] },
    { sid: "cap_20261007_215607", job: "2ed2cf6a4d2342ebb87f4e7fa68fdf3c", center: [2.13, -0.50] },
    { sid: "cap_20261007_215623", job: "a9e1e01fa6644f93aa686daa330a5fcd", center: [2.14, -0.45] },
    { sid: "cap_20261007_215643", job: "e46d035de1b34378b841ca3bc2a1c8f6", center: [2.11, -0.36] },
];
const RADIUS = 0.55, ZLO = 0.05, ZHI = 2.30, R2 = RADIUS * RADIUS;

const shaFile = f => crypto.createHash("sha256").update(fs.readFileSync(f)).digest("hex");
const write = (name, v) => fs.writeFileSync(path.join(__dirname, name), JSON.stringify(v, null, 2) + "\n", { flag: "wx" });

function leveling(root, sid, job) {
    try {
        return { lv: R.levelingBinding(root, sid, job), authoritative: true, note: "recommended=tls" };
    } catch (e) {
        /* 非 recommended 会话：只允许诊断；仍核 transform/manifest 完整性，不碰算法。 */
        const dir = path.join(root, "captures/leveled", job);
        const tf = JSON.parse(fs.readFileSync(path.join(dir, "tls/transform.json"), "utf8"));
        const report = JSON.parse(fs.readFileSync(path.join(dir, "report.json"), "utf8"));
        const manifest = JSON.parse(fs.readFileSync(path.join(dir, "manifest.json"), "utf8"));
        if (report.sid !== sid || tf.estimator !== "tls" || manifest.job_id !== job ||
            manifest.artifacts?.tls?.["transform.json"] !== shaFile(path.join(dir, "tls/transform.json")))
            throw new Error("LEVELING_UNVERIFIED: " + e.message);
        return { lv: { tf }, authoritative: false, note: "levelingBinding rejected: " + e.message };
    }
}

function summarizeCluster(c) {
    return { n: c.n, cx: c.cx, cy: c.cy, cz: c.cz, zmin: c.zmin, zmax: c.zmax,
        height_m: c.height_m, width_m: c.width_m, depth_m: c.depth_m, radius_m: c.radius_m, upcos: c.upcos,
        label: c.label, confidence: c.confidence, joint: c.joint,
        evidence_tag: c.evidence_tag ? c.evidence_tag.label : null, reasons: c.reasons,
        track_id: c.track_id ?? null, track_confirmed: !!c.track_confirmed };
}

function runSession(s) {
    const lv = leveling(ROOT, s.sid, s.job);
    const { meta, frames } = R.loadFrames(ROOT, s.sid, lv.lv);
    const clean = frames.map(PL.denoise);
    const online = PL.build_static_map(clean);
    let strong = 0, supported = 0;
    online.forEach(v => v.tier === "strong" ? strong++ : supported++);
    const tracker = new PL.Tracker();
    const rows = [];
    const tier = { strong: 0, supported: 0, absent: 0 };
    for (let i = 0; i < frames.length; i++) {
        const o = PL.pipeline_frame(frames[i], i, { static_keys: online, tracker });
        const fg = PL.extract_foreground(clean[i], online);
        const own = audit.ownership(PL, fg.fg_xyzi, o, frames[i]);
        const raw = frames[i];
        const mech = { RANGE: 0, GROUND: 0, STATIC: 0, CLEANUP: 0, OTHER: 0 };
        let pRaw = 0, pDen = 0, pWs = 0, pFg = 0, pClean = 0, pClustered = 0;
        const byC = new Map();
        for (let k = 0; k < raw.length; k += 4) {
            const x = raw[k], y = raw[k + 1], z = raw[k + 2];
            const dx = x - s.center[0], dy = y - s.center[1];
            if (dx * dx + dy * dy > R2 || z < ZLO || z > ZHI) continue;
            pRaw++;
            const r2 = x * x + y * y + z * z;
            if (!Number.isFinite(r2) || r2 < PL.PIPE.range_min_m ** 2 || r2 > PL.PIPE.range_max_m ** 2) { mech.RANGE++; continue; }
            pDen++;
            if (z < PL.PIPE.ground_keep_below_m) { mech.GROUND++; continue; }
            pWs++;
            const st = own.status[k / 4];
            if (!st.foreground) { mech.STATIC++; continue; }
            pFg++;
            if (!st.after_cleanup) { mech.CLEANUP++; continue; }
            pClean++;
            if (st.cluster !== null) { pClustered++; byC.set(st.cluster, (byC.get(st.cluster) || 0) + 1); }
            if (k % 28 === 0) { const v = online.get(PL.key_bg(x, y, z)); if (v) tier[v.tier]++; else tier.absent++; }
        }
        if (!(pRaw >= pDen && pDen >= pWs && pWs >= pFg && pFg >= pClean)) throw new Error("person conservation violated at f" + i);
        let top = null;
        for (const [cid, n] of byC) if (!top || n > top.person_points) top = { cluster_index: cid, person_points: n };
        if (top) {
            const c = o.clusters[top.cluster_index];
            top = { cluster_index: top.cluster_index, person_points: top.person_points, foreign_points: c.n - top.person_points, ...summarizeCluster(c) };
        }
        rows.push({ i, n_in: o.n_in, n_denoise: o.n_denoise, n_foreground: o.n_foreground, n_dropped: o.n_dropped,
            clusters_before_cleanup: o.clusters_before_cleanup, clusters_after_cleanup: o.clusters_after_cleanup,
            cleanup_split_delta: o.cleanup_split_delta, n_clusters: o.clusters.length,
            person: { raw: pRaw, denoise: pDen, workspace: pWs, foreground: pFg, cleanup: pClean, clustered: pClustered,
                mechanism: mech, clusters: Object.fromEntries(byC), top },
            tracks: o.tracks.map(t => ({ id: t.id, x: t.x, y: t.y, height: t.height, upcos: t.upcos, label: t.label,
                lost: t.lost, born: t.born_idx, human_confirmed: !!t.human_confirmed, votes: (t.votes || []).join("") })),
            events: o.events });
        if (i % 16 === 0) console.log(`  ${s.sid} f${i}/${frames.length - 1} person raw=${pRaw} fg=${pFg} clean=${pClean} top=${top ? top.label + "/" + top.joint : "NONE"}`);
    }
    /* 汇总 */
    const P = rows.map(r => r.person);
    const stat = a => { const b = a.slice().sort((x, y) => x - y); return { min: b[0], p50: b[b.length >> 1], max: b[b.length - 1] }; };
    const labels = {}, joints = {}, mechTot = { RANGE: 0, GROUND: 0, STATIC: 0, CLEANUP: 0, OTHER: 0 };
    const merge = [], tids = new Map(), confirmed = [];
    for (const r of rows) {
        const t = r.person.top;
        labels[t ? t.label : "NONE"] = (labels[t ? t.label : "NONE"] || 0) + 1;
        if (t) joints[t.joint] = (joints[t.joint] || 0) + 1;
        for (const k in mechTot) mechTot[k] += r.person.mechanism[k];
        if (t && t.foreign_points > 200) merge.push({ i: r.i, cluster_index: t.cluster_index, person_points: t.person_points, foreign_points: t.foreign_points, n: t.n });
        if (t && t.track_id !== null) { const v = tids.get(t.track_id) || { first: r.i, last: r.i, frames: 0 }; v.last = r.i; v.frames++; tids.set(t.track_id, v); }
        if (t && t.track_confirmed) confirmed.push(r.i);
    }
    const summary = { frames: rows.length, person_foreground: stat(P.map(p => p.foreground)), person_cleanup: stat(P.map(p => p.cleanup)),
        person_clustered: stat(P.map(p => p.clustered)), zero_foreground_frames: rows.filter(r => r.person.foreground === 0).map(r => r.i),
        zero_clustered_frames: rows.filter(r => r.person.clustered === 0).map(r => r.i),
        top_label_counts: labels, top_joint_counts: joints, mechanism_totals: mechTot,
        person_points_online_tier_sampled: tier, merge_suspect_frames: merge,
        person_track_ids: Object.fromEntries(tids), confirmed_frames: confirmed };
    const out = { schema: 1, kind: "new_session_person_probe", sid: s.sid,
        person_region: { center: s.center, radius_m: RADIUS, z: [ZLO, ZHI], source: "prior leveled localization (fixed cylinder; not point GT)" },
        leveling: { job: s.job, authoritative: lv.authoritative, note: lv.note,
            transform_id: lv.lv.tf ? lv.lv.tf.transform_id : null, pitch_deg: lv.lv.tf ? lv.lv.tf.pitch_deg : null, roll_deg: lv.lv.tf ? lv.lv.tf.roll_deg : null },
        online_map: { voxels: online.size, strong, supported },
        code_binding: { human_pipe_lib: shaFile(path.join(ROOT, "pc_apps/human_replay/human_pipe_lib.js")),
            registration: shaFile(path.join(ROOT, "pc_apps/human_replay/registration.js")),
            audit_lib: shaFile(path.join(__dirname, "audit_lib.js")), probe: shaFile(__filename) },
        summary, frames: rows };
    write(`probe_${s.sid}.json`, out);
    console.log(`== ${s.sid}: fg survival ${summary.person_foreground.min}/${summary.person_foreground.p50}/${summary.person_foreground.max}` +
        `  clustered ${summary.person_clustered.min}/${summary.person_clustered.p50}/${summary.person_clustered.max}` +
        `  labels=${JSON.stringify(summary.top_label_counts)}  tracks=${Object.keys(summary.person_track_ids).length}  merge_frames=${summary.merge_suspect_frames.length}`);
    return summary;
}

console.log("probe: " + SESSIONS.length + " sessions; ROOT=" + ROOT);
const manifest = { schema: 1, kind: "new_session_person_probe_manifest", created: new Date().toISOString(),
    sessions: SESSIONS.map(s => ({ sid: s.sid, job: s.job,
        session_meta_sha256: shaFile(path.join(ROOT, "captures/remote", s.sid, "meta.json")),
        session_bin_sha256: shaFile(path.join(ROOT, "captures/remote", s.sid, "points.bin")),
        leveling_report_sha256: shaFile(path.join(ROOT, "captures/leveled", s.job, "report.json")),
        leveling_transform_sha256: shaFile(path.join(ROOT, "captures/leveled", s.job, "tls/transform.json")) })),
    code: { human_pipe_lib: shaFile(path.join(ROOT, "pc_apps/human_replay/human_pipe_lib.js")),
        registration: shaFile(path.join(ROOT, "pc_apps/human_replay/registration.js")),
        audit_lib: shaFile(path.join(__dirname, "audit_lib.js")) } };
const results = {};
for (const s of SESSIONS) results[s.sid] = runSession(s);
manifest.results = Object.fromEntries(Object.entries(results).map(([k, v]) => [k, { person_foreground: v.person_foreground, person_cleanup: v.person_cleanup, top_label_counts: v.top_label_counts, top_joint_counts: v.top_joint_counts, person_points_online_tier_sampled: v.person_points_online_tier_sampled, merge_suspect_frames: v.merge_suspect_frames.length }]));
write("00_manifest.json", manifest);
console.log("done.");

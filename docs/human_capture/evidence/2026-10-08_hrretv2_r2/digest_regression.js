"use strict";
/* HR-RET-V2 increment 2 · 行为 digest 回归（离线只读；输出独占写本目录，不覆盖旧证据）。
 * D1: P 路径 digest —— baseline_code/human_pipe_lib.js（inc2 前快照） vs 当前源码，逐位一致；
 * D2: 确定性 —— 当前 P 路径对同输入跑两遍 digest 相等；
 * D3: 负例（真实 artifact）—— 现网 artifact（代码绑定漂移 → STALE）下 fusionKeys(true, …) 必须 null（不启用 v2）；
 * D4: 诊断臂（非生产启用）—— 三段新会话复跑 v2 语义（artifact 已 STALE，离线直读其 transform；shadow 语义同 A/B），
 *     与 P2 A/B `fusion_v2_chain_results.json` 的 v2 数字对账（人 fg/cleanup p50、labels、confirmed）；
 * D5: 融合臂确定性 —— 同一诊断输入跑两遍 digest 相等。
 * 口径：leveled → [registered] → denoise → 提取(v2/融合) → cleanup → cluster → classify/joint → Tracker = pipeline_frame 全链。 */
const fs = require("fs"), path = require("path"), crypto = require("crypto");
const ROOT = path.resolve(__dirname, "../../../..");
const PL = require(path.join(ROOT, "pc_apps/human_replay/human_pipe_lib.js"));
const PLBASE = require(path.join(__dirname, "baseline_code/human_pipe_lib.js"));
const R = require(path.join(ROOT, "pc_apps/human_replay/registration.js"));
const M = require(path.join(ROOT, "pc_apps/human_replay/registration_method.js"));
const sha = b => crypto.createHash("sha256").update(b).digest("hex");
const shaFile = f => sha(fs.readFileSync(f));

/* ---- 全链 digest（P 路径） ---- */
function pipelineDigest(PLmod, sid, job) {
    const raw = R.loadFrames(ROOT, sid, R.levelingBinding(ROOT, sid, job), false).frames;
    const ded = raw.map(PLmod.denoise);
    const online = PLmod.build_static_map(ded, { drop_ground: true });
    const tracker = new PLmod.Tracker();
    const rows = [];
    for (let i = 0; i < raw.length; i++) {
        const r = PLmod.pipeline_frame(raw[i], i, { static_keys: online, tracker });   /* 旗标缺省 = P */
        rows.push({ i, n_in: r.n_in, n_denoise: r.n_denoise, n_foreground: r.n_foreground, n_dropped: r.n_dropped,
            fg_before_cleanup: r.fg_before_cleanup, fg_after_cleanup: r.fg_after_cleanup,
            isolated_3d_candidates: r.isolated_3d_candidates, xy_topology_vetoed: r.xy_topology_vetoed,
            actually_removed_points: r.actually_removed_points, actually_removed_voxels: r.actually_removed_voxels,
            clusters_before_cleanup: r.clusters_before_cleanup, clusters_after_cleanup: r.clusters_after_cleanup,
            cleanup_split_delta: r.cleanup_split_delta, fg_voxels: r.fg_voxels,
            clusters: r.clusters.map(c => ({ n: c.n, label: c.label, joint: c.joint, confidence: c.confidence,
                cx: c.cx, cy: c.cy, cz: c.cz, height_m: c.height_m })),
            tracks: r.tracks.map(t => ({ id: t.id, x: t.x, y: t.y, z: t.z, height: t.height, upcos: t.upcos,
                label: t.label, n: t.n, lost: t.lost, human_confirmed: !!t.human_confirmed })) });
    }
    return { digest: sha(JSON.stringify(rows)), nframes: raw.length };
}

/* ---- D4 诊断臂：registered shadow（直读 transform，因 artifact 已 STALE）+ v2 语义 ----
 * 逐帧人指标复用 P2 A/B fusion_v2_chain.js 的口径（圆柱 R=0.55、z∈[0.10,2.30]、fg/cleanup 点级归属）。 */
const REF_NEW = "cap_20261007_233658", REFJOB_NEW = "3c793d7bda0f4ced86b20ac8076e7b0e";
const SESSIONS = [
    { sid: "cap_20261007_215540", job: "21666bec7e7b44b2bdbbaa790bf4501b", center: [2.10, -0.57] },
    { sid: "cap_20261007_215623", job: "a9e1e01fa6644f93aa686daa330a5fcd", center: [2.14, -0.45] },
    { sid: "cap_20261007_215643", job: "e46d035de1b34378b841ca3bc2a1c8f6", center: [2.11, -0.36] },
];
const RADIUS = 0.55, R2 = RADIUS * RADIUS, ZLO = 0.10, ZHI = 2.30;
const keyAt = (a, k) => a[k] + "," + a[k + 1] + "," + a[k + 2] + "," + a[k + 3];
const stat = a => { const b = a.slice().sort((x, y) => x - y); return { min: b[0], p50: b[b.length >> 1], max: b[b.length - 1] }; };
function diagV2(s) {
    const regdir = path.join(ROOT, "captures/registration", s.sid + "__to__" + REF_NEW);
    const reg = JSON.parse(fs.readFileSync(path.join(regdir, "registration.json"), "utf8"));   /* 只读；诊断专用 */
    const Rm = reg.rotation_row_major.flat(), t = reg.translation_m;
    const raw = R.loadFrames(ROOT, s.sid, R.levelingBinding(ROOT, s.sid, s.job), false).frames;
    const clouds = raw.map(buf => {   /* 单遍 R·p+t（诊断；生产必须经 artifact 状态机，此处不走） */
        const c = buf.slice();
        for (let i = 0; i < c.length; i += 4) { const q = M.m3.apply(Rm, c[i], c[i + 1], c[i + 2]); for (let j = 0; j < 3; j++) c[i + j] = q[j] + t[j]; }
        return c;
    });
    const refFrames = R.loadFrames(ROOT, REF_NEW, R.levelingBinding(ROOT, REF_NEW, REFJOB_NEW), true).frames;
    const refkeys = new Map([...PL.build_reference_map(refFrames).voxels].filter(([, v]) => v.occ >= PL.PIPE.bg_ref_occ_min));
    const clean = clouds.map(PL.denoise);
    const online = PL.build_static_map(clean);
    const center = M.m3.apply(Rm, s.center[0], s.center[1], 0).map((v, i) => v + t[i]);
    const tracker = new PL.Tracker();
    const rows = [];
    for (let i = 0; i < clean.length; i++) {
        const o = PL.pipeline_frame(clouds[i], i, { static_keys: online, tracker, fusion: { refkeys } });
        const fgArr = PL.extract_foreground_fused(clean[i], refkeys, online).fg_xyzi;   /* 与 pipeline 同一提取函数（点级计数用） */
        const fgSet = new Set(); for (let k = 0; k < fgArr.length; k += 4) fgSet.add(keyAt(fgArr, k));
        const iso = PL.cleanup_isolated_fg(fgArr);
        const post = new Set(); for (let k = 0; k < iso.xyzi.length; k += 4) post.add(keyAt(iso.xyzi, k));
        const cs = PL.cluster_voxels(PL.voxelize(iso.xyzi)).filter(c => c.acc.n >= PL.PIPE.human_n_min);
        if (cs.length !== o.clusters.length) throw new Error("cluster mismatch f" + i);
        const owner = new Map(); cs.forEach((c, ci) => c.keys.forEach(k => owner.set(k, ci)));
        let pRaw = 0, pFg = 0, pClean = 0; const byC = new Map();
        for (let k = 0; k < clouds[i].length; k += 4) {
            const x = clouds[i][k], y = clouds[i][k + 1], z = clouds[i][k + 2];
            if ((x - center[0]) ** 2 + (y - center[1]) ** 2 > R2 || z < ZLO || z > ZHI) continue;
            pRaw++;
            if (!fgSet.has(keyAt(clouds[i], k))) continue; pFg++;
            if (!post.has(keyAt(clouds[i], k))) continue; pClean++;
            const ci = owner.get(PL.key_vox(x, y));
            if (ci !== undefined) byC.set(ci, (byC.get(ci) || 0) + 1);
        }
        let top = null;
        for (const [ci, n] of byC) if (!top || n > top.person_points) top = { ci, person_points: n };
        if (top) { const c = o.clusters[top.ci]; top = { person_points: top.person_points, n: c.n, label: c.label, joint: c.joint, track_id: c.track_id ?? null, track_confirmed: !!c.track_confirmed }; }
        rows.push({ i, person: { raw: pRaw, fg: pFg, cleanup: pClean, top }, fusion: o.fusion });
    }
    const P = rows.map(x => x.person);
    const labels = {}; let confirmed = 0; const tids = new Set();
    for (const p of P) { const tp = p.top; labels[tp ? tp.label : "NONE"] = (labels[tp ? tp.label : "NONE"] || 0) + 1; if (tp && tp.track_confirmed) confirmed++; if (tp && tp.track_id !== null) tids.add(tp.track_id); }
    const onlineOnlyKept = rows.reduce((a, x) => a + (x.fusion ? x.fusion.n_online_only_kept : 0), 0);
    return { sid: s.sid, person_raw_p50: stat(P.map(p => p.raw)).p50, person_fg_p50: stat(P.map(p => p.fg)).p50,
        person_cleanup_p50: stat(P.map(p => p.cleanup)).p50, labels, confirmed_frames: confirmed, track_ids: [...tids],
        fusion_online_only_kept_total: onlineOnlyKept, digest: sha(JSON.stringify(rows)) };
}

/* ---- run ---- */
const out = { schema: 1, kind: "hrretv2_inc2_digest_regression", created_utc: new Date().toISOString(),
    inputs: { human_pipe_lib: shaFile(path.join(ROOT, "pc_apps/human_replay/human_pipe_lib.js")),
        baseline_human_pipe_lib: shaFile(path.join(__dirname, "baseline_code/human_pipe_lib.js")),
        registration_js: shaFile(path.join(ROOT, "pc_apps/human_replay/registration.js")),
        ab_chain_results: shaFile(path.join(ROOT, "docs/human_capture/evidence/2026-10-08_fusion_v2_ab_r1/fusion_v2_chain_results.json")) },
    verdicts: [] };
const V = (id, target, actual, pass) => out.verdicts.push({ id, target, actual, pass });

/* D1/D2：P 路径 digest（baseline vs current；current 两遍） */
const GOLDEN = [
    { sid: "cap_20261007_215540", job: "21666bec7e7b44b2bdbbaa790bf4501b" },
    { sid: "cap_20261002_223757", job: "6bc5aabf8f0041ffa961758b4e84da94" },
];
out.p_digests = [];
for (const g of GOLDEN) {
    try {
        const b1 = pipelineDigest(PLBASE, g.sid, g.job);
        const c1 = pipelineDigest(PL, g.sid, g.job);
        const c2 = pipelineDigest(PL, g.sid, g.job);
        out.p_digests.push({ sid: g.sid, nframes: c1.nframes, baseline: b1.digest, current_run1: c1.digest, current_run2: c2.digest });
        V("D1-" + g.sid.slice(-6), "P digest 基线(inc2 前快照) == 当前", b1.digest === c1.digest ? "equal" : "DIFF " + b1.digest + " vs " + c1.digest, b1.digest === c1.digest);
        V("D2-" + g.sid.slice(-6), "P digest 当前两遍一致", c1.digest === c2.digest ? "equal" : "DIFF", c1.digest === c2.digest);
    } catch (e) { out.p_digests.push({ sid: g.sid, error: String(e.message || e) }); V("D1-" + g.sid.slice(-6), "P digest", "ERROR " + e.message, false); }
}

/* D3：真实 artifact 负例（当前应因代码绑定漂移为 STALE；任何非 VALID 一律不启用） */
{
    const dir = path.join(ROOT, "captures/registration", "cap_20261007_215540__to__cap_20261007_233658");
    const loaded = R.load(dir, { root: ROOT, source: "cap_20261007_215540", reference: "cap_20261007_233658" });
    const fk = R.fusionKeys(true, loaded, { root: ROOT });
    out.d3 = { state: loaded.state, reasons: loaded.reasons, fusionKeys: fk === null ? null : "NON-NULL" };
    V("D3-real-stale", "真实 artifact 非 VALID → fusionKeys(true) == null（不启用 v2）", loaded.state + " " + JSON.stringify(loaded.reasons), fk === null);
}

/* D4/D5：诊断臂 vs A/B 对账 + 两遍确定性 */
const ab = JSON.parse(fs.readFileSync(path.join(ROOT, "docs/human_capture/evidence/2026-10-08_fusion_v2_ab_r1/fusion_v2_chain_results.json"), "utf8"));
out.diag = [];
for (const s of SESSIONS) {
    try {
        const a1 = diagV2(s), a2 = diagV2(s);
        const ref = ab.sessions.find(x => x.sid === s.sid).v2;
        const cmp = ["person_raw_p50", "person_fg_p50", "person_cleanup_p50", "confirmed_frames"];
        const mismatch = cmp.filter(k => a1[k] !== ref[k]).concat(JSON.stringify(a1.labels) === JSON.stringify(ref.labels) ? [] : ["labels"]);
        out.diag.push({ sid: s.sid, mine: { person_raw_p50: a1.person_raw_p50, person_fg_p50: a1.person_fg_p50,
                person_cleanup_p50: a1.person_cleanup_p50, labels: a1.labels, confirmed_frames: a1.confirmed_frames,
                track_ids: a1.track_ids, fusion_online_only_kept_total: a1.fusion_online_only_kept_total, digest: a1.digest },
            ab_ref: { person_raw_p50: ref.person_raw_p50, person_fg_p50: ref.person_fg_p50, person_cleanup_p50: ref.person_cleanup_p50,
                labels: ref.labels, confirmed_frames: ref.confirmed_frames, track_ids: ref.track_ids },
            det_equal: a1.digest === a2.digest });
        V("D4-" + s.sid.slice(-6), "诊断 v2 复现 A/B v2 数字（raw/fg/cleanup p50 + labels + confirmed）",
            mismatch.length ? "MISMATCH " + mismatch.join(",") : "matched", mismatch.length === 0);
        V("D5-" + s.sid.slice(-6), "诊断 v2 两遍 digest 一致", a1.digest === a2.digest ? "equal" : "DIFF", a1.digest === a2.digest);
    } catch (e) { out.diag.push({ sid: s.sid, error: String(e.message || e) }); V("D4-" + s.sid.slice(-6), "诊断 v2", "ERROR " + e.message, false); }
}

fs.writeFileSync(path.join(__dirname, "digest_results.json"), JSON.stringify(out, null, 2) + "\n", { flag: "wx" });
for (const v of out.verdicts) console.log((v.pass ? "PASS" : "FAIL") + "  " + v.id + ": " + v.target + " | " + v.actual);
console.log("done. fails=" + out.verdicts.filter(v => !v.pass).length);

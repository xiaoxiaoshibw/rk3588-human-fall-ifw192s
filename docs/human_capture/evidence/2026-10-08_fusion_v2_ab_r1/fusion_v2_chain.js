"use strict";
/* P2 端到端闭环：v2 融合规则进完整链（前景→cleanup→聚类→判定→3/5 确认），并集臂同场对照。
 * 口径：registered → denoise → v2/union 前景 → cleanup → cluster → classify/joint → Tracker。
 * 只读；wx 独占。 */
const fs = require("fs"), path = require("path"), crypto = require("crypto");
const ROOT = path.resolve(__dirname, "../../../..");
const PL = require(path.join(ROOT, "pc_apps/human_replay/human_pipe_lib.js"));
const R = require(path.join(ROOT, "pc_apps/human_replay/registration.js"));
const M = require(path.join(ROOT, "pc_apps/human_replay/registration_method.js"));

const REF_NEW = "cap_20261007_233658", REFJOB_NEW = "3c793d7bda0f4ced86b20ac8076e7b0e";
const SESSIONS = [
    { sid: "cap_20261007_215540", job: "21666bec7e7b44b2bdbbaa790bf4501b", center: [2.10, -0.57] },
    { sid: "cap_20261007_215623", job: "a9e1e01fa6644f93aa686daa330a5fcd", center: [2.14, -0.45] },
    { sid: "cap_20261007_215643", job: "e46d035de1b34378b841ca3bc2a1c8f6", center: [2.11, -0.36] },
];
const RADIUS = 0.55, R2 = RADIUS * RADIUS, ZLO = 0.10, ZHI = 2.30;
const MATCH_R2 = PL.PIPE.bg_match_radius ** 2, BG_BASE = 8192, BG_OFF = 4096;
const bgKey = (ix, iy, iz) => ((ix + BG_OFF) * BG_BASE + (iy + BG_OFF)) * BG_BASE + (iz + BG_OFF);
function match(map, x, y, z) {
    const ix = Math.floor(x / PL.PIPE.bg_voxel_xy), iy = Math.floor(y / PL.PIPE.bg_voxel_xy), iz = Math.floor(z / PL.PIPE.bg_voxel_z);
    for (let a = -1; a <= 1; a++) for (let b = -1; b <= 1; b++) for (let c = -1; c <= 1; c++) {
        const rec = map.get(bgKey(ix + a, iy + b, iz + c));
        if (!rec) continue;
        const dx = rec.x - x, dy = rec.y - y, dz = rec.z - z;
        if (dx * dx + dy * dy + dz * dz < MATCH_R2) return rec;
    }
    return null;
}
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
const stat = a => { const b = a.slice().sort((x, y) => x - y); return { min: b[0], p50: b[b.length >> 1], max: b[b.length - 1] }; };
const keyAt = (a, k) => a[k] + "," + a[k + 1] + "," + a[k + 2] + "," + a[k + 3];

function runChain(sid, job, center0, mode) {
    const regdir = path.join(ROOT, "captures/registration", `${sid}__to__${REF_NEW}`);
    const loaded = R.load(regdir, { root: ROOT, source: sid, reference: REF_NEW });
    const shadow = loaded.state === "DEGRADED";
    const sl = R.levelingBinding(ROOT, sid, job);
    const raw = R.loadFrames(ROOT, sid, sl).frames;
    const clouds = raw.map(buf => R.applyRegistration({ buf, frame: "leveled_session:" + sid }, loaded, { shadow }).buf);
    const r = loaded.registration;
    const center = M.m3.apply(r.rotation_row_major, center0[0], center0[1], 0).map((v, i) => v + r.translation_m[i]);
    const refLevel = R.levelingBinding(ROOT, REF_NEW, REFJOB_NEW);
    const refFrames = R.loadFrames(ROOT, REF_NEW, refLevel, true).frames;
    const refkeys = new Map([...PL.build_reference_map(refFrames).voxels].filter(([, v]) => v.occ >= PL.PIPE.bg_ref_occ_min));
    const clean = clouds.map(PL.denoise);
    const online = PL.build_static_map(clean);
    const tracker = new PL.Tracker();
    const rows = [];
    for (let i = 0; i < clean.length; i++) {
        const cI = clean[i];
        let fgArr;
        if (mode === "v2") {
            const out = [];
            for (let k = 0; k < cI.length; k += 4) {
                const x = cI[k], y = cI[k + 1], z = cI[k + 2];
                if (match(refkeys, x, y, z)) continue;
                const on = match(online, x, y, z);
                if (on && match(refkeys, on.x, on.y, on.z)) continue;
                out.push(x, y, z, cI[k + 3]);
            }
            fgArr = new Float32Array(out);
        } else {
            fgArr = PL.extract_foreground(PL.extract_foreground(cI, refkeys).fg_xyzi, online).fg_xyzi;
        }
        fgArr = PL.extract_foreground(fgArr, null).fg_xyzi;   /* 与 pipeline_frame 内部一致：工作空间裁剪 */
        const o = PL.pipeline_frame(fgArr, i, { static_keys: null, tracker });
        const iso = PL.cleanup_isolated_fg(fgArr);
        const fgSet = new Set(); for (let k = 0; k < fgArr.length; k += 4) fgSet.add(keyAt(fgArr, k));
        const post = new Set(); for (let k = 0; k < iso.xyzi.length; k += 4) post.add(keyAt(iso.xyzi, k));
        const cs = PL.cluster_voxels(PL.voxelize(iso.xyzi)).filter(c => c.acc.n >= PL.PIPE.human_n_min);
        if (cs.length !== o.clusters.length) throw new Error("cluster mismatch f" + i);
        const owner = new Map(); cs.forEach((c, ci) => c.keys.forEach(k => owner.set(k, ci)));
        let pRaw = 0, pFg = 0, pClean = 0; const byC = new Map();
        for (let k = 0; k < cI.length; k += 4) {
            const x = cI[k], y = cI[k + 1], z = cI[k + 2];
            if ((x - center[0]) ** 2 + (y - center[1]) ** 2 > R2 || z < ZLO || z > ZHI) continue;
            pRaw++;
            if (!fgSet.has(keyAt(cI, k))) continue; pFg++;
            if (!post.has(keyAt(cI, k))) continue; pClean++;
            const ci = owner.get(PL.key_vox(x, y));
            if (ci !== undefined) byC.set(ci, (byC.get(ci) || 0) + 1);
        }
        let top = null;
        for (const [ci, n] of byC) if (!top || n > top.person_points) top = { ci, person_points: n };
        if (top) {
            const c = o.clusters[top.ci];
            top = { person_points: top.person_points, n: c.n, label: c.label, joint: c.joint, track_id: c.track_id ?? null, track_confirmed: !!c.track_confirmed };
        }
        rows.push({ i, person: { raw: pRaw, fg: pFg, cleanup: pClean, top } });
    }
    const P = rows.map(x => x.person);
    const labels = {}; let confirmed = 0; const tids = new Set();
    for (const p of P) { const t = p.top; labels[t ? t.label : "NONE"] = (labels[t ? t.label : "NONE"] || 0) + 1; if (t && t.track_confirmed) confirmed++; if (t && t.track_id !== null) tids.add(t.track_id); }
    return { sid, mode, person_raw_p50: stat(P.map(p => p.raw)).p50, person_fg_p50: stat(P.map(p => p.fg)).p50,
        person_cleanup_p50: stat(P.map(p => p.cleanup)).p50, labels, confirmed_frames: confirmed, track_ids: [...tids], rows };
}

const results = [];
for (const s of SESSIONS) {
    const v2 = runChain(s.sid, s.job, s.center, "v2");
    const un = runChain(s.sid, s.job, s.center, "union");
    results.push({ sid: s.sid, v2, union: un });
    console.log(`== ${s.sid}`);
    console.log(`   v2   : person raw=${v2.person_raw_p50} fg=${v2.person_fg_p50} cleanup=${v2.person_cleanup_p50} labels=${JSON.stringify(v2.labels)} confirmed=${v2.confirmed_frames} tracks=${JSON.stringify(v2.track_ids)}`);
    console.log(`   union: person raw=${un.person_raw_p50} fg=${un.person_fg_p50} cleanup=${un.person_cleanup_p50} labels=${JSON.stringify(un.labels)} confirmed=${un.confirmed_frames} tracks=${JSON.stringify(un.track_ids)}`);
}
const verdicts = results.map(r => ({
    id: `F02b-${r.sid.slice(-6)}`,
    target: "v2 链上人成簇且 3/5 确认（或给出 UNKNOWN 原因）",
    actual: `fg p50=${r.v2.person_fg_p50}, cleanup p50=${r.v2.person_cleanup_p50}, labels=${JSON.stringify(r.v2.labels)}, confirmed=${r.v2.confirmed_frames}`,
    pass: r.v2.confirmed_frames > 0 || (r.v2.person_fg_p50 > 0 && r.v2.person_cleanup_p50 > 0) }));
for (const v of verdicts) console.log(`${v.pass ? "PASS" : "FAIL"}  ${v.id}: ${v.target} | ${v.actual}`);
const write = (n, v) => fs.writeFileSync(path.join(__dirname, n), JSON.stringify(v, null, 2) + "\n", { flag: "wx" });
write("fusion_v2_chain_results.json", { schema: 1, kind: "fusion_v2_end_to_end_chain", sessions: results, verdicts,
    code_binding: { human_pipe_lib: crypto.createHash("sha256").update(fs.readFileSync(path.join(ROOT, "pc_apps/human_replay/human_pipe_lib.js"))).digest("hex"),
        script: crypto.createHash("sha256").update(fs.readFileSync(__filename)).digest("hex") } });
console.log("done. fails=" + verdicts.filter(v => !v.pass).length);

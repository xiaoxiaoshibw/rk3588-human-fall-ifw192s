"use strict";
/* P2：融合 v2 离线 A/B（四臂对照 + 不回归窗口 + 代价集 + 工具自复现校验）。
 * 臂：P=仅在线 / REF=仅参考层 / UNION=参考∪在线（现状 S 链语义） / V2=参考 OR (在线 AND 参考邻域支持)。
 * 数据：三段新会话（→233658，已有配准）+ 旧对（223757→203349，已有 artifact）。
 * 只读；wx 独占。ponytail：复用既有 loader/artifact 与 r1 点级归属思路，单脚本。 */
const fs = require("fs"), path = require("path"), crypto = require("crypto");
const ROOT = path.resolve(__dirname, "../../../..");
const PL = require(path.join(ROOT, "pc_apps/human_replay/human_pipe_lib.js"));
const R = require(path.join(ROOT, "pc_apps/human_replay/registration.js"));
const M = require(path.join(ROOT, "pc_apps/human_replay/registration_method.js"));

const REF_NEW = "cap_20261007_233658", REFJOB_NEW = "3c793d7bda0f4ced86b20ac8076e7b0e";
const SESSIONS = [
    { sid: "cap_20261007_215540", job: "21666bec7e7b44b2bdbbaa790bf4501b", center: [2.10, -0.57], prev: { ref: 1803, union: 39 } },
    { sid: "cap_20261007_215623", job: "a9e1e01fa6644f93aa686daa330a5fcd", center: [2.14, -0.45], prev: { ref: 1883, union: 24 } },
    { sid: "cap_20261007_215643", job: "e46d035de1b34378b841ca3bc2a1c8f6", center: [2.11, -0.36], prev: { ref: 1205, union: 23 } },
];
const RADIUS = 0.55, R2 = RADIUS * RADIUS, ZLO = 0.10, ZHI = 2.30;
const MATCH_R2 = PL.PIPE.bg_match_radius ** 2;
const BG_BASE = 8192, BG_OFF = 4096;
const bgKey = (ix, iy, iz) => ((ix + BG_OFF) * BG_BASE + (iy + BG_OFF)) * BG_BASE + (iz + BG_OFF);
function match(map, x, y, z) {  /* 复刻 _bg_match：3×3×3 邻域 + 0.12m */
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

/* ---- 段一：三段新会话四臂 ---- */
const newResults = [];
for (const s of SESSIONS) {
    const regdir = path.join(ROOT, "captures/registration", `${s.sid}__to__${REF_NEW}`);
    const loaded = R.load(regdir, { root: ROOT, source: s.sid, reference: REF_NEW });
    if (loaded.state !== "VALID" && loaded.state !== "DEGRADED") throw new Error(s.sid + " reg=" + loaded.state);
    const shadow = loaded.state === "DEGRADED";
    const sl = R.levelingBinding(ROOT, s.sid, s.job);
    const raw = R.loadFrames(ROOT, s.sid, sl).frames;
    const clouds = raw.map(buf => R.applyRegistration({ buf, frame: "leveled_session:" + s.sid }, loaded, { shadow }).buf);
    const r = loaded.registration;
    const center = M.m3.apply(r.rotation_row_major, s.center[0], s.center[1], 0).map((v, i) => v + r.translation_m[i]);
    const refLevel = R.levelingBinding(ROOT, REF_NEW, REFJOB_NEW);
    const refFrames = R.loadFrames(ROOT, REF_NEW, refLevel, true).frames;
    const refmap = PL.build_reference_map(refFrames);
    const refkeys = new Map([...refmap.voxels].filter(([, v]) => v.occ >= PL.PIPE.bg_ref_occ_min));
    const clean = clouds.map(PL.denoise);
    const online = PL.build_static_map(clean);
    const rows = [];
    for (let i = 0; i < clouds.length; i++) {
        const c0 = clouds[i];
        let pRaw = 0, crRaw = 0, cost = 0, costPerson = 0;
        const surv = { P: 0, REF: 0, UNION: 0, V2: 0 }, crRem = { REF: 0, UNION: 0, V2: 0 };
        for (let k = 0; k < c0.length; k += 4) {
            const x = c0[k], y = c0[k + 1], z = c0[k + 2];
            const refHit = match(refkeys, x, y, z);
            const onHit = match(online, x, y, z);
            const refSup = onHit ? match(refkeys, onHit.x, onHit.y, onHit.z) : null;
            const rem = { P: !!onHit, REF: !!refHit, UNION: !!(refHit || onHit), V2: !!(refHit || (onHit && refSup)) };
            const inPerson = (x - center[0]) ** 2 + (y - center[1]) ** 2 <= R2 && z >= ZLO && z <= ZHI;
            if (inPerson) { pRaw++; for (const a in surv) if (!rem[a]) surv[a]++; }
            const inCrates = x >= 2.35 && x <= 3.30 && y >= -1.25 && y <= -0.50 && z >= 0.05 && z <= 1.6;
            if (inCrates) { crRaw++; for (const a of ["REF", "UNION", "V2"]) if (rem[a]) crRem[a]++; }
            if (!rem.V2 && rem.UNION) { cost++; if (inPerson) costPerson++; }
        }
        rows.push({ i, person: { raw: pRaw, surv }, crates: { raw: crRaw, removed: crRem }, cost: { total: cost, person: costPerson } });
    }
    const pRaw = rows.map(x => x.person.raw), P = rows.map(x => x.person.surv.P), REF = rows.map(x => x.person.surv.REF),
        UN = rows.map(x => x.person.surv.UNION), V2 = rows.map(x => x.person.surv.V2);
    const p50 = a => stat(a).p50;
    const out = { sid: s.sid, registration: { state: loaded.state, artifact_id: loaded.artifact_id },
        person_raw_p50: p50(pRaw),
        arm_person_p50: { P: p50(P), REF: p50(REF), UNION: p50(UN), V2: p50(V2) },
        arm_person_pct: { P: 100 * p50(P) / p50(pRaw), REF: 100 * p50(REF) / p50(pRaw), UNION: 100 * p50(UN) / p50(pRaw), V2: 100 * p50(V2) / p50(pRaw) },
        crates: { raw_p50: p50(rows.map(x => x.crates.raw)), removed_pct: Object.fromEntries(["REF", "UNION", "V2"].map(a => [a, 100 * p50(rows.map(x => x.crates.removed[a])) / Math.max(1, p50(rows.map(x => x.crates.raw)))])) },
        cost_total: rows.reduce((s2, x) => s2 + x.cost.total, 0), cost_person: rows.reduce((s2, x) => s2 + x.cost.person, 0),
        prev_ref_p50: s.prev.ref, prev_union_p50: s.prev.union,
        harness_ref_ok: Math.abs(p50(REF) - s.prev.ref) <= 8,
        harness_union_ok: Math.abs(p50(UN) - s.prev.union) <= Math.max(5, Math.round(0.3 * s.prev.union)),
        frames: rows };
    newResults.push(out);
    console.log(`== ${s.sid}: person raw p50=${out.person_raw_p50}  P=${out.arm_person_pct.P.toFixed(1)}%  REF=${out.arm_person_pct.REF.toFixed(1)}%  UNION=${out.arm_person_pct.UNION.toFixed(1)}%  V2=${out.arm_person_pct.V2.toFixed(1)}%`);
    console.log(`   crates removed: REF=${out.crates.removed_pct.REF.toFixed(1)}% UNION=${out.crates.removed_pct.UNION.toFixed(1)}% V2=${out.crates.removed_pct.V2.toFixed(1)}%   cost total=${out.cost_total} (person=${out.cost_person})`);
    console.log(`   harness: REF ${out.harness_ref_ok ? "OK" : "MISMATCH"} (${p50(REF)} vs prev ${s.prev.ref})  UNION ${out.harness_union_ok ? "OK" : "MISMATCH"} (${p50(UN)} vs prev ${s.prev.union})`);
}

/* ---- 段二：旧对（223757→203349）WD01/WD02 不回归 ----
 * 注意：该 artifact 在当前代码下为 STALE（METHOD_STALE，R39 统计修复后设计如此）。
 * 诊断用：直接读 registration.json（经 manifest SHA 防篡改校验）应用 transform；不走 loader 新鲜度门。 */
const pairdir = path.join(ROOT, "captures/registration", "cap_20261002_223757__to__cap_20261004_203349");
const prov = R.read(path.join(pairdir, "provenance.json"));
const srcSid = prov.source_session.sid, refSid = prov.reference_session.sid;
const srcLv = R.levelingBinding(ROOT, srcSid, prov.source_leveling.job_id);
const refLv = R.levelingBinding(ROOT, refSid, prov.reference_leveling.job_id);
const regJson = R.read(path.join(pairdir, "registration.json"));
const manifest2 = R.read(path.join(pairdir, "manifest.json"));
if (manifest2.files["registration.json"] !== R.shaFile(path.join(pairdir, "registration.json"))) throw new Error("REG_TAMPERED");
const Rm = regJson.rotation_row_major, Tm = regJson.translation_m;
const raw2 = R.loadFrames(ROOT, srcSid, srcLv).frames;
const clouds2 = raw2.map(buf => {
    const b = buf.slice();
    for (let i = 0; i < b.length; i += 4) {
        const q = M.m3.apply(Rm, b[i], b[i + 1], b[i + 2]);
        b[i] = q[0] + Tm[0]; b[i + 1] = q[1] + Tm[1]; b[i + 2] = q[2] + Tm[2];
    }
    return b;
});
const refFrames2 = R.loadFrames(ROOT, refSid, refLv, true).frames;
const refkeys2 = new Map([...PL.build_reference_map(refFrames2).voxels].filter(([, v]) => v.occ >= PL.PIPE.bg_ref_occ_min));
const clean2 = clouds2.map(PL.denoise);
const online2 = PL.build_static_map(clean2);
const wd01c = M.m3.apply(Rm, 3.50, -0.76, 0).map((v, i) => v + Tm[i]);
const wd01 = { raw: 0, rem: { REF: 0, UNION: 0, V2: 0 } };
const wd02 = { raw: 0, rem: { REF: 0, UNION: 0, V2: 0 } };
let cost2 = 0;
for (let i = 0; i < clouds2.length; i++) {
    const c0 = clouds2[i];
    for (let k = 0; k < c0.length; k += 4) {
        const x = c0[k], y = c0[k + 1], z = c0[k + 2];
        if (z < 0.10) continue;
        const refHit = match(refkeys2, x, y, z);
        const onHit = match(online2, x, y, z);
        const refSup = onHit ? match(refkeys2, onHit.x, onHit.y, onHit.z) : null;
        const rem = { REF: !!refHit, UNION: !!(refHit || onHit), V2: !!(refHit || (onHit && refSup)) };
        const inWd01 = (x - wd01c[0]) ** 2 + (y - wd01c[1]) ** 2 <= 0.9 * 0.9 && z < 2.2;
        const far = Math.hypot(x, y) > 8 || [[10.75, 4.25], [10.25, -1.75], [10.5, 5.5]].some(q => Math.hypot(x - q[0], y - q[1]) <= 1.5);
        if (inWd01) { wd01.raw++; for (const a in wd01.rem) if (rem[a]) wd01.rem[a]++; }
        if (far) { wd02.raw++; for (const a in wd02.rem) if (rem[a]) wd02.rem[a]++; }
        if (!rem.V2 && rem.UNION) cost2++;
    }
}
const pct2 = (o, a) => 100 * o.rem[a] / Math.max(1, o.raw);
const pairOut = { src: srcSid, ref: refSid, loader: "STALE->direct-transform (diagnostic; manifest SHA checked)",
    wd01: { raw: wd01.raw, removed_pct: { REF: pct2(wd01, "REF"), UNION: pct2(wd01, "UNION"), V2: pct2(wd01, "V2") } },
    wd02: { raw: wd02.raw, removed_pct: { REF: pct2(wd02, "REF"), UNION: pct2(wd02, "UNION"), V2: pct2(wd02, "V2") } },
    cost_total: cost2 };
console.log(`== old pair ${srcSid}->${refSid} (STALE -> direct-transform diagnostic)`);
console.log(`   WD01 raw=${wd01.raw}: removed REF=${pct2(wd01, "REF").toFixed(1)}% UNION=${pct2(wd01, "UNION").toFixed(1)}% V2=${pct2(wd01, "V2").toFixed(1)}%`);
console.log(`   WD02 raw=${wd02.raw}: removed REF=${pct2(wd02, "REF").toFixed(1)}% UNION=${pct2(wd02, "UNION").toFixed(1)}% V2=${pct2(wd02, "V2").toFixed(1)}%`);
console.log(`   cost total=${cost2}`);

/* ---- 判定 ---- */
const verdicts = [];
for (const o of newResults) {
    verdicts.push({ id: `F02-${o.sid.slice(-6)}`, target: "V2 person p50 ≥95%", actual: +o.arm_person_pct.V2.toFixed(1), pass: o.arm_person_pct.V2 >= 95 });
    verdicts.push({ id: `HARNESS-${o.sid.slice(-6)}`, target: "REF/UNION 复现上轮 ±3pt/±20%", actual: `${o.harness_ref_ok}/${o.harness_union_ok}`, pass: o.harness_ref_ok && o.harness_union_ok });
}
verdicts.push({ id: "F03a-WD01", target: "V2 删除率 ≥ REF −2pt", actual: `${pct2(wd01, "V2").toFixed(1)} vs ${pct2(wd01, "REF").toFixed(1)}`, pass: pct2(wd01, "V2") >= pct2(wd01, "REF") - 2 });
verdicts.push({ id: "F03b-WD02", target: "V2 删除率 ≥ REF −2pt", actual: `${pct2(wd02, "V2").toFixed(1)} vs ${pct2(wd02, "REF").toFixed(1)}`, pass: pct2(wd02, "V2") >= pct2(wd02, "REF") - 2 });
for (const v of verdicts) console.log(`${v.pass ? "PASS" : "FAIL"}  ${v.id}: ${v.target} | actual=${v.actual}`);

const write = (n, v) => fs.writeFileSync(path.join(__dirname, n), JSON.stringify(v, null, 2) + "\n", { flag: "wx" });
write("fusion_v2_ab_results.json", { schema: 1, kind: "fusion_v2_offline_ab", sessions: newResults, old_pair: pairOut, verdicts,
    code_binding: { human_pipe_lib: crypto.createHash("sha256").update(fs.readFileSync(path.join(ROOT, "pc_apps/human_replay/human_pipe_lib.js"))).digest("hex"),
        registration: crypto.createHash("sha256").update(fs.readFileSync(path.join(ROOT, "pc_apps/human_replay/registration.js"))).digest("hex"),
        script: crypto.createHash("sha256").update(fs.readFileSync(__filename)).digest("hex") } });
console.log("done. fails=" + verdicts.filter(v => !v.pass).length);

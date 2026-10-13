"use strict";
/* 生成 retention_view 数据：3 会话 × 8 帧，裁剪区点坐标(Int16 mm)+命运类别(Uint8)。
 * 类别: 0=保留 1=参考层删除 2=在线层删除 3=cleanup 删除 4=预剔除(denoise/地面/工作空间)
 * 输出: view_refvox.js（空场模板体素） + view_data_<sid>.js。只读；wx 独占创建。 */
const fs = require("fs"), path = require("path");
const ROOT = path.resolve(__dirname, "../../../..");
const PL = require(path.join(ROOT, "pc_apps/human_replay/human_pipe_lib.js"));
const R = require(path.join(ROOT, "pc_apps/human_replay/registration.js"));
const M = require(path.join(ROOT, "pc_apps/human_replay/registration_method.js"));
const REF = "cap_20261007_233658", REFJOB = "3c793d7bda0f4ced86b20ac8076e7b0e";
const SESSIONS = [
    { sid: "cap_20261007_215540", job: "21666bec7e7b44b2bdbbaa790bf4501b", center: [2.10, -0.57] },
    { sid: "cap_20261007_215623", job: "a9e1e01fa6644f93aa686daa330a5fcd", center: [2.14, -0.45] },
    { sid: "cap_20261007_215643", job: "e46d035de1b34378b841ca3bc2a1c8f6", center: [2.11, -0.36] },
];
const NFRAMES = 8, CROP_HALF = 1.9, ZLO = -0.15, ZHI = 2.40, PMAX = 18000;
const keyAt = (a, k) => a[k] + "," + a[k + 1] + "," + a[k + 2] + "," + a[k + 3];

const refLevel = R.levelingBinding(ROOT, REF, REFJOB);
const refFrames = R.loadFrames(ROOT, REF, refLevel, true).frames;
const refmap = PL.build_reference_map(refFrames);
const refkeys = new Map([...refmap.voxels].filter(([, v]) => v.occ >= PL.PIPE.bg_ref_occ_min));
const refvox = [...refkeys.values()].map(v => [+v.x.toFixed(3), +v.y.toFixed(3), +v.z.toFixed(3)]);
fs.writeFileSync(path.join(__dirname, "view_refvox.js"), "window.RETENTION_REFVOX=" + JSON.stringify(refvox) + ";\n", { flag: "wx" });
console.log(`refvox: ${refvox.length}`);

for (const s of SESSIONS) {
    const regdir = path.join(ROOT, "captures/registration", `${s.sid}__to__${REF}`);
    const loaded = R.load(regdir, { root: ROOT, source: s.sid, reference: REF });
    if (loaded.state !== "VALID" && loaded.state !== "DEGRADED") throw new Error(s.sid + " reg=" + loaded.state);
    const shadow = loaded.state === "DEGRADED";
    const sl = R.levelingBinding(ROOT, s.sid, s.job);
    const raw = R.loadFrames(ROOT, s.sid, sl).frames;
    const clouds = raw.map(buf => R.applyRegistration({ buf, frame: "leveled_session:" + s.sid }, loaded, { shadow }).buf);
    const r = loaded.registration;
    const center = M.m3.apply(r.rotation_row_major, s.center[0], s.center[1], 0).map((v, i) => v + r.translation_m[i]);
    const cx = center[0], cy = center[1];
    const clean = clouds.map(PL.denoise);
    const online = PL.build_static_map(clean);
    const nf = clouds.length;
    const sel = [];
    for (let i = 0; i < NFRAMES; i++) sel.push(Math.round(i * (nf - 1) / (NFRAMES - 1)));
    const outFrames = [];
    for (const i of sel) {
        const s1 = PL.extract_foreground(clean[i], refkeys);
        const f2 = PL.extract_foreground(s1.fg_xyzi, online);
        const iso = PL.cleanup_isolated_fg(f2.fg_xyzi);
        const setRef = new Set(), setAll = new Set(), setPost = new Set();
        for (let k = 0; k < s1.fg_xyzi.length; k += 4) setRef.add(keyAt(s1.fg_xyzi, k));
        for (let k = 0; k < f2.fg_xyzi.length; k += 4) setAll.add(keyAt(f2.fg_xyzi, k));
        for (let k = 0; k < iso.xyzi.length; k += 4) setPost.add(keyAt(iso.xyzi, k));
        const c0 = clouds[i];
        const pts = [];
        for (let k = 0; k < c0.length; k += 4) {
            const x = c0[k], y = c0[k + 1], z = c0[k + 2];
            if (Math.abs(x - cx) > CROP_HALF || Math.abs(y - cy) > CROP_HALF || z < ZLO || z > ZHI) continue;
            const rr = x * x + y * y + z * z;
            let cls;
            if (!Number.isFinite(rr) || rr < PL.PIPE.range_min_m ** 2 || rr > PL.PIPE.range_max_m ** 2 ||
                z < PL.PIPE.ground_keep_below_m || z > PL.PIPE.z_max_m) cls = 4;
            else if (!setRef.has(keyAt(c0, k))) cls = 1;
            else if (!setAll.has(keyAt(c0, k))) cls = 2;
            else if (!setPost.has(keyAt(c0, k))) cls = 3;
            else cls = 0;
            pts.push([x, y, z, cls]);
        }
        const stride = Math.max(1, Math.floor(pts.length / PMAX));
        const keep = stride > 1 ? pts.filter((_, j) => j % stride === 0) : pts;
        const pos = new Int16Array(keep.length * 3), clsA = new Uint8Array(keep.length);
        keep.forEach((p, j) => { pos[j * 3] = Math.round(p[0] * 1000); pos[j * 3 + 1] = Math.round(p[1] * 1000); pos[j * 3 + 2] = Math.round(p[2] * 1000); clsA[j] = p[3]; });
        outFrames.push({ i, n: keep.length,
            pos: Buffer.from(pos.buffer, pos.byteOffset, pos.byteLength).toString("base64"),
            cls: Buffer.from(clsA.buffer, clsA.byteOffset, clsA.byteLength).toString("base64") });
        console.log(`${s.sid} f${i}: crop=${pts.length} kept=${keep.length} stride=${stride}`);
    }
    const data = { center: [+cx.toFixed(4), +cy.toFixed(4)], radius: 0.55, z: [0.05, 2.30], nf, frames: outFrames };
    fs.writeFileSync(path.join(__dirname, `view_data_${s.sid}.js`),
        "window.RETENTION_VIEW=window.RETENTION_VIEW||{};window.RETENTION_VIEW[" + JSON.stringify(s.sid) + "]=" + JSON.stringify(data) + ";\n", { flag: "wx" });
    console.log("written view_data_" + s.sid + ".js");
}
console.log("done.");

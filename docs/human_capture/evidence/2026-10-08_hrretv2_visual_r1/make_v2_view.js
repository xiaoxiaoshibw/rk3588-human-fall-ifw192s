"use strict";
/* HR-RET-V2 效果可视化数据：P（仅在线） vs v2（参考 ∨ 在线∧参考支持）逐点命运。
 * 类别 cls：0=两臂都留 1=参考命中（v2 删；P 留） 2=在线∧参考支持（两臂都删） 4=预剔除（denoise/地面/工作空间）
 *          3/5/6/7 = P 删、v2 救回，按链判定分通道：
 *          3=人通道（joint CONFIRMED_HUMAN） 5=几何候选（label HUMAN_CANDIDATE）
 *          6=链判 NON_HUMAN（家具泄漏，如桌子） 7=救回但未成簇/被 cleanup 清理
 * 会话：三段静立人（215540/215623/215643）；参考=空场 233658；各取 8 帧均匀采样，裁剪区=人位±1.9m。
 * 诊断口径：artifact 现已因代码绑定漂移 STALE → 直读 registration.json 的 transform（非生产消费）；
 * 参考层/在线层构建与 P2 A/B、inc2 digest D4 完全同参。只读；输出 wx 独占创建。 */
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
const R2M = PL.PIPE.bg_match_radius ** 2;
function match(map, x, y, z) {   /* 与 _bg_match 同参：3×3×3 体素邻域 + 0.12m */
    const ix = Math.floor(x / PL.PIPE.bg_voxel_xy), iy = Math.floor(y / PL.PIPE.bg_voxel_xy), iz = Math.floor(z / PL.PIPE.bg_voxel_z);
    for (let a = -1; a <= 1; a++) for (let b = -1; b <= 1; b++) for (let c = -1; c <= 1; c++) {
        const rec = map.get(((ix + a + 4096) * 8192 + (iy + b + 4096)) * 8192 + (iz + c + 4096));
        if (!rec) continue;
        const dx = rec.x - x, dy = rec.y - y, dz = rec.z - z;
        if (dx * dx + dy * dy + dz * dz < R2M) return rec;
    }
    return null;
}

const refFrames = R.loadFrames(ROOT, REF, R.levelingBinding(ROOT, REF, REFJOB), true).frames;
const refkeys = new Map([...PL.build_reference_map(refFrames).voxels].filter(([, v]) => v.occ >= PL.PIPE.bg_ref_occ_min));
fs.writeFileSync(path.join(__dirname, "v2_view_refvox.js"),
    "window.RETV2_REFVOX=" + JSON.stringify([...refkeys.values()].map(v => [+v.x.toFixed(3), +v.y.toFixed(3), +v.z.toFixed(3)])) + ";\n", { flag: "wx" });
console.log("refvox: " + refkeys.size);

for (const s of SESSIONS) {
    const reg = JSON.parse(fs.readFileSync(path.join(ROOT, "captures/registration", s.sid + "__to__" + REF, "registration.json"), "utf8"));
    const Rm = reg.rotation_row_major.flat(), t = reg.translation_m;
    const raw = R.loadFrames(ROOT, s.sid, R.levelingBinding(ROOT, s.sid, s.job), false).frames;
    const clouds = raw.map(buf => {
        const c = buf.slice();
        for (let i = 0; i < c.length; i += 4) { const q = M.m3.apply(Rm, c[i], c[i + 1], c[i + 2]); for (let j = 0; j < 3; j++) c[i + j] = q[j] + t[j]; }
        return c;
    });
    const center = M.m3.apply(Rm, s.center[0], s.center[1], 0).map((v, i) => v + t[i]);
    const cx = center[0], cy = center[1];
    const clean = clouds.map(PL.denoise);
    const online = PL.build_static_map(clean);
    const nf = clouds.length;
    const sel = []; for (let i = 0; i < NFRAMES; i++) sel.push(Math.round(i * (nf - 1) / (NFRAMES - 1)));
    /* v2 全链逐帧（tracker 连续，采样帧取人簇摘要：离人位最近的簇） */
    const tracker = new PL.Tracker();
    const row_at = {};
    for (let i = 0; i < nf; i++) {
        const r = PL.pipeline_frame(clouds[i], i, { static_keys: online, tracker, fusion: { refkeys } });
        if (sel.indexOf(i) < 0) continue;
        let best = null;
        for (const c of r.clusters) { const d = Math.hypot(c.cx - cx, c.cy - cy); if (!best || d < best.d) best = { d, c }; }
        const per = { CONFIRMED_HUMAN: 0, HUMAN_CANDIDATE: 0, NON_HUMAN: 0 };
        r.clusters.forEach(c => per[c.joint]++);
        row_at[i] = { person: best && best.d < 0.9 ? { label: best.c.label, joint: best.c.joint, confirmed: !!best.c.track_confirmed } : null,
            clusters: per, n_fg: r.n_foreground, kept: r.fusion ? r.fusion.n_online_only_kept : 0 };
    }
    /* 采样帧逐点分类（原始配准点云；cls4 = denoise/工作空间预剔除）
     * cls3 = 救回·人通道（joint CONFIRMED_HUMAN）；cls5 = 救回·几何候选（label HUMAN_CANDIDATE）；
     * cls6 = 救回·链判 NON_HUMAN（家具泄漏，如桌子）；cls7 = 救回但未成簇/被 cleanup 清理。 */
    const outFrames = [];
    for (const i of sel) {
        const rp = PL.pipeline_frame(clouds[i], i, { static_keys: online, tracker: new PL.Tracker(), fusion: { refkeys } });
        const fgArr = PL.extract_foreground_fused(clean[i], refkeys, online).fg_xyzi;
        const iso = PL.cleanup_isolated_fg(fgArr);
        const cs = PL.cluster_voxels(PL.voxelize(iso.xyzi)).filter(c => c.acc.n >= PL.PIPE.human_n_min);
        if (cs.length !== rp.clusters.length) throw new Error("cluster mismatch f" + i);
        const owner = new Map(); cs.forEach((c, ci) => c.keys.forEach(k => owner.set(k, ci)));
        const laneOf = (x, y) => {
            const ci = owner.get(PL.key_vox(x, y));
            if (ci === undefined) return 7;
            const f = rp.clusters[ci];
            if (f.joint === "CONFIRMED_HUMAN") return 3;
            return f.label === "HUMAN_CANDIDATE" ? 5 : 6;
        };
        const c0 = clouds[i];
        const pts = [];
        for (let k = 0; k < c0.length; k += 4) {
            const x = c0[k], y = c0[k + 1], z = c0[k + 2];
            if (Math.abs(x - cx) > CROP_HALF || Math.abs(y - cy) > CROP_HALF || z < ZLO || z > ZHI) continue;
            const rr = x * x + y * y + z * z;
            let cls;
            if (!isFinite(rr) || rr < PL.PIPE.range_min_m ** 2 || rr > PL.PIPE.range_max_m ** 2 ||
                z < PL.PIPE.ground_keep_below_m || z > PL.PIPE.z_max_m) cls = 4;
            else if (match(refkeys, x, y, z)) cls = 1;
            else {
                const on = match(online, x, y, z);
                cls = !on ? 0 : (match(refkeys, on.x, on.y, on.z) ? 2 : laneOf(x, y));
            }
            pts.push([x, y, z, cls]);
        }
        const stride = Math.max(1, Math.floor(pts.length / PMAX));
        const keep = stride > 1 ? pts.filter((_, j) => j % stride === 0) : pts;
        const pos = new Int16Array(keep.length * 3), clsA = new Uint8Array(keep.length);
        keep.forEach((p, j) => { pos[j * 3] = Math.round(p[0] * 1000); pos[j * 3 + 1] = Math.round(p[1] * 1000); pos[j * 3 + 2] = Math.round(p[2] * 1000); clsA[j] = p[3]; });
        outFrames.push({ i, n: keep.length,
            pos: Buffer.from(pos.buffer, pos.byteOffset, pos.byteLength).toString("base64"),
            cls: Buffer.from(clsA.buffer, clsA.byteOffset, clsA.byteLength).toString("base64"),
            row: row_at[i] });
        const per = {}; pts.forEach(p => per[p[3]] = (per[p[3]] || 0) + 1);
        console.log(`${s.sid} f${i}: crop=${pts.length} kept=${keep.length} stride=${stride} cls=${JSON.stringify(per)}`);
    }
    const data = { center: [+cx.toFixed(4), +cy.toFixed(4)], radius: 0.55, z: [0.10, 2.30], nf, frames: outFrames };
    fs.writeFileSync(path.join(__dirname, `v2_view_data_${s.sid}.js`),
        "window.RETV2_VIEW=window.RETV2_VIEW||{};window.RETV2_VIEW[" + JSON.stringify(s.sid) + "]=" + JSON.stringify(data) + ";\n", { flag: "wx" });
    console.log("written v2_view_data_" + s.sid + ".js");
}
console.log("done.");

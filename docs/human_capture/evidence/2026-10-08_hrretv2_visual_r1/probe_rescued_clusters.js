"use strict";
/* 诊断：v2 救回点（cls3=在线-only 保留）的团块身份与被判定结果。
 * 回答：上方绿色团块（桌子）是什么、为何被 v2 保留、决策层被判成什么。
 * 口径同 v2_view / A/B / inc2 D4：artifact 直读 transform（STALE，非生产消费）。只读。 */
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
const R2M = PL.PIPE.bg_match_radius ** 2;
function match(map, x, y, z) {
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
const refArr = [...refkeys.values()];
function nearestRefDist(x, y, z) {
    let best = Infinity;
    for (const v of refArr) { const dx = v.x - x, dy = v.y - y, dz = v.z - z; const d2 = dx * dx + dy * dy + dz * dz; if (d2 < best) best = d2; }
    return Math.sqrt(best);
}

for (const s of SESSIONS) {
    const reg = JSON.parse(fs.readFileSync(path.join(ROOT, "captures/registration", s.sid + "__to__" + REF, "registration.json"), "utf8"));
    const Rm = reg.rotation_row_major.flat(), t = reg.translation_m;
    const raw = R.loadFrames(ROOT, s.sid, R.levelingBinding(ROOT, s.sid, s.job), false).frames;
    const clouds = raw.map(buf => { const c = buf.slice(); for (let i = 0; i < c.length; i += 4) { const q = M.m3.apply(Rm, c[i], c[i + 1], c[i + 2]); for (let j = 0; j < 3; j++) c[i + j] = q[j] + t[j]; } return c; });
    const center = M.m3.apply(Rm, s.center[0], s.center[1], 0).map((v, i) => v + t[i]);
    const clean = clouds.map(PL.denoise);
    const online = PL.build_static_map(clean);
    const tracker = new PL.Tracker();
    console.log(`\n== ${s.sid}  人位(配准系)=(${center[0].toFixed(2)}, ${center[1].toFixed(2)})`);
    for (let i = 0; i < clouds.length; i++) {
        const r = PL.pipeline_frame(clouds[i], i, { static_keys: online, tracker, fusion: { refkeys } });
        if (i !== 0 && i !== clouds.length - 1) continue;
        const c0 = clouds[i];
        const rescued = [], byVox = new Map();
        for (let k = 0; k < c0.length; k += 4) {
            const x = c0[k], y = c0[k + 1], z = c0[k + 2];
            const rr = x * x + y * y + z * z;
            if (!isFinite(rr) || rr < PL.PIPE.range_min_m ** 2 || rr > PL.PIPE.range_max_m ** 2 || z < PL.PIPE.ground_keep_below_m || z > PL.PIPE.z_max_m) continue;
            if (match(refkeys, x, y, z)) continue;
            const on = match(online, x, y, z);
            if (!on) continue;
            if (match(refkeys, on.x, on.y, on.z)) continue;
            rescued.push(x, y, z, 0);
            const vk = PL.key_vox(x, y);
            byVox.set(vk, (byVox.get(vk) || 0) + 1);
        }
        const blobs = PL.cluster_voxels(PL.voxelize(new Float32Array(rescued))).filter(c => c.acc.n >= 60);
        console.log(`  f${i}: v2 链簇=${r.clusters.length} [${r.clusters.map(c => c.label + "/" + c.joint + " n=" + c.n + ` @(${c.cx.toFixed(2)},${c.cy.toFixed(2)})`).join(" | ")}]`);
        const ranked = blobs.map(b => {
            const a = b.acc, n = a.n, cx = a.sx / n, cy = a.sy / n, cz = a.sz / n;
            const pipe = r.clusters.map(c => ({ c, d: Math.hypot(c.cx - cx, c.cy - cy) })).sort((u, v) => u.d - v.d)[0];
            let dmin = Infinity, dlist = [];
            const step = Math.max(1, Math.floor(n / 80));
            for (let q = 0; q < b.keys.length; q += step) { const kk = b.keys[q].split(","); const d = nearestRefDist(+kk[0] * 0.15 + 0.075, +kk[1] * 0.15 + 0.075, cz); dlist.push(d); if (d < dmin) dmin = d; }
            dlist.sort((u, v) => u - v);
            return { n, cx, cy, cz, pipe: pipe && pipe.d < 0.6 ? pipe.c.label + "/" + pipe.c.joint : "（无对应链簇）", dmin, dmed: dlist[dlist.length >> 1] };
        }).sort((a, b) => b.n - a.n);
        for (const b of ranked) {
            console.log(`    救回团 n=${b.n} @(${b.cx.toFixed(2)},${b.cy.toFixed(2)},z̄=${b.cz.toFixed(2)}) → 链判定=${b.pipe}；离最近参考体素 min=${(b.dmin * 1000).toFixed(0)}mm/中位=${(b.dmed * 1000).toFixed(0)}mm`);
        }
    }
}
console.log("\ndone.");

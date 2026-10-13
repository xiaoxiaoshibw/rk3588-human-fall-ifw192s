"use strict";
/* 为什么静立人的点被删：对 540 / 623 f0 的每一点找匹配到的静态体素，判断
 * (a) 人体自身 voxel 是否进了 online 静态图；(b) 匹配到的体素位置/距离分布。只读。 */
const fs = require("fs"), path = require("path");
const ROOT = path.resolve(__dirname, "../../../..");
const PL = require(path.join(ROOT, "pc_apps/human_replay/human_pipe_lib.js"));
const R = require(path.join(ROOT, "pc_apps/human_replay/registration.js"));
const audit = require(path.join(__dirname, "audit_lib.js"));

const CASES = [
    { sid: "cap_20261007_215540", job: "21666bec7e7b44b2bdbbaa790bf4501b", center: [2.10, -0.57] },
    { sid: "cap_20261007_215623", job: "a9e1e01fa6644f93aa686daa330a5fcd", center: [2.14, -0.45] },
];
for (const c of CASES) {
    const lv = R.levelingBinding(ROOT, c.sid, c.job);
    const { frames } = R.loadFrames(ROOT, c.sid, lv);
    const clean = frames.map(PL.denoise);
    const online = PL.build_static_map(clean);
    let near = 0, nearTier = { strong: 0, supported: 0 };
    online.forEach(v => { if (Math.hypot(v.x - c.center[0], v.y - c.center[1]) < 0.5 && v.z < 2.3) { near++; nearTier[v.tier]++; } });
    const raw = frames[0];
    let n = 0, ground = 0, matched = 0, unmatched = 0, enc = 0;
    const dists = [], off = [[], [], []];
    for (let k = 0; k < raw.length; k += 4) {
        const x = raw[k], y = raw[k + 1], z = raw[k + 2];
        const dx = x - c.center[0], dy = y - c.center[1];
        if (dx * dx + dy * dy > 0.55 * 0.55 || z < 0.05 || z > 2.3) continue;
        n++;
        if (z < PL.PIPE.ground_keep_below_m) { enc++; continue; }
        const m = audit.matcher(PL, online, [x, y, z]);
        if (m) { matched++; if (dists.length < 4000) dists.push(m.distance); if (off[0].length < 4000) { off[0].push(x - m.x); off[1].push(y - m.y); off[2].push(z - m.z); } }
        else unmatched++;
    }
    const pct = (a, p) => { const b = a.slice().sort((x, y) => x - y); return b[Math.min(b.length - 1, Math.floor(p * b.length))]; };
    console.log(`== ${c.sid} f0: person pts in cylinder=${n} (z<0.10 ground=${ground})`);
    console.log(`   map voxels with centroid within r<0.5 of person center, z<2.3: ${near} ${JSON.stringify(nearTier)}`);
    console.log(`   matched-to-static=${matched} unmatched=${unmatched}`);
    if (dists.length) {
        console.log(`   match distance p50/p95/max = ${pct(dists, .5).toFixed(3)}/${pct(dists, .95).toFixed(3)}/${dists.slice().sort((a, b) => a - b)[dists.length - 1].toFixed(3)}`);
        ["x", "y", "z"].forEach((ax, i) => {
            const a = off[i].map(Math.abs); console.log(`   |d${ax}| median=${pct(a, .5).toFixed(3)} p95=${pct(a, .95).toFixed(3)}`);
        });
    }
}

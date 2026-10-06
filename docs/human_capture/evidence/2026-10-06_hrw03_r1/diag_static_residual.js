/* HR-W03 静态残留诊断（只读，不改任何生产代码）
 *
 * 目的：量出「动的只有人、静态物还在被聚类」的真实原因——
 *   1) 残留簇的柱占用率是接近 95% 门槛（遮挡/丢点把柱打掉），
 *      还是本来就很低（散点/抖动，属另一类问题）；
 *   2) 每帧簇数 / 各证据标签占比 / 持续出现的簇位置；
 *   3) 前景体素占用率直方图（全局人口）。
 *
 * 用法：node diag_static_residual.js [sid]
 * 输出：stdout 摘要 + <sid>_diag.json
 */
"use strict";
const fs = require("fs");
const path = require("path");

const REPO = path.resolve(__dirname, "..", "..", "..", "..");
const RP = path.join(REPO, "pc_apps", "human_replay");
const RL = require(path.join(RP, "human_replay_lib.js"));
const PL = require(path.join(RP, "human_pipe_lib.js"));

const sid = process.argv[2] || "cap_20261004_203349";
const dir = path.join(REPO, "captures", "remote", sid);
const meta = JSON.parse(fs.readFileSync(path.join(dir, "meta.json"), "utf8"));
const raw = fs.readFileSync(path.join(dir, "points.bin"));
const f32 = new Float32Array(raw.buffer, raw.byteOffset, raw.byteLength / 4);

const frames = RL.frame_slice(meta);
const STRIDE = RL.STRIDE_F32;
console.log("sid=" + sid + "  frames=" + frames.length + "  fps=" + RL.default_fps(meta).toFixed(2));

/* 1) 与页面同构：全帧 denoise → 占用率（本地重算，带计数） */
const ded = frames.map(function (f) {
    return PL.denoise(RL.strided_f32_copy(f32, f.start_pts, f.count, STRIDE));
});
const occ = new Map();
for (let fi = 0; fi < ded.length; fi++) {
    const fr = ded[fi], seen = new Set();
    for (let k = 0; k < fr.length; k += 4) {
        if (fr[k + 2] < PL.PIPE.ground_keep_below_m) continue;
        const key = PL.key_vox(fr[k], fr[k + 1]);
        if (seen.has(key)) continue;
        seen.add(key);
        occ.set(key, (occ.get(key) || 0) + 1);
    }
}
const staticKeys = PL.build_static_map(ded, { drop_ground: true });
const NF = frames.length;
console.log("静态柱=" + staticKeys.size + "  曾出现柱=" + occ.size
    + "  阈值=" + Math.ceil(NF * PL.PIPE.bg_occupancy_ratio) + "/" + NF + " 帧");

/* 全局占用率直方图（曾出现柱按占用帧数分桶） */
const buckets = new Array(11).fill(0);
occ.forEach(function (c) {
    const b = Math.min(10, Math.floor((c / NF) * 10.0001));
    buckets[b]++;
});
console.log("曾出现柱占用率直方图 (0-10%..90-100%): " + buckets.join(" "));

/* 2) 逐帧管线（只重建 cluster→voxel 映射用于查占用率；不读 fall 事件） */
const tracker = new PL.Tracker();
const clusterRows = [];
for (let i = 0; i < frames.length; i++) {
    const f = frames[i];
    const slice = RL.strided_f32_copy(f32, f.start_pts, f.count, STRIDE);
    const clean = PL.denoise(slice);
    const fg = PL.extract_foreground(clean, staticKeys);
    const rawClusters = PL.cluster_voxels(fg.vox_fg);
    const ev = PL.evidence_postpass(fg.fg_xyzi, rawClusters);
    for (let ci = 0; ci < rawClusters.length; ci++) {
        const feat = PL.cluster_features(rawClusters[ci]);
        if (!feat.ok) continue;
        const tag = PL.evidence_label(ev.clusters_extra[ci]).label;
        const occs = rawClusters[ci].keys.map(function (k) { return occ.get(k) || 0; });
        clusterRows.push({
            frame: i, cx: feat.cx, cy: feat.cy, zmin: feat.zmin, zmax: feat.zmax,
            h: feat.height_m, n: feat.n, tag: tag, upcos: feat.upcos,
            occ_med: median(occs), occ_min: Math.min.apply(null, occs),
        });
    }
    tracker.tick(i, []);   /* 空 tick：只为保持与页面同样的调用序列 */
}

/* 3) 持续簇：以 0.3m 网格归并同一位置，统计出现帧数 */
const byCell = new Map();
for (const r of clusterRows) {
    const key = Math.round(r.cx / 0.3) + "," + Math.round(r.cy / 0.3);
    let a = byCell.get(key);
    if (!a) { a = { frames: new Set(), tags: {}, zmin: 1e9, zmax: -1e9, occ: [], n: 0 }; byCell.set(key, a); }
    a.frames.add(r.frame);
    a.tags[r.tag] = (a.tags[r.tag] || 0) + 1;
    a.zmin = Math.min(a.zmin, r.zmin); a.zmax = Math.max(a.zmax, r.zmax);
    a.occ.push(r.occ_med); a.n++;
}

const persist = [], transient = [];
byCell.forEach(function (a, key) {
    const frac = a.frames.size / NF;
    const rec = { key: key, frac: frac, zmin: a.zmin, zmax: a.zmax,
                  occ_med: median(a.occ), occ_p90: pct(a.occ, 0.9), n_obs: a.n };
    if (frac >= 0.8) persist.push(rec); else transient.push(rec);
});
persist.sort(function (a, b) { return b.frac - a.frac; });

console.log("总簇观测=" + clusterRows.length + "  唯一位置=" + byCell.size
    + "  持续(≥80%帧)=" + persist.length + "  瞬态=" + transient.length);
const tagCount = {};
for (const r of clusterRows) tagCount[r.tag] = (tagCount[r.tag] || 0) + 1;
console.log("标签计数=" + JSON.stringify(tagCount));

console.log("\n持续位置（前 15，按出现率）：");
console.log("frac  zmin..zmax   占用率med/p90  key");
for (const p of persist.slice(0, 15)) {
    console.log((p.frac * 100).toFixed(0) + "%  " + p.zmin.toFixed(2) + ".." + p.zmax.toFixed(2)
        + "  " + p.occ_med + "/" + p.occ_p90 + "  " + p.key);
}

/* 持续簇的占用率分布（帧数换算成 %） */
const pOcc = persist.map(function (p) { return p.occ_med / NF; });
console.log("\n持续簇占用率分位: p10=" + (pct(pOcc, 0.1) * 100).toFixed(0) + "% p50="
    + (pct(pOcc, 0.5) * 100).toFixed(0) + "% p90=" + (pct(pOcc, 0.9) * 100).toFixed(0) + "%");

const out = { sid: sid, frames: NF, static_keys: staticKeys.size, columns_seen: occ.size,
              occ_hist: buckets, tag_count: tagCount, persist: persist, transient: transient,
              clusters: clusterRows };
fs.writeFileSync(path.join(__dirname, sid + "_diag.json"), JSON.stringify(out));

function median(a) { return pct(a, 0.5); }
function pct(a, q) {
    if (!a.length) return NaN;
    const s = a.slice().sort(function (x, y) { return x - y; });
    return s[Math.min(s.length - 1, Math.max(0, Math.round(q * (s.length - 1))))];
}

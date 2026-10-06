/* CL-01 · 05_cluster_probe.js — 真实问题帧 cluster lineage + bridge analysis（只读）
 *
 * 复刻 production 前景链（leveled → denoise → extract_foreground(在线 map) → cleanup → voxelize →
 * cluster_voxels），对重点帧逐簇输出 lineage 统计 + 桥接（cut vertex / removal probe）分析，
 * 并附两个只读诊断（非 AB 变量）：
 *   - refMatch 比例：簇内点对 R3.1 reference（occ≥0.5, d<0.12）的匹配占比（static proxy）
 *   - oracle probe：把 reference 匹配点拆掉后再聚类，看 merge 是否自然消失（residual vs adjacency 归因）
 * 另有全帧聚合统计（fragment/规模/runtime）。
 *
 * 输出：06_cluster_stats.json（逐簇 + 聚合）、07_bridge_analysis.json（桥接/removal probe）、stdout 摘要。
 * 不实现 B/C/D 变体；不改 production。
 *
 * 用法: node 05_cluster_probe.js
 */
"use strict";
const fs = require("fs");
const path = require("path");
const HERE = __dirname;
const REPO = path.resolve(HERE, "..", "..", "..", "..");
const RP = path.join(REPO, "pc_apps", "human_replay");
const RL = require(path.join(RP, "human_replay_lib.js"));
const PL = require(path.join(RP, "human_pipe_lib.js"));

const REF_SID = "cap_20261004_203349";
const CUR_SID = "cap_20261002_223757";
const OCC = 0.5, MATCH_R = 0.12;

const BG_BASE = 8192, BG_OFF = 4096;
function bg_key_ijk(ix, iy, iz) { return ((ix + BG_OFF) * BG_BASE + (iy + BG_OFF)) * BG_BASE + (iz + BG_OFF); }

function resolve_transform(sid) {
    const LV = path.join(REPO, "captures", "leveled");
    let best = null;
    for (const job of fs.readdirSync(LV)) {
        const jd = path.join(LV, job);
        const tfPath = path.join(jd, "tls", "transform.json"), rpPath = path.join(jd, "report.json");
        if (!fs.existsSync(tfPath) || !fs.existsSync(rpPath)) continue;
        let report, tr;
        try { report = JSON.parse(fs.readFileSync(rpPath, "utf8")); tr = JSON.parse(fs.readFileSync(tfPath, "utf8")); } catch (e) { continue; }
        if (report.sid !== sid || report.recommended !== "tls" || !tr || !tr.R || !tr.t) continue;
        const mt = fs.statSync(jd).mtimeMs;
        if (!best || mt > best.mtime) best = { mtime: mt, R: tr.R, t: tr.t, job: job, transform_id: tr.transform_id };
    }
    return best;
}
function apply_Rt(arr, R, t) {
    const r = R.flat ? R.flat() : R;
    for (let k = 0; k < arr.length; k += 4) {
        const x = arr[k], y = arr[k + 1], z = arr[k + 2];
        arr[k] = r[0] * x + r[1] * y + r[2] * z + t[0];
        arr[k + 1] = r[3] * x + r[4] * y + r[5] * z + t[1];
        arr[k + 2] = r[6] * x + r[7] * y + r[8] * z + t[2];
    }
}
function load_leveled_denoised(sid) {
    const dir = path.join(REPO, "captures", "remote", sid);
    const meta = JSON.parse(fs.readFileSync(path.join(dir, "meta.json"), "utf8"));
    const raw = fs.readFileSync(path.join(dir, "points.bin"));
    const f32 = new Float32Array(raw.buffer, raw.byteOffset, raw.byteLength / 4);
    const frames = RL.frame_slice(meta), STRIDE = RL.STRIDE_F32, tf = resolve_transform(sid);
    const ded = frames.map(f => {
        const s = RL.strided_f32_copy(f32, f.start_pts, f.count, STRIDE);
        if (tf) apply_Rt(s, tf.R, tf.t);
        return PL.denoise(s);
    });
    return { dir: dir, frames: ded, tf: tf };
}
function sha256_file(p) { return require("crypto").createHash("sha256").update(fs.readFileSync(p)).digest("hex"); }

console.log("[cl01] loading " + REF_SID + " (reference) ...");
const REF = load_leveled_denoised(REF_SID);
console.log("[cl01] loading " + CUR_SID + " (current) ...");
const CUR = load_leveled_denoised(CUR_SID);
const refMap = PL.build_reference_map(REF.frames);
const CUR_ONLINE = PL.build_static_map(CUR.frames, { drop_ground: true });
const VX = PL.PIPE.bg_voxel_xy, VZ = PL.PIPE.bg_voxel_z, VXY = PL.PIPE.bg_voxel_xy;

/* ref 匹配（occ≥0.5, d<0.12 或 AABB<0.12 分开记） */
function refScan(px, py, pz) {
    const ix = Math.floor(px / VX), iy = Math.floor(py / VX), iz = Math.floor(pz / VZ);
    let d0 = Infinity, d1 = Infinity;
    for (let a = -1; a <= 1; a++) for (let b = -1; b <= 1; b++) for (let c = -1; c <= 1; c++) {
        const rec = refMap.voxels.get(bg_key_ijk(ix + a, iy + b, iz + c));
        if (!rec || rec.occ < OCC) continue;
        const dx = rec.x - px, dy = rec.y - py, dz = rec.z - pz;
        const c2 = dx * dx + dy * dy + dz * dz; if (c2 < d0) d0 = c2;
        const bx = (ix + a) * VX, by = (iy + b) * VXY, bz = (iz + c) * VZ;
        const ex = Math.max(bx - px, 0, px - (bx + VX)), ey = Math.max(by - py, 0, py - (by + VXY))
            , ez = Math.max(bz - pz, 0, pz - (bz + VZ));
        const b2 = ex * ex + ey * ey + ez * ez; if (b2 < d1) d1 = b2;
    }
    return { d0: d0 === Infinity ? null : Math.sqrt(d0), d1: d1 === Infinity ? null : Math.sqrt(d1) };
}

function rawComponents(vox) {
    const saved = PL.PIPE.cluster_min_voxels; PL.PIPE.cluster_min_voxels = 1;
    try { return PL.cluster_voxels(vox); } finally { PL.PIPE.cluster_min_voxels = saved; }
}
function keyNeighbors(k) {
    const ij = k.split(","), ix = +ij[0], iy = +ij[1];
    return [(ix - 1) + "," + iy, (ix + 1) + "," + iy, ix + "," + (iy - 1), ix + "," + (iy + 1)];
}
/* cut vertices + degree，限 V<=MAXV 的 comp 全量，否则标注 skipped */
function bridgeAnalyze(keys) {
    const MAXV = 700;
    const set = new Set(keys);
    if (set.size > MAXV) return { skipped: true, V: set.size };
    const deg = new Map(); let edges = 0, boundary = 0;
    set.forEach(k => {
        let d = 0; for (const nk of keyNeighbors(k)) if (set.has(nk)) d++;
        deg.set(k, d); edges += d; if (d < 4) boundary++;
    });
    const cuts = [];
    for (const k of set) {
        if (set.size - 1 <= 1) break;
        const rest = new Set(set); rest.delete(k);
        /* BFS 数分量（rest 内部） */
        const seen = new Set(); let comps = 0; const sizes = [];
        for (const seed of rest) {
            if (seen.has(seed)) continue;
            comps++; const q = [seed]; seen.add(seed); let cnt = 0;
            while (q.length) {
                const cur = q.pop(); cnt++;
                for (const nk of keyNeighbors(cur)) if (rest.has(nk) && !seen.has(nk)) { seen.add(nk); q.push(nk); }
            }
            sizes.push(cnt);
            if (comps > 2) break;
        }
        if (comps > 1) {
            sizes.sort((a, b) => a - b);
            cuts.push({ key: k, deg: deg.get(k), parts: sizes, min_part_frac: +(sizes[0] / (set.size - 1)).toFixed(4) });
        }
    }
    return { skipped: false, V: set.size, E: edges, boundary: boundary,
             cut_count: cuts.length, bridge_fraction: +(cuts.length / set.size).toFixed(4), cuts: cuts };
}
function pct(arr, q) { if (!arr.length) return null; const s = arr.slice().sort((a, b) => a - b); return s[Math.min(s.length - 1, Math.ceil(q * s.length) - 1)]; }

/* 一帧 → 前景 + 原始/生产簇 + 逐簇统计 */
function frameProbe(fi, scanRefPerPoint) {
    const fr = CUR.frames[fi];
    const t0 = Date.now();
    const fg = PL.extract_foreground(fr, CUR_ONLINE);
    const t1 = Date.now();
    const iso = PL.cleanup_isolated_fg(fg.fg_xyzi);
    const t2 = Date.now();
    const vox = PL.voxelize(iso.xyzi);
    const t3 = Date.now();
    const raw = rawComponents(vox);
    const prod = PL.cluster_voxels(vox);
    const t4 = Date.now();
    const extras = PL.evidence_postpass(iso.xyzi, prod).clusters_extra;

    const stats = [];
    for (let ci = 0; ci < prod.length; ci++) {
        const c = prod[ci], set = new Set(c.keys), a = c.acc;
        const pts = [];
        for (let k = 0; k < iso.xyzi.length; k += 4) {
            if (set.has(PL.key_vox(iso.xyzi[k], iso.xyzi[k + 1]))) pts.push([iso.xyzi[k], iso.xyzi[k + 1], iso.xyzi[k + 2]]);
        }
        const f = PL.cluster_features(c);
        const tag = PL.evidence_label(extras[ci]);
        const okf = f.ok;
        let cls;
        if (okf) {
            cls = PL.classify_human(f);
            f.label = cls.label; f.confidence = cls.confidence; f.reasons = cls.reasons;
            f.evidence = extras[ci]; f.evidence_tag = tag; f.joint = PL.joint_status(f);
        }
        else { cls = { label: "NON_HUMAN", confidence: 0, reasons: [f.reason] }; }
        let refMatch = 0, aabbMatch = 0, nScan = 0;
        if (scanRefPerPoint) for (const p of pts) {
            const r = refScan(p[0], p[1], p[2]); nScan++;
            if (r.d0 !== null && r.d0 < MATCH_R) { refMatch++; continue; }
            if (r.d1 !== null && r.d1 < MATCH_R) aabbMatch++;
        }
        /* 最近邻簇距离（cell 中心欧氏 XY 最小） */
        let nbOther = Infinity;
        for (let cj = 0; cj < prod.length; cj++) if (cj !== ci) {
            for (const ka of c.keys) for (const kb of prod[cj].keys) {
                const ia = ka.split(","), ib = kb.split(",");
                const dx = (+ia[0] - +ib[0]) * PL.PIPE.voxel_m, dy = (+ia[1] - +ib[1]) * PL.PIPE.voxel_m;
                const d2 = dx * dx + dy * dy; if (d2 < nbOther) nbOther = d2;
            }
        }
        const br = bridgeAnalyze(c.keys);
        let mnx = Infinity, mxx = -Infinity, mny = Infinity, mxy = -Infinity;
        for (let pi = 0; pi < pts.length; pi++) {
            const px2 = pts[pi][0], py2 = pts[pi][1];
            if (px2 < mnx) mnx = px2; if (px2 > mxx) mxx = px2;
            if (py2 < mny) mny = py2; if (py2 > mxy) mxy = py2;
        }
        stats.push({
            cluster_id: "f" + fi + "_c" + ci, frame_id: fi,
            n_points: a.n, n_voxels: c.keys.length,
            centroid_x: +(a.sx / a.n).toFixed(3), centroid_y: +(a.sy / a.n).toFixed(3), centroid_z: +(a.sz / a.n).toFixed(3),
            min_x: +mnx.toFixed(3), max_x: +mxx.toFixed(3),
            min_y: +mny.toFixed(3), max_y: +mxy.toFixed(3),
            min_z: +a.zmin.toFixed(3), max_z: +a.zmax.toFixed(3),
            extent_x: +(mxx - mnx).toFixed(3),
            extent_y: +(mxy - mny).toFixed(3),
            extent_z: +(a.zmax - a.zmin).toFixed(3), height: okf ? +f.height_m.toFixed(3) : null,
            density_pts_per_voxel: +(a.n / c.keys.length).toFixed(2),
            nearest_other_cluster_dist_m: isFinite(nbOther) ? +Math.sqrt(nbOther).toFixed(3) : null,
            adjacency_edges: br.skipped ? null : br.E, boundary_voxels: br.skipped ? null : br.boundary,
            bridge_fraction: br.skipped ? null : br.bridge_fraction, cut_count: br.skipped ? null : br.cut_count,
            cuts: br.skipped ? null : (br.cuts.length ? br.cuts : null),
            upcos: okf ? +f.upcos.toFixed(3) : null, width_m: okf ? +f.width_m.toFixed(3) : null,
            depth_m: okf ? +f.depth_m.toFixed(3) : null,
            radius_m: okf ? +f.radius_m.toFixed(3) : null, spread_m: okf ? +f.spread_m.toFixed(3) : null,
            label: cls.label, confidence: cls.confidence, reasons: cls.reasons,
            evidence_label: tag.label, spread_cv: extras[ci].spread_cv === null ? null : +extras[ci].spread_cv.toFixed(3),
            anisotropy_xy: extras[ci].anisotropy_xy === null ? null : +extras[ci].anisotropy_xy.toFixed(2),
            joint: okf ? f.joint : "NON_HUMAN",
            ref_match_n: scanRefPerPoint ? refMatch : null, ref_aabb_only_n: scanRefPerPoint ? aabbMatch : null,
            ref_matched_frac: scanRefPerPoint ? +(refMatch / pts.length).toFixed(3) : null,
        });
    }
    return {
        fi: fi, fg_points: fg.n_fg, fg_before_cleanup: iso.fg_before_cleanup, fg_after_cleanup: iso.fg_after_cleanup,
        removed_points: iso.actually_removed_points, vetoed: iso.xy_topology_vetoed,
        raw_components: raw.length, prod_clusters: prod.length,
        fragment_components: raw.filter(c => c.keys.length < PL.PIPE.cluster_min_voxels).length,
        max_component_voxels: raw.reduce((m, c) => Math.max(m, c.keys.length), 0),
        max_component_points: raw.reduce((m, c) => Math.max(m, c.acc.n), 0),
        ms: { fg: t1 - t0, cleanup: t2 - t1, voxelize: t3 - t2, cluster: t4 - t3 },
        clusters: stats,
    };
}

/* ---- 全帧聚合 ---- */
console.log("[cl01] aggregate over all frames ...");
const perFrame = [], rt = { fg: [], cleanup: [], voxelize: [], cluster: [] };
for (let fi = 0; fi < CUR.frames.length; fi++) {
    const p = frameProbe(fi, false);
    perFrame.push({ fi: fi, fg: p.fg_points, raw: p.raw_components, prod: p.prod_clusters,
                    frag: p.fragment_components, maxvox: p.max_component_voxels, maxpts: p.max_component_points,
                    removed: p.removed_points, vetoed: p.vetoed, ms: p.ms });
    rt.fg.push(p.ms.fg); rt.cleanup.push(p.ms.cleanup); rt.voxelize.push(p.ms.voxelize); rt.cluster.push(p.ms.cluster);
    if ((fi + 1) % 55 === 0) console.log("[cl01]   " + (fi + 1) + "/" + CUR.frames.length);
}

/* ---- 重点帧详查 ---- */
const DETAIL = [
    [2, "WD01 静态物"], [42, "WD01 静态物"], [10, "f10 合并嫌疑"], [30, "f30 合并嫌疑"], [55, "f55 合并嫌疑"],
    [63, "walk"], [65, "walk"], [146, "walk"], [80, "stand"], [85, "stand"], [90, "stand"],
    [92, "lying"], [95, "lying"], [99, "lying"], [123, "lying"], [150, "near-furniture"], [155, "near-furniture"], [160, "near-furniture"],
];
const detail = [];
for (const [fi, note] of DETAIL) {
    console.log("[cl01] detail frame " + fi + " (" + note + ") ...");
    const p = frameProbe(fi, true);
    p.note = note;
    detail.push(p);
}

/* ---- oracle probe（f10/30/55 + near-furniture）：拆 ref 匹配点后再聚类 ---- */
const oracle = [];
for (const fi of [10, 30, 55, 150, 155, 160]) {
    const fr = CUR.frames[fi];
    const fg = PL.extract_foreground(fr, CUR_ONLINE);
    const iso = PL.cleanup_isolated_fg(fg.fg_xyzi);
    const keep = [];
    for (let k = 0; k < iso.xyzi.length; k += 4) {
        const r = refScan(iso.xyzi[k], iso.xyzi[k + 1], iso.xyzi[k + 2]);
        if (r.d0 !== null && r.d0 < MATCH_R) continue;       /* 拆掉 reference 匹配点（静态 proxy） */
        keep.push(iso.xyzi[k], iso.xyzi[k + 1], iso.xyzi[k + 2], iso.xyzi[k + 3]);
    }
    const kept = new Float32Array(keep);
    const before = rawComponents(PL.voxelize(iso.xyzi));
    const after = rawComponents(PL.voxelize(kept));
    oracle.push({ fi: fi, removed_static_proxy_pts: iso.xyzi.length / 4 - kept.length / 4,
                  raw_before: before.length, raw_after: after.length,
                  after_sizes: after.map(c => ({ vox: c.keys.length, pts: c.acc.n })).sort((a, b) => b.pts - a.pts).slice(0, 6) });
    console.log("[cl01] oracle f" + fi + ": raw " + before.length + " → " + after.length
        + "（拆 ref 匹配点 " + (iso.xyzi.length / 4 - kept.length / 4) + "）");
}

/* ---- cut removal probe：重点大簇去掉全部 cut 体素后是否分裂成 人/静态 两块 ---- */
const CUT_TARGETS = [
    ["f55_c2", 55], ["f150_c1", 150], ["f155_c2", 155], ["f160_c2", 160],
    ["f10_c1", 10], ["f42_c2", 42], ["f160_c20", 160], ["f146_c1", 146],
];
const cutProbe = [];
for (const [cid, fi] of CUT_TARGETS) {
    const d = detail.find(x => x.fi === fi);
    const c = d && d.clusters.find(cc => cc.cluster_id === cid);
    if (!c || !c.cut_count) { cutProbe.push({ cluster_id: cid, found: !!(c), has_cuts: !!(c && c.cut_count) }); continue; }
    const fr = CUR.frames[fi];
    const fg = PL.extract_foreground(fr, CUR_ONLINE);
    const iso = PL.cleanup_isolated_fg(fg.fg_xyzi);
    const prod = PL.cluster_voxels(PL.voxelize(iso.xyzi));
    let target = null;
    for (const cc of prod) {
        const f = PL.cluster_features(cc);
        if (f.ok && Math.abs(f.cx - c.centroid_x) < 0.02 && Math.abs(f.cy - c.centroid_y) < 0.02
            && cc.keys.length === c.n_voxels) { target = cc; break; }
    }
    if (!target) { cutProbe.push({ cluster_id: cid, found: false }); continue; }
    const set = new Set(target.keys);
    const cutSet = new Set((c.cuts || []).map(x => x.key));
    const out = [];
    for (let k = 0; k < iso.xyzi.length; k += 4) {
        const kv = PL.key_vox(iso.xyzi[k], iso.xyzi[k + 1]);
        if (!set.has(kv) || cutSet.has(kv)) continue;
        out.push(iso.xyzi[k], iso.xyzi[k + 1], iso.xyzi[k + 2], iso.xyzi[k + 3]);
    }
    const after = rawComponents(PL.voxelize(new Float32Array(out)));
    const key2ci = new Map();
    after.forEach((cc, i2) => cc.keys.forEach(k => key2ci.set(k, i2)));
    const agg = after.map(() => ({ pts: 0, refC: 0 }));
    for (let k = 0; k < out.length; k += 4) {
        const ci2 = key2ci.get(PL.key_vox(out[k], out[k + 1]));
        if (ci2 === undefined) continue;
        agg[ci2].pts++;
        const r = refScan(out[k], out[k + 1], out[k + 2]);
        if (r.d0 !== null && r.d0 < MATCH_R) agg[ci2].refC++;
    }
    const parts = after.map((cc, i2) => ({ vox: cc.keys.length, pts: agg[i2].pts,
            refFrac: agg[i2].pts ? +(agg[i2].refC / agg[i2].pts).toFixed(3) : null,
            zmin: +cc.acc.zmin.toFixed(2), zmax: +cc.acc.zmax.toFixed(2) }))
        .sort((a, b) => b.pts - a.pts).slice(0, 8);
    cutProbe.push({ cluster_id: cid, found: true, n_points: c.n_points, n_voxels: c.n_voxels,
                    cut_cells: cutSet.size, removed_pts: c.n_points - out.length / 4,
                    after_components: after.length, parts: parts });
    console.log("[cl01] cutProbe " + cid + ": cuts=" + cutSet.size + " removed_pts=" + (c.n_points - out.length / 4)
        + " after_components=" + after.length + " parts=" + JSON.stringify(parts.slice(0, 4)));
}

/* ---- 桥接分析汇总（详细帧的全部簇） ---- */
const bridges = [];
for (const p of detail) for (const c of p.clusters) {
    if (c.bridge_fraction !== null && c.bridge_fraction > 0) {
        bridges.push({ cluster_id: c.cluster_id, frame_id: c.frame_id, n_points: c.n_points, n_voxels: c.n_voxels,
                       bridge_fraction: c.bridge_fraction, cut_count: c.cut_count, height: c.height,
                       centroid: [c.centroid_x, c.centroid_y], ref_matched_frac: c.ref_matched_frac });
    }
}
bridges.sort((a, b) => b.bridge_fraction - a.bridge_fraction);

/* ---- 输出 ---- */
const stats = {
    generated: new Date().toISOString(), ref_sid: REF_SID, cur_sid: CUR_SID,
    inputs: {
        ref_points: sha256_file(path.join(REF.dir, "points.bin")), cur_points: sha256_file(path.join(CUR.dir, "points.bin")),
        human_pipe_lib: sha256_file(path.join(RP, "human_pipe_lib.js")),
    },
    params: { occ: OCC, match_r: MATCH_R, voxel_m: PL.PIPE.voxel_m, cluster_min_voxels: PL.PIPE.cluster_min_voxels,
              connectivity: "XY 4-neighbor BFS (key_vox, Z ignored)" },
    tls: { ref: REF.tf && REF.tf.job, cur: CUR.tf && CUR.tf.job },
    aggregate: {
        frames: perFrame.length,
        runtime_ms: { fg: { mean: +(rt.fg.reduce((a, b) => a + b, 0) / rt.fg.length).toFixed(3), p50: pct(rt.fg, .5), p95: pct(rt.fg, .95), p99: pct(rt.fg, .99), max: Math.max.apply(null, rt.fg) },
                      cleanup: { mean: +(rt.cleanup.reduce((a, b) => a + b, 0) / rt.cleanup.length).toFixed(3), p50: pct(rt.cleanup, .5), p95: pct(rt.cleanup, .95), p99: pct(rt.cleanup, .99), max: Math.max.apply(null, rt.cleanup) },
                      voxelize: { mean: +(rt.voxelize.reduce((a, b) => a + b, 0) / rt.voxelize.length).toFixed(3), p50: pct(rt.voxelize, .5), p95: pct(rt.voxelize, .95), p99: pct(rt.voxelize, .99), max: Math.max.apply(null, rt.voxelize) },
                      cluster: { mean: +(rt.cluster.reduce((a, b) => a + b, 0) / rt.cluster.length).toFixed(3), p50: pct(rt.cluster, .5), p95: pct(rt.cluster, .95), p99: pct(rt.cluster, .99), max: Math.max.apply(null, rt.cluster) } },
        cluster_counts: { raw_mean: +(perFrame.reduce((a, b) => a + b.raw, 0) / perFrame.length).toFixed(2),
                          prod_mean: +(perFrame.reduce((a, b) => a + b.prod, 0) / perFrame.length).toFixed(2),
                          prod_max: perFrame.reduce((m, b) => Math.max(m, b.prod), 0),
                          fragments_total: perFrame.reduce((a, b) => a + b.frag, 0) },
        largest_component: { max_voxels: perFrame.reduce((m, b) => Math.max(m, b.maxvox), 0), max_points: perFrame.reduce((m, b) => Math.max(m, b.maxpts), 0) },
        frames: perFrame,
    },
    detail: detail,
    oracle_probe: oracle,
    probes: { note: "oracle_probe = 拆掉 reference 匹配点(occ≥0.5,d<0.12) 后重聚类：raw_before→raw_after 缩量说明 merge 依赖静态残留点" },
};
fs.writeFileSync(path.join(HERE, "06_cluster_stats.json"), JSON.stringify(stats, null, 1) + "\n");

const bridgeOut = {
    generated: stats.generated,
    definition: { cut_vertex: "去掉后该 component 分量数变多（comp V≤700 全量），parts=各分量 voxel 数",
                  bridge_fraction: "cut 体素数 / comp 体素数", adjacency: "XY 4 邻（production 同款）" },
    bridge_clusters: bridges,
    oracle_probe: oracle,
    cut_removal_probe: cutProbe,
};
fs.writeFileSync(path.join(HERE, "07_bridge_analysis.json"), JSON.stringify(bridgeOut, null, 1) + "\n");

/* ---- stdout 摘要 ---- */
console.log("");
console.log("== 全帧聚合 ==");
console.log("raw 分量均值 " + stats.aggregate.cluster_counts.raw_mean + "；prod 簇均值 " + stats.aggregate.cluster_counts.prod_mean
    + "（max " + stats.aggregate.cluster_counts.prod_max + "）；<3 voxel 碎片总数 " + stats.aggregate.cluster_counts.fragments_total);
console.log("最大分量 voxels " + stats.aggregate.largest_component.max_voxels + " / points " + stats.aggregate.largest_component.max_points);
console.log("runtime ms/帧：fg mean " + stats.aggregate.runtime_ms.fg.mean + " p95 " + stats.aggregate.runtime_ms.fg.p95
    + " | cleanup p95 " + stats.aggregate.runtime_ms.cleanup.p95 + " | voxelize p95 " + stats.aggregate.runtime_ms.voxelize.p95
    + " | cluster p95 " + stats.aggregate.runtime_ms.cluster.p95);
console.log("");
console.log("== 重点帧（prod 簇） ==");
for (const p of detail) {
    console.log("f" + p.fi + " [" + p.note + "] fg=" + p.fg_points + " raw=" + p.raw_components + " prod=" + p.prod_clusters);
    for (const c of p.clusters.slice(0, 6)) {
        console.log("   " + c.cluster_id + " n=" + c.n_points + " vox=" + c.n_voxels
            + " c=(" + c.centroid_x + "," + c.centroid_y + "," + c.centroid_z + ") h=" + c.height
            + " upcos=" + c.upcos + " " + c.label + "/" + c.evidence_label + "/" + c.joint
            + " ref=" + c.ref_matched_frac + " bridge=" + c.bridge_fraction + " cuts=" + c.cut_count);
    }
}
console.log("");
console.log("== bridge clusters (bridge_fraction>0) ==");
for (const b of bridges) console.log("   " + b.cluster_id + " bf=" + b.bridge_fraction + " cuts=" + b.cut_count
    + " vox=" + b.n_voxels + " n=" + b.n_points + " ref=" + b.ref_matched_frac + " h=" + b.height);
console.log("");
console.log("== cut removal probe ==");
for (const p of cutProbe) {
    if (p.found && p.parts) console.log("   " + p.cluster_id + " cuts=" + p.cut_cells + " removed=" + p.removed_pts
        + " after_components=" + p.after_components + " top=" + JSON.stringify(p.parts.slice(0, 3)));
    else console.log("   " + p.cluster_id + " " + JSON.stringify(p));
}
console.log("[cl01] wrote 06_cluster_stats.json / 07_bridge_analysis.json");

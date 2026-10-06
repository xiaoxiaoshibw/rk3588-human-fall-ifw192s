/* W03-R3.0 Static Leakage Audit — READ-ONLY evidence script (no production changes).
 *
 * Purpose: explain why wall / static-furniture clusters survive background subtraction.
 * Every final cluster of the production pipeline (same pure functions, same map, same order)
 * gets: map availability (exact cell / 3x3x3 neighborhood, distance ignored), point-to-nearest
 * static centroid distance percentiles, build-time voxel occupancy (persistence) plus a full
 * replica of the builder tier verdict for every cluster point's own voxel, centroid/bbox,
 * PCA/upcos, joint status, and track-based centroid motion over 5/20 frames.
 *
 * Field names follow the W03-R3.0 audit spec:
 *   bg_exact_hit_ratio      share of cluster points whose exact 3D cell exists in static map (any tier)
 *   bg_neighbor_hit_ratio   share with >=1 static voxel in the 3x3x3 neighborhood (distance ignored)
 *   bg_miss_ratio           1 - bg_neighbor_hit_ratio (no map voxel anywhere around the point)
 *   bg_min_dist_p50/p95     distance to nearest static centroid among neighbor-hit points (>=0.12 by construction)
 *   bg_match_r015/r020      share that a 0.15/0.20 m matching radius would absorb (radius sensitivity)
 *   persistent_voxel_ratio  share of points whose own voxel occupancy (frames with >=2 pts / nframes) >= 0.50
 *   occ_p50 / occ1_p50      median own-voxel occupancy under the >=2 rule / >=1 rule (sparsity contrast)
 *   why_*                   own-voxel builder verdict shares: strong / supported / occ_low / jitter /
 *                           no_strong_nb / no_hits (no frame ever reached >=2 pts)
 *   centroid_motion_5f/20f  |centroid(t)-centroid(t-k)| in XY with the same track_id (offline post-pass)
 *   bg_match_cur_ratio      current-rule hit ratio; MUST be 0 for survivors (self-check)
 *
 * Frames are TLS-leveled exactly like the console load path (newest recommended=="tls" job
 * under captures/leveled for the same sid; raw only when no job exists). Same order as
 * human_detect.js: apply_Rt -> denoise -> build_static_map / pipeline_frame.
 *
 * Usage: node 01_audit_static_leakage.js cap_20261002_223757 cap_20261004_203349 synth_bend_v1
 */
"use strict";
const fs = require("fs");
const path = require("path");
const HERE = __dirname;
const REPO = path.resolve(HERE, "..", "..", "..", "..");
const RP = path.join(REPO, "pc_apps", "human_replay");
const RL = require(path.join(RP, "human_replay_lib.js"));
const PL = require(path.join(RP, "human_pipe_lib.js"));

/* 与生产 key_bg 同源的整数编码（脚本本地复刻，仅供审计枚举邻域） */
const BG_BASE = 8192, BG_OFF = 4096;
function bg_key_ijk(ix, iy, iz) { return ((ix + BG_OFF) * BG_BASE + (iy + BG_OFF)) * BG_BASE + (iz + BG_OFF); }
function bg_decode(key) {
    let iz = key % BG_BASE; key = (key - iz) / BG_BASE;
    const iy = key % BG_BASE;
    return [(key - iy) / BG_BASE - BG_OFF, iy - BG_OFF, iz - BG_OFF];
}

/* 生产 _bg_match 的邻域 + 距离结构：exact = 精确格存在；nb = 邻域存在（忽略距离）；d2min = 最小形心距平方 */
function nearest_static(sm, x, y, z) {
    const ix = Math.floor(x / PL.PIPE.bg_voxel_xy), iy = Math.floor(y / PL.PIPE.bg_voxel_xy),
          iz = Math.floor(z / PL.PIPE.bg_voxel_z);
    let exact = false, nb = false, d2min = Infinity, tier = null;
    for (let a = -1; a <= 1; a++) for (let b = -1; b <= 1; b++) for (let c = -1; c <= 1; c++) {
        const rec = sm.get(bg_key_ijk(ix + a, iy + b, iz + c));
        if (!rec) continue;
        nb = true;
        if (!a && !b && !c) { exact = true; tier = rec.tier; }
        const dx = rec.x - x, dy = rec.y - y, dz = rec.z - z, d2 = dx * dx + dy * dy + dz * dz;
        if (d2 < d2min) d2min = d2;
    }
    return { exact: exact, nb: nb, d2min: d2min, tier: tier };
}

/* build_static_map 全量语义复刻（逐帧命中 / Welford 形心抖动 / strong / supported / 失败原因）。
 * stats: key -> {hits, hits1, cx..mz}；verdict: key -> strong|supported|occ_low|jitter|no_strong_nb。
 * 调用方须校验 verdict 的 strong|supported 集合 == 生产 map 的 key 集合（脚本失败即口径错）。 */
function build_voxel_stats(frames) {
    const nframes = frames.length, stats = new Map();
    for (const frame of frames) {
        const per = new Map();
        for (let k = 0; k < frame.length; k += 4) {
            const z = frame[k + 2];
            if (z < PL.PIPE.ground_keep_below_m) continue;
            if (z > PL.PIPE.z_max_m) continue;
            const key = PL.key_bg(frame[k], frame[k + 1], z);
            let a = per.get(key);
            if (!a) { a = { n: 0, sx: 0, sy: 0, sz: 0 }; per.set(key, a); }
            a.n++; a.sx += frame[k]; a.sy += frame[k + 1]; a.sz += z;
        }
        per.forEach((a, key) => {
            let s = stats.get(key);
            if (!s) { s = { hits: 0, hits1: 0, cx: 0, cy: 0, cz: 0, mx: 0, my: 0, mz: 0 }; stats.set(key, s); }
            s.hits1++;
            if (a.n < PL.PIPE.bg_hit_min_pts) return;              /* 与 builder 相同的每帧命中门 */
            s.hits++;
            const px = a.sx / a.n, py = a.sy / a.n, pz = a.sz / a.n;
            const dx = px - s.cx, dy = py - s.cy, dz = pz - s.cz;
            s.cx += dx / s.hits; s.mx += dx * (px - s.cx);
            s.cy += dy / s.hits; s.my += dy * (py - s.cy);
            s.cz += dz / s.hits; s.mz += dz * (pz - s.cz);
        });
    }
    const thr_strong = Math.ceil(nframes * PL.PIPE.bg_occ_strong);
    const thr_sup = Math.ceil(nframes * PL.PIPE.bg_occ_supported);
    const strong = new Set(), verdict = new Map();
    stats.forEach((s, key) => { if (s.hits >= thr_strong) { strong.add(key); verdict.set(key, "strong"); } });
    stats.forEach((s, key) => {
        if (verdict.has(key)) return;
        if (s.hits < thr_sup) { verdict.set(key, "occ_low"); return; }
        const jit = Math.sqrt(Math.max(s.mx, s.my, s.mz) / s.hits);
        if (jit > PL.PIPE.bg_jitter_max) { verdict.set(key, "jitter"); return; }
        let nb = 0; const ij = bg_decode(key);
        for (let a = -1; a <= 1 && nb < PL.PIPE.bg_neighbor_min; a++)
            for (let b = -1; b <= 1 && nb < PL.PIPE.bg_neighbor_min; b++)
                for (let c = -1; c <= 1 && nb < PL.PIPE.bg_neighbor_min; c++)
                    if ((a || b || c) && strong.has(bg_key_ijk(ij[0] + a, ij[1] + b, ij[2] + c))) nb++;
        verdict.set(key, nb >= PL.PIPE.bg_neighbor_min ? "supported" : "no_strong_nb");
    });
    return { stats: stats, verdict: verdict, nframes: nframes };
}

function pct(sorted, q) {
    if (!sorted.length) return null;
    return sorted[Math.min(sorted.length - 1, Math.ceil(q * sorted.length) - 1)];
}
function median(arr) {
    if (!arr.length) return null;
    const s = arr.slice().sort((a, b) => a - b);
    return pct(s, 0.5);
}
function round(v, d) { return v === null || v === undefined ? null : +v.toFixed(d === undefined ? 4 : d); }
function distxy(a, b) { return Math.sqrt((a.x - b.x) * (a.x - b.x) + (a.y - b.y) * (a.y - b.y)); }

/* 一帧生产链路复刻：返回 {clusters, key2raw, raw2ci, iso}；clusters 与 pipeline_frame 的最终列表同构造 */
function frame_clusters(slice, sm, tracker, frameIdx) {
    const clean = PL.denoise(slice);
    const fg = PL.extract_foreground(clean, sm);
    const iso = PL.cleanup_isolated_fg(fg.fg_xyzi);
    const rawC = PL.cluster_voxels(PL.voxelize(iso.xyzi));
    const key2raw = new Map();
    rawC.forEach((c, ci) => { for (const k of c.keys) key2raw.set(k, ci); });
    const ev = PL.evidence_postpass(iso.xyzi, rawC);
    const clusters = [], raw2ci = new Map();
    for (let ci = 0; ci < rawC.length; ci++) {
        const f = PL.cluster_features(rawC[ci]);
        if (!f.ok) continue;
        const c = PL.classify_human(f);
        f.label = c.label; f.confidence = c.confidence; f.reasons = c.reasons;
        f.evidence = ev.clusters_extra[ci];
        f.evidence_tag = PL.evidence_label(f.evidence);
        f.joint = PL.joint_status(f);
        raw2ci.set(ci, clusters.length);
        clusters.push(f);
    }
    if (tracker) tracker.tick(frameIdx, clusters);
    return { clusters: clusters, key2raw: key2raw, raw2ci: raw2ci, iso: iso };
}

const WHY_KEYS = ["strong", "supported", "occ_low", "jitter", "no_strong_nb", "no_hits"];

function audit_frame(sid, frameIdx, slice, sm, vstats, tracker) {
    const { clusters, key2raw, raw2ci, iso } = frame_clusters(slice, sm, tracker, frameIdx);
    const acc = clusters.map(() => ({ n: 0, sx: 0, sy: 0, sz: 0,
        xmin: Infinity, ymin: Infinity, zmin: Infinity, xmax: -Infinity, ymax: -Infinity, zmax: -Infinity,
        exact: 0, nbn: 0, tierStrong: 0, tierSupported: 0, matchCur: 0,
        why: { strong: 0, supported: 0, occ_low: 0, jitter: 0, no_strong_nb: 0, no_hits: 0 },
        dists: [], occs: [], occs1: [] }));
    const R2 = PL.PIPE.bg_match_radius * PL.PIPE.bg_match_radius;
    let curMatchTotal = 0;
    for (let k = 0; k < iso.xyzi.length; k += 4) {
        const x = iso.xyzi[k], y = iso.xyzi[k + 1], z = iso.xyzi[k + 2];
        const ci = raw2ci.get(key2raw.get(PL.key_vox(x, y)));
        if (ci === undefined) continue;                       /* 未进最终列表的碎簇不入审计 */
        const A = acc[ci], bgKey = PL.key_bg(x, y, z);
        A.n++; A.sx += x; A.sy += y; A.sz += z;
        if (x < A.xmin) A.xmin = x; if (x > A.xmax) A.xmax = x;
        if (y < A.ymin) A.ymin = y; if (y > A.ymax) A.ymax = y;
        if (z < A.zmin) A.zmin = z; if (z > A.zmax) A.zmax = z;
        const r = nearest_static(sm, x, y, z);
        if (r.exact) { A.exact++; if (r.tier === "strong") A.tierStrong++; else A.tierSupported++; }
        if (r.nb) A.nbn++;
        if (r.d2min < R2) { A.matchCur++; curMatchTotal++; }  /* 与现行匹配互斥 → 恒 0，作口径自检 */
        if (r.nb) A.dists.push(Math.sqrt(r.d2min));
        const s = vstats.stats.get(bgKey);
        A.occs.push(s ? s.hits / vstats.nframes : 0);
        A.occs1.push(s ? s.hits1 / vstats.nframes : 0);
        A.why[vstats.verdict.get(bgKey) || "no_hits"]++;
    }
    const rows = [];
    for (let ci = 0; ci < clusters.length; ci++) {
        const f = clusters[ci], A = acc[ci];
        const ds = A.dists.slice().sort((a, b) => a - b);
        const occs = A.occs.slice().sort((a, b) => a - b);
        const occs1 = A.occs1.slice().sort((a, b) => a - b);
        let m15 = 0, m20 = 0, occ50 = 0, occ65 = 0, occ85 = 0;
        for (const d of A.dists) { if (d < 0.15) m15++; if (d < 0.20) m20++; }
        for (const o of A.occs) { if (o >= 0.50) occ50++; if (o >= 0.65) occ65++; if (o >= 0.85) occ85++; }
        const why = {};
        for (const k of WHY_KEYS) why["why_" + k] = round(A.why[k] / A.n);
        rows.push({ sid, f: frameIdx, ci,
            track_id: f.track_id === undefined ? null : f.track_id,
            track_confirmed: !!f.track_confirmed,
            joint: f.joint, hard_label: f.label, human_shape: f.evidence_tag && f.evidence_tag.label,
            n: f.n, cx: round(f.cx, 3), cy: round(f.cy, 3), cz: round(f.cz, 3),
            bbox: { xmin: round(A.xmin, 3), xmax: round(A.xmax, 3), ymin: round(A.ymin, 3),
                    ymax: round(A.ymax, 3), zmin: round(A.zmin, 3), zmax: round(A.zmax, 3) },
            height_m: round(f.height_m), width_m: round(f.width_m), depth_m: round(f.depth_m),
            upcos: round(f.upcos), eig: f.eig.values.map(v => round(v, 5)),
            bg_exact_hit_ratio: round(A.exact / A.n),
            bg_neighbor_hit_ratio: round(A.nbn / A.n),
            bg_miss_ratio: round(1 - A.nbn / A.n),
            bg_min_dist_p50: round(pct(ds, 0.5)), bg_min_dist_p95: round(pct(ds, 0.95)),
            bg_match_r015_ratio: round(m15 / A.n), bg_match_r020_ratio: round(m20 / A.n),
            bg_match_cur_ratio: round(A.matchCur / A.n),
            persistent_voxel_ratio: round(occ50 / A.n),
            occ_p50: round(pct(occs, 0.5)), occ1_p50: round(pct(occs1, 0.5)),
            occ_ge065_ratio: round(occ65 / A.n), occ_ge085_ratio: round(occ85 / A.n),
            why_strong: why.why_strong, why_supported: why.why_supported, why_occ_low: why.why_occ_low,
            why_jitter: why.why_jitter, why_no_strong_nb: why.why_no_strong_nb, why_no_hits: why.why_no_hits,
            exact_tier_strong: A.exact ? round(A.tierStrong / A.exact) : null,
            exact_tier_supported: A.exact ? round(A.tierSupported / A.exact) : null,
            centroid_motion_5f: null, centroid_motion_20f: null });
    }
    return { rows, curMatchTotal };
}

function session_paths(sid) { return path.join(REPO, "captures", "remote", sid); }

/* 与 console 载入路径一致：取该 id 最新 recommended=="tls" 的 job transform（captures/leveled）。 */
function resolve_transform(sid) {
    const LV = path.join(REPO, "captures", "leveled");
    if (!fs.existsSync(LV)) return null;
    let best = null;
    for (const job of fs.readdirSync(LV)) {
        const jd = path.join(LV, job);
        const tfPath = path.join(jd, "tls", "transform.json");
        const rpPath = path.join(jd, "report.json");
        if (!fs.existsSync(tfPath) || !fs.existsSync(rpPath)) continue;
        let report, tr;
        try {
            report = JSON.parse(fs.readFileSync(rpPath, "utf8"));
            tr = JSON.parse(fs.readFileSync(tfPath, "utf8"));
        } catch (e) { continue; }
        if (report.sid !== sid || report.recommended !== "tls") continue;
        if (!tr || !tr.R || !tr.t) continue;
        const mt = fs.statSync(jd).mtimeMs;
        if (!best || mt > best.mtime) best = { mtime: mt, R: tr.R, t: tr.t, job: job, transform_id: tr.transform_id };
    }
    return best;
}

/* 复刻 human_detect.js apply_Rt：行主序 R.flat()，leveled = R·p + t（原位） */
function apply_Rt(arr, R, t) {
    const r = R.flat ? R.flat() : R;
    for (let k = 0; k < arr.length; k += 4) {
        const x = arr[k], y = arr[k + 1], z = arr[k + 2];
        arr[k] = r[0] * x + r[1] * y + r[2] * z + t[0];
        arr[k + 1] = r[3] * x + r[4] * y + r[5] * z + t[1];
        arr[k + 2] = r[6] * x + r[7] * y + r[8] * z + t[2];
    }
}

function run_session(sid, jsonl) {
    const dir = session_paths(sid);
    const meta = JSON.parse(fs.readFileSync(path.join(dir, "meta.json"), "utf8"));
    const raw = fs.readFileSync(path.join(dir, "points.bin"));
    const f32 = new Float32Array(raw.buffer, raw.byteOffset, raw.byteLength / 4);
    const frames = RL.frame_slice(meta);
    const STRIDE = RL.STRIDE_F32;
    /* 与 console 同序：先 TLS 配平（leveled_latest 同款 job），再 denoise/管线 */
    const tf = resolve_transform(sid);
    const tf_frames = frames.map(f => {
        const s = RL.strided_f32_copy(f32, f.start_pts, f.count, STRIDE);
        if (tf) apply_Rt(s, tf.R, tf.t);
        return s;
    });
    const ded = tf_frames.map(f => PL.denoise(f));
    const sm = PL.build_static_map(ded, { drop_ground: true });
    const vstats = build_voxel_stats(ded);
    console.log("[audit] " + sid + " leveled=" + (tf ? ("job " + tf.job) : "NONE (raw)"));
    /* 口径自检：复刻 verdict 的 (strong ∪ supported) 必须恰好等于生产 map 的 key 集合 */
    const derived = new Set();
    vstats.verdict.forEach((v, key) => { if (v === "strong" || v === "supported") derived.add(key); });
    let replicaSame = derived.size === sm.size;
    if (replicaSame) sm.forEach((rec, key) => { if (!derived.has(key)) replicaSame = false; });
    if (!replicaSame) throw new Error("verdict replica mismatch vs build_static_map for " + sid);
    console.log("[audit] " + sid + " verdict replica == static map (" + derived.size + " voxels)");
    let nStrong = 0, nSupported = 0;
    sm.forEach(rec => { if (rec.tier === "strong") nStrong++; else nSupported++; });

    const tracker = new PL.Tracker();
    const rows = [];
    let curMatchTotal = 0;
    for (let i = 0; i < frames.length; i++) {
        const r = audit_frame(sid, i, tf_frames[i], sm, vstats, tracker);
        rows.push.apply(rows, r.rows);
        curMatchTotal += r.curMatchTotal;
    }
    /* track 历史 → 5f/20f 质心位移（离线后处理） */
    const hist = new Map();
    for (const row of rows) {
        if (row.track_id === null) continue;
        if (!hist.has(row.track_id)) hist.set(row.track_id, []);
        hist.get(row.track_id).push({ f: row.f, x: row.cx, y: row.cy });
    }
    for (const row of rows) {
        if (row.track_id === null) continue;
        const h = hist.get(row.track_id);
        for (const [k, field] of [[5, "centroid_motion_5f"], [20, "centroid_motion_20f"]]) {
            let best = null;
            for (const e of h) if (e.f <= row.f - k && (!best || e.f > best.f)) best = e;
            row[field] = best ? round(distxy({ x: row.cx, y: row.cy }, best), 4) : null;
        }
    }
    for (const row of rows) jsonl.push(row);

    /* 分桶聚合（0.25m XY 栅格） */
    const buckets = new Map();
    for (const row of rows) {
        const key = Math.floor(row.cx / 0.25) + "," + Math.floor(row.cy / 0.25);
        if (!buckets.has(key)) buckets.set(key, { key, rows: [], frames: new Set() });
        const b = buckets.get(key);
        b.rows.push(row); b.frames.add(row.f);
    }
    const bucket_list = [];
    buckets.forEach(b => {
        const rws = b.rows;
        const green = rws.filter(r => r.track_confirmed);
        const maxRow = rws.reduce((a, r) => (r.n > a.n ? r : a), rws[0]);
        const joints = {};
        rws.forEach(r => { joints[r.joint] = (joints[r.joint] || 0) + 1; });
        bucket_list.push({ key: b.key, rows: rws.length, frames: b.frames.size,
            cx_med: median(rws.map(r => r.cx)), cy_med: median(rws.map(r => r.cy)),
            n_med: median(rws.map(r => r.n)), n_max: maxRow.n,
            bg_exact_med: median(rws.map(r => r.bg_exact_hit_ratio)),
            bg_nb_med: median(rws.map(r => r.bg_neighbor_hit_ratio)),
            bg_miss_med: median(rws.map(r => r.bg_miss_ratio)),
            d50_med: median(rws.map(r => r.bg_min_dist_p50).filter(v => v !== null)),
            persist_med: median(rws.map(r => r.persistent_voxel_ratio)),
            occ65_med: median(rws.map(r => r.occ_ge065_ratio)),
            why_low_med: median(rws.map(r => r.why_occ_low)),
            why_nsnb_med: median(rws.map(r => r.why_no_strong_nb)),
            why_nohit_med: median(rws.map(r => r.why_no_hits)),
            motion5_med: median(rws.map(r => r.centroid_motion_5f).filter(v => v !== null)),
            green_rows: green.length,
            joints: joints,
            max_row: { f: maxRow.f, ci: maxRow.ci, n: maxRow.n, joint: maxRow.joint,
                       track_id: maxRow.track_id, track_confirmed: maxRow.track_confirmed } });
    });
    bucket_list.sort((a, b) => (b.green_rows - a.green_rows) || (b.frames - a.frames) || (b.n_max - a.n_max));

    const green_total = rows.filter(r => r.track_confirmed).length;
    const summary = { sid, frames: frames.length, leveled: tf ? tf.job : null,
        map: { strong: nStrong, supported: nSupported, all: sm.size },
        rows: rows.length, cur_match_nonzero: curMatchTotal, green_rows: green_total,
        clusters_median: median(rows.map(r => r.n)) };
    return { summary, bucket_list, rows };
}

/* top 候选簇 SVG（逐点 map 命中状态：蓝=精确格存在 / 橙=仅邻域 / 红=邻域无 map） */
function write_svg(sid, frameIdx, ci, out, label) {
    const dir = session_paths(sid);
    const meta = JSON.parse(fs.readFileSync(path.join(dir, "meta.json"), "utf8"));
    const raw = fs.readFileSync(path.join(dir, "points.bin"));
    const f32 = new Float32Array(raw.buffer, raw.byteOffset, raw.byteLength / 4);
    const frames = RL.frame_slice(meta);
    const STRIDE = RL.STRIDE_F32;
    const tf = resolve_transform(sid);
    const tf_frames = frames.map(f => {
        const s = RL.strided_f32_copy(f32, f.start_pts, f.count, STRIDE);
        if (tf) apply_Rt(s, tf.R, tf.t);
        return s;
    });
    const ded = tf_frames.map(f => PL.denoise(f));
    const sm = PL.build_static_map(ded, { drop_ground: true });
    const r = frame_clusters(tf_frames[frameIdx], sm, null, frameIdx);
    const cluster = r.clusters[ci];
    if (!cluster) return false;
    const pts = [];
    for (let k = 0; k < r.iso.xyzi.length; k += 4) {
        const x = r.iso.xyzi[k], y = r.iso.xyzi[k + 1], z = r.iso.xyzi[k + 2];
        if (r.raw2ci.get(r.key2raw.get(PL.key_vox(x, y))) !== ci) continue;
        const m = nearest_static(sm, x, y, z);
        pts.push({ x, y, z, cls: m.exact ? "exact" : (m.nb ? "nb" : "miss") });
    }
    const vox = [];
    sm.forEach(rec => { vox.push(rec); });
    const pad = 0.6;
    const xmin = Math.min.apply(null, pts.map(p => p.x)) - pad, xmax = Math.max.apply(null, pts.map(p => p.x)) + pad;
    const ymin = Math.min.apply(null, pts.map(p => p.y)) - pad, ymax = Math.max.apply(null, pts.map(p => p.y)) + pad;
    const zmin = Math.min.apply(null, pts.map(p => p.z)) - pad, zmax = Math.max.apply(null, pts.map(p => p.z)) + pad;
    const vox_near = vox.filter(v => v.x >= xmin && v.x <= xmax && v.y >= ymin && v.y <= ymax && v.z >= zmin && v.z <= zmax);
    const W = 460, H = 420, M = 34;
    function sx_xy(x) { return M + (x - xmin) / (xmax - xmin) * (W - 2 * M); }
    function sy_xy(y) { return H - M - (y - ymin) / (ymax - ymin) * (H - 2 * M); }
    function sx_xz(x) { return M + (x - xmin) / (xmax - xmin) * (W - 2 * M); }
    function sz_xz(z) { return H - M - (z - zmin) / (zmax - zmin) * (H - 2 * M); }
    const COL = { exact: "#1f6fd6", nb: "#e8890c", miss: "#d02b2b", vox: "#b9b9b9" };
    const parts = [];
    parts.push('<svg xmlns="http://www.w3.org/2000/svg" width="' + (W * 2) + '" height="' + (H + 74) + '" font-family="Consolas,monospace">');
    parts.push('<rect width="100%" height="100%" fill="#ffffff"/>');
    parts.push('<text x="16" y="22" font-size="14">' + label + '</text>');
    parts.push('<text x="16" y="40" font-size="11">blue=exact map cell, orange=neighborhood only, red=no map in 3x3x3, gray=voxel centroids</text>');
    parts.push('<text x="16" y="56" font-size="11">left: XY top view | right: XZ side view</text>');
    for (const gx of [0, 1]) {
        parts.push('<g transform="translate(' + (gx * W) + ',74)">');
        parts.push('<rect x="' + M + '" y="' + M + '" width="' + (W - 2 * M) + '" height="' + (H - 2 * M) + '" fill="none" stroke="#ccc"/>');
        for (const v of vox_near) {
            const px = gx === 0 ? sx_xy(v.x) : sx_xz(v.x);
            const py = gx === 0 ? sy_xy(v.y) : sz_xz(v.z);
            parts.push('<rect x="' + px.toFixed(1) + '" y="' + py.toFixed(1) + '" width="2" height="2" fill="' + COL.vox + '"/>');
        }
        for (const p of pts) {
            const px = gx === 0 ? sx_xy(p.x) : sx_xz(p.x);
            const py = gx === 0 ? sy_xy(p.y) : sz_xz(p.z);
            parts.push('<circle cx="' + px.toFixed(1) + '" cy="' + py.toFixed(1) + '" r="1.6" fill="' + COL[p.cls] + '"/>');
        }
        parts.push('<text x="' + M + '" y="' + (H - M + 14) + '" font-size="10">' + (gx === 0 ? "XY" : "XZ") + '  [' + (gx === 0 ? xmin.toFixed(2) + "," + xmax.toFixed(2) + " / " + ymin.toFixed(2) + "," + ymax.toFixed(2) : xmin.toFixed(2) + "," + xmax.toFixed(2) + " / " + zmin.toFixed(2) + "," + zmax.toFixed(2)) + ']</text>');
        parts.push('</g>');
    }
    parts.push('</svg>');
    fs.writeFileSync(out, parts.join("\n") + "\n");
    return true;
}

const argv = process.argv.slice(2);
/* --svg-only <sid> <frame> <ci>：只渲染单个案例 SVG（不重跑审计） */
const svgIdx = argv.indexOf("--svg-only");
if (svgIdx >= 0) {
    const sid = argv[svgIdx + 1], f = +argv[svgIdx + 2], ci = +argv[svgIdx + 3];
    const out = path.join(HERE, "09_case_" + sid + "_f" + f + "_ci" + ci + ".svg");
    const ok = write_svg(sid, f, ci, out, sid + " frame " + f + " cluster#" + ci);
    console.log("[audit] case svg: " + (ok ? path.basename(out) : "FAILED"));
    process.exit(ok ? 0 : 1);
}
const args = argv;
if (!args.length) { console.error("usage: node 01_audit_static_leakage.js <sid> [sid...]"); process.exit(2); }
const jsonl = [], stats = { generated_for: args, per_session: {} };
for (const sid of args) {
    const res = run_session(sid, jsonl);
    stats.per_session[sid] = { summary: res.summary, buckets: res.bucket_list };
    console.log("[audit] " + sid + " frames=" + res.summary.frames
        + " map=" + res.summary.map.all + " (strong " + res.summary.map.strong + "/supported " + res.summary.map.supported + ")"
        + " cluster_rows=" + res.summary.rows + " green_rows=" + res.summary.green_rows
        + " cur_match_nonzero=" + res.summary.cur_match_nonzero);
    const top = res.bucket_list.filter(b => b.green_rows > 0).slice(0, 6);
    for (const b of top) {
        console.log("   green bucket " + b.key + " frames=" + b.frames + " n_med=" + round(b.n_med, 0)
            + " nb=" + round(b.bg_nb_med, 2) + " miss=" + round(b.bg_miss_med, 2)
            + " persist=" + round(b.persist_med, 2) + " occ65=" + round(b.occ65_med, 2)
            + " motion5=" + round(b.motion5_med, 3) + " green_rows=" + b.green_rows);
    }
}
/* top 候选 SVG：优先 green + 低运动 + 持续出现 */
for (const sid of args) {
    const s = stats.per_session[sid];
    const cand = s.buckets.find(b => b.green_rows >= 5 && b.frames >= 15 && b.motion5_med !== null && b.motion5_med <= 0.06)
        || s.buckets.find(b => b.green_rows >= 1 && b.frames >= 15)
        || null;
    if (cand) {
        const out = path.join(HERE, "05_candidate_" + sid + "_f" + cand.max_row.f + ".svg");
        const ok = write_svg(sid, cand.max_row.f, cand.max_row.ci, out,
            sid + " frame " + cand.max_row.f + " cluster#" + cand.max_row.ci
            + "  n=" + cand.max_row.n + " joint=" + cand.max_row.joint + " confirmed=" + cand.max_row.track_confirmed
            + "  nb_med=" + round(cand.bg_nb_med, 2) + " miss_med=" + round(cand.bg_miss_med, 2)
            + " persist_med=" + round(cand.persist_med, 2) + " motion5_med=" + round(cand.motion5_med, 3));
        console.log("[audit] candidate svg: " + (ok ? path.basename(out) : "FAILED") + " bucket=" + cand.key);
    }
}
const totalNonzero = Object.values(stats.per_session).reduce((a, s) => a + s.summary.cur_match_nonzero, 0);
if (totalNonzero !== 0) throw new Error("sanity failed: survivors matched by current rule: " + totalNonzero);
fs.writeFileSync(path.join(HERE, "02_audit_results.jsonl"), jsonl.map(r => JSON.stringify(r)).join("\n") + "\n");
fs.writeFileSync(path.join(HERE, "03_audit_stats.json"), JSON.stringify(stats, null, 1));
console.log("[audit] wrote 02_audit_results.jsonl (" + jsonl.length + " rows), 03_audit_stats.json; sanity OK (cur_match=0)");

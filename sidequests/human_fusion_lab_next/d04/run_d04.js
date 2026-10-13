'use strict';
/* HFUS-D04 单因素消融变体 runner — 派生自 background/run_b.js，不改任何只读文件。
 * hook 全部作用在「当次 createDetector 返回的 engine 实例」的 pipe.PIPE / 实例方法上。
 * CLI: node run_d04.js <variant> <outdir> [sid,sid,...]   (variant ∈ VARIANT) */
const fs = require('fs'), path = require('path'), assert = require('assert');
const B = require('../background/detector_b');
const RB = require('../background/run_b');
const E = require('../background/engine_b');
const I = require('../contracts/index_v1');
const V = require('../contracts/strict_v2');
const { instrument } = require('../eval/instrument');
const D = require('../../human_fusion_lab/core/data_loader');
const S = require('../../human_fusion_lab/core/schema');
const EV = require('../../human_fusion_lab/core/evaluate_fusion_gt');
const { objects } = require('../../human_fusion_lab/export');

const ROOT = B.ROOT;
const DEFAULT_OUT = path.join(ROOT, 'docs/human_capture/evidence/2026-10-11_hfus_d04_r1/runs');

const VARIANT = Object.freeze({
    BASE: 'base',
    SPLIT: 'split_only',
    P30: 'point30_only',
    P15: 'point15_only',
    U04: 'unknown04_only',
});

/* ------------------- hooks（全部 monkey-patch 实例，不改文件） ------------------- */

/* P30/P15: 修改 pipe.PIPE.human_n_min 并 hook pipe.cluster_features 的 n 门(两处调用点共享此函数)。 */
function hookPointGate(engine, n_min) {
    engine.pipe.PIPE.human_n_min = n_min;
    const origCF = engine.pipe.cluster_features;
    const pipe = engine.pipe;
    engine.pipe.cluster_features = function (cl) {
        const PIPE = this.PIPE;
        const n = cl.acc.n;
        if (n < n_min) return { ok: false, reason: 'points<' + n_min, n: n };
        return origCF.call(pipe, cl);
    };
    return { human_n_min: n_min, cluster_features_wrapped: true };
}

/* SPLIT: 包装 pipe.cluster_voxels — 对每个几何异质簇（radius>human_radius_max 或 height 出窗）
 * 从簇内 raw 点按 XY>0.45m BFS 分量 + z-hist(0.15m) 峰分离做拆分；每个子簇重建 acc 并
 * 重新走 cluster_features+classify_human。结果作为替代簇序列返回，并把拆分日记挂到
 * engine._split_log（run 循环取走写进该帧 row）。默认关（仅 split_only 变体挂）。 */
function hookSplit(engine) {
    const pipe = engine.pipe;
    const PIPE = pipe.PIPE;
    const origCV = pipe.cluster_voxels;
    const origCF = pipe.cluster_features;
    const origCH = pipe.classify_human;
    let curFgFinal = null;                       // 来自 voxelize 包装（instrument 已包一层 voxelize 但只缓存 fg_final）
    const origVoxelize = pipe.voxelize;
    pipe.voxelize = function (fg) { curFgFinal = fg; return origVoxelize.call(this, fg); };

    /* 从簇 keys 抽出所有 raw 位置 (frame-pos 级) */
    function clusterPoints(cl, fg_final) {
        const keySet = new Set(cl.keys);
        const pts = [];
        for (let p = 0; p < fg_final.length / 4; p++) {
            const key = pipe.key_vox(fg_final[p * 4], fg_final[p * 4 + 1]);
            if (keySet.has(key)) pts.push(p);
        }
        return pts;
    }
    function rebuildAcc(pts, fg_final) {
        const acc = { n: 0, sx: 0, sy: 0, sz: 0, sxx: 0, syy: 0, szz: 0, sxy: 0, sxz: 0, syz: 0, zmin: Infinity, zmax: -Infinity };
        for (const p of pts) {
            const x = fg_final[p * 4], y = fg_final[p * 4 + 1], z = fg_final[p * 4 + 2];
            acc.n++; acc.sx += x; acc.sy += y; acc.sz += z;
            acc.sxx += x * x; acc.syy += y * y; acc.szz += z * z;
            acc.sxy += x * y; acc.sxz += x * z; acc.syz += y * z;
            if (z < acc.zmin) acc.zmin = z;
            if (z > acc.zmax) acc.zmax = z;
        }
        return acc;
    }
    /* XY 0.45m BFS 分量（同 voxel 网格 0.15m, 4 邻, 门 = 3 体素对角） */
    function xyComponents(pts, fg_final) {
        const inv = 1 / PIPE.voxel_m, maxHop = Math.ceil(0.45 / PIPE.voxel_m);
        const keyOf = p => Math.floor(fg_final[p * 4] * inv) + ',' + Math.floor(fg_final[p * 4 + 1] * inv);
        const key2pts = new Map();
        for (const p of pts) { const k = keyOf(p); if (!key2pts.has(k)) key2pts.set(k, []); key2pts.get(k).push(p); }
        const keys = [...key2pts.keys()], remaining = new Set(keys), comps = [];
        while (remaining.size) {
            const seed = remaining.values().next().value;
            remaining.delete(seed);
            const comp = [], q = [seed];
            while (q.length) {
                const cur = q.pop(); comp.push(...key2pts.get(cur));
                const [ix, iy] = cur.split(',').map(Number);
                for (let dx = -maxHop; dx <= maxHop; dx++) for (let dy = -maxHop; dy <= maxHop; dy++) {
                    if (!dx && !dy) continue;
                    if (dx * dx + dy * dy > maxHop * maxHop) continue;
                    const nb = (ix + dx) + ',' + (iy + dy);
                    if (remaining.has(nb)) { remaining.delete(nb); q.push(nb); }
                }
            }
            comps.push(comp);
        }
        return comps;
    }
    /* z-hist 0.15m 峰分离：若峰间有「空槽」则切分 */
    function zSplit(pts, fg_final) {
        if (pts.length < 2) return [pts];
        const bin = 0.15;
        const counts = new Map();
        let zmin = Infinity;
        for (const p of pts) { const z = fg_final[p * 4 + 2]; const b = Math.floor(z / bin); counts.set(b, (counts.get(b) || 0) + 1); if (b < zmin) zmin = b; }
        const bins = [...counts.keys()].sort((a, b) => a - b);
        /* 找长度≥1 的空槽 */
        const cuts = [];
        for (let i = 1; i < bins.length; i++) if (bins[i] - bins[i - 1] >= 2) cuts.push((bins[i - 1] + 1) * bin);
        if (!cuts.length) return [pts];
        const groups = Array.from({ length: cuts.length + 1 }, () => []);
        for (const p of pts) {
            const z = fg_final[p * 4 + 2];
            let gi = 0; while (gi < cuts.length && z >= cuts[gi]) gi++;
            groups[gi].push(p);
        }
        return groups.filter(g => g.length);
    }

    pipe.cluster_voxels = function (vox_fg) {
        const clusters = origCV.call(pipe, vox_fg);
        if (!engine._split_log) engine._split_log = [];
        const out = [];
        for (let ci = 0; ci < clusters.length; ci++) {
            const cl = clusters[ci];
            const f0 = origCF.call(pipe, cl);
            const heterogeneous = f0.ok && (f0.radius_m > PIPE.human_radius_max || f0.height_m > PIPE.human_height_max);
            if (!heterogeneous || !curFgFinal) { out.push(cl); continue; }
            const pts = clusterPoints(cl, curFgFinal);
            /* 两级拆分：先 XY 分量，再在每个分量内 z 峰分离 */
            let subGroups = [];
            for (const comp of xyComponents(pts, curFgFinal)) for (const zg of zSplit(comp, curFgFinal)) subGroups.push(zg);
            subGroups = subGroups.filter(g => g.length >= PIPE.human_n_min);
            if (subGroups.length <= 1) { out.push(cl); continue; }
            const entry = { cluster: ci, acc_n: cl.acc.n, sub_clusters: [] };
            /* 重算子簇 acc + keys：以 key_vox 集近似（每个子簇所属体素集） */
            for (const g of subGroups) {
                const keySet = new Set(g.map(p => pipe.key_vox(curFgFinal[p * 4], curFgFinal[p * 4 + 1])));
                const acc = rebuildAcc(g, curFgFinal);
                const sub = { keys: [...keySet], acc: acc };
                const fs = origCF.call(pipe, sub);
                let cls = null;
                if (fs.ok) cls = origCH.call(pipe, fs);
                out.push(sub);
                entry.sub_clusters.push({ acc_n: acc.n, radius_m: fs.ok ? fs.radius_m : null, height_m: fs.ok ? fs.height_m : null, classify: cls ? cls.label : 'bypass' });
            }
            /* 重跑 cluster_features+classify_human 的 judge 路径（热路径将再算一遍——这里 done 只记一次日记） */
            engine._split_log.push(entry);
        }
        return out;
    };
    return { split_enabled: true };
}

/* U04: 保持 0.4m 现状, 只是显式记录（分账 histogram run_b 已产生; 我们补 row.bg 块/SUMMARY 顶层加 variant_info 即可）。 */
function hookU04() { return { unknown_radius_m: 0.4, bg_breakdown: 'reasons passthrough (run_b native)' }; }

/* ------------------- 变体 run（复刻 run_b 主循环, 只把 mode 名换成 D04_<variant>） ------------------- */
function applyVariant(engine, variant) {
    switch (variant) {
        case VARIANT.BASE: return { variant: 'base' };
        case VARIANT.P30: return Object.assign({ variant }, hookPointGate(engine, 30));
        case VARIANT.P15: return Object.assign({ variant }, hookPointGate(engine, 15));
        case VARIANT.SPLIT: return Object.assign({ variant }, hookSplit(engine));
        case VARIANT.U04: return Object.assign({ variant }, hookU04());
        default: throw new Error('unknown variant ' + variant);
    }
}

function run(variant, outdir, filter) {
    if (!Object.values(VARIANT).includes(variant)) throw new Error('variant must be one of ' + Object.values(VARIANT).join(','));
    fs.mkdirSync(outdir, { recursive: true });
    const mode = 'D04_' + variant;
    const summaryFile = path.join(outdir, mode + '_SUMMARY.json');
    if (fs.existsSync(summaryFile)) throw new Error('refuse overwrite ' + summaryFile);

    const ref = B.buildReference();
    const audit = JSON.parse(fs.readFileSync(path.join(B.LAB, 'results/AUDIT.json')));
    const sessions = [];
    const sourceFiles = ['background/engine_b.js', 'background/detector_b.js', 'background/run_b.js', 'contracts/index_v1.js', 'contracts/strict_v2.js', 'contracts/SCHEMA_V2.json', 'eval/instrument.js', 'd04/run_d04.js']
        .map(p => ({ path: 'sidequests/human_fusion_lab_next/' + p, sha256: B.sha(path.join(ROOT, 'sidequests/human_fusion_lab_next', p)) }));
    let variantInfo = null;

    for (const rec of audit.sessions) {
        if (filter && !filter.includes(rec.sid)) continue;
        const session = D.load_session(path.join(ROOT, 'captures/remote', rec.sid));
        assert.equal(session.meta_sha256, rec.input_sha256.meta);
        assert.equal(session.points_sha256, rec.input_sha256.points);

        const gtManifest = path.join(path.dirname(rec.gt_path), 'manifest.json');
        const gtManifestSHA = fs.existsSync(gtManifest) ? B.sha(gtManifest) : null;
        let doc = fs.existsSync(rec.gt_path) ? JSON.parse(fs.readFileSync(rec.gt_path, 'utf8')) : null;
        if (!(gtManifestSHA === rec.manifest_sha256 && rec.eligible && doc && doc.session_id === rec.sid && doc.review_status === 'reviewed' && fs.existsSync(rec.gt_path) && B.sha(rec.gt_path) === rec.gt_sha256 && doc.session_sha256?.meta === session.meta_sha256 && doc.session_sha256?.points === session.points_sha256)) doc = null;

        const det = B.createDetector(ref);
        const vi = applyVariant(det.engine, variant);   /* hook 只作用当次实例 */
        if (!variantInfo) variantInfo = vi;
        const e = instrument(det.engine), gen = det.begin(rec.sid);
        const file = path.join(outdir, mode + '_' + rec.sid + '.jsonl');
        const fd = fs.openSync(file, 'wx');
        const sum = { sid: rec.sid, input_sha256: rec.input_sha256, gt_manifest_sha256: gtManifestSHA, gt_binding_valid: !!doc, gt_sha256: doc ? B.sha(rec.gt_path) : null, model_sha256: e.rf_model_sha, config: e.cfg, activity: rec.activity, frames: session.frames.length, qualified_frames: 0, gt_persons: 0, proposal: stats(), accepted: stats(), observed_confirmed: stats(), legacy_accepted: stats(), legacy_confirmed: stats(), unknown_frames: 0, duplicate_ids: 0, bare_b_points: 0, chain_b_points: 0, unsupported_UNKNOWN_points: 0, failures: [], candidate_count: 0, split_clusters: 0 };
        const times = [], heaps = [], layerTimes = {};
        try {
            for (const f of session.frames) {
                e._split_log = [];
                const fc = S.make_frame_context({ session_id: rec.sid, session_generation: gen, frame_index: f.index, timestamp: f.timestamp, xyzi: f.xyzi, meta: session.meta });
                const d = det.tick(fc);
                const mapping = e._mapped, lv = mapping.leveled_xyzi;
                const gt = objects(doc, f.index, Array.from(mapping.compact_to_raw));
                const q = gt ? 'PARTIAL' : 'UNKNOWN';
                const candidates = d._candidates.map(c => {
                    if (!c.scoring_centroid) {
                        const n = c.point_indices.length; c.scoring_centroid = { x: 0, y: 0, z: 0 };
                        for (const r of c.point_indices) for (const [k, dim] of ['x', 'y', 'z'].entries()) c.scoring_centroid[dim] += lv[r * 4 + k] / n;
                    }
                    return RB.candidate(c, gt);
                });
                const components = e._ledger.components;
                const strict = V.evaluateFrame({ gt, candidates, raw_components: components, tracks: d._tracks, qualification: q, exhaustive: false });
                const persons = (gt || []).filter(g => g.class_name === 'PERSON');
                const accepted = candidates.filter(c => c.prob >= .35);
                const confirmed = d._tracks.filter(t => t.human_confirmed && t.lost === 0);
                const legacy = gt ? { accepted: EV.count(persons, accepted, .75), confirmed: EV.count(persons, confirmed, .75) } : null;
                if (gt) {
                    sum.qualified_frames++; sum.gt_persons += persons.length;
                    add(sum.proposal, strict.proposal); add(sum.accepted, strict.accepted); add(sum.observed_confirmed, strict.observed_confirmed); add(sum.legacy_accepted, legacy.accepted); add(sum.legacy_confirmed, legacy.confirmed);
                } else sum.unknown_frames++;
                const tids = candidates.map(c => c.track_id); assert.equal(new Set(tids).size, tids.length);
                sum.candidate_count += candidates.length;
                let bg = null;
                {
                    const bd = e._bg_diagnostics, hist = {};
                    for (const r of bd.reasons) hist[r] = (hist[r] || 0) + 1;
                    const bare = bd.bare_keep.reduce((a, b) => a + b, 0), kept = bd.keep.reduce((a, b) => a + b, 0);
                    bg = { bare_b_points: bare, chain_b_points: kept, unsupported_UNKNOWN_points: hist.no_reference_XY_support_UNKNOWN || 0, reasons: hist, FREE: 0, policy: bd.policy };
                    sum.bare_b_points += bare; sum.chain_b_points += kept; sum.unsupported_UNKNOWN_points += bg.unsupported_UNKNOWN_points;
                }
                const splitLog = e._split_log && e._split_log.length ? e._split_log.slice() : [];
                sum.split_clusters += splitLog.reduce((a, x) => a + x.sub_clusters.length, 0);
                const failure = gt && (strict.observed_confirmed.fn || strict.accepted.fp || legacy.confirmed.fp);
                if (failure) sum.failures.push({ frame_index: f.index, strict_fn: strict.observed_confirmed.fn_ids, strict_fp: strict.accepted.fp_ids, legacy });
                const row = { schema_version: 'hfus-frame-v2', evaluation_version: V.VERSION, variant: mode, sid: rec.sid, segment: e.track_segment, timestamp_s: f.timestamp, frame_index: f.index, timestamp: f.timestamp, raw_n: f.n_points, valid_n: mapping.compact_to_raw.length, qualification: q, exhaustive: false, gt: gt || [], candidates, raw_components: components, tracks: d._tracks, visible_candidates: candidates.filter(c => strict.observed_ids.some(id => c.track_id === `FUS_t${c.track_segment}_${id}`) && ['HUMAN_CANDIDATE', 'CONFIRMED_HUMAN'].includes(c.decision)).map(c => c.id), strict, legacy, bg, layers: d.layers, diagnostic_total_ms: d.total_ms, heap_mb: d.peak_heap_mb, foreground_count: e._ledger.final_ids.length, split_log: splitLog.length ? splitLog : undefined };
                fs.writeSync(fd, JSON.stringify(row) + '\n');
                if (f.index >= 5) { times.push(d.total_ms); heaps.push(d.peak_heap_mb); for (const layer of d.layers) (layerTimes[layer.layer] ||= []).push(layer.elapsed_ms); }
            }
        } finally { fs.closeSync(fd); }
        assert.equal(B.sha(path.join(session.session_dir, 'meta.json')), rec.input_sha256.meta);
        assert.equal(B.sha(path.join(session.session_dir, 'points.bin')), rec.input_sha256.points);
        if (doc) { assert.equal(B.sha(rec.gt_path), rec.gt_sha256); assert.equal(B.sha(gtManifest), rec.manifest_sha256); }
        sum.performance = { diagnostic_compute_p50_ms: percentile(times, .5), diagnostic_compute_p95_ms: percentile(times, .95), diagnostic_compute_p99_ms: percentile(times, .99), heap_max_mb: Math.max(...heaps), layers: Object.fromEntries(Object.entries(layerTimes).map(([k, v]) => [k, { p50: percentile(v, .5), p95: percentile(v, .95), p99: percentile(v, .99) }])), scope: 'includes ledger shadow instrumentation; excludes read/render; cold first5 excluded' };
        sum.ledger = { path: file, sha256: B.sha(file) };
        sessions.push(sum);
        console.log(mode, rec.sid, sum.gt_persons, JSON.stringify(sum.legacy_confirmed), sum.performance.diagnostic_compute_p95_ms.toFixed(2));
    }
    const report = { version: 'hfus-d04-v1', schema_version: 'hfus-frame-v2', evaluation_version: V.VERSION, source_sha256: null, mode, variant_info: variantInfo, reference: ref.manifest, sources: sourceFiles, node: process.version, platform: process.platform, sessions, interpretation: 'HFUS-D04 single-factor ablation derived from run_b; variant hook applied to per-session engine instance only; original sources untouched' };
    fs.writeFileSync(summaryFile, JSON.stringify(report, null, 2), { flag: 'wx' });
    return report;
}
function stats() { return { tp: 0, fp: 0, fn: 0, unmatched_unknown: 0 }; }
function add(a, b) { if (b) for (const k of Object.keys(a)) a[k] += b[k] || 0; }
function percentile(a, q) { if (!a.length) return null; return a.slice().sort((a, b) => a - b)[Math.min(a.length - 1, Math.floor(a.length * q))]; }

module.exports = { run, VARIANT, applyVariant, hookPointGate, hookSplit, hookU04 };
if (require.main === module) {
    const variant = process.argv[2] || VARIANT.BASE;
    const outdir = process.argv[3] || path.join(DEFAULT_OUT, variant);
    const filter = process.argv[4] ? process.argv[4].split(',') : null;
    run(variant, outdir, filter);
}

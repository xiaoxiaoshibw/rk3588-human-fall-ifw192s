'use strict';
/* HFUS-D05 runner — 同 run_d04.js 主循环，替换点为 A(adaptive unknown)/B(cleanup aware)/C(temporal)。
 * 所有 hook 仅作用每会话 createDetector 实例；base 不重跑，引用 D04_base SHA 钉死。
 * CLI: node run_d05.js <variant> <outdir> [sid,sid,...]
 * variant ∈ { base, a03, a06, b, c, abc }
 * 说明:
 *  base = 不跑（引用 D04）。本 runner 处理 a/b/c/abc；若 variant=base 只复制引用。
 */
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
const DEFAULT_OUT = path.join(ROOT, 'docs/human_capture/evidence/2026-10-11_hfus_d05_r1/runs');
const BASE_DIR = path.join(ROOT, 'docs/human_capture/evidence/2026-10-11_hfus_d04_r1/runs/base');

const VARIANT = Object.freeze({ BASE: 'base', A03: 'a03', A06: 'a06', B: 'b', C: 'c', ABC: 'abc' });

function applyVariant(engine, variant) {
    const info = { variant };
    if (variant === VARIANT.A03 || variant === VARIANT.A06 || variant === VARIANT.ABC) {
        const { applyUnknown } = require('./hook_unknown');
        info.unknown = applyUnknown(engine, { r: variant === VARIANT.A03 ? 0.3 : 0.6, link_xy_m: 0.3, min_ref_support: 1, min_local_pts: 1 });
    }
    if (variant === VARIANT.B || variant === VARIANT.ABC) {
        const { applyCleanupAware } = require('./hook_cleanup');
        info.cleanup = applyCleanupAware(engine, { link_xy_m: 0.45, min_anchor_pts: 10, min_vertical_span_m: 0.5, furniture_z_max_m: 0.35, furniture_min_span_m: 0.3 });
    }
    if (variant === VARIANT.C || variant === VARIANT.ABC) {
        const { applyTemporal } = require('./hook_temporal');
        info.temporal = applyTemporal(engine, { window_frames: 2, boost_lost_max: 5, min_cluster_pts: 8, still_min_pts: 40, still_frames: 3, still_hot_radius_m: 0.45 });
    }
    return info;
}

/* base 变体：只引用 D04（SHA 已冻结），不复制 ledger。 */
function linkBase(outdir) {
    fs.mkdirSync(outdir, { recursive: true });
    const refFile = path.join(outdir, 'D05_base_REFERENCE.json');
    const payload = { version: 'hfus-d05-v1', note: 'D05 base 引用 D04 现行 base，不重跑；SHA 已在 BASELINE_SHAS.json 钉死', source_dir: BASE_DIR, shas: {} };
    for (const n of fs.readdirSync(BASE_DIR)) if (n.startsWith('D04_base_') && (n.endsWith('.jsonl') || n.endsWith('_SUMMARY.json'))) payload.shas[n] = B.sha(path.join(BASE_DIR, n));
    if (!fs.existsSync(refFile)) fs.writeFileSync(refFile, JSON.stringify(payload, null, 2), { flag: 'wx' });
    console.log('D05 base linked to', BASE_DIR);
    return payload;
}

function stats() { return { tp: 0, fp: 0, fn: 0, unmatched_unknown: 0 }; }
function add(a, b) { if (b) for (const k of Object.keys(a)) a[k] += b[k] || 0; }
function percentile(a, q) { if (!a.length) return null; return a.slice().sort((a, b) => a - b)[Math.min(a.length - 1, Math.floor(a.length * q))]; }

function run(variant, outdir, filter) {
    if (!Object.values(VARIANT).includes(variant)) throw new Error('variant must be one of ' + Object.values(VARIANT).join(','));
    outdir = outdir || path.join(DEFAULT_OUT, variant);
    if (variant === VARIANT.BASE) return linkBase(outdir);
    fs.mkdirSync(outdir, { recursive: true });
    const mode = 'D05_' + variant;
    const summaryFile = path.join(outdir, mode + '_SUMMARY.json');
    if (fs.existsSync(summaryFile)) throw new Error('refuse overwrite ' + summaryFile);

    const ref = B.buildReference();
    const audit = JSON.parse(fs.readFileSync(path.join(B.LAB, 'results/AUDIT.json')));
    const sessions = [];
    const sourceFiles = ['background/engine_b.js', 'background/detector_b.js', 'background/run_b.js', 'contracts/index_v1.js', 'contracts/strict_v2.js', 'contracts/SCHEMA_V2.json', 'eval/instrument.js', 'eval/baseline.js', 'd05/run_d05.js', 'd05/hook_unknown.js', 'd05/hook_cleanup.js', 'd05/hook_temporal.js']
        .filter(p => fs.existsSync(path.join(ROOT, 'sidequests/human_fusion_lab_next', p)))
        .map(p => ({ path: 'sidequests/human_fusion_lab_next/' + p, sha256: B.sha(path.join(ROOT, 'sidequests/human_fusion_lab_next', p)) }));
    let variantInfo = null;

    for (const rec of audit.sessions) {
        if (filter && !filter.includes(rec.sid)) continue;
        const session = D.load_session(path.join(ROOT, 'captures/remote', rec.sid));
        assert.equal(session.meta_sha256, rec.input_sha256.meta);
        assert.equal(session.points_sha256, rec.input_sha256.points);

        const gtManifest = path.join(path.dirname(rec.gt_path), 'manifest.json');
        const gtManifestSHA = fs.existsSync(gtManifest) ? B.sha(gtManifest) : null;
        /* D05 冻结 GT 参会：必须 eligible+reviewed+meta&points SHA 双等。S9 (180751) 缺 meta 键 → doc=null → 探索行。 */
        let doc = fs.existsSync(rec.gt_path) ? JSON.parse(fs.readFileSync(rec.gt_path, 'utf8')) : null;
        if (!(gtManifestSHA === rec.manifest_sha256 && rec.eligible && doc && doc.session_id === rec.sid && doc.review_status === 'reviewed' && fs.existsSync(rec.gt_path) && B.sha(rec.gt_path) === rec.gt_sha256 && doc.session_sha256 && doc.session_sha256.meta === session.meta_sha256 && doc.session_sha256.points === session.points_sha256)) doc = null;

        const det = B.createDetector(ref);
        const vi = applyVariant(det.engine, variant);
        if (!variantInfo) variantInfo = vi;
        const e = instrument(det.engine), gen = det.begin(rec.sid);
        const file = path.join(outdir, mode + '_' + rec.sid + '.jsonl');
        const fd = fs.openSync(file, 'wx');
        const sum = { sid: rec.sid, activity: rec.activity, gt_binding_valid: !!doc, exploration_only: !doc, input_sha256: rec.input_sha256, gt_manifest_sha256: gtManifestSHA, model_sha256: e.rf_model_sha, frames: session.frames.length, qualified_frames: 0, gt_persons: 0, proposal: stats(), accepted: stats(), observed_confirmed: stats(), legacy_accepted: stats(), legacy_confirmed: stats(), unknown_frames: 0, duplicate_ids: 0, bare_b_points: 0, chain_b_points: 0, unsupported_UNKNOWN_points: 0, failures: [], candidate_count: 0, hook_stats: { unknown: [], cleanup: [], temporal: [] } };
        const times = [], heaps = [], layerTimes = {};
        try {
            for (const f of session.frames) {
                const fc = S.make_frame_context({ session_id: rec.sid, session_generation: gen, frame_index: f.index, timestamp: f.timestamp, xyzi: f.xyzi, meta: session.meta });
                const d = det.tick(fc);
                const mapping = e._mapped, lv = mapping.leveled_xyzi;
                const gt = objects(doc, f.index, Array.from(mapping.compact_to_raw));
                const q = doc ? (gt ? 'PARTIAL' : 'UNKNOWN') : 'INVALID_BINDING';
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
                if (gt && doc) {
                    sum.qualified_frames++; sum.gt_persons += persons.length;
                    add(sum.proposal, strict.proposal); add(sum.accepted, strict.accepted); add(sum.observed_confirmed, strict.observed_confirmed); add(sum.legacy_accepted, legacy.accepted); add(sum.legacy_confirmed, legacy.confirmed);
                } else if (!doc) sum.unknown_frames++;
                const tids = candidates.map(c => c.track_id); assert.equal(new Set(tids).size, tids.length);
                sum.candidate_count += candidates.length;
                const bd = e._bg_diagnostics, hist = {};
                for (const r of bd.reasons) hist[r] = (hist[r] || 0) + 1;
                const bare = bd.bare_keep.reduce((a, b) => a + b, 0), kept = bd.keep.reduce((a, b) => a + b, 0);
                const unknownBreakdown = Object.keys(hist).filter(k => k.startsWith('no_reference_XY_support_UNKNOWN')).reduce((s, k) => s + hist[k], 0);
                const bg = { bare_b_points: bare, chain_b_points: kept, unsupported_UNKNOWN_points: unknownBreakdown, reasons: hist, FREE: 0, policy: bd.policy };
                sum.bare_b_points += bare; sum.chain_b_points += kept; sum.unsupported_UNKNOWN_points += unknownBreakdown;
                if (e._unknown_hook_stats) sum.hook_stats.unknown.push({ frame_index: f.index, ...e._unknown_hook_stats });
                if (e._cleanup_stats) sum.hook_stats.cleanup.push({ frame_index: f.index, ...e._cleanup_stats });
                if (e._temporal_stats) sum.hook_stats.temporal.push({ frame_index: f.index, ...e._temporal_stats });
                const failure = gt && doc && (strict.observed_confirmed.fn || strict.accepted.fp || legacy.confirmed.fp);
                if (failure) sum.failures.push({ frame_index: f.index, strict_fn: strict.observed_confirmed.fn_ids, strict_fp: strict.accepted.fp_ids, legacy });
                const row = { schema_version: 'hfus-frame-v2', evaluation_version: V.VERSION, variant: mode, sid: rec.sid, segment: e.track_segment, timestamp_s: f.timestamp, frame_index: f.index, timestamp: f.timestamp, raw_n: f.n_points, valid_n: mapping.compact_to_raw.length, qualification: q, exhaustive: false, gt: gt || [], candidates, raw_components: components, tracks: d._tracks, visible_candidates: candidates.filter(c => strict.observed_ids.some(id => c.track_id === `FUS_t${c.track_segment}_${id}`) && ['HUMAN_CANDIDATE', 'CONFIRMED_HUMAN'].includes(c.decision)).map(c => c.id), strict, legacy, bg, layers: d.layers, diagnostic_total_ms: d.total_ms, heap_mb: d.peak_heap_mb, foreground_count: e._ledger.final_ids.length };
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
        console.log(mode, rec.sid, doc ? 'FORMAL' : 'EXPLORATION', 'GTp=' + sum.gt_persons, 'conf=' + JSON.stringify(sum.legacy_confirmed), 'acc=' + JSON.stringify(sum.accepted), 'p95=' + sum.performance.diagnostic_compute_p95_ms.toFixed(2));
    }
    const report = { version: 'hfus-d05-v1', schema_version: 'hfus-frame-v2', evaluation_version: V.VERSION, mode, variant_info: variantInfo, reference: ref.manifest, sources: sourceFiles, node: process.version, platform: process.platform, sessions, interpretation: 'HFUS-D05 replacement variants; base references frozen D04 base ledger; S9 exploration-only (INVALID_BINDING, never scored)' };
    fs.writeFileSync(summaryFile, JSON.stringify(report, null, 2), { flag: 'wx' });
    return report;
}

module.exports = { run, VARIANT, applyVariant };
if (require.main === module) {
    const variant = process.argv[2] || VARIANT.BASE;
    const outdir = process.argv[3] || path.join(DEFAULT_OUT, variant);
    const filter = process.argv[4] ? process.argv[4].split(',') : null;
    run(variant, outdir, filter);
}

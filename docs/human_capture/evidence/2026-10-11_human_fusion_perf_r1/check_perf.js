'use strict';
// Full-frame offline check; hashes are outside tick timing. No GT writes.
const fs = require('fs'), path = require('path'), crypto = require('crypto'), assert = require('assert'), os = require('os');
const root = path.resolve(__dirname, '../../../..');
const core = path.join(root, 'pc_apps/human_core');
const D = require(path.join(core, 'data_loader')), S = require(path.join(core, 'schema'));
const E = require(path.join(core, 'engine')), R = require(path.join(core, 'runner'));
const hash = x => crypto.createHash('sha256').update(x).digest('hex');
const phase = process.argv[2];
assert(['before', 'after'].includes(phase));
const out = path.join(__dirname, phase + '_runs');
assert(!fs.existsSync(out), 'new output directory required');
fs.mkdirSync(out);
const sources = R.source_sha();
const models = [path.join(root, 'pc_apps/human_replay/rf_person_v1.json'),
    path.join(root, 'docs/human_capture/evidence/2026-10-10_human_unify_fusion_r2/train_02/rf_person_v2.json')];
const modelHashes = models.map(p => hash(fs.readFileSync(p)));
const sessions = ['175553', '175429', '175227', '180557', '180235', '180751'].map(x => 'cap_20261010_' + x);
const percentile = (a, p) => a.slice().sort((x, y) => x - y)[Math.floor((a.length - 1) * p)];
const results = [];
for (const sid of sessions) {
    const session = D.load_session(path.join(root, 'captures/remote', sid));
    for (let modelIndex = 0; modelIndex < models.length; modelIndex++) {
        const engine = new E.UnifiedEngine({mode: 'FUSION'});
        engine.rf.init(fs.readFileSync(models[modelIndex], 'utf8'));
        engine.rf_model_sha = modelHashes[modelIndex];
        const generation = engine.begin_session(sid);
        const times = [], heap = [], rss = [], external = [], layers = {}, stages = {}, frames = [];
        for (const name of ['_fusion_a_chain', '_fusion_b_chain', '_fusion_organize']) {
            const fn = engine[name];
            engine[name] = function (...args) {
                const start = performance.now(), result = fn.apply(this, args);
                if (!stages[name]) stages[name] = [];
                stages[name].push(performance.now() - start);
                return result;
            };
        }
        for (let i = 0; i < session.frames.length; i++) {
            const frame = session.frames[i];
            const diag = engine.tick(S.make_frame_context({session_id: sid, session_generation: generation,
                frame_index: i, timestamp: frame.timestamp, xyzi: frame.xyzi, meta: session.meta}));
            // Exact order and all candidate/track/event fields; omit only measured times and memory.
            const semantics = {candidates: diag._candidates, tracks: diag._tracks, events: diag._events,
                cls_scores: diag.cls_scores, notes: diag.notes,
                layers: diag.layers.map(l => Object.fromEntries(Object.entries(l).filter(([k]) => k !== 'elapsed_ms'))),
                retention: engine.retention, internal_tracks: engine.pipe_ctx.tracker.tracks,
                fusion_tracks: engine.fusion_ctx.tracker.tracks};
            frames.push({input_sha: hash(Buffer.from(frame.xyzi.buffer, frame.xyzi.byteOffset, frame.xyzi.byteLength)),
                semantic_sha: hash(JSON.stringify(semantics))});
            if (i >= 5) {
                times.push(diag.total_ms); heap.push(diag.peak_heap_mb); rss.push(diag.rss_mb); external.push(diag.external_mb);
                diag.layers.forEach(l => {if (!layers[l.layer]) layers[l.layer] = []; layers[l.layer].push(l.elapsed_ms);});
            }
        }
        assert.deepStrictEqual(R.source_sha(), sources, 'source drift');
        assert.deepStrictEqual(models.map(p => hash(fs.readFileSync(p))), modelHashes, 'model drift');
        assert.strictEqual(E.hash_file(path.join(session.session_dir, 'meta.json')), session.meta_sha256);
        assert.strictEqual(E.hash_file(path.join(session.session_dir, 'points.bin')), session.points_sha256);
        const metrics = a => ({p50: percentile(a, .5), p95: percentile(a, .95), p99: percentile(a, .99), max: Math.max(...a)});
        const result = {sid, model: modelIndex + 1, model_sha: modelHashes[modelIndex],
            input_sha: {meta: session.meta_sha256, points: session.points_sha256}, frames,
            n_frames: frames.length, warmup: 5, timing: metrics(times), heap_mb: Math.max(...heap),
            rss_mb: Math.max(...rss), external_mb: Math.max(...external),
            layers: Object.fromEntries(Object.entries(layers).map(([k, a]) => [k, metrics(a)])),
            stages: Object.fromEntries(Object.entries(stages).map(([k, a]) => [k, metrics(a.slice(5))]))};
        result.gate = result.timing.p95 < 50 && result.heap_mb < 1500 ? 'PASS' : 'FAIL';
        const filename = sid + '_v' + result.model + '.json';
        if (phase === 'after') {
            const prior = JSON.parse(fs.readFileSync(path.join(__dirname, 'before_runs', filename), 'utf8'));
            assert.deepStrictEqual(result.input_sha, prior.input_sha);
            assert.strictEqual(result.model_sha, prior.model_sha);
            assert.deepStrictEqual(result.frames, prior.frames, 'frame output drift ' + filename);
            result.parity = 'PASS';
        }
        fs.writeFileSync(path.join(out, filename), JSON.stringify(result, null, 1), {flag: 'wx'});
        results.push(result);
        console.log(sid, 'v' + result.model, frames.length, 'P95', result.timing.p95.toFixed(2), result.gate,
            'stages', JSON.stringify(result.stages));
    }
}
fs.writeFileSync(path.join(out, 'summary.json'), JSON.stringify({sources, modelHashes, node: process.version,
    cpu: os.cpus()[0].model, results: results.map(({frames, ...r}) => r)}, null, 1), {flag: 'wx'});
if (phase === 'after' && results.some(r => r.gate === 'FAIL')) process.exitCode = 1;

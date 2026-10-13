'use strict';
// R4 read-only diagnosis. GT compact indices and engine raw indices are distinct.
const fs = require('fs'), path = require('path'), assert = require('assert');
const E = require('./engine'), D = require('./data_loader'), S = require('./schema'), L = require('./leveling');
const GT = require('../human_replay/gt_lib'), R = require('./runner');
const ROOT = path.resolve(__dirname, '../..');
const read = p => JSON.parse(fs.readFileSync(p, 'utf8'));
const write = (p, v) => fs.writeFileSync(p, JSON.stringify(v, null, 1), {flag: 'wx'});

function compact_to_raw(xyzi) {
    const map = [];
    for (let i = 0; i < xyzi.length / 4; i++) {
        const x = xyzi[i * 4], y = xyzi[i * 4 + 1], z = xyzi[i * 4 + 2];
        if ([x, y, z].every(Number.isFinite) && (x !== 0 || y !== 0 || z !== 0)) map.push(i);
    }
    return map;
}
function object_raw_indices(object, map) {
    const indices = GT.decode_indices(object.raw_point_indices);
    assert(indices.length > 0 && indices.length === object.point_count, 'GT point count');
    assert(new Set(indices).size === indices.length, 'duplicate GT indices');
    return indices.map(i => {
        assert(Number.isSafeInteger(i) && i >= 0 && i < map.length, 'GT compact index bound');
        return map[i];
    });
}
function overlap(indices, objects) {
    const points = new Set(indices), seen = new Set(), hits = [];
    for (const object of objects) {
        const key = object.class_name + ':' + object.indices.slice().sort((a, b) => a - b).join(',');
        if (seen.has(key)) continue;
        seen.add(key);
        const count = object.indices.reduce((n, i) => n + Number(points.has(i)), 0);
        if (count) hits.push({object_id: object.object_id, class_name: object.class_name, source: object.source,
            intersection: count, candidate_fraction: count / points.size, object_fraction: count / object.indices.length});
    }
    // No dominance threshold or automatic identity: expose every overlap, including mixed objects.
    return hits;
}
function scoring_indices(candidate, a_out, b_items) {
    if (candidate.fusion_source_SRC !== 'A+B') return Array.from(candidate.point_indices);
    const item = b_items.find(b => b._merged_into === candidate);
    assert(item, 'merged candidate without B contributor');
    const positions = new Set(candidate._fusion_positions.map(p => p.frame_pos));
    item.frame_positions.forEach(p => positions.add(p));
    return Array.from(positions, p => {
        assert(Number.isSafeInteger(p) && p >= 0 && p < a_out.final_ids.length, 'fusion frame position bound');
        return a_out.final_ids[p];
    });
}
function main() {
    assert(process.argv.length === 4, 'audit snapshot JSON and new outdir required');
    const auditPath = path.resolve(process.argv[2]), out = path.resolve(process.argv[3]);
    assert(!fs.existsSync(out), 'new output directory required'); fs.mkdirSync(out);
    const audit = read(auditPath), auditSha = E.hash_file(auditPath), baseSources = R.source_sha(), frozen = {...baseSources};
    frozen['pc_apps/human_core/fusion.js'] = E.hash_file(path.join(__dirname, 'fusion.js'));
    frozen['pc_apps/human_core/audit_fusion_candidates.js'] = E.hash_file(__filename);
    frozen['pc_apps/human_replay/gt_lib.js'] = E.hash_file(path.join(__dirname, '../human_replay/gt_lib.js'));
    const models = [path.join(ROOT, 'pc_apps/human_replay/rf_person_v1.json'),
        path.join(ROOT, 'docs/human_capture/evidence/2026-10-10_human_unify_fusion_r2/train_02/rf_person_v2.json'),
        path.join(ROOT, 'docs/human_capture/evidence/2026-10-10_human_r3/train_03/rf_person_v3.json')];
    const hashes = models.map(E.hash_file), summary = [];
    for (const entry of audit.sessions) {
        const record = entry.record, doc = entry.doc, sid = record.sid;
        assert(record.eligible, 'GT ineligible ' + sid + ': ' + record.issues.join(','));
        const session = D.load_session(path.join(ROOT, 'captures/remote', sid));
        assert.deepStrictEqual({meta: session.meta_sha256, points: session.points_sha256}, record.input_sha256);
        assert.strictEqual(E.hash_file(record.gt_path), record.gt_sha256);
        assert.strictEqual(E.hash_file(path.join(path.dirname(record.gt_path), 'manifest.json')), record.manifest_sha256);
        for (let mi = 0; mi < models.length; mi++) {
            const engine = new E.UnifiedEngine({mode: 'FUSION'});
            engine.rf.init(fs.readFileSync(models[mi], 'utf8')); engine.rf_model_sha = hashes[mi];
            let scoringSets = new Map();
            const organize = engine._fusion_organize;
            engine._fusion_organize = function(fc, diag, a_out, b_items) {
                const candidates = organize.call(this, fc, diag, a_out, b_items);
                scoringSets = new Map(candidates.map(c => [c.candidate_id, scoring_indices(c, a_out, b_items)]));
                return candidates;
            };
            const generation = engine.begin_session(sid), frames = [], totals = {candidates: 0, accepted: 0,
                strong: 0, current_confirmed_tracks: 0, unknown_frames: 0, evaluated_frames: 0,
                zero_person_frames: 0, zero_person_accepted: 0, zero_person_strong: 0, zero_person_confirmed: 0};
            for (let fi = 0; fi < session.frames.length; fi++) {
                const f = session.frames[fi], diag = engine.tick(S.make_frame_context({session_id: sid,
                    session_generation: generation, frame_index: fi, timestamp: f.timestamp, xyzi: f.xyzi, meta: session.meta}));
                const ids = doc.frames_objects[String(fi)];
                const uncertain = (doc.uncertain_intervals || []).some(i => fi >= i.start && fi <= i.end);
                const evaluated = !!ids && ids.length > 0 && !uncertain && ids.every(id => doc.objects[id].class_name !== 'UNKNOWN');
                let objects = [], roi = [];
                if (evaluated) {
                    const map = compact_to_raw(f.xyzi), contract = engine.report().coordinate_contract;
                    const leveled = L.level_frame(f.xyzi, contract.R, contract.T, contract.already_leveled);
                    objects = ids.map(id => ({...doc.objects[id], indices: object_raw_indices(doc.objects[id], map)}));
                    const seen = new Set();
                    for (const o of objects) {
                        const key = o.class_name + ':' + o.indices.slice().sort((a, b) => a - b).join(',');
                        if (seen.has(key)) continue; seen.add(key);
                        const sub = {n: o.indices.length, x: new Float32Array(o.indices.length), y: new Float32Array(o.indices.length), z: new Float32Array(o.indices.length)};
                        const intens = new Float32Array(o.indices.length);
                        o.indices.forEach((raw, i) => {sub.x[i] = leveled[raw * 4]; sub.y[i] = leveled[raw * 4 + 1]; sub.z[i] = leveled[raw * 4 + 2]; intens[i] = leveled[raw * 4 + 3];});
                        const features = engine.rf.extract(sub, intens);
                        roi.push({object_id: o.object_id, class_name: o.class_name, source: o.source,
                            point_count: sub.n, prob: engine.rf.predict_person(features), features: Array.from(features)});
                    }
                }
                const candidates = diag._candidates.map(c => ({id: c.candidate_id, point_count: c.point_count,
                    scoring_point_count: scoringSets.get(c.candidate_id).length,
                    scoring_pointset_differs: JSON.stringify(scoringSets.get(c.candidate_id)) !== JSON.stringify(Array.from(c.point_indices)),
                    centroid: c.centroid, source: c.fusion_source_SRC, foreground_source: c.foreground_source,
                    decision: c.classifier_decision, prob: c.scores.rf51.prob, track_id: c.track_id,
                    track_confirmed: c.track_confirmed, overlaps: evaluated ? overlap(scoringSets.get(c.candidate_id), objects) : [],
                    gt_status: evaluated ? 'ANNOTATED_POINT_OVERLAP_ONLY' : 'UNKNOWN'}));
                const accepted = candidates.filter(c => ['HUMAN_CANDIDATE', 'CONFIRMED_HUMAN'].includes(c.decision)).length;
                const strong = candidates.filter(c => c.decision === 'CONFIRMED_HUMAN').length;
                const tracks = diag._tracks.filter(t => t.human_confirmed && t.lost === 0);
                totals.candidates += candidates.length; totals.accepted += accepted; totals.strong += strong;
                totals.current_confirmed_tracks += tracks.length;
                totals[evaluated ? 'evaluated_frames' : 'unknown_frames']++;
                // This is a protocol-bound zero-person observation, not an overlap-derived identity.
                if (entry.zero_person_protocol === true && evaluated && !objects.some(o => o.class_name === 'PERSON')) {
                    totals.zero_person_frames++; totals.zero_person_accepted += accepted;
                    totals.zero_person_strong += strong; totals.zero_person_confirmed += tracks.length;
                }
                frames.push({frame_index: fi, status: evaluated ? 'ANNOTATED' : 'UNKNOWN', candidates, roi, tracks});
            }
            assert.deepStrictEqual(R.source_sha(), baseSources);
            assert.strictEqual(E.hash_file(path.join(__dirname, 'fusion.js')), frozen['pc_apps/human_core/fusion.js']);
            assert.strictEqual(E.hash_file(__filename), frozen['pc_apps/human_core/audit_fusion_candidates.js']);
            assert.strictEqual(E.hash_file(path.join(__dirname, '../human_replay/gt_lib.js')), frozen['pc_apps/human_replay/gt_lib.js']);
            assert.deepStrictEqual(models.map(E.hash_file), hashes); assert.strictEqual(E.hash_file(auditPath), auditSha);
            assert.strictEqual(E.hash_file(record.gt_path), record.gt_sha256);
            assert.strictEqual(E.hash_file(path.join(path.dirname(record.gt_path), 'manifest.json')), record.manifest_sha256);
            assert.strictEqual(E.hash_file(path.join(session.session_dir, 'meta.json')), session.meta_sha256);
            assert.strictEqual(E.hash_file(path.join(session.session_dir, 'points.bin')), session.points_sha256);
            const row = {sid, model: 'v' + (mi + 1), model_sha: hashes[mi], totals};
            write(path.join(out, sid + '__' + row.model + '.json'), {...row, gt_source: record, frames});
            summary.push(row); console.log(sid, row.model, JSON.stringify(totals));
        }
    }
    write(path.join(out, 'SUMMARY.json'), {sources: frozen, audit_sha: auditSha, summary,
        limits: 'Annotated frames only; propagated copies not independent; overlap is not a semantic identity; no training or promotion.'});
}
if (require.main === module) main();
module.exports = {compact_to_raw, object_raw_indices, overlap, scoring_indices};

// GL-04 R6 new consumer combinations from the compacted design review. Only new
// evidence is written; the frozen original 44/48 lib assertions and all r1-r5
// evidence are untouched. ponytail read: C:/Users/30680/.config/opencode/skills/
// ponytail/SKILL.md (full).
//
// Covers: C08 empty-candidate occluded source prediction (grey box/age, unknown
// current/fall), explicit negative actual-observation flags, lost/ambiguous/
// unselected stale ground rejection in ground mode, explicit source units
// selection refusal + legacy tolerance, and observation recovery.
const fs = require('fs'), path = require('path'), assert = require('assert');
const { createRequire } = require('module');
const source = fs.readFileSync(path.join(__dirname, 'r7_full_review.js'), 'utf8');
const prefix = source.slice(0, source.indexOf("check('V01'"));
const { fixture, worldWith } = new Function('require', 'module', '__dirname',
  prefix + ';return {fixture,worldWith};')(
  createRequire(path.join(__dirname, 'r7_full_review.js')), { exports: {} }, __dirname);
const { createWorld, HF } = require('./r7_runtime_harness');
const results = [];
const output = path.join(__dirname, 'r7_consumers_extra_results.json');
if (fs.existsSync(output)) throw new Error('Evidence exists: ' + output);
function check(id, matrix, name, run) {
  let observed = {};
  try { run(v => { observed = v; }); results.push({ id, matrix, name, result: 'PASS', observed }); }
  catch (error) { results.push({ id, matrix, name, result: 'FAIL', observed, error: error.message }); }
}
function readout(w) {
  const target = w.context.__review.hfBoxes.target;
  return { fall: w.$('hfFall').textContent, fall_class: w.$('hfFall').className,
    position: w.$('hfPos').textContent, prediction: w.$('hfPred').textContent,
    track: w.$('hfTrack').textContent,
    target_visible: !!(target && target.line.visible),
    target_color: target ? target.line.material.color.getHexString() : null };
}

// C08: occluded prediction with an empty candidate list keeps its independent
// grey diagnostic box/age while current position/fall stay unknown.
check('V07', 'C08', 'empty-candidate occluded source prediction keeps grey box/age, unknown current/fall', capture => {
  const f = fixture();
  Object.assign(f.state, { position_predicted: true, prediction_age_s: .5, track_status: 'occluded',
    center_ground_m: null, bbox_ground_from: 'unavailable', bbox_ground_min_m: null, bbox_ground_max_m: null });
  f.snap.candidates = [];
  const o = readout(worldWith(f)); capture(o);
  assert.strictEqual(o.position, '--');
  assert.strictEqual(o.fall, 'unknown');
  assert.strictEqual(o.fall_class, 'hf-unk');
  assert.ok(o.prediction.includes('预测 age=0.50s'), 'prediction age diagnostic must stay');
  assert.strictEqual(o.target_visible, true, 'grey prediction box stays visible');
  assert.strictEqual(o.target_color, '6b7a90');
});

// C08: explicit negative actual-observation flags never endorse a physical fall.
for (const [label, flag] of [
  ['bbox_observed=false', { bbox_observed: false }],
  ['position_source_from=unavailable', { position_source_from: 'unavailable' }],
  ['position_source_from=predicted', { position_source_from: 'predicted' }]
]) {
  check('V07', 'C08', 'locked target with ' + label + ' keeps physical fall unknown', capture => {
    const f = fixture();
    Object.assign(f.state, flag);
    const o = readout(worldWith(f)); capture(o);
    assert.strictEqual(o.fall, 'unknown');
    assert.strictEqual(o.fall_class, 'hf-unk');
    if (o.target_visible) assert.strictEqual(o.target_color, '8fa0b8');
  });
}
check('V07', 'C08', 'legacy missing actual-observation flags still endorse a valid physical fall', capture => {
  const f = fixture();
  delete f.state.bbox_observed; delete f.state.position_source_from;
  const o = readout(worldWith(f)); capture(o);
  assert.strictEqual(o.fall, 'upright');
});

// C08: lost/ambiguous/unselected reject a retained GROUND pose in ground mode,
// even when its ground fields still match a live candidate.
for (const status of ['lost', 'ambiguous', 'unselected']) {
  check('V07/V09', 'C08', status + ' rejects retained ground pose in ground mode', capture => {
    const f = fixture();
    if (status === 'unselected') f.state.track_id = null;
    f.state.track_status = status;
    f.state.position_predicted = false;
    const w = worldWith(f);
    w.context.__review.hfSetMode('ground');
    w.context.__review.hfRenderState(); w.frame();
    const o = readout(w); capture(Object.assign({ valid_state: HF.validState(f.state) }, o));
    assert.strictEqual(o.position, '--', 'stale ground center must not be current');
    assert.strictEqual(o.fall, 'unknown');
    assert.strictEqual(o.target_visible, false);
  });
}

// C14: explicit wrong source units cannot qualify a fresh click/drag choice;
// missing units stay legacy-tolerant.
check('V03', 'C14', 'explicit source mm cannot qualify current list selection', capture => {
  const f = fixture(); f.snap.units.length = 'mm';
  const w = worldWith(f);
  w.context.__review.hfRenderCandidates();
  const n = w.sent.length;
  const q = HF.selectionContextQualified(w.context.__hf.candidates.values().next().value.snap, f.state);
  if (w.$('hfCands').children.length) w.$('hfCands').children.at(-1).onclick();
  capture({ selection_context: q, requests_before: n, requests_after: w.sent.length });
  assert.strictEqual(q.ok, false);
  assert.strictEqual(w.sent.length, n, 'wrong-unit frame must not submit a selection');
});
check('V09', 'C14', 'legacy missing source units still qualifies selection', capture => {
  const f = fixture(); delete f.snap.units.length;
  const w = worldWith(f);
  w.context.__review.hfRenderCandidates();
  const n = w.sent.length;
  const q = HF.selectionContextQualified(w.context.__hf.candidates.values().next().value.snap, f.state);
  w.$('hfCands').children.at(-1).onclick();
  capture({ selection_context: q, requests_before: n, requests_after: w.sent.length });
  assert.strictEqual(q.ok, true);
  assert.strictEqual(w.sent.length, n + 1);
});

// Recovery: an unknown ground becomes valid again and restores the physical fall.
check('V06', 'C10', 'ground unknown -> valid restores physical fall (recovery)', capture => {
  const f = fixture();
  f.snap.calibration.ground_status = f.state.calibration.ground_status = 'unknown';
  f.snap.ground.status = f.state.ground.status = 'unknown';
  const w = worldWith(f);
  const before = w.$('hfFall').textContent;
  // Re-publish the same frame with a valid ground.
  const g = fixture();
  w.message('state', g.state); w.message('candidates', g.snap); w.frame();
  w.context.__review.hfRenderState();
  const after = w.$('hfFall').textContent;
  capture({ before, after });
  assert.strictEqual(before, 'unknown');
  assert.strictEqual(after, 'upright');
});

// Recovery: a mutated in-place choice is rejected, then a genuine same-content
// reload is accepted again.
check('V05', 'C11', 'mutated choice rejected then same-content reload accepted', capture => {
  const f = fixture();
  const w = worldWith(f);
  w.context.__review.hfRenderCandidates();
  const b = w.$('hfCands').children.at(-1);
  w.context.__hf.candidates.values().next().value.snap.candidates[0].bbox_source_min_m[0] = 1;
  const n = w.sent.length; b.onclick();
  const rejectedAfter = w.sent.length;
  w.message('candidates', JSON.parse(JSON.stringify(f.snap))); w.frame();
  w.context.__review.hfRenderCandidates();
  w.$('hfCands').children.at(-1).onclick();
  capture({ requests_before: n, after_reject: rejectedAfter, after_reload: w.sent.length });
  assert.strictEqual(rejectedAfter, n, 'mutated token must be rejected');
  assert.strictEqual(w.sent.length, n + 1, 'fresh same-content reload must be accepted');
});

fs.writeFileSync(output, JSON.stringify(results, null, 2) + '\n', { flag: 'wx' });
for (const r of results) console.log(r.result + ' ' + r.id + ' ' + r.matrix + ' ' + r.name + (r.error ? ' :: ' + r.error : ''));
console.log(JSON.stringify({ pass: results.filter(r => r.result === 'PASS').length, fail: results.filter(r => r.result === 'FAIL').length }));
process.exitCode = results.some(r => r.result === 'FAIL') ? 1 : 0;

// GL-04 R7 source-position provenance closure. Only new evidence is written; the
// frozen 44/48/54 production assertions and all r1-r6 evidence are untouched.
// ponytail read: C:/Users/30680/.config/opencode/skills/ponytail/SKILL.md (full).
//
// The two R6 lifecycle FAILs: a locked current target whose explicit
// position_source_from is unavailable/predicted must NOT read as current source
// XYZ nor be labelled 实测, even though position_predicted=false. Legal
// actual_points and missing/null legacy keep their raw centre; bbox_observed=false
// is a box/physical flag only and never erases the raw centre; the grey prediction
// diagnostic and history readouts keep their original semantics.
const fs = require('fs'), path = require('path'), assert = require('assert');
const { createRequire } = require('module');
const source = fs.readFileSync(path.join(__dirname, 'r7_full_review.js'), 'utf8');
const prefix = source.slice(0, source.indexOf("check('V01'"));
const { fixture, worldWith } = new Function('require', 'module', '__dirname',
  prefix + ';return {fixture,worldWith};')(
  createRequire(path.join(__dirname, 'r7_full_review.js')), { exports: {} }, __dirname);
const { createWorld, HF } = require('./r7_runtime_harness');
const results = [];
const output = path.join(__dirname, 'r7_provenance_results.json');
if (fs.existsSync(output)) throw new Error('Evidence exists: ' + output);
function check(id, matrix, name, run) {
  let observed = {};
  try { run(v => { observed = v; }); results.push({ id, matrix, name, result: 'PASS', observed }); }
  catch (error) { results.push({ id, matrix, name, result: 'FAIL', observed, error: error.message }); }
}
function readout(w) {
  const target = w.context.__review.hfBoxes.target;
  return { position: w.$('hfPos').textContent, position_label: w.$('hfPosLabel').textContent,
    fall: w.$('hfFall').textContent, fall_class: w.$('hfFall').className,
    prediction: w.$('hfPred').textContent, track: w.$('hfTrack').textContent,
    target_visible: !!(target && target.line.visible),
    target_color: target ? target.line.material.color.getHexString() : null };
}

// The two real R6 FAILs: explicit non-actual source provenance cannot read as a
// current measured XYZ while the triple/position_predicted=false still hold.
for (const from of ['unavailable', 'predicted']) {
  check('V07/V09', 'C08', 'explicit source provenance ' + from + ' cannot read as current measured XYZ', capture => {
    const f = fixture(); f.state.position_source_from = from; f.state.position_predicted = false;
    const o = readout(worldWith(f)); capture({ valid_state: HF.validState(f.state), ...o });
    assert.strictEqual(o.position, '--', 'explicit non-actual source position must be unavailable');
    assert.ok(!o.prediction.includes('实测'), 'explicit non-actual source position cannot be labelled measured');
    assert.strictEqual(o.fall, 'unknown');
  });
}
// A fourth explicit non-actual token (other/foreign) behaves identically.
check('V07/V09', 'C08', 'explicit source provenance other cannot read as current measured XYZ', capture => {
  const f = fixture(); f.state.position_source_from = 'other'; f.state.position_predicted = false;
  const o = readout(worldWith(f)); capture(o);
  assert.strictEqual(o.position, '--');
  assert.ok(!o.prediction.includes('实测'));
});
// bbox_observed=false is a box/physical flag only: it must NOT erase the raw centre.
check('V07/V09', 'C08', 'bbox flag alone does not erase actual_points raw center', capture => {
  const f = fixture(); f.state.bbox_observed = false; f.state.position_source_from = 'actual_points';
  const o = readout(worldWith(f)); capture(o);
  assert.ok(o.position.includes('3.00'), 'bbox-only negative keeps legal raw centre');
  assert.strictEqual(o.fall, 'unknown');
});
// Legacy missing/null provenance keeps the current source XYZ and the measured label.
for (const how of ['missing', 'null']) {
  check('V07/V09', 'C08', 'legacy ' + how + ' provenance retains current source XYZ and measured', capture => {
    const f = fixture();
    if (how === 'missing') { delete f.state.position_source_from; delete f.state.bbox_observed; }
    else { f.state.position_source_from = null; f.state.bbox_observed = null; }
    const o = readout(worldWith(f)); capture(o);
    assert.ok(o.position.includes('3.00'));
    assert.ok(o.prediction.includes('实测') || o.prediction === '实测');
    assert.strictEqual(o.fall, 'upright');
  });
}
// Explicit actual_points is a real measurement: raw centre + measured + physical fall.
check('V07/V09', 'C08', 'explicit actual_points provenance keeps raw centre and measured', capture => {
  const f = fixture(); f.state.position_source_from = 'actual_points'; f.state.bbox_observed = true;
  const o = readout(worldWith(f)); capture(o);
  assert.ok(o.position.includes('3.00'));
  assert.ok(o.prediction.includes('实测'));
  assert.strictEqual(o.fall, 'upright');
});
// Recovery: flipping an explicit negative back to actual_points restores the readout.
check('V06/V09', 'C08', 'recovery: unavailable -> actual_points restores current source XYZ', capture => {
  const bad = fixture(); bad.state.position_source_from = 'unavailable';
  const wBad = worldWith(bad); const oBad = readout(wBad);
  const good = fixture(); good.state.position_source_from = 'actual_points';
  const wGood = worldWith(good); const oGood = readout(wGood);
  capture({ while_unavailable: oBad.position, after_actual_points: oGood.position });
  assert.strictEqual(oBad.position, '--');
  assert.ok(oGood.position.includes('3.00'));
});
// A legal prediction (position_predicted=true) still renders only via the grey
// prediction diagnostic; the source position row is never a current position.
check('V07', 'C08', 'legal prediction keeps grey diagnostic and empty current position', capture => {
  const f = fixture();
  Object.assign(f.state, { track_status: 'occluded', position_predicted: true,
    prediction_age_s: 0.5, prediction_stale: false, position_source_from: 'predicted' });
  const o = readout(worldWith(f)); capture(o);
  assert.strictEqual(o.position, '--');
  assert.strictEqual(o.fall, 'unknown');
  assert.ok(o.prediction.includes('预测 age=0.50s'));
  assert.strictEqual(o.target_visible, true);
  assert.strictEqual(o.target_color, '6b7a90');
});
// The lib-level provenance gate is independent of the bbox flag.
check('V07/V09', 'C08', 'sourcePositionQualified ignores bbox flag but gates source token', capture => {
  capture({ missing: HF.sourcePositionQualified({}).ok,
    bbox_only: HF.sourcePositionQualified({ bbox_observed: false }).ok,
    actual: HF.sourcePositionQualified({ position_source_from: 'actual_points' }).ok,
    unavailable: HF.sourcePositionQualified({ position_source_from: 'unavailable' }).ok });
  assert.strictEqual(HF.sourcePositionQualified({}).ok, true);
  assert.strictEqual(HF.sourcePositionQualified({ bbox_observed: false }).ok, true);
  assert.strictEqual(HF.sourcePositionQualified({ position_source_from: 'actual_points' }).ok, true);
  assert.strictEqual(HF.sourcePositionQualified({ position_source_from: 'unavailable' }).ok, false);
});

fs.writeFileSync(output, JSON.stringify(results, null, 2) + '\n', { flag: 'wx' });
for (const r of results) console.log(r.result + ' ' + r.id + ' ' + r.matrix + ' ' + r.name + (r.error ? ' :: ' + r.error : ''));
console.log(JSON.stringify({ pass: results.filter(r => r.result === 'PASS').length, fail: results.filter(r => r.result === 'FAIL').length }));
process.exitCode = results.some(r => r.result === 'FAIL') ? 1 : 0;

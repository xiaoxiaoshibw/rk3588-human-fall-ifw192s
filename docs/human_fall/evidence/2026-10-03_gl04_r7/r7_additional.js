// Independent GL04 acceptance-v1 additions. Only new evidence is written.
// Reuses the existing Codex VM fixture; no production/test source is changed.
// ponytail read: C:/Users/30680/.codex/skills/ponytail/SKILL.md.
const fs = require('fs'), path = require('path'), assert = require('assert');
const { createRequire } = require('module');
const source = fs.readFileSync(path.join(__dirname, 'r7_full_review.js'), 'utf8');
const prefix = source.slice(0, source.indexOf("check('V01'"));
const { fixture, worldWith } = new Function('require', 'module', '__dirname',
  prefix + ';return {fixture,worldWith};')(
  createRequire(path.join(__dirname, 'r7_full_review.js')), { exports: {} }, __dirname);
const HF = require(path.resolve(__dirname, '../../../../webui/human_fall_preview/human_fall_lib.js'));
const results = [];
const output = path.join(__dirname, 'r7_additional_results.json');
if (fs.existsSync(output)) throw new Error('Evidence exists: ' + output);
function check(id, matrix, name, run) {
  let observed = {};
  try {
    run(value => { observed = value; });
    results.push({ id, matrix, name, result: 'PASS', observed });
  } catch (error) {
    results.push({ id, matrix, name, result: 'FAIL', observed, error: error.message });
  }
}
function readout(w) {
  const target = w.context.__review.hfBoxes.target;
  return { fall: w.$('hfFall').textContent, fall_class: w.$('hfFall').className,
    position: w.$('hfPos').textContent, position_label: w.$('hfPosLabel').textContent,
    track: w.$('hfTrack').textContent, prediction: w.$('hfPred').textContent,
    target_visible: !!(target && target.line.visible),
    target_color: target ? target.line.material.color.getHexString() : null };
}
function unknownPhysical(o, predicted = false) {
  assert.strictEqual(o.fall, 'unknown', 'physical fall must be unknown');
  assert.strictEqual(o.fall_class, 'hf-unk', 'physical fall class must be unknown');
  if (o.target_visible) assert.strictEqual(o.target_color, predicted ? '6b7a90' : '8fa0b8',
    'visible target must use unknown/prediction color, never physical upright color');
}
for (const groundStatus of ['unknown', 'none']) {
  check('V06', 'C10', 'source raw XYZ survives ground ' + groundStatus + ' but physical fall/color are unknown', capture => {
    const f = fixture();
    f.snap.calibration.ground_status = f.state.calibration.ground_status = groundStatus;
    f.snap.ground.status = f.state.ground.status = groundStatus;
    const o = readout(worldWith(f)); capture(o);
    assert.strictEqual(o.position, '3.00, 0.00, -0.50', 'current raw XYZ must stay available');
    assert.ok(o.track.includes('/ locked'), 'raw lock monitoring must stay available');
    unknownPhysical(o);
  });
}
check('V06/V09', 'C01/C10', 'legacy source-only locked retains raw XYZ while physical fall/color are unknown', capture => {
  const f = fixture();
  f.snap.calibration = { calibration_id: null, schema_version: null, ground_status: 'unknown', ground_derived_id: null };
  f.snap.coordinate = { source_frame: 'innolidar', ground_relative_available: false, ground_derived_id: null, horizontal_basis: 'raw_xy_uncalibrated' };
  f.snap.ground = f.snap.ground_render = null;
  Object.assign(f.state, { calibration: structuredClone(f.snap.calibration),
    coordinate: structuredClone(f.snap.coordinate), ground: null, ground_derived_id: null,
    center_ground_m: null, bbox_ground_from: 'unavailable', bbox_ground_min_m: null, bbox_ground_max_m: null });
  const o = readout(worldWith(f)); capture(o);
  assert.strictEqual(o.position, '3.00, 0.00, -0.50');
  assert.ok(o.track.includes('/ locked'));
  unknownPhysical(o);
});
check('V07', 'C08', 'predicted pose without current target observation keeps diagnostic but physical fall is unknown', capture => {
  const f = fixture(), c = f.snap.candidates[0];
  Object.assign(c, { candidate_id: 'other', center_source_m: [12, 0, -.5],
    bbox_source_min_m: [11.8, -.2, -1], bbox_source_max_m: [12.2, .2, .5],
    center_ground_m: [12, 0, 1], bbox_ground_min_m: [11.8, -.2, .5], bbox_ground_max_m: [12.2, .2, 2] });
  Object.assign(f.state, { position_predicted: true, prediction_age_s: .5, track_status: 'occluded',
    center_ground_m: null, bbox_ground_from: 'unavailable', bbox_ground_min_m: null, bbox_ground_max_m: null });
  const o = readout(worldWith(f)); capture(o);
  assert.strictEqual(o.position, '--');
  assert.ok(o.prediction.includes('预测 age=0.50s'));
  unknownPhysical(o, true);
});
for (const status of ['lost', 'ambiguous', 'unselected']) {
  check('V07/V09', 'C08', status + ' rejects retained prior source observation while respecting validState', capture => {
    const f = fixture();
    Object.assign(f.state, { track_status: status, position_predicted: false,
      center_ground_m: null, bbox_ground_from: 'unavailable', bbox_ground_min_m: null, bbox_ground_max_m: null });
    if (status === 'unselected') f.state.track_id = null;
    assert.ok(HF.validState(f.state), 'state is supported by current message validator');
    const o = readout(worldWith(f)); capture(Object.assign({ valid_state: true }, o));
    assert.strictEqual(o.position, '--', 'lost/ambiguous/unselected cannot claim retained source pose as current');
    unknownPhysical(o);
  });
}
for (const guard of ['schema2', 'verifier_unavailable']) {
  check('V06', 'C06/C10', guard + ' existing source invalidation stays unknown/null', capture => {
    const f = fixture();
    if (guard === 'schema2') f.snap.calibration.schema_version = f.state.calibration.schema_version = 2;
    else f.state.sensor_quality.ground_verifier_available = false;
    const o = readout(worldWith(f)); capture(o);
    assert.strictEqual(o.position, '--'); unknownPhysical(o);
  });
}
const mutations = {
  'snapshot units.length': s => { s.units.length = 'mm'; },
  'candidate center_ground_m': s => { s.candidates[0].center_ground_m[0] = 99; },
  'ground block kind': s => { s.coordinate.ground.kind = s.ground_render.kind = 'other'; },
  'ground block schema_version': s => { s.coordinate.ground.schema_version = s.ground_render.schema_version = 2; }
};
for (const [field, mutate] of Object.entries(mutations)) for (const mode of ['source', 'ground']) {
  check('V05', 'C05/C11', mode + ' old rendered choice rejects in-place ' + field, capture => {
    const w = worldWith(fixture());
    if (mode === 'ground') w.context.__review.hfSetMode('ground');
    w.context.__review.hfRenderCandidates();
    const button = w.$('hfCands').children.at(-1), sentBefore = w.sent.length;
    mutate(w.context.__hf.candidates.values().next().value.snap);
    button.onclick();
    capture({ mode, changed_field: field, requests_before: sentBefore, requests_after: w.sent.length });
    assert.strictEqual(w.sent.length, sentBefore, 'old choice must reject changed render/coordinate metadata');
  });
}
check('V03', 'C14', 'explicit source mm cannot be presented as measured source metres', capture => {
  const f = fixture(); f.snap.units.length = 'mm';
  const o = readout(worldWith(f)); capture(o);
  assert.ok(o.position === '--' || !o.position_label.includes('(m)'),
    'source mm must be unavailable or labelled with its actual/unknown unit');
});
check('V03/V06', 'C14', 'explicit source mm cannot qualify metre ground transform', capture => {
  const f = fixture(); f.snap.units.length = 'mm';
  const gr = HF.parseGroundRender(f.snap); capture({ status: gr.status, reason: gr.reason });
  assert.notStrictEqual(gr.status, 'ready', 'contradictory source units must not feed a metre transform');
});
check('V02/V03', 'C13', 'explicit support_units mm cannot qualify metre support layer', capture => {
  const f = fixture(); f.snap.ground.support_units = 'mm';
  const support = HF.parseGroundRender(f.snap).support; capture({ status: support.status, reason: support.reason });
  assert.notStrictEqual(support.status, 'ready', 'explicit non-metre support is unknown/unavailable, never metre geometry');
});
fs.writeFileSync(output, JSON.stringify(results, null, 2) + '\n', { flag: 'wx' });
for (const r of results) console.log(r.result + ' ' + r.id + ' ' + r.matrix + ' ' + r.name + (r.error ? ' :: ' + r.error : ''));
console.log(JSON.stringify({ pass: results.filter(r => r.result === 'PASS').length, fail: results.filter(r => r.result === 'FAIL').length }));
process.exitCode = results.some(r => r.result === 'FAIL') ? 1 : 0;

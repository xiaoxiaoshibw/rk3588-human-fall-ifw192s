// GL-04 R6 fixture qualification checks. Verifies the r6 offline fixtures carry
// the same binding/coordinate/ground/sensor_quality/current-actual fields the
// live node publishes, that positive/negative qualification is honest, and that
// the frozen plane contract (normal=R[2] => offset_m=t[2]) holds. Read-only.
const fs = require('fs'), path = require('path'), assert = require('assert');
const HF = require(path.join(__dirname, '../../../..', 'webui/human_fall_preview/human_fall_lib.js'));
const dir = path.join(__dirname, 'fixtures');
const load = n => JSON.parse(fs.readFileSync(path.join(dir, n + '.json'), 'utf8'));
const clone = o => JSON.parse(JSON.stringify(o));
const results = [];
function check(id, matrix, name, run) {
  let observed = {};
  try { run(v => { observed = v; }); results.push({ id, matrix, name, result: 'PASS', observed }); }
  catch (error) { results.push({ id, matrix, name, result: 'FAIL', observed, error: error.message }); }
}

for (const name of ['normal', 'tilted']) {
  check('V08', 'C15', name + ' fixture is a complete bound published-shape snapshot/state', capture => {
    const f = load(name), snap = f.snapshot, state = f.state;
    const gr = HF.parseGroundRender(snap);
    const o = { snapvalid: HF.validSnapshot(snap), statevalid: HF.validState(state),
      ground: gr.status, support: gr.support && gr.support.status,
      obs: HF.observationQualified(snap, state),
      plane: snap.ground.normal && { normal: snap.ground.normal, offset_m: snap.ground.offset_m, t2: gr.t[2] },
      physical: state.physical };
    capture(o);
    assert.strictEqual(o.snapvalid, true);
    assert.strictEqual(o.statevalid, true);
    assert.strictEqual(gr.status, 'ready');
    assert.strictEqual(o.support, 'ready');
    assert.strictEqual(o.obs.ok, true);
    // Frozen plane contract.
    assert.deepStrictEqual(snap.ground.normal, [gr.R[2][0], gr.R[2][1], gr.R[2][2]]);
    assert.strictEqual(snap.ground.offset_m, gr.t[2]);
    assert.strictEqual(state.position_source_from, 'actual_points');
    assert.strictEqual(state.bbox_observed, true);
    assert.deepStrictEqual(state.sensor_quality.ground_monitor, { status: 'ok' });
    assert.strictEqual(state.physical.ground_physical_verified, false);
    assert.strictEqual(state.calibration.schema_version, snap.calibration.schema_version);
    assert.strictEqual(state.snapshot_id, snap.snapshot_id);
    assert.deepStrictEqual(state.coordinate, snap.coordinate);
  });
}
check('V09/V10', 'C15', 'no_extrinsics fixture keeps actual source, no ground, physical false', capture => {
  const f = load('no_extrinsics'), snap = f.snapshot, state = f.state;
  const gr = HF.parseGroundRender(snap);
  const o = { snapvalid: HF.validSnapshot(snap), statevalid: HF.validState(state),
    ground: gr.status, obs: HF.observationQualified(snap, state),
    sel: HF.selectionContextQualified(snap, state),
    position_source_from: state.position_source_from, physical: state.physical };
  capture(o);
  assert.strictEqual(o.snapvalid, true);
  assert.strictEqual(o.statevalid, true);
  assert.notStrictEqual(gr.status, 'ready');
  assert.strictEqual(o.obs.ok, false, 'no ground => physical observation is not qualified');
  assert.strictEqual(o.sel.ok, true, 'legacy/source-only selection stays possible');
  assert.strictEqual(state.position_source_from, 'actual_points', 'source actual position IS available');
  assert.strictEqual(state.physical.ground_physical_verified, false);
});

check('V03', 'C14', 'r6 normal fixture with source mm refused; legacy missing units tolerated', capture => {
  const f = load('normal');
  const bad = clone(f.snapshot); bad.units.length = 'mm';
  const legacy = clone(f.snapshot); delete legacy.units.length;
  const o = { bad: HF.parseGroundRender(bad).status, legacy: HF.parseGroundRender(legacy).status };
  capture(o);
  assert.notStrictEqual(o.bad, 'ready');
  assert.strictEqual(o.legacy, 'ready');
});
check('V02/V03', 'C13/C14', 'r6 normal fixture with support_units mm refused', capture => {
  const f = load('normal');
  const bad = clone(f.snapshot); bad.ground.support_units = 'mm';
  const s = HF.parseGroundRender(bad).support;
  capture({ status: s.status, reason: s.reason });
  assert.notStrictEqual(s.status, 'ready');
});
check('V05', 'C05/C11', 'r6 identity token covers units.length/ground kind+schema/center_ground', capture => {
  const f = load('normal');
  const base = HF.snapshotIdentity(f.snapshot);
  const a = clone(f.snapshot); a.units.length = 'mm';
  const b = clone(f.snapshot); b.coordinate.ground.kind = 'other';
  const c = clone(f.snapshot); c.coordinate.ground.schema_version = 2;
  const sig = HF.candidateSignature(f.snapshot.candidates[0]);
  const d = clone(f.snapshot); d.candidates[0].center_ground_m[0] = 99;
  capture({ units: base !== HF.snapshotIdentity(a), kind: base !== HF.snapshotIdentity(b),
    schema: base !== HF.snapshotIdentity(c), center: sig !== HF.candidateSignature(d.candidates[0]) });
  assert.strictEqual(base !== HF.snapshotIdentity(a), true);
  assert.strictEqual(base !== HF.snapshotIdentity(b), true);
  assert.strictEqual(base !== HF.snapshotIdentity(c), true);
  assert.strictEqual(sig !== HF.candidateSignature(d.candidates[0]), true);
});

const output = path.join(__dirname, 'r7_fixture_results.json');
if (fs.existsSync(output)) throw new Error('Evidence exists: ' + output);
fs.writeFileSync(output, JSON.stringify(results, null, 2) + '\n', { flag: 'wx' });
for (const r of results) console.log(r.result + ' ' + r.id + ' ' + r.matrix + ' ' + r.name + (r.error ? ' :: ' + r.error : ''));
console.log(JSON.stringify({ pass: results.filter(r => r.result === 'PASS').length, fail: results.filter(r => r.result === 'FAIL').length }));
process.exitCode = results.some(r => r.result === 'FAIL') ? 1 : 0;

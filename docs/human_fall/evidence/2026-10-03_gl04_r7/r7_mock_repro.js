// GL-04 R7 browser-15 reproduction via the Node runtime harness. Mirrors the r6
// localhost mock bridge's synthetic-normal shape (source mode) and confirms an
// explicit unavailable provenance no longer reads as current measured XYZ. Only
// new evidence is written; no production/test source or r6 evidence is touched.
const fs = require('fs'), path = require('path');
const { createWorld, HF } = require('./r7_runtime_harness');
const sc = HF.syntheticScenario('normal');
const rows = [];
for (const [mode, from] of [['normal', undefined], ['bad_source_unavailable', 'unavailable'], ['bad_source_predicted', 'predicted']]) {
  const snap = JSON.parse(JSON.stringify(sc.snapshot)), state = JSON.parse(JSON.stringify(sc.state));
  snap.coordinate.ground = snap.ground_render;
  const sup = snap.ground_render.support;
  snap.ground.support_polygon = sup.polygon.map(p => [p[0], p[1], 0]);
  snap.ground.support_frame = 'ground_local'; snap.ground.support_schema_version = 1;
  snap.ground.ground_derived_id = sup.ground_derived_id; delete snap.ground_render;
  state.snapshot_id = snap.snapshot_id; state.coordinate = JSON.parse(JSON.stringify(snap.coordinate));
  state.ground = JSON.parse(JSON.stringify(snap.ground)); state.calibration = JSON.parse(JSON.stringify(snap.calibration));
  state.center_ground_m = snap.candidates[0].center_ground_m; state.ground_derived_id = snap.ground.ground_derived_id;
  state.sensor_quality = { ground_verifier_available: true, ground_monitor: { status: 'ok' } };
  if (from) state.position_source_from = from;
  const w = createWorld();
  w.raw(snap.source.seq, snap.source.stamp_secs, snap.source.stamp_nsecs);
  w.message('candidates', snap); w.message('state', state); w.frame();
  w.context.__review.hfRenderState();
  const row = { mode, hfPos: w.$('hfPos').textContent, hfPred: w.$('hfPred').textContent, hfFall: w.$('hfFall').textContent };
  row.result = (mode === 'normal')
    ? (row.hfPos.includes('3.00') && row.hfPred.includes('实测') ? 'PASS' : 'FAIL')
    : (row.hfPos === '--' && !row.hfPred.includes('实测') && row.hfFall === 'unknown' ? 'PASS' : 'FAIL');
  rows.push(row);
}
fs.writeFileSync(path.join(__dirname, 'r7_mock_repro_results.json'), JSON.stringify(rows, null, 2) + '\n', { flag: 'wx' });
for (const r of rows) console.log(r.result + ' ' + JSON.stringify(r));
process.exitCode = rows.some(r => r.result === 'FAIL') ? 1 : 0;

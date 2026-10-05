// Independent V06/C10 consumer check: source XYZ and fall qualification differ.
const {createWorld, HF} = require('./codex_runtime_harness');
const fs = require('fs');
const path = require('path');
const rows = [];
for (const status of ['valid', 'unknown', 'none']) {
    const sc = HF.syntheticScenario('normal');
    const snap = sc.snapshot, state = sc.state;
    state.snapshot_id = snap.snapshot_id;
    state.calibration = JSON.parse(JSON.stringify(snap.calibration));
    state.ground_derived_id = snap.coordinate.ground_derived_id;
    state.center_ground_m = snap.candidates[0].center_ground_m;
    state.sensor_quality = {ground_verifier_available:true, ground_monitor:{status:'ok'}};
    snap.calibration.ground_status = status;
    state.calibration.ground_status = status;
    snap.ground.status = status;
    state.ground = JSON.parse(JSON.stringify(snap.ground));
    const w = createWorld();
    w.raw(snap.source.seq, snap.source.stamp_secs, snap.source.stamp_nsecs);
    w.message('candidates', snap); w.message('state', state); w.frame();
    w.context.__review.hfRenderState();
    const actual = {fall:w.nodes.hfFall.textContent, position:w.nodes.hfPos.textContent};
    const expectedFall = status === 'valid' ? 'upright' : 'unknown';
    rows.push({id:'V06',matrix:'C10',status,expectedFall,actual,result:actual.fall===expectedFall?'PASS':'FAIL'});
}
fs.writeFileSync(path.join(__dirname,'95_codex_source_fall_results.json'),JSON.stringify(rows,null,2));
console.log(JSON.stringify(rows,null,2));
process.exitCode=rows.some(r=>r.result==='FAIL')?1:0;

// GL-04 R5 offline fixture generator (Node only). Reuses the same synthetic
// contract as R3 but writes this round's static JSON under r5/fixtures; it never
// overwrites the R2/R3 fixtures. The browser entry only fetches these fields and
// performs no geometry construction. Fields copied from the already-published
// candidate are marked synthetic/offline; physical verification flags stay false
// and production build_snapshot still emits no R/t/support (V10 BLOCKED).
const fs = require('fs');
const path = require('path');
const HF = require(path.join(__dirname, '../../../..', 'webui/human_fall_preview/human_fall_lib.js'));

const names = ['normal', 'tilted', 'no_extrinsics'];
const outDir = path.join(__dirname, 'fixtures');
fs.mkdirSync(outDir, { recursive: true });

for (const name of names) {
  const scen = HF.syntheticScenario(name);
  if (!scen) throw new Error('no scenario ' + name);
  const snap = scen.snapshot;
  const state = scen.state;
  const hadGround = !!snap.ground_render;
  if (snap.ground_render) {
    snap.coordinate.ground = snap.ground_render;
    const sup = snap.ground_render.support;
    snap.ground = snap.ground || { status: 'valid', frame: snap.source.frame_id };
    if (sup) {
      snap.ground.support_polygon = sup.polygon || null;
      snap.ground.support_polyline = sup.polyline || null;
      snap.ground.support_frame = sup.frame;
      snap.ground.support_ground_derived_id = sup.ground_derived_id;
      snap.ground.support_schema_version = sup.schema_version;
    }
    // Offline-only source plane copy of the declared R/t (never derived in the
    // browser): ground z=0 -> source normal R[2], offset -t[2].
    const R = snap.ground_render.R, t = snap.ground_render.t;
    snap.ground.normal = [R[2][0], R[2][1], R[2][2]];
    snap.ground.offset_m = -t[2];
    snap.ground.sensor_height_m = t[2];
    delete snap.ground_render;
  }
  // Copy the fields the live node publishes from the current candidate so the
  // offline consumer path matches the real state shape (R5 PLAN_REVIEW).
  const c0 = snap.candidates[0];
  state.center_ground_m = c0.center_ground_m;
  state.ground_derived_id = snap.coordinate.ground_derived_id;
  state.position_source_from = hadGround ? 'actual_points' : 'unavailable';
  state.performance = { kind: 'performance', schema_version: 1, enabled: true, queue_dropped: 0 };
  state.physical = { ground_physical_verified: false, extrinsics_verified: false, imu_alignment_verified: false };
  const fixture = {
    name: name,
    synthetic: true,
    frame_version: 'r5-sample-frame-v1',
    note: 'synthetic/offline GL-04 R5 fixture; browser loads fields only; physical flags false',
    logTimeNs: Number(scen.logTimeNs),
    cloud_b64: Buffer.from(scen.cloud).toString('base64'),
    snapshot: snap,
    state: state
  };
  const file = path.join(outDir, name + '.json');
  fs.writeFileSync(file, JSON.stringify(fixture, null, 2));
  const parsed = HF.parseGroundRender(snap);
  console.log(name + ' bytes=' + scen.cloud.length + ' ground=' + parsed.status +
    ' support=' + (parsed.support ? parsed.support.status : '-') +
    ' snapvalid=' + HF.validSnapshot(snap) + ' statevalid=' + HF.validState(state) +
    ' center_ground=' + JSON.stringify(state.center_ground_m) + ' gdid=' + state.ground_derived_id);
}

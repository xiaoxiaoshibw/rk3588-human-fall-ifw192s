// GL-04 R6 offline fixture generator (Node only). Reuses the synthetic contract
// and writes this round's static JSON under r6/fixtures; it never overwrites the
// r2-r5 fixtures. The browser entry only fetches these fields and performs no
// geometry construction. It now copies the binding/coordinate/ground/
// sensor_quality/current-actual fields the live node publishes (node_runtime.py
// build_state) so the offline consumer matches the real shape; physical
// verification flags stay false and production build_snapshot still emits no
// R/t/support (V10 BLOCKED).
//
// Frozen plane contract: for a source plane with normal = R[2] (the ground
// normal expressed in the source frame), the plane offset must equal t[2].
const fs = require('fs');
const path = require('path');
const HF = require(path.join(__dirname, '../../../..', 'webui/human_fall_preview/human_fall_lib.js'));

const names = ['normal', 'tilted', 'no_extrinsics'];
const outDir = path.join(__dirname, 'fixtures');
fs.mkdirSync(outDir, { recursive: true });
const clone = o => JSON.parse(JSON.stringify(o));

for (const name of names) {
  const scen = HF.syntheticScenario(name);
  if (!scen) throw new Error('no scenario ' + name);
  const snap = scen.snapshot, state = scen.state;
  const hadGround = !!snap.ground_render;
  if (hadGround) {
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
    // Offline-only source plane copy of the declared R/t. Frozen contract:
    // normal = R[2] and offset_m = t[2] (R5 wrote -t[2], which contradicted the
    // frozen geometry contract and is corrected here).
    const R = snap.ground_render.R, t = snap.ground_render.t;
    snap.ground.normal = [R[2][0], R[2][1], R[2][2]];
    snap.ground.offset_m = t[2];
    snap.ground.sensor_height_m = t[2];
    delete snap.ground_render;
  }
  const c0 = snap.candidates[0];
  // Copy the fields the live node publishes from the current candidate.
  state.snapshot_id = snap.snapshot_id;
  state.source = clone(snap.source);
  state.coordinate = clone(snap.coordinate);
  state.ground = clone(snap.ground);
  state.calibration = {
    calibration_id: snap.calibration.calibration_id,
    schema_version: snap.calibration.schema_version,
    ground_status: snap.calibration.ground_status,
    ground_derived_id: snap.calibration.ground_derived_id
  };
  state.ground_derived_id = snap.coordinate.ground_derived_id;
  state.position_source_from = 'actual_points';
  state.bbox_observed = true;
  state.position_reference_m = hadGround ? clone(c0.center_ground_m) : null;
  state.bbox_reference_min_m = hadGround ? clone(c0.bbox_ground_min_m) : null;
  state.bbox_reference_max_m = hadGround ? clone(c0.bbox_ground_max_m) : null;
  state.center_ground_m = hadGround ? clone(c0.center_ground_m) : null;
  state.bbox_ground_from = hadGround ? c0.bbox_ground_from : 'unavailable';
  state.sensor_quality = {
    ground_valid: hadGround,
    ground_verifier_available: hadGround,
    ground_monitor: hadGround ? { status: 'ok' } : { status: 'unknown', reason: 'no_ground' },
    candidate_count: 1, input_point_count: snap.quality.input_point_count
  };
  state.performance = { kind: 'performance', schema_version: 1, enabled: true, queue_dropped: 0 };
  state.physical = { ground_physical_verified: false, extrinsics_verified: false, imu_alignment_verified: false };
  const fixture = {
    name: name,
    synthetic: true,
    frame_version: 'r6-sample-frame-v1',
    note: 'synthetic/offline GL-04 R6 fixture; browser loads fields only; physical flags false',
    logTimeNs: Number(scen.logTimeNs),
    cloud_b64: Buffer.from(scen.cloud).toString('base64'),
    snapshot: snap,
    state: state
  };
  const parsed = HF.parseGroundRender(snap);
  if (hadGround) {
    if (parsed.status !== 'ready') throw new Error(name + ' ground not ready: ' + parsed.status);
    // Frozen plane contract: normal = R[2] and offset_m = t[2].
    if (parsed.t[2] !== snap.ground.offset_m)
      throw new Error(name + ' plane offset ' + snap.ground.offset_m + ' != t[2] ' + parsed.t[2]);
  }
  fs.writeFileSync(path.join(outDir, name + '.json'), JSON.stringify(fixture, null, 2));
  console.log(name + ' bytes=' + scen.cloud.length + ' ground=' + parsed.status +
    ' support=' + (parsed.support ? parsed.support.status : '-') +
    ' snapvalid=' + HF.validSnapshot(snap) + ' statevalid=' + HF.validState(state) +
    ' position_source_from=' + state.position_source_from +
    ' offset_eq_t2=' + (hadGround ? (snap.ground.offset_m === parsed.t[2]) : 'n/a'));
}

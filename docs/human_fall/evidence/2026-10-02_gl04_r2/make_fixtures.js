// Offline GL-04 fixture generator (Node only). It precomputes the complete
// sample frame -- PointCloud2 wire bytes, source/ground point min/max/center,
// R/t and supports -- and writes fixed static JSON. The browser entry only
// fetches these fields; it never builds scenario geometry.
//
// Output: fixtures/<name>.json = { name, logTimeNs, cloud_b64, snapshot, state }
// The snapshot is converted to the authoritative R2 schema: the transform lives
// in coordinate.ground and the support region in snapshot.ground.support_*.
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
    delete snap.ground_render;
  }
  const fixture = {
    name: name,
    synthetic: true,
    note: 'synthetic/offline GL-04 R2 fixture; browser loads fields only',
    logTimeNs: Number(scen.logTimeNs),
    cloud_b64: Buffer.from(scen.cloud).toString('base64'),
    snapshot: snap,
    state: scen.state
  };
  const file = path.join(outDir, name + '.json');
  fs.writeFileSync(file, JSON.stringify(fixture, null, 2));
  // Verify what the browser will consume is exactly the ready authoritative path.
  const parsed = HF.parseGroundRender(snap);
  console.log(name + ' bytes=' + scen.cloud.length + ' ground=' + parsed.status +
    ' support=' + (parsed.support ? parsed.support.status : '-') +
    ' snapvalid=' + HF.validSnapshot(snap) + ' statevalid=' + HF.validState(scen.state));
}

// GL-04 R3 offline fixture generator (Node only). Same contract as the R2
// generator but writes this round's static JSON under r3/fixtures; it never
// overwrites the R2 fixtures. The browser entry only fetches these fields.
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
    note: 'synthetic/offline GL-04 R3 fixture; browser loads fields only',
    logTimeNs: Number(scen.logTimeNs),
    cloud_b64: Buffer.from(scen.cloud).toString('base64'),
    snapshot: snap,
    state: scen.state
  };
  const file = path.join(outDir, name + '.json');
  fs.writeFileSync(file, JSON.stringify(fixture, null, 2));
  const parsed = HF.parseGroundRender(snap);
  console.log(name + ' bytes=' + scen.cloud.length + ' ground=' + parsed.status +
    ' support=' + (parsed.support ? parsed.support.status : '-') +
    ' snapvalid=' + HF.validSnapshot(snap) + ' statevalid=' + HF.validState(scen.state));
}

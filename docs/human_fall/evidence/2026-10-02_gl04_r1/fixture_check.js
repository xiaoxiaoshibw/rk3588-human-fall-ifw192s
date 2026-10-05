/* GL-04 R1 evidence helper: dump the offline synthetic fixtures produced by the
 * shared pure lib and re-validate them through the same parsers the browser uses.
 * Run: node fixture_check.js   (from this evidence directory) */
"use strict";
const fs = require("fs");
const path = require("path");
const HF = require("../../../../webui/human_fall_preview/human_fall_lib.js");

const out = {};
for (const name of ["normal", "tilted", "no_extrinsics"]) {
  const s = HF.syntheticScenario(name);
  const gr = HF.parseGroundRender(s.snapshot);
  out[name] = {
    validSnapshot: HF.validSnapshot(s.snapshot),
    validState: HF.validState(s.state),
    groundRender: gr.status,
    groundRenderReason: gr.reason,
    support: gr.support ? gr.support.status : null,
    cloudBytes: s.cloud.length,
    cloudHeader: HF.headerFromPayload(s.cloud),
    cloudFrameKeys: HF.frameKeys(HF.headerFromPayload(s.cloud), "/human_fall/display_points"),
    snapshotFrameKeys: HF.objectKeys(s.snapshot, "/human_fall/display_points"),
    candidateGroundBoxFrom: s.snapshot.candidates[0].bbox_ground_from,
    snapshot: s.snapshot,
    state: s.state
  };
}
fs.writeFileSync(path.join(__dirname, "synthetic_fixtures.json"), JSON.stringify(out, null, 2));
console.log(JSON.stringify(out, (k, v) => (k === "cloud" ? undefined : v), 2));

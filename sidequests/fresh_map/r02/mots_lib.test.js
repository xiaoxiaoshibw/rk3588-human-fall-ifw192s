"use strict";
const assert = require("assert/strict");
const M = require("./mots_lib.js"), F = require("../r01/fresh_lib.js");
const P = require("../../../pc_apps/human_replay/human_pipe_lib.js");
const empty = new Float32Array();
function cloud(xs) {
    return new Float32Array(xs.flatMap(x => [x, 0.02, 1.02, 1, x + 0.005, 0.02, 1.02, 2]));
}
const fixed = cloud([1.01]), key = P.key_bg(1.01, 0.02, 1.02);
const ref = { voxels: new Map([[key, { x: 1.0125, y: 0.02, z: 1.02, occ: 1 }]]) };
for (const group of ["A0", "A1", "A2"]) {
    const st = M.create(ref, group);
    for (let i = 0; i < 20; i++) {
        const r = M.update(st, fixed, i);
        assert.equal(M.kept_keys(st, r.obs).size, 0, "stationary reference must stay cold");
    }
}
// A0 byte parity against unmodified original candidate projection (without anchors).
const a0 = M.create(null, "A0"), base = F.create_fresh_state(null);
for (let i = 0; i < 30; i++) {
    const fr = i % 4 === 0 ? empty : cloud([1.01 + Math.floor(i / 8) * 0.15]);
    const r = M.update(a0, fr, i * 0.1); F.fresh_update(base, fr, i * 0.1);
    assert.deepEqual(M.candidates(a0, fr, M.kept_keys(a0, r.obs)), F.candidate_xyzi(base, fr, null));
}
// Neighborhood change triggers the supported center even though it never moves.
const a1 = M.create(ref, "A1");
let extras = 0;
for (let i = 0; i < 18; i++) {
    const fr = cloud(i % 2 ? [1.01, 0.86, 1.16] : [1.01]);
    const r = M.update(a1, fr, i * 0.1); extras += r.n_mots_fired;
}
assert(extras > 0); assert(a1.base.voxels.get(key).ever_event);
// A2: one burst not enough, persistent positive evidence qualifies, stable observed
// occupancy can reverse confidence. UNKNOWN and duplicate clocks cannot inflate it.
const a2 = M.create(null, "A2");
M.update(a2, fixed, 0); let r = M.update(a2, fixed, 0.1);
assert.equal(M.kept_keys(a2, r.obs).size, 0);
for (let i = 1; i <= 7; i++) { a2.base.voxels.get(key).ever_event = false; r = M.update(a2, fixed, i); }
assert(M.kept_keys(a2, r.obs).has(key));
const before = a2.beliefs.get(key).log_odds;
M.update(a2, empty, 8); M.update(a2, empty, 80);
assert.equal(a2.beliefs.get(key).log_odds, before);
const snap = JSON.stringify(a2.beliefs.get(key));
assert.throws(() => M.update(a2, fixed, 80));
assert.throws(() => M.update(a2, fixed, 79));
assert.equal(JSON.stringify(a2.beliefs.get(key)), snap);
for (let i = 81; i < 200; i++) r = M.update(a2, fixed, i);
assert(!M.kept_keys(a2, r.obs).has(key), "stable evidence reverses event confidence (retention risk)");
assert.throws(() => M.update(a2, new Float32Array(3), 201));
assert.throws(() => M.update(a2, fixed, NaN));
const invalid = M.create(null, "A1");
assert.equal(M.update(invalid, new Float32Array([NaN, 0, 1, 1]), 0).obs.size, 0);
console.log("PASS: stationary ref, A0 parity, neighborhood motion, A2 burst gate/reversal, UNKNOWN, clocks, invalid input");

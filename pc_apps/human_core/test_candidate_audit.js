'use strict';
const assert = require('assert'), A = require('./audit_fusion_candidates');
const xyzi = Float32Array.from([0, 0, 0, 1, 1, 2, 3, 2, NaN, 1, 2, 3, 4, 5, 6, 4]);
const map = A.compact_to_raw(xyzi);
assert.deepStrictEqual(map, [1, 3]);
assert.deepStrictEqual(A.object_raw_indices({raw_point_indices: ['s', 0, 1], point_count: 2}, map), [1, 3]);
for (const indices of [['s', 2], ['s', -1], ['s', 0, 0], ['s']])
    assert.throws(() => A.object_raw_indices({raw_point_indices: indices, point_count: indices.length - 1}, map));
const objects = [{object_id: 'person', class_name: 'PERSON', indices: [1, 3]},
    {object_id: 'copy', class_name: 'PERSON', indices: [3, 1]},
    {object_id: 'furniture', class_name: 'FURNITURE', indices: [3, 9]}];
const hits = A.overlap(Uint32Array.from([1, 3, 7]), objects);
assert.strictEqual(hits.length, 2);
assert.strictEqual(hits[0].candidate_fraction, 2 / 3);
assert.strictEqual(hits[1].intersection, 1);
assert.deepStrictEqual(A.overlap([8], objects), []);
assert.deepStrictEqual(A.overlap([1], []), []); // Unannotated has no invented identity.
const merged = {fusion_source_SRC: 'A+B', point_indices: [10], _fusion_positions: [{frame_pos: 0}]};
assert.deepStrictEqual(A.scoring_indices(merged, {final_ids: [10, 11, 12]},
    [{_merged_into: merged, frame_positions: [0, 1, 2]}]), [10, 11, 12]);
assert.throws(() => A.scoring_indices(merged, {final_ids: [10]}, []));
assert.deepStrictEqual(A.scoring_indices({fusion_source_SRC: 'A', point_indices: [10]}, {}, []), [10]);
console.log('candidate audit mapping/bounds/dedup/ambiguity/unknown PASS');

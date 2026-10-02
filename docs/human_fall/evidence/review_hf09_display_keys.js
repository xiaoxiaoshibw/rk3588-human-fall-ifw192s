// Independent display-topic isolation: matching numbers must not bypass mapping.
const assert = require('node:assert/strict');
const HF = require('../../../webui/human_fall/human_fall_lib.js');
const source = {seq:17, stamp_secs:100, stamp_nsecs:1};
const obj = {source, visualization:{topic:'/human_fall/display_points',
  source_topic:'/innolidar_points', wire_seq:2, source}};
assert.deepEqual(HF.objectKeys(obj, '/human_fall/display_points'),
  [HF.visualizationKey(obj.visualization)]);
assert.deepEqual(HF.objectKeys(obj, '/innolidar_points'), ['S|'+HF.sourceKey(source)]);
assert.deepEqual(HF.objectKeys(obj, '/other/display_points'), []);
const mismatch = {...obj, visualization:{...obj.visualization,
  source:{...source, stamp_nsecs:2}}};
assert.deepEqual(HF.objectKeys(mismatch, '/human_fall/display_points'), []);
assert.deepEqual(HF.pruneRawFrames([{rxMs:20}, {rxMs:90}, {rxMs:110}], 100, 20), [{rxMs:90}]);
console.log('Independent display topic/source/negative-age checks PASS');

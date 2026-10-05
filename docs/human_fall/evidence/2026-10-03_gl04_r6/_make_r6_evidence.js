// Build the R6 evidence scripts from the frozen R5 harness (copies only; never
// overwrites r1-r5). Run once; refuses to clobber an existing r6 file.
const fs = require('fs'), path = require('path');
const d = __dirname, r5 = path.join(d, '..', '2026-10-03_gl04_r5');
function write(name, text) {
  const out = path.join(d, name);
  if (fs.existsSync(out)) throw new Error('exists: ' + out);
  fs.writeFileSync(out, text);
}
function transformed(src, ...rules) {
  let t = fs.readFileSync(path.join(r5, src), 'utf8');
  for (const [a, b] of rules) t = t.split(a).join(b);
  return t;
}
write('r6_runtime_harness.js', transformed('codex_runtime_harness.js'));
write('r6_full_review.js', transformed('codex_full_review.js',
  ["'./codex_runtime_harness'", "'./r6_runtime_harness'"],
  ['90_codex_results.json', 'r6_self_90_results.json']));
write('r6_self_90.js', transformed('r5_self_90.js',
  ["'./r5_runtime_harness'", "'./r6_runtime_harness'"],
  ['r5_self_90_results.json', 'r6_self_90_results.json']));
write('r6_self_92.js', transformed('r5_self_92.js',
  ["'r5_self_90.js'", "'r6_self_90.js'"],
  ['r5_self_92_results.json', 'r6_self_92_results.json']));
write('r6_self_95.js', transformed('95_codex_source_fall_gate.js',
  ["'./codex_runtime_harness'", "'./r6_runtime_harness'"],
  ['95_codex_source_fall_results.json', 'r6_self_95_results.json']));
write('r6_additional.js', transformed('97_codex_additional.js',
  ["'codex_full_review.js'", "'r6_full_review.js'"],
  ['./codex_full_review.js', './r6_full_review.js'],
  ['97_codex_additional_results.json', 'r6_additional_results.json']));
console.log('r6 evidence scripts written');

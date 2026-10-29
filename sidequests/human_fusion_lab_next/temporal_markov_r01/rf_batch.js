// Exact existing RF extractor and immutable tree model; no ported feature approximation.
const fs = require('fs'), path = require('path');
const root = path.resolve(__dirname, '../../..');
const rf = require(path.join(root, 'pc_apps/human_replay/rf_person.js'));
rf.init(fs.readFileSync(path.join(root, 'pc_apps/human_replay/rf_person_v1.json'), 'utf8'));
const readline = require('readline').createInterface({input: process.stdin});
readline.on('line', line => {
  const r = JSON.parse(line), p = r.points;
  if (!p.length) { console.log(JSON.stringify({rf:null,ms:0})); return; }
  const t = process.hrtime.bigint();
  const f = {n:p.length, x:Float32Array.from(p.map(q=>q[0])), y:Float32Array.from(p.map(q=>q[1])), z:Float32Array.from(p.map(q=>q[2]))};
  const prob = rf.predict_person(rf.extract(f, Float32Array.from(p.map(q=>q[3]))));
  console.log(JSON.stringify({rf:prob,ms:Number(process.hrtime.bigint()-t)/1e6}));
});

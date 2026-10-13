'use strict';
/* D05 基线 SHA 冻结：跑数前固定输入/代码/参考的资产指纹。 */
const fs = require('fs'), path = require('path');
const B = require('../background/detector_b');
const ROOT = B.ROOT;
const rel = p => path.relative(ROOT, p).replaceAll('\\', '/');
const entries = {};
const files = [
    'sidequests/human_fusion_lab_next/background/engine_b.js',
    'sidequests/human_fusion_lab_next/background/detector_b.js',
    'sidequests/human_fusion_lab_next/background/run_b.js',
    'sidequests/human_fusion_lab_next/contracts/index_v1.js',
    'sidequests/human_fusion_lab_next/contracts/strict_v2.js',
    'sidequests/human_fusion_lab_next/contracts/SCHEMA_V2.json',
    'sidequests/human_fusion_lab_next/eval/instrument.js',
    'sidequests/human_fusion_lab_next/d04/run_d04.js',
    'sidequests/human_fusion_lab/models/xgb69_candidate.json',
    'sidequests/human_fusion_lab/results/AUDIT.json',
];
for (const f of files) entries[f] = B.sha(path.join(ROOT, f));
/* 九会话输入 + 参考 */
const audit = JSON.parse(fs.readFileSync(path.join(ROOT, 'sidequests/human_fusion_lab/results/AUDIT.json'), 'utf8'));
for (const rec of audit.sessions) {
    const dir = path.join(ROOT, 'captures/remote', rec.sid);
    entries['captures/remote/' + rec.sid + '/meta.json'] = B.sha(path.join(dir, 'meta.json'));
    entries['captures/remote/' + rec.sid + '/points.bin'] = B.sha(path.join(dir, 'points.bin'));
    if (rec.gt_path) entries[rel(rec.gt_path)] = B.sha(rec.gt_path);
    const m = path.join(path.dirname(rec.gt_path), 'manifest.json');
    if (fs.existsSync(m)) entries[rel(m)] = B.sha(m);
}
const refDir = path.join(ROOT, 'captures/remote/cap_20261009_113611');
entries['captures/remote/cap_20261009_113611/meta.json'] = B.sha(path.join(refDir, 'meta.json'));
entries['captures/remote/cap_20261009_113611/points.bin'] = B.sha(path.join(refDir, 'points.bin'));
/* D04 基线 ledger 引用（D05 base 不重跑） */
const baseRuns = path.join(ROOT, 'docs/human_capture/evidence/2026-10-11_hfus_d04_r1/runs/base');
for (const n of fs.readdirSync(baseRuns)) {
    if (n.endsWith('.jsonl') || n.endsWith('_SUMMARY.json')) entries['evidence/d04_base_ledger/' + n] = B.sha(path.join(baseRuns, n));
}
const out = { version: 'hfus-d05-baseline-shas-v1', date: '2026-10-11', note: 'frozen before any D05 variant run', shas: entries };
fs.mkdirSync(path.join(ROOT, 'docs/human_capture/evidence/2026-10-11_hfus_d05_r1'), { recursive: true });
fs.writeFileSync(path.join(ROOT, 'docs/human_capture/evidence/2026-10-11_hfus_d05_r1/BASELINE_SHAS.json'), JSON.stringify(out, null, 2), { flag: 'wx' });
console.log('BASELINE_SHAS_D05_WRITTEN', Object.keys(entries).length, 'files');

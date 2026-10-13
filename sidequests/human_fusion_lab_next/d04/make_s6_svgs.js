'use strict';
/* Generate S6 f128/187/188 SVG snapshots for each D04 variant from its D04 ledger.
 * Reuses run_b.js svg() drawing convention but standalone so D04 evidence can be self-contained.
 * Outputs D04_<variant>_S6_f{128,187,188}.svg into docs/human_capture/evidence/2026-10-11_hfus_d04_r1/
 * Node 24 | read-only on captures/Git | writes only to evidence root. */
const fs = require('fs'), path = require('path'), readline = require('readline');
const B = require('../background/detector_b');
const D = require('../../human_fusion_lab/core/data_loader');
const L = require('../../human_fusion_lab/core/leveling');
const I = require('../contracts/index_v1');

const ROOT = B.ROOT;
const EVID = path.join(ROOT, 'docs/human_capture/evidence/2026-10-11_hfus_d04_r1');
const SID = 'cap_20261010_180235';
const FRAMES = [128, 187, 188];
const session = D.load_session(path.join(ROOT, 'captures/remote', SID));
const co = L.resolve_contract({ already_leveled: false }, null);

function colorFor(i, gt, acc, all) {
    if (gt.has(i)) return '#ef4444';
    if (acc.has(i)) return '#16a34a';
    if (all.has(i)) return '#a855f7';
    return '#aaaaaa';
}

async function* lines(file) {
    const rl = readline.createInterface({ input: fs.createReadStream(file), crlfDelay: Infinity });
    for await (const l of rl) if (l.trim()) yield l;
}

function svgBlock(variant, sid, fidx, frame, lv, row) {
    const gt = new Set(row.gt.filter(g => g.class_name === 'PERSON').flatMap(g => g.indices));
    const all = new Set(row.candidates.flatMap(c => c.raw_indices));
    const acc = new Set(row.candidates.filter(c => c.prob >= .35).flatMap(c => c.raw_indices));
    let body = '';
    let drawn = 0;
    for (let i = 0; i < lv.length / 4; i++) {
        if (!Number.isFinite(lv[i * 4]) || lv[i * 4 + 2] < .1 || lv[i * 4 + 2] > 2.5) continue;
        const x = 350 + lv[i * 4] * 45, y = 540 - lv[i * 4 + 1] * 45;
        if (x < 0 || x > 900 || y < 60 || y > 650) continue;
        const c = colorFor(i, gt, acc, all);
        body += `<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="${gt.has(i) ? 2 : 1}" fill="${c}"/>`;
        drawn++;
    }
    for (const c of row.candidates) {
        body += `<text x="${350 + c.x * 45}" y="${540 - c.y * 45}" font-size="10">${c.id} p=${c.prob.toFixed(3)} ${c.track_confirmed ? 'confirmed' : 'tentative'}</text>`;
    }
    return `<svg xmlns="http://www.w3.org/2000/svg" width="900" height="680"><rect width="900" height="680" fill="white"/><text x="10" y="25">${variant} ${sid} f${fidx} — red=GT-p, green=accepted, purple=cand, gray=level-fg; drawn=${drawn}, gt=${gt.size}, acc=${acc.size}, cand=${all.size}</text>${body}</svg>`;
}

async function makeOne(variant, fidx) {
    const ledger = path.join(EVID, 'runs', variant, `D04_${variant}_${SID}.jsonl`);
    if (!fs.existsSync(ledger)) { console.log('MISSING ledger', ledger); return false; }
    let row = null;
    for await (const l of lines(ledger)) { const o = JSON.parse(l); if (o.frame_index === fidx) { row = o; break; } }
    if (!row) { console.log('no frame', fidx, 'in', ledger); return false; }
    const frameObj = session.frames.find(f => f.index === fidx);
    if (!frameObj) { console.log('no session frame', fidx); return false; }
    const lv = I.mapFrame(frameObj.xyzi, co).leveled_xyzi;
    const out = path.join(EVID, `D04_${variant}_S6_f${fidx}.svg`);
    fs.writeFileSync(out, svgBlock(variant, SID, fidx, frameObj, lv, row), { flag: 'wx' });
    console.log('wrote', path.relative(ROOT, out));
    return true;
}

(async () => {
    for (const v of ['base', 'split_only', 'point30_only', 'point15_only', 'unknown04_only']) {
        for (const f of FRAMES) await makeOne(v, f);
    }
})();

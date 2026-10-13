'use strict';
/* D04 案例包：12 个真实帧 SVG + 最小人工审核集。
 * 输出 docs/human_capture/evidence/2026-10-11_hfus_d04_r1/case_pack/（新目录，wx 不覆盖）
 * Node 24 | 只读 captures/GT | 不写 GT / 不改生产 */
const fs = require('fs'), path = require('path'), readline = require('readline'), crypto = require('crypto');
const B = require('../background/detector_b');
const D = require('../../human_fusion_lab/core/data_loader');
const L = require('../../human_fusion_lab/core/leveling');
const I = require('../contracts/index_v1');

const ROOT = B.ROOT;
const EVID = path.join(ROOT, 'docs/human_capture/evidence/2026-10-11_hfus_d04_r1');
const OUT = path.join(EVID, 'case_pack');
if (fs.existsSync(OUT)) throw new Error('refuse overwrite ' + OUT);
fs.mkdirSync(OUT, { recursive: true });
fs.mkdirSync(path.join(OUT, 'frames'));

const sha = p => crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
async function* lines(f) { const rl = readline.createInterface({ input: fs.createReadStream(f), crlfDelay: Infinity }); for await (const l of rl) if (l.trim()) yield l; }

/* cases: [label, category, sid, frame, ledgers]  ledgers: base-A(D03), base-B(D04-d04_base) */
const CASES = [
    ['s5_miss',       'MISS_STILL', 'cap_20261010_175943', 0,   'S5'],
    ['s6_f128',       'FAIL_SPARSE','cap_20261010_180235', 128, 'S6'],
    ['s6_f187',       'FAIL_SPARSE','cap_20261010_180235', 187, 'S6'],
    ['s6_f188',       'FAIL_SPARSE','cap_20261010_180235', 188, 'S6'],
    ['near_body',     'MOVE_NEAR',  'cap_20261010_175429', 100, 'S3near'],
    ['near_furn_fp',  'FURN_NEAR',  'cap_20261010_175429', 0,   'S3near'],
    ['far_body',      'SPARSE_FAR', 'cap_20261010_175553', 100, 'S3far'],
    ['s1_empty_mid',  'EMPTY_FURN', 'cap_20261010_175227', 151, 'S1'],
    ['s4_still',      'STILL_20S',  'cap_20261010_175804', 100, 'S4'],
    ['s8_still',      'STILL_20S',  'cap_20261010_180557', 100, 'S8'],
    ['s7_sparse',     'SPARSE_FAR', 'cap_20261010_180337', 100, 'S7'],
    ['s1_start',      'EMPTY_FURN', 'cap_20261010_175227', 0,   'S1'],
];
async function firstLines(p, n) { const out = []; for await (const l of lines(p)) { out.push(JSON.parse(l)); if (out.length >= n) break; } return out; }
async function getRow(p, fidx) { for await (const l of lines(p)) { const o = JSON.parse(l); if (o.frame_index === fidx) return o; } return null; }

function svgFrame(label, sid, fidx, lv, rows) {
    /* rows: [{name:'base-A',row},{name:'base-B',row}]  shared lv */
    const panes = [];
    for (let pi = 0; pi < rows.length; pi++) {
        const r = rows[pi].row, ox = 20 + pi * 470;
        const gt = r ? new Set(r.gt.filter(g => g.class_name === 'PERSON').flatMap(g => g.indices)) : new Set();
        const acc = r ? new Set(r.candidates.filter(c => c.prob >= .35).flatMap(c => c.raw_indices)) : new Set();
        const all = r ? new Set(r.candidates.flatMap(c => c.raw_indices)) : new Set();
        panes.push(`<text x="${ox}" y="20" font-size="12" font-weight="bold">${rows[pi].name} ${label} f${fidx}</text>`);
        let cnt = 0;
        for (let i = 0; i < lv.length / 4; i++) {
            if (!Number.isFinite(lv[i * 4]) || lv[i * 4 + 2] < .1 || lv[i * 4 + 2] > 2.5) continue;
            const x = ox + 30 + lv[i * 4] * 22, y = 320 - lv[i * 4 + 1] * 22;
            if (x < ox || x > ox + 450 || y < 30 || y > 330) continue;
            const c = gt.has(i) ? '#ef4444' : acc.has(i) ? '#16a34a' : all.has(i) ? '#a855f7' : '#c9c9c9';
            panes.push(`<circle cx="${x.toFixed(1)}" cy="${y.toFixed(1)}" r="${gt.has(i) ? 1.8 : 1}" fill="${c}"/>`);
            if (++cnt > 6000) break;
        }
        if (r) {
            const so = r.strict && r.strict.observed_confirmed || { tp: '-', fn: '-', fp: '-', unmatched_unknown: '-' };
            const lg = r.legacy && r.legacy.confirmed || { tp: '-', fp: '-', fn: '-' };
            panes.push(`<text x="${ox}" y="345" font-size="10">strict obs tp=${so.tp} fn=${so.fn} fp=${so.fp} uu=${so.unmatched_unknown} | legacy conf tp=${lg.tp} fp=${lg.fp} fn=${lg.fn}</text>`);
            for (const c of r.candidates.slice(0, 12)) panes.push(`<text x="${ox + 30 + c.x * 22}" y="${320 - c.y * 22}" font-size="9">${c.id} p=${c.prob.toFixed(2)}</text>`);
        } else panes.push(`<text x="${ox}" y="345" font-size="10" fill="red">frame NOT in ledger (S9 INVALID_BINDING or skipped)</text>`);
    }
    return `<svg xmlns="http://www.w3.org/2000/svg" width="950" height="360"><rect width="950" height="360" fill="white"/>${panes.join('')}</svg>`;
}

(async () => {
    const co = L.resolve_contract({ already_leveled: false }, null);
    const files = {};
    const indexHtml = [];
    indexHtml.push('<!doctype html><html><meta charset="utf-8"><title>D04 案例包</title><style>body{font:15px sans-serif;background:#10141c;color:#eee;padding:14px}h2{color:#8fd}svg{border:1px solid #555;margin:8px 0}table{border-collapse:collapse}td,th{border:1px solid #555;padding:4px}</style>');
    indexHtml.push('<h2>HFUS-D04 案例对比（base-A 旧版 vs base-B D04 基线）— 12 帧真实数据</h2><p>红=GT 人体，绿=legacy 接受候选，紫=被拒候选，灰=背景/前景非候选。每个 SVG 下方写该帧 strict/legacy 计分。</p>');
    for (const [label, cat, sid, fidx, sessName] of CASES) {
        const sess = D.load_session(path.join(ROOT, 'captures/remote', sid));
        const f0 = sess.frames.find(fr => fr.index === fidx);
        if (!f0) { console.log('skip', label, 'no frame', fidx); continue; }
        const lv = I.mapFrame(f0.xyzi, co).leveled_xyzi;
        const rowA = await getRow(path.join(ROOT, 'docs/human_capture/evidence/2026-10-11_hfus_d03_r1/A_' + sid + '.jsonl'), fidx);
        const rowB = await getRow(path.join(ROOT, 'docs/human_capture/evidence/2026-10-11_hfus_d04_r1/runs/base/D04_base_' + sid + '.jsonl'), fidx);
        const rows = [{ name: 'D03-A(legacy线)' }, { name: 'D04-base(B线)' }];
        const svgname = `case_${label}_f${fidx}.svg`;
        rows[0].row = rowA; rows[1].row = rowB;
        fs.writeFileSync(path.join(OUT, 'frames', svgname), svgFrame(label, sid, fidx, lv, rows));
        indexHtml.push(`<h3>${sessName} · ${label} · f${fidx}（${cat}）</h3><img src="frames/${svgname}">`);
        console.log('wrote', svgname);
    }
    indexHtml.push('<p>生成时间 2026-10-11 D04；本页不修改 GT。若需人工复核另开 review.html。</p></html>');
    fs.writeFileSync(path.join(OUT, 'index.html'), indexHtml.join('\n'));

    /* ---------- minimal review set (4 categories × 2 sessions × 1 frame) ---------- */
    const REVIEW = [
        ['static_human',  'S4', 'cap_20261010_175804', 100, 'static person in window'],
        ['static_human',  'S8', 'cap_20261010_180557', 100, 'static person in window'],
        ['moving_human',  'S3near', 'cap_20261010_175429', 100, 'walk near'],
        ['moving_human',  'S6', 'cap_20261010_180235', 60, 'sit-to-stand'],
        ['sparse_far',    'S3far', 'cap_20261010_175553', 100, 'far walk'],
        ['sparse_far',    'S7', 'cap_20261010_180337', 100, 'sparse far'],
        ['empty_furniture','S1', 'cap_20261010_175227', 151, 'empty+furniture'],
        ['empty_furniture','S1', 'cap_20261010_175227', 302, 'empty+furniture end'],
    ];
    const minimal = { schema_version: 'hfus-d04-minimal-review-v1', created: '2026-10-11', instruction: 'User reviews each case in demo/review.html, marks person vs furniture regions. DRAFT only; no auto-reviewed.', categories: {} };
    for (const [cat, sessName, sid, fidx, note] of REVIEW) {
        (minimal.categories[cat] ||= []).push({ session: sessName, sid, frame: fidx, note, review_status: 'DRAFT_UNREVIEWED', human_label: null, person_raw_indices: null, furniture_raw_indices: null });
    }
    fs.writeFileSync(path.join(OUT, 'minimal_review_set.json'), JSON.stringify(minimal, null, 2));

    /* manifest */
    const man = { created: '2026-10-11', case_svgs: CASES.map(c => 'frames/case_' + c[0] + '_f' + c[3] + '.svg'), minimal_review_set: 'minimal_review_set.json', review_html: 'sidequests/human_fusion_lab_next/review/review.html', note: 'Case SVGs embed leveled xyzi coords from captures; ledgers SHA in MANIFEST_DEMO.json' };
    fs.writeFileSync(path.join(OUT, 'MANIFEST_CASE_PACK.json'), JSON.stringify(man, null, 2));
    console.log('done case_pack');
})();

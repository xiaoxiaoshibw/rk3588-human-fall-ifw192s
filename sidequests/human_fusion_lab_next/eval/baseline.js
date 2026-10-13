'use strict';
/* D05 逐点阶段归因探针（元信息诊断，只读 base ledger + instrument，不改管线、不参与打分）。
 * 输出 GT PERSON 点从 RAW→BG→CLEANUP→FINAL 的逐点去向，回答「是谁、在哪一层、为什么删了人点」。
 * CLI: node sidequests/human_fusion_lab_next/eval/baseline.js <out_dir> [sid,sid,...]
 * 依赖前提：base ledger 已存在（D04 runs/base/D04_base_cap_*.jsonl），输入/GT SHA 已由 BASELINE_SHAS 冻结。 */
const fs = require('fs'), path = require('path');
const B = require('../background/detector_b');
const I = require('../contracts/index_v1');
const D = require('../../human_fusion_lab/core/data_loader');
const S = require('../../human_fusion_lab/core/schema');
const { objects } = require('../../human_fusion_lab/export');
const { instrument } = require('./instrument');

const ROOT = B.ROOT;
const BASE = path.join(ROOT, 'docs/human_capture/evidence/2026-10-11_hfus_d04_r1/runs/base');
const OUT_DEFAULT = path.join(ROOT, 'docs/human_capture/evidence/2026-10-11_hfus_d05_r1/baseline_probe');

/* 与 detector_b.select 完全同构的「带逐点原因」BG 判定（副本逻辑，原样私有；返回逐点 keep+reason） */
function pointwiseSelect(lv, pipe, keys, columns, unknownRadius) {
    const BG = require('../../human_fusion_lab_v3/core/bg_groups');
    const out = BG.groupB(lv, pipe, keys);
    const radius = unknownRadius === undefined ? .4 : unknownRadius;
    if (columns) {
        for (let r = 0; r < out.keep.length; r++) {
            if (!out.keep[r]) continue;
            const x = lv[r * 4], y = lv[r * 4 + 1], ix = Math.floor(x / .15), iy = Math.floor(y / .15);
            let support = false;
            outer: for (let a = -3; a <= 3; a++) for (let b = -3; b <= 3; b++) {
                const list = columns.get((ix + a) + ',' + (iy + b));
                if (list && list.some(c => (c.x - x) ** 2 + (c.y - y) ** 2 <= radius ** 2)) { support = true; break outer; }
            }
            if (!support) { out.keep[r] = 0; out.reasons[r] = 'no_reference_XY_support_UNKNOWN'; }
            else out.reasons[r] = 'no_bg_match_supported_XY_UNKNOWN';
        }
    }
    return out;
}

function run(outdir, filter) {
    outdir = outdir || OUT_DEFAULT;
    fs.mkdirSync(outdir, { recursive: true });
    const summary = [];
    const audit = JSON.parse(fs.readFileSync(path.join(ROOT, 'sidequests/human_fusion_lab/results/AUDIT.json'), 'utf8'));
    for (const rec of audit.sessions) {
        if (filter && !filter.includes(rec.sid)) continue;
        const baseLedger = path.join(BASE, 'D04_base_' + rec.sid + '.jsonl');
        if (!fs.existsSync(baseLedger)) { console.log('skip(no base ledger)', rec.sid); continue; }
        const session = D.load_session(path.join(ROOT, 'captures/remote', rec.sid));
        let doc = null;
        const gtManifest = path.join(path.dirname(rec.gt_path), 'manifest.json');
        const ok = fs.existsSync(gtManifest) && B.sha(gtManifest) === rec.manifest_sha256 && rec.eligible && fs.existsSync(rec.gt_path) && B.sha(rec.gt_path) === rec.gt_sha256;
        if (ok) {
            const cand = JSON.parse(fs.readFileSync(rec.gt_path, 'utf8'));
            if (cand.session_id === rec.sid && cand.review_status === 'reviewed' && cand.session_sha256 && cand.session_sha256.meta === session.meta_sha256 && cand.session_sha256.points === session.points_sha256) doc = cand;
        }
        if (!doc) { console.log('skip(no/gInvalid GT)', rec.sid); continue; }

        const det = B.createDetector(B.buildReference());
        const e = instrument(det.engine);
        const ref = det.engine._bgB;
        const gen = det.begin(rec.sid);
        const ledger = new Map();
        for (const line of fs.readFileSync(baseLedger, 'utf8').split(/\r?\n/)) {
            if (!line) continue;
            const j = JSON.parse(line);
            ledger.set(j.frame_index, j);
        }
        let gt_tot = 0, gt_bgkeep = 0, gt_cleankeep = 0, gt_final = 0, gt_comp = 0, gt_cand = 0;
        const reason_lit = {};
        const per_frame = [];
        for (const f of session.frames) {
            const fc = S.make_frame_context({ session_id: rec.sid, session_generation: gen, frame_index: f.index, timestamp: f.timestamp, xyzi: f.xyzi, meta: session.meta });
            det.tick(fc);
            const mapping = e._mapped, lv = mapping.leveled_xyzi;
            const gt = objects(doc, f.index, Array.from(mapping.compact_to_raw));
            const persons = (gt || []).filter(g => g.class_name === 'PERSON' && g.source === 'human');
            if (!persons.length) continue;

            /* 逐点 BG 真判定（含 UNKNOWN 半径原因）——与 select 同构,不改引擎 */
            const pw = pointwiseSelect(lv, det.engine.pipe, ref.staticKeys, ref.columns, .4);

            const ledger_row = ledger.get(f.index);
            const comp_ids = new Set(), cand_ids = new Set();
            if (ledger_row) {
                for (const c of ledger_row.raw_components) for (const i of c.raw_indices) comp_ids.add(i);
                for (const c of ledger_row.candidates) for (const i of c.raw_indices) cand_ids.add(i);
            }
            /* instrument._ledger.final_ids/cleanup_ids/background_ids 是本帧 leveled 长向量子序列 → raw 行索引（见 instrument） */
            const leds = e._ledger || { background_ids: [], cleanup_ids: [], final_ids: [], components: [] };
            const bgK = new Set(leds.background_ids), clK = new Set(leds.cleanup_ids), fnK = new Set(leds.final_ids);

            for (const g of persons) {
                for (const rawIdx of g.indices) {
                    gt_tot++;
                    const reason = pw.reasons[rawIdx] || 'unknown';
                    const stage = {
                        bg_keep: !!pw.keep[rawIdx], bg_reason: reason,
                        bg_kept_set: bgK.has(rawIdx), cleanup_kept: clK.has(rawIdx), final_fg: fnK.has(rawIdx),
                        in_components: comp_ids.has(rawIdx), in_candidates: cand_ids.has(rawIdx),
                    };
                    reason_lit[reason] = (reason_lit[reason] || 0) + 1;
                    if (stage.bg_keep) gt_bgkeep++;
                    if (stage.cleanup_kept) gt_cleankeep++;
                    if (stage.final_fg) gt_final++;
                    if (stage.in_components) gt_comp++;
                    if (stage.in_candidates) gt_cand++;
                }
                /* 帧级简表（GT 对象所在帧，n/覆盖率） */
                const si = g.indices;
                const c1 = si.filter(i => pw.keep[i]).length;
                const c2 = si.filter(i => clK.has(i)).length;
                const c3 = si.filter(i => comp_ids.has(i)).length;
                const c4 = si.filter(i => cand_ids.has(i)).length;
                per_frame.push({ frame_index: f.index, gt_id: g.id, gt_n: si.length, bg_keep: c1, cleanup_keep: c2, comp: c3, cand: c4, strict_fn: !!(ledger_row && ledger_row.strict.observed_confirmed.fn_ids.includes(g.id)) });
            }
        }
        const s = { sid: rec.sid, activity: rec.activity, gt_person_pts: gt_tot, bg_keep: gt_bgkeep, cleanup_keep: gt_cleankeep, final_fg: gt_final, in_components: gt_comp, in_candidates: gt_cand, reason_hist: reason_lit, per_frame };
        summary.push({ sid: rec.sid, activity: rec.activity, gt_person_pts: gt_tot, bg_keep_pct: +(100 * gt_bgkeep / gt_tot).toFixed(1), cleanup_keep_pct: +(100 * gt_cleankeep / gt_tot).toFixed(1), final_fg_pct: +(100 * gt_final / gt_tot).toFixed(1), in_components_pct: +(100 * gt_comp / gt_tot).toFixed(1), in_candidates_pct: +(100 * gt_cand / gt_tot).toFixed(1), reason_hist: reason_lit });
        fs.writeFileSync(path.join(outdir, 'PROBE_' + rec.sid + '.json'), JSON.stringify(s, null, 2), { flag: 'wx' });
        console.log('PROBE', rec.sid, rec.activity, 'GTpts=' + gt_tot, 'bg=' + (100 * gt_bgkeep / gt_tot).toFixed(1) + '%', 'cleanup=' + (100 * gt_cleankeep / gt_tot).toFixed(1) + '%', 'comp=' + (100 * gt_comp / gt_tot).toFixed(1) + '%', JSON.stringify(reason_lit));
    }
    fs.writeFileSync(path.join(outdir, 'PROBE_SUMMARY.json'), JSON.stringify({ version: 'hfus-d05-probe-v1', date: '2026-10-11', note: 'pointwise stage attribution of GT PERSON (source==human only); diagnostic, not for promotion', sessions: summary }, null, 2), { flag: 'wx' });
    return summary;
}
module.exports = { run, pointwiseSelect };
if (require.main === module) run(process.argv[2], process.argv[3] ? process.argv[3].split(',') : null);

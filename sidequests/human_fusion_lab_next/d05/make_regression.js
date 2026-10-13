'use strict';
/* HFUS-D05 跨变体最终回归合并：引用 D04 base (不重跑) + 新 A/B/C/abc 变体。
 * 判定原则延续 D04:
 *  - 正式打分只算 doc-bound 的 8 会话；S9 (180751) 永远 exploration。
 *  - 每会话给 strict(accepted/observed_confirmed)/legacy(accepted/confirmed) 双轨 + perf。
 *  - 不给总平均；标 ΔTP/ΔFP/ΔFN 相对 base。
 * CLI: node sidequests/human_fusion_lab_next/d05/make_regression.js
 */
const fs = require('fs'), path = require('path');
const B = require('../background/detector_b');
const ROOT = B.ROOT;
const D5 = path.join(ROOT, 'docs/human_capture/evidence/2026-10-11_hfus_d05_r1');
const D4 = path.join(ROOT, 'docs/human_capture/evidence/2026-10-11_hfus_d04_r1');

const SESSIONS = ['cap_20261010_175227', 'cap_20261010_175429', 'cap_20261010_175553', 'cap_20261010_175804', 'cap_20261010_175943', 'cap_20261010_180235', 'cap_20261010_180337', 'cap_20261010_180557', 'cap_20261010_180751'];

function loadSummary(variant) {
    if (variant === 'base') {
        const p = path.join(D4, 'runs/base/D04_base_SUMMARY.json');
        const j = JSON.parse(fs.readFileSync(p, 'utf8'));
        return { path: p, sha: B.sha(p), report: j };
    }
    const p = path.join(D5, 'runs', variant, 'D05_' + variant + '_SUMMARY.json');
    if (!fs.existsSync(p)) return null;
    return { path: p, sha: B.sha(p), report: JSON.parse(fs.readFileSync(p, 'utf8')) };
}

function extractFormal(s) {
    /* 正式分会话行；S9 进 exploration 行 */
    const bySid = {};
    for (const sess of s.report.sessions) {
        if (sess.sid === 'cap_20261010_180751') continue;
        bySid[sess.sid] = {
            activity: sess.activity,
            gt_persons: sess.gt_persons,
            strict: { accepted: sess.accepted, observed_confirmed: sess.observed_confirmed, proposal: sess.proposal },
            legacy: { accepted: sess.legacy_accepted, confirmed: sess.legacy_confirmed },
            candidates: sess.candidate_count,
            unsupported_UNKNOWN_points: sess.unsupported_UNKNOWN_points,
            perf: { p50: sess.performance.diagnostic_compute_p50_ms, p95: sess.performance.diagnostic_compute_p95_ms, p99: sess.performance.diagnostic_compute_p99_ms, heap_max: sess.performance.heap_max_mb },
            hook_stats_summary: summarizeHookStats(sess.hook_stats),
        };
    }
    return bySid;
}
function summarizeHookStats(hs) {
    if (!hs) return null;
    const out = {};
    for (const k of Object.keys(hs)) {
        const rows = hs[k];
        if (!rows || !rows.length) { out[k] = null; continue; }
        const last = rows[rows.length - 1];
        out[k] = { frames: rows.length, final_totals: {} };
        for (const key of Object.keys(last)) if (key !== 'frame_index') out[k].final_totals[key] = last[key];
    }
    return out;
}

function build() {
    const variants = ['base', 'a03', 'a06', 'b', 'c', 'abc'];
    const loaded = {};
    for (const v of variants) {
        const s = loadSummary(v);
        if (s) loaded[v] = extractFormal(s);
    }
    const base = loaded.base;
    const bySession = {};
    for (const sid of SESSIONS) {
        if (sid === 'cap_20261010_180751') continue;
        bySession[sid] = { activity: base[sid].activity, variants: {} };
        for (const v of variants) {
            if (!loaded[v] || !loaded[v][sid]) continue;
            const d = loaded[v][sid];
            if (v === 'base') bySession[sid].variants[v] = d;
            else {
                bySession[sid].variants[v] = {
                    ...d,
                    delta_vs_base: {
                        legacy_confirmed_tp: d.legacy.confirmed.tp - base[sid].legacy.confirmed.tp,
                        legacy_confirmed_fp: d.legacy.confirmed.fp - base[sid].legacy.confirmed.fp,
                        legacy_confirmed_fn: d.legacy.confirmed.fn - base[sid].legacy.confirmed.fn,
                        strict_accepted_tp: d.strict.accepted.tp - base[sid].strict.accepted.tp,
                        strict_observed_confirmed_tp: d.strict.observed_confirmed.tp - base[sid].strict.observed_confirmed.tp,
                        unsupported_UNKNOWN_points: d.unsupported_UNKNOWN_points - base[sid].unsupported_UNKNOWN_points,
                        p95_ms: +(d.perf.p95 - base[sid].perf.p95).toFixed(2),
                    },
                };
            }
        }
    }
    /* exploration 行 (S9) 单列，不进 bySession */
    const exploration = {};
    for (const v of variants) {
        if (!loaded[v]) continue;
        const src = (v === 'base' ? JSON.parse(fs.readFileSync(path.join(D4, 'runs/base/D04_base_SUMMARY.json'), 'utf8')) : JSON.parse(fs.readFileSync(path.join(D5, 'runs', v, 'D05_' + v + '_SUMMARY.json'), 'utf8')));
        const row = src.sessions.find(s => s.sid === 'cap_20261010_180751');
        exploration[v] = row ? { activity: row.activity, exploration_only: true, candidates: row.candidate_count, unsupported_UNKNOWN_points: row.unsupported_UNKNOWN_points } : null;
    }
    const out = { version: 'hfus-d05-regression-final-v1', date: '2026-10-11', base_reference: 'D04_base_SUMMARY.json sha=' + B.sha(path.join(D4, 'runs/base/D04_base_SUMMARY.json')), formal_sessions: 8, exploration_session: 'cap_20261010_180751 (INVALID_BINDING, exploration only, never scored)', sessions: bySession, exploration };
    fs.writeFileSync(path.join(D5, 'REGRESSION_FINAL.json'), JSON.stringify(out, null, 2), { flag: 'wx' });
    console.log('REGRESSION_FINAL_D05_WRITTEN', Object.keys(loaded).join(','));
}
build();

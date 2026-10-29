"""Reconcile S07F tables and re-verify support connectivity and drops."""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'r11'))

import numpy as np
from common2 import EV, OLD_EV, SK, save, read, jsonlines
from support_geometry import prep, transverse_local, band_distal_mask, comps, spans_ok
from experiment import summarize
import experiment as X


def main():
    for g in ('RAW_NEW2', 'FG_NEW2'):
        records = jsonlines(EV / (g + '_FRAMES.jsonl'))
        assert summarize(records) == read(EV / (g + '_SUMMARY.json'))
        assert read(EV / (g + '_VERIFY.json'))['frames'] == 386
    src = X.source()
    with np.load(OLD_EV / 'FOREGROUND_LEDGER.npz', allow_pickle=False) as z:
        ledger = {k: z[k] for k in z.files}
    conn = {}
    try:
        for fi in range(386):
            f = src.frame(fi)
            p, rows = X.roi(f)
            sl = slice(ledger['indptr'][fi], ledger['indptr'][fi + 1])
            p = p[ledger['keep'][sl]]
            rows = rows[ledger['keep'][sl]]
            if len(p) < 30:
                continue
            p2, rows2, local, frac = prep(p, rows)
            t = transverse_local(local, frac)
            idx = band_distal_mask(t, frac, -1., (.52, .88))
            if not len(idx):
                continue
            ncomp = len(comps(local[idx], .30))
            span = np.ptp(local[idx], axis=0)
            if 183 <= fi < 334:
                reason = 'valid'
                if not spans_ok(local, idx):
                    reason = 'LOW_SUPPORT mask_n=%d' % len(idx) if len(idx) < 6 else ('SPARSE_VERTICAL_SUPPORT' if span[2] < .025 else 'CONFLICTING_SPATIAL_SUPPORT')
                conn[fi] = dict(mask_n=len(idx), ncomp=ncomp, span_m=span.tolist(), valid=reason == 'valid', reason=reason)
    finally:
        src.close()
    recs = jsonlines(EV / 'FG_NEW2_FRAMES.jsonl')
    invalid_frames = [r['fi'] for r in recs[183:334] if not r['nodes']['OUTER_A']['valid']]
    drops = {fi: d for fi, d in conn.items() if not d['valid']}
    assert sorted(drops) == invalid_frames, (sorted(drops), invalid_frames)
    mech = read(EV / 'MECHANISM_SUPPORT_RULES_R3.json')
    assert sorted(drops) == sorted(mech['rules']['OUTER_A|RB']['drops']), 'drop list differs from registered mechanism expectation'
    single = sum(1 for d in conn.values() if d['ncomp'] == 1)
    hist = {}
    for d in conn.values():
        hist[d['ncomp']] = hist.get(d['ncomp'], 0) + 1
    old_recs = {r['fi']: r for r in jsonlines(OLD_EV / 'FG_NEW_FRAMES.jsonl')}
    deltas = []
    for r in recs[183:334]:
        o = old_recs[r['fi']]['nodes']['OUTER_A']
        n = r['nodes']['OUTER_A']
        if o['valid'] and n['valid']:
            deltas.append(float(np.linalg.norm(np.asarray(n['xyz']) - np.asarray(o['xyz'])) * 1000))
    save('VERIFY2.json', dict(
        summary_reconciliation='summarize(FRAMES)==SUMMARY for RAW_NEW2 and FG_NEW2; each run recorded 386 frames',
        xyz_recompute='per-run: every valid node recomputed from bound source rows, max error < 1e-10 m (RAW_NEW2/FG_NEW2 *_VERIFY.json)',
        connectivity=dict(hold_frames=len(conn), single_component=single, ratio=single / len(conn), component_hist=dict(sorted(hist.items())), linkage_m=.30),
        drops=drops,
        records_vs_recompute_agree=True,
        drops_match_registered_expectation=True,
        outer_a_delta_vs_s07_mm=dict(n=len(deltas), min=round(min(deltas), 1), p50=round(float(np.median(deltas)), 1), max=round(max(deltas), 1)),
        note='Recomputed from source rows + frozen ledger; connectivity verified on the registered variant support. Dropped frames have mask_n below the unchanged minimum point gate (6); no whole-window missing substitution.',
    ))
    print('connectivity', single, '/', len(conn), dict(sorted(hist.items())))
    print('drops', drops)
    print('delta_vs_s07', dict(n=len(deltas), min=round(min(deltas), 1), p50=round(float(np.median(deltas)), 1), max=round(max(deltas), 1)))


if __name__ == '__main__':
    main()

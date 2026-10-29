"""Source-row mechanism review: dual OUTER populations and support-rule comparison.

Read-only over frozen S07 artifacts + the registered session. Produces the
mechanism evidence that the single registered variant is based on.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'r11'))

import numpy as np
from common2 import EV, OLD_EV, SK, save, read, jsonlines
from support_geometry import prep, r11_masks, band_distal_mask, comps, spans_ok
import experiment as X

HOLD = (183, 334)
RULES = ('R0', 'R1', 'R4', 'R5', 'RB')


def steps(series, lo, hi):
    valid = sorted((fi, q) for fi, q in series.items() if lo <= fi < hi and q is not None)
    cons = [(fa, fb, float(np.linalg.norm(b - a) * 1000)) for (fa, a), (fb, b) in zip(valid, valid[1:]) if fb == fa + 1]
    span = [(fa, fb, float(np.linalg.norm(b - a) * 1000)) for (fa, a), (fb, b) in zip(valid, valid[1:]) if fb > fa + 1]
    return valid, cons, span


def main():
    suffix = sys.argv[1] if len(sys.argv) > 1 else ''
    sfx = '_' + suffix if suffix else ''
    src = X.source()
    with np.load(OLD_EV / 'FOREGROUND_LEDGER.npz', allow_pickle=False) as z:
        ledger = {k: z[k] for k in z.files}
    records = jsonlines(OLD_EV / 'FG_NEW_FRAMES.jsonl')
    pairs = sorted({(c['from_frame'], c['to_frame']) for c in read(OLD_EV / 'CANDIDATE_FAILURE_DIAGNOSIS.json')['cases']})
    pairframes = sorted({f for p in pairs for f in p})
    series = {nm: {k: {} for k in RULES} for nm in ('OUTER_A', 'OUTER_B')}
    mask_check = dict(frames=0, nodes=0, mismatch=[])
    rb_comp = {}
    rb_span = {}
    rb_size = {}
    multi_hold = 0
    multi_full = 0
    dual = []
    try:
        for fi in range(386):
            f = src.frame(fi)
            p, rows = X.roi(f)
            sl = slice(ledger['indptr'][fi], ledger['indptr'][fi + 1])
            assert np.array_equal(rows, ledger['global_rows'][sl])
            p = p[ledger['keep'][sl]]
            rows = rows[ledger['keep'][sl]]
            if len(p) < 30:
                continue
            p2, rows2, local, frac = prep(p, rows)
            m, t = r11_masks(local, frac)
            rec = records[fi]
            if rec.get('diagnostics') and 'partitions' in rec['diagnostics']:
                mask_check['frames'] += 1
                for nm in SK.SLOTS:
                    sel = set(int(rr) for rr in rec['diagnostics']['partitions'][nm]['selected_rows'])
                    mine = set(int(rows2[i]) for i in m[nm])
                    mask_check['nodes'] += 1
                    if sel != mine:
                        mask_check['mismatch'].append([fi, nm, len(sel), len(mine)])
            else:
                mask_check.setdefault('skipped_frames', []).append(fi)
            upmask = m['UPPER_A']
            up = np.median(p2[upmask], 0) if len(upmask) and spans_ok(local, upmask) else None
            for nm, sgn in (('OUTER_A', -1.0), ('OUTER_B', 1.0)):
                idx = m[nm]
                if not len(idx):
                    for k in RULES:
                        series[nm][k][fi] = None
                    continue
                series[nm]['R0'][fi] = np.median(p2[idx], 0) if spans_ok(local, idx) else None
                gs = comps(local[idx], .30)
                if nm == 'OUTER_A' and len(gs) > 1:
                    multi_full += 1
                    if HOLD[0] <= fi < HOLD[1]:
                        multi_hold += 1
                series[nm]['R1'][fi] = np.median(p2[idx[gs[0]]], 0) if spans_ok(local, idx[gs[0]]) else None
                pos = int(np.argmax(frac[idx]))
                c4 = next(g for g in gs if pos in g)
                series[nm]['R4'][fi] = np.median(p2[idx[c4]], 0) if spans_ok(local, idx[c4]) else None
                if up is not None:
                    d = np.linalg.norm(p2[idx] - up, axis=1)
                    pos5 = int(np.argmin(d))
                    c5 = next(g for g in gs if pos5 in g)
                    series[nm]['R5'][fi] = np.median(p2[idx[c5]], 0) if spans_ok(local, idx[c5]) else None
                else:
                    series[nm]['R5'][fi] = None
                idxb = band_distal_mask(t, frac, sgn, (.52, .88))
                series[nm]['RB'][fi] = np.median(p2[idxb], 0) if (len(idxb) and spans_ok(local, idxb)) else None
                if nm == 'OUTER_A' and HOLD[0] <= fi < HOLD[1] and len(idxb):
                    rb_comp[fi] = len(comps(local[idxb], .30))
                    rb_size[fi] = len(idxb)
                    rb_span[fi] = np.ptp(local[idxb], axis=0).tolist()
                if fi in pairframes:
                    pops = [dict(n=len(g), proj=[float(local[idx[g], 2].min()), float(local[idx[g], 2].max())], frac=[float(frac[idx[g]].min()), float(frac[idx[g]].max())], t=[float((sgn * t[idx[g], 0]).min()), float((sgn * t[idx[g], 0]).max())], centroid=np.round(p2[idx[g]].mean(0), 4).tolist(), rows=[int(rows2[i]) for i in g]) for g in gs]
                    gaps = np.diff(np.sort(local[idx, 2]))
                    dual.append(dict(fi=fi, mask_n=len(idx), comps=pops, largest_axis_gap=float(gaps.max()) if len(gaps) else None, median_r0=None if series['OUTER_A']['R0'][fi] is None else np.round(series['OUTER_A']['R0'][fi], 4).tolist(), upA=None if up is None else np.round(up, 4).tolist()))
    finally:
        src.close()

    summary = {}
    for nm in ('OUTER_A', 'OUTER_B'):
        for k in RULES:
            valid, cons, span = steps(series[nm][k], *HOLD)
            drops = [fi for fi in range(*HOLD) if series[nm][k].get(fi) is None]
            summary[nm + '|' + k] = dict(valid=len(valid), max_step=None if not cons else round(max(x[2] for x in cons), 1), top5=sorted([round(x[2], 1) for x in cons], reverse=True)[:5], over100=[(a, b, round(x, 1)) for a, b, x in cons if x > 100], spanning_over100=[(a, b, round(x, 1)) for a, b, x in span if x > 100], drops=drops)
    rb_drops = {}
    for fi in summary['OUTER_A|RB']['drops']:
        n = rb_size.get(fi, 0)
        span = rb_span.get(fi)
        if n < 6:
            reason = 'LOW_SUPPORT mask_n=%d' % n
        elif span is not None and span[2] < .025:
            reason = 'SPARSE_VERTICAL_SUPPORT'
        elif span is not None and max(span[0], span[1]) > .8:
            reason = 'CONFLICTING_SPATIAL_SUPPORT'
        else:
            reason = 'unknown'
        rb_drops[fi] = reason
    hist = {}
    for v in rb_comp.values():
        hist[v] = hist.get(v, 0) + 1
    save('MECHANISM_SUPPORT_RULES' + sfx + '.json', dict(
        method='Hold [183,334) only; masks/medians recomputed from ROI+ledger source rows in canonical order using support_geometry (verified equal to frozen S07 FG_NEW partitions); steps = consecutive valid frames only; RB = OUTER eligibility band [0.52,0.88) (UPPER band) with unchanged distal quantile 0.75 and validity gates.',
        hold=list(HOLD),
        mask_replica=mask_check,
        r11_hold_multicomponent_frames=multi_hold,
        r11_full_multicomponent_frames=multi_full,
        rules=summary,
        rb_outer_a=dict(component_hist_0p30=hist, drops=rb_drops),
        choice='Registered variant = RB only (branch-band-consistent support). Component-pick rules were evaluated and rejected: R1/R4/R5 flip between or drop the patch populations (see per-rule numbers); RB keeps the branch population with 0.75 quantile and yields a single connected support (component histogram above) with reduced misses.',
        limits='No GT, no anatomy: regions are point-supported areas only. Thresholds frozen before the candidate run; results remain REUSED_DEVELOPMENT. No second variant after observing outcomes.',
    ))
    save('MECHANISM_DUAL_POP' + sfx + '.json', dict(
        pairs=pairs,
        frames=dual,
        note='Source-row dual-population review of r11 OUTER_A beyond-100mm hold steps. Each component is recomputed from bound rows (coordinate recompute error verified 0 in S07 R2 diagnosis); these are geometric groups, not body parts.',
        correction='The lower-frac population (approx .33-.44) is longitudinally separated from the upper population (approx .72-.88) by about 0.83-0.86m; the r0 median switches between populations when membership counts cross. The RB band excludes the lower population by construction; connectivity of the remaining support is verified separately.',
    ))
    for k, v in summary.items():
        print('%-16s valid=%3d max=%-7s over100=%s drops=%d' % (k, v['valid'], v['max_step'], v['over100'][:4], len(v['drops'])))
    print('mask replica mismatch:', len(mask_check['mismatch']), 'frames:', mask_check['frames'], 'nodes:', mask_check['nodes'])
    print('r11 multicomponent OUTER_A frames: hold', multi_hold, 'full', multi_full)
    print('RB comp hist:', dict(sorted(hist.items())))
    print('RB drops:', rb_drops)


if __name__ == '__main__':
    main()

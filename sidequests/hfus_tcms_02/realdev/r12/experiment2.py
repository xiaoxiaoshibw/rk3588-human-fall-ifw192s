"""One official S07F candidate run for the registered branch-band variant.

Group semantics mirror the frozen r11 runner: prefix fg = foreground ledger
applied; suffix new2 = regions2 extractor. Writes only into the S07F evidence
directory; S07 artifacts are read-only inputs.
"""
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'r11'))

import numpy as np
from common2 import EV, OLD_EV, SK, save, sha, W
from experiment import source, roi, summarize  # frozen r11 helpers
import regions2 as R2
from calibrate import CalibrationLayer


def run(group):
    start = time.perf_counter()
    src = source()
    foreground = group.startswith('fg')
    assert (EV / 'REGION_PROTOCOL_V2.json').exists()
    cal = CalibrationLayer(SK.EDGES)
    records = []
    with np.load(OLD_EV / 'FOREGROUND_LEDGER.npz', allow_pickle=False) as z:
        ledger = {k: z[k] for k in z.files}
    verify = dict(frames=0, nodes=0, max_recompute_error_m=0., partition=True)
    try:
        for fi in range(386):
            f = src.frame(fi)
            p, rows = roi(f)
            sl = slice(ledger['indptr'][fi], ledger['indptr'][fi + 1])
            assert np.array_equal(rows, ledger['global_rows'][sl])
            mask = ledger['keep'][sl] if foreground else np.ones(len(p), bool)
            p = p[mask]
            rows = rows[mask]
            sk, _ = R2.estimate(p, rows.tolist(), coordinate_version='RAW/innolidar', session_id='cap_20261018_110029')
            measurements = W.skeleton_measurements(sk, SK.EDGES)
            cf = cal.update(fi, measurements)
            # Every valid node must remain reproducible from current source rows.
            byrow = {int(r): i for i, r in enumerate(rows)}
            for key, n in sk['nodes'].items():
                if not n['valid']:
                    continue
                assert all(r in byrow for r in n['support_rows'])
                ids = [byrow[r] for r in n['support_rows']]
                expected = np.median(p[ids], axis=0)
                err = float(np.max(np.abs(expected - n['xyz'])))
                assert err < 1e-10
                verify['nodes'] += 1
                verify['max_recompute_error_m'] = max(verify['max_recompute_error_m'], err)
            verify['frames'] += 1
            records.append(dict(fi=fi, t=src.times[fi], candidate_rows=len(p), valid_nodes=W.valid_nodes(sk), nodes=sk['nodes'], reason=sk['reason'], axis=sk.get('axis'), basis_lateral=sk.get('basis_lateral'), diagnostics=sk.get('diagnostics'), calibration=cf))
    finally:
        src.close()
    save(group.upper() + '_FRAMES.jsonl', ''.join(json.dumps(r, separators=(',', ':'), allow_nan=False) + '\n' for r in records))
    summary = summarize(records)
    save(group.upper() + '_SUMMARY.json', summary)
    save(group.upper() + '_CALIBRATION.json', cal.summary())
    save(group.upper() + '_VERIFY.json', dict(**verify, seconds=time.perf_counter() - start, source_sha=sha(HERE / 'experiment2.py'), extractor_sha=sha(HERE / 'regions2.py')))
    hold = summary['hold']
    print(group, 'six', hold['six_frames'], 'chest', hold['nodes']['CHEST']['raw']['valid_frames'], 'outer', hold['nodes']['OUTER_A']['raw'], flush=True)


if __name__ == '__main__':
    run(sys.argv[1])

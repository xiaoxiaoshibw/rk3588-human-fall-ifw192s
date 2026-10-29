"""E1 补充：旧入口 fit_ground_plane 的 holdout/support 门细节（OB08 根因用）。

只读复用 core.ground；输出 results/E1_OLD_ENTRY_DETAIL.json（排他写）。
"""
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / 'src/human_fall_detection'))
import source_io as sio
import core.ground as g

EVID = ROOT / 'docs/human_fall/evidence/2026-10-17_hfus_ground_obs_r1'
RESULTS = EVID / 'results'
SESSION = ROOT / 'data/sessions/cap_20261017_113516'


def main():
    t0 = time.time()
    ses = sio.Session(SESSION)
    fit_fis = [fi for fi in range(len(ses.frames)) if ses.rel_s(fi) < 20.0]
    agg = np.concatenate([ses.xyz(fi)[sio.validity(ses.xyz(fi))[1]] for fi in fit_fis if fi % 5 == 0])
    if len(agg) > 200000:
        agg = agg[::int(np.ceil(len(agg) / 200000))]
    cases = [(f'fi{fi}', ses.xyz(fi)[sio.validity(ses.xyz(fi))[1]]) for fi in (20, 100, 180)] + [('aggregate_fit_stride', agg)]
    runs = []
    for name, pts in cases:
        res = g.fit_ground_plane(pts)
        runs.append(dict(case=name, status=res['status'], reason=res['reason'],
                         normal=res['normal'], offset_m=res['offset_m'], tilt_rad=res['tilt_rad'],
                         inlier_fraction=res['inlier_fraction'], fit_residual=res.get('fit_residual'),
                         holdout_residual=res['holdout_residual'], holdout_support=res['holdout_support'],
                         settings=res['settings']))
    out = dict(item='HFUS-GROUND-OBSERVABILITY-RD-01', measurement='E1_OLD_ENTRY_DETAIL',
               argv=sys.argv, wall_s=round(time.time() - t0, 2),
               note='复现旧入口 holdout 门细节；只读复用 core.ground.fit_ground_plane；不改旧门、不翻旧 FAIL',
               runs=runs)
    sio.write_new(RESULTS / 'E1_OLD_ENTRY_DETAIL.json', out)
    for r in runs:
        print(r['case'], r['status'], r['reason'], 'holdout_support=', r['holdout_support'])


if __name__ == '__main__':
    main()

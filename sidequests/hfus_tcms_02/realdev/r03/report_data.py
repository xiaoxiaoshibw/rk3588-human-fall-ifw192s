"""Collect report numbers: plane deltas, patch purity, denominators."""
import json, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
from s2core import load_source, OUT, ROOT, load, sha, write, validity, roles

if __name__ == '__main__':
    base = OUT / 'full_r1'
    cand = load(base / 'CANDIDATES.json')
    dom = load(OUT / 'audit/AUDIT_DOMAINS_V4.json')
    hist = load(ROOT / 'data/leveled/61cb6976b0f8479394641850d9a7c6ca/tls/transform.json')
    R = np.asarray(hist['R']); t = np.asarray(hist['t'])
    src, times = load_source()
    fit, val, pre = roles(times)
    by = {c['id']: c for c in cand}
    old = by['OLD_TLS']; best = by['C3D_03']; d2 = by['DIMG_01']

    def delta(a, b):
        na, nb = np.asarray(a['n']), np.asarray(b['n'])
        ang = float(np.degrees(np.arccos(np.clip(abs(na @ nb), -1, 1))))
        return dict(normal_deg=ang, offset_m=float(abs(abs(a['d']) - abs(b['d']))))

    purity = {}
    for pt in dom['patches']:
        u0, u1, v0, v1 = pt['rect_uv']
        hs = []
        for fi in fit[::5]:
            p = src.frame(fi)['xyz']; ok = validity(p)[1]
            loc = p[ok] @ R.T + t
            m = ((loc[:, 0] >= u0) & (loc[:, 0] < u1) & (loc[:, 1] >= v0) & (loc[:, 1] < v1) & (np.abs(loc[:, 2]) <= 0.15))
            hs.append(loc[m, 2])
        h = np.concatenate(hs)
        purity[pt['id']] = dict(count=int(len(h)), median_h=float(np.median(h)),
                                frac_within_3cm_of_peak=float(np.mean(np.abs(h + 0.03) <= 0.03)))
    summary = load(base / 'SUMMARY.json')
    out = dict(best_vs_old=delta(best, old), d_img_vs_old=delta(d2, old), c_vs_d=delta(best, d2),
               planes={k: dict(n=by[k]['n'], d=by[k]['d'], fit_pass=by[k]['fit_pass'], val_pass=by[k]['val_pass']) for k in by},
               purity=purity, seconds=summary['seconds'], peak_rss=summary['peak_rss'],
               distance=summary['distance'], output_bytes=summary['output_bytes'])
    write(OUT / 'REPORT_DATA.json', out)
    print(json.dumps(out, indent=1)[:3000])
    src.close()

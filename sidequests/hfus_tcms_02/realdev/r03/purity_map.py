"""FIT-only floor-purity map to place audit domains v3 (prior-conditioned, disclosed)."""
import sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
from s2core import load_source, OUT, ROOT, load, validity

if __name__ == '__main__':
    hist = load(ROOT / 'data/leveled/61cb6976b0f8479394641850d9a7c6ca/tls/transform.json')
    R = np.asarray(hist['R']); t = np.asarray(hist['t'])
    src, times = load_source()
    fit = [i for i, x in enumerate(times) if x < 20][::3]
    pts = []
    for fi in fit:
        p = src.frame(fi)['xyz']; ok = validity(p)[1]
        loc = p[ok] @ R.T + t
        m = (np.abs(loc[:, 2]) <= 0.15) & (loc[:, 0] > 0) & (loc[:, 0] < 3) & (loc[:, 1] > -1.2) & (loc[:, 1] < 2.4)
        pts.append(loc[m, :3])
    q = np.concatenate(pts)
    us = np.arange(0.2, 2.81, 0.2); vs = np.arange(-1.0, 2.21, 0.2)
    print('u\\v ' + ' '.join('%5.1f' % v for v in vs))
    for u0 in us[:-1]:
        row = []
        for v0 in vs[:-1]:
            m = (q[:, 0] >= u0) & (q[:, 0] < u0 + 0.2) & (q[:, 1] >= v0) & (q[:, 1] < v0 + 0.2)
            n = int(m.sum())
            if n < 100:
                row.append('  .  ')
            else:
                f = np.mean(np.abs(q[m, 2] + 0.03) <= 0.03)
                row.append('%5.2f' % f)
        print('%4.1f ' % u0 + ' '.join(row))

"""Inspect thin-slab patches: h distribution, contamination, per-patch plane hints."""
import sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
from s2core import load_source, OUT, ROOT, load, validity, write_png

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

if __name__ == '__main__':
    dom = load(OUT / 'audit/AUDIT_DOMAINS_V2.json')
    hist = load(ROOT / 'data/leveled/61cb6976b0f8479394641850d9a7c6ca/tls/transform.json')
    R = np.asarray(hist['R']); t = np.asarray(hist['t'])
    src, times = load_source()
    fit = [i for i, x in enumerate(times) if x < 20]
    fig, axs = plt.subplots(2, 4, figsize=(16, 7), constrained_layout=True)
    for ax, patch in zip(axs.ravel(), dom['patches']):
        u0, u1, v0, v1 = patch['rect_uv']
        hs = []
        for fi in fit[::4]:
            p = src.frame(fi)['xyz']
            ok = validity(p)[1]
            loc = p[ok] @ R.T + t
            m = ((loc[:, 0] >= u0) & (loc[:, 0] < u1) & (loc[:, 1] >= v0) & (loc[:, 1] < v1)
                 & (np.abs(loc[:, 2]) <= 0.15))
            hs.append(loc[m, 2])
        h = np.concatenate(hs)
        ax.hist(h, bins=120, range=(-0.15, 0.15))
        ax.set_title('%s n=%d med=%.3f f|h|<3cm=%.2f' % (patch['id'], len(h), np.median(h), np.mean(np.abs(h) < 0.03)))
        ax.set_xlabel('h (m)')
    axs.ravel()[-1].axis('off')
    write_png(OUT / 'audit/patch_h.png', fig)
    plt.close(fig)
    print('ok')

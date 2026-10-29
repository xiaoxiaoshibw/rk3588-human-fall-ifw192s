"""FIT-only local-frame orientation renders. View frame only; no fitting, no patch selection."""
import json
import sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
from s2core import load_source, OUT, write_png, ROOT, load

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def gather(source, frames, stride=30):
    parts = [source.frame(fi)['xyz'][::stride] for fi in frames]
    p = np.concatenate(parts)
    ok = np.isfinite(p).all(axis=1) & np.any(p != 0, axis=1)
    return p[ok]


if __name__ == '__main__':
    src, times = load_source()
    fit = [fi for fi, t in enumerate(times) if t < 20.0]
    q = gather(src, fit)
    old = load(ROOT / 'data/leveled/61cb6976b0f8479394641850d9a7c6ca/tls/transform.json')
    R = np.asarray(old['R'], dtype=float); t = np.asarray(old['t'], dtype=float)
    print('det', np.linalg.det(R), 'R@n+t', R @ (np.asarray(old['R'], dtype=float)[2]))
    loc = q @ R.T + t
    print('local percentiles u,v,h')
    for a, name in enumerate('uvh'):
        print(name, np.percentile(loc[:, a], [0, 1, 5, 25, 50, 75, 95, 99, 100]).round(3))
    d = OUT / 'audit'
    fig, ax = plt.subplots(1, 3, figsize=(19, 6), constrained_layout=True)
    m = np.hypot(loc[:, 0], loc[:, 1]) < 12
    hb = ax[0].hexbin(loc[m, 0], loc[m, 1], C=loc[m, 2], gridsize=220, cmap='turbo',
                      vmin=-0.5, vmax=2.0, reduce_C_function=np.median)
    ax[0].set_title('FIT local top view, color=median h (m)')
    ax[0].set_xlabel('u (m)'); ax[0].set_ylabel('v (m)'); ax[0].set_aspect('equal')
    fig.colorbar(hb, ax=ax[0], shrink=0.75)
    near = np.hypot(loc[:, 0], loc[:, 1]) < 8
    ax[1].hist(loc[near, 2], bins=400, range=(-3, 6))
    ax[1].set_yscale('log'); ax[1].set_xlabel('h = n.p + d (m)'); ax[1].set_title('FIT h histogram (r<8m)')
    sub = loc[np.random.default_rng(7).choice(len(loc), size=min(120000, len(loc)), replace=False)]
    ax2 = fig.add_subplot(1, 3, 3, projection='3d')
    ax2.scatter(sub[:, 0], sub[:, 1], sub[:, 2], s=0.15, c=sub[:, 2], cmap='turbo', vmin=-1, vmax=3, linewidths=0)
    ax2.set_xlabel('u'); ax2.set_ylabel('v'); ax2.set_zlabel('h'); ax2.set_title('FIT local 3D')
    ax2.set_box_aspect((2, 2, 1))
    write_png(d / 'fit_local.png', fig); plt.close(fig)
    print('ok')

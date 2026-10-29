"""Orientation-only floor map in the historical candidate view frame (no fitting, no freeze)."""
import sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
from s2core import load_source, OUT, write_png, ROOT, load

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


if __name__ == '__main__':
    src, times = load_source()
    fit = [fi for fi, t in enumerate(times) if t < 20.0]
    q = np.concatenate([src.frame(fi)['xyz'][::20] for fi in fit])
    ok = np.isfinite(q).all(axis=1) & np.any(q != 0, axis=1)
    q = q[ok]
    old = load(ROOT / 'data/leveled/61cb6976b0f8479394641850d9a7c6ca/tls/transform.json')
    R = np.asarray(old['R'], dtype=float); t = np.asarray(old['t'], dtype=float)
    loc = q @ R.T + t
    d = OUT / 'audit'
    fig, ax = plt.subplots(1, 2, figsize=(15, 7), constrained_layout=True)
    low = loc[(loc[:, 2] > -0.06) & (loc[:, 2] < 0.12)]
    hb = ax[0].hexbin(low[:, 0], low[:, 1], gridsize=120, cmap='magma', mincnt=1)
    ax[0].set_title('FIT low band h in [-0.06,0.12] m (orientation only)')
    ax[0].set_xlabel('u (m)'); ax[0].set_ylabel('v (m)'); ax[0].set_aspect('equal')
    ax[0].set_xlim(-0.2, 6); ax[0].set_ylim(-2, 6)
    for g in np.arange(0, 6.1, 0.5):
        ax[0].axvline(g, color='w', lw=0.2, alpha=0.35); ax[0].axhline(g, color='w', lw=0.2, alpha=0.35)
    fig.colorbar(hb, ax=ax[0], shrink=0.8)
    ax[1].hexbin(loc[:, 0], loc[:, 2], gridsize=160, cmap='magma', mincnt=1)
    ax[1].set_title('FIT u-h side (all h)'); ax[1].set_xlabel('u (m)'); ax[1].set_ylabel('h (m)')
    ax[1].set_xlim(-0.2, 6); ax[1].set_ylim(-1, 4)
    write_png(d / 'fit_floor_map.png', fig); plt.close(fig)
    for name, a, b in [('u', 0, 1), ('v', 1, 2)]:
        pass
    print('low band points', len(low))
    print('low u pct', np.percentile(low[:, 0], [0, 50, 100]))
    print('low v pct', np.percentile(low[:, 1], [0, 50, 100]))

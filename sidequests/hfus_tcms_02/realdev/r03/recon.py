"""FIT-only visual recon for ground audit domain selection. Renders, never writes data."""
import json
import sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
from s2core import load_source, OUT, write_png

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def gather(source, frames, stride=40):
    parts = []
    for fi in frames:
        f = source.frame(fi)
        p = f['xyz']
        ok = np.isfinite(p).all(axis=1) & np.any(p != 0, axis=1)
        q = p[ok]
        parts.append(q[::stride])
    return np.concatenate(parts) if parts else np.empty((0, 3))


if __name__ == '__main__':
    src, times = load_source()
    fit = [fi for fi, t in enumerate(times) if t < 20.0]
    q = gather(src, fit)
    print('fit frames', len(fit), 'sample', len(q))
    for a, name in enumerate('xyz'):
        print(name, np.percentile(q[:, a], [0, 1, 5, 50, 95, 99, 100]).round(3))
    d = OUT / 'audit'
    d.mkdir(exist_ok=True)
    fig, ax = plt.subplots(1, 3, figsize=(18, 6), constrained_layout=True)
    for i, (a, b) in enumerate([(0, 1), (0, 2), (1, 2)]):
        ax[i].scatter(q[:, a], q[:, b], s=0.2, c=q[:, 2], cmap='viridis', alpha=0.3, linewidths=0)
        ax[i].set_xlabel('xyz'[a]); ax[i].set_ylabel('xyz'[b]); ax[i].set_aspect('equal')
        ax[i].set_title('FIT [0,20)s ' + 'xyz'[a] + 'xyz'[b])
    fig.colorbar(ax[0].collections[0], ax=ax, label='raw z (m)', shrink=0.8)
    write_png(d / 'fit_overview.png', fig)
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(6, 4), constrained_layout=True)
    ax.hist(q[:, 2], bins=200)
    ax.set_yscale('log'); ax.set_xlabel('raw z (m)'); ax.set_ylabel('count')
    write_png(d / 'fit_z_hist.png', fig); plt.close(fig)
    print('rendered to', d)

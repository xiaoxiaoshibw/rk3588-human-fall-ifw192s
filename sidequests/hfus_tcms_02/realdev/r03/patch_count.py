"""Candidate audit rectangles: count valid rows per patch before freezing."""
import sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parent))
from s2core import load_source, ROOT, load

PATCHES = [
 ('FIT_A', .40, 1.15, -.90, .00), ('FIT_B', 1.25, 2.00, -.90, .00),
 ('FIT_C', .40, 1.15, .10, 1.00), ('FIT_D', 1.25, 2.00, .10, 1.00),
 ('VAL_E', .40, 1.15, 1.10, 1.95), ('VAL_F', 1.25, 2.00, 1.10, 1.95),
 ('VAL_G', 2.10, 2.55, -.90, 1.00)]

if __name__ == '__main__':
    src, times = load_source()
    old = load(ROOT / 'data/leveled/61cb6976b0f8479394641850d9a7c6ca/tls/transform.json')
    R = np.asarray(old['R']); t = np.asarray(old['t'])
    fit = [i for i, x in enumerate(times) if x < 20]
    val = [i for i, x in enumerate(times) if 20 <= x < 28]
    for name, u0, u1, v0, v1 in PATCHES:
        frames = fit if name.startswith('FIT') else val
        counts = []
        for fi in frames[::10]:
            p = src.frame(fi)['xyz']; ok = np.isfinite(p).all(1) & np.any(p != 0, 1)
            q = (p[ok] @ R.T + t)[:, :2]
            m = (q[:, 0] >= u0) & (q[:, 0] < u1) & (q[:, 1] >= v0) & (q[:, 1] < v1)
            counts.append(int(m.sum()))
        print(name, 'frames', len(frames), 'sampled', len(counts), 'per-frame min/med/max',
              min(counts) if counts else None, int(np.median(counts)) if counts else None, max(counts) if counts else None)

"""Region-support geometry helpers for S07F (read-only, no state).

Replicates the frozen r11 extractor's per-frame intermediates exactly
(verified equal against the S07 FG_NEW partitions) and provides the
branch-band variant used by regions2.
"""
import numpy as np
from scipy.spatial import cKDTree
from common2 import SK

CENTRAL_BANDS = [(.88, 1.03), (.70, .88), (.52, .70), (.33, .52), (-.03, .33)]


def prep(p, rows):
    """Canonical row order + r11 principal-plane intermediates."""
    rows = np.asarray(rows)
    order = np.argsort(rows, kind='stable')
    p = p[order]
    rows = rows[order]
    center = np.mean(p, 0)
    values, vectors = np.linalg.eigh(np.cov((p - center).T))
    axis = vectors[:, -1].copy()
    if axis[2] < 0:
        axis = -axis
    lateral = vectors[:, -2].copy()
    if lateral[np.argmax(np.abs(lateral))] < 0:
        lateral = -lateral
    depth = np.cross(lateral, axis)
    basis = np.column_stack([lateral, depth, axis])
    local = (p - center) @ basis
    lo, hi = np.quantile(local[:, 2], [.02, .98])
    frac = (local[:, 2] - lo) / (hi - lo)
    return p, rows, local, frac


def transverse_local(local, frac):
    """Core-subtracted transverse coordinate (r11 semantics)."""
    mid = (frac >= .33) & (frac < .70)
    core = float(np.median(local[mid, 0]))
    t = local.copy()
    t[:, 0] = local[:, 0] - core
    return t


def r11_masks(local, frac):
    """Exact r11 region masks (OUTER band [.33,.88))."""
    t = transverse_local(local, frac)
    out = {}
    for name, (low, high) in zip(SK.SLOTS[:5], CENTRAL_BANDS):
        out[name] = np.flatnonzero((frac >= low) & (frac < high) & (np.abs(t[:, 0]) <= .18))
    for label, sign in [('A', -1), ('B', 1)]:
        out['UPPER_' + label] = np.flatnonzero((sign * t[:, 0] > .18) & (frac >= .52) & (frac < .88))
        out['OUTER_' + label] = band_distal_mask(t, frac, sign, (.33, .88))
        out['LOWER_' + label] = np.flatnonzero((sign * t[:, 0] > .18) & (frac >= .12) & (frac < .33))
        out['END_' + label] = np.flatnonzero((sign * t[:, 0] > .18) & (frac >= -.03) & (frac < .12))
    return out, t


def band_distal_mask(t, frac, sign, band, q=.75):
    """Side/band eligibility + distal transverse quantile (r11 method, band param)."""
    elig = (sign * t[:, 0] > .18) & (frac >= band[0]) & (frac < band[1])
    if not elig.any():
        return np.array([], dtype=int)
    dq = float(np.quantile(sign * t[elig, 0], q))
    return np.flatnonzero(elig & (sign * t[:, 0] >= dq))


def comps(points, T):
    """Single-linkage connected components (largest first, stable tie-break)."""
    n = len(points)
    if n == 0:
        return []
    if n == 1:
        return [np.array([0])]
    pairs = cKDTree(points).query_pairs(T, output_type='ndarray')
    par = list(range(n))

    def find(a):
        while par[a] != a:
            par[a] = par[par[a]]
            a = par[a]
        return a

    for a, b in pairs:
        ra, rb = find(int(a)), find(int(b))
        if ra != rb:
            par[ra] = rb
    groups = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)
    return [np.asarray(g, dtype=int) for g in sorted(groups.values(), key=lambda g: (-len(g), int(g[0])))]


def spans_ok(local, idx):
    """G.observe validity replica on local coordinates (points/axis-span/xy-span)."""
    if len(idx) < 6:
        return False
    span = np.ptp(local[idx], axis=0)
    return span[2] >= .025 and max(span[0], span[1]) <= .8

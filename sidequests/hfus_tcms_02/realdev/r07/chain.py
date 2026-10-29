"""HFUS-HUMAN-SKELETON-01 v2: observable-segment model and robust measurement (no pose optimisation).

Measured and calibrated quantities are exactly the ones a single-view body-plane point cloud can
support: trunk length, four limb pairs (upper/fore arm, thigh/shin) and two widths. Segment
separation inside a limb needs a real bend, so the synthetic scenarios use joint angles >= 25 deg
and the reporting keeps a per-segment observability flag.
"""
import sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import s5core as C

TRUNK_HALF_WIDTH = 0.07      # registered seed: trunk core band (limbs sit at |v| >= 0.1)
LIMB_GAP = 0.09              # registered seed: lateral gap that separates a limb from the trunk
SEGMENTS = ['TRUNK', 'UPPER_ARM_L', 'FOREARM_L', 'UPPER_ARM_R', 'FOREARM_R',
            'THIGH_L', 'SHIN_L', 'THIGH_R', 'SHIN_R']
WIDTHS = ['SHOULDER_W', 'HIP_W']
SEED = dict(TRUNK=0.70, UPPER_ARM_L=0.30, FOREARM_L=0.26, UPPER_ARM_R=0.30, FOREARM_R=0.26,
            THIGH_L=0.42, SHIN_L=0.42, THIGH_R=0.42, SHIN_R=0.42,
            SHOULDER_W=0.36, HIP_W=0.30)


def percentile_span(a, lo=2, hi=98):
    if len(a) < 5:
        return None
    p = np.percentile(a, [lo, hi])
    return float(p[1] - p[0])


def frame_axes(uv):
    """Body frame: u along the body, head side chosen where the lateral spread is smallest."""
    c = np.median(uv, axis=0)
    q = uv - c
    w, v = np.linalg.eigh(np.cov(q.T) + np.eye(2) * 1e-12)
    axis = v[:, -1]
    lat = v[:, 0]
    best = None
    for s in (1.0, -1.0):
        u = q @ (axis * s)
        vv = q @ lat
        top = np.abs(vv[u > np.percentile(u, 80)])
        score = float(np.percentile(top, 90)) if len(top) > 5 else 9.9
        if best is None or score < best[0]:
            best = (score, u, vv, axis * s)
    return best[1], best[2], best[3], lat


def two_segment(uv_body, min_frac=0.25):
    """Best breakpoint for a bent limb in body-frame coordinates.

    Returns the proximal (closer to the trunk, higher body-u) and distal lengths measured along each
    part's own principal direction, minus twice the median cross-section radius.
    """
    if len(uv_body) < 40:
        return None
    order = np.argsort(-uv_body[:, 0])          # proximal first (higher body-u)
    loc = uv_body[order]
    n = len(loc)
    best = None
    for frac in np.linspace(min_frac, 1 - min_frac, 19):
        k = int(frac * n)
        prox, dist = loc[:k], loc[k:]
        if len(prox) < 20 or len(dist) < 20:
            continue
        res = 0.0
        lens, radii = [], []
        for part in (prox, dist):
            pc = part - part.mean(axis=0)
            w, vec = np.linalg.eigh(np.cov(pc.T) + np.eye(2) * 1e-12)
            d = vec[:, -1]
            t = pc @ d
            perp = np.abs(pc @ vec[:, 0])
            res += float(np.median(perp) * len(part))
            lens.append(percentile_span(t))
            radii.append(float(np.median(perp)))
        if any(x is None for x in lens):
            continue
        score = res / n
        if best is None or score < best[0]:
            best = (score, lens[0] - 2 * radii[0], lens[1] - 2 * radii[1], radii[0], radii[1])
    if best is None:
        return None
    return dict(proximal=max(best[1], 0.02), distal=max(best[2], 0.02), radius_proximal=best[3],
                radius_distal=best[4], residual=best[0])


def trunk_ridge(uv, bins=26, band=0.06, centre_max=0.08):
    """Per-u-bin density mode; the trunk is the longest run whose mode stays central.

    This replaces the global |v| band, which the PCA skew of the limbs made unreliable.
    """
    u, v, axis, lat = frame_axes(uv)
    lo, hi = np.percentile(u, [1, 99])
    edges = np.linspace(lo, hi, bins + 1)
    rows = []
    for i in range(bins):
        m = (u >= edges[i]) & (u < edges[i + 1])
        if m.sum() < 25:
            rows.append(None)
            continue
        vv = v[m]
        span = np.percentile(vv, [2, 98])
        if span[1] - span[0] < 0.03:
            rows.append(None)
            continue
        h, e = np.histogram(vv, bins=20, range=(span[0], span[1]))
        k = int(np.argmax(h))
        c = 0.5 * (e[k] + e[k + 1])
        near = np.abs(vv - c) <= band
        width = float(np.percentile(np.abs(vv[near] - c), 75)) if near.sum() > 12 else None
        rows.append(dict(i=i, u0=edges[i], u1=edges[i + 1], c=float(c), width=width,
                         n=int(m.sum()), n_near=int(near.sum())))
    # longest run of consecutive central bins
    best, run = [], []
    for r in rows:
        if r is not None and abs(r['c']) <= centre_max:
            run.append(r)
        else:
            if len(run) > len(best):
                best = run
            run = []
    if len(run) > len(best):
        best = run
    if len(best) < 3:
        return None
    w = [r['width'] for r in best if r['width'] is not None]
    if not w:
        return None
    radius = float(np.median(w))
    extent = float(best[-1]['u1'] - best[0]['u0'])
    return dict(length=extent - 2 * radius, radius=radius, u0=float(best[0]['u0']),
                u1=float(best[-1]['u1']), bins=len(best), centres=[r['c'] for r in best],
                u=u, v=v, axis=axis)


def measure(uv):
    """Per-frame measurement of the observable segments and widths. Returns dict + diagnostics."""
    u, v, axis, lat = frame_axes(uv)
    trunk = np.abs(v) <= TRUNK_HALF_WIDTH
    out, diag = {}, dict(points=len(uv), trunk=trunk.tolist()[:0])
    if trunk.sum() < 60:
        return {}, dict(reason='NO_TRUNK', points=len(uv))
    ut = u[trunk]
    vt = v[trunk]
    lo, hi = np.percentile(ut, [2, 98])
    r_trunk = float(np.median(np.abs(vt)))
    trunk_len = float(hi - lo - 2 * r_trunk)
    if trunk_len <= 0.05:
        return {}, dict(reason='TRUNK_TOO_SHORT', points=len(uv))
    out['TRUNK'] = trunk_len
    # widths at the shoulder and hip heights
    span = hi - lo
    for name, frac in [('SHOULDER_W', 0.85), ('HIP_W', 0.15)]:
        band = np.abs(u - (lo + frac * span)) <= 0.06
        if band.sum() >= 40:
            w = percentile_span(v[band])
            if w:
                out[name] = float(w)
    # limbs: quadrants relative to the trunk
    upper = u > lo + 0.70 * span
    lower = u < lo + 0.30 * span
    for side, sign in [('L', 1.0), ('R', -1.0)]:
        arm = upper & (sign * v > LIMB_GAP)
        leg = lower & (sign * v > LIMB_GAP)
        r_arm = two_segment(np.column_stack([u[arm], v[arm]]))
        if r_arm:
            out['UPPER_ARM_' + side] = r_arm['proximal']
            out['FOREARM_' + side] = r_arm['distal']
            diag['arm_' + side] = r_arm
        r_leg = two_segment(np.column_stack([u[leg], v[leg]]))
        if r_leg:
            out['THIGH_' + side] = r_leg['proximal']
            out['SHIN_' + side] = r_leg['distal']
            diag['leg_' + side] = r_leg
    diag['trunk_radius'] = r_trunk
    diag['trunk_span'] = float(span)
    diag['axis'] = axis.tolist()
    return out, diag


class Calibrator:
    """Per-segment online mean/variance with an explicit state machine (no labels, no truth)."""

    def __init__(self, seed, min_samples=12, window=15, calib_rel_std=0.03, drift=(0.6, 1.7)):
        self.seg = {k: dict(mean=float(v), n=0, history=[], state='COLLECTING', resets=0, last_update=None)
                    for k, v in seed.items()}
        self.min_samples, self.window = min_samples, window
        self.calib_rel_std, self.drift = calib_rel_std, drift
        self.log = []

    def update(self, frame, measured):
        for name, value in measured.items():
            if name not in self.seg:
                continue
            s = self.seg[name]
            if s['n'] >= self.min_samples and s['mean'] > 1e-6:
                ratio = value / s['mean']
                if ratio < self.drift[0] or ratio > self.drift[1]:
                    self.log.append(dict(frame=frame, segment=name, event='DRIFT_RESET', ratio=ratio,
                                         value=value, mean=s['mean'], n=s['n']))
                    s.update(mean=float(value), n=1, history=[float(value)], state='COLLECTING',
                             resets=s['resets'] + 1)
                    continue
            s['n'] += 1
            s['mean'] += (value - s['mean']) / s['n']
            s['history'].append(float(value))
            if len(s['history']) > self.window:
                s['history'].pop(0)
            s['last_update'] = frame
            hist = np.asarray(s['history'])
            if s['n'] < self.min_samples:
                s['state'] = 'COLLECTING'
            else:
                rel = float(np.std(hist) / max(s['mean'], 1e-9)) if len(hist) >= 5 else 1.0
                s['state'] = 'CALIBRATED' if (len(hist) >= self.window and rel <= self.calib_rel_std) else 'CALIBRATING'
        return self.snapshot()

    def snapshot(self):
        return {k: dict(mean=float(v['mean']), std=float(np.std(v['history'])) if v['history'] else None,
                        n=v['n'], state=v['state'], resets=v['resets'], last_update=v['last_update'])
                for k, v in self.seg.items()}

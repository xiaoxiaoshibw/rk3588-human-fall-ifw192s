"""Skeleton fitting and continuous segment-length calibration (geometry only, no labels, no truth).

Per frame: alternate (a) assignment of body-plane points to bones, (b) a linear least-squares solve
for all joint positions with a weak segment-length prior. The calibration then reads the *fitted*
joint distances as measurements, so lengths are observable rather than assumed.
"""
import sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import body as B

SEG_INDEX = {name: i for i, (name, _, _) in enumerate(B.TOPOLOGY)}
JOINT_INDEX = {n: i for i, n in enumerate(B.JOINTS)}


def to_plane(points):
    """Principal-axis projection; returns 2D points and the 2D->3D frame for reporting."""
    p = np.asarray(points, dtype=float).reshape(-1, 3)
    c = p.mean(axis=0)
    q = p - c
    w, v = np.linalg.eigh(np.cov(q.T) + np.eye(3) * 1e-12)
    axis = v[:, -1]
    if axis[2] < 0:
        axis = -axis
    lateral = np.cross([0.0, 0.0, 1.0], axis)
    if np.linalg.norm(lateral) < 1e-6:
        lateral = np.cross([1.0, 0.0, 0.0], axis)
    lateral /= np.linalg.norm(lateral)
    depth = np.cross(axis, lateral)
    return q @ np.column_stack([axis, lateral]), (c, axis, lateral, depth)


def init_joints(uv, lengths):
    """Seed pose from the point extent: pelvis near the low end of the long axis."""
    lo = np.percentile(uv, 2, axis=0)
    hi = np.percentile(uv, 98, axis=0)
    span = float(max(np.linalg.norm(hi - lo), 0.4))
    total = lengths['SPINE'] + lengths['CHEST_HEAD'] + lengths['THIGH_L'] + lengths['SHIN_L']
    s = span / max(total, 1e-6)
    L = {k: v * s for k, v in lengths.items()}
    c = np.median(uv, axis=0)
    up = np.array([1.0, 0.0])
    lat = np.array([0.0, 1.0])
    J = {}
    J['PELVIS'] = c - up * (L['SPINE'] * 0.25)
    J['CHEST'] = J['PELVIS'] + up * L['SPINE']
    J['HEAD'] = J['CHEST'] + up * L['CHEST_HEAD']
    J['SHOULDER_C'] = J['CHEST']
    J['HIP_C'] = J['PELVIS']
    for side, sign in [('L', 1.0), ('R', -1.0)]:
        J['SHOULDER_' + side] = J['CHEST'] + sign * L['SHOULDER_SPAN'] / 2 * lat
        J['ELBOW_' + side] = J['SHOULDER_' + side] - up * L['UPPER_ARM_' + side]
        J['WRIST_' + side] = J['ELBOW_' + side] - up * L['FOREARM_' + side]
        J['HIP_' + side] = J['PELVIS'] + sign * L['HIP_SPAN'] / 2 * lat
        J['KNEE_' + side] = J['HIP_' + side] - up * L['THIGH_' + side]
        J['ANKLE_' + side] = J['KNEE_' + side] - up * L['SHIN_' + side]
    return np.array([J[n] for n in B.JOINTS])


def bone_dirs(J):
    d = []
    for name, a, b in B.TOPOLOGY:
        v = J[JOINT_INDEX[b]] - J[JOINT_INDEX[a]]
        n = np.linalg.norm(v)
        d.append(v / n if n > 1e-9 else np.array([1.0, 0.0]))
    return np.array(d)


def assign(uv, J, dirs):
    """Nearest bone (by distance to the finite segment) for every point."""
    best = np.full(len(uv), -1)
    bestd = np.full(len(uv), np.inf)
    for i, (name, a, b) in enumerate(B.TOPOLOGY):
        pa, pb = J[JOINT_INDEX[a]], J[JOINT_INDEX[b]]
        ab = pb - pa
        L2 = max(float(ab @ ab), 1e-12)
        t = np.clip(((uv - pa) @ ab) / L2, 0.0, 1.0)
        proj = pa + t[:, None] * ab
        d = np.linalg.norm(uv - proj, axis=1)
        m = d < bestd
        best[m] = i
        bestd[m] = d[m]
    return best, bestd


def solve(uv, assigned, J, dirs, lengths, lam=1.5, damp=0.10):
    """Linear least squares over joint positions.

    Point rows of one bone are normalised to unit total weight so a dense trunk cannot outvote a
    sparse wrist; the segment-length prior then has comparable weight and small bones stay bounded.
    """
    nj = len(B.JOINTS)
    rows, rhs = [], []
    count = np.bincount(assigned[assigned >= 0], minlength=len(B.TOPOLOGY))
    for i, (name, a, b) in enumerate(B.TOPOLOGY):
        m = assigned == i
        pts = uv[m]
        if not len(pts):
            continue
        d = dirs[i]
        P = np.eye(2) - np.outer(d, d)
        ia, ib = JOINT_INDEX[a], JOINT_INDEX[b]
        scale = 1.0 / np.sqrt(2.0 * len(pts))
        block = np.zeros((2 * len(pts), 2 * nj))
        rhs_block = np.empty(2 * len(pts))
        for k, p in enumerate(pts):
            block[2 * k, 2 * ia:2 * ia + 2] = -P[0]
            block[2 * k + 1, 2 * ia:2 * ia + 2] = -P[1]
            rhs_block[2 * k] = -(P[0] @ p)
            rhs_block[2 * k + 1] = -(P[1] @ p)
        rows.append(block * scale)
        rhs.append(rhs_block * scale)
        row = np.zeros(2 * nj)
        row[2 * ia:2 * ia + 2] = -d
        row[2 * ib:2 * ib + 2] = d
        rows.append((row * lam)[None, :])
        rhs.append(np.array([lengths[name] * lam]))
    damp_rows = np.zeros((2 * nj, 2 * nj))
    for j in range(nj):
        damp_rows[2 * j, 2 * j] = damp
        damp_rows[2 * j + 1, 2 * j + 1] = damp
    rows.append(damp_rows)
    rhs.append((damp * J).ravel())
    A = np.vstack(rows)
    b = np.concatenate(rhs)
    sol, *_ = np.linalg.lstsq(A, b, rcond=None)
    new = sol.reshape(nj, 2)
    far = np.linalg.norm(new - J, axis=1) > 0.6
    new[far] = J[far]
    return new


def fit(uv, lengths, iters=10, lam=1.0):
    """Two orientation hypotheses (axis sign), keep the better one."""
    best = None
    for flip in (1.0, -1.0):
        p = uv * np.array([flip, 1.0])
        J = init_joints(p, lengths)
        for _ in range(iters):
            dirs = bone_dirs(J)
            assigned, dist = assign(p, J, dirs)
            J = solve(p, assigned, J, dirs, lengths, lam=lam)
        dirs = bone_dirs(J)
        assigned, dist = assign(p, J, dirs)
        keep = dist <= 0.25
        resid = float(np.median(dist[keep])) if keep.any() else float('inf')
        if best is None or resid < best['resid']:
            best = dict(J=J * np.array([flip, 1.0]), assigned=assigned, dist=dist, resid=resid,
                        support=np.bincount(assigned[keep], minlength=len(B.TOPOLOGY)), flip=flip)
    return best


def measure(J, uv=None, assigned=None, min_support=40, support=None):
    """Per-frame length measurement from the data, not from the prior.

    Inside each bone's assigned point set the axial extent (2-98 percentile) is the capsule length
    plus two end radii; the median perpendicular distance estimates that radius, so the measurement
    is span - 2*radius. Without points for a bone the fitted joint distance is used and flagged.
    """
    out = {}
    for i, (name, a, b) in enumerate(B.TOPOLOGY):
        if support is not None and support[i] < min_support:
            continue
        span_measure = None
        if uv is not None and assigned is not None:
            pts = uv[assigned == i]
            if len(pts) >= min_support:
                pa, pb = J[JOINT_INDEX[a]], J[JOINT_INDEX[b]]
                d = pb - pa
                n = np.linalg.norm(d)
                if n > 1e-9:
                    d = d / n
                    t = (pts - pa) @ d
                    lo, hi = np.percentile(t, [2, 98])
                    perp = np.linalg.norm(pts - pa - np.outer(t, d), axis=1)
                    radius = float(np.median(perp))
                    span_measure = float(hi - lo - 2.0 * radius)
        if span_measure is not None and span_measure > 0.02:
            out[name] = span_measure
        else:
            out[name] = float(np.linalg.norm(J[JOINT_INDEX[b]] - J[JOINT_INDEX[a]]))
    return out


class Calibrator:
    """Per-segment online mean/variance with an explicit state machine (no labels, no truth)."""

    def __init__(self, seed, min_samples=15, window=20, calib_rel_std=0.02, drift=(0.7, 1.4)):
        self.seg = {k: dict(mean=float(v), m2=0.0, n=0, history=[], state='COLLECTING',
                            resets=0, last_update=None) for k, v in seed.items()}
        self.min_samples, self.window = min_samples, window
        self.calib_rel_std, self.drift = calib_rel_std, drift
        self.log = []

    def update(self, frame, measured, weight=1.0):
        for name, value in measured.items():
            s = self.seg[name]
            if s['n'] >= self.min_samples and s['mean'] > 1e-6:
                ratio = value / s['mean']
                if ratio < self.drift[0] or ratio > self.drift[1]:
                    self.log.append(dict(frame=frame, segment=name, event='DRIFT_RESET', ratio=ratio,
                                         value=value, mean=s['mean'], n=s['n']))
                    s.update(mean=float(value), m2=0.0, n=0, history=[], state='COLLECTING', resets=s['resets'] + 1)
            s['n'] += 1
            delta = value - s['mean']
            s['mean'] += weight * delta / s['n']
            s['m2'] += weight * delta * (value - s['mean'])
            s['history'].append(value)
            if len(s['history']) > self.window:
                s['history'].pop(0)
            s['last_update'] = frame
            if s['n'] < self.min_samples:
                s['state'] = 'COLLECTING'
            else:
                hist = np.asarray(s['history'])
                rel = float(np.std(hist) / max(s['mean'], 1e-9)) if len(hist) >= 5 else 1.0
                s['state'] = 'CALIBRATED' if (len(hist) >= self.window and rel <= self.calib_rel_std) else 'CALIBRATING'
        return self.snapshot()

    def snapshot(self):
        return {k: dict(mean=v['mean'], std=float(np.std(v['history'])) if v['history'] else None,
                        n=v['n'], state=v['state'], resets=v['resets'], last_update=v['last_update'])
                for k, v in self.seg.items()}

    def states(self):
        return {k: v['state'] for k, v in self.seg.items()}

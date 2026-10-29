"""Temporal tracking + online length calibration (the "continuous" part of the milestone).

Per frame the pose is fitted by coordinate descent starting from the previous frame's pose; then each
segment's length is measured from the points assigned to that segment (axial span minus twice the
median cross-section radius). The pose therefore carries memory, and lengths are data measurements.
No label, no truth, no training.
"""
import sys
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
import body2 as B
import chain as H

ANGLE_KEYS = ['arm_L', 'arm_R', 'elbow_L', 'elbow_R', 'leg_L', 'leg_R', 'knee_L', 'knee_R']
SEGMENTS = [s[0] for s in B.SEGMENTS]
LENGTH_KEYS = list(SEGMENTS)
WIDTH_KEYS = ['SHOULDER_W', 'HIP_W']


def pose_joints(theta, L, W, root):
    """theta = [trunk_angle, arm_L, arm_R, elbow_L, elbow_R, leg_L, leg_R, knee_L, knee_R]."""
    t = theta[0]
    u = np.array([np.cos(t), np.sin(t)])
    n = np.array([-np.sin(t), np.cos(t)])
    g = dict(zip(ANGLE_KEYS, theta[1:]))
    J = {}
    J['PELVIS'] = np.asarray(root, dtype=float)
    J['HEAD'] = J['PELVIS'] + L['TRUNK'] * u
    J['SHOULDER_C'] = J['PELVIS'] + 0.85 * L['TRUNK'] * u
    J['HIP_C'] = J['PELVIS'] + 0.08 * L['TRUNK'] * u
    for side, sign in [('L', 1.0), ('R', -1.0)]:
        J['SHOULDER_' + side] = J['SHOULDER_C'] + sign * W['SHOULDER_W'] / 2 * n
        a = np.deg2rad(g['arm_' + side])
        d1 = -u * np.cos(a) + sign * n * np.sin(a)
        J['ELBOW_' + side] = J['SHOULDER_' + side] + L['UPPER_ARM_' + side] * d1
        e = np.deg2rad(g['elbow_' + side])
        n1 = np.array([-d1[1], d1[0]]) * sign
        d2 = d1 * np.cos(e) + n1 * np.sin(e)
        J['WRIST_' + side] = J['ELBOW_' + side] + L['FOREARM_' + side] * d2
        J['HIP_' + side] = J['HIP_C'] + sign * W['HIP_W'] / 2 * n
        b = np.deg2rad(g['leg_' + side])
        e1 = -u * np.cos(b) + sign * n * np.sin(b)
        J['KNEE_' + side] = J['HIP_' + side] + L['THIGH_' + side] * e1
        k = np.deg2rad(g['knee_' + side])
        n2 = np.array([-e1[1], e1[0]]) * sign
        e2 = e1 * np.cos(k) + n2 * np.sin(k)
        J['ANKLE_' + side] = J['KNEE_' + side] + L['SHIN_' + side] * e2
    return J


def segments_of(J):
    return [(name, J[a], J[b]) for name, a, b, _ in B.SEGMENTS]


def point_seg_dist(uv, segs):
    D = np.empty((len(uv), len(segs)))
    for k, (_, a, b) in enumerate(segs):
        ab = b - a
        L2 = max(float(ab @ ab), 1e-12)
        t = np.clip(((uv - a) @ ab) / L2, 0.0, 1.0)
        D[:, k] = np.linalg.norm(uv - (a + t[:, None] * ab), axis=1)
    return D


def cost(uv, J, tree, lam=0.6, reach=0.35):
    """Per-point fit plus coverage.

    A per-segment balanced variant was also tried and was worse on the synthetic set (it collapsed
    sideways), so this per-point form is the recorded v4 configuration.
    """
    segs = segments_of(J)
    D = point_seg_dist(uv, segs)
    data = float(np.mean(np.minimum(D.min(axis=1), reach)))
    M = np.array([a + (b - a) * t for _, a, b in segs for t in np.linspace(0, 1, 6)])
    cover = float(np.mean(np.minimum(tree.query(M)[0], reach)))
    return data + lam * cover


def fit(uv, L, W, theta0, root0, tree, sweeps=3):
    theta = np.array(theta0, dtype=float)
    root = np.array(root0, dtype=float)
    steps = np.array([0.14] + [0.30] * 8)
    best = cost(uv, pose_joints(theta, L, W, root), tree)
    for _ in range(sweeps):
        for k in range(9):
            for d in (-1.0, 1.0):
                cand = theta.copy()
                cand[k] += d * steps[k]
                c = cost(uv, pose_joints(cand, L, W, root), tree)
                if c < best - 1e-9:
                    best, theta = c, cand
        for k in range(2):
            for d in (-1.0, 1.0):
                r = root.copy()
                r[k] += d * 0.06
                c = cost(uv, pose_joints(theta, L, W, r), tree)
                if c < best - 1e-9:
                    best, root = c, r
        steps = steps * 0.55
    return theta, root, best


def measure_lengths(uv, J, min_support=25):
    """Data-side length: axial span of the assigned points minus twice the median radius.

    Widths are measured from the lateral offset of each limb's proximal attachment cluster, so they
    are data measurements too rather than model parameters.
    """
    segs = segments_of(J)
    D = point_seg_dist(uv, segs)
    assigned = np.argmin(D, axis=1)
    out = {}
    for k, (name, a, b) in enumerate(segs):
        pts = uv[assigned == k]
        if len(pts) < min_support:
            continue
        ab = b - a
        n = np.linalg.norm(ab)
        if n < 1e-9:
            continue
        d = ab / n
        t = (pts - a) @ d
        lo, hi = np.percentile(t, [2, 98])
        perp = np.linalg.norm(pts - a - np.outer(t, d), axis=1)
        r = float(np.median(perp))
        val = float(hi - lo - 2.0 * r)
        if val > 0.03:
            out[name] = val
    # widths: lateral offset of each limb's proximal cluster from the trunk axis
    pelvis, head = J['PELVIS'], J['HEAD']
    axis = head - pelvis
    axis = axis / max(np.linalg.norm(axis), 1e-9)
    perp_axis = np.array([-axis[1], axis[0]])
    for name, seg_names in [('SHOULDER_W', ('UPPER_ARM_L', 'UPPER_ARM_R')),
                            ('HIP_W', ('THIGH_L', 'THIGH_R'))]:
        offs = []
        for seg_name in seg_names:
            k = SEGMENTS.index(seg_name)
            pts = uv[assigned == k]
            if len(pts) < min_support:
                offs = []
                break
            a, b = segs[k][1], segs[k][2]
            d = (b - a) / max(np.linalg.norm(b - a), 1e-9)
            t = (pts - a) @ d
            prox = pts[t <= np.percentile(t, 40)]
            if len(prox) < 8:
                offs = []
                break
            offs.append(abs(float(np.median((prox - pelvis) @ perp_axis))))
        if len(offs) == 2:
            out[name] = float(sum(offs))
    return out, assigned


def seed(uv, L, W, tree, n_angles=12):
    """Frame-0 coarse seed: trunk angle sweep with a canonical joint set, root at the cloud median."""
    root = np.median(uv, axis=0)
    best = None
    canon = [35.0, 35.0, 40.0, 40.0, 12.0, 12.0, 35.0, 35.0]
    for k in range(n_angles):
        t = 2 * np.pi * k / n_angles
        for mir in (1.0, -1.0):
            theta = np.array([t] + [c * (mir if i % 2 == 0 else mir) for i, c in enumerate(canon)])
            c = cost(uv, pose_joints(theta, L, W, root), tree)
            if best is None or c < best[0]:
                best = (c, theta, root)
    return best[1], best[2], best[0]


class Tracker:
    def __init__(self, lengths, widths, theta, root, calib=None):
        self.L = dict(lengths)
        self.W = dict(widths)
        self.theta = np.asarray(theta, dtype=float)
        self.root = np.asarray(root, dtype=float)
        self.cal = calib or H.Calibrator(dict(H.SEED))
        self.frames = []

    def step(self, uv, t=None):
        tree = cKDTree(uv)
        theta, root, c = fit(uv, self.L, self.W, self.theta, self.root, tree)
        J = pose_joints(theta, self.L, self.W, root)
        meas, assigned = measure_lengths(uv, J)
        snap = self.cal.update(len(self.frames), meas)
        # lengths used for the next frame are the calibrated means (this is the online calibration)
        for k in self.L:
            if k in snap and snap[k]['n']:
                self.L[k] = snap[k]['mean']
        self.theta, self.root = theta, root
        rec = dict(frame=len(self.frames), cost=c, measured=sorted(meas), n_meas=len(meas),
                   states={k: v['state'] for k, v in snap.items()})
        self.frames.append(rec)
        return rec, J, snap

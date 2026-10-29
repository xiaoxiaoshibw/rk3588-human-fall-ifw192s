"""Synthetic articulated body: capsule sampling with known segment lengths (scoring only).

The extractor never imports this module; the true lengths live only here and in the scoring code.
"""
import sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import s5core as C

TOPOLOGY = [
    ('SPINE', 'PELVIS', 'CHEST'),
    ('CHEST_HEAD', 'CHEST', 'HEAD'),
    ('SHOULDER_SPAN', 'CHEST', 'SHOULDER_C'),
    ('HIP_SPAN', 'PELVIS', 'HIP_C'),
    ('SHOULDER_OFF_L', 'SHOULDER_C', 'SHOULDER_L'),
    ('SHOULDER_OFF_R', 'SHOULDER_C', 'SHOULDER_R'),
    ('HIP_OFF_L', 'HIP_C', 'HIP_L'),
    ('HIP_OFF_R', 'HIP_C', 'HIP_R'),
    ('UPPER_ARM_L', 'SHOULDER_L', 'ELBOW_L'),
    ('FOREARM_L', 'ELBOW_L', 'WRIST_L'),
    ('UPPER_ARM_R', 'SHOULDER_R', 'ELBOW_R'),
    ('FOREARM_R', 'ELBOW_R', 'WRIST_R'),
    ('THIGH_L', 'HIP_L', 'KNEE_L'),
    ('SHIN_L', 'KNEE_L', 'ANKLE_L'),
    ('THIGH_R', 'HIP_R', 'KNEE_R'),
    ('SHIN_R', 'KNEE_R', 'ANKLE_R'),
]
JOINTS = ['PELVIS', 'CHEST', 'HEAD', 'SHOULDER_C', 'SHOULDER_L', 'SHOULDER_R', 'ELBOW_L', 'ELBOW_R',
          'WRIST_L', 'WRIST_R', 'HIP_C', 'HIP_L', 'HIP_R', 'KNEE_L', 'KNEE_R', 'ANKLE_L', 'ANKLE_R']
SEGMENTS = [name for name, _, _ in TOPOLOGY]

# Seed ratios only (no per-person or population claim): they are replaced by online estimates.
SEED = dict(SPINE=0.50, CHEST_HEAD=0.20, SHOULDER_SPAN=0.36, HIP_SPAN=0.30,
            SHOULDER_OFF_L=0.18, SHOULDER_OFF_R=0.18, HIP_OFF_L=0.15, HIP_OFF_R=0.15,
            UPPER_ARM_L=0.30, FOREARM_L=0.26, UPPER_ARM_R=0.30, FOREARM_R=0.26,
            THIGH_L=0.42, SHIN_L=0.42, THIGH_R=0.42, SHIN_R=0.42)

RADIUS = dict(SPINE=0.11, CHEST_HEAD=0.09, SHOULDER_SPAN=0.09, HIP_SPAN=0.10,
              SHOULDER_OFF_L=0.06, SHOULDER_OFF_R=0.06, HIP_OFF_L=0.06, HIP_OFF_R=0.06,
              UPPER_ARM_L=0.045, FOREARM_L=0.038, UPPER_ARM_R=0.045, FOREARM_R=0.038,
              THIGH_L=0.065, SHIN_L=0.050, THIGH_R=0.065, SHIN_R=0.050)


def rot(deg):
    a = np.deg2rad(deg)
    return np.array([[np.cos(a), -np.sin(a)], [np.sin(a), np.cos(a)]])


def pose(lengths, angles):
    """2D forward kinematics in the body plane (u = body axis at rest, v = lateral)."""
    L = dict(lengths)
    g = dict(angles)
    J = {}
    tilt = rot(g.get('tilt', 0.0))
    up = np.array([1.0, 0.0]) @ tilt            # head direction
    lat = np.array([0.0, 1.0]) @ tilt
    J['PELVIS'] = np.array([0.0, 0.0])
    J['CHEST'] = J['PELVIS'] + L['SPINE'] * up
    J['HEAD'] = J['CHEST'] + L['CHEST_HEAD'] * up
    J['SHOULDER_C'] = J['CHEST']
    J['HIP_C'] = J['PELVIS']
    for side, sign, sgn in [('L', -1, 1), ('R', 1, -1)]:
        J['SHOULDER_' + side] = J['CHEST'] + sign * L['SHOULDER_SPAN'] / 2 * lat
        arm = (g.get('shoulder_' + side, 0.0) + 180.0) * sgn
        J['ELBOW_' + side] = J['SHOULDER_' + side] + L['UPPER_ARM_' + side] * (up @ rot(arm))
        fore = (g.get('elbow_' + side, 0.0) + 180.0) * sgn
        J['WRIST_' + side] = J['ELBOW_' + side] + L['FOREARM_' + side] * (up @ rot(arm + fore * sgn))
        J['HIP_' + side] = J['PELVIS'] + sign * L['HIP_SPAN'] / 2 * lat
        thigh = (g.get('hip_' + side, 0.0) + 180.0) * sgn
        J['KNEE_' + side] = J['HIP_' + side] + L['THIGH_' + side] * (up @ rot(thigh))
        shin = (g.get('knee_' + side, 0.0) + 180.0) * sgn
        J['ANKLE_' + side] = J['KNEE_' + side] + L['SHIN_' + side] * (up @ rot(thigh + shin * sgn))
    return J


def sample(lengths, angles, rng, n_per_m=260, noise=0.012, drop=(), depth=0.09):
    """Capsule points around every segment plus depth jitter; optional dropped segments."""
    J = pose(lengths, angles)
    pts = []
    for name, a, b in TOPOLOGY:
        if name in drop:
            continue
        pa, pb = J[a], J[b]
        length = float(np.linalg.norm(pb - pa))
        n = max(12, int(n_per_m * length))
        t = rng.uniform(0.0, 1.0, n)
        base = pa + (pb - pa) * t[:, None]
        r = RADIUS[name]
        # capsule surface sampling: random direction in the plane plus depth
        ang = rng.uniform(0, 2 * np.pi, n)
        rad = r * np.sqrt(rng.uniform(0.25, 1.0, n))
        perp = np.array([-(pb - pa)[1], (pb - pa)[0]]) / max(length, 1e-9)
        off = rad[:, None] * (np.cos(ang)[:, None] * perp + np.sin(ang)[:, None] * np.array([0.0, 1.0]))
        w = rng.normal(0, depth * 0.35, n)
        pts.append(np.column_stack([base + off, w]))
    p = np.concatenate(pts)
    p[:, :2] += rng.normal(0, noise, (len(p), 2))
    return dict(points=p, joints_true=J, lengths_true=dict(lengths))


def scenario(name, rng):
    """Registered synthetic scenarios; the truth is returned for scoring only."""
    base = dict(SEED)
    scale = rng.uniform(0.92, 1.08)
    lengths = {k: v * scale for k, v in base.items()}
    if name == 'upright':
        angles = dict(tilt=rng.uniform(-6, 6), hip_L=rng.uniform(-8, 8), hip_R=rng.uniform(-8, 8),
                      knee_L=rng.uniform(0, 12), knee_R=rng.uniform(0, 12),
                      shoulder_L=rng.uniform(0, 20), shoulder_R=rng.uniform(0, 20),
                      elbow_L=rng.uniform(0, 25), elbow_R=rng.uniform(0, 25))
        drop = ()
    elif name == 'bent':
        angles = dict(tilt=rng.uniform(55, 75), hip_L=rng.uniform(-20, 10), hip_R=rng.uniform(-20, 10),
                      knee_L=rng.uniform(5, 25), knee_R=rng.uniform(5, 25),
                      shoulder_L=rng.uniform(20, 45), shoulder_R=rng.uniform(20, 45),
                      elbow_L=rng.uniform(0, 30), elbow_R=rng.uniform(0, 30))
        drop = ()
    elif name == 'lying':
        angles = dict(tilt=rng.uniform(82, 92), hip_L=rng.uniform(-10, 15), hip_R=rng.uniform(-10, 15),
                      knee_L=rng.uniform(0, 20), knee_R=rng.uniform(0, 20),
                      shoulder_L=rng.uniform(-10, 20), shoulder_R=rng.uniform(-10, 20),
                      elbow_L=rng.uniform(0, 30), elbow_R=rng.uniform(0, 30))
        drop = ()
    elif name == 'occluded':
        angles = dict(tilt=rng.uniform(-6, 20), hip_L=rng.uniform(-8, 8), hip_R=rng.uniform(-8, 8),
                      knee_L=rng.uniform(0, 12), knee_R=rng.uniform(0, 12),
                      shoulder_L=rng.uniform(0, 20), shoulder_R=rng.uniform(0, 20),
                      elbow_L=rng.uniform(0, 25), elbow_R=rng.uniform(0, 25))
        drop = ('FOREARM_L', 'SHIN_L')
    else:
        raise ValueError('unknown scenario')
    return dict(lengths=lengths, angles=angles, drop=drop)

"""v2 synthetic bodies for the observable model (trunk, four limb pairs, two widths).

Truth lives only here and in the scoring code; the extractor (`chain.py`) sees points only.
"""
import numpy as np

TRUNK_R = 0.11
ARM_R = (0.045, 0.038)
LEG_R = (0.065, 0.050)


def rot(a):
    return np.array([[np.cos(a), -np.sin(a)], [np.sin(a), np.cos(a)]])


def direction(angle_deg, sign):
    """Downward direction in body coordinates (u toward the head), tilted outward by angle."""
    a = np.deg2rad(angle_deg)
    d = np.array([-np.cos(a), sign * np.sin(a)])
    return d / np.linalg.norm(d)


def build(spec):
    """Joint positions for the given spec (2D body frame, u toward the head)."""
    L, W, A = spec['lengths'], spec['widths'], spec['angles']
    J = {}
    J['PELVIS'] = np.array([0.0, 0.0])
    J['HEAD'] = np.array([L['TRUNK'], 0.0])
    J['SHOULDER_C'] = np.array([0.85 * L['TRUNK'], 0.0])
    J['HIP_C'] = np.array([0.08 * L['TRUNK'], 0.0])
    for side, sign in [('L', 1.0), ('R', -1.0)]:
        J['SHOULDER_' + side] = J['SHOULDER_C'] + np.array([0.0, sign * W['SHOULDER_W'] / 2])
        d1 = direction(A['arm_' + side], sign)
        J['ELBOW_' + side] = J['SHOULDER_' + side] + L['UPPER_ARM_' + side] * d1
        d2 = rot(np.deg2rad(sign * A['elbow_' + side])) @ d1
        J['WRIST_' + side] = J['ELBOW_' + side] + L['FOREARM_' + side] * d2
        J['HIP_' + side] = J['HIP_C'] + np.array([0.0, sign * W['HIP_W'] / 2])
        e1 = direction(A['leg_' + side], sign)
        J['KNEE_' + side] = J['HIP_' + side] + L['THIGH_' + side] * e1
        e2 = rot(np.deg2rad(sign * A['knee_' + side])) @ e1
        J['ANKLE_' + side] = J['KNEE_' + side] + L['SHIN_' + side] * e2
    return J


SEGMENTS = [('TRUNK', 'PELVIS', 'HEAD', TRUNK_R),
            ('UPPER_ARM_L', 'SHOULDER_L', 'ELBOW_L', ARM_R[0]), ('FOREARM_L', 'ELBOW_L', 'WRIST_L', ARM_R[1]),
            ('UPPER_ARM_R', 'SHOULDER_R', 'ELBOW_R', ARM_R[0]), ('FOREARM_R', 'ELBOW_R', 'WRIST_R', ARM_R[1]),
            ('THIGH_L', 'HIP_L', 'KNEE_L', LEG_R[0]), ('SHIN_L', 'KNEE_L', 'ANKLE_L', LEG_R[1]),
            ('THIGH_R', 'HIP_R', 'KNEE_R', LEG_R[0]), ('SHIN_R', 'KNEE_R', 'ANKLE_R', LEG_R[1])]


def sample(spec, rng, density=2400.0, noise=0.010, drop=()):
    """Surface-area-proportional sampling: thicker parts return more points, as a real scan does.

    Linear density proportional to length only would make a thin limb as dense per metre as the
    trunk, which is not how the sensor behaves and is not what the extractor must rely on.
    """
    J = build(spec)
    pts = []
    for name, a, b, r in SEGMENTS:
        if name in drop:
            continue
        pa, pb = J[a], J[b]
        length = float(np.linalg.norm(pb - pa))
        n = max(40, int(density * length * r))
        t = rng.uniform(0.0, 1.0, n)
        base = pa + (pb - pa) * t[:, None]
        d = (pb - pa) / max(length, 1e-9)
        perp = np.array([-d[1], d[0]])
        ang = rng.uniform(0, 2 * np.pi, n)
        rad = r * np.sqrt(rng.uniform(0.15, 1.0, n))
        off = rad[:, None] * (np.cos(ang)[:, None] * perp + np.sin(ang)[:, None] * np.array([0.0, 1.0]))
        pts.append(base + off)
    p = np.concatenate(pts)
    p += rng.normal(0, noise, p.shape)
    w = rng.normal(0, 0.045, len(p))
    return np.column_stack([p, w]), J


def scenario(name, rng):
    lengths = dict(TRUNK=rng.uniform(0.62, 0.76),
                   UPPER_ARM_L=rng.uniform(0.27, 0.33), FOREARM_L=rng.uniform(0.23, 0.28),
                   UPPER_ARM_R=rng.uniform(0.27, 0.33), FOREARM_R=rng.uniform(0.23, 0.28),
                   THIGH_L=rng.uniform(0.38, 0.46), SHIN_L=rng.uniform(0.38, 0.46),
                   THIGH_R=rng.uniform(0.38, 0.46), SHIN_R=rng.uniform(0.38, 0.46))
    widths = dict(SHOULDER_W=rng.uniform(0.34, 0.42), HIP_W=rng.uniform(0.28, 0.34))
    if name == 'upright':
        angles = dict(arm_L=rng.uniform(25, 40), arm_R=rng.uniform(25, 40),
                      elbow_L=rng.uniform(30, 50), elbow_R=rng.uniform(30, 50),
                      leg_L=rng.uniform(8, 16), leg_R=rng.uniform(8, 16),
                      knee_L=rng.uniform(28, 45), knee_R=rng.uniform(28, 45))
        drop = ()
        tilt = 0.0
    elif name == 'bent':
        angles = dict(arm_L=rng.uniform(30, 50), arm_R=rng.uniform(30, 50),
                      elbow_L=rng.uniform(30, 55), elbow_R=rng.uniform(30, 55),
                      leg_L=rng.uniform(10, 20), leg_R=rng.uniform(10, 20),
                      knee_L=rng.uniform(30, 50), knee_R=rng.uniform(30, 50))
        drop = ()
        tilt = rng.uniform(55, 75)
    elif name == 'lying':
        angles = dict(arm_L=rng.uniform(30, 55), arm_R=rng.uniform(30, 55),
                      elbow_L=rng.uniform(30, 55), elbow_R=rng.uniform(30, 55),
                      leg_L=rng.uniform(8, 18), leg_R=rng.uniform(8, 18),
                      knee_L=rng.uniform(30, 50), knee_R=rng.uniform(30, 50))
        drop = ()
        tilt = rng.uniform(82, 92)
    elif name == 'occluded':
        angles = dict(arm_L=rng.uniform(25, 40), arm_R=rng.uniform(25, 40),
                      elbow_L=rng.uniform(30, 50), elbow_R=rng.uniform(30, 50),
                      leg_L=rng.uniform(8, 16), leg_R=rng.uniform(8, 16),
                      knee_L=rng.uniform(28, 45), knee_R=rng.uniform(28, 45))
        drop = ('FOREARM_L', 'SHIN_L')
        tilt = rng.uniform(-10, 10)
    else:
        raise ValueError('unknown scenario')
    return dict(lengths=lengths, widths=widths, angles=angles, drop=drop, tilt=tilt)


def place(points, tilt_deg, rng):
    """Rotate the whole body in its plane and add depth, so nothing in the data says 'upright'."""
    q = points[:, :2] @ rot(np.deg2rad(tilt_deg)).T
    return np.column_stack([q, points[:, 2] + rng.normal(0, 0.02, len(q))])

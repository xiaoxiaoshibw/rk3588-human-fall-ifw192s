"""Point-supported region skeleton of the current target, not anatomical joints.

Intrinsic axes also allow horizontal objects. Axis ends and A/B are deliberately
unnamed: a single visible surface cannot establish head/feet or left/right.
No inferred, carried-over or smoothed node is passed to fall detection.
"""
import numpy as np


VERSION = '0.1.0'
SETTINGS = dict(min_points=30, min_support=6, axis_ratio=1.6,
                min_span_m=.35, min_branch_m=.10)
EDGES = [('TOP', 'UPPER'), ('UPPER', 'CENTER'), ('CENTER', 'BASE'),
         ('UPPER', 'UPPER_A'), ('UPPER', 'UPPER_B'),
         ('UPPER_A', 'OUTER_A'), ('UPPER_B', 'OUTER_B'),
         ('BASE', 'LOWER_A'), ('BASE', 'LOWER_B'),
         ('LOWER_A', 'END_A'), ('LOWER_B', 'END_B')]


def estimate(points, source_rows):
    p = np.asarray(points, dtype=np.float64).reshape(-1, 3)
    rows = np.asarray(source_rows)
    if (len(rows) != len(p) or rows.ndim != 1 or
            (len(rows) and (rows.dtype.kind not in 'iu' or np.any(rows < 0))) or
            len(np.unique(rows)) != len(rows)):
        raise ValueError('skeleton requires unique current target source rows')
    result = dict(version=VERSION, semantic='GEOMETRIC_REGIONS',
                  anatomicalJoints='UNKNOWN', reason='insufficient_support', nodes={}, edges=[])
    if len(p) < SETTINGS['min_points'] or not np.isfinite(p).all():
        return result
    center = np.median(p, axis=0)
    values, vectors = np.linalg.eigh(np.cov((p-center).T))
    if values[-1] <= 1e-9 or values[-1] < SETTINGS['axis_ratio'] * max(values[-2], 1e-9):
        result['reason'] = 'ambiguous_axis'
        return result
    axis = vectors[:, -1].copy()
    # Deterministic sign only; no head/foot or physical vertical identity.
    if axis[np.argmax(np.abs(axis))] < 0:
        axis = -axis
    lateral = vectors[:, -2].copy()
    if lateral[np.argmax(np.abs(lateral))] < 0:
        lateral = -lateral
    local = p-center
    along, across = local @ axis, local @ lateral
    lo, hi = np.quantile(along, [.02, .98])
    if hi-lo < SETTINGS['min_span_m']:
        result['reason'] = 'short_axis'
        return result
    fraction = (along-lo)/(hi-lo)

    def node(name, mask):
        ids = np.flatnonzero(mask)
        if len(ids) < SETTINGS['min_support']:
            return
        # A visible-surface regional centre; evidence is the complete support set.
        result['nodes'][name] = dict(xyz=np.median(p[ids], axis=0).tolist(),
                                    sourceRows=rows[ids].tolist(), supportCount=len(ids))

    for name, low, high in [('TOP', .88, 1.03), ('UPPER', .68, .88),
                             ('CENTER', .46, .68), ('BASE', .28, .46)]:
        node(name, (fraction >= low) & (fraction < high))
    for suffix, sign in [('A', -1), ('B', 1)]:
        for name, low, high, offset in [('UPPER', .55, .86, .10),
                                       ('OUTER', .35, .80, .22),
                                       ('LOWER', .12, .28, .08),
                                       ('END', -.03, .12, .08)]:
            node(name+'_'+suffix, (fraction >= low) & (fraction < high) & (sign*across > offset))
    for a, b in [('LOWER_A', 'LOWER_B'), ('END_A', 'END_B')]:
        nodes = result['nodes']
        if a in nodes and b in nodes and np.linalg.norm(np.array(nodes[a]['xyz'])-nodes[b]['xyz']) < SETTINGS['min_branch_m']:
            del nodes[a], nodes[b]
    result['edges'] = [[a, b] for a, b in EDGES if a in result['nodes'] and b in result['nodes']]
    result['reason'] = 'point_supported_regions'
    return result


def project_regions(skeleton, frame):
    """Same measured support to v2 display pixels, without reprojecting RAW XYZ."""
    if not skeleton['nodes']:
        return skeleton
    y, x = np.nonzero(frame.valid)
    sources = frame.source_rows[y, x]
    row_to_pixel = np.full((int(sources.max())+1, 2), np.nan)
    row_to_pixel[sources] = np.column_stack((frame.valid.shape[1]-1-x, frame.valid.shape[0]-1-y))
    for node in skeleton['nodes'].values():
        rows = np.asarray(node['sourceRows'], dtype=np.int64)
        if np.any(rows < 0) or np.any(rows >= len(row_to_pixel)):
            raise ValueError('skeleton support missing from current range frame')
        pixels = row_to_pixel[rows]
        if not np.isfinite(pixels).all():
            raise ValueError('skeleton support missing from current range frame')
        node['imageXY'] = np.median(pixels, axis=0).tolist()
    return skeleton

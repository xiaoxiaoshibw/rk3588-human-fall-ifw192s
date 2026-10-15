"""Frozen-background single-frame XYZ pipeline and explicit unverified body regions."""
import numpy as np
from scipy.spatial import cKDTree
from sklearn.cluster import DBSCAN

R = np.array([[.893544, 0, .448975], [-.014337, .99949, .028533], [-.448746, -.031932, .893089]])
T = np.array([0, 0, 1.380286])
PARTS = ['UNKNOWN', 'HEAD', 'TORSO', 'LEFT_ARM', 'RIGHT_ARM', 'LEFT_LEG', 'RIGHT_LEG']
SLOTS = ['TOP_REGION', 'UPPER_TORSO', 'CHEST', 'PELVIS', 'LOWER_CENTER',
         'UPPER_A', 'UPPER_B', 'OUTER_A', 'OUTER_B', 'LOWER_A', 'LOWER_B', 'END_A', 'END_B']
EDGES = [('TOP_REGION', 'UPPER_TORSO'), ('UPPER_TORSO', 'CHEST'), ('CHEST', 'PELVIS'), ('PELVIS', 'LOWER_CENTER'),
         ('UPPER_TORSO', 'UPPER_A'), ('UPPER_TORSO', 'UPPER_B'), ('UPPER_A', 'OUTER_A'), ('UPPER_B', 'OUTER_B'),
         ('PELVIS', 'LOWER_A'), ('PELVIS', 'LOWER_B'), ('LOWER_A', 'END_A'), ('LOWER_B', 'END_B')]


def valid_raw(p):
    return np.isfinite(p).all(axis=1) & np.any(p != 0, axis=1)


def roi_mask(p, polygon):
    inside = np.zeros(len(p), bool)
    for a, b in zip(polygon, polygon[1:] + polygon[:1]):
        if a[1] == b[1]:
            continue
        inside ^= ((a[1] > p[:, 1]) != (b[1] > p[:, 1])) & (p[:, 0] < (b[0]-a[0])*(p[:, 1]-a[1])/(b[1]-a[1])+a[0])
    return inside


def voxelize(points, size):
    keys, inv = np.unique(np.floor(points / size).astype('i4'), axis=0, return_inverse=True)
    counts = np.bincount(inv)
    centers = np.column_stack([np.bincount(inv, weights=points[:, i]) / counts for i in range(3)])
    return keys, centers, inv, counts


def cluster(points, cfg, dimensions=3):
    if len(points) == 0:
        return [], np.empty((0, 3))
    _, centers, inv, _ = voxelize(points, cfg['voxel_m'])
    labels = DBSCAN(eps=cfg['cluster_eps_m'], min_samples=cfg['cluster_min_voxels'], n_jobs=1).fit_predict(centers[:, :dimensions])
    groups = [np.flatnonzero(labels[inv] == label) for label in sorted(set(labels)) if label >= 0]
    return [g for g in groups if len(g) >= cfg['cluster_min_points']], centers


def describe(points):
    center = np.mean(points, axis=0)
    lo, hi = np.quantile(points, [.02, .98], axis=0)
    eigen = np.linalg.eigvalsh(np.cov(points.T))
    hist = np.histogram(points[:, 2], bins=np.linspace(lo[2]-.001, hi[2]+.001, 7))[0] / len(points)
    # Fixed-dimensional features of an unordered 3D set, no GT/track input.
    return np.r_[hi-lo, np.quantile(points[:, 2], [.1, .5, .9]), eigen, hist,
                 np.quantile(np.linalg.norm(points-center, axis=1), [.25, .5, .9]), np.log1p(len(points))].tolist()


def independence(points, background_distances, others, tolerance, cfg):
    _, centers, _, _ = voxelize(points, cfg['voxel_m'])
    labels = DBSCAN(eps=cfg['cluster_eps_m']*cfg['independence_probe_eps_fraction'],
                    min_samples=cfg['cluster_min_voxels'], n_jobs=1).fit_predict(centers)
    sizes = [int((labels == k).sum()) for k in set(labels) if k >= 0]
    coherent = max(sizes, default=0) / max(1, len(centers))
    near = float(np.mean(background_distances < tolerance * cfg['near_background_factor']))
    gap = float(cKDTree(others).query(centers, k=1)[0].min()) if len(others) else None
    separated = 1. if gap is None else min(1., gap / cfg['separation_normalizer_m'])
    score = 100 * np.dot(cfg['independence_weights'], [coherent, separated, 1-near])
    return {'score_0_100': round(score, 2), 'score_kind': 'GEOMETRIC_DIAGNOSTIC_NOT_HUMAN_PROBABILITY',
            'dense_core_fraction': coherent, 'near_background_fraction': near, 'nearest_other_cluster_gap_m': gap,
            'tight_components': len(sizes), 'warning': ['POSSIBLE_BACKGROUND_CONTACT'] if near > cfg['background_contact_warning_fraction'] else []}


def skeleton(points, source_rows, cfg):
    """PCA-axis point-supported regions; never anatomical training labels."""
    unknown = lambda why: {'valid': False, 'xyz': None, 'support_source_indices': [], 'reason': why}
    nodes = {k: unknown('INSUFFICIENT_SUPPORT') for k in SLOTS}
    result = {'nodes': nodes, 'edges': [], 'kind': 'UNVERIFIED_POINT_SUPPORTED_BODY_REGIONS',
              'head_identity': 'UNKNOWN', 'anatomical_left_right': 'UNKNOWN', 'part_labels': 'UNKNOWN'}
    if len(points) < cfg['cluster_min_points']:
        return result
    center = np.mean(points, axis=0)
    vals, vecs = np.linalg.eigh(np.cov(points.T))
    span = np.ptp(points, axis=0)
    upright = span[2] > cfg['upright_min_span_m'] and span[2] > max(span[:2])
    if not upright and vals[-1] / max(vals[-2], 1e-9) < cfg['axis_eigen_ratio_min']:
        result['nodes'] = {k: unknown('AMBIGUOUS_BODY_AXIS') for k in SLOTS}
        return result
    axis = np.array([0., 0., 1.]) if upright else vecs[:, -1]
    if axis[2] < 0:
        axis = -axis
    lateral = np.cross(axis, [1., 0., 0.])
    if np.linalg.norm(lateral) < cfg['lateral_axis_min_norm']:
        lateral = np.cross(axis, [0., 1., 0.])
    lateral /= np.linalg.norm(lateral)
    local = (points-center) @ np.column_stack([lateral, np.cross(lateral, axis), axis])
    low, high = np.quantile(local[:, 2], [.02, .98])
    if high-low < cfg['body_axis_min_span_m']:
        return result
    fraction = (local[:, 2]-low) / (high-low)

    def node(name, mask):
        ix = np.flatnonzero(mask)
        if len(ix) >= cfg['part_min_points']:
            nodes[name] = {'valid': True, 'xyz': np.mean(points[ix], axis=0).tolist(),
                           'support_source_indices': np.asarray(source_rows)[ix].tolist(),
                           'reason': 'POINT_SUPPORTED_REGION_NOT_CALIBRATED_JOINT'}
    for name, (a, b) in zip(SLOTS[:5], cfg['body_bands']):
        node(name, (fraction >= a) & (fraction < b))
    for side, sign in [('A', -1), ('B', 1)]:
        branch = sign*local[:, 0] > cfg['branch_offset_m']
        for prefix, band in [('UPPER', 'upper'), ('OUTER', 'outer'), ('LOWER', 'lower'), ('END', 'end')]:
            a, b = cfg['branch_bands'][band]
            selected = sign*local[:, 0] > cfg['outer_branch_offset_m'] if band == 'outer' else branch
            node(prefix+'_'+side, selected & (fraction >= a) & (fraction < b))
    for a, b in [('LOWER_A', 'LOWER_B'), ('END_A', 'END_B')]:
        if nodes[a]['valid'] and nodes[b]['valid'] and np.linalg.norm(np.subtract(nodes[a]['xyz'], nodes[b]['xyz'])) < cfg['branch_min_separation_m']:
            nodes[a], nodes[b] = unknown('BRANCHES_NOT_SEPARATED'), unknown('BRANCHES_NOT_SEPARATED')
    result.update(axis=axis.tolist(), edges=[[a, b] for a, b in EDGES if nodes[a]['valid'] and nodes[b]['valid']])
    return result


def sample_points(points, count=256):
    # Match frozen PointNet's ordered subsampling + centering; no scale normalization.
    out = points[np.floor(np.arange(count)*len(points)/count).astype(int)].astype('f4')
    return out - out.mean(axis=0)


def decode_indices(v):
    if not v:
        return []
    if v[0] == 's':
        ids = v[1:]
    elif v[0] == 'r':
        ids = [v[1]+k*v[2] for k in range(v[3])]
    elif v[0] == 'm':
        r, tail = v[1:]
        ids = [r[j]+k*r[j+1] for j in range(0, len(r), 3) for k in range(r[j+2])] + tail
    else:
        raise ValueError('Unknown source-index encoding')
    if any(not isinstance(i, int) or i < 0 for i in ids) or len(set(ids)) != len(ids):
        raise ValueError('Invalid source indices')
    return np.asarray(ids, dtype='i8')

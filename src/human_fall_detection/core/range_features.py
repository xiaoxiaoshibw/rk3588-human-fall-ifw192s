"""W2薄适配：复用既有几何，只描述本帧真实来源行。"""
import numpy as np

from .lidar_candidates import rebuild_candidate
from .range_contract import binding_tuple


def bound_ground(frame, ground):
    if (not isinstance(ground, dict) or ground.get('status') != 'valid'
            or not isinstance(ground.get('binding'), dict)):
        return None
    try:
        if binding_tuple(ground['binding']) != frame.binding:
            return None
        normal=np.asarray(ground.get('normal'),dtype=float)
        offset=float(ground.get('offset_m'))
    except (TypeError,ValueError):
        return None
    if (normal.shape != (3,) or not np.isfinite(normal).all() or not np.isfinite(offset)
            or abs(float(np.linalg.norm(normal))-1)>1e-6
            or ground.get('binding',{}).get('coordinate') != 'RAW/'+str(ground.get('frame'))):
        return None
    return ground


def valid_source_row_mask(frame):
    """Per-frame O(1) lookup mask of valid decoded source rows (exact equivalent of np.isin)."""
    n = len(frame.xyz)
    valid = frame.valid
    source_rows = frame.source_rows
    key = (id(valid), id(source_rows), n, int(np.count_nonzero(valid)))
    cached = getattr(frame, '_valid_row_mask_cache', None)
    if cached is not None and cached[0] == key:
        return cached[1]
    mask = np.zeros(n, dtype=bool)
    sr = np.asarray(source_rows[valid], dtype=np.int64)
    if sr.size:
        sr = sr[(sr >= 0) & (sr < n)]
        mask[sr] = True
    try:
        frame._valid_row_mask_cache = (key, mask)
    except (AttributeError, TypeError):
        pass
    return mask


def measured_features(frame, rows, ground=None):
    rows = np.asarray(rows)
    if (rows.ndim != 1 or not len(rows) or rows.dtype.kind not in 'iu'
            or len(np.unique(rows)) != len(rows) or rows.min() < 0 or rows.max() >= len(frame.xyz)
            or not valid_source_row_mask(frame)[rows].all()):
        raise ValueError('features require unique current decoded measurement rows')
    plane = bound_ground(frame,ground)
    # 只向共享函数传入本帧所选点，避免每个组件复制完整扫描。
    xyz = frame.xyz[rows].astype(float)
    features = rebuild_candidate(xyz, np.arange(len(rows)), ground=plane,
                                 frame_id=plane['frame'] if plane else 'unbound')
    axis = features['axis']
    return dict(point_count=len(rows), center_m=features['center_source_m'],
                bbox_min_m=features['bbox_source_min_m'], bbox_max_m=features['bbox_source_max_m'],
                range_m=features['range_m'], height_m=features['height_m'],
                height_reason=None if features['ground_relative_available'] else 'ground_unavailable_or_unbound',
                ground_uncertainty_m=None, ground_uncertainty_reason='not_independently_measured',
                axis=axis['axis'], axis_valid=not axis['ambiguous'], axis_reason=axis['reason'],
                eigenvalues_m2=axis['eigenvalues'], axis_definition='dominant source-coordinate PCA axis',
                verticality=axis['verticality'], visible_ratio=None,
                visible_ratio_reason='no_trusted_total_visible_surface_denominator', semantic='unknown')

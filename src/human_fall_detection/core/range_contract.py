"""离线距离链的输入身份与证据聚合，不声明物理标定资格。"""
import hashlib
import json
from pathlib import Path

import numpy as np

def source_binding(session, meta, meta_sha, points_sha, grid):
    return dict(session=Path(session).name, meta_sha256=meta_sha, points_sha256=points_sha,
                coordinate='RAW/' + meta['sensor']['frame_id'], units='m',
                coordinate_transform='identity', grid_sha256=grid.sha256,
                epoch='source_header_epoch')


def binding_tuple(binding):
    return (json.dumps(binding, sort_keys=True, separators=(',', ':'), allow_nan=False),)


def load_ground(path, binding):
    """校验实际provenance字节及其中的源身份/平面，不接受仅同名坐标。"""
    ground = json.loads(Path(path).read_text(encoding='utf-8'))
    if ground.get('status') != 'valid' or ground.get('binding') != binding:
        raise ValueError('ground source binding mismatch')
    provenance = ground.get('provenance', {})
    try:
        raw = Path(provenance['source']).read_bytes()
    except (KeyError, OSError) as exc:
        raise ValueError('ground provenance unavailable') from exc
    if hashlib.sha256(raw).hexdigest() != provenance.get('sha256'):
        raise ValueError('ground provenance SHA mismatch')
    original = json.loads(raw.decode('utf-8-sig'))
    if (original.get('sid') != binding['session']
            or original.get('source_sha256') != dict(meta=binding['meta_sha256'], points=binding['points_sha256'])
            or original.get('from_frame') != binding['coordinate'] or original.get('units') != 'm'
            or ground.get('frame') != binding['coordinate'][4:]):
        raise ValueError('ground provenance source mismatch')
    plane = original.get('plane', {})
    if (ground.get('normal') != plane.get('normal_source')
            or ground.get('offset_m') != plane.get('offset_source_m')):
        raise ValueError('ground plane differs from provenance')
    normal = np.asarray(ground.get('normal'), dtype=float)
    if (normal.shape != (3,) or not np.isfinite(normal).all()
            or abs(float(np.linalg.norm(normal))-1) > 1e-6
            or not np.isfinite(float(ground.get('offset_m')))):
        raise ValueError('invalid ground plane')
    return ground


def distribution(values):
    values = [float(v) for v in values if v is not None]
    if not all(np.isfinite(v) for v in values):
        raise ValueError('nonfinite distribution sample')
    result = dict(samples=len(values), median=None, minimum=None, p05=None, p95=None, maximum=None)
    if values:
        result.update(median=float(np.median(values)), minimum=min(values), maximum=max(values),
                      p05=float(np.percentile(values, 5)), p95=float(np.percentile(values, 95)))
    return result


def reference_summary(checks):
    checks = [c for c in checks if c and c.get('reference_observed')]
    keys = ('diagnostic_component_points', 'kept_reference_fraction', 'diagnostic_reference_fraction',
            'reference_dispersion_fraction', 'component_reference_jaccard', 'union_reference_fraction',
            'added_component_points', 'removed_reference_points', 'component_count', 'largest_component_points')
    result = {k: distribution([r.get(k) for r in checks]) for k in keys}
    total = sum(r['reference_points'] for r in checks)
    survived = sum(r['kept_reference_points'] for r in checks)
    intersection = sum(r['selected_intersection_points'] for r in checks)
    union = sum(r['union_reference_points'] for r in checks)
    result['aggregate'] = dict(samples=len(checks), reference_points=total, survived_reference_points=survived,
        selected_intersection_points=intersection, union_reference_points=union,
        weighted_union_coverage=union/total if total else None,
        weighted_main_coverage=intersection/total if total else None,
        weighted_dispersion=(survived-intersection)/survived if survived else None,
        dispersion_reason=None if survived else 'no_surviving_reference_rows',
        denominator_reason=None if total else 'no_observed_reference_rows')
    return result

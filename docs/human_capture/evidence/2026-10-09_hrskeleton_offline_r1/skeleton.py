"""Controlled offline geometry only; no ROS, original Tracker or background imports."""
import math
import numpy as np

SLOTS = ['HEAD', 'UPPER_TORSO', 'CHEST', 'PELVIS_REGION', 'LOWER_REGION']
ALL_SLOTS = SLOTS + ['LOWER_A', 'LOWER_B']

def require(ok, code):
    if not ok:
        raise ValueError(code)

def unknown(reason):
    return {'xyz': None, 'xyz_local': None, 'valid': False, 'support_score': 0,
            'confidence_kind': 'POINT_COUNT_DIAGNOSTIC', 'support_rows': [], 'support_n': 0, 'reason': reason}

def normalize(member, params):
    r = member['receipt']
    rows = r['rows']
    require(len(rows) == len(set(rows)), 'DUPLICATE_MEMBER_ROWS')
    require(len(rows) == len(member['global_rows']) == len(member['xyz']), 'MAP_LENGTH_MISMATCH')
    xyz = np.asarray(member['xyz'], dtype=np.float64).reshape(-1, 3)
    excluded = set(member['invalid_source_rows'])
    require(excluded.issubset(set(rows)), 'INVALID_SOURCE_ROW_UNBOUND')
    mask = np.array([row not in excluded for row in rows], dtype=bool) & np.isfinite(xyz).all(axis=1)
    good = xyz[mask].copy()
    center = np.mean(good, axis=0) if len(good) else np.zeros(3)
    translation = np.array([-center[0], -center[1], 0.0])
    local = good + translation
    err = float(np.max(np.abs(local-translation-good))) if len(good) else 0.0
    require(err <= params['inverse_tolerance_m'], 'INVERSE_ERROR')
    axis = {'status': 'UNKNOWN_DEGENERATE', 'body_orientation': 'UNKNOWN', 'sign': 'UNKNOWN', 'eigenvalues': None, 'line_axis_unsigned': None}
    if len(good) >= 3:
        centered = good-np.mean(good, axis=0)
        values, vectors = np.linalg.eigh(centered.T.dot(centered)/len(good))
        axis['eigenvalues'] = values[::-1].tolist()
        if values[-1] > 1e-12 and values[-1] > params['axis_eigen_ratio_min']*max(values[-2], 1e-12):
            axis.update(status='UNSIGNED_LINE_ONLY', line_axis_unsigned=vectors[:, -1].tolist())
    return {'rows': [r for r, keep in zip(rows, mask) if keep],
            'global_rows': [r for r, keep in zip(member['global_rows'], mask) if keep],
            'xyz': local.tolist(), 'excluded_source_rows': [r for r, keep in zip(rows, mask) if not keep],
            'forward_translation_m': translation.tolist(), 'inverse_translation_m': (-translation).tolist(),
            'inverse_max_error_m': err, 'z_policy': 'EXISTING_BOUND_REFERENCE_HEIGHT_UNCHANGED',
            'principal_axis': axis, 'span_m': np.ptp(good, axis=0).tolist() if len(good) else [0, 0, 0]}

def observe(norm, ids, params):
    if len(ids) < params['node_min_points']:
        return unknown('LOW_SUPPORT')
    points = np.asarray(norm['xyz'])[ids]
    span = np.ptp(points, axis=0)
    if span[2] < params['node_min_z_span_m']:
        return unknown('SPARSE_VERTICAL_SUPPORT')
    if max(span[:2]) > params['node_max_xy_span_m']:
        return unknown('CONFLICTING_SPATIAL_SUPPORT')
    local = np.median(points, axis=0)
    ref = local + np.array(norm['inverse_translation_m'])
    return {'xyz': ref.tolist(), 'xyz_local': local.tolist(), 'valid': True,
            'support_score': min(1.0, len(ids)/(2.0*params['node_min_points'])),
            'confidence_kind': 'POINT_COUNT_DIAGNOSTIC', 'support_rows': [norm['rows'][i] for i in ids],
            'support_n': len(ids), 'support_span_m': span.tolist(),
            'density_points_per_m3': len(ids)/max(float(np.prod(span)), 1e-9), 'reason': 'OBSERVED_REGION_MEDIAN'}

def nodes(norm, review, params):
    # ponytail: fixed standing Z bands; broader posture definitions need a separate reviewed contract.
    out = {}
    xyz = np.asarray(norm['xyz'], dtype=float).reshape(-1, 3)
    for name in SLOTS:
        v = review.get(name)
        if not v or v['visibility'] != 'VISIBLE':
            reason = 'NO_VISIBLE_HEAD_SUPPORT' if name == 'HEAD' and v and v['visibility'] == 'INVISIBLE' else 'VISIBILITY_UNKNOWN'
            out[name] = unknown(reason)
            continue
        if name == 'HEAD':
            if v['reason'] != 'HEAD_CONFIRMED':
                out[name] = unknown('HEAD_OR_HAND_AMBIGUOUS')
                continue
            region = set(v['region_rows'])
            ids = [i for i, row in enumerate(norm['rows']) if row in region]
        else:
            lo, hi = params['bands_m'][name]
            ids = np.flatnonzero((xyz[:, 2] >= lo) & (xyz[:, 2] < hi)).tolist()
        out[name] = observe(norm, ids, params)
        out[name]['reference_region_rows'] = v['region_rows']
    lower = out['LOWER_REGION']
    if lower['valid'] and all(review.get(k, {}).get('visibility') == 'VISIBLE' for k in ['LOWER_A', 'LOWER_B']):
        ix = [i for i, row in enumerate(norm['rows']) if row in set(lower['support_rows'])]
        xy = xyz[ix, :2]
        centered = xy-np.mean(xy, axis=0)
        val, vec = np.linalg.eigh(centered.T.dot(centered)/len(xy))
        if val[-1] > 1e-12 and val[-1] > params['axis_eigen_ratio_min']*max(val[0], 1e-12):
            axis = vec[:, -1]
            if axis[np.argmax(np.abs(axis))] < 0:
                axis = -axis
            projection = xy.dot(axis)
            order = np.argsort(projection, kind='stable')
            gap = np.diff(projection[order])
            k = int(np.argmax(gap))+1 if len(gap) else 0
            if k and gap[k-1] >= params['lower_gap_m']:
                groups = [[ix[i] for i in order[:k]], [ix[i] for i in order[k:]]]
                pair = [observe(norm, g, params) for g in groups]
                if all(p['valid'] for p in pair) and np.linalg.norm(np.array(pair[0]['xyz'])[:2]-np.array(pair[1]['xyz'])[:2]) >= params['lower_min_separation_m']:
                    out['LOWER_A'], out['LOWER_B'] = pair
                    for name in ['LOWER_A', 'LOWER_B']:
                        out[name]['reference_region_rows'] = review[name]['region_rows']
                        out[name]['reason'] = 'SEPARATED_UNSIGNED_A_B_SUPPORT'
    return out

def process(member, label, review, params, allowed):
    if label != 'PERSON':
        return None, {k: unknown('REJECT_'+label) for k in SLOTS}
    if not allowed:
        return None, {k: unknown('BLOCKED_MINIMUM_REAL_GT') for k in SLOTS}
    norm = normalize(member, params)
    return norm, nodes(norm, review, params)

def minimum_gt(records, entries):
    dev = {e['sid'] for e in entries if e['split'] == 'development'}
    met = []
    for sid in sorted(dev):
        groups = {}
        for r in records:
            if r['sid'] == sid and r['label'] == 'PERSON':
                groups.setdefault((r['person_id'], r['track_epoch']), set()).add(r['ordinal'])
        if any(any(all(i+j in seq for j in range(3)) for i in seq) for seq in groups.values()):
            met.append(sid)
    torso = any(r['label'] == 'PERSON' and any(r['nodes'][k]['visibility'] == 'VISIBLE' and r['nodes'][k]['region_rows'] for k in ['CHEST', 'UPPER_TORSO']) for r in records if r['sid'] in dev)
    negative = any(r['label'] != 'PERSON' or any(v['visibility'] == 'INVISIBLE' for v in r['nodes'].values()) for r in records if r['sid'] in dev)
    return {'satisfied': len(met) == 2 and torso and negative, 'continuous_development_sids': met,
            'visible_torso_positive': torso, 'missing_or_reject_control': negative}

class SkeletonTracker:
    def __init__(self, params):
        self.params = params
        self.key = None
        self.stamp = None
        self.ordinal = None
        self.history = {}

    def tick(self, frame, raw, seek=False):
        key = tuple(frame.get(k) for k in ['sid', 'branch', 'coordinate_id', 'person_id', 'track_epoch'])
        sec, ns = frame['stamp_sec'], frame['stamp_nanosec']
        require(isinstance(sec, int) and isinstance(ns, int) and 0 <= ns < 1000000000, 'INVALID_STAMP')
        stamp = sec*1000000000+ns
        dt = (stamp-self.stamp)/1e9 if self.stamp is not None else None
        reason = None
        if seek:
            reason = 'EXPLICIT_SEEK'
        elif self.key != key:
            reason = 'KEY_CHANGED'
        elif dt is not None and dt <= 0:
            reason = 'DUPLICATE_OR_REVERSE_STAMP'
        elif self.ordinal is not None and frame['ordinal'] != self.ordinal+1:
            reason = 'MISSING_FRAME_OR_SEEK'
        elif dt is not None and dt > self.params['reset_gap_s']:
            reason = 'TIME_GAP'
        if reason:
            self.history.clear()
        filtered = {}
        for name, node in raw.items():
            previous = self.history.get(name)
            value = {'measurement_valid': node['valid'], 'raw_xyz': node['xyz'], 'filtered_xyz': None,
                     'history_xyz': previous['xyz'] if previous else None, 'filter_valid': False,
                     'reason': node['reason'], 'jump_m': None, 'speed_m_s': None}
            if not node['valid']:
                self.history.pop(name, None)
            else:
                q = np.array(node['xyz'])
                value['filter_valid'] = True
                if previous is not None:
                    previous_dt = (stamp-previous['stamp'])/1e9
                    jump = float(np.linalg.norm(q-np.array(previous['xyz'])))
                    speed = jump/previous_dt
                    value.update(jump_m=jump, speed_m_s=speed)
                    if jump > self.params['max_jump_m'] or speed > self.params['max_speed_m_s']:
                        value.update(filter_valid=False, reason='FILTER_JUMP_REJECTED_RAW_RETAINED')
                        self.history.pop(name, None)
                    else:
                        alpha = 1.0-math.exp(-previous_dt/self.params['ema_tau_s'])
                        q = np.array(previous['xyz'])+alpha*(q-np.array(previous['xyz']))
                        value['reason'] = 'EMA_ACTUAL_DT'
                else:
                    value['reason'] = 'INITIALIZED_FROM_CURRENT_SUPPORT'
                if value['filter_valid']:
                    value['filtered_xyz'] = q.tolist()
                    self.history[name] = {'xyz': q.tolist(), 'stamp': stamp}
            filtered[name] = value
        self.key, self.stamp, self.ordinal = key, stamp, frame['ordinal']
        return {'dt_s': dt, 'reset_reason': reason, 'nodes': filtered}

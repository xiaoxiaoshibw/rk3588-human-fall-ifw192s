"""Causal geometric fall evidence, Python 3.8 + NumPy. Offline candidate only.

All lengths are metres, times seconds. The supplied plane must be bound to the
input coordinate frame by the caller. No plane is fitted from future frames.
Unknown observations break descent/hold evidence; they do not prove recovery.
"""
import math
from collections import deque

import numpy as np

from human_pointset import valid_binding


DEFAULTS = dict(minimum_points=10, max_gap_s=0.5, upright_deg=30.0,
                low_deg=65.0, low_span_m=1.10, low_height_m=0.8,
                drop_m=0.35, descent_s=2.0, hold_s=0.3, recovery_s=0.5)


def frame_geometry(points, normal, offset_m, minimum_points=10):
    """Ground-relative evidence without changing point membership or scaling."""
    p, n = np.asarray(points, dtype=np.float64), np.asarray(normal, dtype=np.float64)
    if (n.shape != (3,) or not np.isfinite(n).all() or
            not isinstance(offset_m, (int, float)) or not math.isfinite(offset_m) or
            np.any(np.abs(n) > 1e100) or np.linalg.norm(n) < 1e-12):
        raise ValueError('Expected explicit finite upward ground plane')
    norm = float(np.linalg.norm(n))
    n, d = n / norm, float(offset_m) / norm
    if p.ndim != 2 or p.shape[1] != 3:
        raise ValueError('Expected N,3 target points')
    quality = dict(points=len(p), finite=bool(np.isfinite(p).all()))
    if len(p) < minimum_points or not quality['finite']:
        return dict(quality, valid=False, reason='insufficient_or_invalid_points')
    centre = p.mean(0)
    centred = p - centre
    values, vectors = np.linalg.eigh(centred.T @ centred / len(p))
    heights = p @ n + d
    # Axis ambiguity is not a missing height observation. Keep measured geometry
    # and mask only orientation; an almost isotropic crop must not become upright.
    axis_valid = bool(values[-1] > 1e-12 and values[-1] >= 1.2 * max(values[-2], 1e-12))
    angle = (math.degrees(math.acos(min(1.0, abs(float(vectors[:, -1] @ n)))))
             if axis_valid else None)
    return dict(quality, valid=True, centroid_height_m=float(centre @ n + d),
                inclination_deg=angle, axis_valid=axis_valid, vertical_span_m=float(np.ptp(heights)),
                eigenvalues=values.tolist())


class FallGeometryRuntime:
    """Upright -> measured descent -> low hold; release only after upright hold."""
    def __init__(self, normal=None, offset_m=None, **settings):
        unknown = set(settings) - set(DEFAULTS)
        if unknown:
            raise ValueError('Unknown geometry settings: %s' % sorted(unknown))
        self.settings = dict(DEFAULTS, **settings)
        s = self.settings
        if (not all(isinstance(v, (int, float)) and not isinstance(v, bool) and
                    math.isfinite(v) and v > 0 for v in s.values()) or
                not isinstance(s['minimum_points'], int) or s['minimum_points'] < 3 or
                not s['upright_deg'] < s['low_deg'] <= 90):
            raise ValueError('Invalid geometry settings')
        self.normal, self.offset_m = normal, offset_m
        if normal is not None:
            frame_geometry(np.empty((0, 3)), normal, offset_m, s['minimum_points'])
        self.counter = 0
        self.reset()

    def reset(self):
        self.binding = self.last_time = self.previous = None
        self.active_event = None
        self._clear_motion()

    def _clear_motion(self):
        self.anchor = self.middle_time = self.low_since = self.recovery_since = None
        self.middle_basis = None
        self.upright_samples = deque()
        self.height_samples = deque()
        self.previous = None

    def push(self, points, timestamp, identity, generation, calibration, observed=True, measurements=None):
        key = (identity, generation, calibration)
        result = dict(state='unknown', new_event=None, event_id=None, evidence=None,
                      observed=bool(observed), confirmed_enabled=False)
        if not all(valid_binding(v) for v in key):
            self.reset()
            return dict(result, reason='invalid_binding')
        if key != self.binding:
            self.reset()
            self.binding = key
        result['event_id'] = self.active_event
        if not isinstance(timestamp, (int, float, np.integer, np.floating)) or not math.isfinite(timestamp):
            self._clear_motion()
            self.last_time = None
            return dict(result, reason='invalid_time')
        timestamp = float(timestamp)
        dt = None if self.last_time is None else timestamp - self.last_time
        self.last_time = timestamp
        if dt is not None and (dt <= 0 or dt > self.settings['max_gap_s']):
            self._clear_motion()
            return dict(result, reason='time_discontinuity', dt_s=dt)
        if not observed or (self.normal is None and measurements is None):
            self._clear_motion()
            return dict(result, reason='unobserved' if not observed else 'missing_ground', dt_s=dt)
        evidence = (frame_geometry(points, self.normal, self.offset_m, self.settings['minimum_points'])
                    if measurements is None else dict(measurements))
        if measurements is not None and evidence.get('valid'):
            if (not all(isinstance(evidence.get(k), bool) for k in ('upright', 'low', 'middle')) or
                    sum(evidence[k] for k in ('upright', 'low', 'middle')) > 1 or
                    not isinstance(evidence.get('centroid_height_m'), (int, float)) or
                    not math.isfinite(evidence['centroid_height_m'])):
                raise ValueError('Invalid precomputed evidence')
        result.update(evidence=evidence, dt_s=dt)
        if not evidence['valid']:
            self._clear_motion()
            return dict(result, reason=evidence['reason'])
        height = evidence['centroid_height_m']
        evidence['vertical_velocity_m_s'] = ((height - self.previous[1]) / (timestamp - self.previous[0])
                                            if self.previous is not None else None)
        self.previous = (timestamp, height)
        self.height_samples.append((timestamp, height))
        s = self.settings
        if measurements is None:
            angle = evidence['inclination_deg']
            upright = angle is not None and angle <= s['upright_deg']
            low_height = evidence['vertical_span_m'] <= s['low_span_m'] and height <= s['low_height_m']
            low = bool(low_height and (angle is not None and angle >= s['low_deg'] or
                                      angle is None and self.low_since is not None))
            evidence['low_hold_by_height_continuity'] = bool(low and angle is None)
            middle = angle is not None and s['upright_deg'] < angle < s['low_deg']
        else:
            upright, low, middle = (evidence[k] for k in ('upright', 'low', 'middle'))
        if upright:
            self.upright_samples.append((timestamp, height))
            self.middle_time = self.low_since = None
            self.middle_basis = None
            if self.recovery_since is None:
                self.recovery_since = timestamp
            if timestamp - self.recovery_since >= s['recovery_s']:
                self.active_event = None
        else:
            self.recovery_since = None
        while self.upright_samples and timestamp-self.upright_samples[0][0] > s['descent_s']:
            self.upright_samples.popleft()
        while self.height_samples and timestamp-self.height_samples[0][0] > s['descent_s']:
            self.height_samples.popleft()
        # A vertical body can already be descending. Overwriting its standing
        # reference on each upright-looking frame erases the height loss itself.
        self.anchor = max(self.upright_samples, key=lambda row: row[1]) if self.upright_samples else None
        if self.anchor is None:
            self.middle_time = self.low_since = None
            self.middle_basis = None
        if self.anchor is not None and middle and self.middle_time is None:
            self.middle_time = timestamp
            self.middle_basis = 'precomputed_transition' if measurements is not None else 'measured_angle'
        if self.anchor is not None and self.middle_time is None:
            drop = self.anchor[1]-height
            if drop >= s['drop_m']:
                # Real intermediate heights can prove a sampled process even if
                # PCA is undefined throughout the rotation. The middle half of
                # the measured drop excludes small standing-height noise at the
                # endpoints; no interpolated height or angle is invented.
                measured_middle = [t for t,h in self.height_samples
                                   if self.anchor[0] < t < timestamp and
                                   height+.25*drop <= h <= self.anchor[1]-.25*drop]
                if measured_middle:
                    self.middle_time = min(measured_middle)
                    self.middle_basis = 'measured_intermediate_height'
        descent = (self.anchor is not None and self.middle_time is not None and
                   self.anchor[1] - height >= s['drop_m'])
        if low and descent:
            if self.low_since is None:
                self.low_since = timestamp
            if timestamp - self.low_since + 1e-9 >= s['hold_s'] and self.active_event is None:
                self.counter += 1
                self.active_event = 'geometry-candidate:%d' % self.counter
                result['new_event'] = dict(event_id=self.active_event, kind='geometry_fall_candidate',
                                           onset_evidence_s=self.middle_time, alarm_s=timestamp,
                                           process_evidence=self.middle_basis,
                                           physically_verified=False)
        else:
            self.low_since = None
        state = ('fall_candidate_active' if self.active_event is not None else
                 'low_hold_pending' if low and descent else
                 'low_without_descent' if low else 'upright' if upright else
                 'orientation_unknown' if measurements is None and angle is None else 'transition')
        return dict(result, state=state, event_id=self.active_event, descent_evidence=descent,
                    low_hold_elapsed_s=timestamp-self.low_since if self.low_since is not None else 0.,
                    descent_process_basis=self.middle_basis,
                    height_anchor_s=self.anchor[0] if self.anchor else None,
                    height_anchor_m=self.anchor[1] if self.anchor else None)

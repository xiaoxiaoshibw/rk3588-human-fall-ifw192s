"""Binary fall candidate sidecar. Python 3.8 + NumPy, no production state writes.

Models use synthetic or public sequence labels, not frame-labelled fall onset.
A candidate event is a model hypothesis, never a physically verified fall alarm.
"""
import hashlib
import json
import math
from pathlib import Path

import numpy as np

from human_pointset import valid_binding
from lidar_numpy_runtime import CausalCache, NumpyForest, summarize, summarize_ordered


def file_sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            digest.update(block)
    return digest.hexdigest()


class FallEpisodeLatch:
    """Fixed consecutive-window votes; no invented physical duration or onset GT."""
    def __init__(self, high=0.8, low=0.2, positive_windows=3, release_windows=5):
        if (not math.isfinite(high) or not math.isfinite(low) or not 0 <= low < high <= 1 or
                not isinstance(positive_windows, int) or isinstance(positive_windows, bool) or positive_windows < 1 or
                not isinstance(release_windows, int) or isinstance(release_windows, bool) or release_windows < 1):
            raise ValueError('Invalid probability thresholds or window vote counts')
        self.high, self.low = high, low
        self.positive_windows, self.release_windows = positive_windows, release_windows
        self.counter = 0
        self.reset()

    def reset(self):
        self.positive_count = self.negative_count = 0
        self.active_event_id = None
        self.binding = None

    def gap(self):
        # Quality gaps break continuous votes, not an unrecovered same-target episode.
        self.positive_count = self.negative_count = 0

    def update(self, probability, binding):
        if not valid_binding(binding):
            raise ValueError('Missing episode binding')
        if not math.isfinite(probability) or not 0 <= probability <= 1:
            self.gap()
            raise ValueError('Invalid fall probability')
        if binding != self.binding:
            self.reset()
            self.binding = binding
        self.positive_count = self.positive_count + 1 if probability >= self.high else 0
        self.negative_count = self.negative_count + 1 if probability <= self.low else 0
        event = None
        if self.positive_count >= self.positive_windows and self.active_event_id is None:
            self.counter += 1
            prefix = hashlib.sha256(repr(binding).encode()).hexdigest()[:16]
            self.active_event_id = 'ml-candidate:%s:%d' % (prefix, self.counter)
            event = {'kind': 'ml_fall_candidate', 'event_id': self.active_event_id,
                     'fall_probability': float(probability), 'physically_verified': False}
        if self.negative_count >= self.release_windows:
            self.active_event_id = None
        state = ('fall_candidate_active' if self.active_event_id is not None else
                 'nonfall_candidate' if probability <= self.low else 'uncertain')
        return {'state': state, 'fall_probability': float(probability),
                'positive_votes': self.positive_count, 'negative_votes': self.negative_count,
                'event_id': self.active_event_id, 'new_event': event}


def load_candidate_runtime(manifest_path, ground=None):
    """Select an explicit schema; legacy RF/MIL behavior remains unchanged."""
    doc = json.loads(Path(manifest_path).read_text(encoding='utf-8'))
    if doc.get('task') == 'geometry_event_gru_v1':
        from event_model_numpy import EventEvidenceRuntime
        return EventEvidenceRuntime(manifest_path, ground=ground)
    return FallCandidateRuntime(manifest_path)


class FallCandidateRuntime:
    def __init__(self, manifest_path):
        manifest_path = Path(manifest_path)
        self.manifest_sha256 = file_sha256(manifest_path)
        self.manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
        doc = self.manifest
        if (doc.get('task') not in ('synthetic_sequence_fall_vs_nonfall', 'laseract_sequence_falling_vs_other') or
                doc.get('feature_schema') not in ('sequence_xyz_v1', 'sequence_ordered_xyz_v1') or doc.get('positive_class') != 1):
            raise ValueError('Expected explicit binary fall label/schema contract')
        path = manifest_path.parent/doc['model']
        self.model_sha256 = file_sha256(path)
        if self.model_sha256 != doc['model_sha256']:
            raise ValueError('Model SHA mismatch')
        model_format = doc.get('model_format', 'numpy_forest_v1')
        if doc['feature_schema'] == 'sequence_ordered_xyz_v1' and model_format != 'numpy_mil_v1':
            raise ValueError('Ordered schema requires an explicit MIL model contract')
        if model_format == 'numpy_forest_v1':
            self.model = NumpyForest(path)
        elif model_format == 'numpy_mil_v1':
            from fall_mil_numpy import NumpyMIL
            self.model = NumpyMIL(path)
        else:
            raise ValueError('Unknown candidate model format')
        if not np.array_equal(self.model.classes, [0, 1]):
            raise ValueError('Expected classes 0=nonfall, 1=fall; action IDs are not fall labels')
        self.cache = CausalCache(doc['window_frames'], doc['max_gap_s'])
        self.minimum_frames = doc.get('minimum_frames', doc['window_frames'])
        if (not isinstance(self.minimum_frames, int) or isinstance(self.minimum_frames, bool) or
                not 5 <= self.minimum_frames <= doc['window_frames']):
            raise ValueError('Invalid minimum causal context')
        self.ordered = doc['feature_schema'] == 'sequence_ordered_xyz_v1'
        if self.ordered and self.minimum_frames < 6:
            raise ValueError('Ordered schema needs six observed frames')
        self.latch = FallEpisodeLatch(**doc['episode'])
        self.key = None

    def reset(self):
        self.cache.clear()
        self.latch.reset()
        self.key = None

    def _unknown(self, reason):
        self.cache.clear()
        self.latch.gap()
        return self._result({'state': 'unknown', 'reason': reason, 'fall_probability': None,
                             'event_id': self.latch.active_event_id, 'new_event': None})

    def _result(self, result):
        return dict(result, cached_frames=len(self.cache.frames), model_sha256=self.model_sha256,
                    manifest_sha256=self.manifest_sha256, stream_binding=self.key,
                    confirmed_enabled=False, validity='UNVERIFIED_TARGET_DOMAIN',
                    training_scope=self.manifest['task']+'; sequence labels are not frame fall onset GT')

    def push(self, points, timestamp, identity, generation, calibration, observed=True):
        key = (identity, generation, calibration)
        if not all(valid_binding(value) for value in key):
            self.reset()
            return self._unknown('invalid_binding')
        if key != self.key:
            self.reset()
            self.key = key
        if not isinstance(observed, (bool, np.bool_)):
            return self._unknown('invalid_observed_flag')
        if not observed:
            return self._unknown('not_measured_locked_target')
        if np.iscomplexobj(points):
            return self._unknown('invalid_points')
        try:
            if not math.isfinite(timestamp):
                return self._unknown('invalid_time')
            if self.cache.last_time is not None:
                if timestamp <= self.cache.last_time:
                    return self._unknown('nonincreasing_time')
                if timestamp-self.cache.last_time > self.cache.max_gap_s:
                    self.cache.clear()
                    self.latch.gap()
            with np.errstate(over='raise', invalid='raise', divide='raise'):
                feature = self.cache.push(points, timestamp, identity, generation, calibration)
                if self.ordered:
                    feature = (summarize_ordered(self.cache.frames)
                               if len(self.cache.frames) >= self.minimum_frames else None)
                elif feature is None and len(self.cache.frames) >= self.minimum_frames:
                    feature = summarize(self.cache.frames)
        except (TypeError, ValueError, OverflowError, FloatingPointError, np.linalg.LinAlgError):
            return self._unknown('invalid_points_or_time')
        if feature is None:
            return self._result({'state': 'warming', 'fall_probability': None,
                                 'event_id': self.latch.active_event_id, 'new_event': None})
        try:
            probability = self.model.predict_proba(feature[None])[0, 1]
            result = self.latch.update(float(probability), (self.manifest_sha256, self.key))
        except (ValueError, FloatingPointError):
            return self._unknown('invalid_model_input_or_output')
        if result['new_event'] is not None:
            result['new_event'].update(source_stamp_s=float(timestamp), stream_binding=self.key,
                                      model_sha256=self.model_sha256, manifest_sha256=self.manifest_sha256)
        return self._result(result)

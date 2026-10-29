"""Causal single-target track + fall state for the active project replay.

Reuses the frozen HF-05/HF-06 pure modules in ``src/human_fall_detection/core``:
``TargetTracker`` (association only), ``FeatureExtractor`` (measured height and
descent) and ``FallStateMachine``. No node coordinate is smoothed or predicted;
a predicted track position is never fed as an observation and never used as
fall evidence. ``confirmed`` stays disabled (no human-labelled stance/fall truth
for this session), so the machine can at most report ``suspected``.

A stance baseline uses the shared 3s / 15 measured-sample collector, including
position spread, height stability and vertical span checks. It is bound to
session/track/epoch/selection/generation and the
ground transform, so it can never be inherited by another target.
"""
import sys
import time

import numpy as np

from project_dependencies import ROOT

CORE = ROOT / 'src/human_fall_detection'
if str(CORE) not in sys.path:
    sys.path.insert(0, str(CORE))

from core.fall_state import FallStateMachine  # noqa: E402
from core.features import FeatureExtractor  # noqa: E402
from core.tracking import TargetTracker
from core.baseline import StanceBaselineCollector  # noqa: E402
from core.target_acquisition import TargetAcquisition  # noqa: E402

BODY_MIN_POINTS = 30            # same candidate floor as the frozen region chain


class FallRuntime:
    def __init__(self, session_id, calibration_version, acquisition_settings=None):
        self.session_id = session_id
        self.calibration_version = calibration_version
        self.tracker = TargetTracker(session_id)
        self.acquisition = TargetAcquisition(self.tracker, acquisition_settings)
        self.features = FeatureExtractor(session_id)
        self.machine = FallStateMachine(session_id)
        self.timings_s = {}
        self.baseline = None
        self.baseline_collector = StanceBaselineCollector(session_id)
        self._epoch = 0

    def step(self, source_stamp_s, candidate, time_epoch=0, valid=True, *,
             points=None, row_offset=0, frame_seq=None, ground=None, rebuild=None):
        candidates = candidate if isinstance(candidate, list) else ([] if candidate is None else [candidate])
        started = time.perf_counter()
        self._epoch = time_epoch
        snapshot, acquisition, candidate = self.acquisition.step(
            candidates, self._epoch, source_stamp_s,
            calibration_version=self.calibration_version, coordinate_version='RAW/innolidar', valid=valid,
            points=points, row_offset=row_offset, frame_seq=frame_seq, ground=ground,
            rebuild=rebuild)
        associated = time.perf_counter()
        observation = dict(
            source_stamp_s=(float(source_stamp_s) if source_stamp_s is not None
                            and np.isfinite(float(source_stamp_s)) else None), time_epoch=self._epoch,
            track_id=snapshot['track_id'], track_status=snapshot['track_status'],
            action_generation=snapshot['action_generation'],
            selection_version=snapshot['selection_version'],
            calibration_version=self.calibration_version,
            position_predicted=snapshot['position_predicted'],
            candidate=None if snapshot['position_predicted'] else candidate)
        self.baseline_collector.feed_automatic(observation['candidate'], snapshot, source_stamp_s)
        self.baseline = self.baseline_collector.baseline
        features = self.features.update(observation, self.baseline)
        state = self.machine.update(features, observation, self.baseline)
        self.timings_s = dict(history_association_s=associated-started,
                              baseline_fall_s=time.perf_counter()-associated)
        return dict(
            acquisition=acquisition, target_rows=[] if candidate is None else candidate.get('source_rows', []),
            candidate_history=dict(candidates=self.acquisition.history.ledger,
                                   departed=self.acquisition.history.departed),
            target_candidate_id=None if candidate is None else candidate['candidate_id'],
            track=dict(track_id=snapshot['track_id'], status=snapshot['track_status'],
                       predicted=snapshot['position_predicted'],
                       requires_reselection=snapshot['requires_reselection'],
                       position_ground_m=snapshot['position_m'],
                       prediction_age_s=snapshot['prediction_age_s'],
                       selection_version=snapshot['selection_version'],
                       generation=snapshot['action_generation']),
            fall=dict(status=state['fall_status'], reasons=state['reason_codes'],
                      state_since_source_s=state['state_since_source_s'],
                      event_count=state['event_count'],
                      confirmed_enabled=state['confirmed_enabled'],
                      baseline_ready=self.baseline is not None,
                      height_m=features['height_median_m'],
                      descent_rate_m_s=features['descent_rate_m_s'],
                      near_ground_duration_s=features['near_ground_duration_s'],
                      limitations=state['limitations']),
            candidate=dict(height_m=candidate['height_m'],
                           horizontal_extent_m=candidate['horizontal_extent_m'],
                           point_count=candidate['point_count'],
                           axis=candidate['axis']) if candidate is not None else None)


def body_candidate(points_ground):
    """Measured body candidate from this frame's foreground points (ground frame)."""
    points = np.asarray(points_ground, dtype=float).reshape(-1, 3)
    if len(points) < BODY_MIN_POINTS or not np.isfinite(points).all():
        return None
    z = points[:, 2]
    center = np.median(points, axis=0)
    covariance = np.cov((points - center).T)
    values, vectors = np.linalg.eigh(covariance)
    verticality = None
    ambiguous = True
    if values[-1] > 1e-9 and values[-2] > 1e-9:
        axis = vectors[:, -1]
        verticality = float(abs(axis[2]))
        ambiguous = bool(values[-1] / values[-2] < 1.05)
    return dict(
        candidate_id='body', ground_relative_available=True,
        center_reference_m=center.tolist(),
        height_m=dict(min=float(z.min()), p10=float(np.quantile(z, .10)),
                      median=float(np.median(z)), p90=float(np.quantile(z, .90)),
                      max=float(z.max())),
        horizontal_extent_m=dict(max=float(max(np.ptp(points[:, 0]), np.ptp(points[:, 1])))),
        point_count=int(len(points)),
        axis=dict(ambiguous=ambiguous, verticality=verticality))

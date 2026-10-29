"""Minimal deterministic replay entry for the HF-04..06 geometry chain (HF-06).

This composes the pure modules into one frame-by-frame callable so a fixed
recording replays identically. It is not a ROS node and it performs no selection
of its own by default: the target is ``unselected`` unless an explicit initial
candidate/position is supplied, or the caller opts into the synthetic-fixture
auto-selection (clearly labelled test-only, never an operator confirmation). A
lost/ambiguous lock is never silently re-acquired. Confirmed output stays gated
by the fall-state mode flags.
"""

import hashlib
import json
import time

import numpy as np
from core.baseline import StanceBaselineCollector
from core.roi import RoiController, resolve_settings as resolve_roi

try:  # pragma: no cover - import shim
    from core.fall_state import FallStateMachine
    from core.features import FeatureExtractor
    from core.lidar_candidates import (build_snapshot, ground_frame_eligible,
                                       prepare_background, rebuild_candidate)
    from core.tracking import TargetTracker
    from core.target_acquisition import TargetAcquisition
except ImportError:  # pragma: no cover
    from fall_state import FallStateMachine
    from features import FeatureExtractor
    from lidar_candidates import (build_snapshot, ground_frame_eligible,
                                  prepare_background, rebuild_candidate)
    from tracking import TargetTracker
    from core.target_acquisition import TargetAcquisition


def _ground_version(ground):
    """Content identity of the plane the ROI is defined in (no private state)."""
    if ground is None:
        return None
    try:
        encoded = json.dumps(ground, sort_keys=True, separators=(',', ':'),
                             allow_nan=False)
    except (TypeError, ValueError):
        return None
    return hashlib.sha256(encoded.encode('utf8')).hexdigest()


class ReplayPipeline:
    def __init__(self, session_id, settings=None, baseline=None, *,
                 auto_select=False, initial_candidate_id=None, initial_position_m=None,
                 target_mode="manual"):
        sections = settings or {}
        self.session_id = session_id
        self.tracker = TargetTracker(session_id, sections.get("tracking"))
        if target_mode not in ("manual", "automatic"):
            raise ValueError("target_mode must be manual or automatic")
        self.target_mode = target_mode
        self.acquisition = TargetAcquisition(self.tracker, sections.get("acquisition"))
        self.features = FeatureExtractor(session_id, sections.get("features"))
        self.fall = FallStateMachine(session_id, sections.get("fall"))
        self.candidate_settings = sections.get("candidates")
        self.baseline = baseline
        # The ROI is a separate, opt-in section. With no section (or with
        # enabled: false) the controller is never constructed and build_snapshot
        # is called exactly as before, so the deterministic payload is unchanged.
        self.roi_settings = (None if sections.get("roi") is None
                             else resolve_roi(sections.get("roi")))
        self.roi_enabled = bool(self.roi_settings and self.roi_settings["enabled"])
        self.roi_controller = RoiController(self.roi_settings) if self.roi_enabled else None
        # Optional caller-owned dict that receives per-stage seconds. It never
        # changes the fingerprint/output and is only for offline measurement.
        self.timing_sink = None
        self.baseline_collector = StanceBaselineCollector(session_id, sections.get('baseline'))
        self.background = None
        self.ground = None
        self.auto_select = bool(auto_select)
        self.initial_candidate_id = initial_candidate_id
        self.initial_position_m = initial_position_m
        self.initial_selection_source = ("fixture_auto" if auto_select
                                         else "explicit" if (
                                             initial_candidate_id is not None
                                             or initial_position_m is not None)
                                         else None)
        self._started = False

    @property
    def background(self):
        return self._background

    @background.setter
    def background(self, value):
        self._background = prepare_background(value)

    def _initial_pick(self, candidates):
        if self.initial_candidate_id is not None:
            for candidate in candidates:
                if candidate["candidate_id"] == self.initial_candidate_id:
                    return candidate
            return None
        if self.auto_select and candidates:
            return min(candidates, key=lambda item: (-item["point_count"],
                                                     item["candidate_id"]))
        return None

    def step(self, points, source_stamp_s, time_epoch, seq=None):
        started_step = time.perf_counter()
        sink = self.timing_sink if isinstance(self.timing_sink, dict) else None
        timings = sink if sink is not None else {}
        want_stage_timings = self.roi_controller is not None or sink is not None
        roi_decision = None
        if self.roi_controller is not None:
            started = time.perf_counter()
            roi_decision = self.roi_controller.advance(
                self.tracker.snapshot(), source_stamp_s=source_stamp_s,
                ground=self.ground, frame_id="innolidar",
                binding=(self.session_id, time_epoch, "innolidar",
                         _ground_version(self.ground)))
            timings["roi_controller_s"] = time.perf_counter() - started
        snapshot = build_snapshot(
            points, self.candidate_settings, session_id=self.session_id,
            time_epoch=time_epoch, snapshot_id="seq:{}".format(seq),
            seq=seq, source_stamp_s=source_stamp_s, ground=self.ground,
            background=self.background,
            roi=roi_decision,
            timings=timings if want_stage_timings else None)
        candidates = snapshot["candidates"]
        if self.target_mode == "manual" and not self._started and self.tracker.track_status == "unselected":
            pick = self._initial_pick(candidates)
            if pick is not None:
                self.tracker.select("t0001", time_epoch, candidate=pick,
                                    selection_version=self.tracker.selection_version + 1,
                                    source_stamp_s=source_stamp_s,
                                    receive_s=source_stamp_s)
                self._started = True
            elif self.initial_position_m is not None:
                self.tracker.select("t0001", time_epoch,
                                    position_m=self.initial_position_m,
                                    selection_version=self.tracker.selection_version + 1,
                                    source_stamp_s=source_stamp_s,
                                    receive_s=source_stamp_s)
                self._started = True
        acquisition = None
        observed = None
        if self.target_mode == "automatic":
            version=snapshot['calibration']['calibration_id']
            eligible=self.ground is None or ground_frame_eligible(self.ground,'innolidar')
            if version is None and self.ground is not None:
                try:
                    encoded=json.dumps(self.ground,sort_keys=True,separators=(',',':'),allow_nan=False)
                    version='ground-only-'+hashlib.sha256(encoded.encode('utf8')).hexdigest()[:16]
                except (ValueError,TypeError):
                    eligible=False
            generation = self.tracker.action_generation
            rebuild_target = lambda local_rows: rebuild_candidate(
                points, np.asarray(local_rows, dtype=np.int64), self.candidate_settings,
                ground=self.ground)
            state, acquisition, observed = self.acquisition.step(
                candidates, time_epoch, source_stamp_s,
                calibration_version=version,valid=eligible,
                coordinate_version=snapshot['coordinate']['source_frame'],
                points=points, frame_seq=seq, ground=self.ground,
                rebuild=rebuild_target)
            if state['action_generation'] != generation:
                self.baseline = None
        else:
            state = self.tracker.update(candidates, time_epoch, source_stamp_s=source_stamp_s,
                                        receive_s=source_stamp_s)
        if self.target_mode == "manual" and state["candidate_id"] is not None and state['track_status'] == 'locked' and not state['position_predicted']:
            for candidate in candidates:
                if candidate["candidate_id"] == state["candidate_id"]:
                    observed = candidate
                    break
        if state['track_status'] != 'locked' or state['position_predicted']:
            observed = None
        if self.target_mode == 'automatic':
            self.baseline_collector.feed_automatic(observed, state, source_stamp_s)
            self.baseline = self.baseline_collector.baseline
        feature_block = self.features.update({
            "candidate": observed,
            "track_id": state["track_id"],
            "track_status": state["track_status"],
            "position_predicted": state["position_predicted"],
            "time_epoch": time_epoch,
            "action_generation": state["action_generation"],
            "selection_version": state["selection_version"],
            "calibration_version": state["calibration_version"],
            "source_stamp_s": source_stamp_s,
        }, self.baseline)
        fall_block = self.fall.update(feature_block, {
            "source_stamp_s": source_stamp_s,
            "time_epoch": time_epoch,
            "action_generation": state["action_generation"],
            "selection_version": state["selection_version"],
            "calibration_version": state["calibration_version"],
            "track_id": state["track_id"],
            "track_status": state["track_status"],
        }, self.baseline)
        if self.roi_controller is not None:
            # Only a measured, non-predicted observation advances the controller.
            if observed is not None and state["track_status"] == "locked" \
                    and not state["position_predicted"]:
                center = observed.get("center_reference_m") \
                    or observed.get("center_source_m")
                extent = (observed.get("horizontal_extent_m") or {}).get("max")
                self.roi_controller.note_measured(
                    center, source_stamp_s, support_extent_m=extent,
                    velocity_m_s=state.get("velocity_m_s"))
            timings["pipeline_step_s"] = time.perf_counter() - started_step
        result = {"snapshot_id": snapshot["snapshot_id"], "track": state,
                "features": feature_block, "fall": fall_block,
                "acquisition": acquisition,
                "target_source_rows": [] if observed is None else observed['evidence_indices'],
                "selection_source": "automatic_acquisition" if self.target_mode == "automatic" else self.initial_selection_source}
        if self.roi_controller is not None:
            result["roi"] = dict(snapshot.get("roi") or {},
                                 state=self.roi_controller.state,
                                 reset_reason=self.roi_controller.reset_reason)
            result["timings_s"] = dict(timings)
        return result

    def run(self, frames, times=None, time_epoch=0):
        outputs = []
        for index, frame in enumerate(frames):
            source_stamp_s = None if times is None else float(times[index])
            outputs.append(self.step(np.asarray(frame, dtype=np.float64),
                                     source_stamp_s, time_epoch, seq=index))
        return outputs

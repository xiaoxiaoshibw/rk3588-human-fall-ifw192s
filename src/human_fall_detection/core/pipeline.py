"""Minimal deterministic replay entry for the HF-04..06 geometry chain (HF-06).

This composes the pure modules into one frame-by-frame callable so a fixed
recording replays identically. It is not a ROS node and it performs no selection
of its own by default: the target is ``unselected`` unless an explicit initial
candidate/position is supplied, or the caller opts into the synthetic-fixture
auto-selection (clearly labelled test-only, never an operator confirmation). A
lost/ambiguous lock is never silently re-acquired. Confirmed output stays gated
by the fall-state mode flags.
"""

import numpy as np

try:  # pragma: no cover - import shim
    from core.fall_state import FallStateMachine
    from core.features import FeatureExtractor
    from core.lidar_candidates import build_snapshot
    from core.tracking import TargetTracker
except ImportError:  # pragma: no cover
    from fall_state import FallStateMachine
    from features import FeatureExtractor
    from lidar_candidates import build_snapshot
    from tracking import TargetTracker


class ReplayPipeline:
    def __init__(self, session_id, settings=None, baseline=None, *,
                 auto_select=False, initial_candidate_id=None, initial_position_m=None):
        sections = settings or {}
        self.session_id = session_id
        self.tracker = TargetTracker(session_id, sections.get("tracking"))
        self.features = FeatureExtractor(session_id, sections.get("features"))
        self.fall = FallStateMachine(session_id, sections.get("fall"))
        self.candidate_settings = sections.get("candidates")
        self.baseline = baseline
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
        snapshot = build_snapshot(
            points, self.candidate_settings, session_id=self.session_id,
            time_epoch=time_epoch, snapshot_id="seq:{}".format(seq),
            seq=seq, source_stamp_s=source_stamp_s, ground=self.ground,
            background=self.background)
        candidates = snapshot["candidates"]
        if not self._started and self.tracker.track_status == "unselected":
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
        state = self.tracker.update(candidates, time_epoch, source_stamp_s=source_stamp_s,
                                    receive_s=source_stamp_s)
        observed = None
        if state["candidate_id"] is not None:
            for candidate in candidates:
                if candidate["candidate_id"] == state["candidate_id"]:
                    observed = candidate
                    break
        feature_block = self.features.update({
            "candidate": observed,
            "track_id": state["track_id"],
            "track_status": state["track_status"],
            "position_predicted": state["position_predicted"],
            "time_epoch": time_epoch,
            "action_generation": state["action_generation"],
            "calibration_version": state["calibration_version"],
            "source_stamp_s": source_stamp_s,
        }, self.baseline)
        fall_block = self.fall.update(feature_block, {
            "source_stamp_s": source_stamp_s,
            "time_epoch": time_epoch,
            "action_generation": state["action_generation"],
            "track_id": state["track_id"],
            "track_status": state["track_status"],
        }, self.baseline)
        return {"snapshot_id": snapshot["snapshot_id"], "track": state,
                "features": feature_block, "fall": fall_block,
                "selection_source": self.initial_selection_source}

    def run(self, frames, times=None, time_epoch=0):
        outputs = []
        for index, frame in enumerate(frames):
            source_stamp_s = None if times is None else float(times[index])
            outputs.append(self.step(np.asarray(frame, dtype=np.float64),
                                     source_stamp_s, time_epoch, seq=index))
        return outputs

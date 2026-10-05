"""Single-target lock, prediction and lifecycle for an operator-chosen target (HF-05).

The operator selects one candidate; the tracker keeps one ``track_id`` for the
session and follows it with a bounded constant-velocity prediction and a
distance gate. It never swaps people: a pose/size jump or a near-equal pair of
candidates yields ``ambiguous``/``occluded``/``lost`` and asks for a fresh
operator selection instead of silently re-binding to another cluster.

Time/continuity rules (HF04-06 R2):

- The occlusion/clock check runs *before* association, using the elapsed time
  since the last valid *measured* observation in a single clock domain (source
  stamps when available, else receive time). Past the window the track is
  ``lost`` with ``requires_reselection`` and no candidate is bound, so a late
  near candidate cannot bypass the timeout by arriving with a match.
- A prediction is always recomputed from the last measured position/velocity/
  time, never by integrating the previous prediction again.
- A negative elapsed time (clock regression) is a clock fault, not a zero dt:
  the track goes ``lost`` instead of associating on a bad dt.
- A predicted position is flagged and is never a fall observation.

Operator actions, a clock-epoch change, ambiguity and loss all reset the target
action history (the generation counter increments); already-published fall
events live elsewhere and are never deleted here.
"""

import math
from collections import deque

import numpy as np

try:  # pragma: no cover - import shim
    from core.association import associate_tracks, resolve_settings as resolve_assoc
except ImportError:  # pragma: no cover
    from association import associate_tracks, resolve_settings as resolve_assoc

TRACK_STATUSES = ("unselected", "locked", "occluded", "ambiguous", "lost")
KIND = "target_state"
SCHEMA_VERSION = 1

DEFAULT_SETTINGS = {
    "gate_m": 0.8,
    "ambiguity_margin_m": 0.2,
    "max_speed_m_s": 2.5,
    "occlusion_timeout_s": 1.5,
    "lost_timeout_s": 3.0,
    "velocity_smoothing": 0.5,
    "max_size_ratio": 3.0,
    "history_size": 64,
}
_POSITIVE = ("gate_m", "ambiguity_margin_m", "max_speed_m_s", "occlusion_timeout_s",
             "lost_timeout_s", "max_size_ratio", "history_size")


def resolve_settings(settings=None):
    resolved = dict(DEFAULT_SETTINGS)
    for key, value in (settings or {}).items():
        if key not in resolved:
            raise ValueError("unknown tracking setting: " + str(key))
        resolved[key] = value
    for key in _POSITIVE:
        resolved[key] = float(resolved[key])
    resolved["history_size"] = int(resolved["history_size"])
    if resolved["history_size"] <= 0:
        raise ValueError("history_size must be positive")
    if resolved["lost_timeout_s"] <= resolved["occlusion_timeout_s"]:
        raise ValueError("lost_timeout_s must exceed occlusion_timeout_s")
    for key in ("gate_m", "ambiguity_margin_m", "max_speed_m_s",
                "occlusion_timeout_s", "lost_timeout_s", "max_size_ratio"):
        if not np.isfinite(resolved[key]) or resolved[key] <= 0.0:
            raise ValueError(key + " must be a positive finite number")
    return resolved


def candidate_view(candidate):
    """Position/size view of a HF-04 candidate (reference frame when present)."""
    position = candidate.get("center_reference_m") or candidate.get("center_source_m")
    size = None
    extent = candidate.get("horizontal_extent_m")
    if isinstance(extent, dict) and extent.get("max") is not None:
        size = float(extent["max"])
    return {"candidate_id": candidate.get("candidate_id"),
            "position_m": position, "size_m": size}


def _finite(value):
    if value is None:
        return None
    number = float(value)
    return number if math.isfinite(number) else None


class TargetTracker:
    def __init__(self, session_id, settings=None):
        self.session_id = session_id
        self.settings = resolve_settings(settings)
        self.calibration_version = None
        self.track_id = None
        self.track_status = "unselected"
        self.candidate_id = None
        self.position_m = None
        self.velocity_m_s = None
        self.selection_version = 0
        self.position_predicted = False
        self.requires_reselection = False
        self.time_epoch = None
        self._measured_position = None
        self._measured_source_s = None
        self._measured_receive_s = None
        self._occluded_since = None
        self._prediction_age_s = None
        self.time_domain = None
        self.clock_reason = None
        self.action_generation = 0
        self.history_reset_reason = None
        self.action_history = deque(maxlen=self.settings["history_size"])

    def last_measured_source(self):
        """Board-side source stamp of the last measured observation (or None)."""
        return self._measured_source_s

    def _assoc_settings(self):
        keys = ("gate_m", "ambiguity_margin_m", "max_speed_m_s", "max_size_ratio")
        return {key: self.settings[key] for key in keys}

    def _reset_history(self, reason):
        self.action_history.clear()
        self.action_generation += 1
        self.history_reset_reason = reason

    def _elapsed(self, source_stamp_s, receive_s):
        """Elapsed in the target's fixed clock domain since the last measurement.

        The domain is fixed at selection (receive time when available, else
        source stamps for pure offline replay). A current frame whose own value
        in that domain is missing/non-finite returns ``(None, "current_invalid")``
        so the caller refuses the observation instead of switching domains.
        """
        if self.time_domain is None:
            return None, None
        if self.time_domain == "source_stamp_s":
            current = _finite(source_stamp_s)
            measured = self._measured_source_s
        else:
            current = _finite(receive_s)
            measured = self._measured_receive_s
        if current is None:
            return None, "current_invalid"
        if measured is None:
            return None, None
        return current - measured, None

    def note_epoch(self, time_epoch):
        """A changed source epoch is a clock reset: history clears, lock is lost."""
        if self.time_epoch is not None and time_epoch != self.time_epoch:
            self.track_status = "lost"
            self.position_predicted = True
            self.requires_reselection = True
            self._reset_history("time_epoch_changed")
        self.time_epoch = int(time_epoch)

    def select(self, track_id, time_epoch, candidate=None, position_m=None,
               calibration_version=None, selection_version=None,
               source_stamp_s=None, receive_s=None):
        """Lock one operator-chosen candidate (or explicit position) in the session."""
        if track_id is None:
            raise ValueError("track_id is required to lock a target")
        if candidate is not None:
            view = candidate_view(candidate)
            position = view["position_m"]
            self.candidate_id = view["candidate_id"]
        else:
            position = position_m
            self.candidate_id = None
        if position is None:
            raise ValueError("select needs a candidate or an explicit position_m")
        array = np.asarray(position, dtype=np.float64)
        if array.shape != (3,) or not np.all(np.isfinite(array)):
            raise ValueError("position_m must be three finite numbers")
        self.note_epoch(time_epoch)
        self.track_id = track_id
        self.track_status = "locked"
        self.position_m = [float(value) for value in array]
        self.velocity_m_s = None
        self.position_predicted = False
        self.requires_reselection = False
        self.calibration_version = calibration_version
        if selection_version is not None:
            self.selection_version = int(selection_version)
        self._measured_position = array.tolist()
        self._measured_source_s = _finite(source_stamp_s)
        self._measured_receive_s = _finite(receive_s)
        if self._measured_receive_s is not None:
            self.time_domain = "time_received_s"
        elif self._measured_source_s is not None:
            self.time_domain = "source_stamp_s"
        else:
            self.time_domain = None
        self.clock_reason = None
        self._occluded_since = None
        self._prediction_age_s = None
        self._reset_history("operator_select")
        self.action_history.append({"type": "observed", "source_stamp_s": self._measured_source_s})
        return self.snapshot()

    def release(self, reason="operator_release"):
        self.track_id = None
        self.candidate_id = None
        self.track_status = "unselected"
        self.position_m = None
        self.velocity_m_s = None
        self.position_predicted = False
        self.requires_reselection = False
        self._measured_position = None
        self._measured_source_s = None
        self._measured_receive_s = None
        self._occluded_since = None
        self._prediction_age_s = None
        self.time_domain = None
        self.clock_reason = None
        self._reset_history(reason)
        return self.snapshot()

    def _go_lost(self, reason, source_stamp_s=None, receive_s=None):
        self.track_status = "lost"
        self.position_predicted = True
        self.requires_reselection = True
        self._prediction_age_s = None
        self._reset_history(reason)
        if source_stamp_s is not None:
            self._measured_source_s = _finite(source_stamp_s)
        if receive_s is not None:
            self._measured_receive_s = _finite(receive_s)
        return self.snapshot()

    def update(self, candidates, time_epoch, source_stamp_s=None, receive_s=None):
        """Feed one candidate frame; returns the track state after the update."""
        self.note_epoch(time_epoch)
        if self.track_status not in ("locked", "occluded"):
            return self.snapshot()
        if self.track_id is None:
            return self.snapshot()

        elapsed, invalid = self._elapsed(source_stamp_s, receive_s)
        if invalid is not None:
            return self._reject_current(invalid)
        if elapsed is not None:
            if elapsed < 0.0:
                return self._go_lost("clock_regressed", source_stamp_s, receive_s)
            if elapsed > self.settings["lost_timeout_s"]:
                return self._go_lost("lost_timeout", source_stamp_s, receive_s)

        dt = 0.0 if elapsed is None else elapsed
        predicted = self._predict(dt)
        track = {"track_id": self.track_id, "position_m": predicted.tolist(), "size_m": None}
        views = [candidate_view(candidate) for candidate in candidates]
        views = [view for view in views if view["position_m"] is not None]
        association = associate_tracks([track], views, dt, self._assoc_settings())

        if association["matches"]:
            match = association["matches"][0]
            measured = next(view["position_m"] for view in views
                            if view["candidate_id"] == match["candidate_id"])
            self._apply_measured(measured, dt, source_stamp_s, receive_s)
            self.candidate_id = match["candidate_id"]
            return self.snapshot()

        if self.track_id in association["ambiguous_track_ids"]:
            self.track_status = "ambiguous"
            self.position_m = predicted.tolist()
            self.position_predicted = True
            self.requires_reselection = True
            self._prediction_age_s = dt
            self._reset_history("ambiguous")
            return self.snapshot()

        now = _finite(receive_s)
        if now is None:
            now = _finite(source_stamp_s)
        if self._occluded_since is None:
            self._occluded_since = now
        self.position_predicted = True
        self.position_m = predicted.tolist()
        # A predicted position is as old as its last measured anchor, including
        # any gap before the first missing frame was reported.
        self._prediction_age_s = dt
        self.track_status = "occluded"
        return self.snapshot()

    def _reject_current(self, reason):
        """Refuse the current frame's timing without consuming a measurement.

        The last valid measured baseline is kept and the position is reported as
        predicted; the clock domain is never switched to manufacture a valid dt.
        """
        self.track_status = "occluded"
        self.position_predicted = True
        self.position_m = self._predict(0.0).tolist()
        self.clock_reason = reason
        return self.snapshot()

    def _predict(self, dt):
        """Prediction anchored at the last measurement (never re-integrated)."""
        if self._measured_position is None:
            return np.asarray(self.position_m, dtype=np.float64)
        anchor = np.asarray(self._measured_position, dtype=np.float64)
        if self.velocity_m_s is not None:
            return anchor + np.asarray(self.velocity_m_s, dtype=np.float64) * max(0.0, dt)
        return anchor

    def _apply_measured(self, measured, dt, source_stamp_s, receive_s):
        measured = np.asarray(measured, dtype=np.float64)
        previous = np.asarray(self._measured_position, dtype=np.float64)
        if dt > 0.0:
            raw = (measured - previous) / dt
            speed = float(np.linalg.norm(raw))
            if speed > self.settings["max_speed_m_s"]:
                raw = raw * (self.settings["max_speed_m_s"] / speed)
            smoothing = self.settings["velocity_smoothing"]
            if self.velocity_m_s is None:
                self.velocity_m_s = raw.tolist()
            else:
                blended = (1.0 - smoothing) * np.asarray(self.velocity_m_s) + smoothing * raw
                self.velocity_m_s = blended.tolist()
        self.track_status = "locked"
        self.position_m = measured.tolist()
        self.position_predicted = False
        self.requires_reselection = False
        self._measured_position = measured.tolist()
        self._measured_source_s = _finite(source_stamp_s)
        self._measured_receive_s = _finite(receive_s)
        self._occluded_since = None
        self._prediction_age_s = None
        self.action_history.append({"type": "observed",
                                    "source_stamp_s": self._measured_source_s})

    def snapshot(self):
        return {
            "kind": KIND,
            "schema_version": SCHEMA_VERSION,
            "session_id": self.session_id,
            "time_epoch": self.time_epoch,
            "track_id": self.track_id,
            "track_status": self.track_status,
            "candidate_id": self.candidate_id,
            "position_m": None if self.position_m is None else list(self.position_m),
            "position_predicted": bool(self.position_predicted),
            "prediction_age_s": self._prediction_age_s,
            "prediction_stale": (self._prediction_age_s is not None
                                 and self._prediction_age_s > self.settings["occlusion_timeout_s"]),
            "velocity_m_s": None if self.velocity_m_s is None else list(self.velocity_m_s),
            "selection_version": self.selection_version,
            "calibration_version": self.calibration_version,
            "requires_reselection": bool(self.requires_reselection),
            "action_generation": self.action_generation,
            "history_reset_reason": self.history_reset_reason,
            "time_domain": self.time_domain,
            "clock_reason": self.clock_reason,
            "last_measured_source_s": self._measured_source_s,
            "last_measured_receive_s": self._measured_receive_s,
        }

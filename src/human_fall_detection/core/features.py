"""Temporal geometry features for one locked target (HF-06).

The features are derived from the already-computed HF-04 candidate geometry
(ground-relative height quantiles, horizontal extent, PCA verticality) plus a
bounded history of *measured* observations. A predicted/occluded position is
explicitly not an observation: it never advances the history, the near-ground
duration or the descent estimate, so prediction cannot manufacture fall
evidence. A degenerate principal axis stays unknown and is not treated as a
body direction.

A baseline is only consumed when its session/track/epoch/selection/calibration
bindings match the current observation, so another target's ready baseline can
never be inherited. ``reset_now`` is a one-shot flag for the single frame in
which a reset happened; ``history_reset_reason`` is the persistent diagnostic.

The point-cloud centre is a visible-surface cluster centre, not an anatomical
centroid; no skeleton or keypoint is claimed. All durations use device source
seconds, never a fixed frame count.
"""

import numpy as np

try:  # pragma: no cover - import shim
    from core.timebase import linear_fit
except ImportError:  # pragma: no cover
    from timebase import linear_fit

KIND = "target_features"
SCHEMA_VERSION = 1

DEFAULT_SETTINGS = {
    "window_s": 1.2,
    "max_history": 64,
    "low_height_m": 0.7,
    "near_ground_tolerance_m": 0.05,
}

# Every binding is required: a ready baseline missing any of these is not valid
# for any target (the consumer's own session may supply the current session_id).
_BINDING_FIELDS = ("session_id", "track_id", "time_epoch", "selection_version",
                   "action_generation", "calibration_version")


def resolve_settings(settings=None):
    resolved = dict(DEFAULT_SETTINGS)
    for key, value in (settings or {}).items():
        if key not in resolved:
            raise ValueError("unknown feature setting: " + str(key))
        resolved[key] = value
    for key in ("window_s", "low_height_m", "near_ground_tolerance_m"):
        resolved[key] = float(resolved[key])
        if not np.isfinite(resolved[key]) or resolved[key] < 0.0:
            raise ValueError(key + " must be a finite non-negative number")
    resolved["max_history"] = int(resolved["max_history"])
    if resolved["max_history"] <= 0:
        raise ValueError("max_history must be positive")
    return resolved


def baseline_applies(baseline, observation, session_id=None):
    """True when a ready baseline is fully bound to this observation's target.

    Every required binding must be present in the baseline and match the current
    context; a baseline missing any binding is not valid for any target. The
    consumer's own ``session_id`` may supply the current session when the
    observation does not carry one, but it never supplies a missing track/epoch/
    selection/generation/calibration binding.
    """
    if not isinstance(baseline, dict) or baseline.get("status") != "ready":
        return False
    for field in _BINDING_FIELDS:
        bound = baseline.get(field)
        if bound is None:
            return False
        current = observation.get(field)
        if field == "session_id" and current is None:
            current = session_id
        if current is None or bound != current:
            return False
    return True


class FeatureExtractor:
    def __init__(self, session_id, settings=None):
        self.session_id = session_id
        self.settings = resolve_settings(settings)
        self.history = []
        self.history_reset_reason = None
        self._last_epoch = None
        self._last_generation = None
        self._last_track_id = None
        self._last_calibration_version = None

    def _reset(self, reason):
        self.history = []
        self.history_reset_reason = reason

    def _check_context(self, observation):
        epoch = observation.get("time_epoch")
        generation = observation.get("action_generation")
        track_id = observation.get("track_id")
        calibration_version = observation.get("calibration_version")
        reason = None
        if self._last_epoch is not None and epoch != self._last_epoch:
            reason = "time_epoch_changed"
        elif self._last_generation is not None and generation != self._last_generation:
            reason = "action_history_reset"
        elif self._last_track_id is not None and track_id != self._last_track_id:
            reason = "target_changed"
        elif (self._last_calibration_version is not None
              and calibration_version != self._last_calibration_version):
            reason = "calibration_changed"
        self._last_epoch = epoch
        self._last_generation = generation
        self._last_track_id = track_id
        self._last_calibration_version = calibration_version
        if reason is not None:
            self._reset(reason)
        return reason

    def _base(self, observation, reset_now):
        return {
            "kind": KIND,
            "schema_version": SCHEMA_VERSION,
            "session_id": self.session_id,
            "time_epoch": observation.get("time_epoch"),
            "track_id": observation.get("track_id"),
            "source_stamp_s": observation.get("source_stamp_s"),
            "observable": False,
            "reason": None,
            "reset_now": bool(reset_now),
            "ground_relative": False,
            "height_m": None,
            "height_median_m": None,
            "horizontal_extent_m": None,
            "axis_verticality": None,
            "axis_ambiguous": True,
            "point_count": None,
            "baseline_height_m": None,
            "baseline_bound": False,
            "height_drop_m": None,
            "descent_rate_m_s": None,
            "near_ground_duration_s": None,
            "history_samples": len(self.history),
            "history_reset_reason": self.history_reset_reason,
        }

    def update(self, observation, baseline=None):
        """Consume one candidate frame and return the derived feature block."""
        reset_now = self._check_context(observation)
        features = self._base(observation, reset_now)
        candidate = observation.get("candidate")
        if observation.get("position_predicted"):
            features["reason"] = "prediction_not_observation"
            return features
        if candidate is None or not candidate.get("ground_relative_available"):
            features["reason"] = "no_ground_or_candidate"
            return features
        height = (candidate.get("height_m") or {}).get("median")
        if height is None:
            features["reason"] = "no_height"
            return features
        source_stamp_s = observation.get("source_stamp_s")
        features["observable"] = True
        features["ground_relative"] = True
        features["height_m"] = candidate.get("height_m")
        features["height_median_m"] = float(height)
        extent = candidate.get("horizontal_extent_m") or {}
        features["horizontal_extent_m"] = extent.get("max")
        axis = candidate.get("axis") or {}
        features["axis_ambiguous"] = bool(axis.get("ambiguous", True))
        features["axis_verticality"] = axis.get("verticality")
        features["point_count"] = candidate.get("point_count")
        bound = baseline if baseline_applies(baseline, observation, self.session_id) else None
        features["baseline_bound"] = bound is not None
        baseline_height = None
        if bound is not None:
            baseline_height = (bound.get("height_m") or {}).get("median")
        features["baseline_height_m"] = None if baseline_height is None else float(baseline_height)
        if source_stamp_s is not None and baseline_height is not None:
            features["height_drop_m"] = float(baseline_height) - float(height)

        if source_stamp_s is not None:
            self.history.append({"source_stamp_s": float(source_stamp_s),
                                 "height_m": float(height)})
            if len(self.history) > self.settings["max_history"]:
                self.history = self.history[-self.settings["max_history"]:]
        features["descent_rate_m_s"] = self._descent_rate()
        features["near_ground_duration_s"] = self._near_ground_duration(source_stamp_s)
        features["history_samples"] = len(self.history)
        return features

    def _descent_rate(self):
        if len(self.history) < 2:
            return None
        current = self.history[-1]["source_stamp_s"]
        window = [sample for sample in self.history
                  if current - sample["source_stamp_s"] <= self.settings["window_s"]]
        if len(window) < 2:
            return None
        fit = linear_fit([sample["source_stamp_s"] for sample in window],
                         [sample["height_m"] for sample in window])
        if fit is None:
            return None
        return float(-fit["slope"])

    def _near_ground_duration(self, source_stamp_s):
        if not self.history or source_stamp_s is None:
            return None
        threshold = self.settings["low_height_m"] + self.settings["near_ground_tolerance_m"]
        if self.history[-1]["height_m"] > threshold:
            return 0.0
        start = self.history[-1]["source_stamp_s"]
        for sample in reversed(self.history):
            if sample["height_m"] <= threshold:
                start = sample["source_stamp_s"]
            else:
                break
        return float(self.history[-1]["source_stamp_s"] - start)

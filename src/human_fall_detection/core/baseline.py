"""Operator stance baseline from stable measured observations (HF-05).

The baseline is collected only from consecutive, valid, measured observations of
the locked target. Predicted/occluded observations and samples from a different
calibration version are refused. An initial lying or too-low target fails
explicitly, and a failed collection stores no baseline (never a fabricated one).

An operator may record intent to treat the current posture as a stance, but that
never bypasses the measured quality gates: a flat low pose (short vertical
extent, low upper height) is refused whether or not it was "confirmed". The
accepted stance must have real measured vertical extent (``p90``/``max`` present
when available) and stable position/height. Durations are in device seconds from
the source stamps, thresholds carry their units, and the ready artifact binds an
independent baseline version plus session/track/epoch/selection/calibration so
another target can never inherit it.
"""

import math

import numpy as np

STATE_IDLE = "idle"
STATE_PENDING = "pending"
STATE_READY = "ready"
STATE_FAILED = "failed"
STATES = (STATE_IDLE, STATE_PENDING, STATE_READY, STATE_FAILED)
BASELINE_KIND = "target_stance_baseline"
SCHEMA_VERSION = 1

DEFAULT_SETTINGS = {
    "require_seconds": 3.0,
    "max_duration_s": 10.0,
    "min_samples": 15,
    "min_point_count": 60,
    "max_position_spread_m": 0.25,
    "height_min_m": 0.8,
    "height_max_m": 2.2,
    "min_stance_upper_m": 0.8,
    "min_stance_span_m": 0.4,
    "max_height_std_m": 0.12,
}


def resolve_settings(settings=None):
    resolved = dict(DEFAULT_SETTINGS)
    for key, value in (settings or {}).items():
        if key not in resolved:
            raise ValueError("unknown baseline setting: " + str(key))
        resolved[key] = value
    for key in ("require_seconds", "max_duration_s", "max_position_spread_m",
                "height_min_m", "height_max_m", "min_stance_upper_m",
                "min_stance_span_m", "max_height_std_m"):
        resolved[key] = float(resolved[key])
        if not np.isfinite(resolved[key]) or resolved[key] <= 0.0:
            raise ValueError(key + " must be a positive finite number")
    resolved["min_samples"] = int(resolved["min_samples"])
    resolved["min_point_count"] = int(resolved["min_point_count"])
    if resolved["min_samples"] <= 0 or resolved["min_point_count"] <= 0:
        raise ValueError("min_samples and min_point_count must be positive")
    if resolved["height_max_m"] <= resolved["height_min_m"]:
        raise ValueError("height_max_m must be greater than height_min_m")
    if resolved["max_duration_s"] <= resolved["require_seconds"]:
        raise ValueError("max_duration_s must exceed require_seconds")
    return resolved


class StanceBaselineCollector:
    def __init__(self, session_id, settings=None):
        self.session_id = session_id
        self.settings = resolve_settings(settings)
        self.status = STATE_IDLE
        self.reason = None
        self.track_id = None
        self.calibration_version = None
        self.time_epoch = None
        self.selection_version = None
        self.action_generation = None
        self.operator_confirmed = False
        self.start_source_s = None
        self.samples = []
        self.baseline = None
        self.retired = []
        self._baseline_counter = 0

    def invalidate(self, reason):
        """Drop the current baseline *eligibility* (history is retained)."""
        if self.baseline is not None:
            self.retired.append(self.baseline)
        self.status = STATE_IDLE
        self.reason = reason
        self.track_id = None
        self.calibration_version = None
        self.time_epoch = None
        self.selection_version = None
        self.action_generation = None
        self.operator_confirmed = False
        self.start_source_s = None
        self.samples = []
        self.baseline = None
        return self.snapshot()

    def start(self, track_id, calibration_version, start_source_s=None,
              operator_confirmed=False, time_epoch=None, selection_version=None,
              action_generation=None):
        self.status = STATE_PENDING
        self.reason = None
        self.track_id = track_id
        self.calibration_version = calibration_version
        self.operator_confirmed = bool(operator_confirmed)
        self.time_epoch = time_epoch
        self.selection_version = selection_version
        self.action_generation = action_generation
        self.start_source_s = None if start_source_s is None else float(start_source_s)
        self.samples = []
        self.baseline = None
        return self.snapshot()

    def _fail(self, reason):
        self.status = STATE_FAILED
        self.reason = reason
        self.baseline = None
        return self.snapshot()

    def feed(self, observation, source_stamp_s=None, predicted=False, occluded=False):
        if self.status != STATE_PENDING:
            return self.snapshot()
        if observation.get("track_id") != self.track_id:
            return self._fail("target_changed")
        if predicted or occluded:
            self.reason = "observation_not_measured"
            return self.snapshot()
        if observation.get("calibration_version") != self.calibration_version:
            return self._fail("calibration_version_changed")
        if not observation.get("ground_relative"):
            return self._fail("ground_unavailable")
        point_count = observation.get("point_count")
        height_block = observation.get("height_m") or {}
        height = height_block.get("median")
        position = observation.get("position_m")
        if point_count is None or point_count < self.settings["min_point_count"]:
            return self._fail("low_point_count")
        if height is None or position is None:
            return self._fail("missing_geometry")
        height = float(height)
        upper = height_block.get("max")
        if upper is None:
            upper = height_block.get("p90")
        upper = float(upper) if upper is not None else height
        p10 = height_block.get("p10")
        p90 = height_block.get("p90")
        if not self.samples and upper < self.settings["min_stance_upper_m"]:
            return self._fail("initial_low_posture")
        if upper < self.settings["min_stance_upper_m"]:
            return self._fail("insufficient_stance_height")
        if p10 is not None and p90 is not None \
                and (float(p90) - float(p10)) < self.settings["min_stance_span_m"]:
            return self._fail("insufficient_stance_span")
        if height > self.settings["height_max_m"]:
            return self._fail("height_out_of_range")
        self.samples.append({
            "source_stamp_s": None if source_stamp_s is None else float(source_stamp_s),
            "point_count": int(point_count),
            "height_m": height,
            "upper_m": upper,
            "position_m": [float(value) for value in position],
        })
        return self._evaluate()

    def _evaluate(self):
        if not self.samples:
            return self.snapshot()
        heights = np.array([sample["height_m"] for sample in self.samples], dtype=np.float64)
        positions = np.array([sample["position_m"] for sample in self.samples], dtype=np.float64)
        center = np.median(positions, axis=0)
        spread = float(np.max(np.linalg.norm(positions - center, axis=1)))
        height_std = float(np.std(heights))
        duration = None
        if self.start_source_s is not None:
            last = self.samples[-1]["source_stamp_s"]
            if last is not None:
                duration = last - self.start_source_s
        enough = (len(self.samples) >= self.settings["min_samples"]
                  and duration is not None
                  and duration >= self.settings["require_seconds"])
        if enough and spread <= self.settings["max_position_spread_m"] \
                and height_std <= self.settings["max_height_std_m"]:
            return self._ready(duration, center, heights, height_std, spread)
        if duration is not None and duration > self.settings["max_duration_s"]:
            return self._fail("timeout_insufficient_samples")
        if spread > self.settings["max_position_spread_m"]:
            return self._fail("position_unstable")
        if height_std > self.settings["max_height_std_m"]:
            return self._fail("height_unstable")
        return self.snapshot()

    def _ready(self, duration, center, heights, height_std, spread):
        self._baseline_counter += 1
        self.status = STATE_READY
        self.reason = None
        self.baseline = {
            "kind": BASELINE_KIND,
            "schema_version": SCHEMA_VERSION,
            "baseline_version": self._baseline_counter,
            "session_id": self.session_id,
            "track_id": self.track_id,
            "time_epoch": self.time_epoch,
            "selection_version": self.selection_version,
            "action_generation": self.action_generation,
            "calibration_version": self.calibration_version,
            "status": STATE_READY,
            "unit": "m",
            "source": "operator_confirmed" if self.operator_confirmed else "measured",
            "height_m": {"median": float(np.median(heights)),
                         "p10": float(np.percentile(heights, 10.0)),
                         "p90": float(np.percentile(heights, 90.0)),
                         "std": height_std},
            "position_m": [float(value) for value in center],
            "sample_count": len(self.samples),
            "duration_s": float(duration),
            "position_spread_m": spread,
            "point_count_median": float(np.median(
                [sample["point_count"] for sample in self.samples])),
            "thresholds": {key: self.settings[key] for key in (
                "require_seconds", "min_samples", "min_point_count",
                "max_position_spread_m", "height_min_m", "height_max_m",
                "min_stance_upper_m", "min_stance_span_m", "max_height_std_m")},
            "units": {"length": "m", "time": "s"},
        }
        return self.snapshot()

    def snapshot(self):
        return {
            "status": self.status,
            "reason": self.reason,
            "session_id": self.session_id,
            "track_id": self.track_id,
            "calibration_version": self.calibration_version,
            "time_epoch": self.time_epoch,
            "selection_version": self.selection_version,
            "action_generation": self.action_generation,
            "sample_count": len(self.samples),
            "operator_confirmed": self.operator_confirmed,
            "baseline": None if self.baseline is None else dict(self.baseline),
        }

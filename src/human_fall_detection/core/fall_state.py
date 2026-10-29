"""Measured single-target fall state; confirmed requires a bound baseline,
measured descent, sustained lying and enabled verification gates.
Confirmed is disabled by default; without both verification gates the highest
state is suspected. Posture and suspicion are geometry, not human or fall GT.
Predictions are gaps, not measurements.
Active lying and falls may be indistinguishable. Durations use source time.
"""

import numpy as np

try:  # pragma: no cover - import shim
    from core.features import baseline_applies
except ImportError:  # pragma: no cover
    from features import baseline_applies

STATE_UNKNOWN = "unknown"
STATE_UPRIGHT = "upright"
STATE_DESCENDING = "descending"
STATE_LOW = "low_posture_unclassified"
STATE_SUSPECTED = "suspected"
STATE_CONFIRMED = "confirmed"
STATE_RECOVERING = "recovering"
STATES = (STATE_UNKNOWN, STATE_UPRIGHT, STATE_DESCENDING, STATE_LOW,
          STATE_SUSPECTED, STATE_CONFIRMED, STATE_RECOVERING)

KIND = "fall_state"
EVENT_KIND = "fall_event"
SCHEMA_VERSION = 1
METHOD = "lidar_geometry"

DEFAULT_SETTINGS = {
    "descending_min_drop_m": 0.35,
    "descending_min_rate_m_s": 0.35,
    "low_height_m": 0.7,
    "low_min_duration_s": 1.5,
    "confirmed_min_low_duration_s": 3.0,
    "recovery_fraction": 0.6,
    "recovery_min_duration_s": 1.0,
    # Sustained low posture needs measured lying support: a body that is long on
    # the ground (horizontal extent) or low-topped (top of the measured surface).
    "lying_min_extent_m": 0.6,
    "lying_max_top_m": 0.7,
    # A short unmeasured gap is a quality gap, not a new target: the measured
    # episode (peak/descent) survives up to this many device seconds. Only a real
    # target change, a clock/generation reset, or a longer gap clears it.
    "gap_tolerance_s": 1.5,
    # Posture layer (core.range_posture) replaces the visible-surface median
    # height as the low/lying predicate, and a recent stable standing posture is
    # accepted as descent evidence (slow falls never reach the rate threshold).
    "posture_enabled": True,
    "transition_window_s": 10.0,
    "mode_verified": False,
    "allow_confirmed": False,
}

LIMITATIONS = [
    "active_lying_indistinguishable_from_fall",
    "slow_slide_may_not_reach_descent_threshold",
    "geometric_mode_not_human_labelled",
    "lying_pose_required_for_suspected",
    "posture_suspected_also_covers_voluntary_lying_or_floor_sitting",
]


def resolve_settings(settings=None):
    resolved = dict(DEFAULT_SETTINGS)
    for key, value in (settings or {}).items():
        if key not in resolved:
            raise ValueError("unknown fall setting: " + str(key))
        resolved[key] = value
    for key in ("mode_verified", "allow_confirmed", "posture_enabled"):
        if not isinstance(resolved[key], bool):
            raise ValueError(key + " must be a boolean")
    for key in ("descending_min_drop_m", "descending_min_rate_m_s", "low_height_m",
                "low_min_duration_s", "confirmed_min_low_duration_s",
                "recovery_fraction", "recovery_min_duration_s",
                "lying_min_extent_m", "lying_max_top_m", "transition_window_s"):
        resolved[key] = float(resolved[key])
        if not np.isfinite(resolved[key]) or resolved[key] < 0.0:
            raise ValueError(key + " must be a finite non-negative number")
    resolved["gap_tolerance_s"] = float(resolved["gap_tolerance_s"])
    if not np.isfinite(resolved["gap_tolerance_s"]) or resolved["gap_tolerance_s"] <= 0.0:
        raise ValueError("gap_tolerance_s must be a positive finite number")
    if not 0.0 < resolved["recovery_fraction"] <= 1.0:
        raise ValueError("recovery_fraction must be in (0, 1]")
    if resolved["confirmed_min_low_duration_s"] < resolved["low_min_duration_s"]:
        raise ValueError("confirmed_min_low_duration_s must be >= low_min_duration_s")
    return resolved


class FallStateMachine:
    def __init__(self, session_id, settings=None):
        self.session_id = session_id
        self.settings = resolve_settings(settings)
        self.confirmed_enabled = (self.settings["mode_verified"]
                                  and self.settings["allow_confirmed"])
        self.fall_status = STATE_UNKNOWN
        self.state_since_source_s = None
        self.events = []
        self._event_counter = 0
        self._active_event_id = None
        self._descent_seen = False
        self._descent_start_s = None
        self._low_since_s = None
        self._recovery_since_s = None
        self._measured_peak = None
        self._episode_event_emitted = False
        self._stance_s = None
        self._stance_since_s = None
        self._last_epoch = None
        self._last_generation = None
        self._last_track_id = None
        self._last_calibration = None
        self._last_selection = None
        self._last_locked_s = None
        self.posture_state = None
        self.history_reset_reason = None

    def _clear_action_history(self, reason):
        self._descent_seen = False
        self._descent_start_s = None
        self._low_since_s = None
        self._recovery_since_s = None
        self._measured_peak = None
        self._episode_event_emitted = False
        self._stance_s = None
        self._stance_since_s = None
        self.history_reset_reason = reason

    def _note_gap(self):
        """Break duration continuity without ending an un-recovered episode."""
        self._low_since_s = None
        self._recovery_since_s = None
        self._stance_since_s = None

    def _context_reset(self, observation):
        epoch = observation.get("time_epoch")
        generation = observation.get("action_generation")
        track_id = observation.get("track_id")
        calibration = observation.get("calibration_version")
        selection = observation.get("selection_version")
        reason = None
        if self._last_epoch is not None and epoch != self._last_epoch:
            reason = "time_epoch_changed"
        elif self._last_generation is not None and generation != self._last_generation:
            reason = "action_history_reset"
        elif (self._last_calibration is not None and calibration is not None
              and calibration != self._last_calibration):
            reason = "calibration_changed"
        elif (self._last_selection is not None and selection is not None
              and selection != self._last_selection):
            reason = "selection_changed"
        elif (track_id is not None and self._last_track_id is not None
              and track_id != self._last_track_id):
            # A missing track id is a measurement gap, not a different target;
            # the update() gap policy decides whether the episode survives.
            reason = "target_changed"
        self._last_epoch = epoch
        self._last_generation = generation
        if calibration is not None:
            self._last_calibration = calibration
        if selection is not None:
            self._last_selection = selection
        if track_id is not None:
            self._last_track_id = track_id
        return reason

    def _set_state(self, state, source_s):
        if state != self.fall_status:
            self.fall_status = state
            self.state_since_source_s = source_s
            if state != STATE_CONFIRMED:
                self._active_event_id = None

    def _is_descending(self, features):
        rate = features.get("descent_rate_m_s")
        if rate is None or rate < self.settings["descending_min_rate_m_s"]:
            return False
        height = features.get("height_median_m")
        if height is None or self._measured_peak is None:
            return False
        return (self._measured_peak - height) >= self.settings["descending_min_drop_m"]

    def _lying_support(self, features):
        """Measured geometry consistent with a body lying on the ground.

        A long horizontal extent or a low measured top qualifies. Missing or
        non-finite geometry is not support, so an unavailable posture can never
        be upgraded to suspected by this gate.
        """
        extent = features.get("horizontal_extent_m")
        height_block = features.get("height_m") or {}
        top = height_block.get("max")
        if top is None:
            top = height_block.get("p90")
        try:
            extent = float(extent)
        except (TypeError, ValueError, OverflowError):
            extent = None
        try:
            top = float(top)
        except (TypeError, ValueError, OverflowError):
            top = None
        return bool((extent is not None and np.isfinite(extent)
                     and extent >= self.settings["lying_min_extent_m"])
                    or (top is not None and np.isfinite(top)
                        and top <= self.settings["lying_max_top_m"]))

    def _emit_event(self, features, source_s, low_duration, baseline):
        self._event_counter += 1
        event = {
            "kind": EVENT_KIND,
            "schema_version": SCHEMA_VERSION,
            "event_id": "fall:{}:{}:{}".format(self.session_id, features.get("track_id"),
                                               self._event_counter),
            "session_id": self.session_id,
            "time_epoch": features.get("time_epoch"),
            "track_id": features.get("track_id"),
            "fall_status": STATE_CONFIRMED,
            "method": METHOD,
            "start_source_s": (self._descent_start_s if self._descent_start_s is not None
                               else self._low_since_s),
            "end_source_s": source_s,
            "low_duration_s": None if low_duration is None else float(low_duration),
            "height_drop_m": features.get("height_drop_m"),
            "reason_codes": ["measured_descent", "sustained_low_posture",
                             "lying_pose_supported",
                             "valid_stance_baseline", "mode_verified"],
            "baseline_version": (baseline or {}).get("baseline_version"),
            "calibration_version": (baseline or {}).get("calibration_version"),
            "config_version": SCHEMA_VERSION,
            "evidence": {"features": features},
        }
        self.events.append(event)
        self._active_event_id = event["event_id"]
        return event

    def update(self, features, observation, baseline=None, posture=None):
        source_s = features.get("source_stamp_s", observation.get("source_stamp_s"))
        track_status = observation.get("track_status")
        track_id = observation.get("track_id")
        reason_codes = []
        self.posture_state = None
        reset_reason = self._context_reset(observation)
        if (reset_reason is None and features.get("reset_now")
                and not (track_id is None and features.get("history_reset_reason") == "target_changed")):
            reset_reason = features.get("history_reset_reason") or "history_reset"
        if reset_reason is not None:
            self._clear_action_history(reset_reason)
            self._set_state(STATE_UNKNOWN, source_s)
            reason_codes.append(reset_reason)
            return self._output(features, observation, baseline, reason_codes, None)

        candidate = observation.get("candidate")
        ground_lost = (observation.get("ground_relative_available") is False or
                       (isinstance(candidate, dict) and
                        candidate.get("ground_relative_available") is False))
        if ground_lost:
            self._clear_action_history("ground_unavailable")
            self._set_state(STATE_UNKNOWN, source_s)
            return self._output(features, observation, baseline, ["ground_unavailable"], None)

        if track_status == "ambiguous":
            gap_s = None if source_s is None or self._last_locked_s is None else float(source_s) - self._last_locked_s
            if gap_s is not None and not 0 <= gap_s <= self.settings["gap_tolerance_s"]:
                self._clear_action_history("observation_gap_timeout")
            else:
                self._note_gap()
            self._set_state(STATE_UNKNOWN, source_s)
            return self._output(features, observation, baseline, ["target_ambiguous"], None)

        if track_id is None or track_status in (None, "unselected", "held"):
            # A missing target is a bounded measurement gap.
            gap_s = None
            if source_s is not None and self._last_locked_s is not None:
                gap_s = float(source_s) - self._last_locked_s
            episode = (self._descent_seen or self._low_since_s is not None
                       or self.fall_status in (STATE_DESCENDING, STATE_LOW, STATE_SUSPECTED,
                                               STATE_CONFIRMED, STATE_RECOVERING))
            keep = (episode and gap_s is not None
                    and 0 <= gap_s <= self.settings["gap_tolerance_s"])
            if keep:
                self._note_gap()
                self._set_state(STATE_UNKNOWN, source_s)
                reason_codes.append("target_held_gap")
                return self._output(features, observation, baseline, reason_codes, None)
            self._clear_action_history("target_not_locked")
            self._set_state(STATE_UNKNOWN, source_s)
            reason_codes.append("target_not_locked")
            return self._output(features, observation, baseline, reason_codes, None)

        if not features.get("observable"):
            gap_s = None if source_s is None or self._last_locked_s is None else float(source_s) - self._last_locked_s
            if gap_s is not None and not 0 <= gap_s <= self.settings["gap_tolerance_s"]:
                self._clear_action_history("observation_gap_timeout")
            else:
                self._note_gap()
            self._set_state(STATE_UNKNOWN, source_s)
            reason_codes.append(features.get("reason") or "not_observable")
            return self._output(features, observation, baseline, reason_codes, None)

        if features.get("observation_gap"):
            gap_s = None if source_s is None or self._last_locked_s is None else float(source_s) - self._last_locked_s
            if gap_s is not None and not 0 <= gap_s <= self.settings["gap_tolerance_s"]:
                self._clear_action_history("observation_gap_timeout")
            else:
                self._note_gap()
            reason_codes.append("observation_gap")

        if source_s is not None and np.isfinite(float(source_s)):
            self._last_locked_s = float(source_s)
        posture_state = None
        if posture is not None and self.settings["posture_enabled"]:
            posture_state = posture.get("state")
        self.posture_state = posture_state
        bound = baseline if baseline_applies(baseline, observation, self.session_id) else None
        baseline_ready = bound is not None
        baseline_height = None
        if baseline_ready:
            baseline_height = (bound.get("height_m") or {}).get("median")
        height = features["height_median_m"]
        if self._measured_peak is None or height > self._measured_peak:
            self._measured_peak = height
        state, reasons, low_duration = self._classify(features, baseline_ready,
                                                      baseline_height, source_s,
                                                      posture_state)
        reason_codes.extend(reasons)
        previous = self.fall_status
        self._set_state(state, source_s)
        new_event = None
        if state == STATE_CONFIRMED and not self._episode_event_emitted:
            new_event = self._emit_event(features, source_s, low_duration, bound)
            self._episode_event_emitted = True
        return self._output(features, observation, bound, reason_codes, new_event)

    def _stance_recent(self, source_s):
        if self._stance_s is None or source_s is None:
            return False
        return float(source_s) - float(self._stance_s) <= self.settings["transition_window_s"] + 1e-9

    def _classify(self, features, baseline_ready, baseline_height, source_s, posture_state=None):
        height = features["height_median_m"]
        if posture_state == "standing":
            self._stance_s = source_s
            if self._stance_since_s is None:
                self._stance_since_s = source_s
        elif posture_state is not None:
            self._stance_since_s = None
        if posture_state is not None:
            # The posture layer classifies the body from measured top/span/axis;
            # the visible-surface median height is not a posture quantity.
            low = posture_state in ("lying_pending", "lying_candidate", "sitting")
            lying = posture_state == "lying_candidate"
            posture_reasons = ["posture_" + posture_state]
        else:
            low = height <= self.settings["low_height_m"]
            lying = None
            posture_reasons = []
        descending = self._is_descending(features)
        if descending and not self._descent_seen:
            self._descent_seen = True
            self._descent_start_s = source_s
        if low:
            if self._low_since_s is None:
                self._low_since_s = source_s
            self._recovery_since_s = None
            low_duration = None
            if source_s is not None and self._low_since_s is not None:
                low_duration = float(source_s - self._low_since_s)
            if lying is None:
                lying = self._lying_support(features)
            sustained = low_duration is not None and low_duration >= self.settings["low_min_duration_s"]
            if lying and sustained:
                evidence = (["measured_descent"] if self._descent_seen else [])
                if self._stance_recent(source_s):
                    evidence.append("posture_transition_supported")
                if (self._descent_seen and self.confirmed_enabled and baseline_ready
                        and low_duration >= self.settings["confirmed_min_low_duration_s"]):
                    return (STATE_CONFIRMED,
                            evidence + ["sustained_low_posture", "lying_pose_supported",
                                        "valid_stance_baseline", "mode_verified"],
                            low_duration)
                if evidence:
                    return (STATE_SUSPECTED,
                            evidence + ["sustained_low_posture", "lying_pose_supported"],
                            low_duration)
                return (STATE_LOW, posture_reasons + ["lying_pose_supported",
                                                      "low_posture_without_confirmed_descent"],
                        low_duration)
            if lying:
                return (STATE_LOW, posture_reasons + ["lying_pose_supported",
                                                      "low_posture_duration_pending"], low_duration)
            reasons = posture_reasons + (
                ["low_posture_without_lying_pose"] if self._descent_seen
                else ["low_posture_without_confirmed_descent"])
            return STATE_LOW, reasons, low_duration
        self._low_since_s = None
        if descending:
            self._recovery_since_s = None
            return STATE_DESCENDING, posture_reasons + ["height_dropping"], None
        if self._descent_seen or self.fall_status in (STATE_SUSPECTED, STATE_CONFIRMED,
                                                      STATE_RECOVERING):
            if posture_state == "standing":
                standing_for = (None if source_s is None
                                else float(source_s - self._stance_since_s))
                if standing_for is not None and standing_for >= self.settings["recovery_min_duration_s"]:
                    self._clear_action_history("recovered")
                    return STATE_UPRIGHT, ["recovered", "standing_posture"], None
                return STATE_RECOVERING, posture_reasons + ["rising_toward_baseline"], None
            if posture_state is not None:
                self._recovery_since_s = None
                return STATE_UNKNOWN, posture_reasons + ["recovery_posture_unknown"], None
            recovered = False
            if baseline_ready and baseline_height:
                recovered = height >= baseline_height * self.settings["recovery_fraction"]
            if recovered:
                if self._recovery_since_s is None:
                    self._recovery_since_s = source_s
                duration = None
                if source_s is not None and self._recovery_since_s is not None:
                    duration = source_s - self._recovery_since_s
                if duration is not None and duration >= self.settings["recovery_min_duration_s"]:
                    self._clear_action_history("recovered")
                    return STATE_UPRIGHT, ["recovered"], None
                return STATE_RECOVERING, ["rising_toward_baseline"], None
            self._recovery_since_s = None
            return STATE_RECOVERING, ["above_low_below_recovery"], None
        if posture_state == "standing":
            return STATE_UPRIGHT, posture_reasons + ["standing_posture"], None
        if posture_state is not None:
            return STATE_UNKNOWN, posture_reasons + ["posture_not_upright"], None
        if baseline_ready:
            return STATE_UPRIGHT, ["near_stance_baseline"], None
        return STATE_UNKNOWN, ["baseline_not_ready"], None

    def _output(self, features, observation, baseline, reason_codes, new_event):
        return {
            "kind": KIND,
            "schema_version": SCHEMA_VERSION,
            "session_id": self.session_id,
            "time_epoch": observation.get("time_epoch"),
            "track_id": observation.get("track_id"),
            "track_status": observation.get("track_status"),
            "source_stamp_s": features.get("source_stamp_s", observation.get("source_stamp_s")),
            "fall_status": self.fall_status,
            "state": self.fall_status,
            "state_since_source_s": self.state_since_source_s,
            "reason_codes": list(dict.fromkeys(reason_codes)),
            "event_id": self._active_event_id,
            "new_event": new_event,
            "event_count": len(self.events),
            "posture_state": self.posture_state,
            "confirmed_enabled": bool(self.confirmed_enabled),
            "mode_verified": bool(self.settings["mode_verified"]),
            "allow_confirmed": bool(self.settings["allow_confirmed"]),
            "method": METHOD,
            "baseline_version": (baseline or {}).get("baseline_version"),
            "calibration_version": (baseline or {}).get("calibration_version"),
            "history_reset_reason": self.history_reset_reason,
            "limitations": list(LIMITATIONS),
            "features": features,
        }

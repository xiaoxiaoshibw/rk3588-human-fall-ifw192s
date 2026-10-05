"""Explainable rule-based fall state machine for one locked target (HF-06).

Seven states: ``unknown / upright / descending / low_posture_unclassified /
suspected / confirmed / recovering``. All durations are device source seconds,
never a fixed frame count. ``confirmed`` requires a valid stance baseline, a
same-target measured descent history and sustained low-posture evidence.

Evidence rules (HF04-06 R1/R4/R5):

- The descent evidence is the *measured* drop from the recent measured peak plus
  the measured descent rate. A static baseline difference is only a posture
  quantity, never descent evidence: an initially lying target with a stored
  stance baseline stays ``low_posture_unclassified``.
- A prediction or quality gap breaks the continuous low-posture duration but
  keeps the episode: an already-emitted event is never duplicated while the fall
  episode has not recovered. Only a real recovery or a fresh target/reset starts
  a new episode that can emit a new ``event_id``.
- A context reset (clock epoch / target switch / operator action) is a one-shot
  event; after it, fresh valid observations can classify again (the reset reason
  does not stick the machine in ``unknown``).
- A baseline is consumed only when its bindings match the current observation.

Honesty gates: the real geometric mode has not been human-labelled and is not
accepted, so online ``confirmed`` is disabled by default (``mode_verified`` and
``allow_confirmed`` both false) and the machine tops out at ``suspected``.
Synthetic tests may explicitly enable the accepted fixture; that is not
real-device acceptance and this module never ships an always-confirmed demo.

Active lying and a fall may be geometrically indistinguishable, and slow slides
may be missed; those limits are reported, not hidden.
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
    "mode_verified": False,
    "allow_confirmed": False,
}

LIMITATIONS = [
    "active_lying_indistinguishable_from_fall",
    "slow_slide_may_not_reach_descent_threshold",
    "geometric_mode_not_human_labelled",
]


def resolve_settings(settings=None):
    resolved = dict(DEFAULT_SETTINGS)
    for key, value in (settings or {}).items():
        if key not in resolved:
            raise ValueError("unknown fall setting: " + str(key))
        resolved[key] = value
    for key in ("mode_verified", "allow_confirmed"):
        if not isinstance(resolved[key], bool):
            raise ValueError(key + " must be a boolean")
    for key in ("descending_min_drop_m", "descending_min_rate_m_s", "low_height_m",
                "low_min_duration_s", "confirmed_min_low_duration_s",
                "recovery_fraction", "recovery_min_duration_s"):
        resolved[key] = float(resolved[key])
        if not np.isfinite(resolved[key]) or resolved[key] < 0.0:
            raise ValueError(key + " must be a finite non-negative number")
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
        self._last_epoch = None
        self._last_generation = None
        self._last_track_id = None
        self.history_reset_reason = None

    def _clear_action_history(self, reason):
        self._descent_seen = False
        self._descent_start_s = None
        self._low_since_s = None
        self._recovery_since_s = None
        self._measured_peak = None
        self._episode_event_emitted = False
        self.history_reset_reason = reason

    def _note_gap(self):
        """Break duration continuity without ending an un-recovered episode."""
        self._low_since_s = None
        self._recovery_since_s = None

    def _context_reset(self, observation):
        epoch = observation.get("time_epoch")
        generation = observation.get("action_generation")
        track_id = observation.get("track_id")
        reason = None
        if self._last_epoch is not None and epoch != self._last_epoch:
            reason = "time_epoch_changed"
        elif self._last_generation is not None and generation != self._last_generation:
            reason = "action_history_reset"
        elif self._last_track_id is not None and track_id != self._last_track_id:
            reason = "target_changed"
        self._last_epoch = epoch
        self._last_generation = generation
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
                             "valid_stance_baseline", "mode_verified"],
            "baseline_version": (baseline or {}).get("baseline_version"),
            "calibration_version": (baseline or {}).get("calibration_version"),
            "config_version": SCHEMA_VERSION,
            "evidence": {"features": features},
        }
        self.events.append(event)
        self._active_event_id = event["event_id"]
        return event

    def update(self, features, observation, baseline=None):
        source_s = observation.get("source_stamp_s")
        track_status = observation.get("track_status")
        track_id = observation.get("track_id")
        reason_codes = []
        reset_reason = self._context_reset(observation)
        if reset_reason is None and features.get("reset_now"):
            reset_reason = features.get("history_reset_reason") or "history_reset"
        if reset_reason is not None:
            self._clear_action_history(reset_reason)
            self._set_state(STATE_UNKNOWN, source_s)
            reason_codes.append(reset_reason)
            return self._output(features, observation, baseline, reason_codes, None)

        if track_id is None or track_status in (None, "unselected"):
            self._clear_action_history("target_not_locked")
            self._set_state(STATE_UNKNOWN, source_s)
            reason_codes.append("target_not_locked")
            return self._output(features, observation, baseline, reason_codes, None)

        if not features.get("observable"):
            self._note_gap()
            self._set_state(STATE_UNKNOWN, source_s)
            reason_codes.append(features.get("reason") or "not_observable")
            return self._output(features, observation, baseline, reason_codes, None)

        bound = baseline if baseline_applies(baseline, observation, self.session_id) else None
        baseline_ready = bound is not None
        baseline_height = None
        if baseline_ready:
            baseline_height = (bound.get("height_m") or {}).get("median")
        height = features["height_median_m"]
        if self._measured_peak is None or height > self._measured_peak:
            self._measured_peak = height
        state, reasons, low_duration = self._classify(features, baseline_ready,
                                                      baseline_height, source_s)
        reason_codes.extend(reasons)
        previous = self.fall_status
        self._set_state(state, source_s)
        new_event = None
        if state == STATE_CONFIRMED and not self._episode_event_emitted:
            new_event = self._emit_event(features, source_s, low_duration, bound)
            self._episode_event_emitted = True
        return self._output(features, observation, bound, reason_codes, new_event)

    def _classify(self, features, baseline_ready, baseline_height, source_s):
        height = features["height_median_m"]
        low = height <= self.settings["low_height_m"]
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
            if self._descent_seen and low_duration is not None:
                if (self.confirmed_enabled and baseline_ready
                        and low_duration >= self.settings["confirmed_min_low_duration_s"]):
                    return STATE_CONFIRMED, ["measured_descent", "sustained_low_posture",
                                             "valid_stance_baseline", "mode_verified"], low_duration
                if low_duration >= self.settings["low_min_duration_s"]:
                    return STATE_SUSPECTED, ["measured_descent", "sustained_low_posture"], low_duration
            return STATE_LOW, ["low_posture_without_confirmed_descent"], low_duration
        self._low_since_s = None
        if descending:
            self._recovery_since_s = None
            return STATE_DESCENDING, ["height_dropping"], None
        if self._descent_seen or self.fall_status in (STATE_SUSPECTED, STATE_CONFIRMED,
                                                      STATE_RECOVERING):
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
            return STATE_RECOVERING, ["above_low_below_recovery"], None
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
            "source_stamp_s": observation.get("source_stamp_s"),
            "fall_status": self.fall_status,
            "state": self.fall_status,
            "state_since_source_s": self.state_since_source_s,
            "reason_codes": list(dict.fromkeys(reason_codes)),
            "event_id": self._active_event_id,
            "new_event": new_event,
            "event_count": len(self.events),
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

"""Offline dynamic-ROI controller and mask for the single-target chain.

Scope: the ROI only limits *where* the candidate stage searches. It cannot make
one body's points connected, and it never changes the tracker's association
rules, so it is not a fragmentation fix. It is disabled by default, is driven only
by source time and previously committed measurements, and never reads tracker
private state.

Coordinate contract: the ROI is a horizontal circle in the valid ground tangent
plane (``ground_plane_basis``) plus a loose ground-relative height band. Raw
sensor XY is never used as horizontal. Row indices are never renumbered: the mask
only filters rows, so ``evidence_indices`` keep their domain.

States:

- ``SEARCH``: no selected target (or explicitly released) -> full view.
- ``LOCKED``: valid lock or short occlusion -> circle around the last measured
  support, optionally advanced by the target's own velocity.
- ``LOST``: measurement missing beyond the short-occlusion window -> the radius
  grows with source time up to the recovery radius.
- ``RECOVER``: recovery radius/time reached -> full view again.

A frame's decision is produced only from state committed on earlier frames; the
first locking frame is always full view.
"""

import math

import numpy as np

KIND = "roi_decision"
SCHEMA_VERSION = 1
STATES = ("SEARCH", "LOCKED", "LOST", "RECOVER")

DEFAULT_SETTINGS = {
    "enabled": False,
    "base_radius_m": 1.5,
    "margin_m": 0.8,
    "k_sigma": 1.0,
    "max_sigma_m": 0.5,
    "height_band_m": [-0.10, 2.50],
    "prediction": True,
    "expand_m_per_s": 0.8,
    "recover_radius_m": 4.0,
    "shrink_m_per_s": 2.0,
    "before_stride": False,
    "min_radius_m": 0.2,
    "shell_m": 0.2,
    "short_occlusion_s": 1.5,
    "max_prediction_s": 1.5,
}
_POSITIVE = ("base_radius_m", "margin_m", "k_sigma", "max_sigma_m", "expand_m_per_s",
             "recover_radius_m", "shrink_m_per_s", "min_radius_m", "shell_m",
             "short_occlusion_s", "max_prediction_s")


def resolve_settings(settings=None):
    """Merge/validate ROI settings; unknown keys and illegal ranges are refused."""
    resolved = dict(DEFAULT_SETTINGS)
    for key, value in (settings or {}).items():
        if key not in resolved:
            raise ValueError("unknown roi setting: " + str(key))
        resolved[key] = value
    for key in ("enabled", "prediction", "before_stride"):
        if not isinstance(resolved[key], bool):
            raise ValueError("roi." + key + " must be true or false")
    for key in _POSITIVE:
        resolved[key] = float(resolved[key])
        if not np.isfinite(resolved[key]) or resolved[key] <= 0.0:
            raise ValueError("roi." + key + " must be a positive finite number")
    band = resolved["height_band_m"]
    if not isinstance(band, (list, tuple)) or len(band) != 2:
        raise ValueError("roi.height_band_m must be [low, high]")
    band = [float(band[0]), float(band[1])]
    if not all(np.isfinite(band)) or band[0] >= band[1]:
        raise ValueError("roi.height_band_m must be two finite increasing numbers")
    resolved["height_band_m"] = band
    if resolved["recover_radius_m"] <= resolved["base_radius_m"]:
        raise ValueError("roi.recover_radius_m must exceed base_radius_m")
    return resolved


def ground_basis(ground, frame_id="innolidar"):
    """Validated ground tangent basis, or an explicit refusal reason.

    A *missing/invalid* plane is a runtime fall back to the full view. A plane
    that claims to be valid but whose basis is non-finite, non-unit or not
    orthogonal is a programming/data error and raises.
    """
    if not isinstance(ground, dict):
        return None, "ground_unavailable"
    from core.lidar_candidates import ground_frame_eligible, ground_plane_basis
    if ground.get("status") != "valid":
        return None, "ground_unavailable"
    if not ground_frame_eligible(ground, frame_id):
        return None, "ground_frame_mismatch"
    try:
        raw_normal = np.asarray(ground.get("normal"), dtype=np.float64)
    except (TypeError, ValueError):
        raise ValueError("roi ground normal is not numeric")
    if raw_normal.shape != (3,) or not np.all(np.isfinite(raw_normal)):
        raise ValueError("roi ground normal is not finite")
    raw_norm = float(np.linalg.norm(raw_normal))
    if raw_norm <= 1e-9:
        raise ValueError("roi ground normal is degenerate")
    basis = ground_plane_basis(ground)
    if basis is None:
        return None, "ground_unavailable"
    normal, u, v = basis
    for vector in (normal, u, v):
        array = np.asarray(vector, dtype=np.float64)
        if array.shape != (3,) or not np.all(np.isfinite(array)):
            raise ValueError("roi ground basis is not finite")
        norm = float(np.linalg.norm(array))
        if abs(norm - 1.0) > 1e-6:
            raise ValueError("roi ground basis is not unit length")
    if abs(float(np.dot(normal, u))) > 1e-6 or abs(float(np.dot(normal, v))) > 1e-6 \
            or abs(float(np.dot(u, v))) > 1e-6:
        raise ValueError("roi ground basis is not orthogonal")
    try:
        offset = float(ground["offset_m"])
    except (KeyError, TypeError, ValueError):
        return None, "ground_offset_unavailable"
    if not math.isfinite(offset):
        return None, "ground_offset_unavailable"
    return dict(normal=normal, u=u, v=v, offset_m=offset), None


class RoiController:
    """Causal ROI state machine; call :meth:`update` before the frame and
    :meth:`note_measured` after it."""

    def __init__(self, settings=None):
        self.settings = resolve_settings(settings)
        self.reset("startup")

    def reset(self, reason):
        self.state = "SEARCH"
        self.last_center_m = None
        self.last_measured_source_s = None
        self.last_sigma_m = 0.0
        self.velocity_m_s = None
        self.radius_m = None
        self.binding = None
        self.reset_reason = reason
        self.decisions = 0

    def advance(self, track_state, *, source_stamp_s, ground, frame_id="innolidar",
                binding=None, support_extent_m=None):
        """Decide this frame's ROI from previously committed state only.

        ``track_state`` is the tracker's public snapshot before this frame. The
        returned decision is what ``build_snapshot(roi=...)`` consumes.
        """
        settings = self.settings
        decision = dict(kind=KIND, schema_version=SCHEMA_VERSION,
                        enabled=bool(settings["enabled"]), apply=False,
                        state="SEARCH", reason=None, predicted=False,
                        center_m=None, radius_m=None, margin_m=settings["margin_m"],
                        sigma_m=None, basis=None, height_band_m=list(settings["height_band_m"]),
                        before_stride=bool(settings["before_stride"]),
                        settings=dict(settings),
                        source_stamp_s=None, age_s=None)
        if not settings["enabled"]:
            decision["reason"] = "disabled"
            self.state = "SEARCH"
            return decision
        stamp = None
        try:
            stamp = float(source_stamp_s)
        except (TypeError, ValueError):
            stamp = None
        decision["source_stamp_s"] = stamp
        if stamp is None or not math.isfinite(stamp):
            self.reset("invalid_source_time")
            decision["reason"] = "invalid_source_time"
            return decision
        if self.last_measured_source_s is not None and stamp <= self.last_measured_source_s:
            self.reset("nonincreasing_source_time")
            decision["reason"] = "nonincreasing_source_time"
            return decision
        if binding is not None and self.binding is not None and binding != self.binding:
            self.reset("binding_changed")
            decision["reason"] = "binding_changed"
            return decision
        self.binding = binding
        basis, refusal = ground_basis(ground, frame_id)
        if basis is None:
            decision["reason"] = refusal
            decision["state"] = "SEARCH"
            self.state = "SEARCH"
            return decision
        decision["basis"] = {key: np.asarray(value, dtype=np.float64).tolist()
                             if key != "offset_m" else float(value)
                             for key, value in basis.items()}
        if not isinstance(track_state, dict) or track_state.get("track_id") is None:
            decision["reason"] = "no_selected_target"
            decision["state"] = "SEARCH"
            self.state = "SEARCH"
            return decision
        status = track_state.get("track_status")
        if status in ("unselected", "ambiguous", "lost"):
            if status == "lost":
                return self._lost_decision(decision, stamp, basis)
            decision["reason"] = "no_selected_target"
            decision["state"] = "SEARCH"
            self.state = "SEARCH"
            return decision
        if self.last_center_m is None or self.last_measured_source_s is None:
            decision["reason"] = "no_committed_measurement"
            decision["state"] = "SEARCH"
            self.state = "SEARCH"
            return decision
        age = max(0.0, stamp - self.last_measured_source_s)
        if age > settings["short_occlusion_s"]:
            return self._lost_decision(decision, stamp, basis)
        return self._locked_decision(decision, stamp, basis, age)

    def _sigma(self, support_extent_m):
        if support_extent_m is None:
            sigma = self.last_sigma_m
        else:
            sigma = 0.5 * float(support_extent_m)
        sigma = min(max(0.0, sigma), self.settings["max_sigma_m"])
        return sigma

    def _centre(self, age, predicted_allowed):
        centre = np.asarray(self.last_center_m, dtype=np.float64)
        velocity = self.velocity_m_s
        if (predicted_allowed and self.settings["prediction"] and velocity is not None
                and age > 0.0):
            bounded = max(0.0, min(age, self.settings["max_prediction_s"]))
            speed = float(np.linalg.norm(velocity))
            limit = self.settings["expand_m_per_s"] * self.settings["max_prediction_s"]
            if speed > 0.0 and speed * bounded > limit:
                velocity = np.asarray(velocity, dtype=np.float64) * (limit / (speed * bounded))
            return centre + np.asarray(velocity, dtype=np.float64) * bounded, True
        return centre, False

    def _target_radius(self, sigma):
        return self.settings["base_radius_m"] + self.settings["margin_m"] \
            + self.settings["k_sigma"] * float(sigma)

    def _apply_rate(self, target_radius, elapsed):
        """Speed-limited shrink, immediate growth (never below the minimum)."""
        minimum = self.settings["min_radius_m"]
        if self.radius_m is None:
            radius = target_radius
        elif target_radius >= self.radius_m:
            radius = target_radius
        else:
            radius = max(target_radius, self.radius_m
                         - self.settings["shrink_m_per_s"] * max(0.0, elapsed))
        if not math.isfinite(radius) or radius < minimum:
            raise ValueError("roi radius is not a usable positive number")
        return radius

    def _locked_decision(self, decision, stamp, basis, age):
        centre, predicted = self._centre(age, True)
        sigma = self._sigma(None)
        radius = self._apply_rate(self._target_radius(sigma), age)
        self.radius_m = radius
        self.state = "LOCKED"
        decision.update(apply=True, state="LOCKED", reason="locked_target",
                        predicted=predicted, center_m=centre.tolist(),
                        radius_m=float(radius), sigma_m=float(sigma), age_s=float(age))
        return decision

    def _lost_decision(self, decision, stamp, basis):
        if self.last_center_m is None or self.last_measured_source_s is None:
            decision["reason"] = "no_committed_measurement"
            decision["state"] = "SEARCH"
            self.state = "SEARCH"
            return decision
        age = max(0.0, stamp - self.last_measured_source_s)
        centre, predicted = self._centre(age, True)
        sigma = self._sigma(None)
        radius = self._target_radius(sigma) + self.settings["expand_m_per_s"] * age
        radius = min(max(radius, self.settings["min_radius_m"]),
                     self.settings["recover_radius_m"])
        self.radius_m = radius
        if radius >= self.settings["recover_radius_m"] or age > 3.0 * self.settings[
                "short_occlusion_s"]:
            self.state = "RECOVER"
            decision.update(apply=False, state="RECOVER", reason="recovery_radius_reached",
                            predicted=predicted, center_m=centre.tolist(),
                            radius_m=float(radius), sigma_m=float(sigma), age_s=float(age))
            return decision
        self.state = "LOST"
        decision.update(apply=True, state="LOST", reason="measurement_missing",
                        predicted=predicted, center_m=centre.tolist(),
                        radius_m=float(radius), sigma_m=float(sigma), age_s=float(age))
        return decision

    def note_measured(self, center_m, source_stamp_s, *, support_extent_m=None,
                      velocity_m_s=None):
        """Commit one measured target observation (never a prediction)."""
        if center_m is None:
            return
        array = np.asarray(center_m, dtype=np.float64)
        if array.shape != (3,) or not np.all(np.isfinite(array)):
            raise ValueError("roi measured centre must be three finite numbers")
        stamp = None
        try:
            stamp = float(source_stamp_s)
        except (TypeError, ValueError):
            stamp = None
        if stamp is None or not math.isfinite(stamp):
            self.reset("invalid_measured_time")
            return
        if self.last_measured_source_s is not None and stamp <= self.last_measured_source_s:
            self.reset("nonincreasing_measured_time")
            return
        self.last_center_m = array.tolist()
        self.last_measured_source_s = stamp
        self.last_sigma_m = self._sigma(support_extent_m)
        self.velocity_m_s = None if velocity_m_s is None else [
            float(value) for value in velocity_m_s]


def roi_mask(points, decision, ground, frame_id="innolidar", *, settings=None,
             timings=None):
    """Horizontal ground-tangent circle + height band mask for one frame.

    Returns ``(mask, diagnostics)``; ``mask`` is a boolean array aligned with the
    row order of ``points`` and never renumbers rows. A non-applied decision
    returns an all-True mask with the reason recorded.
    """
    import time as _time
    started = _time.perf_counter()
    if settings is None and isinstance(decision.get("settings"), dict):
        settings = decision["settings"]
    resolved = resolve_settings(settings)
    array = np.asarray(points, dtype=np.float64)
    if array.ndim != 2 or array.shape[1] != 3:
        raise ValueError("roi points must be (N,3)")
    diagnostics = dict(applied=False, reason=decision.get("reason"),
                       state=decision.get("state"), input_points=int(len(array)),
                       kept_points=int(len(array)), dropped_points=0,
                       boundary_shell_points=0, radius_m=decision.get("radius_m"),
                       margin_m=resolved["margin_m"],
                       height_band_m=list(resolved["height_band_m"]),
                       center_m=decision.get("center_m"),
                       predicted=bool(decision.get("predicted")))
    if not decision.get("apply"):
        diagnostics["reason"] = decision.get("reason") or "not_applied"
        _record(timings, "roi_mask_s", _time.perf_counter() - started)
        return np.ones(len(array), dtype=bool), diagnostics
    centre = decision.get("center_m")
    radius = decision.get("radius_m")
    if centre is None or radius is None:
        diagnostics["reason"] = "invalid_decision"
        _record(timings, "roi_mask_s", _time.perf_counter() - started)
        return np.ones(len(array), dtype=bool), diagnostics
    centre = np.asarray(centre, dtype=np.float64)
    radius = float(radius)
    if centre.shape != (3,) or not np.all(np.isfinite(centre)):
        raise ValueError("roi centre must be three finite numbers")
    if not math.isfinite(radius) or radius < resolved["min_radius_m"]:
        raise ValueError("roi radius is not a usable positive number")
    basis, refusal = ground_basis(ground, frame_id)
    if basis is None:
        diagnostics["reason"] = refusal
        _record(timings, "roi_mask_s", _time.perf_counter() - started)
        return np.ones(len(array), dtype=bool), diagnostics
    normal, u, v = basis["normal"], basis["u"], basis["v"]
    horizontal = np.column_stack((array @ u, array @ v))
    centre_horizontal = np.array([centre @ u, centre @ v])
    distance = np.sqrt(np.sum((horizontal - centre_horizontal) ** 2, axis=1))
    height = array @ normal + basis["offset_m"]
    low, high = resolved["height_band_m"]
    inside = (distance <= radius) & (height >= low) & (height <= high)
    shell_low = max(0.0, radius - resolved["shell_m"])
    shell = (distance >= shell_low) & (distance <= radius)
    diagnostics.update(applied=True, reason="applied",
                       kept_points=int(np.count_nonzero(inside)),
                       dropped_points=int(len(array) - np.count_nonzero(inside)),
                       boundary_shell_points=int(np.count_nonzero(shell)),
                       radius_m=radius)
    _record(timings, "roi_mask_s", _time.perf_counter() - started)
    return inside, diagnostics


def _record(timings, key, seconds):
    if timings is None:
        return
    timings[key] = float(timings.get(key, 0.0)) + float(seconds)
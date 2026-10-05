"""Auxiliary-IMU semantics and data-quality checks (HF-02).

The device IMU is a device-motion / static-gravity reference only; it is not a
human-impact sensor. Six-axis unit verification and orientation validity are
tracked separately. Magnitude clues (gravity-sized acceleration, near-zero
angular rate) are never accepted as scale or axis proof: units/alignment/bias
only become ``verified`` through a named evidence source (vendor protocol or a
controlled known motion/attitude).
"""

import math

from sensor_health import (finite_or_none, orientation_covariance_flags,
                           quaternion_report)

IMU_ROLE = "device_motion_gravity_reference_not_human_impact"
EVIDENCE_SOURCES = ("vendor_protocol", "controlled_motion", "controlled_attitude")
SEMANTIC_FIELDS = ("acceleration_units", "angular_velocity_units",
                   "axis_mapping", "bias")
DEFAULT_GRAVITY_M_S2 = 9.80665
ACCELERATION_UNITS_TO_SI = {"m_s2": 1.0, "g": DEFAULT_GRAVITY_M_S2}
ANGULAR_VELOCITY_UNITS_TO_SI = {"rad_s": 1.0, "deg_s": math.pi / 180.0}


def _validated_bias(value):
    try:
        values = [float(item) for item in value]
    except (TypeError, ValueError):
        raise ValueError("bias must be a sequence of six finite numbers") from None
    if len(values) != 6 or not all(math.isfinite(item) for item in values):
        raise ValueError("bias must be a sequence of six finite numbers")
    return values


# Reference-frame directions used by the supported axis_mapping triad, in a
# right-handed forward/left/up frame (ROS REP-103 style). Only the direction
# names are defined here; the device's actual mounting stays unknown.
REFERENCE_DIRECTIONS = {
    "forward": (1.0, 0.0, 0.0),
    "backward": (-1.0, 0.0, 0.0),
    "left": (0.0, 1.0, 0.0),
    "right": (0.0, -1.0, 0.0),
    "up": (0.0, 0.0, 1.0),
    "down": (0.0, 0.0, -1.0),
}


def _validated_axis_mapping(value):
    """Validate the supported three-axis mapping description.

    Accepted form: ``x_<direction>_y_<direction>_z_<direction>``. It is read
    ``from`` each IMU sensor axis ``x``/``y``/``z`` (listed once, in order)
    ``to`` the direction it points to in the reference frame. The directions
    must be known names, pairwise distinct and form a proper (right-handed)
    rotation, so text such as ``unknown``, missing/duplicate axes, duplicate
    directions and mirrored triads are rejected before any state change. This
    validates the description only; it never guesses the real device axes.
    """
    if not isinstance(value, str):
        raise ValueError("axis_mapping must be a supported triad string")
    tokens = value.split("_")
    if len(tokens) != 6 or tokens[0::2] != ["x", "y", "z"]:
        raise ValueError("axis_mapping must be "
                         "'x_<direction>_y_<direction>_z_<direction>' with each "
                         "sensor axis exactly once")
    directions = tokens[1::2]
    for name in directions:
        if name not in REFERENCE_DIRECTIONS:
            raise ValueError("unsupported axis direction: " + repr(name))
    if len(set(directions)) != 3:
        raise ValueError("axis direction conflict: two sensor axes point the same way")
    first, second, third = (REFERENCE_DIRECTIONS[name] for name in directions)
    cross = (first[1] * second[2] - first[2] * second[1],
             first[2] * second[0] - first[0] * second[2],
             first[0] * second[1] - first[1] * second[0])
    if cross != third:
        raise ValueError("axis_mapping is not a right-handed rotation of x/y/z")
    return value


class ImuSemantics:
    """Per-field verification state for the auxiliary device IMU."""

    def __init__(self):
        self.status = {field: "unknown" for field in SEMANTIC_FIELDS}
        self.values = {}
        self.evidence = []

    def verify(self, field, value, evidence, note=None):
        """Mark one semantic field verified by named evidence.

        The value itself is validated: empty values, unsupported unit names,
        invalid axis-mapping descriptions and wrong-sized/non-finite bias
        vectors are rejected before any state mutation, so neither an empty nor
        an arbitrary ``verify`` call can enable motion classification.
        """
        if field not in SEMANTIC_FIELDS:
            raise ValueError("unknown IMU semantic field: " + str(field))
        if evidence not in EVIDENCE_SOURCES:
            raise ValueError(
                "unsupported evidence {!r}: magnitude hints (gravity-sized "
                "acceleration, near-zero rate) are not scale proof".format(evidence))
        if field == "acceleration_units":
            if not isinstance(value, str) or value not in ACCELERATION_UNITS_TO_SI:
                raise ValueError("unsupported acceleration units: " + repr(value))
        elif field == "angular_velocity_units":
            if not isinstance(value, str) or value not in ANGULAR_VELOCITY_UNITS_TO_SI:
                raise ValueError("unsupported angular velocity units: " + repr(value))
        elif field == "axis_mapping":
            value = _validated_axis_mapping(value)
        elif field == "bias":
            value = _validated_bias(value)
        self.status[field] = "verified"
        self.values[field] = value
        self.evidence.append({"field": field, "value": value, "evidence": evidence,
                              "note": note})
        return dict(self.report())

    @property
    def units_verified(self):
        return (self.status["acceleration_units"] == "verified"
                and self.status["angular_velocity_units"] == "verified")

    @property
    def alignment_verified(self):
        return self.status["axis_mapping"] == "verified"

    def report(self):
        return {"role": IMU_ROLE,
                "acceleration_units": self.status["acceleration_units"],
                "angular_velocity_units": self.status["angular_velocity_units"],
                "axis_mapping": self.status["axis_mapping"],
                "bias": self.status["bias"],
                "values": dict(self.values),
                "units_verified": self.units_verified,
                "alignment_verified": self.alignment_verified,
                "evidence": [dict(item) for item in self.evidence]}


def six_axis_report(acceleration, angular_velocity):
    """Finiteness of the six-axis measurement, kept separate from orientation.

    A usable six-axis sample is exactly three finite acceleration values and
    exactly three finite angular-velocity values; missing/extra axes or
    unreadable values are reported invalid instead of being treated as finite.
    """
    if acceleration is None or angular_velocity is None:
        return {"finite": None, "reason": None}
    try:
        accel = [float(value) for value in acceleration]
        rate = [float(value) for value in angular_velocity]
    except (TypeError, ValueError):
        return {"finite": False, "reason": "imu_measurement_malformed"}
    if len(accel) != 3 or len(rate) != 3:
        return {"finite": False, "reason": "imu_axis_count_invalid"}
    finite = all(math.isfinite(value) for value in accel + rate)
    return {"finite": finite,
            "reason": None if finite else "imu_measurement_nonfinite"}


def orientation_report(quaternion, covariance):
    """Orientation usability, reusing the frozen HF-01 rules.

    ``covariance[0] == -1`` (not provided) and all-zero/non-unit/non-finite
    quaternions are unusable; no valid quaternion is ever fabricated.
    """
    covariance_zero, not_provided = orientation_covariance_flags(covariance)
    if not_provided:
        usable, reason = False, "orientation_not_provided"
    elif quaternion is None:
        usable, reason = None, None
    else:
        usable, reason = quaternion_report(quaternion)
    return {"usable": usable, "reason": reason,
            "not_provided": bool(not_provided),
            "covariance_zero": bool(covariance_zero)}


def device_motion_status(acceleration, angular_velocity, semantics,
                         gravity_m_s2=DEFAULT_GRAVITY_M_S2,
                         accel_tolerance_m_s2=0.25,
                         rate_tolerance_rad_s=0.03):
    """Static/moving status of the device, only once units+axes are verified.

    Raw values are converted from the verified units (``m_s2``/``g`` and
    ``rad_s``/``deg_s``) to SI before the SI thresholds are compared; unknown
    or unsupported units keep the verdict ``unknown`` instead of silently
    assuming SI. Thresholds are the physical tuning knobs for the board
    installation. This is a device-motion hint only: bias/alignment and the
    static-background ground/background conditions stay separate, and this
    verdict alone never enables fusion.
    """
    if not semantics.units_verified:
        return {"status": "unknown", "reason": "imu_units_unverified",
                "scope": IMU_ROLE}
    if not semantics.alignment_verified:
        return {"status": "unknown", "reason": "imu_alignment_unverified",
                "scope": IMU_ROLE}
    accel_scale = ACCELERATION_UNITS_TO_SI.get(semantics.values.get("acceleration_units"))
    rate_scale = ANGULAR_VELOCITY_UNITS_TO_SI.get(
        semantics.values.get("angular_velocity_units"))
    if accel_scale is None or rate_scale is None:
        return {"status": "unknown", "reason": "imu_units_unverified",
                "scope": IMU_ROLE}
    report = six_axis_report(acceleration, angular_velocity)
    if report["finite"] is not True:
        return {"status": "unknown", "reason": report["reason"] or "imu_measurement_missing",
                "scope": IMU_ROLE}
    magnitude = math.sqrt(sum((float(value) * accel_scale) ** 2
                              for value in acceleration))
    max_rate = max(abs(float(value)) * rate_scale for value in angular_velocity)
    gravity_residual = abs(magnitude - float(gravity_m_s2))
    if gravity_residual <= float(accel_tolerance_m_s2) and max_rate <= float(rate_tolerance_rad_s):
        status = "static"
    else:
        status = "moving"
    return {"status": status, "reason": None, "scope": IMU_ROLE,
            "gravity_residual_m_s2": gravity_residual,
            "max_angular_rate": finite_or_none(max_rate),
            "comparison_units": "m_s2/rad_s"}


def static_background_usable(ground_valid, background_residual_ok, device_motion):
    """Gate the static-background scheme on ground, residual and device motion.

    A missing IMU motion verdict is not a pass: the IMU alone cannot prove the
    device did not translate, so unknown motion keeps the scheme unusable and
    asks for a fresh on-site initialisation along with the other failures.
    """
    reasons = []
    if ground_valid is not True:
        reasons.append("ground_invalid")
    if background_residual_ok is not True:
        reasons.append("background_residual_invalid")
    if device_motion != "static":
        reasons.append("device_motion_" + str(device_motion))
    usable = not reasons
    return {"usable": usable, "reinit_required": not usable, "reasons": reasons}

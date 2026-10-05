"""Fixed installation leveling from declared pitch/height, never a ground fit."""
import hashlib
import json
import math

import numpy as np

from .calibration import apply_transform, validate_rotation, validate_translation
from .numeric import strict_numeric_array

CONVENTION = "source:X-forward,Y-left,Z-up; pitch-down-positive; roll=yaw=0"


def _identity(record):
    raw = json.dumps(record, sort_keys=True, separators=(",", ":"),
                     allow_nan=False).encode("utf8")
    return "nominal:" + hashlib.sha256(raw).hexdigest()


def build_nominal_model(pitch_down_deg, height_m, from_frame, to_frame="ground_nominal"):
    pitch = float(strict_numeric_array(pitch_down_deg, (), "pitch_down_deg"))
    height = float(strict_numeric_array(height_m, (), "height_m"))
    if not -90 <= pitch <= 90 or not 0 <= height <= 50:
        raise ValueError("pitch must be in [-90,90] deg and height in [0,50] m")
    if not all(isinstance(f, str) and f.strip() for f in (from_frame, to_frame)) \
            or from_frame == to_frame:
        raise ValueError("explicit distinct from/to frames required")
    angle = math.radians(pitch)
    c, s = math.cos(angle), math.sin(angle)
    rotation = validate_rotation([[c, 0, s], [0, 1, 0], [-s, 0, c]])
    translation = validate_translation([0, 0, height])
    model = {"kind": "nominal_installation_leveling", "schema": 1,
             "status": "nominal", "from_frame": from_frame, "to_frame": to_frame,
             "direction": "p_to = R @ p_from + t", "convention": CONVENTION,
             "pitch_down_deg": pitch, "height_m": height,
             "units": {"length": "m", "angle": "deg"},
             "provenance": "user_declared_installation_parameters",
             "rotation": rotation.tolist(), "translation_m": translation.tolist(),
             "up_source": rotation[2].tolist(),
             "physical_verified": False, "extrinsics_verified": False,
             "runtime_eligible": False}
    model["model_id"] = _identity(model)
    return model


def validate_nominal_model(model):
    if not isinstance(model, dict) or type(model.get("schema")) is not int:
        raise ValueError("nominal model schema required")
    expected = build_nominal_model(model.get("pitch_down_deg"), model.get("height_m"),
                                   model.get("from_frame"), model.get("to_frame"))
    # Includes all types/fields, derived R/t/up, ID and qualification flags.
    if json.dumps(model, sort_keys=True, allow_nan=False) != \
            json.dumps(expected, sort_keys=True, allow_nan=False):
        raise ValueError("model content/ID/schema/qualification mismatch")
    return expected


def apply_nominal(points, model, frame):
    record = validate_nominal_model(model)
    if frame != record["from_frame"]:
        raise ValueError("source frame mismatch")
    if not isinstance(points, np.ndarray):
        points = np.asarray(points, dtype=object)
    array = strict_numeric_array(points, (len(points), 3), "points")
    # Frozen helper is used only for arithmetic; nominal is never a known
    # mount record accepted by validate_known_transform or runtime consumers.
    return apply_transform(array, record)


def inverse_nominal(points, model, frame):
    record = validate_nominal_model(model)
    if frame != record["to_frame"]:
        raise ValueError("target frame mismatch")
    if not isinstance(points, np.ndarray):
        points = np.asarray(points, dtype=object)
    array = strict_numeric_array(points, (len(points), 3), "points")
    rotation = np.asarray(record["rotation"])
    return (array - record["translation_m"]) @ rotation

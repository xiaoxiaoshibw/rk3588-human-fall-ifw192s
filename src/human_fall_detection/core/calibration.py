"""Rigid-body transform and geometry-calibration artifact validation (HF-03).

Scope and honesty rules (see docs/human_fall/tickets/HF-03_geometric_calibration.md):

- A transform ``T_from_to`` maps a point ``p_from`` to ``p_to = R @ p_from + t``.
  Direction, frames and length unit are explicit; a rotation must be a proper
  (orthonormal, ``det=+1``) rigid rotation, so non-rigid matrices and axis-sign
  flips (reflections, ``det=-1``) are rejected before any value is stored.
- A mount translation is checked for plausibility in metres. Supplying a value
  still in millimetres while declaring ``m`` produces an implausible magnitude
  and is reported as ``unit_mismatch_suspected`` instead of being accepted.
- The LiDAR->reference installation transform and the IMU->LiDAR mounting
  rotation are only ever recorded with an explicit evidence source. With no
  on-site measurement they stay ``unknown``; an identity matrix is never
  fabricated just because two frame names match or two topics share a frame_id.
- A single static-scene ground fit never claims a world installation pose or a
  passed calibration: this module stores geometry with an explicit status and a
  separate physical-verification flag that stays false until verified on-site.

This module is pure NumPy + stdlib and is shared by the offline calibration tool
and the regression tests; it never reads ROS, the network or a clock.
"""

import copy
import hashlib
import json

import numpy as np

try:  # pragma: no cover - import shim
    from core.numeric import strict_numeric_array
except ImportError:  # pragma: no cover
    from numeric import strict_numeric_array
from core.ground import (STATUS_VALID, validate_constrained_ground,
                         validate_ground_plane)

KIND = "geometry_calibration"
SCHEMA_VERSION = 1
UNITS = {"length": "m", "angle": "rad"}
LENGTH_TO_M = {"m": 1.0, "mm": 0.001}
SUPPORTED_LENGTH_UNITS = tuple(sorted(LENGTH_TO_M))
ROTATION_TOLERANCE = 1e-6
MAX_MOUNT_TRANSLATION_M = 50.0
TRANSFORM_STATUSES = ("unknown", "synthetic", "verified")
ROTATION_STATUSES = ("unknown", "synthetic", "verified")
GROUND_STATUSES = ("valid", "orientation_unverified", "invalid")
# Evidence that may back a *real* mount. ``synthetic`` only marks test fixtures
# and can never be promoted to ``verified``.
TRANSFORM_EVIDENCE = ("measured_mount", "survey", "controlled_attitude",
                      "vendor_protocol", "synthetic")
REAL_TRANSFORM_EVIDENCE = tuple(item for item in TRANSFORM_EVIDENCE
                                if item != "synthetic")

# GL-02 ground-derived transform: a local ground frame from one validated plane.
# The block is additive/optional and never a measured extrinsic. Its nested
# schema version is independent of the parent artifact, so an unknown version is
# rejected instead of guessed/merged.
GROUND_DERIVED_KEY = "ground_derived"
GROUND_DERIVED_SCHEMA_VERSION = 1
GROUND_LOCAL_FRAME = "ground_local"
GROUND_DERIVED_UNITS = "m"
GROUND_DERIVED_DEFAULT_ORIGIN = "sensor_origin_ground_foot"
GROUND_DERIVED_DEFAULT_CONVENTION = "o=-d*n; u=proj(a); v=n x u; R=[u;v;n]; t=-R@o"
# Synthetic design value, NOT a field measurement: the reference axis must be
# far enough from the ground normal that its ground projection is not degenerate
# (0.05 ~= 2.9 degrees off the normal). The real installation axis is BLOCKED.
MIN_REFERENCE_AXIS_PROJECTION = 0.05
GROUND_DERIVED_TOLERANCE = 1e-6
_GROUND_DERIVED_REGION_KEYS = ("x_min_m", "x_max_m", "y_min_m", "y_max_m",
                               "z_min_m", "z_max_m")


class GeometryCalibrationError(ValueError):
    pass


def _strict_numeric_array(values, shape, field):
    """Shared helper with this module's error type, for callers in this file."""
    return strict_numeric_array(values, shape, field,
                                error_cls=GeometryCalibrationError)


def _numeric_array(values, shape, field):
    if values is None:
        raise GeometryCalibrationError(field + " is required")
    try:
        array = np.asarray(values, dtype=np.float64)
    except (TypeError, ValueError):
        raise GeometryCalibrationError(field + " must be numeric") from None
    if array.shape != shape:
        raise GeometryCalibrationError(
            "{} must have shape {}".format(field, shape))
    if not np.all(np.isfinite(array)):
        raise GeometryCalibrationError(field + " must be finite")
    return array


def validate_rotation(rotation, tolerance=ROTATION_TOLERANCE):
    """Return a validated 3x3 proper rotation, else raise.

    Rejects wrong shape, non-finite entries, non-orthonormal matrices
    (non-rigid / scaled / sheared) and reflections (``det=-1``, an axis-sign
    flip). Only a tolerance-checked orthogonal matrix with ``det=+1`` passes.
    """
    matrix = _numeric_array(rotation, (3, 3), "rotation")
    if abs(float(np.linalg.det(matrix))) < 1e-9:
        raise GeometryCalibrationError("rotation is singular")
    if not np.allclose(matrix @ matrix.T, np.eye(3), atol=float(tolerance)):
        raise GeometryCalibrationError(
            "rotation is not orthonormal (non-rigid matrix)")
    if float(np.linalg.det(matrix)) < 0.0:
        raise GeometryCalibrationError(
            "rotation has negative determinant (axis sign flip)")
    return matrix


def length_to_meters(value, units="m"):
    """Convert a finite length to metres; unknown units raise."""
    if units not in LENGTH_TO_M:
        raise GeometryCalibrationError("unsupported length unit: " + repr(units))
    number = float(value)
    if not np.isfinite(number):
        raise GeometryCalibrationError("length must be finite")
    return number * LENGTH_TO_M[units]


def validate_translation(translation, units="m",
                         max_magnitude_m=MAX_MOUNT_TRANSLATION_M):
    """Return a finite 3-vector in metres, else raise.

    A magnitude beyond ``max_magnitude_m`` (a plausible mount offset) is treated
    as ``unit_mismatch_suspected``: this catches millimetre values declared as
    metres (e.g. a 1.5 m mount entered as ``1500`` with ``units='m'``).
    """
    vector = _numeric_array(translation, (3,), "translation")
    meters = vector * LENGTH_TO_M.get(units, None) if units in LENGTH_TO_M else None
    if meters is None:
        raise GeometryCalibrationError("unsupported length unit: " + repr(units))
    magnitude = float(np.linalg.norm(meters))
    if max_magnitude_m is not None and magnitude > float(max_magnitude_m):
        raise GeometryCalibrationError(
            "unit_mismatch_suspected: translation magnitude {:.3f} m exceeds "
            "the plausible mount bound {:.3f} m".format(magnitude,
                                                        float(max_magnitude_m)))
    return meters


def _check_distinct_frames(from_frame, to_frame):
    for frame in (from_frame, to_frame):
        if not isinstance(frame, str) or not frame:
            raise GeometryCalibrationError("frame names must be non-empty strings")
    if from_frame == to_frame:
        raise GeometryCalibrationError(
            "from_frame and to_frame must differ; a same-name transform is "
            "never assumed to be identity")


def make_unknown_transform(from_frame, to_frame, note=None):
    _check_distinct_frames(from_frame, to_frame)
    return {"kind": "transform", "from_frame": from_frame, "to_frame": to_frame,
            "status": "unknown", "direction": "p_to = R @ p_from + t",
            "rotation": None, "translation_m": None, "units": UNITS["length"],
            "evidence": None, "note": note}


def make_transform(rotation, translation, from_frame, to_frame, units="m",
                   evidence=None, note=None,
                   max_magnitude_m=MAX_MOUNT_TRANSLATION_M):
    """Build a validated transform record with an explicit evidence source.

    Without evidence a numeric transform would be a fabricated mount, so this
    raises; callers that genuinely have no measurement use
    :func:`make_unknown_transform`. A ``synthetic`` transform is a test fixture
    and is certified as ``synthetic``, never ``verified``.
    """
    _check_distinct_frames(from_frame, to_frame)
    if evidence not in TRANSFORM_EVIDENCE:
        raise GeometryCalibrationError(
            "unsupported transform evidence {!r}: a mount transform requires "
            "measured_mount/survey/controlled_attitude/vendor_protocol".format(evidence))
    matrix = validate_rotation(rotation)
    meters = validate_translation(translation, units, max_magnitude_m)
    status = "verified" if evidence in REAL_TRANSFORM_EVIDENCE else "synthetic"
    return {"kind": "transform", "from_frame": from_frame, "to_frame": to_frame,
            "status": status, "direction": "p_to = R @ p_from + t",
            "rotation": matrix.tolist(), "translation_m": meters.tolist(),
            "units": UNITS["length"], "evidence": evidence, "note": note}


def make_rotation(rotation, from_frame, to_frame, evidence=None, note=None):
    """Rotation-only record (e.g. IMU axes into the LiDAR frame)."""
    _check_distinct_frames(from_frame, to_frame)
    if evidence not in TRANSFORM_EVIDENCE:
        raise GeometryCalibrationError(
            "unsupported rotation evidence {!r}: an IMU mounting rotation "
            "requires measured_mount/controlled_attitude/vendor_protocol".format(evidence))
    matrix = validate_rotation(rotation)
    status = "verified" if evidence in REAL_TRANSFORM_EVIDENCE else "synthetic"
    return {"kind": "rotation", "from_frame": from_frame, "to_frame": to_frame,
            "status": status, "rotation": matrix.tolist(),
            "evidence": evidence, "note": note}


def make_unknown_rotation(from_frame, to_frame, note=None):
    _check_distinct_frames(from_frame, to_frame)
    return {"kind": "rotation", "from_frame": from_frame, "to_frame": to_frame,
            "status": "unknown", "rotation": None, "evidence": None, "note": note}


def _load_transform(transform):
    if not isinstance(transform, dict) or transform.get("status") == "unknown":
        raise GeometryCalibrationError("transform is unknown")
    matrix = validate_rotation(transform.get("rotation"))
    meters = _numeric_array(transform.get("translation_m"), (3,), "translation_m")
    return matrix, meters


def validate_known_transform(transform):
    """Return a deep-copied, fully qualified known transform, else raise.

    Numeric R/t alone is not a qualification (GL-03 G03): a known transform
    must carry explicit non-empty distinct frames, the canonical direction,
    metres, an explicit evidence source and a status consistent with that
    evidence, besides the rigid rotation/plausible translation checks. It
    reuses :func:`make_transform` as the one strict constructor, so a record
    that could never have been built is never treated as usable. The input is
    not mutated; the copy is what a caller may bind.
    """
    if not isinstance(transform, dict) or transform.get("status") == "unknown":
        raise GeometryCalibrationError("transform is unknown")
    if transform.get("units") != UNITS["length"]:
        raise GeometryCalibrationError(
            "transform units must be " + repr(UNITS["length"]))
    recovered = make_transform(transform.get("rotation"),
                               transform.get("translation_m"),
                               transform.get("from_frame"),
                               transform.get("to_frame"),
                               units=transform.get("units", "m"),
                               evidence=transform.get("evidence"),
                               note=transform.get("note"))
    if recovered["status"] != transform.get("status"):
        raise GeometryCalibrationError(
            "transform status disagrees with its evidence source")
    direction = transform.get("direction")
    if direction is not None and direction != recovered["direction"]:
        raise GeometryCalibrationError("transform direction is not supported")
    return copy.deepcopy(transform)


def invert_transform(transform):
    """Return the inverse transform record (to->from).

    For ``p_to = R p_from + t`` the inverse is ``p_from = R.T p_to - R.T t``.
    The result reuses the same evidence/status, so identity is only ever the
    numerical inverse of a real transform, never an assumed one.
    """
    rotation, translation = _load_transform(transform)
    inverse_rotation = rotation.T
    inverse_translation = -inverse_rotation @ translation
    result = dict(transform)
    result["from_frame"], result["to_frame"] = transform["to_frame"], transform["from_frame"]
    result["rotation"] = inverse_rotation.tolist()
    result["translation_m"] = inverse_translation.tolist()
    return result


def transform_matrix(transform):
    """Homogeneous 4x4 matrix of a transform record."""
    rotation, translation = _load_transform(transform)
    matrix = np.eye(4)
    matrix[:3, :3] = rotation
    matrix[:3, 3] = translation
    return matrix


def apply_transform(points, transform):
    """Apply a transform to an (N,3) point array, returning points in ``to``."""
    try:
        array = np.asarray(points, dtype=np.float64)
    except (TypeError, ValueError):
        raise GeometryCalibrationError("points must be numeric") from None
    if array.ndim != 2 or array.shape[1] != 3 or not np.all(np.isfinite(array)):
        raise GeometryCalibrationError("points must be a finite (N,3) array")
    rotation, translation = _load_transform(transform)
    return array @ rotation.T + translation


def _same_transform_record(left, right):
    """Structural equality for two transform records (never raises)."""
    if not isinstance(left, dict) or not isinstance(right, dict):
        return False
    try:
        return json.dumps(left, sort_keys=True, separators=(",", ":"),
                          allow_nan=False) == \
            json.dumps(right, sort_keys=True, separators=(",", ":"),
                      allow_nan=False)
    except (TypeError, ValueError):
        return False


def calibration_reference_transform(calibration):
    """The artifact-owned lidar->reference transform, or None when unknown.

    A non-object ``transforms`` container or child record yields ``None`` here
    rather than a raw ``AttributeError``; structural qualification refuses such
    damage before a reference binding is consumed, so this is only a safeguard.
    A legal ``unknown``/absent record keeps the original no-canonical meaning.
    """
    if not isinstance(calibration, dict):
        return None
    transforms = calibration.get("transforms")
    if not isinstance(transforms, dict):
        return None
    record = transforms.get("T_reference_lidar")
    if isinstance(record, dict) and record.get("status") != "unknown":
        return record
    return None


# Constructor-exclusive full-product blocks (GL-03 G03 input classification):
# a complete geometry-calibration artifact always carries these, so their
# presence marks a full product whose missing/null ``kind`` is damage, not a
# legacy minimal summary. The summary-visible fields (calibration_id,
# schema_version, ground_status, ground_derived_id, frames, transforms, note)
# are deliberately not markers, and unknown ordinary extensions are not
# blacklisted.
FULL_ARTIFACT_KEYS = ("units", "created_at_utc", "rotations", "verification",
                      "status", "input", "ground", "ground_derived",
                      "sensor_height_m")


def _has_full_artifact_shape(calibration):
    return any(key in calibration for key in FULL_ARTIFACT_KEYS)


def _legacy_summary_reason(summary):
    """Reason a legacy minimal summary is unusable, else ``None``.

    A true summary (no full-product block, no ``kind``) keeps the original
    compatibility semantics: the optional containers and frame labels may be
    absent/``None`` (an empty object also means "undeclared"), and an absent or
    legal-``unknown`` canonical child keeps the standalone fallback. But every
    *declared* field must have its declared type -- a container is an object, a
    frame name is a non-empty string and the canonical child is an object -- and
    the explicitly present ``schema_version`` must be the supported one. A
    damaged container/child is refused here instead of surfacing a raw
    ``AttributeError`` in a later consumer, and is never mistaken for "no
    canonical record" (which would wrongly re-enable the standalone fallback).
    """
    if "schema_version" in summary:
        version = summary.get("schema_version")
        if isinstance(version, bool) or not isinstance(version, int) \
                or version != SCHEMA_VERSION:
            return "reference_calibration_invalid"
    frames = summary.get("frames")
    if frames is not None and not isinstance(frames, dict):
        return "reference_calibration_invalid"
    if isinstance(frames, dict):
        for label in ("lidar", "reference"):
            if label in frames:
                value = frames.get(label)
                if value is not None \
                        and (not isinstance(value, str) or not value):
                    return "reference_calibration_invalid"
    transforms = summary.get("transforms")
    if transforms is not None and not isinstance(transforms, dict):
        return "reference_calibration_invalid"
    if isinstance(transforms, dict) and "T_reference_lidar" in transforms:
        record = transforms.get("T_reference_lidar")
        if record is not None and not isinstance(record, dict):
            return "reference_calibration_invalid"
    return None


def resolve_reference_transform(calibration=None, transform=None, frame_id=None):
    """Effective lidar->reference transform for a producing frame, or ``None``.

    The geometry artifact owns the installation transform: when it carries a
    known ``T_reference_lidar`` a standalone caller transform that disagrees
    with that record is a conflict and is never silently preferred; with no
    known artifact record a legal standalone transform keeps the legacy
    support. Inputs are classified before validation: a supported artifact
    ``kind`` or the constructor-exclusive full-product blocks force the full
    validator, so deleting/nulling the ``kind`` of a complete product or an
    unsupported schema/identity can never be downgraded to the legacy path; an
    explicit non-artifact ``kind`` is refused. Only a true minimal summary (no
    full-product block, no ``kind``, supported-or-absent ``schema_version``,
    declared containers/labels/child of the declared types) keeps the legacy
    path. The effective record itself must be fully qualified
    (frames/direction/units/status/evidence/R/t), not merely numerically
    loadable, and a record whose ``from_frame`` differs from the actual
    producing ``frame_id`` or from the parent's declared ``frames.lidar``, or
    whose ``to_frame`` disagrees with the declared ``frames.reference``, can
    never supply reference coordinates. Returns
    ``(record_or_None, reason_or_None)``
    with a deep-copied record; an unusable reference is reported as ``None``
    (and the caller publishes null reference fields) rather than raising, so
    the ordinary no-reference/source-only path is unchanged.
    """
    parent = calibration if isinstance(calibration, dict) else None
    if parent is not None:
        kind = parent.get("kind")
        if kind == KIND or (kind is None and _has_full_artifact_shape(parent)):
            # A supported kind -- or a complete product whose kind was removed/
            # nulled -- must pass the supported validator end-to-end; a
            # different/unknown schema or a damaged identity is refused, never
            # silently treated as legacy (GL-03 G03).
            try:
                parent = validate_geometry_calibration(copy.deepcopy(parent))
            except (GeometryCalibrationError, TypeError, AttributeError,
                    KeyError):
                return None, "reference_calibration_invalid"
        elif kind is not None:
            # Explicit non-artifact kind: a damaged/foreign record, never a
            # legacy minimal summary (which has no ``kind``).
            return None, "reference_calibration_invalid"
        else:
            # True minimal summary: the explicitly present version and every
            # declared container/label/canonical child must have their declared
            # types before any consumer reads them (GL-03 G03).
            reason = _legacy_summary_reason(parent)
            if reason is not None:
                return None, reason
    canonical = calibration_reference_transform(parent)
    if canonical is not None:
        try:
            effective = validate_known_transform(canonical)
        except (GeometryCalibrationError, TypeError, ValueError):
            return None, "reference_transform_invalid"
        if isinstance(transform, dict) and transform.get("status") != "unknown" \
                and not _same_transform_record(transform, effective):
            return None, "reference_transform_conflict"
    elif isinstance(transform, dict) and transform.get("status") != "unknown":
        try:
            effective = validate_known_transform(transform)
        except (GeometryCalibrationError, TypeError, ValueError):
            return None, "reference_transform_invalid"
    else:
        return None, None
    if isinstance(frame_id, str) and frame_id:
        declared = effective.get("from_frame")
        if isinstance(declared, str) and declared and declared != frame_id:
            return None, "reference_from_frame_mismatch"
    declared_lidar = None
    reference_frame = None
    if parent is not None and isinstance(parent.get("frames"), dict):
        declared_lidar = parent["frames"].get("lidar")
        reference_frame = parent["frames"].get("reference")
    if isinstance(declared_lidar, str) and declared_lidar:
        # Cross-record binding: the producing ``from`` frame cannot contradict
        # the parent artifact's declared lidar frame (GL-03 G03), even when the
        # caller supplies no frame_id (node startup/reload binding). A declared
        # non-string label was already refused by the structural guard, so it
        # can never silently skip this comparison.
        declared = effective.get("from_frame")
        if isinstance(declared, str) and declared and declared != declared_lidar:
            return None, "reference_from_frame_mismatch"
    to_frame = effective.get("to_frame")
    if reference_frame and isinstance(to_frame, str) and to_frame \
            and to_frame != reference_frame:
        return None, "reference_to_frame_mismatch"
    return effective, None


def apply_rotation(vectors, rotation_record):
    """Rotate (N,3) vectors by a rotation-only record."""
    array = np.asarray(vectors, dtype=np.float64)
    if array.ndim != 2 or array.shape[1] != 3 or not np.all(np.isfinite(array)):
        raise GeometryCalibrationError("vectors must be a finite (N,3) array")
    if not isinstance(rotation_record, dict) or rotation_record.get("status") == "unknown":
        raise GeometryCalibrationError("rotation is unknown")
    matrix = validate_rotation(rotation_record.get("rotation"))
    return array @ matrix.T


def sensor_height_from_ground(ground):
    """Signed height of the sensor origin above a ground plane, in metres.

    The plane is ``n . p + d = 0`` with ``n`` the unit normal pointing toward
    the sensor (up) and the ground below the origin. The origin's signed
    distance is ``d``; a sensor above its ground has ``d > 0`` and height ``d``.
    A plane at or above the origin, or any non-finite/missing value, stays
    ``None`` instead of guessing.
    """
    if not isinstance(ground, dict) or ground.get("status") != "valid":
        return None
    normal = np.asarray(ground.get("normal"), dtype=np.float64)
    offset = ground.get("offset_m")
    if normal.shape != (3,) or offset is None:
        return None
    if not np.all(np.isfinite(normal)) or not np.isfinite(float(offset)):
        return None
    if normal[2] < 0.0:
        normal = -normal
        offset = -float(offset)
    height = float(offset)
    if height <= 0.0:
        return None
    return height


def _unit_vector3(values, name, tolerance=1e-6):
    vector = _numeric_array(values, (3,), name)
    norm = float(np.linalg.norm(vector))
    if abs(norm - 1.0) > float(tolerance):
        raise GeometryCalibrationError(name + " must be unit length (norm %.6f)" % norm)
    return vector


def _reference_axis_projection(reference_axis, normal,
                               min_projection=MIN_REFERENCE_AXIS_PROJECTION):
    """Ground X direction: the unit projection of ``reference_axis`` onto the plane.

    A reference axis nearly parallel to the normal has a degenerate projection;
    it is rejected rather than producing an arbitrary X axis.
    """
    axis = _numeric_array(reference_axis, (3,), "x_reference_axis_source")
    projection = axis - float(axis @ normal) * normal
    magnitude = float(np.linalg.norm(projection))
    if magnitude < float(min_projection):
        raise GeometryCalibrationError(
            "x_reference_axis_source is too close to the ground normal "
            "(projection %.4f < %.4f): the ground X axis is degenerate"
            % (magnitude, float(min_projection)))
    return projection / magnitude


def ground_derived_basis(ground, reference_axis):
    """Return ``(R, t, n, d, u, v)`` for the PLAN ``ground_local`` frame.

    ``n`` is the validated unit up normal of ``n . p + d = 0``, ``o = -d*n`` the
    sensor-origin ground foot, ``u`` the unit ground projection of the reference
    axis, ``v = n x u`` and ``R = [u; v; n]`` (rows), ``t = -R @ o`` so that
    ``p_ground = R @ p_source + t`` and the sensor origin maps to ``[0, 0, d]``.
    Never fabricates a plane: it requires an already-valid ground record.
    """
    if not isinstance(ground, dict) or ground.get("status") != STATUS_VALID:
        raise GeometryCalibrationError(
            "a valid ground plane is required for a ground-derived transform")
    normal = _unit_vector3(ground.get("normal"), "ground.normal")
    offset = ground.get("offset_m")
    if isinstance(offset, bool) or not isinstance(offset, (int, float, np.integer,
                                                           np.floating)):
        raise GeometryCalibrationError("ground.offset_m must be a finite number")
    offset = float(offset)
    if not np.isfinite(offset) or offset <= 0.0:
        raise GeometryCalibrationError(
            "ground.offset_m must be a positive sensor height")
    u = _reference_axis_projection(reference_axis, normal)
    v = np.cross(normal, u)
    rotation = validate_rotation(np.vstack([u, v, normal]))
    origin = -offset * normal
    translation = -rotation @ origin
    return rotation, translation, normal, offset, u, v


def _derived_region_from_source(ground, rotation, translation):
    """Ground-local AABB from the source valid_region corners (point count kept)."""
    region = ground.get("valid_region")
    if not isinstance(region, dict):
        raise GeometryCalibrationError(
            "a ground-derived transform needs the source valid_region bounds")
    for key in _GROUND_DERIVED_REGION_KEYS:
        value = region.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float, np.integer,
                                                             np.floating)) \
                or not np.isfinite(float(value)):
            raise GeometryCalibrationError(
                "ground.valid_region." + key + " must be finite")
    point_count = region.get("point_count")
    if not isinstance(point_count, int) or isinstance(point_count, bool) \
            or point_count < 0:
        raise GeometryCalibrationError(
            "ground.valid_region.point_count must be a non-negative integer")
    xs = (float(region["x_min_m"]), float(region["x_max_m"]))
    ys = (float(region["y_min_m"]), float(region["y_max_m"]))
    zs = (float(region["z_min_m"]), float(region["z_max_m"]))
    corners = np.array([[x, y, z] for x in xs for y in ys for z in zs])
    mapped = corners @ rotation.T + translation
    low, high = mapped.min(axis=0), mapped.max(axis=0)
    return {"available": True, "source": "source_valid_region_corners",
            "x_min_m": float(low[0]), "x_max_m": float(high[0]),
            "y_min_m": float(low[1]), "y_max_m": float(high[1]),
            "z_min_m": float(low[2]), "z_max_m": float(high[2]),
            "point_count": int(point_count),
            # An auto-derived AABB of the *source* valid_region corners is only an
            # outer geometric bound: it proves no ground identity or coverage, so
            # monitoring must never report ok from it. trusted stays False.
            "trusted": False, "evidence": None}


def _region_trusted_fields(region):
    trusted = region.get("trusted")
    if trusted is not None and not isinstance(trusted, bool):
        raise GeometryCalibrationError(
            "valid_region_ground_local.trusted must be a boolean")
    evidence = region.get("evidence")
    if evidence is not None and (not isinstance(evidence, str) or not evidence):
        raise GeometryCalibrationError(
            "valid_region_ground_local.evidence must be a non-empty string")
    trusted = bool(trusted)
    if trusted and not evidence:
        raise GeometryCalibrationError(
            "a trusted ground ROI must record its evidence source")
    return trusted, evidence


def _normalise_ground_region(region):
    if not isinstance(region, dict):
        raise GeometryCalibrationError(
            "valid_region_ground_local must be an object")
    normalised = {"available": bool(region.get("available", True))}
    if region.get("source") is not None:
        normalised["source"] = region["source"]
    if not normalised["available"]:
        normalised["reason"] = region.get("reason")
        return normalised
    for key in _GROUND_DERIVED_REGION_KEYS:
        value = region.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float, np.integer,
                                                             np.floating)) \
                or not np.isfinite(float(value)):
            raise GeometryCalibrationError(
                "valid_region_ground_local." + key + " must be finite")
        normalised[key] = float(value)
    if normalised["x_min_m"] > normalised["x_max_m"] \
            or normalised["y_min_m"] > normalised["y_max_m"] \
            or normalised["z_min_m"] > normalised["z_max_m"]:
        raise GeometryCalibrationError(
            "valid_region_ground_local bounds are inconsistent")
    point_count = region.get("point_count")
    if not isinstance(point_count, int) or isinstance(point_count, bool) \
            or point_count < 0:
        raise GeometryCalibrationError(
            "valid_region_ground_local.point_count must be a non-negative integer")
    normalised["point_count"] = int(point_count)
    trusted, evidence = _region_trusted_fields(region)
    normalised["trusted"] = trusted
    normalised["evidence"] = evidence
    return normalised


def _ground_derived_identity(block):
    """The exact content a ``ground_derived_id`` binds (stable JSON subset)."""
    return {"n": block["n"], "d": block["d"], "R": block["R"], "t": block["t"],
            "from_frame": block["from_frame"], "to_frame": block["to_frame"],
            "valid_region_ground_local": block.get("valid_region_ground_local"),
            "source": block.get("source") or {}}


def ground_derived_id_for(block):
    payload = json.dumps(_ground_derived_identity(block), sort_keys=True,
                         separators=(",", ":"), allow_nan=False)
    return "gd_" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _resolve_applicability(applicability):
    resolved = {"single_plane_assumed": True, "single_plane_confirmed": False,
                "single_plane_note": ("software precondition (fixed mount, flat "
                                      "indoor, one dominant plane); declared is "
                                      "not confirmed"),
                "confirmed_note": ("field confirmation flag; stays false until "
                                   "measured/confirmed")}
    for key, value in (applicability or {}).items():
        if key not in resolved:
            raise GeometryCalibrationError(
                "unknown ground_derived applicability field: " + str(key))
        resolved[key] = value
    for key in ("single_plane_assumed", "single_plane_confirmed"):
        if not isinstance(resolved[key], bool):
            raise GeometryCalibrationError(key + " must be a boolean")
    return resolved


def build_ground_derived(ground, reference_axis, source=None, created_at_utc=None,
                         valid_region_ground_local=None, applicability=None,
                         note=None):
    """Build a validated ``ground_derived`` block from a valid ground plane.

    The result is explicitly a candidate local frame: geometric usability is
    separate from ground-identity confirmation and from physical height
    verification, and every verification flag stays false. It never writes into
    the measured extrinsics and never claims north/body-forward.
    """
    rotation, translation, normal, offset, _, _ = ground_derived_basis(
        ground, reference_axis)
    from_frame = ground.get("frame")
    if not isinstance(from_frame, str) or not from_frame:
        raise GeometryCalibrationError("ground.frame must be a non-empty string")
    if valid_region_ground_local is None:
        region = _derived_region_from_source(ground, rotation, translation)
    else:
        region = _normalise_ground_region(valid_region_ground_local)
    source = dict(source) if source else {"kind": "synthetic_fixture"}
    block = {
        "kind": GROUND_DERIVED_KEY,
        "schema_version": GROUND_DERIVED_SCHEMA_VERSION,
        "units": GROUND_DERIVED_UNITS,
        "from_frame": from_frame,
        "to_frame": GROUND_LOCAL_FRAME,
        "R": rotation.tolist(),
        "t": translation.tolist(),
        "n": [float(value) for value in normal],
        "d": float(offset),
        "origin": GROUND_DERIVED_DEFAULT_ORIGIN,
        "x_reference_axis_source": [float(value) for value in
                                    _numeric_array(reference_axis, (3,),
                                                   "x_reference_axis_source")],
        "convention": GROUND_DERIVED_DEFAULT_CONVENTION,
        "applicability": _resolve_applicability(applicability),
        "valid_region_ground_local": region,
        "source": source,
        "created_at_utc": created_at_utc,
        "physical_verified": False,
        "note": note,
    }
    block["ground_derived_id"] = ground_derived_id_for(block)
    return validate_ground_derived(block, expected_from_frame=from_frame)


def _ground_derived_region_validate(region):
    if not isinstance(region, dict):
        raise GeometryCalibrationError("valid_region_ground_local must be an object")
    if "available" in region and not isinstance(region["available"], bool):
        raise GeometryCalibrationError("valid_region_ground_local.available must be a boolean")
    if region.get("available") is False:
        return
    for key in _GROUND_DERIVED_REGION_KEYS:
        if key not in region:
            raise GeometryCalibrationError(
                "valid_region_ground_local." + key + " is required")
        value = region[key]
        if isinstance(value, bool) or not isinstance(value, (int, float, np.integer,
                                                             np.floating)) \
                or not np.isfinite(float(value)):
            raise GeometryCalibrationError(
                "valid_region_ground_local." + key + " must be finite")
    if region["x_min_m"] > region["x_max_m"] or region["y_min_m"] > region["y_max_m"] \
            or region["z_min_m"] > region["z_max_m"]:
        raise GeometryCalibrationError(
            "valid_region_ground_local bounds are inconsistent")
    if "point_count" in region:
        point_count = region["point_count"]
        if not isinstance(point_count, int) or isinstance(point_count, bool) \
                or point_count < 0:
            raise GeometryCalibrationError(
                "valid_region_ground_local.point_count must be a non-negative integer")
    _region_trusted_fields(region)


def _validate_ground_derived_source(source, artifact=None):
    """The origin record every new derived artifact must carry.

    ``sha256`` must be 64 *hex* characters (anything else could not be a real
    digest), and whenever the parent artifact records an ``input.sha256`` the
    derived block must name that same hash or explain why its source differs
    via ``sha256_reason``; silently disagreeing hashes are rejected instead of
    guessing.
    """
    if not isinstance(source, dict):
        raise GeometryCalibrationError(
            "ground_derived.source must be an origin record object")
    kind = source.get("kind")
    if not isinstance(kind, str) or not kind:
        raise GeometryCalibrationError(
            "ground_derived.source.kind must be a non-empty string")
    frame = source.get("frame")
    if frame is not None and (not isinstance(frame, str) or not frame):
        raise GeometryCalibrationError(
            "ground_derived.source.frame must be a non-empty string when present")
    sha256 = source.get("sha256")
    if sha256 is not None and (
            not isinstance(sha256, str) or len(sha256) != 64
            or not all(char in "0123456789abcdefABCDEF" for char in sha256)):
        raise GeometryCalibrationError(
            "ground_derived.source.sha256 must be a 64-char hex string when present")
    reason = source.get("sha256_reason")
    if reason is not None and (not isinstance(reason, str) or not reason):
        raise GeometryCalibrationError(
            "ground_derived.source.sha256_reason must be a non-empty string")
    if isinstance(artifact, dict):
        parent_input = artifact.get("input")
        parent_sha = parent_input.get("sha256") \
            if isinstance(parent_input, dict) else None
        if parent_sha and sha256 is not None \
                and sha256.lower() != parent_sha.lower() and not reason:
            raise GeometryCalibrationError(
                "ground_derived.source.sha256 disagrees with the parent "
                "input.sha256 without a sha256_reason")
    return source


def validate_ground_derived(block, expected_from_frame=None, artifact=None,
                            _prevalidated=False):
    """Strictly validate a persisted ``ground_derived`` block, else raise.

    Rejects a missing/unknown nested schema version, non-metre units, illegal or
    same frames, a non-unit ``n``, a non-rigid/reflected ``R``, an ``R`` that
    disagrees with ``n``/the reference-axis projection, a ``t`` inconsistent with
    ``n``/``d``, a near-normal (degenerate) reference axis, a damaged content id,
    and any attempt to mark the candidate physically verified or identity
    confirmed. It never promotes a candidate to verified.
    """
    if not isinstance(block, dict) or block.get("kind") != GROUND_DERIVED_KEY:
        raise GeometryCalibrationError(
            "ground_derived must be an object with kind " + repr(GROUND_DERIVED_KEY))
    # Strict integer version: bool/True and floats (1.0 == 1) must never pass.
    version = block.get("schema_version")
    if isinstance(version, bool) or not isinstance(version, int) \
            or version != GROUND_DERIVED_SCHEMA_VERSION:
        raise GeometryCalibrationError("unsupported ground_derived schema_version")
    if block.get("units") != GROUND_DERIVED_UNITS:
        raise GeometryCalibrationError("ground_derived units must be " + repr(GROUND_DERIVED_UNITS))
    from_frame, to_frame = block.get("from_frame"), block.get("to_frame")
    if not isinstance(from_frame, str) or not from_frame:
        raise GeometryCalibrationError("ground_derived.from_frame must be a non-empty string")
    if to_frame != GROUND_LOCAL_FRAME:
        raise GeometryCalibrationError(
            "ground_derived.to_frame must be " + repr(GROUND_LOCAL_FRAME))
    if from_frame == to_frame:
        raise GeometryCalibrationError("ground_derived frames must differ")
    if expected_from_frame is not None and from_frame != expected_from_frame:
        raise GeometryCalibrationError(
            "ground_derived.from_frame does not match the artifact lidar frame")
    normal = _strict_numeric_array(block.get("n"), (3,), "ground_derived.n")
    norm = float(np.linalg.norm(normal))
    if abs(norm - 1.0) > 1e-6:
        raise GeometryCalibrationError(
            "ground_derived.n must be unit length (norm %.6f)" % norm)
    offset = block.get("d")
    if isinstance(offset, bool) or not isinstance(offset, (int, float, np.integer,
                                                           np.floating)):
        raise GeometryCalibrationError("ground_derived.d must be a finite number")
    offset = float(offset)
    if not np.isfinite(offset) or offset <= 0.0:
        raise GeometryCalibrationError(
            "ground_derived.d must be a positive sensor height")
    # Elements are validated before any NumPy conversion: a bool True must not
    # silently become the 1.0 an identity matrix happens to contain.
    rotation = _strict_numeric_array(block.get("R"), (3, 3), "ground_derived.R")
    if abs(float(np.linalg.det(rotation))) < 1e-9:
        raise GeometryCalibrationError("rotation is singular")
    if not np.allclose(rotation @ rotation.T, np.eye(3), atol=ROTATION_TOLERANCE):
        raise GeometryCalibrationError(
            "rotation is not orthonormal (non-rigid matrix)")
    if float(np.linalg.det(rotation)) < 0.0:
        raise GeometryCalibrationError(
            "rotation has negative determinant (axis sign flip)")
    if not np.allclose(rotation[2], normal, atol=GROUND_DERIVED_TOLERANCE):
        raise GeometryCalibrationError(
            "ground_derived.R row 3 disagrees with n")
    u = _reference_axis_projection(
        _strict_numeric_array(block.get("x_reference_axis_source"), (3,),
                              "x_reference_axis_source"), normal)
    if not np.allclose(rotation[0], u, atol=GROUND_DERIVED_TOLERANCE):
        raise GeometryCalibrationError(
            "ground_derived.R row 1 disagrees with the reference-axis projection")
    if not np.allclose(rotation[1], np.cross(normal, u), atol=GROUND_DERIVED_TOLERANCE):
        raise GeometryCalibrationError("ground_derived.R row 2 disagrees with n x u")
    translation = _strict_numeric_array(block.get("t"), (3,), "ground_derived.t")
    origin = -offset * normal
    if not np.allclose(translation, -rotation @ origin, atol=GROUND_DERIVED_TOLERANCE):
        raise GeometryCalibrationError(
            "ground_derived.t disagrees with n/d (t must equal -R @ o)")
    applicability = block.get("applicability")
    if not isinstance(applicability, dict):
        raise GeometryCalibrationError("ground_derived.applicability must be an object")
    if applicability.get("single_plane_assumed") is not True:
        raise GeometryCalibrationError(
            "ground_derived must declare the single-plane software assumption")
    if applicability.get("single_plane_confirmed") is not False:
        raise GeometryCalibrationError(
            "ground_derived.single_plane_confirmed must stay false until confirmed")
    if block.get("physical_verified") is not False:
        raise GeometryCalibrationError(
            "ground_derived.physical_verified must stay false for an unmeasured candidate")
    _ground_derived_region_validate(block.get("valid_region_ground_local"))
    _validate_ground_derived_source(block.get("source"), artifact=artifact)
    created = block.get("created_at_utc")
    if created is not None and (not isinstance(created, str) or not created):
        raise GeometryCalibrationError(
            "ground_derived.created_at_utc must be a non-empty string or null")
    recorded_id = block.get("ground_derived_id")
    if not isinstance(recorded_id, str) or not recorded_id:
        raise GeometryCalibrationError("ground_derived.ground_derived_id is required")
    if recorded_id != ground_derived_id_for(block):
        raise GeometryCalibrationError(
            "ground_derived.ground_derived_id does not match its content (damaged)")
    # Return a bound copy so a caller cannot mutate the original dict in place
    # after validation and desynchronise an already-stored record.
    return copy.deepcopy(block)


def apply_ground_derived(points, block):
    """Map (N,3) source points into ``ground_local`` (no measured mount)."""
    validate_ground_derived(block)
    try:
        array = np.asarray(points, dtype=np.float64)
    except (TypeError, ValueError):
        raise GeometryCalibrationError("points must be numeric") from None
    if array.ndim != 2 or array.shape[1] != 3 or not np.all(np.isfinite(array)):
        raise GeometryCalibrationError("points must be a finite (N,3) array")
    rotation = np.asarray(block["R"], dtype=np.float64)
    translation = np.asarray(block["t"], dtype=np.float64)
    return array @ rotation.T + translation


def ground_derived_inverse(block):
    """Numeric inverse mapping (ground_local -> source); not a second artifact."""
    validate_ground_derived(block)
    rotation = np.asarray(block["R"], dtype=np.float64)
    translation = np.asarray(block["t"], dtype=np.float64)
    return {"from_frame": block["to_frame"], "to_frame": block["from_frame"],
            "R": rotation.T.tolist(),
            "t": (-rotation.T @ translation).tolist()}


def ground_derived_status(block):
    """Separate geometric usability, identity confirmation and physical verification."""
    if not isinstance(block, dict):
        return {"present": False, "geometric_usable": False,
                "ground_identity_confirmed": False,
                "physical_height_verified": False}
    applicability = block.get("applicability") or {}
    return {"present": True, "ground_derived_id": block.get("ground_derived_id"),
            "geometric_usable": True,
            "ground_identity_confirmed": bool(
                applicability.get("single_plane_confirmed")),
            "physical_height_verified": block.get("physical_verified") is True}


def _validate_ground_derived_consistency(ground, block):
    """The derived block must agree with the parent ground it was built from.

    Each block passing its own validator is not enough: a derived transform that
    carries a different frame, normal or offset than the parent ground is a
    cross-record inconsistency, and R/t must reconstruct from the same plane.
    """
    if not isinstance(ground, dict) or ground.get("status") != STATUS_VALID:
        raise GeometryCalibrationError(
            "ground_derived requires a valid parent ground record")
    if ground.get("frame") != block.get("from_frame"):
        raise GeometryCalibrationError(
            "ground_derived.from_frame does not match the parent ground.frame")
    parent_normal = np.asarray(ground.get("normal"), dtype=np.float64)
    block_normal = np.asarray(block.get("n"), dtype=np.float64)
    if not np.allclose(block_normal, parent_normal, atol=GROUND_DERIVED_TOLERANCE):
        raise GeometryCalibrationError(
            "ground_derived.n disagrees with the parent ground.normal")
    parent_offset = float(ground.get("offset_m"))
    if not np.isclose(float(block.get("d")), parent_offset,
                      atol=GROUND_DERIVED_TOLERANCE):
        raise GeometryCalibrationError(
            "ground_derived.d disagrees with the parent ground.offset_m")
    return block


def _validate_geometry_calibration(artifact):
    """Full structural validation; never mutates the passed artifact."""
    if not isinstance(artifact, dict):
        raise GeometryCalibrationError("artifact must be an object")
    if artifact.get("kind") != KIND:
        raise GeometryCalibrationError("kind must be " + repr(KIND))
    # Strict parent identity/version: a bool/float schema_version (True/1.0) or a
    # blank/absent/non-string calibration_id must never pass, exactly as the
    # constructor refuses to build them. Otherwise a damaged artifact with a
    # falsy id would silently take the ground-only fallback at startup.
    calibration_id = artifact.get("calibration_id")
    if isinstance(calibration_id, bool) or not isinstance(calibration_id, str) \
            or not calibration_id:
        raise GeometryCalibrationError("calibration_id must be a non-empty string")
    version = artifact.get("schema_version")
    if isinstance(version, bool) or not isinstance(version, int) \
            or version != SCHEMA_VERSION:
        raise GeometryCalibrationError("unsupported schema_version")
    if artifact.get("units") != UNITS:
        raise GeometryCalibrationError("units must be " + repr(UNITS))
    frames = artifact.get("frames")
    if not isinstance(frames, dict):
        raise GeometryCalibrationError("frames must be an object")
    lidar_frame = frames.get("lidar")
    if not isinstance(lidar_frame, str) or not lidar_frame:
        raise GeometryCalibrationError("frames.lidar must be a non-empty string")
    reference_frame = frames.get("reference")
    if reference_frame is not None \
            and (not isinstance(reference_frame, str) or not reference_frame):
        raise GeometryCalibrationError(
            "frames.reference must be null or a non-empty string")
    for field in ("transforms", "rotations"):
        container = artifact.get(field)
        if container is not None and not isinstance(container, dict):
            raise GeometryCalibrationError(field + " must be an object")
    for name, record in (artifact.get("transforms") or {}).items():
        if not isinstance(record, dict):
            raise GeometryCalibrationError(
                "transform record must be an object: " + str(name))
        if record.get("status") != "unknown":
            recovered = make_transform(record.get("rotation"),
                                       record.get("translation_m"),
                                       record.get("from_frame"),
                                       record.get("to_frame"),
                                       units=record.get("units", "m"),
                                       evidence=record.get("evidence"),
                                       note=record.get("note"))
            if recovered["status"] != record.get("status"):
                raise GeometryCalibrationError("transform status mismatch: " + name)
        else:
            _check_distinct_frames(record.get("from_frame"), record.get("to_frame"))
    for name, record in (artifact.get("rotations") or {}).items():
        if not isinstance(record, dict):
            raise GeometryCalibrationError(
                "rotation record must be an object: " + str(name))
        if record.get("status") != "unknown":
            recovered = make_rotation(record.get("rotation"), record.get("from_frame"),
                                      record.get("to_frame"),
                                      evidence=record.get("evidence"),
                                      note=record.get("note"))
            if recovered["status"] != record.get("status"):
                raise GeometryCalibrationError("rotation status mismatch: " + name)
        else:
            _check_distinct_frames(record.get("from_frame"), record.get("to_frame"))
    ground = artifact.get("ground")
    if ground is not None:
        if not isinstance(ground, dict):
            raise GeometryCalibrationError("invalid ground record: must be an object")
        try:
            validate_ground_plane(ground, expected_frame=frames["lidar"])
        except ValueError as exc:
            raise GeometryCalibrationError("invalid ground record: " + str(exc)) from None
    ground_derived = artifact.get(GROUND_DERIVED_KEY)
    if ground_derived is not None:
        # Additive/optional. A damaged block or an unknown nested version is
        # rejected outright so a client can never fall back to a green ground
        # mode; an old v1 client that does not know the key simply ignores it.
        # The parent sha rule consults the caller-visible artifact only (the
        # derived copy is not yet bound).
        ground_derived = validate_ground_derived(
            ground_derived, expected_from_frame=frames["lidar"], artifact=artifact)
        _validate_ground_derived_consistency(ground, ground_derived)
    # A constrained-ground record must pass the GL-01 strict validator too;
    # structural presence alone is not enough.
    if isinstance(artifact.get("constrained_ground"), dict):
        try:
            validate_constrained_ground(artifact["constrained_ground"],
                                        expected_frame=frames["lidar"])
        except ValueError as exc:
            raise GeometryCalibrationError(
                "invalid constrained_ground record: " + str(exc)) from None
    verification = artifact.get("verification")
    if not isinstance(verification, dict):
        raise GeometryCalibrationError("verification must be an object")
    transforms = artifact.get("transforms") or {}
    rotations = artifact.get("rotations") or {}
    consistency = (
        ("extrinsics_verified",
         transforms.get("T_reference_lidar", {}).get("status") == "verified"),
        ("imu_alignment_verified",
         rotations.get("R_lidar_imu", {}).get("status") == "verified"),
        ("ground_physical_verified",
         ground is not None and ground.get("status") == STATUS_VALID),
    )
    for flag, satisfied in consistency:
        if verification.get(flag) is True and not satisfied:
            raise GeometryCalibrationError(
                "verification." + flag + " contradicts an unknown/synthetic record")
    statuses = artifact.get("status")
    if not isinstance(statuses, dict):
        raise GeometryCalibrationError("status must be an object")
    if statuses.get("ground") == "valid" and (ground is None
                                              or ground.get("status") != STATUS_VALID):
        raise GeometryCalibrationError("status.ground=valid contradicts the ground record")
    return ground_derived


def validate_geometry_calibration(artifact):
    """Validate and normalise a geometry-calibration artifact.

    Structural checks only; it does not turn an unverified fit into a verified
    one. Unknown transforms/rotations/ground are allowed and preserved, but any
    present numeric record must pass the rigid/unit checks. The passed artifact
    is never mutated: validation is performed first, and the caller receives a
    new canonical artifact in which input sub-records are deep copies bound
    after validation, so a caller cannot edit the original dict afterwards to
    desynchronise a stored record.
    """
    validated_derived = _validate_geometry_calibration(artifact)
    canonical = copy.deepcopy(artifact)
    if validated_derived is not None:
        canonical[GROUND_DERIVED_KEY] = validated_derived
    parent_input = canonical.get("input")
    if isinstance(parent_input, dict) and parent_input.get("source") is None \
            and parent_input.get("constrained") is not True \
            and parent_input.get("created_by") is None:
        # Origin honesty for caller-built fixtures: a caller that never
        # described real input gets an explicit synthetic label rather than a
        # blank one. Persisted artifacts are not built through this path.
        if canonical.get("ground") is not None and canonical.get("created_at_utc"):
            parent_input["source"] = "synthetic_fixture"
    return canonical


def ground_context_calibration(ground, ground_derived, parent_calibration=None,
                               fallback_frame=None):
    """Build the single canonical artifact any context entry point binds.

    Every supported ground-context path (full artifact, paired
    ground+derived update, ground-only derive/update) yields exactly one
    canonical artifact built here, so the published
    ``calibration.calibration_id``/``ground_derived.ground_derived_id`` can
    never disagree with the ground/derived the core actually consumes. The
    parent record's own id is used when it matches; a caller-built pair with a
    caller-owned id gets a content-derived ``ground-context-<sha>`` id because
    quoting the old caller id unchanged would mislabel a new context as the
    old version (the pair was never validated together before). ``ground``
    and ``ground_derived`` must already be validated/canonical copies; the
    returned artifact is fully validated again here.
    """
    lidar_frame = None
    if fallback_frame:
        lidar_frame = fallback_frame
    if isinstance(parent_calibration, dict):
        frame = (parent_calibration.get("frames") or {}).get("lidar")
        if frame:
            lidar_frame = frame
    if isinstance(ground, dict) and ground.get("frame"):
        lidar_frame = ground["frame"]
    if not lidar_frame:
        raise GeometryCalibrationError("a lidar frame is required to bind a "
                                       "ground context artifact")
    calibration_id = None
    created_at_utc = "unset"
    if isinstance(parent_calibration, dict) \
            and parent_calibration.get("kind") == KIND:
        parent_ground = parent_calibration.get("ground")
        parent_derived = parent_calibration.get(GROUND_DERIVED_KEY)
        ground_same = (parent_ground is None) is (ground is None)
        if ground_same and parent_ground is not None:
            ground_same = json.dumps(parent_ground, sort_keys=True,
                                     separators=(",", ":"), allow_nan=False) \
                == json.dumps(ground, sort_keys=True,
                              separators=(",", ":"), allow_nan=False)
        derived_same = (parent_derived is None) is (ground_derived is None)
        if derived_same and parent_derived is not None:
            derived_same = json.dumps(parent_derived, sort_keys=True,
                                      separators=(",", ":"), allow_nan=False) \
                == json.dumps(ground_derived, sort_keys=True,
                              separators=(",", ":"), allow_nan=False)
        if ground_same and derived_same \
                and isinstance(parent_calibration.get("calibration_id"), str) \
                and parent_calibration["calibration_id"]:
            # Unchanged same version: re-validate the *whole* parent artifact
            # (damaged records are refused, not re-loaded) and return a fresh
            # deep copy so the full product (input.sha256/input.evidence/note/
            # reference/transforms/rotations/status/verification/constrained_
            # ground and any legal extension) is preserved, the core stays
            # decoupled from caller mutation, and no new version is fabricated.
            preserved = validate_geometry_calibration(
                copy.deepcopy(parent_calibration))
            preserved["ground"] = copy.deepcopy(ground) if ground is not None else None
            if ground_derived is not None:
                preserved[GROUND_DERIVED_KEY] = copy.deepcopy(ground_derived)
            else:
                preserved.pop(GROUND_DERIVED_KEY, None)
            preserved["sensor_height_m"] = \
                sensor_height_from_ground(preserved["ground"]) \
                if preserved["ground"] is not None else None
            return validate_geometry_calibration(preserved)
        if isinstance(parent_calibration.get("created_at_utc"), str) \
                and parent_calibration["created_at_utc"]:
            created_at_utc = parent_calibration["created_at_utc"]
    if calibration_id is None:
        payload = json.dumps({"ground": ground, GROUND_DERIVED_KEY: ground_derived,
                              "frame": lidar_frame},
                             sort_keys=True, separators=(",", ":"),
                             allow_nan=False)
        calibration_id = "ground-context-" \
            + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
    return build_geometry_calibration(
        calibration_id, created_at_utc, lidar_frame,
        ground=ground, ground_derived=ground_derived)


def ground_context_from_calibration(calibration):
    """Return ``(ground_copy, derived_copy_or_None)`` from a loaded artifact.

    Both sub-records are freshly deep-copied from the loaded artifact: the
    ground the core consumes and the derived block the monitor uses always
    stay bound to the same validated parent, and a caller-side later edit can
    never desynchronise them.
    """
    if not isinstance(calibration, dict):
        return None, None
    ground = calibration.get("ground")
    ground = copy.deepcopy(ground) if isinstance(ground, dict) else None
    derived = calibration.get(GROUND_DERIVED_KEY)
    derived = copy.deepcopy(derived) if isinstance(derived, dict) else None
    return ground, derived


def default_statuses():
    return {"extrinsics": "unknown", "imu_alignment": "unknown",
            "ground": "unknown", "geometry_params": "pending"}


def default_verification():
    return {"ground_physical_verified": False, "extrinsics_verified": False,
            "imu_alignment_verified": False}


def build_geometry_calibration(calibration_id, created_at_utc, lidar_frame,
                               reference_frame=None, transforms=None,
                               rotations=None, ground=None, ground_derived=None,
                               input_info=None, statuses=None, verification=None,
                               note=None):
    """Assemble and validate an independent geometry-calibration artifact.

    ``transforms``/``rotations`` are records built by the ``make_*`` helpers.
    Missing installation transforms and IMU mounting stay explicit ``unknown``
    records, never silent identity matrices. An optional ``ground_derived``
    block adds a candidate local ground frame without touching the measured
    extrinsics or any verification flag.
    """
    if not isinstance(calibration_id, str) or not calibration_id:
        raise GeometryCalibrationError("calibration_id must be a non-empty string")
    if not isinstance(created_at_utc, str) or not created_at_utc:
        raise GeometryCalibrationError("created_at_utc must be a non-empty string")
    if reference_frame is not None:
        _check_distinct_frames(lidar_frame, reference_frame)
    transforms = dict(transforms or {})
    rotations = dict(rotations or {})
    if reference_frame is not None and "T_reference_lidar" not in transforms:
        transforms["T_reference_lidar"] = make_unknown_transform(
            lidar_frame, reference_frame, note="no on-site installation measurement")
    if "R_lidar_imu" not in rotations:
        rotations["R_lidar_imu"] = make_unknown_rotation(
            "imu", lidar_frame, note="no IMU mounting evidence")
    resolved_statuses = default_statuses()
    resolved_statuses.update(statuses or {})
    resolved_verification = default_verification()
    resolved_verification.update(verification or {})
    if ground is not None and ground.get("status") != "valid":
        resolved_statuses["ground"] = "unknown"
    artifact = {
        "kind": KIND,
        "schema_version": SCHEMA_VERSION,
        "calibration_id": calibration_id,
        "created_at_utc": created_at_utc,
        "units": dict(UNITS),
        "frames": {"lidar": lidar_frame, "reference": reference_frame},
        "transforms": transforms,
        "rotations": rotations,
        "ground": ground,
        "sensor_height_m": sensor_height_from_ground(ground) if ground else None,
        "status": resolved_statuses,
        "verification": resolved_verification,
        "input": input_info or {},
        "note": note,
    }
    if ground_derived is not None:
        artifact[GROUND_DERIVED_KEY] = ground_derived
    return validate_geometry_calibration(artifact)

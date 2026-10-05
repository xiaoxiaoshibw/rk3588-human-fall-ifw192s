"""Robust ground-plane fitting and validation in the sensor frame (HF-03).

The fit is deliberately bounded (iteration cap + point cap + fixed seed) and
reports its residual and valid region instead of only a sample error. Failure
modes are explicit:

- too few points -> ``ground_points_insufficient``;
- no dominant plane -> ``ground_not_found``;
- a dominant vertical surface (wall) whose normal is not plausibly "up" ->
  ``ground_orientation_ambiguous`` (horizontal/vertical plane confusion), kept
  as ``orientation_unverified`` rather than reported as ground;
- a dominant plane at or above the origin -> ``ground_above_sensor``;
- a held-out split that is missing, too small, or has too little ground
  support -> ``ground_holdout_insufficient`` / ``ground_holdout_failed``. The
  gate separates two quantities: all-holdout statistics (which include
  legitimate off-plane scene objects such as furniture or a standing person)
  and the independent held-out *ground support* points. Decisive checks are a
  sufficient number of on-ground support points, a support rate coordinated
  with the fit's minimum support gate, and a small on-ground residual. So a
  dominant floor in an ordinary room still passes while a disjoint hold-out
  surface (no ground support) fails. Statistics alone are never a pass.

A plane is ``n . p + d = 0`` with ``n`` a unit normal. The reported normal is
oriented toward the sensor (``n_z >= 0``) and the plane sits below the origin:
the sensor height is the origin's signed distance ``d > 0``. The numerically
heavy step is a thin (``full_matrices=False``) SVD of the inlier covariance, so
memory stays O(N), not O(N^2). A single static-scene fit is a candidate
geometry, never a claim that the world installation pose was verified.
"""

import math
from collections import deque

import numpy as np

try:  # pragma: no cover - import shim
    from core.numeric import strict_numeric_array
except ImportError:  # pragma: no cover
    from numeric import strict_numeric_array

DEFAULT_SETTINGS = {
    "max_points": 100000,
    "max_fit_points": 50000,
    "range_min_m": 1.0,
    "range_max_m": 30.0,
    "ransac_iterations": 150,
    "inlier_threshold_m": 0.05,
    "min_inliers": 100,
    "min_inlier_fraction": 0.2,
    "normal_up_min_z": 0.5,
    "holdout_fraction": 0.3,
    "min_holdout_points": 20,
    "max_holdout_rms_m": 0.12,
    "min_holdout_support": 0.5,
    "seed": 20261001,
}

STATUS_VALID = "valid"
STATUS_ORIENTATION_UNVERIFIED = "orientation_unverified"
STATUS_INVALID = "invalid"
STATUSES = (STATUS_VALID, STATUS_ORIENTATION_UNVERIFIED, STATUS_INVALID)

REASON_INSUFFICIENT = "ground_points_insufficient"
REASON_NOT_FOUND = "ground_not_found"
REASON_ORIENTATION = "ground_orientation_ambiguous"
REASON_ABOVE_SENSOR = "ground_above_sensor"
REASON_HOLDOUT_INSUFFICIENT = "ground_holdout_insufficient"
REASON_HOLDOUT_FAILED = "ground_holdout_failed"

_REGION_BOUNDS = ("x_min_m", "x_max_m", "y_min_m", "y_max_m", "z_min_m",
                  "z_max_m", "range_min_m", "range_max_m")


def resolve_settings(settings=None):
    """Merge overrides onto the defaults and validate the numeric bounds."""
    resolved = dict(DEFAULT_SETTINGS)
    for key, value in (settings or {}).items():
        if key not in resolved:
            raise ValueError("unknown ground setting: " + str(key))
        resolved[key] = value
    for key in ("max_points", "max_fit_points", "ransac_iterations",
                "min_inliers", "min_holdout_points"):
        resolved[key] = int(resolved[key])
        if resolved[key] <= 0:
            raise ValueError(key + " must be a positive integer")
    for key in ("range_min_m", "range_max_m", "inlier_threshold_m",
                "min_inlier_fraction", "normal_up_min_z", "holdout_fraction",
                "max_holdout_rms_m", "min_holdout_support"):
        resolved[key] = float(resolved[key])
        if not np.isfinite(resolved[key]):
            raise ValueError(key + " must be finite")
    if resolved["range_max_m"] <= resolved["range_min_m"]:
        raise ValueError("range_max_m must be greater than range_min_m")
    if resolved["inlier_threshold_m"] <= 0.0:
        raise ValueError("inlier_threshold_m must be positive")
    if not 0.0 <= resolved["holdout_fraction"] < 1.0:
        raise ValueError("holdout_fraction must be in [0, 1)")
    if not 0.0 <= resolved["normal_up_min_z"] <= 1.0:
        raise ValueError("normal_up_min_z must be between 0 and 1")
    if resolved["max_holdout_rms_m"] <= 0.0:
        raise ValueError("max_holdout_rms_m must be positive")
    if not 0.0 <= resolved["min_holdout_support"] <= 1.0:
        raise ValueError("min_holdout_support must be in [0, 1]")
    return resolved


def _region(points):
    if len(points) == 0:
        return None
    return {"x_min_m": float(points[:, 0].min()), "x_max_m": float(points[:, 0].max()),
            "y_min_m": float(points[:, 1].min()), "y_max_m": float(points[:, 1].max()),
            "z_min_m": float(points[:, 2].min()), "z_max_m": float(points[:, 2].max()),
            "range_min_m": float(np.linalg.norm(points, axis=1).min()),
            "range_max_m": float(np.linalg.norm(points, axis=1).max()),
            "point_count": int(len(points))}


def _residual(plane_normal, offset, points):
    if len(points) == 0:
        return None
    distances = np.abs(points @ plane_normal + offset)
    return {"count": int(len(points)), "rms_m": float(np.sqrt(np.mean(distances ** 2))),
            "max_m": float(distances.max())}


def _support_stats(plane_normal, offset, points, threshold):
    """Ground-support statistics for a point set (unit: metres).

    ``near_ground`` are the points within ``threshold`` of the plane; the
    reported ``rms_m``/``max_m`` are their on-plane residuals. ``fraction`` is
    the near-ground support rate over all supplied points. Non-ground scene
    points (furniture, a standing person) are legitimate off-plane samples and
    are counted in ``fraction`` as non-support, never mistaken for plane error.
    """
    distances = np.abs(points @ plane_normal + offset)
    near = distances <= threshold
    count = int(np.count_nonzero(near))
    if count:
        rms = float(np.sqrt(np.mean(distances[near] ** 2)))
        maximum = float(distances[near].max())
    else:
        rms = maximum = None
    return {"count": count, "rms_m": rms, "max_m": maximum,
            "fraction": float(count / len(points)) if len(points) else None}


def _result(status, reason, settings, point_count, frame, normal=None,
            offset=None, fit_inliers=None, holdout_residual=None,
            inlier_fraction=None, tilt_rad=None):
    valid = status == STATUS_VALID
    height = None
    if normal is not None and offset is not None:
        height = float(offset)
        if height <= 0.0:
            valid = False
            if status == STATUS_VALID:
                status, reason = STATUS_INVALID, REASON_ABOVE_SENSOR
    return {"kind": "ground_plane", "status": status, "valid": valid,
            "reason": reason, "frame": frame, "point_count": int(point_count),
            "normal": None if normal is None else [float(v) for v in normal],
            "offset_m": None if offset is None else float(offset),
            "sensor_height_m": height, "tilt_rad": tilt_rad,
            "fit_inlier_count": None if fit_inliers is None else int(fit_inliers),
            "inlier_fraction": inlier_fraction,
            "holdout_residual": holdout_residual,
            "holdout_support": None,
            "valid_region": None,
            "settings": settings}


def _finish(result, inlier_points, fit_residual_rms, fit_residual_max):
    result["valid_region"] = _region(inlier_points)
    if result["fit_inlier_count"] is not None:
        result["fit_residual"] = {"count": result["fit_inlier_count"],
                                  "rms_m": float(fit_residual_rms),
                                  "max_m": float(fit_residual_max)}
    return result


def _holdout_gate(resolved, normal, offset, holdout, fit_support_threshold):
    """Return (ok, reason, residual, support).

    Validation needs independent held-out ground evidence. ``residual`` keeps
    the all-holdout-point statistics (including legitimate off-plane scene
    objects) for inspection, while ``support`` is the decisive measure: a
    sufficient number of held-out points must lie on the ground with a good
    support rate (coordinated with the fit's minimum support gate) and a small
    on-ground residual. A disjoint hold-out surface gives no ground support and
    still fails; furniture/person points only lower the support rate, they are
    not treated as plane-fit error.
    """
    residual = _residual(normal, offset, holdout)
    support = _support_stats(normal, offset, holdout, resolved["inlier_threshold_m"])
    if len(holdout) < resolved["min_holdout_points"]:
        return False, REASON_HOLDOUT_INSUFFICIENT, residual, support
    support_fraction = max(resolved["min_holdout_support"], fit_support_threshold)
    enough_support = support["count"] >= resolved["min_holdout_points"]
    good_rate = support["fraction"] is not None and support["fraction"] >= support_fraction
    good_points = support["rms_m"] is not None and support["rms_m"] <= resolved["max_holdout_rms_m"]
    if not (enough_support and good_rate and good_points):
        return False, REASON_HOLDOUT_FAILED, residual, support
    return True, None, residual, support


def fit_ground_plane(points, settings=None, frame=None):
    """Fit and validate a ground plane from an (N,3) sensor-frame point array."""
    resolved = resolve_settings(settings)
    array = np.asarray(points, dtype=np.float64)
    if array.ndim != 2 or array.shape[1] != 3:
        raise ValueError("points must be an (N,3) array")
    array = array[np.all(np.isfinite(array), axis=1)]
    if len(array):
        ranges = np.linalg.norm(array, axis=1)
        array = array[(ranges >= resolved["range_min_m"])
                      & (ranges <= resolved["range_max_m"])]
    empty = _result(STATUS_INVALID, REASON_INSUFFICIENT, resolved, len(array), frame)

    if len(array) < max(3, resolved["min_inliers"]):
        return empty
    if len(array) > resolved["max_points"]:
        stride = int(np.ceil(len(array) / resolved["max_points"]))
        array = array[::stride]

    rng = np.random.RandomState(int(resolved["seed"]) % (2 ** 32))
    order = rng.permutation(len(array))
    holdout_count = int(len(array) * resolved["holdout_fraction"])
    holdout = array[order[:holdout_count]] if holdout_count else array[:0]
    fit = array[order[holdout_count:]]
    if len(fit) > resolved["max_fit_points"]:
        fit = fit[::int(np.ceil(len(fit) / resolved["max_fit_points"]))]

    threshold = resolved["inlier_threshold_m"]
    best_count, best_normal, best_offset = -1, None, None
    for _ in range(int(resolved["ransac_iterations"])):
        sample = fit[rng.randint(0, len(fit), 3)]
        normal = np.cross(sample[1] - sample[0], sample[2] - sample[0])
        norm = float(np.linalg.norm(normal))
        if norm < 1e-9:
            continue
        normal = normal / norm
        offset = -float(normal @ sample[0])
        count = int(np.count_nonzero(np.abs(fit @ normal + offset) <= threshold))
        if count > best_count:
            best_count, best_normal, best_offset = count, normal, offset

    if best_normal is None or best_count < resolved["min_inliers"] \
            or best_count < resolved["min_inlier_fraction"] * len(fit):
        return empty

    inliers = fit[np.abs(fit @ best_normal + best_offset) <= threshold]
    centroid = inliers.mean(axis=0)
    # Thin SVD of the (N,3) centred inliers: U is Nx3, so memory stays O(N).
    _, _, vt = np.linalg.svd(inliers - centroid, full_matrices=False)
    normal = vt[-1]
    offset = -float(normal @ centroid)
    if normal[2] < 0.0:
        normal = -normal
        offset = -offset
    tilt = float(np.arccos(np.clip(normal[2], -1.0, 1.0)))

    inlier_distances = np.abs(inliers @ normal + offset)
    inlier_fraction = float(len(inliers) / len(fit))
    fit_rms = float(np.sqrt(np.mean(inlier_distances ** 2)))
    fit_max = float(inlier_distances.max())

    if tilt > np.arccos(resolved["normal_up_min_z"]):
        result = _result(STATUS_ORIENTATION_UNVERIFIED, REASON_ORIENTATION,
                         resolved, len(array), frame, normal, offset,
                         len(inliers), _residual(normal, offset, holdout),
                         inlier_fraction, tilt)
        result["holdout_support"] = _support_stats(normal, offset, holdout,
                                                   threshold)
        return _finish(result, inliers, fit_rms, fit_max)

    ok, reason, residual, support = _holdout_gate(
        resolved, normal, offset, holdout, resolved["min_inlier_fraction"])
    status = STATUS_VALID if ok else STATUS_INVALID
    result = _result(status, reason, resolved, len(array), frame, normal, offset,
                     len(inliers), residual, inlier_fraction, tilt)
    result["holdout_support"] = support
    return _finish(result, inliers, fit_rms, fit_max)


def ground_is_valid(result):
    return bool(isinstance(result, dict) and result.get("status") == STATUS_VALID)


# ---------------------------------------------------------------------------
# GL-01 constrained ground path.
#
# Explicitly enabled and fully separate from ``fit_ground_plane``: the legacy
# defaults, result fields and behaviour above are untouched. The constrained
# path adds an explicit up-axis prior, a sensor-height prior, spatial balanced
# sampling, multiple deduplicated candidates, SVD refinement with an explicit
# degeneracy test and a per-region untruncated validation gate. Everything is a
# software candidate; no physical flag is ever raised here.
# ---------------------------------------------------------------------------

CONSTRAINED_DEFAULT_SETTINGS = {
    "min_inliers": 100,
    "min_fit_inlier_fraction": 0.2,
    "fit_point_cap": 5000,
    "holdout_point_cap": 10000,
    "spatial_cell_m": 0.20,
    "max_points_per_cell": 4,
    "max_candidates": 3,
    "ransac_iterations": 861,
    "ransac_iteration_hard_cap": 2000,
    "seed": 20261001,
    "inlier_threshold_m": 0.05,
    "max_angle_rad": 0.2617993877991494,
    "min_sample_separation_m": 0.05,
    "min_sample_triangle_area_m2": 0.0025,
    "min_planar_eigenvalue_ratio": 0.02,
    "support_close_ratio": 0.8,
    "distinct_normal_deg": 10.0,
    "distinct_offset_m": 0.05,
    "independent_regions_min": 3,
    "points_per_region_min": 20,
    "untruncated_rms_max_m": 0.03,
    "abs_residual_p95_max_m": 0.05,
    "support_fraction_min": 0.8,
    "normal_change_max_deg": 2.0,
    "offset_change_max_m": 0.03,
}

REASON_OVERLAP = "ground_fit_validation_overlap"
REASON_GROUP_LEAKAGE = "ground_frame_group_leakage"
REASON_DEGENERATE = "ground_degenerate"
REASON_VALIDATION_INSUFFICIENT = "ground_validation_insufficient"
REASON_VALIDATION_FAILED = "ground_validation_failed"
REASON_METADATA = "ground_validation_metadata_invalid"
REASON_COMPETITION = "ground_competition_unresolved"

# Approved protocol floors/caps: lowering them is not a way to pass.
_MIN_INLIERS_FLOOR = 100
_POINTS_PER_REGION_FLOOR = 20
_INDEPENDENT_REGIONS_FLOOR = 3
_MAX_CANDIDATES_CEIL = 3
_HARD_CAP_CEIL = 2000
# Bounded competition evidence kept regardless of the output candidate cap, so
# that reducing ``max_candidates`` cannot hide a close competing plane.
_COMPETITION_CANDIDATE_CAP = 8

_CONSTRAINED_INT_KEYS = (
    "min_inliers", "fit_point_cap", "holdout_point_cap", "max_points_per_cell",
    "max_candidates", "ransac_iterations", "ransac_iteration_hard_cap",
    "independent_regions_min", "points_per_region_min",
)
_CONSTRAINED_POSITIVE_KEYS = (
    "inlier_threshold_m", "spatial_cell_m", "max_angle_rad",
    "min_sample_separation_m", "min_sample_triangle_area_m2",
    "distinct_normal_deg", "distinct_offset_m", "untruncated_rms_max_m",
    "abs_residual_p95_max_m", "normal_change_max_deg", "offset_change_max_m",
)
_CONSTRAINED_RATIO_KEYS = (
    "min_fit_inlier_fraction", "support_close_ratio", "support_fraction_min",
    "min_planar_eigenvalue_ratio",
)
_REGION_BOUND_KEYS = ("x_min_m", "x_max_m", "y_min_m", "y_max_m",
                      "z_min_m", "z_max_m")


def _finite_number(value, name):
    if isinstance(value, bool) or not isinstance(
            value, (int, float, np.integer, np.floating)):
        raise ValueError(name + " must be a finite number")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(name + " must be finite")
    return number


def _integer_value(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, np.integer)):
        raise ValueError(name + " must be an integer")
    return int(value)


def resolve_constrained_settings(settings=None):
    """Validate GL-01 parameters strictly (no bool/NaN/Inf/negative coercion).

    Floors and caps come from the approved protocol and cannot be relaxed by a
    caller (``min_inliers`` 100, per-region 20, >=3 regions, ``max_candidates``
    <=3, iteration hard cap <=2000, eigenvalue ratio in (0,1]). A budget larger
    than the hard cap is rejected rather than silently truncated.
    """
    resolved = dict(CONSTRAINED_DEFAULT_SETTINGS)
    for key, value in (settings or {}).items():
        if key not in resolved:
            raise ValueError("unknown constrained ground setting: " + str(key))
        resolved[key] = value
    resolved["seed"] = _integer_value(resolved["seed"], "seed")
    if resolved["seed"] < 0:
        raise ValueError("seed must be a non-negative integer")
    for key in _CONSTRAINED_INT_KEYS:
        value = _integer_value(resolved[key], key)
        if value <= 0:
            raise ValueError(key + " must be a positive integer")
        resolved[key] = value
    for key in _CONSTRAINED_POSITIVE_KEYS:
        value = _finite_number(resolved[key], key)
        if value <= 0.0:
            raise ValueError(key + " must be a positive number")
        resolved[key] = value
    for key in _CONSTRAINED_RATIO_KEYS:
        value = _finite_number(resolved[key], key)
        if not 0.0 < value <= 1.0:
            raise ValueError(key + " must be in (0, 1]")
        resolved[key] = value
    if resolved["max_angle_rad"] >= math.pi / 2.0:
        raise ValueError("max_angle_rad must be less than pi/2")
    if resolved["min_inliers"] < _MIN_INLIERS_FLOOR:
        raise ValueError("min_inliers must be >= %d" % _MIN_INLIERS_FLOOR)
    if resolved["points_per_region_min"] < _POINTS_PER_REGION_FLOOR:
        raise ValueError("points_per_region_min must be >= %d"
                         % _POINTS_PER_REGION_FLOOR)
    if resolved["independent_regions_min"] < _INDEPENDENT_REGIONS_FLOOR:
        raise ValueError("independent_regions_min must be >= %d"
                         % _INDEPENDENT_REGIONS_FLOOR)
    if resolved["max_candidates"] > _MAX_CANDIDATES_CEIL:
        raise ValueError("max_candidates must be <= %d" % _MAX_CANDIDATES_CEIL)
    if resolved["ransac_iteration_hard_cap"] > _HARD_CAP_CEIL:
        raise ValueError("ransac_iteration_hard_cap must be <= %d" % _HARD_CAP_CEIL)
    if resolved["ransac_iterations"] > resolved["ransac_iteration_hard_cap"]:
        raise ValueError("ransac_iterations exceeds ransac_iteration_hard_cap")
    if resolved["fit_point_cap"] < resolved["min_inliers"]:
        raise ValueError("fit_point_cap must be >= min_inliers")
    return resolved


def _strict_float_sequence(values, length, name):
    """Materialise ``values`` into ``length`` finite floats, rejecting bool and
    non-numeric entries element by element (mixed bool/str must not pass)."""
    if values is None:
        raise ValueError(name + " is required")
    if isinstance(values, np.ndarray):
        if values.dtype.kind == "b" or values.dtype.kind not in "fiub":
            raise ValueError(name + " must be finite numbers")
        items = values.tolist()
    elif isinstance(values, (list, tuple)):
        items = list(values)
    else:
        raise ValueError(name + " must be a sequence of finite numbers")
    if len(items) != length:
        raise ValueError("%s must have %d entries" % (name, length))
    numbers = []
    for item in items:
        if isinstance(item, bool) or not isinstance(
                item, (int, float, np.integer, np.floating)):
            raise ValueError(name + " must contain finite numbers only")
        number = float(item)
        if not math.isfinite(number):
            raise ValueError(name + " must contain finite numbers only")
        numbers.append(number)
    return np.asarray(numbers, dtype=np.float64)


def _unit_vector(values, name, tolerance=1e-3):
    array = _strict_float_sequence(values, 3, name)
    norm = float(np.linalg.norm(array))
    if norm <= 0.0:
        raise ValueError(name + " must be a non-zero vector")
    if abs(norm - 1.0) > float(tolerance):
        raise ValueError(name + " must be a unit vector (norm %.6f)" % norm)
    return array / norm


def _height_interval(values):
    array = _strict_float_sequence(values, 2, "sensor_height_interval_m")
    low, high = float(array[0]), float(array[1])
    if low < 0.0:
        raise ValueError("sensor_height_interval_m must be non-negative")
    if not low < high:
        raise ValueError("sensor_height_interval_m low must be below high")
    return low, high


def _normalise_indices(values, name, limit):
    """Return a 1-D int64 index array, rejecting bool/mixed/float entries.

    Bool is rejected element by element *before* any NumPy cast, so a mixed
    ``[True, 0, 1]`` list cannot be silently promoted to integers.
    """
    if isinstance(values, np.ndarray):
        if values.dtype.kind == "b" or values.dtype.kind not in "iu":
            raise ValueError(name + " must be integer indices")
        items = values.tolist()
    elif isinstance(values, (list, tuple)):
        items = list(values)
    else:
        raise ValueError(name + " must be a 1-D integer index sequence")
    for item in items:
        if isinstance(item, bool) or not isinstance(item, (int, np.integer)):
            raise ValueError(name + " must be integer indices")
    indices = np.asarray(items, dtype=np.int64)
    if indices.ndim != 1:
        raise ValueError(name + " must be a 1-D index array")
    if len(indices) and (int(indices.min()) < 0 or int(indices.max()) >= int(limit)):
        raise ValueError(name + " contains an out-of-range index")
    return indices


def region_indices(points, region):
    """Source indices selected by an explicit GL-01 region.

    A region is either ``{"region_id": ..., "indices": [...]}`` or carries the
    six ``x/y/z_min_m`` / ``x/y/z_max_m`` bounds. It never guesses a region.
    """
    array = np.asarray(points, dtype=np.float64)
    if array.ndim != 2 or array.shape[1] != 3:
        raise ValueError("points must be an (N,3) array")
    if not isinstance(region, dict):
        raise ValueError("region must be an object")
    if "indices" in region:
        return np.unique(_normalise_indices(region["indices"],
                                            "region.indices", len(array)))
    present = [key for key in _REGION_BOUND_KEYS if key in region]
    if not present:
        raise ValueError("region needs indices or x/y/z bounds")
    if len(present) != len(_REGION_BOUND_KEYS):
        raise ValueError("region bounds are incomplete")
    mask = np.ones(len(array), dtype=bool)
    for axis, key in enumerate(("x", "y", "z")):
        low = _finite_number(region[key + "_min_m"], key + "_min_m")
        high = _finite_number(region[key + "_max_m"], key + "_max_m")
        if low > high:
            raise ValueError("region " + key + " bounds are inverted")
        mask &= (array[:, axis] >= low) & (array[:, axis] <= high)
    return np.nonzero(mask)[0]


def _tangent_basis(up):
    reference = np.array([1.0, 0.0, 0.0])
    if abs(float(up @ reference)) > 0.9:
        reference = np.array([0.0, 1.0, 0.0])
    first = np.cross(up, reference)
    first = first / np.linalg.norm(first)
    return first, np.cross(up, first)


def _balanced_sample(array, indices, up, tangent_u, tangent_v, cell, per_cell,
                     cap, rng):
    """Keep at most ``per_cell`` points per ground-tangent cell.

    Only the fit sample is thinned; the returned entries are original source
    indices, so support can be re-checked on the untouched cloud.
    """
    points = array[indices]
    cell_x = np.floor((points @ tangent_u) / cell).astype(np.int64)
    cell_y = np.floor((points @ tangent_v) / cell).astype(np.int64)
    perm = rng.permutation(len(indices))
    shuffled = indices[perm]
    cell_x = cell_x[perm]
    cell_y = cell_y[perm]
    order = np.lexsort((np.arange(len(shuffled)), cell_y, cell_x))
    shuffled = shuffled[order]
    cell_x = cell_x[order]
    cell_y = cell_y[order]
    new_cell = np.ones(len(shuffled), dtype=bool)
    if len(shuffled) > 1:
        new_cell[1:] = (cell_x[1:] != cell_x[:-1]) | (cell_y[1:] != cell_y[:-1])
    row = np.arange(len(shuffled))
    first = np.maximum.accumulate(np.where(new_cell, row, 0))
    sampled = shuffled[(row - first) < per_cell]
    if len(sampled) > cap:
        sampled = sampled[::int(np.ceil(len(sampled) / cap))]
    return sampled


def _candidate_summary(candidate):
    return {"normal": [float(v) for v in candidate["normal"]],
            "offset_m": float(candidate["offset_m"]),
            "support_count": int(candidate["support_count"])}


def _attach(result, diagnostics):
    for key, value in diagnostics.items():
        result[key] = value
    return result


def _constrained_failure(status, reason, resolved, frame, diagnostics,
                         normal=None, offset=None, fit_inliers=None,
                         inlier_fraction=None, tilt=None):
    result = _result(status, reason, resolved, diagnostics["input_point_count"],
                     frame, normal, offset, fit_inliers, None, inlier_fraction,
                     tilt)
    return _attach(result, diagnostics)


def _angle_deg(first, second):
    value = float(np.clip(float(np.asarray(first) @ np.asarray(second)), -1.0, 1.0))
    return math.degrees(math.acos(value))


def fit_ground_plane_constrained(points, settings=None, frame=None, up_axis=None,
                                 sensor_height_interval_m=None, fit_indices=None,
                                 fit_frame_group=None, validation_regions=None):
    """GL-01 constrained ground fit; opt-in and separate from the legacy path.

    Requires an explicit ``up_axis`` prior and a fixture-supplied
    ``sensor_height_interval_m``; validation regions and fit points are given as
    explicit source indices (or x/y/z bounds) and must be disjoint. Returns a
    candidate geometry with diagnostics, never a physical claim.
    """
    resolved = resolve_constrained_settings(settings)
    up = _unit_vector(up_axis, "up_axis")
    height_low, height_high = _height_interval(sensor_height_interval_m)
    array = np.asarray(points, dtype=np.float64)
    if array.ndim != 2 or array.shape[1] != 3:
        raise ValueError("points must be an (N,3) array")

    finite = np.all(np.isfinite(array), axis=1)
    norms = np.zeros(len(array))
    norms[finite] = np.linalg.norm(array[finite], axis=1)
    valid_index = np.nonzero(finite & (norms > 0.0))[0]

    if fit_indices is None:
        fit_index = valid_index
    else:
        fit_index = np.intersect1d(
            _normalise_indices(fit_indices, "fit_indices", len(array)),
            valid_index)

    regions = []
    for region in (validation_regions or []):
        if not isinstance(region, dict):
            raise ValueError("each validation region must be an object")
        region_id = region.get("region_id")
        if not isinstance(region_id, str) or not region_id:
            raise ValueError("each validation region needs a non-empty region_id")
        selected = np.intersect1d(region_indices(array, region), valid_index)
        regions.append((region, selected))

    diagnostics = {
        "constrained": True,
        "up_axis": [float(v) for v in up],
        "sensor_height_interval_m": [height_low, height_high],
        "fit_frame_group": fit_frame_group,
        "input_point_count": int(len(array)),
        "valid_point_count": int(len(valid_index)),
        "fit_index_count": int(len(fit_index)),
        "seed": int(resolved["seed"]),
        "iterations": int(min(resolved["ransac_iterations"],
                              resolved["ransac_iteration_hard_cap"])),
        "iterations_cap": int(min(resolved["ransac_iterations"],
                                  resolved["ransac_iteration_hard_cap"])),
        "sampled_fit_count": 0,
        "degenerate_samples": 0,
        "ambiguous": False,
        "raw_candidates": [],
        "candidates": [],
        "validation_regions": [],
        "fit_support_indices": [],
    }

    if not regions:
        return _constrained_failure(STATUS_INVALID, REASON_VALIDATION_INSUFFICIENT,
                                    resolved, frame, diagnostics)
    if not isinstance(fit_frame_group, str) or not fit_frame_group:
        return _constrained_failure(STATUS_INVALID, REASON_METADATA, resolved,
                                    frame, diagnostics)
    seen_ids = set()
    seen_groups = set()
    for region, _ in regions:
        group = region.get("frame_group")
        if not isinstance(group, str) or not group:
            return _constrained_failure(STATUS_INVALID, REASON_METADATA, resolved,
                                        frame, diagnostics)
        if region["region_id"] in seen_ids or group in seen_groups:
            return _constrained_failure(STATUS_INVALID, REASON_METADATA, resolved,
                                        frame, diagnostics)
        seen_ids.add(region["region_id"])
        seen_groups.add(group)

    for region, selected in regions:
        if np.intersect1d(fit_index, selected).size:
            return _constrained_failure(STATUS_INVALID, REASON_OVERLAP, resolved,
                                        frame, diagnostics)
    if fit_frame_group is not None:
        for region, _ in regions:
            if region.get("frame_group") == fit_frame_group:
                return _constrained_failure(STATUS_INVALID, REASON_GROUP_LEAKAGE,
                                            resolved, frame, diagnostics)
    for first in range(len(regions)):
        for second in range(first + 1, len(regions)):
            if np.intersect1d(regions[first][1], regions[second][1]).size:
                return _constrained_failure(STATUS_INVALID, REASON_OVERLAP,
                                            resolved, frame, diagnostics)
            group_first = regions[first][0].get("frame_group")
            group_second = regions[second][0].get("frame_group")
            if group_first is not None and group_first == group_second:
                return _constrained_failure(STATUS_INVALID, REASON_GROUP_LEAKAGE,
                                            resolved, frame, diagnostics)

    if len(fit_index) < max(3, resolved["min_inliers"]):
        return _constrained_failure(STATUS_INVALID, REASON_INSUFFICIENT, resolved,
                                    frame, diagnostics)

    rng = np.random.RandomState(int(resolved["seed"]) % (2 ** 32))
    tangent_u, tangent_v = _tangent_basis(up)
    sampled = _balanced_sample(array, fit_index, up, tangent_u, tangent_v,
                               resolved["spatial_cell_m"],
                               resolved["max_points_per_cell"],
                               resolved["fit_point_cap"], rng)
    diagnostics["sampled_fit_count"] = int(len(sampled))
    if len(sampled) < max(3, resolved["min_inliers"]):
        return _constrained_failure(STATUS_INVALID, REASON_INSUFFICIENT, resolved,
                                    frame, diagnostics)

    fit_points = array[sampled]
    threshold = resolved["inlier_threshold_m"]
    max_angle = resolved["max_angle_rad"]
    min_inliers = resolved["min_inliers"]
    min_fraction = resolved["min_fit_inlier_fraction"]
    distinct_normal = math.radians(resolved["distinct_normal_deg"])
    distinct_offset = resolved["distinct_offset_m"]
    n_fit = len(fit_points)

    candidates = []
    degenerate = 0
    evaluated = 0
    competition_truncated = False
    for _ in range(diagnostics["iterations"]):
        draw = rng.choice(n_fit, size=3, replace=False)
        p0, p1, p2 = fit_points[draw]
        if min(float(np.linalg.norm(p1 - p0)), float(np.linalg.norm(p2 - p0)),
               float(np.linalg.norm(p2 - p1))) < resolved["min_sample_separation_m"]:
            degenerate += 1
            continue
        cross = np.cross(p1 - p0, p2 - p0)
        length = float(np.linalg.norm(cross))
        if length <= 0.0 or length / 2.0 < resolved["min_sample_triangle_area_m2"]:
            degenerate += 1
            continue
        normal = cross / length
        if float(normal @ up) < 0.0:
            normal = -normal
        if math.acos(max(-1.0, min(1.0, float(normal @ up)))) > max_angle:
            continue
        offset = -float(normal @ p0)
        if not height_low <= offset <= height_high:
            continue
        evaluated += 1
        count = int(np.count_nonzero(
            np.abs(fit_points @ normal + offset) <= threshold))
        if count < min_inliers or count < min_fraction * n_fit:
            continue
        for candidate in candidates:
            if _angle_deg(candidate["normal"], normal) <= resolved["distinct_normal_deg"] \
                    and abs(candidate["offset_m"] - offset) <= distinct_offset:
                if count > candidate["support_count"]:
                    candidate.update({"normal": normal, "offset_m": offset,
                                      "support_count": count})
                break
        else:
            candidates.append({"normal": normal, "offset_m": offset,
                               "support_count": count})
        if len(candidates) > _COMPETITION_CANDIDATE_CAP:
            candidates.sort(key=lambda item: item["support_count"], reverse=True)
            del candidates[_COMPETITION_CANDIDATE_CAP:]
            competition_truncated = True
    diagnostics["degenerate_samples"] = degenerate
    diagnostics["raw_candidates"] = [_candidate_summary(item) for item in candidates]

    refined = []
    rejected_degenerate = 0
    for candidate in candidates:
        inlier_mask = np.abs(fit_points @ candidate["normal"]
                             + candidate["offset_m"]) <= threshold
        inlier_points = fit_points[inlier_mask]
        if len(inlier_points) < max(min_inliers, int(math.ceil(min_fraction * n_fit))):
            continue
        centroid = inlier_points.mean(axis=0)
        covariance = (inlier_points - centroid).T @ (inlier_points - centroid)
        eigenvalues, eigenvectors = np.linalg.eigh(covariance)
        largest = float(eigenvalues[2])
        ratio = float(eigenvalues[1]) / largest if largest > 0.0 else 0.0
        normal = eigenvectors[:, 0]
        if float(normal @ up) < 0.0:
            normal = -normal
        if ratio < resolved["min_planar_eigenvalue_ratio"]:
            rejected_degenerate += 1
            continue
        if math.acos(max(-1.0, min(1.0, float(normal @ up)))) > max_angle:
            continue
        offset = -float(normal @ centroid)
        if not height_low <= offset <= height_high:
            continue
        support_mask = np.abs(array[fit_index] @ normal + offset) <= threshold
        support_count = int(np.count_nonzero(support_mask))
        if support_count < max(min_inliers,
                               int(math.ceil(min_fraction * len(fit_index)))):
            continue
        refined.append({"normal": normal, "offset_m": offset,
                        "support_count": support_count,
                        "fit_support_mask": support_mask,
                        "eigenvalue_ratio": ratio})
    refined.sort(key=lambda item: item["support_count"], reverse=True)

    deduped = []
    for item in refined:
        if any(_angle_deg(item["normal"], other["normal"])
               <= resolved["distinct_normal_deg"]
               and abs(item["offset_m"] - other["offset_m"]) <= distinct_offset
               for other in deduped):
            continue
        deduped.append(item)
    competition = deduped[:_COMPETITION_CANDIDATE_CAP]
    if len(deduped) > _COMPETITION_CANDIDATE_CAP:
        competition_truncated = True
    refined = deduped[:resolved["max_candidates"]]
    diagnostics["candidates"] = [_candidate_summary(item) for item in refined]
    diagnostics["competition_candidates"] = [_candidate_summary(item)
                                             for item in competition]
    diagnostics["competition_truncated"] = competition_truncated

    if not refined:
        if candidates and rejected_degenerate == len(candidates):
            reason = REASON_DEGENERATE
        elif not candidates and evaluated == 0 and degenerate > 0:
            reason = REASON_DEGENERATE
        else:
            reason = REASON_NOT_FOUND
        return _constrained_failure(STATUS_INVALID, reason, resolved, frame,
                                    diagnostics)

    best = competition[0]
    tilt = math.acos(max(-1.0, min(1.0, float(best["normal"] @ up))))
    inlier_fraction = float(best["support_count"] / len(fit_index))
    if len(competition) >= 2:
        second = competition[1]
        angle = _angle_deg(best["normal"], second["normal"])
        offset_gap = abs(best["offset_m"] - second["offset_m"])
        close = second["support_count"] >= \
            resolved["support_close_ratio"] * best["support_count"]
        distinct = (angle > resolved["distinct_normal_deg"]
                    or offset_gap > resolved["distinct_offset_m"])
        if close and distinct:
            diagnostics["ambiguous"] = True
            diagnostics["ambiguity"] = {
                "normal_change_deg": angle, "offset_change_m": offset_gap,
                "best_support": int(best["support_count"]),
                "second_support": int(second["support_count"])}
            return _constrained_failure(STATUS_ORIENTATION_UNVERIFIED,
                                        REASON_ORIENTATION, resolved, frame,
                                        diagnostics, best["normal"],
                                        best["offset_m"], best["support_count"],
                                        inlier_fraction, tilt)
    if competition_truncated:
        return _constrained_failure(STATUS_ORIENTATION_UNVERIFIED,
                                    REASON_COMPETITION, resolved, frame,
                                    diagnostics, best["normal"], best["offset_m"],
                                    best["support_count"], inlier_fraction, tilt)

    region_count = max(1, len(regions))
    if resolved["holdout_point_cap"] // region_count < \
            resolved["points_per_region_min"]:
        return _constrained_failure(STATUS_INVALID, REASON_VALIDATION_INSUFFICIENT,
                                    resolved, frame, diagnostics)
    allowance = resolved["holdout_point_cap"] // region_count
    usable = []
    unusable = []
    aggregate = []
    for region, selected in regions:
        report = {"region_id": region["region_id"],
                  "frame_group": region.get("frame_group"),
                  "point_count": int(len(selected))}
        if len(selected) < resolved["points_per_region_min"]:
            report["usable"] = False
            report["reason"] = "points_below_min"
            diagnostics["validation_regions"].append(report)
            unusable.append(report)
            continue
        original_count = int(len(selected))
        chosen = selected if original_count <= allowance else \
            selected[::int(np.ceil(original_count / allowance))]
        region_points = array[chosen]
        residuals = np.abs(region_points @ best["normal"] + best["offset_m"])
        rms = float(np.sqrt(np.mean(residuals ** 2)))
        p95 = float(np.percentile(residuals, 95.0))
        fraction = float(np.count_nonzero(residuals <= threshold)
                         / len(residuals))
        passed = (rms <= resolved["untruncated_rms_max_m"]
                  and p95 <= resolved["abs_residual_p95_max_m"]
                  and fraction >= resolved["support_fraction_min"])
        report.update({"usable": True, "count": int(len(chosen)),
                       "original_count": original_count, "rms_m": rms,
                       "p95_m": p95, "support_fraction": fraction,
                       "passed": passed,
                       "indices": [int(v) for v in chosen]})
        diagnostics["validation_regions"].append(report)
        usable.append(report)
        aggregate.append(region_points)

    diagnostics["usable_region_count"] = len(usable)
    diagnostics["skipped_region_count"] = len(unusable)
    if unusable or len(usable) < resolved["independent_regions_min"]:
        return _constrained_failure(STATUS_INVALID,
                                    REASON_VALIDATION_INSUFFICIENT, resolved,
                                    frame, diagnostics)
    if not all(report["passed"] for report in usable):
        return _constrained_failure(STATUS_INVALID, REASON_VALIDATION_FAILED,
                                    resolved, frame, diagnostics)

    validation_points = np.vstack(aggregate)
    holdout_residual = _residual(best["normal"], best["offset_m"],
                                 validation_points)
    holdout_support = _support_stats(best["normal"], best["offset_m"],
                                     validation_points, threshold)
    support_points = array[fit_index[best["fit_support_mask"]]]
    support_distances = np.abs(support_points @ best["normal"]
                               + best["offset_m"])
    diagnostics["fit_support_indices"] = [int(v) for v in
                                          fit_index[best["fit_support_mask"]]]
    diagnostics["eigenvalue_ratio"] = float(best["eigenvalue_ratio"])
    result = _result(STATUS_VALID, None, resolved, int(len(array)), frame,
                     best["normal"], best["offset_m"], best["support_count"],
                     holdout_residual, inlier_fraction, tilt)
    result["holdout_support"] = holdout_support
    _finish(result, support_points,
            float(np.sqrt(np.mean(support_distances ** 2))),
            float(support_distances.max()))
    return _attach(result, diagnostics)


def _validated_indices(values, name, limit, require_unique):
    """Strict index set: reject bool/mixed/float, out-of-range and duplicates."""
    if not isinstance(values, list):
        raise ValueError(name + " must be a list")
    indices = _normalise_indices(values, name, limit)
    unique = set(int(v) for v in indices)
    if require_unique and len(unique) != len(indices):
        raise ValueError(name + " must not contain duplicate indices")
    return unique


def _region_number(report, key, name):
    value = report.get(key)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(
            value, (int, float, np.integer, np.floating)):
        raise ValueError(name + " " + key + " must be a finite number")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(name + " " + key + " must be finite")
    return number


def _validate_present_indices(values, name, limit):
    if values is None:
        return
    if not isinstance(values, list):
        raise ValueError(name + " must be a list")
    _normalise_indices(values, name, limit)


def _validate_region_diagnostics(reports, point_count, strict, resolved,
                                 fit_support, fit_group):
    """Validate persisted region diagnostics.

    When ``strict`` (a declared-valid record) every region must independently
    pass and its indices must be unique, in range and disjoint from the fit
    support and from every other region, and the total must respect the
    holdout cap. Otherwise present fields are still type/range checked, but a
    failing region is allowed (a legal failure record must remain saveable).
    """
    seen_ids, seen_groups, covered, total = set(), set(), set(), 0
    for report in reports:
        if not isinstance(report, dict):
            raise ValueError("each validation region must be an object")
        region_id = report.get("region_id")
        group = report.get("frame_group")
        if region_id is not None and (not isinstance(region_id, str)
                                      or not region_id):
            raise ValueError("validation region region_id must be a non-empty string")
        if group is not None and (not isinstance(group, str) or not group):
            raise ValueError("validation region frame_group must be a non-empty string")
        if "usable" in report and not isinstance(report["usable"], bool):
            raise ValueError("validation region usable must be a boolean")
        if "passed" in report and not isinstance(report["passed"], bool):
            raise ValueError("validation region passed must be a boolean")
        rms = _region_number(report, "rms_m", "validation region")
        p95 = _region_number(report, "p95_m", "validation region")
        fraction = _region_number(report, "support_fraction", "validation region")
        if rms is not None and rms < 0.0:
            raise ValueError("validation region rms_m must be non-negative")
        if p95 is not None and p95 < 0.0:
            raise ValueError("validation region p95_m must be non-negative")
        if fraction is not None and not 0.0 <= fraction <= 1.0:
            raise ValueError("validation region support_fraction must be in [0, 1]")
        if not strict:
            _validate_present_indices(report.get("indices"),
                                      "validation region indices", point_count)
            continue
        if not isinstance(region_id, str) or not region_id:
            raise ValueError("a valid validation region needs a region_id")
        if not isinstance(group, str) or not group:
            raise ValueError("a valid validation region needs a frame_group")
        if region_id in seen_ids or group in seen_groups or group == fit_group:
            raise ValueError("validation region ids/groups must be distinct")
        seen_ids.add(region_id)
        seen_groups.add(group)
        if report.get("usable") is not True or report.get("passed") is not True:
            raise ValueError("a valid constrained ground needs every region to pass")
        count = report.get("count")
        if not isinstance(count, int) or isinstance(count, bool) \
                or count < resolved["points_per_region_min"]:
            raise ValueError("a passing validation region needs enough points")
        index_set = _validated_indices(report.get("indices"),
                                       "validation region indices", point_count,
                                       require_unique=True)
        if len(index_set) != count:
            raise ValueError("validation region count does not match its indices")
        if index_set & fit_support or index_set & covered:
            raise ValueError("validation region indices overlap fit/other regions")
        covered |= index_set
        total += count
        if rms is None or rms > resolved["untruncated_rms_max_m"]:
            raise ValueError("validation region RMS exceeds the gate")
        if p95 is None or p95 > resolved["abs_residual_p95_max_m"]:
            raise ValueError("validation region p95 exceeds the gate")
        if fraction is None or fraction < resolved["support_fraction_min"]:
            raise ValueError("validation region support fraction is below the gate")
    if strict and total > resolved["holdout_point_cap"]:
        raise ValueError("validation regions exceed the holdout point cap")


def validate_constrained_ground(ground, expected_frame=None,
                                normal_tolerance=1e-3):
    """Strict structural validation of a persisted GL-01 constrained record.

    Builds on :func:`validate_ground_plane` (so a ``valid`` status still needs a
    unit normal, a region and held-out residual/support). A declared-valid
    record must additionally reproduce every physical/independence gate that
    produced it: a unit stored ``up_axis`` (never silently re-normalised), a
    normal within the declared angle, a height inside the interval, a fit
    support set of unique in-range integer source indices, a fitted group that
    is not a validation group, per-region RMS/p95/support within the settings,
    strictly typed non-negative statistics, disjoint in-range region indices and
    a held-out budget within the cap. Legal ``invalid``/``orientation_unverified``
    records stay saveable: their present fields are still type/range checked but
    they are not required to pass. It never promotes a candidate to verified.
    """
    validate_ground_plane(ground, expected_frame=expected_frame,
                          normal_tolerance=normal_tolerance)
    if ground.get("constrained") is not True:
        raise ValueError("ground record is not a GL-01 constrained fit")
    settings = ground.get("settings")
    if not isinstance(settings, dict):
        raise ValueError("constrained ground settings must be an object")
    resolved = resolve_constrained_settings(settings)
    up = _unit_vector(ground.get("up_axis"), "constrained ground up_axis")
    height_low, height_high = _height_interval(
        ground.get("sensor_height_interval_m"))
    point_count = ground.get("input_point_count")
    if not isinstance(point_count, int) or isinstance(point_count, bool) \
            or point_count < 0:
        raise ValueError("constrained ground input_point_count must be a "
                         "non-negative integer")
    for key in ("seed", "iterations", "iterations_cap", "sampled_fit_count",
                "degenerate_samples"):
        value = ground.get(key)
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise ValueError("constrained ground " + key + " must be a "
                             "non-negative integer")
    if ground["iterations"] < resolved["ransac_iterations"] \
            or ground["iterations"] > resolved["ransac_iteration_hard_cap"]:
        raise ValueError("constrained ground iterations are outside the budget")
    if ground["iterations_cap"] > resolved["ransac_iteration_hard_cap"]:
        raise ValueError("constrained ground iterations exceed the hard cap")
    if ground["sampled_fit_count"] > resolved["fit_point_cap"]:
        raise ValueError("constrained ground sampled fit exceeds the fit point cap")
    for key in ("candidates", "raw_candidates", "validation_regions",
                "fit_support_indices"):
        if not isinstance(ground.get(key), list):
            raise ValueError("constrained ground " + key + " must be a list")
    if len(ground["candidates"]) > resolved["max_candidates"]:
        raise ValueError("constrained ground has too many candidates")
    competition = ground.get("competition_candidates")
    if competition is not None and (not isinstance(competition, list)
                                    or len(competition) > _COMPETITION_CANDIDATE_CAP):
        raise ValueError("constrained ground competition evidence is malformed")
    fit_support = _validated_indices(ground["fit_support_indices"],
                                     "fit_support_indices", point_count,
                                     require_unique=True)
    if ground.get("status") != STATUS_VALID:
        _validate_region_diagnostics(ground["validation_regions"], point_count,
                                     False, resolved, fit_support, None)
        return ground
    if ground.get("ambiguous"):
        raise ValueError("a valid constrained ground must not be ambiguous")
    if ground.get("competition_truncated") is True:
        raise ValueError("constrained ground competition evidence was truncated")
    if not fit_support:
        raise ValueError("a valid constrained ground needs fit support indices")
    fit_group = ground.get("fit_frame_group")
    if not isinstance(fit_group, str) or not fit_group:
        raise ValueError("a valid constrained ground needs a fit_frame_group")
    normal = np.asarray(ground["normal"], dtype=np.float64)
    angle = math.degrees(math.acos(max(-1.0, min(1.0, float(normal @ up)))))
    if angle > math.degrees(resolved["max_angle_rad"]) + 1e-6:
        raise ValueError("constrained ground normal disagrees with up_axis")
    offset = float(ground["offset_m"])
    if not height_low - 1e-9 <= offset <= height_high + 1e-9:
        raise ValueError("constrained ground height is outside the interval")
    regions = ground["validation_regions"]
    if len(regions) < resolved["independent_regions_min"]:
        raise ValueError("a valid constrained ground needs at least %d regions"
                         % resolved["independent_regions_min"])
    _validate_region_diagnostics(regions, point_count, True, resolved,
                                 fit_support, fit_group)
    return ground


def check_ground_stability(reference, current, settings=None):
    """Across-frame-group normal/offset stability check (synthetic gate)."""
    resolved = resolve_constrained_settings(settings)
    report = {"stable": False, "normal_change_deg": None,
              "offset_change_m": None,
              "normal_change_max_deg": resolved["normal_change_max_deg"],
              "offset_change_max_m": resolved["offset_change_max_m"]}
    if not (ground_is_valid(reference) and ground_is_valid(current)):
        report["reason"] = "ground_not_valid"
        return report
    angle = _angle_deg(reference["normal"], current["normal"])
    gap = abs(float(reference["offset_m"]) - float(current["offset_m"]))
    report["normal_change_deg"] = angle
    report["offset_change_m"] = gap
    report["stable"] = (angle <= resolved["normal_change_max_deg"]
                        and gap <= resolved["offset_change_max_m"])
    return report


# ---------------------------------------------------------------------------
# GL-02 trusted-region ground monitoring.
#
# Once a fixed ground-derived transform is frozen, only points inside the
# artifact's trusted ground-local ROI are checked, against the ground Z = 0
# residual. Support thresholds reuse the GL-00 approved gates; the continuity
# count is an explicit synthetic design value (NOT field-measured) and the
# monitor never claims to detect all horizontal movement or yaw.
# ---------------------------------------------------------------------------

MONITOR_OK = "ok"
MONITOR_DEGRADED = "degraded"
MONITOR_UNKNOWN = "unknown"
MONITOR_RECALIBRATION = "recalibration_required"
MONITOR_STATUSES = (MONITOR_OK, MONITOR_DEGRADED, MONITOR_UNKNOWN,
                    MONITOR_RECALIBRATION)

GROUND_MONITOR_DEFAULT_SETTINGS = {
    # Reused GL-00 approved gates (not relaxed here).
    "min_support_points": 20,      # = points_per_region_min
    "min_support_fraction": 0.8,   # = support_fraction_min
    "residual_tolerance_m": 0.05,  # = abs_residual_p95_max_m
    # New synthetic design value (field-unmeasured): how many consecutive frames
    # a residual shift must persist before demanding recalibration. A frame
    # count is NOT a physical duration; the live rate is unmeasured.
    "sustained_frames": 5,
    "history_frames": 30,
}

# Thresholds/duration-style values must be positive finite numbers.
_GROUND_MONITOR_POSITIVE = ("min_support_fraction", "residual_tolerance_m")
# Count keys must be strict integers (a float/bool is rejected, never truncated).
_GROUND_MONITOR_COUNT = ("min_support_points", "sustained_frames",
                         "history_frames")


def resolve_ground_monitor_settings(settings=None):
    resolved = dict(GROUND_MONITOR_DEFAULT_SETTINGS)
    for key, value in (settings or {}).items():
        if key not in resolved:
            raise ValueError("unknown ground monitor setting: " + str(key))
        resolved[key] = value
    for key in _GROUND_MONITOR_POSITIVE:
        value = _finite_number(resolved[key], key)
        if value <= 0.0:
            raise ValueError(key + " must be a positive number")
        resolved[key] = value
    if not 0.0 < resolved["min_support_fraction"] <= 1.0:
        raise ValueError("min_support_fraction must be in (0, 1]")
    for key in _GROUND_MONITOR_COUNT:
        value = _integer_value(resolved[key], key)
        if value <= 0:
            raise ValueError(key + " must be a positive integer")
        resolved[key] = value
    if resolved["sustained_frames"] > resolved["history_frames"]:
        raise ValueError("sustained_frames must not exceed history_frames")
    return resolved


def _ground_monitor_block(block):
    if not isinstance(block, dict) or block.get("kind") != "ground_derived":
        raise ValueError("a ground-derived block is required for ground monitoring")
    try:
        rotation = np.asarray(block.get("R"), dtype=np.float64)
        translation = np.asarray(block.get("t"), dtype=np.float64)
    except (TypeError, ValueError):
        raise ValueError("ground-derived R/t must be numeric") from None
    if rotation.shape != (3, 3) or translation.shape != (3,) \
            or not np.all(np.isfinite(rotation)) or not np.all(np.isfinite(translation)):
        raise ValueError("ground-derived R/t must be finite 3x3/3")
    region = block.get("valid_region_ground_local")
    if not isinstance(region, dict) or region.get("available") is False:
        return rotation, translation, None
    # Ground identity: an auto-derived AABB (source valid_region corners) is only
    # an outer geometric bound, NOT proof of ground coverage. Monitoring may only
    # report a green result when the region carries an explicit trusted flag and
    # an evidence record of where that trusted ROI came from (a synthetic fixture
    # or a field-verified region). Anything else is unknown, never ok.
    if region.get("trusted") is not True:
        return rotation, translation, None
    if not region.get("evidence"):
        return rotation, translation, None
    for key in ("x_min_m", "x_max_m", "y_min_m", "y_max_m"):
        value = region.get(key)
        if value is None or not math.isfinite(float(value)):
            raise ValueError("trusted region " + key + " must be finite")
    if region["x_min_m"] > region["x_max_m"] or region["y_min_m"] > region["y_max_m"]:
        raise ValueError("trusted region bounds are inconsistent")
    return rotation, translation, region


def monitor_ground_residual(points, ground_derived, settings=None):
    """One-frame residual check over the trusted ground-local region.

    Points are mapped to ``ground_local`` with the frozen transform; only those
    inside the trusted ROI count. No trusted region, too few ROI points, or a
    residual signature that is no longer a coherent plane yields ``unknown`` /
    ``degraded`` rather than a green result. Residual statistics are computed
    for every frame that has enough ROI points, so a coherent *whole-plane
    offset* (old support gates fail) still reports a finite ``p95_m`` instead of
    being swallowed as plain "insufficient support". Continuity is applied by
    :class:`GroundMonitor`. No horizontal/yaw detection is claimed.
    """
    resolved = resolve_ground_monitor_settings(settings)
    rotation, translation, region = _ground_monitor_block(ground_derived)
    array = np.asarray(points, dtype=np.float64)
    if array.ndim != 2 or array.shape[1] != 3:
        raise ValueError("points must be an (N,3) array")
    array = array[np.all(np.isfinite(array), axis=1)]
    report = {"status": MONITOR_UNKNOWN, "reason": None,
              "point_count": int(len(array)), "roi_count": 0,
              "support_count": 0, "support_fraction": None, "shift_m": None,
              "shift_spread_m": None, "shift_coherent": None,
              "rms_m": None, "p95_m": None,
              "residual_tolerance_m": resolved["residual_tolerance_m"],
              "min_support_points": resolved["min_support_points"],
              "min_support_fraction": resolved["min_support_fraction"],
              "sustained": False}
    if region is None:
        report["reason"] = "no_trusted_region"
        return report
    if not len(array):
        report["reason"] = "no_points"
        return report
    mapped = array @ rotation.T + translation
    inside = ((mapped[:, 0] >= region["x_min_m"]) & (mapped[:, 0] <= region["x_max_m"])
              & (mapped[:, 1] >= region["y_min_m"]) & (mapped[:, 1] <= region["y_max_m"]))
    roi = mapped[inside]
    report["roi_count"] = int(len(roi))
    if len(roi) < resolved["min_support_points"]:
        report["status"] = MONITOR_UNKNOWN
        report["reason"] = "insufficient_trusted_region_points"
        return report
    signed = roi[:, 2]
    residual = np.abs(signed)
    tolerance = resolved["residual_tolerance_m"]
    support = residual <= tolerance
    support_count = int(np.count_nonzero(support))
    support_fraction = float(support_count / len(residual))
    report["support_count"] = support_count
    report["support_fraction"] = support_fraction
    report["shift_m"] = float(np.median(signed))  # signed: a |z| median could
    # never name a direction
    report["rms_m"] = float(np.sqrt(np.mean(residual ** 2)))
    report["p95_m"] = float(np.percentile(residual, 95.0))

    def _coherence(sample):
        """Dominant-direction evidence for a candidate shift.

        A credible plane shift concentrates the off-support residuals on one
        side of the old plane around one magnitude; bidirectional scatter
        (furniture/obstacle echoes both above and below) has no dominant sign
        and is never shift evidence. Returns ``(shift, spread, coherent)``.
        """
        if len(sample) < resolved["min_support_points"]:
            return 0.0, None, False
        shift = float(np.median(sample))
        aligned = sample[np.sign(sample) == np.sign(shift)]
        if len(aligned) < 0.8 * len(sample):
            return shift, None, False
        deviation = float(np.percentile(np.abs(aligned - shift), 95.0))
        spread_limit = abs(shift) * 0.2 + 0.01  # scale-aware coherence bound
        return shift, deviation, bool(deviation <= spread_limit)

    if support_count >= resolved["min_support_points"] \
            and support_fraction >= resolved["min_support_fraction"]:
        # The old plane still fits with a high support fraction. A coherent
        # *off-support* patch here is a local obstacle/furniture echo (a
        # one-sided flat object is naturally same-sign and low-spread), NOT
        # evidence that the whole ground moved: whole-plane shift evidence is
        # only credited when the old plane itself lost its support. An
        # obstacle-sized patch is reported as a degraded/unknown frame so the
        # caller can warn, but it never feeds the recalibration latch.
        off = signed[residual > tolerance]
        report["status"] = MONITOR_OK
        if len(off) >= resolved["min_support_points"]:
            shift, deviation, coherent = _coherence(off)
            report["shift_m"] = shift
            report["shift_spread_m"] = deviation
            report["shift_coherent"] = False
            if coherent and report["p95_m"] > tolerance:
                # Distinguishable only as "something sits on/partly hides the
                # ground"; we deliberately cannot call this a plane change.
                report["status"] = MONITOR_DEGRADED
                report["reason"] = "local_obstacle_suspected"
        return report
    # Distinguish a *coherent whole-plane shift* (nearly all ROI points on the
    # same wrong side) from a *breaking* ground (bidirectional scatter,
    # obstacles/furniture, sparse edges). Only the former is credible
    # recalibration evidence; the latter is a plain degraded/unknown frame even
    # when its p95 is large. The old-plane |z|<=tol support gate is unchanged
    # (GL-00 thresholds are not relaxed).
    if report["p95_m"] <= tolerance:
        report["status"] = MONITOR_DEGRADED
        report["reason"] = "insufficient_ground_support_scattered"
        report["shift_coherent"] = False
        return report
    shift, deviation, coherent = _coherence(signed)
    report["shift_m"] = shift
    report["shift_spread_m"] = deviation
    report["shift_coherent"] = coherent
    if coherent:
        report["status"] = MONITOR_DEGRADED
        report["reason"] = "ground_residual_shift"
    elif len(signed[np.abs(signed - shift) <= tolerance]) \
            < resolved["min_support_points"]:
        # No dominant direction at all (e.g. a 50/50 +/-0.1 split): the ROI
        # evidence cannot tell a plane shift from scatter, so it is unknown,
        # not a degraded-but-credible shift. Recognised limitation: such a
        # symmetric split can currently not be told apart from a plane being
        # occluded by large furniture from both sides.
        report["status"] = MONITOR_UNKNOWN
        report["reason"] = "residual_shift_incoherent"
    else:
        report["status"] = MONITOR_DEGRADED
        report["reason"] = "residual_shift_incoherent"
    return report


class GroundMonitor:
    """Apply :func:`monitor_ground_residual` over time and require continuity.

    A single frame beyond tolerance is reported as ``degraded``; only a run of
    ``sustained_frames`` consecutive frames carrying a *coherent* grounded
    shift asks for recalibration. ``sustained_frames`` remains an explicit
    synthetic design value (a frame count, never a claimed physical duration).
    A sparse/unknown/breaking frame only clears the *current continuity run* —
    a latched recalibration requirement survives until an explicit new valid
    ground context (``note_valid_ground_context``), so one good frame can
    never silently "heal" a calibration the monitor already invalidated.
    """

    def __init__(self, settings=None):
        self.settings = resolve_ground_monitor_settings(settings)
        self._over = deque(maxlen=self.settings["history_frames"])
        self.recalibration_latched = False

    def feed(self, points, ground_derived):
        report = monitor_ground_residual(points, ground_derived, self.settings)
        # Recalibration evidence = p95 above tolerance AND a coherent
        # dominant-direction shift. Bidirectional scatter (no dominant sign)
        # never feeds the latch; nor does an unknown/no-trusted-region frame.
        over = bool(report.get("p95_m") is not None
                    and report["p95_m"] > self.settings["residual_tolerance_m"])
        coherent_shift = bool(report.get("shift_coherent")) and over \
            and report["status"] in (MONITOR_DEGRADED, MONITOR_OK)
        if report["status"] == MONITOR_UNKNOWN:
            self._over.clear()  # stream gap / no trusted ROI: drop evidence
        else:
            self._over.append(bool(coherent_shift))
        needed = self.settings["sustained_frames"]
        recent = list(self._over)[-needed:]
        sustained = len(recent) == needed and all(recent)
        report["sustained"] = sustained
        if coherent_shift and sustained:
            self.recalibration_latched = True
        if self.recalibration_latched:
            # Latch: a return to the old plane does not undo an established
            # recalibration requirement; only an explicit new valid ground
            # context (reload) is allowed to.
            report["status"] = MONITOR_RECALIBRATION
            report["reason"] = "ground_residual_shift"
        elif over and report["status"] == MONITOR_OK:
            report["status"] = MONITOR_DEGRADED
            report["reason"] = "ground_residual_change_not_sustained"
        return report

    def note_valid_ground_context(self):
        """A new validated ground context took over: clear latch and runs."""
        self._over.clear()
        self.recalibration_latched = False

    def note_invalid(self):
        """Drop the continuity run for a gap/invalid frame.

        Only the *current* continuous evidence is cleared; an established
        recalibration requirement (“the calibration was already invalidated”)
        is a different state and is never erased by a stream interruption.
        """
        self._over.clear()

    def snapshot(self):
        return {"history_frames": list(self._over),
                "sustained_frames": self.settings["sustained_frames"],
                "recalibration_latched": bool(self.recalibration_latched)}


def validate_ground_plane(ground, expected_frame=None, normal_tolerance=1e-3):
    """Strict structural validation of a ground-plane record.

    A ``valid`` ground must carry a unit normal (upward, nearly vertical within
    the reported tilt), a positive height, a well-formed valid region and a
    held-out residual block: statistics alone are not enough, and a record with
    missing/mistyped fields raises instead of being accepted. Non-valid statuses
    may omit the plane but any present normal/offset must still be finite and
    well typed. This never fills in physical values.
    """
    if not isinstance(ground, dict):
        raise ValueError("ground must be an object")
    status = ground.get("status")
    if status not in STATUSES:
        raise ValueError("unsupported ground status: " + repr(status))
    frame = ground.get("frame")
    if not isinstance(frame, str) or not frame:
        raise ValueError("ground.frame must be a non-empty string")
    if expected_frame is not None and frame != expected_frame:
        raise ValueError("ground.frame does not match the artifact lidar frame")
    normal = ground.get("normal")
    offset = ground.get("offset_m")
    if normal is not None:
        # A bool "1.0" (mixed-bool normal) must never be silently coerced.
        array = strict_numeric_array(normal, (3,), "ground.normal",
                                     error_cls=ValueError)
    if offset is not None:
        if isinstance(offset, bool) or not isinstance(
                offset, (int, float, np.integer, np.floating)):
            raise ValueError("ground.offset_m must be a real number")
        value = float(offset)
        if not np.isfinite(value):
            raise ValueError("ground.offset_m must be finite")
    if status != STATUS_VALID:
        return ground
    if normal is None:
        raise ValueError("a valid ground needs a normal")
    if abs(float(np.linalg.norm(normal)) - 1.0) > float(normal_tolerance):
        raise ValueError("ground normal is not unit length")
    if float(offset) <= 0.0 or normal[2] <= 0.0:
        raise ValueError("a valid ground must sit below the sensor")
    region = ground.get("valid_region")
    if not isinstance(region, dict):
        raise ValueError("a valid ground needs a valid_region")
    for key in _REGION_BOUNDS:
        if key in ("range_min_m", "range_max_m"):
            if region.get(key) is None or not np.isfinite(float(region[key])):
                raise ValueError("valid_region." + key + " must be finite")
        else:
            numeric = region.get(key)
            if numeric is None or not np.isfinite(float(numeric)):
                raise ValueError("valid_region." + key + " must be finite")
    if region["x_min_m"] > region["x_max_m"] or region["y_min_m"] > region["y_max_m"] \
            or region["z_min_m"] > region["z_max_m"] \
            or region["range_min_m"] > region["range_max_m"]:
        raise ValueError("valid_region bounds are inconsistent")
    point_count = region.get("point_count")
    if not isinstance(point_count, int) or isinstance(point_count, bool) \
            or point_count < 0:
        raise ValueError("valid_region.point_count must be a non-negative integer")
    residual = ground.get("holdout_residual")
    if not isinstance(residual, dict) or residual.get("count", 0) <= 0:
        raise ValueError("a valid ground needs a non-empty held-out residual")
    for key in ("rms_m", "max_m"):
        if not np.isfinite(float(residual[key])) or float(residual[key]) < 0.0:
            raise ValueError("holdout_residual." + key + " must be finite and >= 0")
    support = ground.get("holdout_support")
    if not isinstance(support, dict) or support.get("count", 0) <= 0:
        raise ValueError("a valid ground needs held-out ground support")
    fraction = support.get("fraction")
    if fraction is None or not np.isfinite(float(fraction)) \
            or not 0.0 <= float(fraction) <= 1.0:
        raise ValueError("holdout_support.fraction must be in [0, 1]")
    for key in ("rms_m", "max_m"):
        if not np.isfinite(float(support[key])) or float(support[key]) < 0.0:
            raise ValueError("holdout_support." + key + " must be finite and >= 0")
    return ground

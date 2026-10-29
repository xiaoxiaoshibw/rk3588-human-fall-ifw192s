"""Posture-independent point-cloud candidates and geometry features (HF-04).

Scope and honesty rules (see docs/human_fall/tickets/HF-04_perception_candidates.md):

- This is geometry only: no camera, no learned human detector, no skeleton. A
  candidate is a connected point cluster with a robust centre, a 3D source-frame
  bounding box, ground-relative height quantiles, a horizontal extent, a PCA
  principal axis (with an explicit degeneracy flag) and the evidence point
  indices back into the decoded cloud. It never claims a semantic human label:
  ``semantic`` stays ``unknown`` until an operator confirms a target (HF-05).
- The old stationary-person size gate (standing height / narrow width-depth) is
  NOT the entry condition here, so a lying or crouching cluster is still kept.
  Low clusters only carry quality flags, they are not dropped for being low.
- Raw LiDAR XY/Z is not assumed to be horizontal/vertical. When the HF-03 ground
  is valid, ground-relative height is ``n . p + d`` and the horizontal plane is
  the ground tangent basis; otherwise the candidate stays in uncalibrated radar
  coordinates with no height/fall observability (never ``ground z = 0``).
- Background is built only from an explicit empty-scene capture and is frozen.
  It is never updated online, so a still person cannot be learned into it.
- Everything here is pure NumPy + stdlib. ROS is touched only in the optional
  ``decode_cloud`` helper, which reuses the existing human_follow decoder.
"""

import copy
import json

import numpy as np

try:  # pragma: no cover - import shim exercised through package/tests
    from core.ground import STATUS_VALID
except ImportError:  # pragma: no cover
    from ground import STATUS_VALID

KIND = "candidate_snapshot"
BACKGROUND_KIND = "candidate_background"
SCHEMA_VERSION = 1
UNITS = {"length": "m", "angle": "rad"}

DEFAULT_SETTINGS = {
    "range_min_m": 0.8,
    "range_max_m": 8.0,
    "height_min_m": -0.3,
    "height_max_m": 2.5,
    "voxel_size_m": 0.08,
    "cluster_cell_m": 0.25,
    "cluster_mode": "horizontal",
    "max_points": 60000,
    "min_cluster_points": 25,
    "preferred_cluster_points": 80,
    "pca_min_points": 12,
    "pca_axis_ratio": 2.5,
    "background_cell_m": 0.1,
    "background_z_cell_m": 0.1,
    "denoise_enabled": False,
    "denoise_radius_m": 0.1,
    "denoise_min_neighbors": 2,
}

_POSITIVE = ("range_max_m", "voxel_size_m", "cluster_cell_m", "max_points",
             "min_cluster_points", "preferred_cluster_points", "pca_min_points",
             "pca_axis_ratio", "background_cell_m", "background_z_cell_m",
             "denoise_radius_m")


def resolve_settings(settings=None):
    """Merge overrides onto the defaults and validate the numeric bounds."""
    resolved = dict(DEFAULT_SETTINGS)
    for key, value in (settings or {}).items():
        if key not in resolved:
            raise ValueError("unknown candidate setting: " + str(key))
        resolved[key] = value
    for key in _POSITIVE:
        resolved[key] = float(resolved[key])
        if not np.isfinite(resolved[key]) or resolved[key] <= 0.0:
            raise ValueError(key + " must be a positive finite number")
    resolved["max_points"] = int(resolved["max_points"])
    resolved["min_cluster_points"] = int(resolved["min_cluster_points"])
    resolved["preferred_cluster_points"] = int(resolved["preferred_cluster_points"])
    resolved["pca_min_points"] = int(resolved["pca_min_points"])
    if resolved['cluster_mode'] not in ('horizontal','spatial_3d'):
        raise ValueError('cluster_mode must be horizontal or spatial_3d')
    if not isinstance(resolved["denoise_enabled"], bool):
        raise ValueError("denoise_enabled must be true or false")
    if isinstance(resolved["denoise_min_neighbors"], bool) \
            or not isinstance(resolved["denoise_min_neighbors"], (int, np.integer)):
        raise ValueError("denoise_min_neighbors must be an integer")
    resolved["denoise_min_neighbors"] = int(resolved["denoise_min_neighbors"])
    if resolved["denoise_min_neighbors"] < 1:
        raise ValueError("denoise_min_neighbors must be at least 1")
    for key in ("range_min_m", "height_min_m", "height_max_m"):
        resolved[key] = float(resolved[key])
        if not np.isfinite(resolved[key]):
            raise ValueError(key + " must be finite")
    if resolved["range_max_m"] <= resolved["range_min_m"]:
        raise ValueError("range_max_m must be greater than range_min_m")
    if resolved["height_max_m"] <= resolved["height_min_m"]:
        raise ValueError("height_max_m must be greater than height_min_m")
    return resolved


def ground_plane_basis(ground):
    """Return (normal, u, v) for a valid ground, else None.

    ``normal`` points up toward the sensor; ``u``/``v`` span the ground tangent
    plane (the physical horizontal plane). An absent/unverified ground returns
    ``None`` so callers fall back to explicit uncalibrated radar coordinates.
    """
    if not isinstance(ground, dict) or ground.get("status") != STATUS_VALID:
        return None
    try:
        normal = np.asarray(ground.get("normal"), dtype=np.float64)
        offset = float(ground.get("offset_m"))
    except (TypeError, ValueError):
        return None
    if normal.shape != (3,) or not np.all(np.isfinite(normal)) or not np.isfinite(offset):
        return None
    norm = float(np.linalg.norm(normal))
    if norm < 1e-9:
        return None
    normal = normal / norm
    reference = np.array([0.0, 0.0, 1.0])
    if abs(float(normal @ reference)) > 0.9:
        reference = np.array([0.0, 1.0, 0.0])
    u = np.cross(normal, reference)
    u = u / np.linalg.norm(u)
    v = np.cross(normal, u)
    return normal, u, v


def ground_frame_eligible(ground, frame_id):
    """True when ``ground`` may be applied to a frame from ``frame_id``.

    The shared source-frame guard for every ground-dependent computation (height
    filtering, per-candidate ``height_m``/horizontal basis, coordinate/quality
    flags and the node's ground gate). A ground plane belongs to the lidar frame
    it was fitted in: applying it to a different source frame would fabricate a
    height-above-ground. A non-empty ``ground['frame']`` that differs from a
    non-empty ``frame_id`` is therefore ineligible, with or without a derived
    block. Missing frame strings keep the pre-existing legacy behaviour.
    """
    if not isinstance(ground, dict) or ground.get("status") != STATUS_VALID:
        return False
    recorded = ground.get("frame")
    if isinstance(recorded, str) and recorded and \
            isinstance(frame_id, str) and frame_id:
        return recorded == frame_id
    return True


def _voxel_cells(points, cell_m, z_cell_m):
    grid = np.floor(points / (cell_m, cell_m, z_cell_m)).astype(np.int64)
    return grid


def build_background(empty_frames, settings=None, frame_id=None, note=None):
    """Freeze a static background from explicit empty-scene frames.

    Only the supplied frames are learned; there is deliberately no update call,
    so a still person captured after the empty scene can never drift into the
    background. Cells are source-frame voxels with per-axis cell sizes in metres.
    """
    resolved = resolve_settings(settings)
    arrays = [np.asarray(frame, dtype=np.float64) for frame in empty_frames]
    arrays = [array for array in arrays if array.ndim == 2 and array.shape[1] == 3]
    if not arrays:
        raise ValueError("background needs at least one (N,3) empty-scene frame")
    cells = set()
    point_count = 0
    for array in arrays:
        array = array[np.all(np.isfinite(array), axis=1)]
        if not len(array):
            continue
        point_count += int(len(array))
        grid = _voxel_cells(array, resolved["background_cell_m"],
                            resolved["background_z_cell_m"])
        cells.update(map(tuple, grid.tolist()))
    if not cells:
        raise ValueError("empty-scene frames contain no finite points")
    return {
        "kind": BACKGROUND_KIND,
        "schema_version": SCHEMA_VERSION,
        "units": dict(UNITS),
        "frame_id": frame_id,
        "cell_m": resolved["background_cell_m"],
        "z_cell_m": resolved["background_z_cell_m"],
        "cells": sorted(cells),
        "cell_count": len(cells),
        "frame_count": len(arrays),
        "point_count": point_count,
        "note": note,
    }


class _BackgroundCells(frozenset):
    """已规范化的冻结体素；有界占据表只在显式准备时构造。"""

    def __new__(cls, cells):
        frozen = super().__new__(cls, cells)
        frozen.dense = None
        if not frozen:
            return frozen
        try:
            values = np.asarray(list(frozen), dtype=np.int64)
        except (OverflowError, ValueError, TypeError):
            return frozen
        low, high = values.min(axis=0), values.max(axis=0)
        shape = tuple(int(b) - int(a) + 1 for a, b in zip(low, high))
        volume = shape[0] * shape[1] * shape[2]
        # Limit the prepared lookup to 8MB; sparse large extents use the set.
        if volume > 8000000:
            return frozen
        local = values - low
        ids = (local[:, 0] * shape[1] + local[:, 1]) * shape[2] + local[:, 2]
        occupied = np.zeros(volume, dtype=bool)
        occupied[ids] = True
        for array in (low, high, occupied):
            array.flags.writeable = False
        frozen.dense = low, high, shape, occupied
        return frozen


def prepare_background(background):
    """Prepare a detached frozen runtime copy; serialized artifacts stay unchanged."""
    if not background:
        return background
    return dict(background, cells=_BackgroundCells(_background_cell_set(background)))


def _background_cell_set(background):
    if isinstance(background.get('cells'), _BackgroundCells):
        return background['cells']
    cells = set()
    for cell in background.get("cells", []):
        cells.add((int(cell[0]), int(cell[1]), int(cell[2])))
    return cells


def foreground_mask(points, background):
    """Boolean mask of points not present in a frozen background (True=foreground)."""
    array = np.asarray(points, dtype=np.float64)
    if array.ndim != 2 or array.shape[1] != 3:
        raise ValueError("points must be an (N,3) array")
    if not background:
        return np.ones(len(array), dtype=bool)
    cell_m = float(background.get("cell_m", DEFAULT_SETTINGS["background_cell_m"]))
    z_cell_m = float(background.get("z_cell_m", DEFAULT_SETTINGS["background_z_cell_m"]))
    cells = _background_cell_set(background)
    grid = _voxel_cells(array, cell_m, z_cell_m)
    if isinstance(cells, _BackgroundCells) and cells.dense is not None:
        low, high, shape, occupied = cells.dense
        inside = (grid >= low).all(axis=1) & (grid <= high).all(axis=1)
        mask = np.ones(len(grid), dtype=bool)
        # Subtract only in-range cells to avoid overflow on extreme queries.
        local = grid[inside] - low
        ids = (local[:, 0] * shape[1] + local[:, 1]) * shape[2] + local[:, 2]
        mask[inside] = ~occupied[ids]
        return mask
    mask = np.array([tuple(cell) not in cells for cell in grid.tolist()], dtype=bool)
    return mask


def scene_change_fraction(points, background):
    """Fraction of supplied points that are not explained by the frozen background.

    A high fraction indicates the scene moved/changed since the empty capture;
    the caller must then recapture instead of trusting background subtraction.
    Returns ``None`` when no background was supplied.
    """
    if not background:
        return None
    array = np.asarray(points, dtype=np.float64)
    if not len(array):
        return None
    return float(np.count_nonzero(foreground_mask(array, background)) / len(array))


def denoise_mask(points, radius_m, min_neighbors):
    """Keep mask for the isolated-point denoise stage (True = keep).

    A point is kept when its ``radius_m``-sized voxel plus the 26 neighbouring
    voxels hold at least ``min_neighbors`` points including the point itself
    (``min_neighbors=1`` keeps everything). This is a coarse deterministic
    radius filter -- candidates are counted per voxel, not by exact pairwise
    distance -- applied after the finite/range gates so coordinates are
    bounded. The dense box-sum path is the normal one; the packed-key fallback
    keeps compute/memory bounded for very small configured radii.
    """
    array = np.asarray(points, dtype=np.float64)
    if array.ndim != 2 or array.shape[1] != 3:
        raise ValueError("points must be an (N,3) array")
    radius = float(radius_m)
    if not np.isfinite(radius) or radius <= 0.0:
        raise ValueError("radius_m must be a positive finite number")
    if isinstance(min_neighbors, bool) \
            or not isinstance(min_neighbors, (int, np.integer)):
        raise ValueError("min_neighbors must be an integer")
    min_neighbors = int(min_neighbors)
    if min_neighbors < 1:
        raise ValueError("min_neighbors must be at least 1")
    if not len(array):
        return np.zeros(0, dtype=bool)
    cells = np.floor(array / radius).astype(np.int64)
    low = cells.min(axis=0)
    span = cells.max(axis=0) - low + 1
    if int(span[0]) * int(span[1]) * int(span[2]) <= _DENSE_CELL_LIMIT:
        total = _dense_neighbour_counts(cells, low, span)
    else:
        total = _packed_neighbour_counts(cells, low, span)
    return total >= min_neighbors


_DENSE_CELL_LIMIT = 8000000  # int32 dense grid cap (~32 MiB transient)


def _dense_neighbour_counts(cells, low, span):
    """27-cell counts via a separable [1,1,1] box sum on a dense int32 grid."""
    shape = (int(span[0]), int(span[1]), int(span[2]))
    ids = ((cells[:, 0] - low[0]) * shape[1] + (cells[:, 1] - low[1])) \
        * shape[2] + (cells[:, 2] - low[2])
    counts = np.bincount(ids, minlength=shape[0] * shape[1] * shape[2])
    grid = counts.reshape(shape).astype(np.int32)
    for axis in (0, 1, 2):
        n = shape[axis]
        moved = grid.copy()
        head = [slice(None)] * 3
        tail = [slice(None)] * 3
        head[axis] = slice(0, n - 1)
        tail[axis] = slice(1, n)
        moved[tuple(tail)] += grid[tuple(head)]
        moved[tuple(head)] += grid[tuple(tail)]
        grid = moved
    return grid.reshape(-1)[ids]


def _packed_neighbour_counts(cells, low, span):
    """Fallback above the dense cap: packed int64 keys + 27 searchsorted.

    A digit base larger than every axis span keeps the 27 shifted keys
    distinct, and makes an out-of-range neighbour key borrow into a digit value
    no real cell can occupy, so it can never match a real point.
    """
    base = int(span.max()) + 1
    if base > (1 << 20):
        raise ValueError("radius_m too small for the point extent")
    key = ((cells[:, 0] - low[0]) * base + (cells[:, 1] - low[1])) * base \
        + (cells[:, 2] - low[2])
    unique, counts = np.unique(key, return_counts=True)
    stride_x = base * base
    stride_y = base
    total = np.zeros(len(key), dtype=np.int64)
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for dz in (-1, 0, 1):
                shifted = key + (dx * stride_x + dy * stride_y + dz)
                index = np.searchsorted(unique, shifted)
                index = np.minimum(index, len(unique) - 1)
                hit = unique[index] == shifted
                total += np.where(hit, counts[index], 0)
    return total


def ground_coverage(points, ground):
    """Fraction of points whose ground projection lies inside the ground region.

    Coverage is judged on the projection onto the ground plane using the fitted
    region's horizontal/range bounds, never by a narrow raw-z band, so a standing
    or lying person is not rejected just for spanning height. No valid ground ->
    ``available`` False with no fraction (never an assumed plane).
    """
    basis = ground_plane_basis(ground)
    if basis is None:
        return {"available": False, "reason": "ground_unavailable",
                "projected_inside_fraction": None, "inside_count": None,
                "point_count": int(len(points))}
    array = np.asarray(points, dtype=np.float64)
    if array.ndim != 2 or array.shape[1] != 3:
        raise ValueError("points must be an (N,3) array")
    if not len(array):
        return {"available": True, "reason": None, "projected_inside_fraction": None,
                "inside_count": 0, "point_count": 0}
    normal, _, _ = basis
    offset = float(ground["offset_m"])
    heights = array @ normal + offset
    projected = array - heights[:, None] * normal
    region = ground.get("valid_region") or {}
    inside = np.ones(len(projected), dtype=bool)
    for axis, prefix in enumerate(("x", "y", "z")):
        low = region.get(prefix + "_min_m")
        high = region.get(prefix + "_max_m")
        if low is not None and high is not None:
            inside &= (projected[:, axis] >= float(low)) & (projected[:, axis] <= float(high))
    ranges = np.linalg.norm(projected, axis=1)
    if region.get("range_min_m") is not None and region.get("range_max_m") is not None:
        inside &= (ranges >= float(region["range_min_m"])) & (ranges <= float(region["range_max_m"]))
    return {"available": True, "reason": None,
            "projected_inside_fraction": float(np.count_nonzero(inside) / len(projected)),
            "inside_count": int(np.count_nonzero(inside)),
            "point_count": int(len(projected))}


def _horizontal_coords(points, basis):
    """Horizontal (u, v) coordinates; raw XY when no valid ground exists."""
    if basis is None:
        return points[:, :2]
    return np.column_stack((points @ basis[1], points @ basis[2]))


def _connected_clusters(horizontal, cell_m):
    """Connected components over occupied horizontal cells (8-neighbourhood)."""
    grid = np.floor(horizontal / float(cell_m)).astype(np.int64)
    buckets = {}
    for index, cell in enumerate(grid.tolist()):
        buckets.setdefault((cell[0], cell[1]), []).append(index)
    seen = set()
    clusters = []
    for start in buckets:
        if start in seen:
            continue
        seen.add(start)
        stack = [start]
        members = []
        while stack:
            current = stack.pop()
            members.extend(buckets[current])
            cx, cy = current
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    neighbour = (cx + dx, cy + dy)
                    if neighbour in buckets and neighbour not in seen:
                        seen.add(neighbour)
                        stack.append(neighbour)
        clusters.append(np.array(members, dtype=np.int64))
    return clusters


def _spatial_block_components(grid, low, base):
    """将必连通的 2x2x2 体素块合并遍历；8 位掩码保留精确边界连接。"""
    digits = grid.astype(np.int64) - low + 1
    fine = (digits[:, 0] * base + digits[:, 1]) * base + digits[:, 2]
    coarse = grid // 2
    coarse_low = coarse.min(axis=0)
    coarse_base = int((coarse.max(axis=0) - coarse_low).max()) + 3
    digits = coarse - coarse_low + 1
    keys = (digits[:, 0] * coarse_base + digits[:, 1]) * coarse_base + digits[:, 2]
    unique, inverse = np.unique(keys, return_inverse=True)
    count = len(unique)
    bits = np.left_shift(1, (grid[:, 0] & 1) * 4 + (grid[:, 1] & 1) * 2 + (grid[:, 2] & 1)).astype(np.uint8)
    masks = np.zeros(count, dtype=np.uint8)
    np.bitwise_or.at(masks, inverse, bits)
    minimum = np.full(count, np.iinfo(np.int64).max, dtype=np.int64)
    np.minimum.at(minimum, inverse, fine)
    masks = masks.tolist()
    remaining = dict(zip(unique.tolist(), range(count)))
    get = remaining.get
    x_masks, y_masks, z_masks = (0x0f, 0xff, 0xf0), (0x33, 0xff, 0xcc), (0x55, 0xff, 0xaa)
    neighbours = [(dx * coarse_base * coarse_base + dy * coarse_base + dz,
                   x_masks[dx + 1] & y_masks[dy + 1] & z_masks[dz + 1],
                   x_masks[1 - dx] & y_masks[1 - dy] & z_masks[1 - dz])
                  for dx in (-1, 0, 1) for dy in (-1, 0, 1)
                  for dz in (-1, 0, 1) if dx or dy or dz]
    allowed = {mask: [(offset, other) for offset, face, other in neighbours if mask & face]
               for mask in set(masks)}
    labels = np.empty(count, dtype=int)
    groups = 0
    for seed in unique[np.argsort(minimum)].tolist():
        index = remaining.pop(seed, None)
        if index is None:
            continue
        labels[index] = groups
        stack = [(seed, masks[index])]
        while stack:
            key, mask = stack.pop()
            for offset, opposite in allowed[mask]:
                neighbour = key + offset
                index = get(neighbour)
                if index is not None and masks[index] & opposite:
                    del remaining[neighbour]
                    labels[index] = groups
                    stack.append((neighbour, masks[index]))
        groups += 1
    labels = labels[inverse]
    order = np.argsort(labels, kind='mergesort')
    return [rows.tolist() for rows in np.split(order, np.flatnonzero(np.diff(labels[order])) + 1)]


def spatial_components(points, cell_m=0.05):
    """RAW 26-neighbour voxel components, deterministic original row indices."""
    cells = {}
    # Batch the same quantization and use Python integer keys in the graph walk.
    # Preserve the input dtype, including float32 voxel-boundary behaviour.
    grid = np.floor(np.asarray(points) / cell_m).astype(int)
    if not len(grid):
        return []
    low = [int(value) for value in grid.min(axis=0)]
    # Padded digits prevent an outside neighbour from borrowing into another
    # occupied coordinate. Python integers keep large coordinates exact.
    base = max(int(value) - low[axis]
               for axis, value in enumerate(grid.max(axis=0))) + 3
    # 仅选择遍历实现，不改变原体素量化或 26 邻接；超大键保留 Python 整数路径。
    if len(grid) >= 1024 and base ** 3 <= np.iinfo(np.int64).max:
        return _spatial_block_components(grid, low, base)
    stride_x = base * base
    neighbours = [dx * stride_x + dy * base + dz
                  for dx in (-1, 0, 1) for dy in (-1, 0, 1)
                  for dz in (-1, 0, 1) if dx or dy or dz]
    if base ** 3 <= np.iinfo(np.int64).max:
        digits = grid.astype(np.int64) - low + 1
        keys = ((digits[:, 0] * base + digits[:, 1]) * base + digits[:, 2]).tolist()
    else:
        keys = [((cell[0]-low[0]+1)*base+cell[1]-low[1]+1)*base+cell[2]-low[2]+1
                for cell in grid.tolist()]
    for index, key in enumerate(keys):
        cells.setdefault(key, []).append(index)
    remaining = set(cells)
    groups = []
    for seed in sorted(cells):
        if seed not in remaining:
            continue
        remaining.remove(seed)
        stack, members = [seed], []
        while stack:
            key = stack.pop()
            members.extend(cells[key])
            for offset in neighbours:
                neighbour = key + offset
                if neighbour in remaining:
                    remaining.remove(neighbour)
                    stack.append(neighbour)
        groups.append(sorted(members))
    return groups


def _principal_axis(cluster):
    """PCA principal axis with an explicit degeneracy flag (source frame)."""
    count = len(cluster)
    report = {"axis": None, "eigenvalues": None, "elongation": None,
              "ambiguous": True, "quiet": True}
    if count < 3:
        return report
    centred = cluster - cluster.mean(axis=0)
    covariance = centred.T @ centred / float(count)
    try:
        values, vectors = np.linalg.eigh(covariance)
    except np.linalg.LinAlgError:  # pragma: no cover - defensive
        return report
    order = np.argsort(values)[::-1]
    values = values[order]
    vectors = vectors[:, order]
    largest = float(values[0])
    second = float(values[1])
    elongation = None if second <= 1e-12 else largest / second
    report["eigenvalues"] = [float(value) for value in values]
    report["elongation"] = elongation
    report["quiet"] = False
    report["axis"] = vectors[:, 0].tolist()
    return report


def _robust_span(values):
    if not len(values):
        return None
    low, high = np.percentile(values, [5.0, 95.0])
    return float(high - low)


def _point_features(cluster, basis, ground, settings, source_indices):
    """Geometry feature block for one cluster (all values in metres)."""
    count = int(len(cluster))
    center = np.median(cluster, axis=0)
    bbox_min = cluster.min(axis=0).tolist()
    bbox_max = cluster.max(axis=0).tolist()
    ranges = np.linalg.norm(cluster, axis=1)
    features = {
        "point_count": count,
        "evidence_indices": source_indices.tolist(),
        "_points": cluster,
        "center_source_m": [float(value) for value in center],
        "bbox_source_min_m": [float(value) for value in bbox_min],
        "bbox_source_max_m": [float(value) for value in bbox_max],
        "range_m": {"min": float(ranges.min()), "median": float(np.median(ranges)),
                    "max": float(ranges.max())},
        "ground_relative_available": False,
        "height_m": None,
        "height_span_m": None,
        "horizontal_extent_m": None,
        "axis": None,
    }
    if basis is not None:
        normal = basis[0]
        offset = float(ground["offset_m"])
        heights = cluster @ normal + offset
        features["ground_relative_available"] = True
        features["height_m"] = {
            "min": float(heights.min()),
            "p10": float(np.percentile(heights, 10.0)),
            "median": float(np.median(heights)),
            "p90": float(np.percentile(heights, 90.0)),
            "max": float(heights.max()),
        }
        features["height_span_m"] = features["height_m"]["p90"] - features["height_m"]["p10"]
        u = cluster @ basis[1]
        v = cluster @ basis[2]
        span_u = _robust_span(u)
        span_v = _robust_span(v)
        features["horizontal_extent_m"] = {
            "u": span_u, "v": span_v,
            "max": None if span_u is None or span_v is None else max(span_u, span_v)}
    pca = _principal_axis(cluster)
    axis_report = dict(pca)
    if count < settings["pca_min_points"]:
        axis_report["ambiguous"] = True
        axis_report["reason"] = "insufficient_points"
    elif pca["elongation"] is None or pca["elongation"] < settings["pca_axis_ratio"]:
        axis_report["ambiguous"] = True
        axis_report["reason"] = "no_dominant_axis"
    else:
        axis_report["ambiguous"] = False
        axis_report["reason"] = None
    if pca["axis"] is not None and basis is not None and not axis_report["ambiguous"]:
        axis_report["verticality"] = abs(float(np.asarray(pca["axis"]) @ basis[0]))
    else:
        axis_report["verticality"] = None
    if axis_report["ambiguous"]:
        axis_report["axis"] = None
    features["axis"] = axis_report
    reasons = []
    if count < settings["min_cluster_points"]:
        reasons.append("insufficient_points")
    elif count < settings["preferred_cluster_points"]:
        reasons.append("low_points")
    if axis_report["ambiguous"]:
        reasons.append("axis_ambiguous")
    if basis is None:
        reasons.append("ground_unavailable")
    features["quality"] = {
        "sufficient_points": count >= settings["min_cluster_points"],
        "low_points": count < settings["preferred_cluster_points"],
        "ground_relative": basis is not None,
        "axis_ambiguous": bool(axis_report["ambiguous"]),
        "reasons": reasons,
    }
    return features


def _resolve_reference_transform(calibration, transform, frame_id):
    """Shared reference resolver (see ``core.calibration``); lazy import."""
    try:
        from core.calibration import resolve_reference_transform
    except ImportError:  # pragma: no cover
        from calibration import resolve_reference_transform
    return resolve_reference_transform(calibration, transform, frame_id)


def _reference_block(features, transform):
    """Reference-frame center/bbox for the candidate.

    The reference bbox is the per-axis AABB over *all* actual transformed
    candidate points, not just the two source corners: with a non-zero rotation
    the transformed source corners under-cover the cluster. The center keeps its
    frozen meaning (the source center mapped by the reference transform), which
    is distinct from the ground per-axis median of actual points.
    """
    block = {"center_reference_m": None, "bbox_reference_min_m": None,
             "bbox_reference_max_m": None}
    if not transform or transform.get("status") == "unknown":
        return block
    try:
        from core.calibration import apply_transform
    except ImportError:  # pragma: no cover
        from calibration import apply_transform
    points = features.get("_points")
    if points is None or not len(points):
        return block
    mapped = apply_transform(np.asarray(points, dtype=np.float64), transform)
    low, high = mapped.min(axis=0), mapped.max(axis=0)
    block["bbox_reference_min_m"] = [float(value) for value in low]
    block["bbox_reference_max_m"] = [float(value) for value in high]
    center = features.get("center_source_m")
    block["center_reference_m"] = [float(value) for value in
                                   apply_transform(np.asarray(center, dtype=np.float64)[None, :],
                                                   transform)[0]]
    return block


def _ground_geometry_block(points, ground_derived):
    """Per-axis AABB and median of the candidate's ACTUAL ground-local points.

    Uses the same validated ground-derived R/t on the same evidence point set as
    ``bbox_ground_from=actual_points``; a rotated source median is explicitly not
    the ground median. When no valid derived artifact is bound the fields stay
    null and the source is ``unavailable`` (never derived from two corners).
    """
    block = {"bbox_ground_min_m": None, "bbox_ground_max_m": None,
             "center_ground_m": None, "bbox_ground_from": "unavailable"}
    if not ground_derived or not len(points):
        return block
    try:
        from core.calibration import apply_ground_derived
    except ImportError:  # pragma: no cover
        from calibration import apply_ground_derived
    mapped = apply_ground_derived(np.asarray(points, dtype=np.float64),
                                  ground_derived)
    low, high = mapped.min(axis=0), mapped.max(axis=0)
    median = np.median(mapped, axis=0)
    block["bbox_ground_min_m"] = [float(value) for value in low]
    block["bbox_ground_max_m"] = [float(value) for value in high]
    block["center_ground_m"] = [float(value) for value in median]
    block["bbox_ground_from"] = "actual_points"
    return block


def _validated_ground_derived(calibration, frame_id=None, ground=None):
    """Return a strictly validated embedded ``ground_derived`` block, else None.

    The *whole* artifact is validated through the shared GL-02 entry point
    (``validate_geometry_calibration``), not just the nested derived record: a
    damaged parent identity/version, a contradictory verification flag, or a
    derived block that disagrees with its parent ground/artifact sha is refused
    here, so a pure-API caller can never publish a valid ``ground_derived_id``
    (or a ground box) from a broken record.

    The derived block is then bound to the snapshot's *actual* context: its
    ``from_frame`` must equal the producing ``frame_id`` and, when the caller
    supplied an explicit ``ground``, that record must equal the artifact parent
    (otherwise a new local frame would be mixed with a different plane). Returns
    ``(block_or_None, ground_or_None)``.
    """
    if not isinstance(calibration, dict):
        return None, None
    if not isinstance(calibration.get("ground_derived"), dict):
        # No derived block: keep the legacy/source-only summary behaviour.
        return None, None
    try:
        from core.calibration import validate_geometry_calibration
    except ImportError:  # pragma: no cover
        from calibration import validate_geometry_calibration
    try:
        canonical = validate_geometry_calibration(copy.deepcopy(calibration))
    except (ValueError, TypeError):
        return None, None
    validated = canonical.get("ground_derived")
    parent = canonical.get("ground")
    if not isinstance(validated, dict) or not isinstance(parent, dict):
        return None, None
    # Bind the actual producing frame: a snapshot decoded from another lidar must
    # not inherit a local ground frame that belongs to a different source frame.
    if frame_id is not None and validated.get("from_frame") != frame_id:
        return None, None
    # Bind an explicitly supplied ground: it must be the same parent plane.
    if ground is not None:
        if not _same_ground_record(parent, ground):
            return None, None
    return validated, parent


def _same_ground_record(left, right):
    """True when two ground records describe the same plane record."""
    if not isinstance(left, dict) or not isinstance(right, dict):
        return False
    try:
        return json.dumps(left, sort_keys=True, separators=(",", ":"),
                          allow_nan=False) == \
            json.dumps(right, sort_keys=True, separators=(",", ":"),
                      allow_nan=False)
    except (TypeError, ValueError):
        return False


def _coordinate_ground_projection(ground_derived, calibration):
    """Project a validated ground-derived R/t into the additive wire form.

    Returns a fresh dict with newly built R/t lists so no caller can mutate the
    cached artifact (or another snapshot's output) through the published
    coordinate block; None when there is no validated block, so a legacy/absent
    artifact never fabricates an identity transform.

    The shared GL-02 validator already guarantees a finite 3x3 R and triple t,
    and accepts list or tuple containers alike (both carry the same JSON/GDID),
    so no second container-schema gate is applied here: the validated values are
    rebuilt into fresh lists.
    """
    if not isinstance(ground_derived, dict):
        return None
    rotation = ground_derived.get("R")
    translation = ground_derived.get("t")
    if rotation is None or translation is None:
        return None
    artifact = calibration if isinstance(calibration, dict) else {}
    return {
        "kind": "coordinate_ground",
        "schema_version": 1,
        "from_frame": ground_derived.get("from_frame"),
        "to_frame": ground_derived.get("to_frame"),
        "units": "m",
        "calibration_id": artifact.get("calibration_id"),
        "geometry_schema_version": artifact.get("schema_version"),
        "ground_derived_id": ground_derived.get("ground_derived_id"),
        "R": [list(row) for row in rotation],
        "t": [float(value) for value in translation],
    }


def _candidate_geometry(cluster, indices, resolved, basis, ground, reference, derived):
    features = _point_features(cluster, basis, ground, resolved, indices)
    features.update(_reference_block(features, reference))
    features.update(_ground_geometry_block(cluster, derived))
    features.pop('_points', None)
    features['semantic'] = 'unknown'
    return features


def rebuild_candidate(points, evidence_indices, settings=None, *, ground=None,
                      calibration=None, transform=None, frame_id="innolidar"):
    """Rebuild every coordinate/feature from explicit local rows in this array.

    No filtering or re-clustering: callers may only pass already accepted rows.
    Session rows must be mapped to this array by the caller, never guessed here.
    """
    p = np.asarray(points, dtype=np.float64)
    ids = np.asarray(evidence_indices)
    if p.ndim != 2 or p.shape[1] != 3 or ids.ndim != 1 or not len(ids):
        raise ValueError('invalid candidate support shape')
    if ids.dtype.kind not in 'iu' or len(np.unique(ids)) != len(ids):
        raise ValueError('invalid candidate support rows')
    if ids.min() < 0 or ids.max() >= len(p) or not np.isfinite(p[ids]).all():
        raise ValueError('candidate support outside finite frame')
    resolved = resolve_settings(settings)
    basis = ground_plane_basis(ground) if ground_frame_eligible(ground, frame_id) else None
    reference, _ = _resolve_reference_transform(calibration, transform, frame_id)
    derived, _ = _validated_ground_derived(calibration, frame_id=frame_id, ground=ground)
    return _candidate_geometry(p[ids], ids, resolved, basis, ground, reference, derived)


def build_snapshot(points, settings=None, *, session_id, time_epoch, snapshot_id,
                   seq=None, stamp_secs=None, stamp_nsecs=None,
                   source_stamp_s=None, frame_id="innolidar", ground=None,
                   calibration=None, transform=None, background=None, note=None,
                   roi=None, timings=None):
    """Build a versioned candidate snapshot from a decoded (N,3) point array.

    The snapshot is self-describing: session/time_epoch/snapshot_id, the raw
    source seq/sec/nsec it came from, frame and coordinate definitions, the
    calibration version, per-candidate geometry and the evidence indices. IDs
    are only unique inside this snapshot and never claim a tracked person.

    ``roi`` is an optional decision from :class:`core.roi.RoiController`; it only
    filters rows after the full-frame stride/distance gates and before denoise, so
    the sampling density and every row index stay unchanged. ``timings`` (a dict)
    receives the mask/stage seconds only when the caller asks for them; with both
    ``roi=None`` and ``timings=None`` the output and the code path are unchanged.
    """
    span = None
    if timings is not None:
        span = _Span(timings, "snapshot_s")
    try:
        return _build_snapshot(points, settings, session_id=session_id,
                               time_epoch=time_epoch, snapshot_id=snapshot_id,
                               seq=seq, stamp_secs=stamp_secs, stamp_nsecs=stamp_nsecs,
                               source_stamp_s=source_stamp_s, frame_id=frame_id,
                               ground=ground, calibration=calibration, transform=transform,
                               background=background, note=note, roi=roi,
                               timings=timings)
    finally:
        if span is not None:
            span.close()


class _Span:
    """Accumulate one named stage into the caller's timings dict."""

    __slots__ = ("timings", "key", "started")

    def __init__(self, timings, key):
        import time
        self.timings, self.key = timings, key
        self.started = time.perf_counter()

    def close(self):
        import time
        self.timings[self.key] = float(self.timings.get(self.key, 0.0)) \
            + (time.perf_counter() - self.started)


def _build_snapshot(points, settings, *, session_id, time_epoch, snapshot_id,
                    seq=None, stamp_secs=None, stamp_nsecs=None,
                    source_stamp_s=None, frame_id="innolidar", ground=None,
                    calibration=None, transform=None, background=None, note=None,
                    roi=None, timings=None):
    from core.roi import resolve_settings as resolve_roi
    from core.roi import roi_mask
    resolved = resolve_settings(settings)
    roi_resolved = resolve_roi(roi.get("settings")) if roi is not None else None
    if timings is not None and roi is not None:
        # The ROI stage is always accounted for, even when this frame falls back
        # to the full view (zero mask cost, no hidden work).
        timings.setdefault("roi_mask_s", 0.0)
    array = np.asarray(points, dtype=np.float64)
    if array.ndim != 2 or array.shape[1] != 3:
        raise ValueError("points must be an (N,3) array")
    finite = np.all(np.isfinite(array), axis=1)
    array = array[finite]
    original_indices = np.nonzero(finite)[0]
    # The original stride is always derived from the full finite frame, never from
    # a ROI-reduced one, so the sampling density cannot change because of the ROI.
    stride = 1
    if len(array) > resolved["max_points"]:
        stride = int(np.ceil(len(array) / resolved["max_points"]))
    roi_before = None
    if roi is not None and roi_resolved is not None \
            and roi_resolved["before_stride"] and roi.get("apply"):
        mask, roi_before = roi_mask(array, roi, ground, frame_id,
                                    settings=roi_resolved, timings=timings)
        array = array[mask]
        original_indices = original_indices[mask]
    if stride > 1:
        array = array[::stride]
        original_indices = original_indices[::stride]

    ranges = np.linalg.norm(array, axis=1) if len(array) else np.zeros(0)
    keep = (ranges >= resolved["range_min_m"]) & (ranges <= resolved["range_max_m"])
    array = array[keep]
    original_indices = original_indices[keep]

    roi_block = None
    if roi is not None and roi_resolved is not None:
        if roi_resolved["before_stride"]:
            mask_diagnostics = roi_before or {}
        elif roi.get("apply"):
            mask, mask_diagnostics = roi_mask(array, roi, ground, frame_id,
                                              settings=roi_resolved, timings=timings)
            array = array[mask]
            original_indices = original_indices[mask]
        else:
            mask_diagnostics = dict(applied=False, reason=roi.get("reason"),
                                    state=roi.get("state"), input_points=int(len(array)),
                                    kept_points=int(len(array)), dropped_points=0,
                                    boundary_shell_points=0,
                                    radius_m=roi.get("radius_m"),
                                    margin_m=roi_resolved["margin_m"],
                                    height_band_m=list(roi_resolved["height_band_m"]),
                                    center_m=roi.get("center_m"),
                                    predicted=bool(roi.get("predicted")))
        roi_block = dict(
            state=roi.get("state"), predicted=bool(roi.get("predicted")),
            center_m=roi.get("center_m"), radius_m=mask_diagnostics.get("radius_m"),
            margin_m=roi_resolved["margin_m"],
            height_band_m=list(roi_resolved["height_band_m"]),
            sigma_m=roi.get("sigma_m"), age_s=roi.get("age_s"),
            before_stride=bool(roi_resolved["before_stride"]),
            applied=bool(mask_diagnostics.get("applied")),
            reason=mask_diagnostics.get("reason"),
            input_points=int(mask_diagnostics.get("input_points", 0)),
            kept_points=int(mask_diagnostics.get("kept_points", 0)),
            dropped_points=int(mask_diagnostics.get("dropped_points", 0)),
            boundary_shell_points=int(mask_diagnostics.get("boundary_shell_points", 0)))

    # Pre-level denoise: it runs before the ground-dependent height gate and
    # before the frozen background so neighbour support never depends on ground
    # validity and never loses points the background is about to remove. Counts
    # below are the points entering/leaving this stage (self included).
    denoise = {"enabled": bool(resolved["denoise_enabled"]),
               "radius_m": None, "min_neighbors": None,
               "input_point_count": int(len(array)),
               "kept_point_count": int(len(array)), "dropped_point_count": 0}
    if resolved["denoise_enabled"] and len(array):
        mask = denoise_mask(array, resolved["denoise_radius_m"],
                            resolved["denoise_min_neighbors"])
        denoise["radius_m"] = resolved["denoise_radius_m"]
        denoise["min_neighbors"] = resolved["denoise_min_neighbors"]
        denoise["kept_point_count"] = int(np.count_nonzero(mask))
        denoise["dropped_point_count"] = int(len(array) - denoise["kept_point_count"])
        array = array[mask]
        original_indices = original_indices[mask]

    # Source-frame guard: a plane fitted in another lidar frame must not filter
    # this frame's points or label them ground-relative, before any height/ground
    # field is computed. Without an eligible plane the output is the explicit
    # uncalibrated/source-only path.
    basis = ground_plane_basis(ground) if ground_frame_eligible(ground, frame_id) \
        else None
    if basis is not None and len(array):
        heights = array @ basis[0] + float(ground["offset_m"])
        keep = (heights >= resolved["height_min_m"]) & (heights <= resolved["height_max_m"])
        array = array[keep]
        original_indices = original_indices[keep]

    if background is not None and len(array):
        fg = foreground_mask(array, background)
        array = array[fg]
        original_indices = original_indices[fg]

    clusters = (spatial_components(array, resolved['cluster_cell_m'])
                if resolved['cluster_mode']=='spatial_3d' else
                _connected_clusters(_horizontal_coords(array, basis),
                                    resolved["cluster_cell_m"])) if len(array) else []

    # GL-02/GL-03 binding: only a strictly validated embedded ground-derived block
    # may drive the ground geometry and the published ``ground_derived_id``.
    ground_derived, _bound_ground = _validated_ground_derived(
        calibration, frame_id=frame_id, ground=ground)
    ground_derived_id = ground_derived.get("ground_derived_id") \
        if isinstance(ground_derived, dict) else None

    # Reference binding: only a transform that matches the actual producing
    # frame, the declared reference label and the artifact-owned record may
    # supply reference coordinates (GL-03 G03/G04/G05). An unusable binding
    # leaves them null rather than mapping with the wrong transform.
    reference, _reference_reason = _resolve_reference_transform(
        calibration, transform, frame_id)

    candidates = []
    rejected_clusters = []
    for members in clusters:
        cluster_points = array[members]
        cluster_indices = original_indices[members]
        # Rejected small components publish rows only; do not compute their PCA
        # and percentiles (most components in a real frame can be small residue).
        if len(members) < resolved["min_cluster_points"]:
            rejected_clusters.append(dict(evidence_indices=cluster_indices.tolist(),
                                          reason='insufficient_points'))
            continue
        features = _candidate_geometry(cluster_points, cluster_indices, resolved,
            basis, ground, reference, ground_derived)
        candidates.append(features)
    candidates.sort(key=lambda item: (round(item["center_source_m"][0], 6),
                                      round(item["center_source_m"][1], 6),
                                      round(item["center_source_m"][2], 6),
                                      item["point_count"]))
    for number, candidate in enumerate(candidates):
        candidate["candidate_id"] = "c{:04d}".format(number)

    # A damaged/non-object parent ``frames`` block was already refused as an
    # unusable reference binding; the coordinate metadata must stay readable
    # (null) instead of raising here (GL-03 G03).
    declared_frames = calibration.get("frames") \
        if isinstance(calibration, dict) else None
    reference_label = declared_frames.get("reference") \
        if isinstance(declared_frames, dict) else None
    coordinate = {
        "source_frame": frame_id,
        "reference_frame": reference_label or None,
        "horizontal_basis": "ground_tangent" if basis is not None else "raw_xy_uncalibrated",
        "ground_relative_available": basis is not None,
        "ground_frame": ground.get("frame") if isinstance(ground, dict) else None,
        "transform_status": reference.get("status") if isinstance(reference, dict) else "unknown",
        "ground_derived_id": ground_derived_id,
        "ground": _coordinate_ground_projection(ground_derived, calibration),
    }
    calibration_block = {
        "calibration_id": (calibration or {}).get("calibration_id"),
        "schema_version": (calibration or {}).get("schema_version"),
        "ground_status": ground.get("status") if isinstance(ground, dict) else "unknown",
        "ground_derived_id": ground_derived_id,
    }
    quality = {
        "ground_valid": basis is not None,
        "background_applied": background is not None,
        "denoise": denoise,
        "candidate_count": len(candidates),
        "input_point_count": int(len(array)),
        "coverage": ground_coverage(array, ground) if len(array) else
        {"available": False, "reason": "no_points", "projected_inside_fraction": None,
         "inside_count": 0, "point_count": 0},
        "reasons": [] if basis is not None else ["ground_unavailable"],
    }
    snapshot = {
        "kind": KIND,
        "schema_version": SCHEMA_VERSION,
        "session_id": session_id,
        "time_epoch": int(time_epoch),
        "snapshot_id": snapshot_id,
        "source": {
            "seq": seq,
            "stamp_secs": stamp_secs,
            "stamp_nsecs": stamp_nsecs,
            "source_stamp_s": None if source_stamp_s is None else float(source_stamp_s),
            "frame_id": frame_id,
        },
        "units": dict(UNITS),
        "coordinate": coordinate,
        "calibration": calibration_block,
        "ground": None if not isinstance(ground, dict) else {
            "status": ground.get("status"), "frame": ground.get("frame"),
            "normal": ground.get("normal"), "offset_m": ground.get("offset_m"),
            "sensor_height_m": ground.get("sensor_height_m"),
            # No trusted support outline is derived here; an auto AABB/trusted
            # ROI is deliberately not promoted to a support polygon (P05).
            "support_polygon": None, "support_polyline": None,
            "support_reason": "no_trusted_support_outline_available",
        },
        "settings": resolved,
        "quality": quality,
        "candidates": candidates,
        "foreground_indices": original_indices.tolist(),
        "rejected_clusters": rejected_clusters,
        "note": note,
    }
    if roi_block is not None:
        snapshot["roi"] = roi_block
    return snapshot


def decode_cloud(msg, min_range_m=0.0):
    """Decode a PointCloud2 message to (N,3) using the existing decoder.

    ROS lives only behind this helper; all other functions are array-pure.
    """
    from sensor_health import _load_xyz_from_cloud
    xyz_from_cloud, calibration_error = _load_xyz_from_cloud()
    if xyz_from_cloud is None:
        raise RuntimeError("human_follow_calibration.xyz_from_cloud is unavailable")
    try:
        return xyz_from_cloud(msg, float(min_range_m))
    except calibration_error as exc:  # type: ignore[misc]
        raise ValueError(str(exc)) from exc


def candidates_from_cloud(msg, settings=None, *, min_range_m=0.0, **context):
    """Decode a PointCloud2 message and build a candidate snapshot."""
    return build_snapshot(decode_cloud(msg, min_range_m), settings, **context)


def validate_snapshot(snapshot):
    """Strict structural validation of a candidate snapshot (finite, no NaN)."""
    if not isinstance(snapshot, dict) or snapshot.get("kind") != KIND:
        raise ValueError("snapshot must be a candidate snapshot object")
    if snapshot.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported snapshot schema_version")
    if not isinstance(snapshot.get("session_id"), str) or not snapshot["session_id"]:
        raise ValueError("snapshot.session_id is required")
    if not isinstance(snapshot.get("snapshot_id"), str) or not snapshot["snapshot_id"]:
        raise ValueError("snapshot.snapshot_id is required")
    seen = set()
    for candidate in snapshot.get("candidates", []):
        candidate_id = candidate.get("candidate_id")
        if not isinstance(candidate_id, str) or not candidate_id:
            raise ValueError("candidate_id is required")
        if candidate_id in seen:
            raise ValueError("duplicate candidate_id in snapshot: " + candidate_id)
        seen.add(candidate_id)
        if candidate.get("semantic") != "unknown":
            raise ValueError("candidates stay semantically unknown until operator confirmation")
        for key in ("center_source_m", "bbox_source_min_m", "bbox_source_max_m"):
            values = candidate.get(key)
            if values is None or len(values) != 3 or not np.all(np.isfinite(values)):
                raise ValueError("candidate." + key + " must be three finite numbers")
        # The ground extension is additive/optional for v1 compatibility: an old
        # candidate that predates it (none of the four keys present) is valid. It
        # is only validated as a complete, self-consistent extension when it
        # appears at all, so a present-but-damaged extension is still refused.
        extension_keys = ("bbox_ground_from", "center_ground_m",
                          "bbox_ground_min_m", "bbox_ground_max_m")
        if any(candidate.get(key) is not None for key in extension_keys):
            source = candidate.get("bbox_ground_from")
            if source not in ("actual_points", "unavailable"):
                raise ValueError(
                    "candidate.bbox_ground_from must be actual_points/unavailable")
            ground_keys = ("center_ground_m", "bbox_ground_min_m",
                           "bbox_ground_max_m")
            if source == "actual_points":
                for key in ground_keys:
                    values = candidate.get(key)
                    if values is None or len(values) != 3 \
                            or not np.all(np.isfinite(values)):
                        raise ValueError(
                            "candidate." + key + " must be three finite numbers")
            else:
                for key in ground_keys:
                    if candidate.get(key) is not None:
                        raise ValueError(
                            "candidate." + key + " must be null when "
                            "bbox_ground_from is unavailable")
    return snapshot

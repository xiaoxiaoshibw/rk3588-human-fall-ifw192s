"""Bounded, track-guided composition of current fragments of one measured target.

Why this exists: a measured person becomes several connected clusters when the
scan loses the skin between limbs (walking, turning, falling). The tracker treats
those as competing candidates and drops the lock, even though every fragment is
still supported by the target's own last measured support. This module scores one
explicit candidate composition against *that previous measured support*; it never
classifies a human and never decides identity on its own.

Contract (see docs/TRACKING_REPAIR_PLAN.md §3):

- Input is only the current frame's real fragment points plus the previous
  measured target support (cells + a bounded point sample). No future frames, no
  predicted points, no operator labels.
- Every fragment group must carry at least one fragment that is supported by the
  target's own previous support: its occupied cells must overlap those support
  cells. Additional fragments may be newly visible surface, but they must be
  chain-connected to that anchor through a short gap; a cluster that merely sits
  near the prediction, or that brings its own separate support, is refused.
- The union must still cover a meaningful part of the previous support while not
  being dominated by never-seen cells, must stay inside a body-sized envelope,
  and must be explained by one rigid motion of the previous support (translation,
  rotation and modest local deformation inside the residual budget).
- A competing candidate that could take the same measurement refuses the
  composition; the caller keeps the ordinary ambiguity instead.
- ICP uses fixed samples and iteration caps. Gap verification visits only the
  supplied current points, with fixed-size distance blocks (no dense N x M).

The result only says "these current fragments are geometrically compatible with
the target's own last measured support". Human semantics stay UNKNOWN.
"""

import math

import numpy as np

DEFAULT_SETTINGS = {
    "enabled": True,
    "cell_m": 0.1,
    "min_fragment_support": 0.05,
    "min_target_coverage": 0.20,
    "max_new_fraction": 0.80,
    "max_rigid_rms_m": 0.16,
    "max_fragment_gap_m": 0.25,
    "max_union_extent_m": 2.5,
    "max_union_height_m": 2.7,
    "min_points": 30,
    "icp_samples": 192,
    "icp_iterations": 12,
    "max_fragments": 6,
    "max_cells": 4096,
}
_POSITIVE = ("cell_m", "max_rigid_rms_m", "max_fragment_gap_m",
             "max_union_extent_m", "max_union_height_m", "min_points", "icp_samples",
             "icp_iterations", "max_fragments", "max_cells")
_FRACTION = ("min_fragment_support", "min_target_coverage", "max_new_fraction")


def resolve_settings(settings=None):
    """Merge and validate composition overrides (unknown keys are refused)."""
    resolved = dict(DEFAULT_SETTINGS)
    for key, value in (settings or {}).items():
        if key not in resolved:
            raise ValueError("unknown composition setting: " + str(key))
        resolved[key] = value
    if not isinstance(resolved["enabled"], bool):
        raise ValueError("composition.enabled must be true or false")
    for key in _POSITIVE:
        resolved[key] = float(resolved[key]) if key not in (
            "icp_samples", "icp_iterations", "max_fragments", "max_cells") else int(resolved[key])
        if not np.isfinite(resolved[key]) or resolved[key] <= 0:
            raise ValueError("composition." + key + " must be positive")
    for key in _FRACTION:
        resolved[key] = float(resolved[key])
        if not 0.0 <= resolved[key] <= 1.0:
            raise ValueError("composition." + key + " must be within [0, 1]")
    return resolved


def support_cells(points, cell_m=0.1, max_cells=4096):
    """Occupied integer cells of real points (bounded, deterministic order)."""
    array = np.asarray(points, dtype=np.float64)
    if array.ndim != 2 or array.shape[1] != 3:
        raise ValueError("support points must be (N,3)")
    if not len(array):
        return set()
    grid = np.floor(array / float(cell_m)).astype(np.int64)
    cells = {tuple(row) for row in grid.tolist()}
    if len(cells) > int(max_cells):
        # Keep the lowest coordinates so the retained subset is a deterministic
        # function of the geometry, never of row order.
        cells = set(sorted(cells)[:int(max_cells)])
    return cells


def sample_points(points, count):
    """Deterministic, row-order-independent sample of a point set.

    Points are canonically sorted by coordinates first, so the same geometry with
    shuffled rows produces the same sample (and therefore the same rigid fit).
    """
    array = np.asarray(points, dtype=np.float64)
    if len(array) == 0:
        return array
    if len(array) > 1:
        order = np.lexsort((array[:, 2], array[:, 1], array[:, 0]))
        array = array[order]
    if len(array) <= count:
        return array
    index = np.linspace(0, len(array) - 1, int(count)).astype(np.int64)
    return array[index]


def rigid_fit(source, target, *, iterations=12, samples=192):
    """Bounded point-to-point ICP; returns RMS residual plus the transform.

    The source is the previous measured support, the target the proposed union.
    Nearest-neighbour correspondences are recomputed each iteration, so a pure
    translation, a rotation about a ground contact and modest local deformation
    are all inside the residual budget; two objects that move independently are
    not.
    """
    src = sample_points(source, samples)
    dst = sample_points(target, samples)
    if len(src) < 3 or len(dst) < 3:
        return {"rms_m": None, "rotation": None, "translation": None,
                "source_samples": int(len(src)), "target_samples": int(len(dst))}
    rotation = np.eye(3)
    translation = np.zeros(3)
    moved = src.copy()
    for _ in range(int(iterations)):
        delta = moved[:, None, :] - dst[None, :, :]
        distance = np.einsum("ijk,ijk->ij", delta, delta)
        pairs = dst[distance.argmin(axis=1)]
        centre_src = moved.mean(axis=0)
        centre_dst = pairs.mean(axis=0)
        covariance = (moved - centre_src).T @ (pairs - centre_dst)
        try:
            u, _, vt = np.linalg.svd(covariance)
        except np.linalg.LinAlgError:  # pragma: no cover - defensive
            return {"rms_m": None, "rotation": None, "translation": None,
                    "source_samples": int(len(src)), "target_samples": int(len(dst))}
        candidate = vt.T @ u.T
        if np.linalg.det(candidate) < 0.0:
            vt[-1] *= -1.0
            candidate = vt.T @ u.T
        # The fit maps the already moved points to their current matches.
        # Compose that increment with the source-to-moved transform.
        increment = centre_dst - candidate @ centre_src
        rotation = candidate @ rotation
        translation = candidate @ translation + increment
        moved = (src @ rotation.T) + translation
    delta = moved[:, None, :] - dst[None, :, :]
    nearest = np.sqrt(np.einsum("ijk,ijk->ij", delta, delta).min(axis=1))
    return {"rms_m": float(np.sqrt(np.mean(nearest ** 2))),
            "rotation": rotation.tolist(), "translation": translation.tolist(),
            "source_samples": int(len(src)), "target_samples": int(len(dst))}


def _spatial_blocks(points):
    """Partition every measured row into tight boxes, without subsampling."""
    pending = [points]
    blocks = []
    while pending:
        part = pending.pop()
        if len(part) <= 64:
            blocks.append(part)
            continue
        axis = int(np.argmax(np.ptp(part, axis=0)))
        middle = len(part) // 2
        order = np.argpartition(part[:, axis], middle)
        pending.extend((part[order[:middle]], part[order[middle:]]))
    return blocks


def _verified_gap(a, b, upper_m):
    """Exact minimum, pruning block pairs with a conservative AABB lower bound.

    A sample minimum is an upper bound, so it can prove an edge exists but
    cannot prove separation. Only refine sample-rejected edges. Memory stays
    bounded at 128 x 128 distances. Large pairs use tight spatial blocks and
    vectorized lower bounds; worst-case work remains quadratic in input size.
    """
    best = float(upper_m) ** 2
    if min(len(a), len(b)) > 128:
        # Source-row blocks can each span the whole object after a row shuffle.
        # Tight spatial boxes make pruning useful without dropping any rows.
        blocks = _spatial_blocks(b)
        lows = np.asarray([block.min(axis=0) for block in blocks])
        highs = np.asarray([block.max(axis=0) for block in blocks])
        for block_a in _spatial_blocks(a):
            low, high = block_a.min(axis=0), block_a.max(axis=0)
            separation = np.maximum(0.0, np.maximum(low - highs, lows - high))
            lower = np.einsum('ij,ij->i', separation, separation)
            # Equal lower/upper bounds already prove this block cannot improve
            # the known sample distance (important for duplicate-point scans).
            for index in np.flatnonzero(lower < best):
                if lower[index] >= best:
                    continue
                delta = block_a[:, None, :] - blocks[index][None, :, :]
                best = min(best, float(np.einsum('ijk,ijk->ij', delta, delta).min()))
        return float(np.sqrt(best))
    blocks = [b[start:start + 128] for start in range(0, len(b), 128)]
    bounds = [(block.min(axis=0), block.max(axis=0)) for block in blocks]
    for start in range(0, len(a), 128):
        block_a = a[start:start + 128]
        low, high = block_a.min(axis=0), block_a.max(axis=0)
        for block_b, (other_low, other_high) in zip(blocks, bounds):
            separation = np.maximum(0.0, np.maximum(low - other_high, other_low - high))
            if float(separation @ separation) > best:
                continue
            delta = block_a[:, None, :] - block_b[None, :, :]
            best = min(best, float(np.einsum('ijk,ijk->ij', delta, delta).min()))
    return float(np.sqrt(best))


def _fragment_gaps(fragments, samples=96, max_gap_m=None):
    """Sample-proven edges; verify separation against all current measured rows."""
    sampled = [sample_points(fragment["points"], samples) for fragment in fragments]
    count = len(sampled)
    gaps = [[0.0] * count for _ in range(count)]
    for first in range(count):
        for second in range(first + 1, count):
            a, b = sampled[first], sampled[second]
            if not len(a) or not len(b):
                gaps[first][second] = gaps[second][first] = float("inf")
                continue
            delta = a[:, None, :] - b[None, :, :]
            distance = float(np.sqrt(np.einsum("ijk,ijk->ij", delta, delta).min()))
            if max_gap_m is not None and distance > max_gap_m:
                distance = _verified_gap(
                    np.asarray(fragments[first]['points'], dtype=np.float64),
                    np.asarray(fragments[second]['points'], dtype=np.float64), distance)
            gaps[first][second] = gaps[second][first] = distance
    return gaps


def _connectivity(gaps, max_gap_m):
    """Chain connectivity of fragments under the maximum allowed gap.

    Returns ``(connected, largest_mst_gap, components)``. ``largest_mst_gap`` is
    the largest edge of the minimum spanning tree over the fragment gaps, so a
    separated cluster always reports the real distance instead of zero. A
    fragment that only touches the union through an implausibly long gap is not
    part of the same observed body, so the caller refuses it instead of swallowing
    it.
    """
    count = len(gaps)
    if count <= 1:
        return True, 0.0, [[0]] if count else []
    inside = {0}
    outside = set(range(1, count))
    largest = 0.0
    while outside:
        best = None
        for first in inside:
            for second in outside:
                distance = gaps[first][second]
                if best is None or distance < best[0]:
                    best = (distance, second)
        largest = max(largest, best[0])
        inside.add(best[1])
        outside.remove(best[1])
    remaining = set(range(count))
    components = []
    while remaining:
        pending = [min(remaining)]
        remaining.remove(pending[0])
        component = []
        while pending:
            node = pending.pop()
            component.append(node)
            for other in sorted(remaining):
                if gaps[node][other] <= max_gap_m:
                    remaining.remove(other)
                    pending.append(other)
        components.append(sorted(component))
    return len(components) == 1, largest, components


def connectivity(fragments, max_gap_m):
    """Bounded pairwise gap graph of the proposed fragments.

    Returns ``dict(gaps, connected, largest_gap_m, components)`` where
    ``components`` are index lists connected by gaps at or below ``max_gap_m``.
    """
    gaps = _fragment_gaps(fragments, max_gap_m=float(max_gap_m))
    connected, largest, components = _connectivity(gaps, float(max_gap_m))
    return {"gaps": gaps, "connected": bool(connected),
            "largest_gap_m": float(largest), "components": components}


def _envelope(union, ground_basis, ground_offset_m):
    span = np.ptp(union, axis=0)
    horizontal = float(max(span[0], span[1]))
    height_p90 = None
    if ground_basis is not None:
        normal, u, v = ground_basis
        projected_u = union @ u
        projected_v = union @ v
        horizontal = float(max(np.percentile(projected_u, 95.0) - np.percentile(projected_u, 5.0),
                               np.percentile(projected_v, 95.0) - np.percentile(projected_v, 5.0)))
        if ground_offset_m is not None:
            height_p90 = float(np.percentile(union @ normal + float(ground_offset_m), 90.0))
    return horizontal, height_p90


def evaluate(prior_points, prior_cells, fragments, *, settings=None, ground_basis=None,
             ground_offset_m=None, predicted_position=None, gate_m=None,
             competitor_positions=None):
    """Score one fragment composition against the previous measured support.

    ``fragments`` are the current clusters that already passed the ordinary
    holding gates; each is ``dict(candidate_id=..., points=(N,3), cells=set)``.
    ``prior_*`` is the target's own last measured support. Returns
    ``dict(accepted, reason, metrics)`` and never mutates its inputs.
    """
    resolved = resolve_settings(settings)
    prior = np.asarray(prior_points, dtype=np.float64).reshape(-1, 3) \
        if prior_points is not None else np.zeros((0, 3))
    prior_cells = set(prior_cells or ())
    metrics = {"fragment_count": len(fragments), "prior_points": int(len(prior)),
               "prior_cells": len(prior_cells)}
    if not resolved["enabled"]:
        return {"accepted": False, "reason": "disabled", "metrics": metrics}
    if len(fragments) < 2:
        return {"accepted": False, "reason": "single_fragment", "metrics": metrics}
    if len(fragments) > resolved["max_fragments"]:
        metrics["fragment_limit"] = resolved["max_fragments"]
        return {"accepted": False, "reason": "too_many_fragments", "metrics": metrics}
    if not len(prior) or not prior_cells:
        return {"accepted": False, "reason": "no_prior_support", "metrics": metrics}
    total_points = 0
    support = []
    union_parts, union_cells = [], set()
    for fragment in fragments:
        points = np.asarray(fragment["points"], dtype=np.float64).reshape(-1, 3)
        cells = set(fragment["cells"])
        if not len(points) or not cells:
            return {"accepted": False, "reason": "fragment_without_points", "metrics": metrics}
        total_points += int(len(points))
        overlap = len(cells & prior_cells)
        ratio = overlap / max(1, len(cells))
        support.append(ratio)
        union_parts.append(points)
        union_cells |= cells
    union = np.vstack(union_parts)
    coverage = len(union_cells & prior_cells) / max(1, len(prior_cells))
    new_fraction = len(union_cells - prior_cells) / max(1, len(union_cells))
    gaps = _fragment_gaps(fragments, max_gap_m=resolved['max_fragment_gap_m'])
    connected, largest_gap, components = _connectivity(gaps, resolved["max_fragment_gap_m"])
    horizontal, height_p90 = _envelope(union, ground_basis, ground_offset_m)
    fit = rigid_fit(prior, union, iterations=resolved["icp_iterations"],
                    samples=resolved["icp_samples"])
    centre = np.median(union, axis=0)
    residual = None if predicted_position is None else float(np.linalg.norm(
        centre - np.asarray(predicted_position, dtype=np.float64)))
    metrics.update(point_count=total_points, fragment_support=[float(value) for value in support],
                   anchor_support=float(max(support)),
                   target_coverage=float(coverage), new_fraction=float(new_fraction),
                   fragment_gap_m=float(largest_gap),
                   fragment_gap_connected=bool(connected),
                   fragment_gap_components=len(components),
                   horizontal_extent_m=float(horizontal),
                   height_p90_m=height_p90, rigid_rms_m=fit["rms_m"],
                   rigid_translation_m=None if fit["translation"] is None else float(
                       np.linalg.norm(fit["translation"])),
                   prediction_residual_m=residual,
                   union_centre_m=[float(value) for value in centre])
    if max(support) < resolved["min_fragment_support"]:
        return {"accepted": False, "reason": "no_supported_fragment",
                "metrics": metrics}
    if total_points < resolved["min_points"]:
        return {"accepted": False, "reason": "insufficient_union_points", "metrics": metrics}
    if coverage < resolved["min_target_coverage"]:
        return {"accepted": False, "reason": "target_coverage_low", "metrics": metrics}
    if new_fraction > resolved["max_new_fraction"]:
        return {"accepted": False, "reason": "unexplained_new_support", "metrics": metrics}
    # Several disconnected components may each have a previous-support anchor.
    # Refuse the proposal as a whole; an anchor does not bridge their gap.
    if not connected:
        return {"accepted": False, "reason": "fragment_gap_exceeded", "metrics": metrics}
    if horizontal > resolved["max_union_extent_m"]:
        return {"accepted": False, "reason": "union_envelope_exceeded", "metrics": metrics}
    if height_p90 is not None and height_p90 > resolved["max_union_height_m"]:
        return {"accepted": False, "reason": "union_envelope_exceeded", "metrics": metrics}
    if fit["rms_m"] is None or fit["rms_m"] > resolved["max_rigid_rms_m"]:
        return {"accepted": False, "reason": "rigid_motion_inconsistent", "metrics": metrics}
    if gate_m is not None and residual is not None and not math.isfinite(residual):
        return {"accepted": False, "reason": "prediction_residual_invalid", "metrics": metrics}
    if gate_m is not None and residual is not None and residual > float(gate_m):
        return {"accepted": False, "reason": "prediction_residual_exceeded", "metrics": metrics}
    for position in competitor_positions or ():
        if position is None:
            continue
        distance = float(np.linalg.norm(np.asarray(position, dtype=np.float64) - centre))
        if gate_m is not None and distance <= float(gate_m):
            metrics["competitor_distance_m"] = distance
            return {"accepted": False, "reason": "competing_support", "metrics": metrics}
    metrics["competitor_distance_m"] = None if not competitor_positions else float(
        min(float(np.linalg.norm(np.asarray(position, dtype=np.float64) - centre))
            for position in competitor_positions if position is not None))
    return {"accepted": True, "reason": "supported_fragment_composition",
            "metrics": metrics}

"""Independent finite-sequence oracle: ALL / NEAR / BEST_ONLY metrics.

An oracle is only over one already-seen finite sequence `W` of refined
witnesses; it never certifies unseen hypotheses. The three metrics are
independent and use the same distinct gate as the frozen constrained path
(>10deg or >0.05 m). Support ties for `best` are kept whole; NEAR examines
*every* pair inside the near-optimal pool `C`, never only best-vs-others.

Statuses (new GL-I05 research contract only; not `ground.status`):
  seen_pairwise_closed      : W non-empty AND ALL holds
  seen_dominant_pool_closed : W non-empty AND NEAR holds AND ALL fails
  unresolved                : W empty OR NEAR fails OR any processing/
                              budget/certificate gap (gaps are separate
                              input, never inferred from W alone)

Distinguishing "all candidates similar" from "proof method too weak" is done
upstream by the bounded prototype; this oracle only states what the same
sequence looks like under the three strict metrics.
"""
import math

import numpy as np


def _angle_deg(a, b):
    value = float(np.clip(float(np.asarray(a, dtype=np.float64)
                                @ np.asarray(b, dtype=np.float64)), -1.0, 1.0))
    return math.degrees(math.acos(value))


def _pairwise_distinct(witnesses, settings):
    """Boolean upper-triangle of distinct pairs, vectorised.

    Same distinct gate (>10deg OR >0.05m) as the frozen production path,
    computed in one shot so the oracle over ~800 witnesses stays cheap.
    """
    n = len(witnesses)
    if n < 2:
        return np.zeros((n, n), dtype=bool)
    normals = np.asarray([w["normal"] for w in witnesses], dtype=np.float64)
    offsets = np.asarray([w["offset_m"] for w in witnesses], dtype=np.float64)
    dots = np.clip(normals @ normals.T, -1.0, 1.0)
    angles = np.degrees(np.arccos(dots))
    offset_gap = np.abs(offsets[:, None] - offsets[None, :])
    distinct = (angles > settings["distinct_normal_deg"]) | (
        offset_gap > settings["distinct_offset_m"])
    return np.triu(distinct, 1)


def _pairs_from_mask(mask):
    positions = np.argwhere(mask)
    return [[int(a), int(b)] for a, b in positions]


def _validate_witness(item, index):
    if not isinstance(item, dict):
        raise ValueError("witness %d must be an object" % index)
    normal = item.get("normal")
    array = np.asarray(normal, dtype=np.float64)
    if array.shape != (3,) or not np.all(np.isfinite(array)):
        raise ValueError("witness %d normal must be finite 3-vector" % index)
    offset = item.get("offset_m")
    if isinstance(offset, bool) or not isinstance(offset, (int, float)) \
            or not math.isfinite(float(offset)):
        raise ValueError("witness %d offset_m must be finite" % index)
    support = item.get("support_count")
    if isinstance(support, bool) or not isinstance(support, int) or support < 0:
        raise ValueError("witness %d support_count must be a non-negative integer" % index)


def oracle(witnesses, settings, gaps=False):
    """Metrics over one finite refined-witness sequence `W`.

    `gaps` is a boolean set by the caller when any qualified hypothesis was
    left unprocessed, any budget was exhausted, or any certificate failed.
    This oracle cannot derive such gaps from `W` alone.
    """
    items = list(witnesses or [])
    for index, item in enumerate(items):
        _validate_witness(item, index)
    distinct_matrix = _pairwise_distinct(items, settings)
    all_pairs_mask = np.triu(np.ones((len(items), len(items)), dtype=bool), 1)
    all_distinct = _pairs_from_mask(distinct_matrix & all_pairs_mask)

    if items:
        best_support = max(item["support_count"] for item in items)
        near = [index for index, item in enumerate(items)
                if item["support_count"]
                >= settings["support_close_ratio"] * best_support]
        top = [index for index, item in enumerate(items)
               if item["support_count"] == best_support]
    else:
        best_support, near, top = None, [], []

    near_mask = np.zeros((len(items), len(items)), dtype=bool)
    for first in near:
        near_mask[first, near] = True
    near_distinct = _pairs_from_mask(distinct_matrix & near_mask & all_pairs_mask)

    best_only_distinct = []
    for anchor in top:
        for other in near:
            if anchor >= other:
                continue
            if distinct_matrix[anchor, other]:
                best_only_distinct.append([anchor, other])
    # A chain break hidden by sorted representatives is visible as a NEAR
    # distinct pair whose endpoints are both similar to the best support
    # witness but not to each other.
    middle_best_swallowed = []
    if top:
        anchor = top[0]
        for first, second in near_distinct:
            lo, hi = min(first, anchor), max(first, anchor)
            lo2, hi2 = min(second, anchor), max(second, anchor)
            if not distinct_matrix[lo, hi] and not distinct_matrix[lo2, hi2]:
                middle_best_swallowed.append([first, second])

    all_holds = not all_distinct
    near_holds = not near_distinct
    if gaps or not items or not near_holds:
        status = "unresolved"
    elif all_holds:
        status = "seen_pairwise_closed"
    else:
        status = "seen_dominant_pool_closed"

    weak_distinct = _pairs_from_mask(distinct_matrix & ~near_mask & all_pairs_mask)
    return {
        "kind": "gli05_sequence_oracle",
        "scope": "same finite seen sequence only; unseen hypotheses not excluded",
        "physical_verified": False,
        "witness_count": len(items),
        "best_support": best_support,
        "top_tie_indices": top,
        "near_pool_indices": near,
        "metrics": {
            "ALL": {"holds": bool(all_holds), "distinct_pairs": all_distinct},
            "NEAR": {"holds": bool(near_holds), "distinct_pairs": near_distinct},
            "BEST_ONLY": {"holds": not best_only_distinct,
                          "distinct_pairs": best_only_distinct,
                          "note": "diagnostic only; never a closure gate"},
            "MIDDLE_BEST_SWALLOWED": {"pairs": middle_best_swallowed},
        },
        "distinct_outside_near_pool": weak_distinct,
        "gaps_input": bool(gaps),
        "status": status,
    }


def _selfcheck():
    settings = {"distinct_normal_deg": 10.0, "distinct_offset_m": 0.05,
                "support_close_ratio": 0.8}
    base = {"normal": [0.0, 0.0, 1.0], "offset_m": 1.0, "support_count": 100}
    # ALL closed.
    assert oracle([base], settings)["status"] == "seen_pairwise_closed"
    # NEAR closed but ALL fails: a weaker witness is distinct.
    weak = {"normal": [0.0, 0.0, 1.0], "offset_m": 1.2, "support_count": 100}
    far = {"normal": [0.0, 0.0, 1.0], "offset_m": 1.0, "support_count": 500}
    weak["support_count"] = 79  # below 0.8*500 = 400 -> not in near pool
    result = oracle([far, weak], settings)
    assert result["status"] == "seen_dominant_pool_closed", result
    assert result["metrics"]["ALL"]["holds"] is False
    assert result["metrics"]["NEAR"]["holds"] is True
    # 0-6-12 deg chain: endpoints distinct, both similar to the middle.
    def plane(deg, support):
        return {"normal": [math.sin(math.radians(deg)), 0.0,
                           math.cos(math.radians(deg))],
                "offset_m": 1.0, "support_count": support}
    middle = plane(6.0, 500)
    left = plane(0.0, 450)
    right = plane(12.0, 450)
    result = oracle([middle, left, right], settings)
    assert result["metrics"]["NEAR"]["holds"] is False
    assert result["status"] == "unresolved"
    # BEST_ONLY would call it closed; recorded as diagnostic only.
    only_best = oracle([middle, left, right], settings)["metrics"]["BEST_ONLY"]
    assert only_best["holds"] is True
    # Gap short-circuits everything.
    assert oracle([base], settings, gaps=True)["status"] == "unresolved"
    # Empty / malformed input.
    assert oracle([], settings)["status"] == "unresolved"
    try:
        oracle([{"normal": [0, 0], "offset_m": 1, "support_count": 1}], settings)
    except ValueError:
        pass
    else:
        raise AssertionError("malformed witness accepted")


if __name__ == "__main__":
    _selfcheck()
    print("oracle_selfcheck PASS")

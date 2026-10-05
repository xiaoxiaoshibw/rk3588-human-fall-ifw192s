"""AGL-A RANSAC 适配器：有界 raw RANSAC（原始三点假设，无 inlier 精修）。

数值语义与冻结 GL-01/工作台一致：固定 seed、``rng.randint(0, N, 3)`` 有放回、
支持数→中位数 tie-break、5 cm 全域支持。支持门不过即 invalid（可携带明确标注
不可应用的 diagnostic 假设），不允许把"预算/支持不足"伪装成有效结果。
"""
import math

import numpy as np

from ..contracts import (REASON_DEGENERATE, REASON_LOW_POINT_COUNT, REASON_RANSAC_INVALID,
                         assemble_estimate, require_domain_config, resolve_estimator_config)
from ..selection import validate_point_domain

ESTIMATOR_ID = "ransac"
MIN_CROSS_NORM = 1e-9


def estimate_ransac(domain, config):
    resolved = resolve_estimator_config(config)
    validate_point_domain(domain)
    require_domain_config(domain, resolved)
    points = domain["source_points"]
    weights = domain["weights"]
    count = len(points)
    iterations = resolved["ransac_iterations"]
    if count < 3:
        return assemble_estimate(ESTIMATOR_ID, domain, resolved,
                                 invalid_reasons=[REASON_LOW_POINT_COUNT],
                                 extra={"hypothesis_count": 0,
                                        "iterations_requested": iterations})
    threshold = resolved["inlier_threshold_m"]
    weight_total = float(weights.sum())
    rng = np.random.RandomState(resolved["seed"] % (2 ** 32))
    best = None
    for _ in range(iterations):
        sample = points[rng.randint(0, count, 3)]
        normal = np.cross(sample[1] - sample[0], sample[2] - sample[0])
        norm = float(np.linalg.norm(normal))
        if norm < MIN_CROSS_NORM:
            continue
        normal = normal / norm
        offset = -float(normal @ sample[0])
        distances = np.abs(points @ normal + offset)
        inside = distances <= threshold
        support = int(np.count_nonzero(inside))
        median = float(np.median(distances))
        if best is None or support > best[0] or (support == best[0] and median < best[1]):
            best = (support, median, normal, offset,
                    float(weights[inside].sum() / weight_total))
    # 每次调用按配置执行完整迭代；hypothesis_count 是实际执行数，便于 runner 审计。
    budget = {"hypothesis_count": int(iterations),
              "iterations_requested": int(iterations),
              "resource_complete": True}
    if best is None:
        return assemble_estimate(ESTIMATOR_ID, domain, resolved,
                                 invalid_reasons=[REASON_DEGENERATE], extra=dict(budget))
    support, median, normal, offset, weighted_fraction = best
    required = max(resolved["min_inliers"],
                   int(math.ceil(resolved["min_inlier_fraction"] * count)))
    if support < required:
        return assemble_estimate(
            ESTIMATOR_ID, domain, resolved,
            invalid_reasons=[REASON_RANSAC_INVALID],
            extra=dict(budget, diagnostic_hypothesis={
                "normal_source": [float(v) for v in normal],
                "offset_source_m": offset,
                "support_count": support,
                "support_fraction": float(support / count),
                "weighted_support_fraction": weighted_fraction,
                "median_distance_m": median,
                "note": "diagnostic only; raw uncanonicalized hypothesis"}))
    return assemble_estimate(ESTIMATOR_ID, domain, resolved, normal=normal, offset=offset,
                             extra=dict(budget))

"""AGL-A SVD 适配器：加权中心化薄 SVD（等权时与 P02/工作台同值）。

与 TLS 属同一正交最小二乘家族（数值自检用途，不构成第二票独立证据）。
"""
import numpy as np

from ..contracts import (REASON_DEGENERATE, REASON_LOW_POINT_COUNT, assemble_estimate,
                         require_domain_config, resolve_estimator_config)
from ..selection import validate_point_domain

ESTIMATOR_ID = "svd"
DEGENERATE_RATIO = 1e-12


def estimate_svd(domain, config):
    resolved = resolve_estimator_config(config)
    validate_point_domain(domain)
    require_domain_config(domain, resolved)
    points = domain["source_points"]
    weights = domain["weights"]
    if len(points) < 3:
        return assemble_estimate(ESTIMATOR_ID, domain, resolved,
                                 invalid_reasons=[REASON_LOW_POINT_COUNT])
    total = float(weights.sum())
    center = (weights[:, None] * points).sum(axis=0) / total
    scaled = np.sqrt(weights)[:, None] * (points - center)
    _, singular, vectors = np.linalg.svd(scaled, full_matrices=False)
    ratio = (float((singular[1] / singular[0]) ** 2)
             if singular[0] > 0.0 and singular[1] > 0.0 else 0.0)
    if singular[0] <= 0.0 or singular[1] <= 0.0 or ratio < DEGENERATE_RATIO:
        return assemble_estimate(ESTIMATOR_ID, domain, resolved,
                                 invalid_reasons=[REASON_DEGENERATE],
                                 extra={"eigenvalue_ratio": ratio})
    normal = vectors[-1]
    offset = -float(normal @ center)
    return assemble_estimate(ESTIMATOR_ID, domain, resolved, normal=normal, offset=offset,
                             extra={"eigenvalue_ratio": ratio})

"""AGL-A TLS 适配器：加权协方差 eigh（等权时与 P02/工作台同值）。

数值有效只表示"可算"；质量接受与门槛属于 GL-B。
"""
import numpy as np

from ..contracts import (REASON_DEGENERATE, REASON_LOW_POINT_COUNT, assemble_estimate,
                         require_domain_config, resolve_estimator_config)
from ..selection import validate_point_domain

ESTIMATOR_ID = "tls"
DEGENERATE_RATIO = 1e-12


def estimate_tls(domain, config):
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
    centered = points - center
    covariance = (centered * weights[:, None]).T @ centered / total
    values, vectors = np.linalg.eigh(covariance)
    ratio = float(values[1] / values[2]) if values[2] > 0.0 else 0.0
    if values[1] <= 0.0 or values[2] <= 0.0 or ratio < DEGENERATE_RATIO:
        return assemble_estimate(ESTIMATOR_ID, domain, resolved,
                                 invalid_reasons=[REASON_DEGENERATE],
                                 extra={"eigenvalue_ratio": ratio})
    normal = vectors[:, 0]
    offset = -float(normal @ center)
    return assemble_estimate(ESTIMATOR_ID, domain, resolved, normal=normal, offset=offset,
                             extra={"eigenvalue_ratio": ratio})

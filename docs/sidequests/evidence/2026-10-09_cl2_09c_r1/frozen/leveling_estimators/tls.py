"""P02 plane_from_tls: equal-weight covariance eigh, full shared domain."""
import numpy as np


def estimate(points):
    center = points.mean(axis=0)
    _, vectors = np.linalg.eigh(np.cov((points - center).T))
    normal = vectors[:, 0]
    return normal, -float(normal @ center)

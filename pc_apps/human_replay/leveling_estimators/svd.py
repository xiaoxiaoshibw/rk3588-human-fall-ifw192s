"""P02 plane_from_svd: centered thin SVD, full shared domain."""
import numpy as np


def estimate(points):
    center = points.mean(axis=0)
    _, _, vectors = np.linalg.svd(points - center, full_matrices=False)
    normal = vectors[-1]
    return normal, -float(normal @ center)

"""P02 raw RANSAC: seed20261001/861/0.05m, no inlier refinement or cap."""
import numpy as np


def estimate(points):
    rng = np.random.RandomState(20261001)
    best_count, best_median, best = -1, float("inf"), None
    for _ in range(861):
        sample = points[rng.randint(0, len(points), 3)]
        normal = np.cross(sample[1] - sample[0], sample[2] - sample[0])
        norm = float(np.linalg.norm(normal))
        if norm < 1e-9:
            continue
        normal = normal / norm
        offset = -float(normal @ sample[0])
        # Same full-domain scoring as P02; einsum avoids repeated BLAS thread startup.
        distances = np.abs(np.einsum("ij,j->i", points, normal) + offset)
        count = int(np.count_nonzero(distances <= .05))
        if count > best_count or (count == best_count and float(np.median(distances)) < best_median):
            best_count, best_median, best = count, float(np.median(distances)), (normal, offset)
    if best is None:
        raise ValueError("RANSAC 无有效三点假设")
    return best

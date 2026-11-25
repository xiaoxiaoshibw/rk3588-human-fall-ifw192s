"""Raw three-point RANSAC, optionally constrained by fit-domain quality only."""
import numpy as np


def estimate(points, candidate_valid=None, selection_report=None):
    rng = np.random.RandomState(20261001)
    best_count, best_median, best = -1, float("inf"), None
    valid_count, valid_median, valid_best = -1, float("inf"), None
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
        if count < best_count and (candidate_valid is None or count < valid_count):
            continue
        median = float(np.median(distances))
        if count > best_count or (count == best_count and median < best_median):
            best_count, best_median, best = count, median, (normal, offset)
        if (candidate_valid is not None
                and (count > valid_count or (count == valid_count and median < valid_median))
                and candidate_valid(normal, offset)):
            valid_count, valid_median, valid_best = count, median, (normal, offset)
    if best is None:
        raise ValueError("RANSAC 无有效三点假设")
    if selection_report is not None:
        selection_report.update(fit_only=True, no_refinement=True,
            raw_support_count=best_count, selected_support_count=valid_count if valid_best is not None else best_count,
            fit_feasible_found=valid_best is not None)
    # No feasible fit hypothesis: keep the original result for explicit downstream
    # rejection and diagnostics. Never search or rank using the held frames.
    return valid_best if valid_best is not None else best

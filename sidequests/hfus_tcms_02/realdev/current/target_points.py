"""Deterministic foreground components, retaining every source row (no largest pick)."""
import numpy as np

from project_fall import body_candidate
from core.lidar_candidates import spatial_components


def components(points, rows, coordinates, cell=0.05):
    points = np.asarray(points, dtype=float).reshape(-1, 3)
    rows = np.asarray(rows, dtype=np.int64)
    groups = spatial_components(points, cell)
    candidates, ledger = [], []
    for index, members in enumerate(groups):
        selected = rows[members].tolist()
        candidate = body_candidate(coordinates.points(points[members]))
        cid = 'c%04d' % index
        ledger.append(dict(candidate_id=cid, source_rows=selected, point_count=len(members),
                           reason='candidate' if candidate else 'insufficient_support'))
        if candidate:
            candidate.update(candidate_id=cid, source_rows=selected, semantic='unknown')
            candidates.append(candidate)
    return candidates, ledger

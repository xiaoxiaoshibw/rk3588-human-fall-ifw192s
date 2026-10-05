"""Full fixed-window voxel contrasts; diagnostics, no calibration/row labels."""
import json
from pathlib import Path

import numpy as np

import check_sessions as original


def run():
    edges = [np.arange(.5, 4.001, .05), np.arange(-1.5, 1.501, .05), np.arange(-.6, 1.001, .05)]
    centers = [(e[1:] + e[:-1]) / 2 for e in edges]
    means = []
    for sid in original.SESSIONS:
        directory = original.ROOT / 'captures/remote' / sid
        meta = json.loads((directory / 'meta.json').read_text())
        raw = np.memmap(directory / 'points.bin', dtype=np.uint8, mode='r')
        xyz = np.ndarray((meta['total_points'], 3), dtype='<f4', buffer=raw, strides=(28, 4))
        hist = np.zeros(tuple(len(e) - 1 for e in edges))
        for frame in meta['frames']:
            lo = frame['offset_points']; hi = lo + frame['count_points']
            pts = xyz[lo:hi].astype(float)
            pts = pts[np.isfinite(pts).all(axis=1) & np.any(pts != 0, axis=1)]
            mapped = np.column_stack((original.C * pts[:, 0] + original.S * pts[:, 2], pts[:, 1],
                                      -original.S * pts[:, 0] + original.C * pts[:, 2] + 1.34))
            hist += np.histogramdd(mapped, bins=edges)[0]
        means.append(hist / len(meta['frames']))
    a, b, c = means
    contrast = b - (a + c) / 2
    # Broad box vicinity fixed before this second diagnostic: not fitted ground.
    vicinity = ((centers[0][:, None, None] >= 1.7) & (centers[0][:, None, None] <= 2.6)
                & (np.abs(centers[1][None, :, None]) <= .6))
    results = {}
    for name, signed in [('gained_in_B', contrast), ('lost_in_B', -contrast)]:
        chosen = vicinity & (signed >= 1.0)
        index = np.argwhere(chosen)
        weights = signed[chosen]
        points = np.array([[centers[axis][row[axis]] for axis in range(3)] for row in index])
        order = np.argsort(weights)[::-1]
        results[name] = {'threshold_points_per_frame': 1.0, 'voxel_count': int(len(index)),
                         'total_positive_contrast_per_frame': float(weights.sum()),
                         'centroid_display_m': np.average(points, axis=0, weights=weights).tolist(),
                         'AC_change_L1_per_frame_selected_voxels': float(np.abs(c - a)[chosen].sum()),
                         'top_12_voxels': [{'center': points[i].tolist(), 'B_minus_AC_mean': float(contrast[tuple(index[i])]),
                                           'A': float(a[tuple(index[i])]), 'B': float(b[tuple(index[i])]),
                                           'C': float(c[tuple(index[i])])} for i in order[:12]]}
    results['centroid_height_difference_m'] = results['gained_in_B']['centroid_display_m'][2] - results['lost_in_B']['centroid_display_m'][2]
    results['qualification'] = 'posthoc_spatial_diagnostic_not_frozen_ground_points'
    with (original.OUT / '02_VOXEL_RESULTS.json').open('x', encoding='utf-8') as f:
        json.dump(results, f, indent=2, allow_nan=False)
    print(json.dumps(results, indent=2))


if __name__ == '__main__':
    run()

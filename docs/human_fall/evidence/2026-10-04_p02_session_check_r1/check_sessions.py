"""Fixed-window ABC diagnostic; never a ground selection/calibration producer."""
import hashlib
import json
import math
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
SESSIONS = ['cap_20261004_202456', 'cap_20261004_203135', 'cap_20261004_203349']
# Predeclared old v11 display ROI; not asserted identical to experimental #3.
ROI = [1.9, 2.4, -0.5, 0.5]
FLOOR_WINDOW = [-0.10, 0.10]
RAISED_WINDOW = [0.15, 0.35]
ANGLE = math.radians(26.0)
C, S = math.cos(ANGLE), math.sin(ANGLE)


def summarize(values):
    return {'mean': float(np.mean(values)), 'median': float(np.median(values)),
            'p5': float(np.percentile(values, 5)), 'p95': float(np.percentile(values, 95)),
            'std': float(np.std(values)), 'min': float(np.min(values)), 'max': float(np.max(values))}


def run():
    results = []
    for sid in SESSIONS:
        directory = ROOT / 'captures' / 'remote' / sid
        meta = json.loads((directory / 'meta.json').read_text(encoding='utf-8'))
        assert meta['point_stride_bytes'] == 28 and meta['sensor']['frame_id'] == 'innolidar'
        raw = np.memmap(directory / 'points.bin', dtype=np.uint8, mode='r')
        assert len(raw) == meta['total_points'] * 28
        xyz = np.ndarray((meta['total_points'], 3), dtype='<f4', buffer=raw, strides=(28, 4))
        frames, histograms, spatial, raised_heights = [], [], [], []
        for ordinal, frame in enumerate(meta['frames']):
            lo = frame['offset_points']; hi = lo + frame['count_points']
            points = xyz[lo:hi].astype(np.float64)
            points = points[np.isfinite(points).all(axis=1) & np.any(points != 0, axis=1)]
            x = C * points[:, 0] + S * points[:, 2]
            y = points[:, 1]
            z = -S * points[:, 0] + C * points[:, 2] + 1.34
            mask = (x >= ROI[0]) & (x <= ROI[1]) & (y >= ROI[2]) & (y <= ROI[3])
            floor = mask & (z >= FLOOR_WINDOW[0]) & (z <= FLOOR_WINDOW[1])
            raised = mask & (z >= RAISED_WINDOW[0]) & (z <= RAISED_WINDOW[1])
            frames.append({'ordinal': ordinal, 'seq': frame['seq'], 'all_roi_count': int(mask.sum()),
                           'floor_window_count': int(floor.sum()), 'raised_window_count': int(raised.sum())})
            histograms.append(np.histogram(z[mask], bins=np.arange(-.5, .61, .01))[0])
            grid = np.histogram2d(x[floor], y[floor], bins=[np.arange(1.9, 2.401, .05), np.arange(-.5, .501, .05)])[0]
            spatial.append(grid)
            raised_heights.extend(z[raised].tolist())
        with (directory / 'points.bin').open('rb') as f:
            sha = hashlib.file_digest(f, 'sha256').hexdigest()
        results.append({'session': sid, 'bin_sha256': sha, 'frame_count': len(frames), 'frames': frames,
                        'all_roi_count': summarize([f['all_roi_count'] for f in frames]),
                        'floor_window_count': summarize([f['floor_window_count'] for f in frames]),
                        'raised_window_count': summarize([f['raised_window_count'] for f in frames]),
                        'mean_height_histogram': np.mean(histograms, axis=0).tolist(),
                        'mean_floor_xy_grid': np.mean(spatial, axis=0).tolist(),
                        'raised_z_summary': summarize(raised_heights) if raised_heights else None})
    a, b, c = results
    delta = np.asarray(a['mean_floor_xy_grid']) - np.asarray(b['mean_floor_xy_grid'])
    weights = np.maximum(delta, 0)
    xc = 1.925 + .05 * np.arange(10); yc = -.475 + .05 * np.arange(20)
    centroid = [float(np.sum(weights * xc[:, None]) / weights.sum()),
                float(np.sum(weights * yc[None, :]) / weights.sum())] if weights.sum() else None
    report = {'kind': 'abc_fixed_window_diagnostic', 'schema': 1, 'source_frame': 'innolidar',
              'display_transform': {'pitch_deg': 26, 'roll_deg': 0, 'tz_m': 1.34,
                                    'status': 'historical_nominal_diagnostic_not_measured'},
              'roi_xy': ROI, 'floor_window_z': FLOOR_WINDOW, 'raised_window_z': RAISED_WINDOW,
              'roi_matches_experimental_3': 'UNKNOWN', 'sessions': results,
              'mean_floor_change_B_minus_A': b['floor_window_count']['mean'] - a['floor_window_count']['mean'],
              'mean_floor_recovery_C_minus_A': c['floor_window_count']['mean'] - a['floor_window_count']['mean'],
              'mean_raised_change_B_minus_A': b['raised_window_count']['mean'] - a['raised_window_count']['mean'],
              'positive_floor_loss_centroid_display_xy_m': centroid,
              'physical_state_label_independently_verified': False,
              'confirmed_ground_point_set_created': False}
    with (OUT / '01_RESULTS.json').open('x', encoding='utf-8') as f:
        json.dump(report, f, indent=2, allow_nan=False)
    print(json.dumps({k: v for k, v in report.items() if k != 'sessions'}, indent=2))
    for result in results:
        print(json.dumps({k: result[k] for k in ['session', 'floor_window_count', 'raised_window_count', 'raised_z_summary']}, indent=2))


if __name__ == '__main__':
    run()

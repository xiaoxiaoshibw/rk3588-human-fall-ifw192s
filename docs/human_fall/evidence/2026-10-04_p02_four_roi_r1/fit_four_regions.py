"""Four frozen ROI union; unchanged estimators; no production calibration."""
import os
os.environ['OPENBLAS_NUM_THREADS'] = '1'
import ast
import hashlib
import json
import math
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
ROI = {1: [1.04, 1.75, -.93, -.45], 2: [1.94, 2.40, -.94, .07],
       3: [1.32, 1.76, -.38, .20], 4: [2.64, 3.31, -.57, .19]}


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def write(name, value):
    with (OUT / name).open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)


def rotation(pitch, roll):
    p, r = math.radians(pitch), math.radians(roll)
    cp, sp, cr, sr = math.cos(p), math.sin(p), math.cos(r), math.sin(r)
    return np.array([[cp, 0, sp], [sr*sp, cr, -sr*cp], [-cr*sp, sr, cr*cp]])


def normalize(n, d, up):
    return (n, d) if n @ up >= 0 else (-n, -d)


def stats(points, n, d):
    z = points @ n + d
    return {'count': len(z), 'rms_m': float(np.sqrt(np.mean(z*z))),
            'p95_m': float(np.percentile(np.abs(z), 95)), 'median_m': float(np.median(z)),
            'support_fraction': float(np.mean(np.abs(z) <= .05))}


def quality(result):
    return 'PASS' if (result['count'] >= 20 and result['rms_m'] <= .03
                      and result['p95_m'] <= .05 and result['support_fraction'] >= .8) else 'FAIL'


def main():
    assert not (OUT / '02_SELECTION.json').exists(), 'immutable outputs already exist'
    baseline = load(OUT / '00_BASELINE.json')
    for name, expected in baseline['sources'].items():
        assert sha(ROOT / name) == expected, 'source changed: ' + name
    old = ROOT / 'docs/human_fall/evidence/2026-10-04_p02_ground_r2'
    selection = load(old / '01_SELECTION.json')
    initial = np.array(selection['display_transform']['matrix_rowmajor'])
    up = initial[2, :3]
    source, rows, codes, regions, ordinals = [], [], [], [], []
    frame_slices, sources = [], []
    offset = 0
    for label, code in [('A', 0), ('C', 2)]:
        directory = ROOT / 'captures/remote' / selection[label]['session']
        for name in ['meta.json', 'points.bin']:
            assert sha(directory / name) == selection['input_sha_check'][str(directory / name)]
        meta = load(directory / 'meta.json')
        raw = np.memmap(directory / 'points.bin', dtype='u1', mode='r')
        assert len(raw) == meta['total_points'] * 28
        xyz = np.ndarray((meta['total_points'], 3), dtype='<f4', buffer=raw, strides=(28, 4))
        for ordinal, frame in enumerate(meta['frames']):
            lo, count = frame['offset_points'], frame['count_points']
            points = xyz[lo:lo+count].astype(np.float64); indices = np.arange(lo, lo+count, dtype=np.int64)
            valid = np.isfinite(points).all(axis=1) & np.any(points != 0, axis=1)
            points, indices = points[valid], indices[valid]
            display = points @ initial[:3, :3].T + initial[:3, 3]
            memberships = np.zeros(len(points), dtype=np.uint8)
            for region, (xl, xh, yl, yh) in ROI.items():
                mask = (display[:, 0] >= xl) & (display[:, 0] <= xh) & (display[:, 1] >= yl) & (display[:, 1] <= yh)
                assert not np.any(memberships[mask]), 'overlapping ROI source rows'
                memberships[mask] = region
            keep = memberships > 0; count = int(keep.sum())
            assert count >= 100
            source.append(points[keep]); rows.append(indices[keep]); regions.append(memberships[keep])
            codes.append(np.full(count, code, dtype=np.uint8)); ordinals.append(np.full(count, ordinal, dtype=np.int16))
            frame_slices.append({'state': label, 'ordinal': ordinal, 'slice': [offset, offset+count]})
            offset += count
        sources.append({'state': label, 'session': selection[label]['session'], 'frames': len(meta['frames']),
                        'meta_sha256': sha(directory/'meta.json'), 'bin_sha256': sha(directory/'points.bin')})
    points, rr, cc, rg, ff = map(np.concatenate, [source, rows, codes, regions, ordinals])
    for code in [0, 2]:
        assert len(np.unique(rr[cc == code])) == int((cc == code).sum())
    identity = {'point_count': len(points), 'point_sha256': hashlib.sha256(points.tobytes()).hexdigest(),
                'source_identity_order': 'A frames then C frames; within frame original rows; disjoint ROI membership',
                'row_sha256': hashlib.sha256(rr.tobytes()).hexdigest(), 'source': sources, 'roi_bounds_display': ROI,
                'roi_counts': {str(r): int((rg == r).sum()) for r in ROI},
                'selection': '2cm XY interior; finite/nonzero; full heights; no residual/Z gates; B excluded',
                'weights': 'each raw point equal; not region equal weighting', 'physical_verified': False}
    write('02_SELECTION.json', identity)
    with (OUT / '02_FROZEN_POINTS.npz').open('xb') as stream:
        np.savez_compressed(stream, source=points, source_rows=rr, session_code=cc, region_code=rg, frame_ordinal=ff)
    # Reuse the three reviewed pure functions without running the old script's output assertions/main.
    tree = ast.parse((old/'p02_same_domain_estimators.py').read_text(encoding='utf-8'))
    names = {'plane_from_ransac', 'plane_from_tls', 'plane_from_svd'}
    definitions = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
    assert len(definitions) == 3
    namespace = {'np': np, 'math': math, 'RANSAC_SEED': 20261001, 'RANSAC_ITERS': 861, 'INLIER_THRESHOLD_M': .05}
    exec(compile(ast.Module(body=definitions, type_ignores=[]), 'reused_three_estimators', 'exec'), namespace)
    estimators = {}
    for name in ['tls', 'svd', 'ransac']:
        fitted = namespace['plane_from_' + name](points)
        n, d = normalize(fitted[0], fitted[1], up)
        pitch, roll = math.degrees(math.atan2(-n[0], n[2])), math.degrees(math.asin(float(n[1])))
        R = rotation(pitch, roll); t = np.array([0., 0., d]); mapped = points @ R.T + t
        assert abs(np.linalg.det(R)-1) < 1e-12 and np.max(np.abs(R @ n - [0, 0, 1])) < 1e-12
        assert np.max(np.abs(mapped[:, 2] - (points @ n + d))) < 1e-12
        overall = stats(points, n, d)
        per_region = {str(r): stats(points[rg == r], n, d) for r in ROI}
        for result in per_region.values():
            result['quality'] = quality(result)
        estimators[name] = {'normal_source': n.tolist(), 'd_source_m': float(d), 'pitch_deg': pitch, 'roll_deg': roll,
                            'rotation': R.tolist(), 'translation_m': t.tolist(), **overall,
                            'per_region': per_region, 'all_regions_quality': 'PASS' if all(quality(s) == 'PASS' for s in per_region.values()) else 'FAIL'}
        print(name + ': ' + json.dumps({k: estimators[name][k] for k in ['pitch_deg', 'roll_deg', 'd_source_m', 'rms_m', 'p95_m', 'all_regions_quality']}), flush=True)
    pairwise = []
    for a, b in [('tls', 'svd'), ('tls', 'ransac'), ('svd', 'ransac')]:
        n1, n2 = np.array(estimators[a]['normal_source']), np.array(estimators[b]['normal_source'])
        pairwise.append({'estimators': [a, b], 'angle_deg': math.degrees(math.acos(float(np.clip(n1 @ n2, -1, 1)))),
                         'offset_gap_m': abs(estimators[a]['d_source_m'] - estimators[b]['d_source_m'])})
    held = {}
    for region in ROI:
        n, d = normalize(*namespace['plane_from_tls'](points[rg != region]), up)
        result = stats(points[rg == region], n, d); result['quality'] = quality(result)
        held[str(region)] = {'fit_regions': [r for r in ROI if r != region], 'held_region': region, **result}
    spread = []
    for frame in frame_slices:
        lo, hi = frame['slice']; n, d = normalize(*namespace['plane_from_tls'](points[lo:hi]), up)
        spread.append({**frame, 'pitch_deg': math.degrees(math.atan2(-n[0], n[2])),
                       'roll_deg': math.degrees(math.asin(float(n[1]))), 'source_d_m': float(d)})
    report = {'scope': 'four-ROI observed display model; not physical extrinsic', 'identity': identity,
              'estimators': estimators, 'pairwise': pairwise, 'leave_one_region_out': held, 'per_frame_TLS': spread,
              'consensus': 'PASS' if all(p['angle_deg'] <= 2 and p['offset_gap_m'] <= .03 for p in pairwise) else 'FAIL',
              'physical_height_record_m': 1.14, 'physical_verified': False, 'runtime_eligible': False}
    write('03_RESULTS.json', report)
    for label in sources:
        directory = ROOT / 'captures/remote' / label['session']
        assert sha(directory/'meta.json') == label['meta_sha256'] and sha(directory/'points.bin') == label['bin_sha256']
    print('four-ROI points ' + str(len(points)) + '; consensus ' + report['consensus'], flush=True)


if __name__ == '__main__':
    main()

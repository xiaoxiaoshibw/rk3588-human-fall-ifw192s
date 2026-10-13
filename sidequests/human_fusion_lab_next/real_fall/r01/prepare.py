"""Read-only sessions -> existing automatic floor gates -> new offline report."""
import hashlib
import json
from pathlib import Path
import sys
import numpy as np

ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / 'docs/human_fall/evidence/2026-10-13_hf_real_01_r1'
sys.path.insert(0, str(ROOT / 'pc_apps/human_replay'))
from leveling import source, freeze_domain, sha
from floor_roi import detect_floor_regions_v3
from leveling_quality import rotation, compare


def frame_xyz(directory, meta, i):
    raw = np.memmap(directory / 'points.bin', dtype='u1', mode='r')
    xyz = np.ndarray((meta['total_points'], 3), dtype='<f4', buffer=raw, strides=(28, 4))
    f = meta['frames'][i]
    points = xyz[f['offset_points']:f['offset_points']+f['count_points']].astype('f8')
    return points[np.isfinite(points).all(axis=1) & np.any(points != 0, axis=1)]


def prepare(sid):
    directory, meta, binding = source(ROOT/'captures/remote', sid)
    times = [f['bag_time_sec'] for f in meta['frames']]
    if not np.isfinite(times).all() or np.any(np.diff(times) <= 0):
        raise ValueError('non-monotonic source time')
    config = {'pitch_deg': 26., 'roll_deg': 0., 'physical_height_m': 1.14, 'mode': 'auto'}
    excluded = {(len(times)-1)//3, 2*(len(times)-1)//3, len(times)-1}
    points, ids = [], []
    for i in range(len(times)):
        if i in excluded:
            continue
        p = frame_xyz(directory, meta, i)
        points.append(p); ids.append(np.full(len(p), i, dtype='i4'))
    print(sid, 'floor discovery', flush=True)
    detected = detect_floor_regions_v3(np.concatenate(points), np.concatenate(ids), 26., 0.)
    del points, ids
    config.update(regions=detected['regions'], auto_candidate=detected['candidate'])
    p, rows, regions, ordinals, held, invalid, anchor = freeze_domain(directory, meta, config)
    result = compare(p, regions, held, anchor)
    report = {'sid': sid, 'source': binding, 'frames': len(times), 'duration_s': times[-1]-times[0],
              'config': config, 'fit_points': len(p), 'holdout_frames': sorted(excluded),
              'physical_verified': False, 'runtime_eligible': False, **result}
    with (OUT/(sid+'_leveling.json')).open('x', encoding='utf8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2, allow_nan=False)
    assert source(ROOT/'captures/remote', sid)[2] == binding
    print(sid, result['consensus'], result['recommended'], flush=True)


if __name__ == '__main__':
    for sid in sys.argv[1:]:
        try:
            prepare(sid)
        except Exception as exc:
            with (OUT/(sid+'_leveling_failure.json')).open('x', encoding='utf8') as f:
                json.dump({'error': str(exc), 'type': type(exc).__name__}, f, ensure_ascii=False)
            print(sid, 'FAIL', type(exc).__name__, str(exc), flush=True)
            raise

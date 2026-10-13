"""Synthetic known-target demo, reusing the unmodified HF-06 feature/state modules."""
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
sys.path.insert(0, str(ROOT / 'src/human_fall_detection'))
from core.features import FeatureExtractor
from core.fall_state import FallStateMachine


def sequence(kind):
    # ponytail: known synthetic target, not a detector; real segmentation remains separate.
    rng = np.random.default_rng(42)
    template = rng.uniform(-1, 1, (240, 3))
    template[:, 2] -= np.median(template[:, 2])
    sid = 'synthetic_' + kind
    binding = dict(session_id=sid, track_id='DEMO-01', time_epoch=0,
                   action_generation=1, selection_version=1, calibration_version='synthetic-floor')
    baseline = dict(binding, status='ready', baseline_version=1, height_m={'median': 1.15})
    extractor = FeatureExtractor(sid)
    machine = FallStateMachine(sid, {'mode_verified': True, 'allow_confirmed': True})
    rows = []
    for i in range(181):
        t = i / 10
        h = 1.15
        if kind in ('fall', 'lie_fast'):
            h -= .91 * min(1, max(0, (t - 4) / .7))
            h += .91 * min(1, max(0, (t - 12) / 2))
        elif kind == 'sit':
            h -= .60 * min(1, max(0, (t - 4) / 3))
        elif kind == 'low':
            h = .24
        hidden = kind == 'occlusion' and 6 <= t < 9
        low = max(0, min(1, (1.15 - h) / .91))
        pts = template * [.22 + .65 * low, .2, .78 - .64 * low]
        pts += [np.sin(t * .5) * .6 if kind in ('walk', 'occlusion') else .3, 0, h]
        height = float(np.median(pts[:, 2]))
        candidate = {'ground_relative_available': True,
                     'height_m': {'median': height, 'p10': float(np.quantile(pts[:, 2], .1)), 'p90': float(np.quantile(pts[:, 2], .9))},
                     'horizontal_extent_m': {'max': float(np.ptp(pts[:, 0]))},
                     'axis': {'ambiguous': False, 'verticality': 1 - low}, 'point_count': len(pts)}
        obs = dict(binding, source_stamp_s=t, track_status='locked',
                   position_predicted=hidden, candidate=None if hidden else candidate)
        features = extractor.update(obs, baseline)
        state = machine.update(features, obs, baseline)
        rows.append({'frame': i, 't': t, 'points': [] if hidden else np.round(pts, 4).tolist(),
                     'observed': not hidden, 'state': state})
    return rows


def main():
    names = {'fall': '跌倒与恢复', 'walk': '正常行走', 'sit': '缓慢坐下',
             'occlusion': '短时遮挡', 'low': '初始低姿态', 'lie_fast': '快速主动躺下 · 误报反例'}
    data = {'provenance': 'SYNTHETIC_KNOWN_TARGET', 'scenarios': {k: {'name': v, 'rows': sequence(k)} for k, v in names.items()}}
    checks = {}
    for key, scenario in data['scenarios'].items():
        rows = scenario['rows']
        events = [r for r in rows if r['state']['new_event']]
        states = {r['state']['state'] for r in rows}
        checks[key] = {'events': len(events), 'states': sorted(states), 'first_event_s': events[0]['t'] if events else None}
        assert len(events) == (1 if key in ('fall', 'lie_fast') else 0), checks[key]
    assert {'descending', 'suspected', 'confirmed', 'recovering', 'upright'} <= set(checks['fall']['states'])
    assert all(r['state']['state'] == 'unknown' for r in data['scenarios']['occlusion']['rows'] if not r['observed'])
    assert data['scenarios']['fall']['rows'][-1]['state']['state'] == 'upright'
    payload = json.dumps(data, ensure_ascii=False, allow_nan=False, separators=(',', ':')).encode('utf-8')
    with (HERE/'data.json').open('xb') as f:
        f.write(payload)
    sources = [Path(__file__), ROOT/'src/human_fall_detection/core/features.py', ROOT/'src/human_fall_detection/core/fall_state.py', ROOT/'src/human_fall_detection/core/timebase.py']
    manifest = {'data_sha256': hashlib.sha256(payload).hexdigest(), 'sources': {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}, 'checks': checks, 'real_fall_accuracy': 'NOT_RUN'}
    with (HERE/'manifest.json').open('x', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
    print(json.dumps(manifest, ensure_ascii=True))


if __name__ == '__main__':
    main()

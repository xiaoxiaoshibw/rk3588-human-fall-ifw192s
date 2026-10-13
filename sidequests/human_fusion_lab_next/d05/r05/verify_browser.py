"""Check actual displayed frame/time/SHA; exclude loading observations."""
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / 'docs/human_capture/evidence/2026-10-12_hfus_d05_r5'
data = json.loads((OUT / 'BROWSER_OPERATIONS_V2.json').read_text(encoding='utf-8'))
verified = []
pending = []
for row in data['rows']:
    if not row['status'].startswith('SHA_VERIFIED'):
        pending.append(row['label'])
        continue
    frame = int(row['frame'])
    stamp = float(re.search(r't=([0-9.]+)', row['status'])[1])
    meta = json.loads((ROOT / 'captures/remote' / row['sid'] / 'meta.json').read_text(encoding='utf-8'))
    assert stamp == meta['frames'][frame]['bag_time_sec']
    for key in ('rawInfo', 'baseInfo', 'curInfo'):
        assert int(re.search(r'\bf(\d+)\b', row[key])[1]) == frame
        assert float(re.search(r't=([0-9.]+)', row[key])[1]) == stamp
    sha = json.loads(row['sha'])
    assert sha['sid'] == row['sid'] and sha['status'] == 'SHA_VERIFIED'
    assert len(sha['records']) == 3
    verified.append({'label': row['label'], 'sid': row['sid'], 'frame': frame, 'timestamp': stamp, 'variant': row['variant']})
assert len({r['sid'] for r in verified}) == 9 and not data['console']
labels = {r['label'] for r in verified}
assert {'pause_loaded', 'step_forward', 'step_backward', 'timeline_end', 'timeline_mouse_drag_loaded', 'reset_zero', 'frame_keyboard_commit', 'success_jump', 'failure_jump', 'delta_projection_far5'} <= labels
assert next(r for r in data['rows'] if r['label'] == 'play_started')['play'] == '暂停'
result = {'status': 'PASS', 'verified_rows': verified, 'pending_excluded': pending, 'sessions': 9,
          'play_started_button': '暂停', 'console': data['console'],
          'limits': ['nine_near220_control label is f51; actual frame governs', 'pending rows cannot prove alignment', 'GT focus is display only', 'S9 INVALID_BINDING']}
with (OUT / 'BROWSER_VERIFICATION_V2.json').open('x', encoding='utf-8') as f:
    json.dump(result, f, ensure_ascii=False, indent=2)
print(json.dumps({'status': 'PASS', 'rows': len(verified), 'pending': pending, 'sessions': 9}))

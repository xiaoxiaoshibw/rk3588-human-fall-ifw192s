"""Verify every edge clue against source global row and immutable transforms."""
import json
from collections import defaultdict
import numpy as np
from audit import ROOT, OUT, R1, save

edge = json.loads((R1 / 'edge_review.json').read_text('utf8'))
b = json.loads((R1 / 'pass3/binding.json').read_text('utf8'))
s = next(s for s in b['sessions'] if s['sid'].endswith('114340'))
meta = json.loads((ROOT / 'captures/remote' / s['sid'] / 'meta.json').read_text('utf8'))
raw = np.memmap(ROOT / 'captures/remote' / s['sid'] / 'points.bin', dtype='<f4', mode='r').reshape(-1, 7)
tf = json.loads((ROOT / 'docs/human_capture/evidence/2026-10-08_new_static_sessions_r1/leveling' / s['job'] / 'tls/transform.json').read_text('utf8'))
groups = defaultdict(list)
for e in edge['points']:
    groups[e['ordinal']].append(e)
seen = set()
for fi, records in groups.items():
    m = meta['frames'][fi]
    ids = [r['row'] + m['offset_points'] for r in records]
    xyz = raw[ids, :3].astype('float64')
    for matrix, t in [(np.array(tf['R']).ravel(), tf['t']), (s['transform']['rotation_row_major'], s['transform']['translation_m'])]:
        xyz = np.array([matrix[j * 3] * xyz[:, 0] + matrix[j * 3 + 1] * xyz[:, 1] + matrix[j * 3 + 2] * xyz[:, 2] + t[j] for j in range(3)]).T.astype('float32').astype('float64')
    assert np.array_equal(xyz, np.array([r['xyz'] for r in records])), fi
    for r in records:
        assert r['id'] not in seen and r['seq'] == m['seq']; seen.add(r['id'])
save('edge_source_audit.json', {'verified_source_row_xyz': len(seen), 'actual_frames': len(groups),
    'global_row_rule': 'meta.frames[ordinal].offset_points + source row', 'all_labels': 'UNKNOWN, diagnostic only',
    'historical185': 185, 'cleanup_rows': [{k: r[k] for k in ['sid', 'ordinal', 'seq', 'row', 'xyz']} for r in edge['cleanup_roi_points']]})
print('EDGE_SOURCE_PASS', len(seen), 'rows', len(groups), 'frames')

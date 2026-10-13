"""独立struct/标量坐标/中位数审计，不导入节点算法或检测器。"""
import hashlib
import json
import statistics
import struct
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / 'docs/human_capture/evidence/2026-10-12_hr_skeleton_demo_01_r1'
CASES = [('175429', 220), ('175553', 5), ('175943', 162), ('180235', 110), ('180557', 0), ('175227', 40), ('180751', 0)]


def f32(x):
    return struct.unpack('<f', struct.pack('<f', x))[0]


def main():
    records = []
    for short, fi in CASES:
        sid = 'cap_20261010_' + short
        with urllib.request.urlopen('http://127.0.0.1:8927/api/skeleton?sid=%s&f=%d&mode=reference' % (sid, fi), timeout=45) as response:
            body = response.read()
            assert hashlib.sha256(body).hexdigest() == response.headers['X-Content-SHA256']
            p = json.loads(body)
        meta = json.loads((ROOT / 'captures/remote' / sid / 'meta.json').read_text(encoding='utf-8'))['frames'][fi]
        with (ROOT / 'captures/remote' / sid / 'points.bin').open('rb') as stream:
            stream.seek(meta['offset_points'] * 28)
            raw = stream.read(meta['count_points'] * 28)
        assert hashlib.sha256(raw).hexdigest() == p['raw_frame_sha256']
        assert p['timestamp_s'] == meta['bag_time_sec']
        R, T = p['coordinate']['R'], p['coordinate']['T']
        errors = []
        valid_nodes = 0
        for c in p['candidates']:
            members = {}
            for row, received in zip(c['member_rows'], c['points']):
                xyz = struct.unpack_from('<fff', raw, row * 28)
                expected = [f32(sum(R[d * 3 + j] * xyz[j] for j in range(3)) + T[d]) for d in range(3)]
                errors.extend(abs(a - b) for a, b in zip(expected, received))
                members[row] = expected
            for n in c['nodes'].values():
                if not n['valid']:
                    assert n['xyz'] is None and not n['support_rows']
                    continue
                valid_nodes += 1
                assert len(n['support_rows']) == n['support_n']
                assert set(n['support_rows']).issubset(members)
                expected = [statistics.median(members[row][d] for row in n['support_rows']) for d in range(3)]
                errors.extend(abs(a - b) for a, b in zip(expected, n['xyz']))
        max_error = max(errors, default=0)
        assert max_error <= 1e-5
        assert not p['node_ground_truth_available']
        if short in ('175227', '180751'):
            assert not p['candidates']
        records.append({'sid': sid, 'frame': fi, 'input_mode': 'reference', 'pointsets': len(p['candidates']),
                        'supported_nodes': valid_nodes, 'max_coordinate_or_median_error_m': max_error,
                        'input_raw_sha256': p['raw_frame_sha256'], 'annotation_sha256': p['reference_annotation_sha256'],
                        'verdict': 'PASS', 'semantic_accuracy': 'BLOCKED_NO_NODE_GT'})
        print(short, fi, 'POINTSETS', len(p['candidates']), 'NODES', valid_nodes, 'max_error', max_error, flush=True)
    with (OUT / 'INDEPENDENT_REAL_AUDIT.json').open('x', encoding='utf-8') as stream:
        json.dump({'implementation': 'struct scalar f32 transform + statistics.median; no algorithm import', 'cases': records}, stream, ensure_ascii=False, indent=2)


if __name__ == '__main__':
    main()

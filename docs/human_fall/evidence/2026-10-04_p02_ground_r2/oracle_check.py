# -*- coding: utf-8 -*-
"""S01 oracle：独立 struct.unpack 逐点标量复核 + 输入/产物 SHA 首尾一致性。"""
import hashlib
import json
import math
import os
import struct

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, '..', '..', '..', '..'))
INV_PATH = os.path.join(ROOT, 'docs', 'human_fall', 'evidence',
                        '2026-10-04_p02_context_r1', '03_SESSION_INVENTORY.json')

OUT = os.path.join(HERE, '04_ORACLE.json')
assert not os.path.exists(OUT), '04 exists, refuse overwrite'

PITCH_RAD = 26.0 * math.pi / 180.0
CP, SP = math.cos(PITCH_RAD), math.sin(PITCH_RAD)
TZ = 1.340
ROI_FIT = {'X': [1.32, 1.76], 'Y': [-0.38, 0.20]}
SESS = {'A': 'cap_20261004_202456', 'B': 'cap_20261004_203135', 'C': 'cap_20261004_203349'}


def load_json(p):
    with open(p, encoding='utf-8') as f:
        return json.load(f)


def sha256_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for c in iter(lambda: f.read(1 << 20), b''):
            h.update(c)
    return h.hexdigest()


def scalar_count(bin_path, off_points, count):
    """对 frame0 用 struct.unpack 逐点独立解码，统计 ROI_FIT 内点数。"""
    n = 0
    with open(bin_path, 'rb') as f:
        f.seek(off_points * 28)
        for _ in range(count):
            b = f.read(28)
            x_s, y_s, z_s = struct.unpack_from('<fff', b, 0)
            if not all(map(math.isfinite, (x_s, y_s, z_s))) or (x_s == 0.0 and y_s == 0.0 and z_s == 0.0):
                continue
            x = CP * x_s + SP * z_s
            y = y_s
            if ROI_FIT['X'][0] <= x <= ROI_FIT['X'][1] and ROI_FIT['Y'][0] <= y <= ROI_FIT['Y'][1]:
                n += 1
    return n


def numpy_count(bin_path, total_points, off_points, count):
    import numpy as np
    raw = np.memmap(bin_path, dtype=np.uint8, mode='r')
    xyz = np.ndarray((total_points, 3), dtype='<f4', buffer=raw, strides=(28, 4))
    pts = xyz[off_points:off_points + count].astype(np.float64)
    ok = np.isfinite(pts).all(axis=1) & np.any(pts != 0.0, axis=1)
    pts = pts[ok]
    x = CP * pts[:, 0] + SP * pts[:, 2]
    y = pts[:, 1]
    return int(np.count_nonzero((x >= ROI_FIT['X'][0]) & (x <= ROI_FIT['X'][1]) &
                                (y >= ROI_FIT['Y'][0]) & (y <= ROI_FIT['Y'][1])))


def main():
    inv = {s['session']: s for s in load_json(INV_PATH)}
    sel = load_json(os.path.join(HERE, '01_SELECTION.json'))
    scalar = []
    for label in ('A', 'B', 'C'):
        sdir = inv[SESS[label]]['path']
        meta = load_json(os.path.join(sdir, 'meta.json'))
        fr0 = meta['frames'][0]
        bp = os.path.join(sdir, 'points.bin')
        a = scalar_count(bp, fr0['offset_points'], fr0['count_points'])
        b = numpy_count(bp, meta['total_points'], fr0['offset_points'], fr0['count_points'])
        scalar.append({'session': SESS[label], 'ordinal': 0,
                       'scalar_roi_count': a, 'numpy_roi_count': b, 'exact_match': a == b})
        assert a == b, 'scalar/numpy mismatch ' + label

    files = {}
    for name in ('00_BASELINE.json', 'make_baseline.py', 'p02_same_domain_estimators.py',
                 '01_SELECTION.json', '02_ESTIMATORS.json', '03_CANDIDATE.json', 'oracle_check.py'):
        files[name] = sha256_file(os.path.join(HERE, name))
    drift = []
    for label in ('A', 'B', 'C'):
        sdir = inv[SESS[label]]['path']
        for name in ('meta.json', 'points.bin'):
            p = os.path.join(sdir, name)
            if sha256_file(p) != sel['input_sha_check'][p]:
                drift.append(p)
    doc = {
        'scalar_checks': scalar,
        'input_sha_drift': drift,
        'output_file_sha256': files,
        'joint_points_sha256': sel['joint']['points_sha256'],
        'row_index_sha256': sel['joint']['row_index_sha256'],
    }
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump(doc, f, ensure_ascii=False, indent=1)
    print('oracle OK: scalar==numpy for 3 frame0s; input drift =', len(drift))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

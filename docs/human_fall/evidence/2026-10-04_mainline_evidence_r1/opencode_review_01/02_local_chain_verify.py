"""GL-E01 R1 independent local chain verification against the frozen assets.

Consumes the independent remote probe (01_remote_raw_probe.json) and compares it
to the local meta.json / points.bin / adapted NPZ without importing the author
chain scripts. Emits only small summaries.
"""
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
SESSION = ROOT / 'captures/remote/cap_20261002_163621'
META = SESSION / 'meta.json'
BIN = SESSION / 'points.bin'
NPZ = ROOT / 'docs/human_fall/evidence/2026-10-03_gl_i02_r1/08_real/real_candidate.adapted.npz'


def sha_bytes(b):
    return hashlib.sha256(b).hexdigest()


def sha_file(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


def main():
    remote = json.loads((OUT / '01_remote_raw_probe.json').read_text(encoding='utf-8'))
    meta_raw = META.read_bytes()
    meta = json.loads(meta_raw)
    bin_raw = BIN.read_bytes()
    rows = np.frombuffer(bin_raw, dtype=np.uint8)
    assert rows.size % 28 == 0
    rows = rows.reshape(-1, 28)
    xyz = rows[:, 0:12].copy()
    checks = {}
    checks['remote_canonical_equals_local_bin'] = (
        remote['canonical_bin_sha256'] == sha_file(BIN))
    checks['remote_xyz_equals_local_bin_xyz'] = (
        remote['canonical_xyz_sha256'] == sha_bytes(xyz.tobytes()))
    checks['declared_bag_sha_matches_remote'] = (
        meta['extraction']['source_bag_sha256'] == remote['source']['sha256_after'])
    checks['points_total_4372400'] = (
        len(rows) == 4372400 == remote['total_points'] == meta['total_points'])
    pad_mask = np.isin(np.arange(28), [18, 19, 24, 25, 26, 27])
    checks['canonical_pad_bytes_all_zero'] = bool(
        not rows[:, pad_mask].any())

    # Per-frame independent local slice hashes vs remote frame hashes.
    frame_checks = []
    for fr in remote['frames']:
        lo = fr['offset_points']
        hi = lo + fr['count_points']
        sub = rows[lo:hi]
        sub_xyz = sub[:, 0:12]
        frame_checks.append(dict(
            ordinal=fr['ordinal'],
            bytes_match=sha_bytes(sub.tobytes()) == fr['canonical_frame_sha256'],
            xyz_match=sha_bytes(sub_xyz.tobytes()) == fr['xyz_frame_sha256']))

    # Remote frames vs local meta frames (bag_time is round(to_sec,6)).
    meta_frames = meta['frames']
    meta_match = len(meta_frames) == len(remote['frames']) == 89
    if meta_match:
        for m, r in zip(meta_frames, remote['frames']):
            if (int(m['seq']) != r['seq'] or
                    int(m['stamp_sec']) != r['stamp_sec'] or
                    int(m['stamp_nanosec']) != r['stamp_nanosec'] or
                    int(m['count_points']) != r['count_points'] or
                    int(m['offset_points']) != r['offset_points'] or
                    int(m['dropped_points']) != r['dropped_points'] or
                    float(m['bag_time_sec']) != round(float(r['bag_time_sec']), 6)):
                meta_match = False
                break

    # Adapted NPZ: independent parse (not the project loader).
    with np.load(str(NPZ), allow_pickle=False) as z:
        npz_keys = sorted(z.files)
        points = z['points']
        manifest = json.loads(str(z['input_manifest'].reshape(()).item()))
    npz_checks = dict(
        keys=npz_keys,
        points_dtype=str(points.dtype),
        points_shape=list(points.shape),
        points_equal_bin_xyz=bool(
            points.tobytes() == xyz.tobytes() and np.array_equal(points, xyz.view('<f4').reshape(-1, 3))),
        source_bin_sha256=manifest['source']['bin_sha256'],
        source_meta_sha256=manifest['source']['meta_sha256'],
        bin_sha_matches=manifest['source']['bin_sha256'] == sha_file(BIN),
        meta_sha_matches=manifest['source']['meta_sha256'] == sha_bytes(meta_raw),
        declared_bag_sha=manifest['source']['source_bag_sha256_declared'],
        source_bag_hash_verified=manifest['source']['source_bag_hash_verified'],
        physical_verified=manifest['provenance']['physical_verified'],
        npz_frames_match_remote=(
            all(int(a['seq']) == b['seq'] and
                int(a['stamp_sec']) == b['stamp_sec'] and
                int(a['stamp_nanosec']) == b['stamp_nanosec'] and
                int(a['count_points']) == b['count_points'] and
                int(a['offset_points']) == b['offset_points'] and
                float(a['bag_time_sec']) == round(float(b['bag_time_sec']), 6)
                for a, b in zip(manifest['frames'], remote['frames']))
            and len(manifest['frames']) == len(remote['frames'])))

    result = dict(
        kind='gle01_r1_independent_local_chain_verify', schema=1,
        local_bin_sha256=sha_file(BIN), local_bin_size=BIN.stat().st_size,
        local_meta_sha256=sha_bytes(meta_raw), local_npz_sha256=sha_file(NPZ),
        remote_canonical_bin_sha256=remote['canonical_bin_sha256'],
        remote_canonical_xyz_sha256=remote['canonical_xyz_sha256'],
        remote_raw_serialized_data_sha256=remote['raw_serialized_data_sha256'],
        remote_frame_count=remote['frame_count'],
        remote_bag_sha256=remote['source']['sha256_after'],
        checks=checks,
        all_frame_bytes_match=all(f['bytes_match'] for f in frame_checks),
        all_frame_xyz_match=all(f['xyz_match'] for f in frame_checks),
        frames_meta_match=bool(meta_match),
        npz=npz_checks,
        timestamp_raw_range=remote['source_timestamp_raw_range'],
        conclusion='independent local+remote aggregate, per-frame and NPZ source '
                   'identity agree; time units and physics remain unverified')
    assert all(checks.values()), checks
    assert result['all_frame_bytes_match'] and result['all_frame_xyz_match']
    assert meta_match and all(v for k, v in npz_checks.items()
                              if isinstance(v, bool))
    (OUT / '02_local_chain_verify.json').write_text(
        json.dumps(result, indent=2), encoding='utf-8')
    print(json.dumps(dict(
        bin=result['local_bin_sha256'][:16], remote=remote['canonical_bin_sha256'][:16],
        checks=all(checks.values()), frames_ok=result['all_frame_bytes_match'],
        meta_match=bool(meta_match), npz_points=bool(npz_checks['points_equal_bin_xyz']),
        npz_verified_flag=npz_checks['source_bag_hash_verified'],
        ts_range=result['timestamp_raw_range'])))


if __name__ == '__main__':
    main()

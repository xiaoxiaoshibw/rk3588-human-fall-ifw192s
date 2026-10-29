"""Per-frame observation ledger for the public LaserAct person streams (read-only).

Purpose: answer "where exactly is the input lost?" for clips whose falling
actions never form a causal window.  The ledger keeps, for every native frame,
the point count, timestamp and the second-moment geometry of the actor crop,
so that a zero-length frame can be separated from a frame that simply carries
too few points, and so that the last/first observed posture around a gap can be
inspected without re-downloading anything.

Nothing here trains, selects or tunes a model.  Frame labels stay UNKNOWN: the
package only labels whole clips.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import tarfile
import time

import numpy as np

LEDGER_VERSION = 1
# Only these actions keep their raw crop, so that step-2 geometry work has real
# points to look at without a second multi-gigabyte pass.
RAW_ACTIONS = ('Falling',)


def sha256_file(path, chunk=1 << 24):
    digest = hashlib.sha256()
    with open(path, 'rb') as stream:
        while True:
            block = stream.read(chunk)
            if not block:
                break
            digest.update(block)
    return digest.hexdigest()


def decode(raw):
    """Decode one `<sensor>_person.npz` member; layout fixed by the dataset."""
    with np.load(io.BytesIO(raw), allow_pickle=False) as z:
        points, offsets, stamps = z['points'], z['frame_offsets'], z['timestamps_bag']
        keys = sorted(z.keys())
    if (points.ndim != 2 or points.shape[1] != 4 or offsets.dtype.kind not in 'iu' or
            len(offsets) != len(stamps) + 1 or not len(offsets) or offsets[0] != 0 or
            offsets[-1] != len(points) or (np.diff(offsets.astype(np.int64)) < 0).any() or
            stamps.ndim != 1 or not np.isfinite(stamps).all()):
        raise ValueError('invalid person stream layout')
    return points, offsets.astype(np.int64), stamps.astype(np.float64), keys


def frame_shape(xyz):
    """Second-moment description of one actor crop (no orientation assumed)."""
    n = len(xyz)
    if n < 3:
        return None
    centre = xyz.mean(0)
    centred = xyz - centre
    values, vectors = np.linalg.eigh(centred.T @ centred / n)
    order = np.argsort(values)[::-1]
    values, vectors = values[order], vectors[:, order]
    # Sign convention keeps the long axis comparable across frames.
    axis = vectors[:, 0]
    if axis[np.argmax(np.abs(axis))] < 0:
        axis = -axis
    # The vertical span separates one body from a crop that accidentally contains
    # two standing actors: their union is wide *and* still ~1.6 m tall, while a
    # body on the ground is ~0.4-0.5 m thick.
    return {'n': n,
            'centroid': [round(float(v), 5) for v in centre],
            'axis': [round(float(v), 6) for v in axis],
            'eig': [round(float(v), 7) for v in values],
            'zspan': round(float(xyz[:, 2].max() - xyz[:, 2].min()), 4)}


def segments(counts, minimum, max_gap, stamps):
    """Valid-frame runs under the frozen rule: >= minimum points, gaps <= max_gap."""
    good = [i for i, c in enumerate(counts) if c >= minimum]
    runs, current = [], []
    for i in good:
        if current and (i - current[-1] != 1 or stamps[i] - stamps[current[-1]] > max_gap):
            runs.append(current)
            current = []
        current.append(i)
    if current:
        runs.append(current)
    return runs


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--sensor', default='velodyne')
    parser.add_argument('--expected-sha256', default='')
    parser.add_argument('--minimum-points', type=int, default=10)
    parser.add_argument('--max-gap', type=float, default=0.5)
    parser.add_argument('--limit', type=int, default=0)
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=False)
    started, digest = time.time(), None
    if args.expected_sha256:
        digest = sha256_file(args.archive)
        if digest != args.expected_sha256:
            raise ValueError('archive SHA256 mismatch: %s' % digest)

    suffix = '/%s_person.npz' % args.sensor
    raw_dir = args.out / 'RAW'
    raw_dir.mkdir(exist_ok=True)
    entries, written = [], 0
    with tarfile.open(args.archive, 'r:') as tar, \
            (args.out / 'OBSERVATIONS.jsonl').open('w', encoding='utf-8') as ledger:
        for member in tar:
            if not member.isfile() or not member.name.endswith(suffix):
                continue
            session, folder, take = member.name.split('/')[1:4]
            sequence = '%s%s%s' % (session, folder.split('_', 1)[0], take)
            action = folder.split('_', 1)[1]
            with tar.extractfile(member) as stream:
                raw = stream.read()
            points, offsets, stamps, keys = decode(raw)
            counts = np.diff(offsets)
            frames = []
            for i in range(len(stamps)):
                block = points[offsets[i]:offsets[i + 1], :3]
                shape = frame_shape(block) if len(block) >= 3 else None
                frames.append({'f': i, 'n': int(counts[i]), 't': round(float(stamps[i]), 6),
                               'shape': shape})
            runs = segments(counts.tolist(), args.minimum_points, args.max_gap, stamps)
            record = {'sensor': args.sensor, 'sequence': sequence, 'action': action,
                      'member': member.name, 'member_bytes': member.size,
                      'member_sha256': hashlib.sha256(raw).hexdigest(),
                      'frames': int(len(stamps)), 'arrays': keys,
                      'points_total': int(len(points)),
                      'zero_frames': [int(i) for i, c in enumerate(counts) if c == 0],
                      'short_frames': [int(i) for i, c in enumerate(counts)
                                       if 0 < c < args.minimum_points],
                      'valid_runs': runs, 'longest_valid_run': max((len(r) for r in runs), default=0),
                      'window_count': sum(max(0, len(r) - 9) for r in runs),
                      'duration_s': round(float(stamps[-1] - stamps[0]), 6) if len(stamps) else 0.0,
                      'median_dt_s': round(float(np.median(np.diff(stamps))), 6) if len(stamps) > 1 else 0.0,
                      'per_frame': frames}
            ledger.write(json.dumps(record, ensure_ascii=False) + '\n')
            entries.append({k: record[k] for k in
                            ('sequence', 'action', 'frames', 'points_total', 'zero_frames',
                             'short_frames', 'longest_valid_run', 'window_count', 'duration_s',
                             'median_dt_s', 'member_sha256')})
            if action in RAW_ACTIONS:
                np.savez_compressed(raw_dir / (sequence + '.npz'), points=points.astype(np.float32),
                                    frame_offsets=offsets.astype(np.int32), timestamps_bag=stamps)
                written += 1
            if args.limit and len(entries) >= args.limit:
                break
    summary = {'ledger_version': LEDGER_VERSION, 'sensor': args.sensor,
               'archive': str(args.archive), 'archive_sha256': digest,
               'verify_command_sha256': args.expected_sha256 or None,
               'minimum_points': args.minimum_points, 'max_gap_s': args.max_gap,
               'frame_labels': 'UNKNOWN', 'sequences': len(entries),
               'raw_action_subset': list(RAW_ACTIONS), 'raw_sequences_written': written,
               'wall_seconds': round(time.time() - started, 1), 'entries': entries}
    (args.out / 'RUN.json').write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding='utf-8')
    print('ledger sequences', len(entries), 'raw', written, 'in', summary['wall_seconds'], 's')


if __name__ == '__main__':
    main()
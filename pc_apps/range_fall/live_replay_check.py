"""Read-only sessions -> driver-layout PointCloud2 -> live range outputs.

Repackages existing capture rows as 26-byte driver messages (float64 timestamp).
This is an offline transport simulation, never a board/device latency test.
"""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import sys
import threading
import time
from types import SimpleNamespace as NS

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'src/human_fall_detection'))
sys.path.insert(0, str(ROOT/'src/human_fall_detection/scripts'))
from core.capture_input import ROW_DTYPE, sha256_file
from core.range_image import ScanGrid
from core.range_live import LiveRange
from replay_range_frontend import session_meta
from depth import png


def driver_message(rows, info, frame_id):
    names = ('x', 'y', 'z', 'intensity', 'ring', 'timestamp')
    offsets = (0, 4, 8, 12, 16, 18)
    dtype = np.dtype(dict(names=names, formats=('<f4', '<f4', '<f4', '<f4', '<u2', '<f8'),
                         offsets=offsets, itemsize=26))
    raw = np.empty(len(rows), dtype=dtype)
    for name in names:
        raw[name] = rows[name]
    return NS(width=len(rows), height=1, point_step=26, row_step=26*len(rows), is_bigendian=False,
              data=raw.tobytes(), fields=[NS(name=n, offset=o, datatype=t, count=1)
              for n,o,t in zip(names, offsets, (7,7,7,7,4,8))],
              header=NS(seq=info['seq'], frame_id=frame_id,
                        stamp=NS(secs=info['stamp_sec'], nsecs=info['stamp_nanosec'])))


def stats(values):
    return dict(n=len(values), **{name:float(value) for name,value in
                zip(('p50','p95','p99','max'), np.percentile(values, [50,95,99,100]))}) if values else dict(n=0)


def run(session, out, rounds=3, reference=None, paced=False):
    meta, meta_sha = session_meta(session)
    points_sha = sha256_file(session/'points.bin')
    tables = ROOT/'src/inno_lidar_ros/config/ifw192s'
    grid = ScanGrid.from_csv(tables/'ifw192s_azimuth_192x256.csv', tables/'ifw192s_elevation_192x256.csv')
    frame_id = meta['sensor']['frame_id']
    output = out/session.name
    output.mkdir(parents=True, exist_ok=False)
    costs, mismatches, processed, producer_errors = [], [], [], []
    by_identity = {(v['seq'],v['stamp_sec'],v['stamp_nanosec']):i for i,v in enumerate(meta['frames'])}
    if len(by_identity) != len(meta['frames']):
        raise ValueError('ambiguous source header identities')
    def messages():
        with (session/'points.bin').open('rb') as stream:
            for i, info in enumerate(meta['frames']):
                stream.seek(info['offset_points']*28)
                raw = stream.read(info['count_points']*28)
                if len(raw) != info['count_points']*28:
                    raise ValueError('truncated input')
                yield i, raw, driver_message(np.frombuffer(raw, ROW_DTYPE), info, frame_id)
    live = None
    with (output/'frames.jsonl').open('x', encoding='utf-8') as ledger:
        for round_index in range(1 if paced else rounds):
            live = LiveRange(grid, frame_id, max_age_s=.5, preview=True)
            done = threading.Event()
            def produce():
                start = time.perf_counter()
                first = meta['frames'][0]
                base = first['stamp_sec']+first['stamp_nanosec']/1e9
                try:
                    for i, raw, msg in messages():
                        stamp = msg.header.stamp.secs+msg.header.stamp.nsecs/1e9
                        delay = start+stamp-base-time.perf_counter()
                        if delay > 0:
                            time.sleep(delay)
                        live.submit(msg)
                except Exception as exc:
                    producer_errors.append(str(exc))
                finally:
                    done.set()
                    live.queue.wake()
            if paced:
                worker = threading.Thread(target=produce)
                worker.start()
                source = None
            else:
                source = iter(messages())
            while True:
                if paced:
                    live.queue.wait(.1)
                else:
                    item = next(source, None)
                    if item is None: break
                    i, raw, msg = item
                    live.submit(msg)
                result = live.process_latest()
                if result is None:
                    if paced and done.is_set(): break
                    continue
                src = result['source']
                i = by_identity[(src['seq'], src['stamp_sec'], src['stamp_nanosec'])]
                processed.append(i)
                if result['status'] not in ('ready', 'no_valid_pixels'):
                    raise AssertionError(result)
                # Independent offline decode on the exact capture bytes, outside live timers.
                info = meta['frames'][i]
                with (session/'points.bin').open('rb') as stream:
                    stream.seek(info['offset_points']*28)
                    raw = stream.read(info['count_points']*28)
                expected = grid.decode(raw, ('offline-reference',))
                images = result.pop('images')
                shape = grid.shape
                actual_range = np.frombuffer(images['range']['data'], '<f4').reshape(shape)
                actual_rows = np.frombuffer(images['source_rows']['data'], '<i4').reshape(shape)
                actual_valid = np.frombuffer(images['valid']['data'], 'u1').reshape(shape)
                rgb = np.frombuffer(images['preview']['data'], 'u1').reshape(shape+(3,))
                checks = dict(range=np.array_equal(actual_range, expected.range_m[::-1,::-1].astype('<f4'), equal_nan=True),
                              source_rows=np.array_equal(actual_rows, expected.source_rows[::-1,::-1]),
                              valid=np.array_equal(actual_valid, expected.valid[::-1,::-1]*255))
                if reference is not None:
                    checks['historical_preview_bytes'] = png(rgb) == (reference/'depth'/('%06d_preview.png'%i)).read_bytes()
                if not all(checks.values()): mismatches.append(dict(frame=i, round=round_index, checks=checks))
                result.update(frame=i, round=round_index, checks={k:bool(v) for k,v in checks.items()},
                              output_sha256={k:hashlib.sha256(v['data']).hexdigest() for k,v in images.items()})
                ledger.write(json.dumps(result, allow_nan=False)+'\n')
                if i >= 10:
                    costs.append(result)
                if round_index == 0 and i == 105:
                    with (output/'frame105_preview.png').open('xb') as image:
                        image.write(png(rgb))
            if paced:
                worker.join()
    summary = dict(session=session.name, mode='source-paced local simulation' if paced else 'serial',
                   scope='Windows/local CPU; excludes disk read, driver repack, reference checks, ROS serialization/network/render',
                   input_frames=len(meta['frames']), rounds=1 if paced else rounds, processed_frames=len(processed),
                   queue_overwritten=live.queue.dropped, invalid=live.invalid, expired=live.expired,
                   mismatches=mismatches, producer_errors=producer_errors,
                   performance={k:stats([r[k] for r in costs]) for k in
                   ('adapt_ms','decode_ms','image_pack_ms','conversion_ms','queue_age_ms','local_frame_age_ms')},
                   conversion_by_round={str(j):stats([r['conversion_ms'] for r in costs if r['round'] == j])
                                        for j in range(1 if paced else rounds)},
                   warmup_exclusion='first 10 source indices of each round',
                   source=dict(meta_sha256=meta_sha, points_sha256=points_sha, grid_sha256=grid.sha256),
                   environment=dict(platform=platform.platform(), python=platform.python_version(), numpy=np.__version__),
                   board_performance='UNKNOWN', human_fall_effect='UNKNOWN')
    with (output/'SUMMARY.json').open('x', encoding='utf-8') as stream:
        json.dump(summary, stream, ensure_ascii=False, indent=2, allow_nan=False)
    print(json.dumps(summary, ensure_ascii=False))
    if mismatches or producer_errors: raise AssertionError('replay mismatch/producer failure')
    if not paced and len(processed) != len(meta['frames'])*rounds:
        raise AssertionError('incomplete serial replay')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--session', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--reference', type=Path)
    parser.add_argument('--rounds', type=int, default=3)
    parser.add_argument('--paced', action='store_true')
    args = parser.parse_args()
    if args.rounds < 1: parser.error('rounds must be positive')
    run(args.session, args.out, args.rounds, args.reference, args.paced)

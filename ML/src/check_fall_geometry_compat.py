"""Portable stdlib/NumPy geometry parity fixture; no ROS or board connection.

Prepare from an audited raw IFW192S replay on the PC, then check the same
measured target rows under another Python/NumPy runtime. This verifies software
compatibility, never native ARM performance or physical detection effectiveness.
"""
import argparse
import json
import math
from pathlib import Path
import platform
import sys

import numpy as np

from fall_candidate_runtime import file_sha256
from fall_geometry import FallGeometryRuntime

ROOT = Path(__file__).resolve().parents[2]


def dependencies():
    return {name:file_sha256(Path(__file__).with_name(name)) for name in
            ('fall_geometry.py', 'human_pointset.py', 'check_fall_geometry_compat.py')}


def prepare(session, replay, out):
    sys.path.insert(0, str(ROOT/'src/human_fall_detection'))
    from core.capture_input import ROW_DTYPE, POINT_STRIDE_BYTES, read_source_meta, validate_frames
    raw_meta = (session/'meta.json').read_bytes()
    frame_id = json.loads(raw_meta)['sensor']['frame_id']
    meta = read_source_meta(raw_meta, frame_id, 'm')
    frames = validate_frames(meta)
    records = [json.loads(line) for line in (replay/'geometry_frames.jsonl').read_text(encoding='utf-8').splitlines()]
    summary = json.loads((replay/'SUMMARY.json').read_text(encoding='utf-8'))
    if (summary['meta_sha256'] != file_sha256(session/'meta.json') or
            summary['points_sha256'] != file_sha256(session/'points.bin') or
            summary['frames_sha256'] != file_sha256(replay/'geometry_frames.jsonl')):
        raise ValueError('Source session or ledger binding mismatch')
    if len(records) != len(frames):
        raise ValueError('Fixture requires complete replay')
    calibration_path = ROOT/'docs/human_fall/evidence/2026-10-18_hfus_project_dev_r1/leveling_02/TRANSFORM.json'
    if file_sha256(calibration_path) != summary['calibration_sha256']:
        raise ValueError('Ground calibration SHA mismatch')
    calibration = json.loads(calibration_path.read_text(encoding='utf-8'))
    blocks, offsets = [], [0]
    with (session/'points.bin').open('rb') as source:
        for i, record in enumerate(records):
            if record['frame'] != i:
                raise ValueError('Ledger frame ordering mismatch')
            frame = frames[i]
            source.seek(frame['offset_points']*POINT_STRIDE_BYTES)
            raw = source.read(frame['count_points']*POINT_STRIDE_BYTES)
            if len(raw) != frame['count_points']*POINT_STRIDE_BYTES or file_bytes_sha(raw) != record['raw_sha256']:
                raise ValueError('Raw source frame mismatch')
            cloud = np.frombuffer(raw, dtype=ROW_DTYPE)
            rows = np.asarray(record['target_source_rows'], dtype=np.int64)
            if (rows < 0).any() or (rows >= len(cloud)).any() or len(set(rows.tolist())) != len(rows):
                raise ValueError('Invalid target source row')
            points = np.column_stack([cloud[k][rows] for k in ('x','y','z')]).astype(np.float64)
            blocks.append(points); offsets.append(offsets[-1]+len(points))
    out.mkdir(parents=True, exist_ok=False)
    np.savez_compressed(out/'points.npz', points=np.concatenate(blocks), offsets=np.asarray(offsets,dtype=np.int64))
    manifest = dict(schema='fall_geometry_compat_v1', frames=records,
                    normal=calibration['R'][2], offset_m=calibration['t'][2],
                    points_sha256=file_sha256(out/'points.npz'), code_sha256=dependencies(),
                    source_meta_sha256=summary['meta_sha256'], source_points_sha256=summary['points_sha256'],
                    source_ledger_sha256=summary['frames_sha256'],
                    scope='software numeric and state parity only; no person GT or ARM timing')
    (out/'INPUT.json').write_text(json.dumps(manifest,indent=2,allow_nan=False),encoding='utf-8')
    return dict(frames=len(records),points=offsets[-1])


def file_bytes_sha(raw):
    import hashlib
    return hashlib.sha256(raw).hexdigest()


def prepare_depth(replay, out):
    """Also exercise descent, masked orientation and event latch on raw depth."""
    summary = json.loads((replay/'SUMMARY.json').read_text(encoding='utf-8'))
    if summary['source_sha256']['fall_geometry.py'] != dependencies()['fall_geometry.py']:
        raise ValueError('Raw-depth geometry source mismatch')
    if (summary['frames_sha256'] != file_sha256(replay/'FRAMES.jsonl') or
            summary['target_cache_sha256'] != file_sha256(replay/'target_points.npz')):
        raise ValueError('Raw-depth source binding mismatch')
    plane, camera = summary['ground'], summary['protocol']['camera']
    if not plane or plane['status'] != 'valid':
        raise ValueError('Depth fixture needs an explicitly recorded candidate plane')
    before = file_bytes_sha(json.dumps(camera,sort_keys=True).encode())
    after = file_bytes_sha(json.dumps(dict(camera=camera,plane=plane),sort_keys=True).encode())
    records, ready = [], False
    for row in map(json.loads,(replay/'FRAMES.jsonl').read_text(encoding='utf-8').splitlines()):
        if row['timestamp_s'] is not None and row['timestamp_s'] > summary['protocol']['settings']['warmup_s']:
            ready = True
        records.append(dict(timestamp_s=row['timestamp_s'],geometry=row['geometry'],
                            binding=row.get('binding',[summary['sequence'],row['target_generation'],after if ready else before])))
    with np.load(replay/'target_points.npz',allow_pickle=False) as data:
        points, offsets = data['points'], data['frame_offsets']
    out.mkdir(parents=True,exist_ok=False)
    np.savez_compressed(out/'points.npz',points=points,offsets=offsets)
    doc = dict(schema='fall_geometry_compat_v1',frames=records,normal=plane['normal'],offset_m=plane['offset_m'],
               points_sha256=file_sha256(out/'points.npz'),code_sha256=dependencies(),
               source_ledger_sha256=summary['frames_sha256'],
               source_target_cache_sha256=summary['target_cache_sha256'],
               scope='nominal-depth software parity fixture; NOT physical event truth')
    (out/'INPUT.json').write_text(json.dumps(doc,indent=2,allow_nan=False),encoding='utf-8')
    return dict(frames=len(records),points=len(points))


def tuples(value):
    return tuple(tuples(v) for v in value) if isinstance(value,list) else value


def compare(expected, actual, path='output'):
    if isinstance(expected, dict):
        if set(expected) != set(actual):
            raise AssertionError(path+': different keys')
        return max([compare(expected[k],actual[k],path+'.'+k) for k in expected]+[0.])
    if isinstance(expected, list):
        if len(expected) != len(actual):
            raise AssertionError(path+': different list lengths')
        return max([compare(e,a,path) for e,a in zip(expected,actual)]+[0.])
    if isinstance(expected,float):
        error = abs(expected-actual)
        if not math.isfinite(actual) or error > 1e-8+1e-10*abs(expected):
            raise AssertionError(path+': numeric parity failed')
        return error
    if expected != actual:
        raise AssertionError(path+': state/value parity failed')
    return 0.


def check(fixture, output):
    doc = json.loads((fixture/'INPUT.json').read_text(encoding='utf-8'))
    if doc.get('schema') != 'fall_geometry_compat_v1' or doc['code_sha256'] != dependencies():
        raise ValueError('Fixture schema/code mismatch')
    if file_sha256(fixture/'points.npz') != doc['points_sha256']:
        raise ValueError('Fixture point SHA mismatch')
    runtime = FallGeometryRuntime(doc['normal'],doc['offset_m'])
    error, events = 0., 0
    with np.load(fixture/'points.npz',allow_pickle=False) as data:
        points, offsets = data['points'], data['offsets']
    if (points.ndim != 2 or points.shape[1] != 3 or not np.isfinite(points).all() or
            offsets.ndim != 1 or offsets.dtype.kind not in 'iu' or
            len(offsets) != len(doc['frames'])+1 or offsets[0] != 0 or
            offsets[-1] != len(points) or np.any(offsets[1:] < offsets[:-1])):
        raise ValueError('Invalid portable point layout')
    for i,row in enumerate(doc['frames']):
        block = points[offsets[i]:offsets[i+1]]
        result = runtime.push(block,row['timestamp_s'],*tuples(row['binding']),observed=row['geometry']['observed'])
        error = max(error, compare(row['geometry'],result))
        events += result['new_event'] is not None
    result = dict(frames=len(doc['frames']),events=events,maximum_numeric_error=error,
                  control_flow_parity=True,python=platform.python_version(),numpy=np.__version__,
                  machine=platform.machine(),platform=platform.platform(),native_arm_board=False,
                  input_sha256=file_sha256(fixture/'INPUT.json'),code_sha256=dependencies())
    with output.open('x',encoding='utf-8') as stream:json.dump(result,stream,indent=2,allow_nan=False)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command',required=True)
    p = sub.add_parser('prepare');p.add_argument('--session',type=Path,required=True)
    p.add_argument('--replay',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p = sub.add_parser('check');p.add_argument('--fixture',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p = sub.add_parser('prepare-depth');p.add_argument('--replay',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    args = parser.parse_args()
    result = (prepare(args.session,args.replay,args.output) if args.command=='prepare' else
              prepare_depth(args.replay,args.output) if args.command=='prepare-depth' else check(args.fixture,args.output))
    print(json.dumps(result,allow_nan=False))

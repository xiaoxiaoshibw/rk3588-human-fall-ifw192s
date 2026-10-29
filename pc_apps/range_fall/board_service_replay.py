"""Full recorded input -> ROS message stand-in -> resident service; no device IO."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

import numpy as np

from live_replay_check import driver_message, ROOT
from live_tracking_check import wire_message
from core.capture_input import ROW_DTYPE
from core.range_contract import load_ground
from core.range_engine import RangeEngine
from core.range_image import ScanGrid
from core.range_service import RangeService


def run(session, reference, ground, out, diagnostics=False):
    from analysis import AnalysisStore, sha_file
    out = Path(out).resolve()
    if any(out == p.resolve() or p.resolve() in out.parents for p in (ROOT/'data', ROOT/'captures')):
        raise ValueError('evidence must be outside data')
    out.mkdir(parents=True, exist_ok=False)
    paths = [Path(__file__), ROOT/'pc_apps/range_fall/live_tracking_check.py',
             *sorted((ROOT/'src/human_fall_detection/core').rglob('*.py'))]
    pinned = {str(p.relative_to(ROOT)): sha_file(p) for p in paths}
    meta = json.loads((session/'meta.json').read_text('utf8'))
    expected = json.loads(reference.read_text('utf8'))
    AnalysisStore.validate(expected)
    if sha_file(session/'meta.json') != expected['metaSha256'] or sha_file(session/'points.bin') != expected['pointsSha256']:
        raise ValueError('reference input SHA mismatch')
    tables = ROOT/'src/inno_lidar_ros/config/ifw192s'
    grid = ScanGrid.from_csv(tables/'ifw192s_azimuth_192x256.csv', tables/'ifw192s_elevation_192x256.csv')
    identity = expected['sourceBinding']
    plane = load_ground(ground, identity)
    engine = RangeEngine(grid, meta['sensor']['frame_id'], identity, empty_prefix_frames=50, ground=plane, diagnostics=diagnostics)
    service = RangeService(engine, release_id='OFFLINE_ROS_MESSAGE_STANDIN')
    differences, active, costs = [], [], []
    from collections import Counter
    reasons = Counter()
    with (session/'points.bin').open('rb') as stream, (out/'frames.jsonl').open('x', encoding='utf8') as ledger:
        for index, info in enumerate(meta['frames']):
            stream.seek(info['offset_points']*28)
            raw = stream.read(info['count_points']*28)
            msg = driver_message(np.frombuffer(raw, ROW_DTYPE), info, meta['sensor']['frame_id'])
            original = wire_message(msg)
            msg.serialize = lambda f, b=original: f.write(b)
            started = time.monotonic()
            service.submit(msg)
            state = service.process_latest()
            service.process_preview()
            result = service.snapshot()
            bundle, row = result.get('local_range') or {}, expected['frames'][index]
            changed = []
            for key, actual in [('sourceRows', result['target_source_rows']), ('trackId', result['track_id']),
                                ('heightMedianM', bundle.get('heightMedianM')), ('state', result['fall_status'])]:
                if row[key] != actual:
                    changed.append(key)
            if bundle.get('wireSha256') != hashlib.sha256(original).hexdigest():
                changed.append('wireSHA')
            if bundle.get('depth', {}).get('previewSha256') != row['depth']['preview']['sha256']:
                changed.append('previewSHA')
            alert = bundle.get('groundAlert', {})
            if alert.get('active') != row['groundAlert']['active'] or alert.get('triggerFrame') != row['groundAlert']['triggerFrame']:
                changed.append('causalGroundAlert')
            if changed:
                differences.append(dict(frame=index, fields=changed))
            if alert.get('active'):
                active.append(index)
            reasons[result['acquisition']['reason']] += 1
            costs.append((time.monotonic()-started)*1000)
            ledger.write(json.dumps(dict(frame=index, source=result.get('source'), targetCount=len(result['target_source_rows']),
                trackId=result['track_id'], heightMedianM=bundle.get('heightMedianM'), groundAlert=alert,
                fallState=result['fall_status'], wireSha256=bundle.get('wireSha256'),
                targetRowsSha256=hashlib.sha256(json.dumps(result['target_source_rows']).encode()).hexdigest(),
                performance=result.get('performance'), diagnostics=result.get('diagnostics'), differences=changed))+'\n')
    summary = dict(frames=len(meta['frames']), differences=differences, activeFrames=active, reasons=dict(reasons),
        health=service.snapshot()['health'],
        pcServiceLoopMs={k:float(np.percentile(costs,p)) for k,p in [('p50',50),('p95',95),('max',100)]},
        source=dict(meta=expected['metaSha256'], points=expected['pointsSha256']),
        referenceSha256=sha_file(reference), groundSha256=sha_file(ground), sourceSha256=pinned,
        scope='offline recorded data, explicit offline prefix/plane binding; not site ground or board performance',
        body='unavailable on ROS service; PC optional body module is checked separately',
        fallGT='UNKNOWN', confirmedEnabled=False,diagnosticsEnabled=diagnostics)
    if any(sha_file(ROOT/name) != sha for name, sha in pinned.items()):
        raise RuntimeError('source changed during replay')
    (out/'SUMMARY.json').write_text(json.dumps(summary, indent=2), encoding='utf8')
    print(json.dumps({k:v for k,v in summary.items() if k not in ('sourceSha256','activeFrames','differences')}, indent=2))
    if differences:
        raise AssertionError('%d frames differ; inspect frames.jsonl' % len(differences))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('session', 'reference', 'ground', 'out'):
        p.add_argument('--'+name, required=True, type=Path)
    p.add_argument('--diagnostics',action='store_true')
    a = p.parse_args()
    run(a.session, a.reference, a.ground, a.out,a.diagnostics)

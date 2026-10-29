"""Shared RAW-coordinate, source-bound results for the desktop and annotation UI.

Export only a completed, sequence-verified runtime replay. Importing never runs
inference, writes a session, or upgrades a geometric suspicion to a human label.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import struct
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'src/human_fall_detection'))
from core.range_posture import STATES as POSTURE_STATES


def ground_alerts(frames, variant):
    from core.range_ground_alert import GroundAlertObserver, VARIANT, SETTINGS, LIMITATIONS, scan
    if variant != VARIANT:
        raise ValueError('unsupported alert variant')
    observer = GroundAlertObserver()
    states = [observer.update(row)[0] for row in frames]
    intervals = [dict(row, label='sustained_low_posture') for row in scan(frames)['intervals']]
    algorithm = dict(id=VARIANT, settings=SETTINGS, limitations=list(LIMITATIONS),
                     semantic='UNKNOWN', confirmedEnabled=False)
    return states, intervals, algorithm


def all_intervals(frames, alert_rows=()):
    return sorted(suspected_intervals(frames)+list(alert_rows),
                  key=lambda r:(r['startFrame'], r['endFrame'], r['label']))


def sha_file(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def content_sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                    ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def stamp(frame):
    return frame['stamp_sec'] + frame.get('stamp_nanosec', 0) / 1e9


def suspected_intervals(frames):
    intervals = []
    active = None
    previous = None
    for row in frames:
        valid = row['state'] == 'suspected' and row['measured']
        continuous = (previous is not None and row['frameIndex'] == previous['frameIndex'] + 1
                      and row['trackId'] == previous['trackId']
                      and row['generation'] == previous['generation']
                      and 0 < row['stampSec'] - previous['stampSec'] <= .3
                      and not row['observationGap'])
        if not valid or not continuous:
            active = None
        if valid:
            if active is None:
                active = dict(startFrame=row['frameIndex'], endFrame=row['frameIndex'],
                              trackId=row['trackId'], generation=row['generation'], label='suspected_fall')
                intervals.append(active)
            else:
                active['endFrame'] = row['frameIndex']
        previous = row
    return intervals


def export_run(run, session, destination):
    run, session, destination = Path(run), Path(session), Path(destination)
    import sys
    root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(root/'src/human_fall_detection'))
    sys.path.insert(0, str(root/'src/human_fall_detection/scripts'))
    from core.range_image import ScanGrid
    from core.range_contract import binding_tuple
    from core.range_posture import PostureObserver, SETTINGS
    from core.range_skeleton import estimate as skeleton_estimate, project_regions, VERSION as SKELETON_VERSION
    from replay_range_frontend import CALIBRATION
    from depth import export_depth
    config = json.loads((run / 'CONFIG.json').read_text('utf-8'))
    summary = json.loads((run / 'SUMMARY.json').read_text('utf-8'))
    if (summary['software_status'] != 'PASS' or summary['consumed_sequence_differences']
            or summary['differences'] or (run / 'FAILURE.json').exists()):
        raise ValueError('a completed verified runtime is required')
    for name in ('frames.jsonl','RULE_BASELINE.jsonl','SOURCE_ROWS.jsonl'):
        if summary.get('ledger_sha256', {}).get(name) != sha_file(run / name):
            raise ValueError('unsealed or changed runtime ledger: ' + name)
    identity = summary['source_binding']
    if config['source_binding'] != identity or config['config_sha256'] != summary['config_sha256']:
        raise ValueError('runtime binding mismatch')
    for name, expected in config['input_and_source_bindings'].items():
        # view.pin records hashes of present files, and null for absent camera pairs.
        p = Path(name)
        actual = dict(bytes=p.stat().st_size, sha256=sha_file(p)) if p.is_file() else None
        if actual != expected:
            raise ValueError('stale runtime input/source: ' + name)
    meta = json.loads((session / 'meta.json').read_text('utf-8'))
    if (identity['session'] != session.name or sha_file(session / 'meta.json') != identity['meta_sha256']
            or sha_file(session / 'points.bin') != identity['points_sha256']):
        raise ValueError('session does not match runtime')
    records = [json.loads(s) for s in (run / 'frames.jsonl').read_text('utf-8').splitlines()]
    rules = [json.loads(s) for s in (run / 'RULE_BASELINE.jsonl').read_text('utf-8').splitlines()]
    if len(records) != len(rules) or len(records) != summary['processed_frames']:
        raise ValueError('incomplete runtime ledgers')
    frames = []
    export_costs = []
    body_enabled = config.get('body_candidates', False)
    if body_enabled:
        sys.path.insert(0, str(root/'pc_apps/annotator_v2'))
        from body_branches import propose, METHOD, SETTINGS as BODY_SETTINGS
        body_sha = sha_file(root/'pc_apps/annotator_v2/body_branches.py')
    grid = ScanGrid.from_csv(CALIBRATION/'ifw192s_azimuth_192x256.csv', CALIBRATION/'ifw192s_elevation_192x256.csv')
    posture = PostureObserver()
    for name in ('azimuth','elevation'):
        if sha_file(CALIBRATION/('ifw192s_%s_192x256.csv'%name)) != identity[name+'_sha256']:
            raise ValueError('depth calibration mismatch')
    with (session / 'points.bin').open('rb') as stream:
        for record, rule in zip(records, rules):
            export_start = time.perf_counter()
            index = record['frame']
            info = meta['frames'][index]
            if (rule['frame'] != index or rule['source_rows'] != record['target_source_rows']
                    or rule['input_inference_sha256'] != record['inference_sha256']
                    or record['source_binding'] != identity):
                raise ValueError('cross-frame result mismatch')
            stream.seek(info['offset_points'] * 28)
            raw = stream.read(info['count_points'] * 28)
            if hashlib.sha256(raw).hexdigest() != record['raw_sha256']:
                raise ValueError('frame bytes changed')
            rows = record['target_source_rows']
            if len(rows) != len(set(rows)) or any(type(r) is not int or not 0 <= r < info['count_points'] for r in rows):
                raise ValueError('invalid source rows')
            box = None
            if rows:
                points = [struct.unpack_from('<fff', raw, r * 28) for r in rows]
                low = [min(p[c] for p in points) for c in range(3)]
                high = [max(p[c] for p in points) for c in range(3)]
                features = record['target_features']
                if low != features['bbox_min_m'] or high != features['bbox_max_m']:
                    raise ValueError('RAW bbox/source mismatch')
                box = dict(x=(low[0]+high[0])/2, y=(low[1]+high[1])/2,
                           w=high[0]-low[0], h=high[1]-low[1], zMin=low[2], zMax=high[2])
            state = rule['state']
            if state['confirmed_enabled'] or state.get('new_event') is not None or state['state'] == 'confirmed':
                raise ValueError('unverified confirmed result')
            frames.append(dict(frameIndex=index, stampSec=stamp(info), timeSec=record['time_s'],
                generation=record['generation'], trackId=record['target_track_id'],
                measured=bool(rows), sourceRows=rows, rawSha256=record['raw_sha256'], box=box,
                state=state['state'], reasons=state.get('reason_codes') or [],
                targetReason=record['target_reason'], resetReason=record['reset_reason'],
                heightMedianM=rule['features'].get('height_median_m'),
                observationGap=bool(rule['features'].get('observation_gap'))))
            decoded = grid.decode(raw, binding_tuple(identity))
            frames[-1]['posture'] = rule.get('posture') or posture.update(
                rule['features'], record, decoded.binding)
            frames[-1]['skeleton'] = project_regions(skeleton_estimate(points if rows else [], rows), decoded)
            body_start = time.perf_counter()
            if body_enabled:
                indices = decoded.source_rows[::-1, ::-1]
                parts = propose(indices, decoded.xyz, rows)
                used = set()
                for part in parts:
                    pixels = part.get('pixels') or []
                    support = indices.ravel()[pixels].tolist() if pixels else []
                    if (len(support) != len(set(support)) or set(support)-set(rows)
                            or used.intersection(support) or any(r < 0 for r in support)):
                        raise ValueError('body candidate/target source mismatch')
                    used.update(support)
                    part['sourceRows'] = support
                frames[-1]['bodyCandidates'] = dict(method=METHOD, sourceSha256=body_sha,
                    semantic='UNKNOWN', orientation='native_grid_rotated_180_for_view', parts=parts)
            body_ms = (time.perf_counter()-body_start)*1000
            frames[-1]['depth'] = export_depth(decoded, rows, destination.parent, index,
                                                stamp(info), record['raw_sha256'], identity)
            export_costs.append(dict(frame=index, body_ms=body_ms, export_ms=(time.perf_counter()-export_start)*1000))
    result = dict(format='range_fall_analysis', version=1, sessionId=session.name,
        coordinateFrame='sensor-IFW192S-raw', units='m', sourceBinding=identity,
        metaSha256=identity['meta_sha256'], pointsSha256=identity['points_sha256'],
        algorithm=dict(id='range-rules', version='1.1.0',
            configSha256=content_sha(dict(runtime=summary['config_sha256'], posture=SETTINGS))),
        postureAlgorithm=dict(id='range-posture',version='0.1.0',settings=SETTINGS,
            configSha256=content_sha(SETTINGS),calibrationStatus='UNVALIDATED_WITH_HUMAN_GT'),
        skeletonAlgorithm=dict(id='range-region-skeleton',version=SKELETON_VERSION,
            sourceSha256=sha_file(root/'src/human_fall_detection/core/range_skeleton.py'),
            humanJointAccuracy='UNKNOWN'),
        sourceSha256=summary['source_sha256'], sourceFrameCount=len(meta['frames']),
        inputFrames=summary['input_frames'], processedFrames=len(frames),
        droppedFrames=summary['dropped_frames'],
        completeSession=[f['frameIndex'] for f in frames] == list(range(len(meta['frames']))),
        confirmedEnabled=False, semantic='UNKNOWN', frames=frames, intervals=suspected_intervals(frames),
        runtimeLedgerSha256={name:sha_file(run / name) for name in ('frames.jsonl','RULE_BASELINE.jsonl','SUMMARY.json')})
    if config.get('alert_variant') is not None:
        states, intervals, algorithm = ground_alerts(frames, config['alert_variant'])
        for row, alert in zip(frames, states):
            row['groundAlert'] = alert
        result['alertAlgorithm'] = algorithm
        result['intervals'] = all_intervals(frames, intervals)
    if body_enabled:
        result['bodyAlgorithm'] = dict(id=METHOD, sourceSha256=body_sha, settings=BODY_SETTINGS,
                                       semantic='UNKNOWN', computation='precomputed_same_frame')
    if body_enabled or config.get('alert_variant') is not None:
        result['algorithm']['configSha256'] = content_sha(dict(base=result['algorithm']['configSha256'],
            alert=result.get('alertAlgorithm'), body=result.get('bodyAlgorithm')))
    result['contentSha256'] = content_sha(result)
    with destination.open('x', encoding='utf-8') as output:
        json.dump(result, output, ensure_ascii=False, allow_nan=False, separators=(',', ':'))
    with (destination.parent/'EXPORT_TIMINGS.jsonl').open('x', encoding='utf-8') as stream:
        for cost in export_costs:
            stream.write(json.dumps(cost)+'\n')
    return result


class AnalysisStore:
    """Explicitly registered completed artifacts. Requests cannot select disk paths."""
    def __init__(self, paths, data_root):
        self.data_root = Path(data_root)
        self.documents = {}
        self.signatures = {}
        self.roots = {}
        for path in paths:
            doc = json.loads(Path(path).read_text('utf-8'))
            self.validate(doc)
            sid = doc['sessionId']
            if sid in self.documents:
                raise ValueError('duplicate analysis session')
            session = self.data_root / sid
            if sha_file(session / 'meta.json') != doc['metaSha256'] or sha_file(session / 'points.bin') != doc['pointsSha256']:
                raise ValueError('stale analysis source')
            meta = json.loads((session / 'meta.json').read_text('utf-8'))
            if (len(meta['frames']) != doc['sourceFrameCount']
                    or meta.get('point_layout',{}).get('stride_bytes') != 28):
                raise ValueError('analysis frame count mismatch')
            for row in doc['frames']:
                if stamp(meta['frames'][row['frameIndex']]) != row['stampSec']:
                    raise ValueError('analysis frame timestamp mismatch')
            self.documents[sid] = doc
            self.roots[sid] = Path(path).resolve().parent
            self.signatures[sid] = self._signature(sid)

    @staticmethod
    def validate(doc):
        claimed = doc.get('contentSha256')
        if content_sha({k:v for k,v in doc.items() if k != 'contentSha256'}) != claimed:
            raise ValueError('analysis content SHA mismatch')
        sid = doc.get('sessionId', '')
        import re
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', sid):
            raise ValueError('bad analysis session')
        if (doc.get('format') != 'range_fall_analysis' or doc.get('version') != 1
                or doc.get('coordinateFrame') != 'sensor-IFW192S-raw' or doc.get('units') != 'm'
                or doc.get('confirmedEnabled') is not False or doc.get('semantic') != 'UNKNOWN'):
            raise ValueError('unsupported analysis contract')
        seen = set()
        previous = -1
        for row in doc['frames']:
            i = row['frameIndex']
            if type(i) is not int or not previous < i < doc['sourceFrameCount'] or i in seen:
                raise ValueError('invalid analysis frame')
            seen.add(i)
            previous = i
            rows = row['sourceRows']
            if (not isinstance(rows,list) or any(type(r) is not int or r < 0 for r in rows)
                    or len(rows) != len(set(rows)) or type(row['measured']) is not bool
                    or type(row['stampSec']) not in (int,float) or not math.isfinite(row['stampSec'])):
                raise ValueError('invalid source rows/time')
            if row['state'] not in ('unknown','upright','descending','low_posture_unclassified','suspected','recovering'):
                raise ValueError('unsupported fall state')
            if 'posture' in row and (row['posture'].get('state') not in POSTURE_STATES
                    or row['posture'].get('humanSemantic') != 'UNKNOWN' or row['posture'].get('fallEvent') is not False):
                raise ValueError('unsupported posture result')
            if row['measured'] != bool(row['sourceRows']) or (row['box'] is not None) != row['measured']:
                raise ValueError('prediction cannot have measured geometry')
            box = row['box']
            if box is not None and (set(box) != {'x','y','w','h','zMin','zMax'}
                    or not all(type(v) in (float,int) and math.isfinite(v) for v in box.values())
                    or box['w'] < 0 or box['h'] < 0 or box['zMax'] < box['zMin']):
                raise ValueError('invalid box')
        alert_intervals = []
        if 'alertAlgorithm' in doc:
            states, alert_intervals, algorithm = ground_alerts(doc['frames'], doc['alertAlgorithm'].get('id'))
            if algorithm != doc['alertAlgorithm'] or any(r.get('groundAlert') != s for r,s in zip(doc['frames'],states)):
                raise ValueError('ground alert causality/semantics mismatch')
        elif any('groundAlert' in row for row in doc['frames']):
            raise ValueError('ground alert variant required')
        if all_intervals(doc['frames'], alert_intervals) != doc['intervals']:
            raise ValueError('interval continuity mismatch')

    def _signature(self, sid):
        return tuple((p.stat().st_size, p.stat().st_mtime_ns) for p in
                     (self.data_root / sid / 'meta.json', self.data_root / sid / 'points.bin'))

    def frame(self, sid, index):
        doc = self.documents.get(sid)
        if doc is None:
            raise KeyError('no registered analysis for session')
        if self.signatures[sid] != self._signature(sid):
            raise ValueError('source changed; reload and verify analysis')
        row = next((r for r in doc['frames'] if r['frameIndex'] == index), None)
        if row is None:
            raise KeyError('source frame was not processed')
        meta = json.loads((self.data_root / sid / 'meta.json').read_text('utf-8'))
        info = meta['frames'][index]
        with (self.data_root / sid / 'points.bin').open('rb') as stream:
            stream.seek(info['offset_points']*28)
            raw = stream.read(info['count_points']*28)
        if hashlib.sha256(raw).hexdigest() != row['rawSha256']:
            raise ValueError('source frame SHA mismatch')
        rows = row['sourceRows']
        if any(i >= info['count_points'] for i in rows):
            raise ValueError('target source row out of bounds')
        if rows:
            points = [struct.unpack_from('<fff',raw,r*28) for r in rows]
            if any(not math.isfinite(v) for p in points for v in p):
                raise ValueError('nonfinite target')
            low = [min(p[c] for p in points) for c in range(3)]
            high = [max(p[c] for p in points) for c in range(3)]
            expected = dict(x=(low[0]+high[0])/2,y=(low[1]+high[1])/2,w=high[0]-low[0],
                            h=high[1]-low[1],zMin=low[2],zMax=high[2])
            if expected != row['box']:
                raise ValueError('RAW box/source row mismatch')
        manifest = {k:v for k,v in doc.items() if k not in ('frames','intervals')}
        return dict(manifest=manifest, frame=row,
                    intervals=[s for s in doc['intervals'] if s['startFrame'] <= index <= s['endFrame']],
                    allIntervals=doc['intervals'])

    def asset(self, sid, index, kind):
        if kind not in ('preview','metric','mask','metadata'):
            raise KeyError('unknown depth asset')
        packet = self.frame(sid,index)
        row = packet['frame']
        depth = row.get('depth')
        if depth is None:
            raise KeyError('depth not generated for this frame')
        orientation_ok = ((depth.get('version') == 1 and depth.get('orientation') == 'row=ring,column=calibration_native_order')
                          or (depth.get('version') == 2 and depth.get('orientation') == 'native_grid_rotated_180_for_view'
                              and depth.get('nativeTransform') == 'rotate180'))
        if (depth.get('format') != 'lidar_range_image' or not orientation_ok
                or depth.get('width') != 256 or depth.get('height') != 192
                or depth.get('sessionId') != sid or depth.get('frameIndex') != index
                or depth.get('stampSec') != row['stampSec'] or depth.get('rawSha256') != row['rawSha256']
                or depth.get('sourceBinding') != packet['manifest'].get('sourceBinding')
                or depth.get('gridSha256') != packet['manifest'].get('sourceBinding',{}).get('grid_sha256')
                or depth.get('interpolation') is not False
                or depth.get('quantity') != 'radial_range' or depth.get('units') != 'm'
                or depth.get('scaleM') != .001 or depth.get('invalidValue') != 0
                or depth.get('overflowValue') != 65535):
            raise ValueError('depth/source contract mismatch')
        asset = depth[kind]
        relative = Path(asset['path'])
        if relative.is_absolute() or '..' in relative.parts or ':' in str(relative):
            raise ValueError('invalid depth asset path')
        path = (self.roots[sid]/relative).resolve()
        try:
            path.relative_to(self.roots[sid])
        except ValueError:
            raise ValueError('depth asset escaped registered root')
        if path.stat().st_size > 1024*1024:
            raise ValueError('depth asset too large')
        raw = path.read_bytes()
        if len(raw) != asset['bytes'] or hashlib.sha256(raw).hexdigest() != asset['sha256']:
            raise ValueError('depth asset SHA mismatch')
        return raw


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--session', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    result = export_run(args.run, args.session, args.out)
    print(json.dumps(dict(frames=len(result['frames']), completeSession=result['completeSession'],
                          contentSha256=result['contentSha256'])))

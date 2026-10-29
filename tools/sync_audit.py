"""Read-only joint-session audit. LiDAR seconds = video seconds + offset_s.

Run with --session DIR --out NEW.json; optionally --alignment ALIGNMENT.json
and --previous OLD.json. No network, capture, label edits or offset adoption.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import statistics


FILES = ('meta.json', 'points.bin', 'joint.json', 'camera_frames.jsonl', 'camera.mjpeg')
CONVENTION = 'lidar_s = video_s + offset_s'


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False,
                                    separators=(',', ':')).encode('utf8')).hexdigest()


def file_binding(path):
    if not path.exists():
        return None
    before = path.stat()
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    after = path.stat()
    if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
        raise ValueError('input changed while hashing: ' + str(path))
    return dict(bytes=after.st_size, sha256=h.hexdigest())


def number(value, name):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(name + ' must be finite numeric')
    return value


def integer(value, name):
    if type(value) is not int or value < 0:
        raise ValueError(name + ' must be a nonnegative integer')
    return value


def text(value, name):
    if not isinstance(value, str) or not value.strip() or value == 'UNKNOWN':
        raise ValueError(name + ' must name its evidence/source')
    return value


def timing(values):
    """Keep failures in the denominator; never sort a clock into validity."""
    valid = [v for v in values if type(v) in (int, float) and math.isfinite(v)]
    delta = [b - a for a, b in zip(values, values[1:])
             if type(a) in (int, float) and type(b) in (int, float)
             and math.isfinite(a) and math.isfinite(b)]
    positive = [d for d in delta if d > 0]
    return dict(n=len(values), invalid=len(values) - len(valid),
                duplicates=sum(d == 0 for d in delta), regressions=sum(d < 0 for d in delta),
                median_positive_interval_s=statistics.median(positive) if positive else None,
                max_positive_interval_s=max(positive) if positive else None,
                dropped_frames='UNKNOWN')


def alignment_audit(alignment):
    if alignment is None:
        return dict(status='UNKNOWN', reason='no dual-stream anchors or adopted offset',
                    automatic_offset_s=None, adopted_offset_s=None,
                    uncertainty_s=None, drift_s_per_s=None, residuals=[])
    if alignment.get('schema') != 'sync_alignment_v1' or alignment.get('convention') != CONVENTION:
        raise ValueError('alignment schema/convention mismatch')
    for key in ('lidar_clock', 'video_clock'):
        text(alignment.get(key), key)
    anchors = alignment.get('anchors')
    if not isinstance(anchors, list):
        raise ValueError('anchors must be a list')
    ids, physical_ids, raw_pairs, fit, checks, residuals = set(), set(), set(), [], [], []
    adopted = alignment.get('adopted_offset_s')
    if adopted is not None:
        number(adopted, 'adopted_offset_s')
        text(alignment.get('adoption_source'), 'adoption_source')
    uncertainty = alignment.get('uncertainty_s')
    if uncertainty is not None:
        if number(uncertainty, 'uncertainty_s') < 0:
            raise ValueError('negative uncertainty_s')
        text(alignment.get('uncertainty_source'), 'uncertainty_source')
    for anchor in anchors:
        aid = text(anchor.get('id'), 'anchor.id')
        physical = text(anchor.get('physical_event_id'), 'physical_event_id')
        if aid in ids or physical in physical_ids:
            raise ValueError('duplicate anchor or physical event; fit/check must be independent')
        ids.add(aid)
        physical_ids.add(physical)
        role = anchor.get('role')
        if role not in ('fit', 'check'):
            raise ValueError('anchor role must be fit/check')
        lidar = number(anchor.get('lidar_s'), 'lidar_s')
        video = number(anchor.get('video_s'), 'video_s')
        if (lidar, video) in raw_pairs:
            raise ValueError('duplicate raw anchor pair; checks must be independent')
        raw_pairs.add((lidar, video))
        for key in ('lidar_source', 'video_source'):
            text(anchor.get(key), key)
        (fit if role == 'fit' else checks).append((video, lidar))
        residuals.append(dict(id=aid, physical_event_id=physical, role=role,
                              lidar_source=anchor['lidar_source'], video_source=anchor['video_source'],
                              raw_lidar_s=lidar, raw_video_s=video,
                              residual_s=lidar - video - adopted if adopted is not None else None))
    automatic = statistics.median(l - v for v, l in fit) if fit else None
    checked = [r['residual_s'] for r in residuals if r['role'] == 'check'] if adopted is not None else []
    # Two independent checkpoints describe drift only over their own time span.
    ordered = sorted(checks)
    span = ordered[-1][0] - ordered[0][0] if len(ordered) >= 2 else None
    drift = ((ordered[-1][1] - ordered[0][1]) / span - 1
             if span is not None and span > 0 else None)
    complete = adopted is not None and uncertainty is not None and bool(checks)
    return dict(status='RECORDED' if complete else 'UNKNOWN',
                reason='evidence recorded; physical correspondence is not verified' if complete
                else 'missing adopted offset, uncertainty or independent check anchors',
                clocks={k: alignment[k] for k in ('lidar_clock', 'video_clock')},
                automatic_offset_s=automatic, adopted_offset_s=adopted,
                adoption_source=alignment.get('adoption_source'),
                uncertainty_s=uncertainty, uncertainty_source=alignment.get('uncertainty_source'),
                fit_anchor_count=len(fit), check_anchor_count=len(checks),
                max_abs_check_residual_s=max(map(abs, checked)) if checked else None,
                check_residual_exceeds_declared_uncertainty=(
                    max(map(abs, checked)) > uncertainty if checked and uncertainty is not None else None),
                check_video_span_s=span, drift_s_per_s=drift, residuals=residuals)


def session_quality(session, meta):
    frames = meta.get('frames', [])
    if not isinstance(frames, list) or any(not isinstance(f, dict) for f in frames):
        raise ValueError('meta.frames must be a list of objects')
    bag = timing([f.get('bag_time_sec') for f in frames])
    sensor = timing([f['stamp_sec'] + f['stamp_nanosec'] / 1e9
                     if type(f.get('stamp_sec')) is int and type(f.get('stamp_nanosec')) is int
                     and 0 <= f['stamp_nanosec'] < 10**9 else None for f in frames])
    index = session / 'camera_frames.jsonl'
    camera_times, byte_errors, gap_bytes, indexed_bytes = [], [], 0, 0
    previous_end = 0
    if index.exists():
        video = session / 'camera.mjpeg'
        with index.open(encoding='utf-8-sig') as lines:
            # No image decoder/dependency: verify the recorded byte envelope only.
            stream = video.open('rb') if video.exists() else None
            try:
                size = video.stat().st_size if stream else 0
                for i, line in enumerate(lines):
                    row = json.loads(line)
                    stamp = row.get('recv_unix_ns')
                    camera_times.append(stamp / 1e9 if type(stamp) is int else None)
                    start = integer(row.get('offset'), 'camera.offset')
                    length = integer(row.get('length'), 'camera.length')
                    indexed_bytes += length
                    if start != previous_end:
                        byte_errors.append(dict(index=i, reason='noncontiguous_or_overlapping'))
                        gap_bytes += max(0, start - previous_end)
                    previous_end = start + length
                    if not stream or length < 4 or start + length > size:
                        byte_errors.append(dict(index=i, reason='outside_file_or_short'))
                    else:
                        stream.seek(start)
                        head = stream.read(2)
                        stream.seek(start + length - 2)
                        if head != b'\xff\xd8' or stream.read(2) != b'\xff\xd9':
                            byte_errors.append(dict(index=i, reason='invalid_jpeg_envelope'))
                trailing = max(0, size - previous_end)
            finally:
                if stream:
                    stream.close()
    else:
        trailing = None
    return dict(lidar_bag_time=bag, lidar_header_time=sensor,
                declared_time_domain=meta.get('time_domain', 'UNKNOWN'),
                extraction_reported_dropped_frames=meta.get('extraction', {}).get('dropped_frames', 'UNKNOWN'),
                extraction_reported_dropped_points=meta.get('total_dropped_points', 'UNKNOWN'),
                camera_host_receipt_time=timing(camera_times), camera_index_present=index.exists(),
                camera_indexed_bytes=indexed_bytes, camera_gap_bytes=gap_bytes,
                camera_trailing_unindexed_bytes=trailing, camera_byte_errors=byte_errors,
                capture_latency_s='UNKNOWN', physical_sync_error_s='UNKNOWN',
                note='Host receipt/bag times are distinct from sensor exposure/sample clocks.')


def audit(session, alignment_path=None, previous_path=None):
    session = Path(session).resolve()
    paths = {name: session / name for name in FILES}
    if alignment_path:
        paths['alignment'] = Path(alignment_path).resolve()
        if not paths['alignment'].is_file():
            raise ValueError('alignment file missing')
    paths['tool'] = Path(__file__).resolve()
    before = {name: file_binding(path) for name, path in paths.items()}
    meta = read_json(paths['meta.json']) if before['meta.json'] else {}
    alignment = read_json(paths['alignment']) if alignment_path else None
    result = dict(schema='sync_audit_v1', session=meta.get('session_id', session.name),
                  convention=CONVENTION, binding=before, binding_sha256=digest(before),
                  quality=session_quality(session, meta), alignment=alignment_audit(alignment))
    if before != {name: file_binding(path) for name, path in paths.items()}:
        raise ValueError('input changed during audit; result discarded')
    result['missing_files'] = [name for name in FILES if before[name] is None]
    result['status'] = 'INCOMPLETE' if result['missing_files'] else result['alignment']['status']
    if previous_path:
        previous = read_json(previous_path)
        if previous.get('schema') != 'sync_audit_v1' or not isinstance(previous.get('binding'), dict):
            raise ValueError('invalid previous audit')
        old = previous['binding']
        if previous.get('binding_sha256') != digest(old):
            raise ValueError('previous audit binding digest mismatch')
        changed = sorted(k for k in set(old) | set(before) if old.get(k) != before.get(k))
        result['previous_audit'] = dict(status='STALE' if changed else 'UNCHANGED', changed=changed,
                                        binding_sha256=previous['binding_sha256'])
        if changed:
            result['status'] = 'STALE'
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--session', required=True)
    parser.add_argument('--alignment')
    parser.add_argument('--previous')
    parser.add_argument('--out', required=True, help='new sidecar JSON outside raw data')
    args = parser.parse_args()
    out = Path(args.out).resolve()
    root = Path(__file__).resolve().parents[1]
    protected = [Path(args.session).resolve(), root / 'data', root / 'captures']
    if any(p == out or p in out.parents for p in protected):
        parser.error('output must be outside session/data/captures')
    if out.exists():
        parser.error('output already exists; choose a new audit file')
    result = audit(args.session, args.alignment, args.previous)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open('x', encoding='utf8') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')
    print(json.dumps(dict(status=result['status'], binding_sha256=result['binding_sha256'], out=str(out))))


if __name__ == '__main__':
    main()

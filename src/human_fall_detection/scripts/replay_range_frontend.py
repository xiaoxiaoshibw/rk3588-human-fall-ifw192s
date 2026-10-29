"""只读原始会话的 W1 前端：显式方向表/前缀，不接节点、跟踪或事件。"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.capture_input import ROW_DTYPE, read_source_meta, sha256_file
from core.range_image import ScanGrid
from core.range_background import RayBackground
from core.range_denoise import denoise
from core.range_components import label_components, merge_components
from core.range_contract import source_binding, binding_tuple, load_ground, reference_summary, distribution

CALIBRATION = ROOT / 'src/inno_lidar_ros/config/ifw192s'


def write_json(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)


def session_meta(path):
    raw = (path / 'meta.json').read_bytes()
    declared = json.loads(raw.decode('utf-8-sig'))
    meta = read_source_meta(raw, declared.get('sensor', {}).get('frame_id'), 'm')
    offset, previous = 0, None
    frames = meta.get('frames')
    if not isinstance(frames, list) or not frames:
        raise ValueError('empty session frame list')
    for frame in frames:
        for name in ('offset_points', 'count_points', 'stamp_sec', 'stamp_nanosec', 'dropped_points'):
            value = frame.get(name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError('invalid frame ' + name)
        if frame['offset_points'] != offset or frame['stamp_nanosec'] >= 1000000000:
            raise ValueError('invalid frame offset or nanoseconds')
        offset += frame['count_points']
        stamp = frame['stamp_sec'] * 1000000000 + frame['stamp_nanosec']
        if previous is not None and stamp <= previous:
            raise ValueError('non-increasing source header time')
        previous = stamp
    if offset != meta.get('total_points') or (path / 'points.bin').stat().st_size != offset * ROW_DTYPE.itemsize:
        raise ValueError('point file size/count mismatch')
    return meta, hashlib.sha256(raw).hexdigest()


def reference_rows(path, meta, meta_sha, points_sha):
    if path is None:
        return None
    summary = json.loads((path / 'SUMMARY.json').read_text(encoding='utf-8'))
    if summary.get('meta_sha256') != meta_sha or summary.get('points_sha256') != points_sha:
        raise ValueError('reference run is from different source bytes')
    with (path / 'target_frames.jsonl').open(encoding='utf-8') as stream:
        records = [json.loads(line) for line in stream]
    if len(records) != len(meta['frames']):
        raise ValueError('reference frame count mismatch')
    for i, (record, frame) in enumerate(zip(records, meta['frames'])):
        rows = record.get('target_source_rows')
        if (record.get('frame') != i or not isinstance(rows, list)
                or any(isinstance(r, bool) or not isinstance(r, int) or r < 0 or r >= frame['count_points'] for r in rows)
                or len(rows) != len(set(rows))):
            raise ValueError('invalid reference frame-local source rows')
    return records


def compare(frame, mask, components, reference):
    """旧行仅用于工程对照；按交集选分量是离线诊断，不是新目标检测。"""
    old = np.asarray(reference['target_source_rows'], dtype=np.int64)
    observed = (reference.get('track', {}).get('track_status') == 'locked'
                and not reference.get('track', {}).get('position_predicted', False))
    if not observed or not len(old):
        return dict(reference_observed=False)
    cell_rows = frame.source_rows[mask]
    survived = np.intersect1d(old, cell_rows, assume_unique=True)
    overlaps = [len(np.intersect1d(old, c['source_rows'], assume_unique=True)) for c in components]
    best = int(np.argmax(overlaps)) if overlaps and max(overlaps) else None
    selected = components[best]['source_rows'] if best is not None else np.empty(0, dtype=np.int64)
    intersection = overlaps[best] if best is not None else 0
    union_rows = np.unique(np.concatenate([c['source_rows'] for c in components])) if components else np.empty(0, dtype=np.int64)
    union_reference = len(np.intersect1d(old, union_rows, assume_unique=True))
    return dict(reference_observed=True, reference_points=len(old), kept_reference_points=len(survived),
                kept_reference_fraction=len(survived) / len(old),
                diagnostic_best_component=best, diagnostic_component_points=len(selected),
                diagnostic_component_retained=bool(best is not None and components[best]['retained']),
                diagnostic_reference_fraction=intersection / len(old),
                reference_dispersion_fraction=1 - intersection / len(survived) if len(survived) else None,
                dispersion_reason=None if len(survived) else 'no_surviving_reference_rows',
                selected_intersection_points=intersection, union_reference_points=union_reference,
                union_reference_fraction=union_reference/len(old),
                other_surviving_reference_points=len(survived)-intersection,
                not_survived_reference_points=len(old)-len(survived),
                added_component_points=len(selected)-intersection, removed_reference_points=len(old)-intersection,
                component_count=len(components), largest_component_points=max((c['points'] if 'points' in c else len(c['source_rows']) for c in components), default=0),
                component_reference_jaccard=intersection / (len(old) + len(selected) - intersection),
                removed_reference_rows=np.setdiff1d(old, selected, assume_unique=True).tolist(),
                added_component_rows=np.setdiff1d(selected, old, assume_unique=True).tolist())


def percentiles(values):
    if not all(np.isfinite(v) and v >= 0 for v in values):
        raise ValueError('timing samples must be finite and nonnegative')
    if not len(values):
        return dict(samples=0, p50_ms=None, p95_ms=None, p99_ms=None, max_ms=None)
    return dict(samples=len(values), p50_ms=float(np.percentile(values, 50)),
                p95_ms=float(np.percentile(values, 95)), p99_ms=float(np.percentile(values, 99)), max_ms=float(np.max(values)))


def run(session, out, *, empty_prefix_frames, azimuth, elevation,
        reference_run=None, save_arrays=False, limit=None, min_neighbours=2, merge_ground=None,
        profile=False):
    session, out = Path(session).resolve(), Path(out).resolve()
    reference_run = Path(reference_run) if reference_run is not None else None
    # 源数据和junction不作输出位置，resolve后再判断，拒绝别名绕过。
    for protected in (ROOT / 'data', ROOT / 'captures'):
        target = protected.resolve()
        if (out == target or target in out.parents or out in session.parents
                or session in out.parents or out == session):
            raise ValueError('output must be a new directory outside source data')
    meta, meta_sha = session_meta(session)
    total = len(meta['frames'])
    count = total if limit is None else limit
    if (isinstance(empty_prefix_frames, bool) or not isinstance(empty_prefix_frames, int)
            or not 1 <= empty_prefix_frames < count <= total):
        raise ValueError('require 1 <= empty prefix < replay frames <= total')
    grid = ScanGrid.from_csv(azimuth, elevation)
    points_sha = sha256_file(session / 'points.bin')
    identity = source_binding(session, meta, meta_sha, points_sha, grid)
    identity.update(azimuth_sha256=sha256_file(azimuth), elevation_sha256=sha256_file(elevation))
    ground = load_ground(merge_ground, identity) if merge_ground is not None else None
    reference = reference_rows(reference_run, meta, meta_sha, points_sha)
    binding = binding_tuple(identity)
    out.mkdir(parents=True, exist_ok=False)
    if save_arrays:
        (out / 'arrays').mkdir()
    write_json(out / 'GRID.json', dict(shape=grid.shape, grid_sha256=grid.sha256,
               azimuth_path=str(Path(azimuth).resolve()), azimuth_sha256=sha256_file(azimuth),
               elevation_path=str(Path(elevation).resolve()), elevation_sha256=sha256_file(elevation),
               tolerance_deg=grid.tolerance_deg, scope='existing driver direction table, physical installation UNKNOWN'))
    prefix, background, fit_ms = [], None, None
    timings, checks, rejected, statuses, component_counts, largest_counts = [], [], {}, {}, [], []
    all_timings, retained_counts = [], []
    digest = hashlib.sha256()
    t0 = meta['frames'][0]['stamp_sec'] * 1000000000 + meta['frames'][0]['stamp_nanosec']
    with (session / 'points.bin').open('rb') as source, \
            (out / 'frames.jsonl').open('x', encoding='utf-8') as ledger, \
            (out / 'timings.jsonl').open('x', encoding='utf-8') as timing_ledger:
        for index, info in enumerate(meta['frames'][:count]):
            e2e_began = time.perf_counter()
            raw = source.read(info['count_points'] * ROW_DTYPE.itemsize)
            if len(raw) != info['count_points'] * ROW_DTYPE.itemsize:
                raise ValueError('source truncated during replay')
            stamp = (info['stamp_sec'] * 1000000000 + info['stamp_nanosec'] - t0) / 1e9
            began = time.perf_counter()
            detail = {} if profile else None
            frame = grid.decode(raw, binding, timings=detail)
            decoded = time.perf_counter()
            if background is None:
                prefix.append(frame)
                foreground = np.zeros(grid.shape, dtype=bool)
                status, unknown = 'prefix_warmup', np.zeros(grid.shape, dtype=bool)
                residual = np.zeros(grid.shape)
            else:
                result = background.foreground(frame)
                foreground, status, unknown = result['mask'], result['status'], result['unknown']
                residual = result['residual_m']
                # W1只限制测量距离；不凭未认证地面裁掉低位点。
                with np.errstate(invalid='ignore'):
                    foreground &= (frame.range_m >= 0.1) & (frame.range_m <= 8.0)
            subtracted = time.perf_counter()
            cleaned = denoise(frame, foreground, min_neighbours)
            denoised = time.perf_counter()
            labels, components = label_components(frame, cleaned['mask'], timings=detail)
            if ground is not None:
                labels, components = merge_components(frame, labels, components, ground)
            finished = time.perf_counter()
            costs = dict(frame=index, status=status, decode_ms=(decoded-began)*1000,
                         background_ms=(subtracted-decoded)*1000, denoise_ms=(denoised-subtracted)*1000,
                         components_ms=(finished-denoised)*1000, frontend_ms=(finished-began)*1000)
            if detail is not None:
                costs.update(detail)
                costs['components_excluding_lift_ms'] = costs['components_ms'] - detail.get('source_lift_ms', 0)
            comparison = compare(frame, cleaned['mask'], components, reference[index]) if reference else None
            if comparison and comparison['reference_observed']:
                checks.append(comparison)
            for key, rows in frame.rejected.items():
                rejected[key] = rejected.get(key, 0) + len(rows)
            statuses[status] = statuses.get(status, 0) + 1
            record = dict(frame=index, time_s=stamp, offset_points=info['offset_points'],
                          raw_sha256=hashlib.sha256(raw).hexdigest(), status=status,
                          valid_cells=int(frame.valid.sum()), foreground_cells=int(foreground.sum()),
                          denoised_cells=int(cleaned['mask'].sum()), unknown_background_cells=int(unknown.sum()),
                          foreground_edge_cells=int(cleaned['edge'].sum()),
                          rejected={k: v.tolist() for k, v in frame.rejected.items()},
                          components=[dict(component_id=c['component_id'], points=c['points'],
                                           retained=c['retained'], semantic=c['semantic'],
                                           merged_from=c.get('merged_from', [c['component_id']]),
                                           source_rows=c['source_rows'].tolist())
                                      for c in components], comparison=comparison)
            ledger_built = time.perf_counter()
            serial = json.dumps(record, sort_keys=True, allow_nan=False)
            serialized = time.perf_counter()
            ledger.write(serial+'\n')
            digest.update(serial.encode())
            written = time.perf_counter()
            if save_arrays:
                np.savez_compressed(out / 'arrays' / ('frame_%04d.npz' % index),
                                    range_m=frame.range_m, valid=frame.valid, source_rows=frame.source_rows,
                                    point_time_s=frame.point_time_s, row_time_s=frame.row_time_s,
                                    intensity=frame.intensity, foreground=foreground, residual_m=residual,
                                    denoised=cleaned['mask'], edge=cleaned['edge'], labels=labels)
            if index + 1 == empty_prefix_frames:
                fit_began = time.perf_counter()
                background = RayBackground(prefix, empty_prefix_declared=True,
                                           min_observations=min(10, empty_prefix_frames))
                fit_ms = (time.perf_counter()-fit_began)*1000
                np.savez_compressed(out / 'background.npz', mean_m=background.mean_m,
                                    sigma_m=background.sigma_m, known=background.known,
                                    observations=background.observations)
                write_json(out / 'BACKGROUND.json', dict(binding=identity, cache_sha256=sha256_file(out/'background.npz'),
                    grid_shape=grid.shape, prefix_first_frame=0, prefix_last_frame=index,
                    first_stamp_ns=t0, last_stamp_ns=info['stamp_sec']*1000000000+info['stamp_nanosec'],
                    parameters=dict(min_observations=min(10, empty_prefix_frames), min_valid_fraction=.6,
                                    scene_change_fraction=.35, sigma_floor_m=.005, mad_scale=1.4826,
                                    residual_floor_m=.04, sigma_multiplier=4, update=False),
                    scope='declared_empty_development; physical applicability UNKNOWN'))
                prefix.clear()
            costs.update(read_io_ms=(began-e2e_began)*1000, ledger_ms=(ledger_built-finished)*1000,
                         json_ms=(serialized-ledger_built)*1000,
                         write_io_ms=(written-serialized)*1000,
                         post_write_io_ms=(time.perf_counter()-written)*1000,
                         end_to_end_ms=(time.perf_counter()-e2e_began)*1000)
            timing_ledger.write(json.dumps(costs, allow_nan=False)+'\n')
            all_timings.append(costs)
            if status != 'prefix_warmup':
                timings.append(costs)
                component_counts.append(len(components))
                retained_counts.append(sum(c['retained'] for c in components))
                largest_counts.append(max((c['points'] for c in components), default=0))
            if (index + 1) % 100 == 0:
                print(json.dumps(dict(frames=index+1, total=count)), flush=True)
    if sha256_file(session / 'points.bin') != points_sha or sha256_file(session / 'meta.json') != meta_sha:
        raise ValueError('source bytes changed during replay')
    sources = [Path(__file__).resolve(), *sorted((ROOT / 'src/human_fall_detection/core').glob('range_*.py'))]
    summary = dict(schema='range_frontend_replay_v1', session=session.name, frames=count,
                   source_frames=total, meta_sha256=meta_sha, points_sha256=points_sha,
                   binding=binding, source_binding=identity, grid_shape=grid.shape, grid_sha256=grid.sha256,
                   empty_prefix_frames=empty_prefix_frames, background_fit_ms=fit_ms,
                   background_scope='declared_empty_development; independent empty-scene GT UNKNOWN',
                   background_known_cells=int(background.known.sum()), statuses=statuses,
                   settings=dict(range_min_m=0.1, range_max_m=8.0, min_neighbours=min_neighbours,
                                 min_component_points=15, background_update=False, merge=ground is not None),
                   merge_ground_sha256=sha256_file(merge_ground) if merge_ground is not None else None,
                   source_declared_dropped_frames=meta.get('extraction', {}).get('dropped_frames'),
                   source_declared_dropped_points=meta.get('total_dropped_points'),
                   processed_declared_dropped_points=sum(f['dropped_points'] for f in meta['frames'][:count]),
                   timing_scope='PC packed bytes -> decode/background/denoise/labels/source-row lift; excludes file IO, serialization, prefix fit',
                   frontend_pc=percentiles([r['frontend_ms'] for r in timings]),
                   phase_pc={k: percentiles([r[k] for r in timings]) for k in
                             ('decode_ms', 'background_ms', 'denoise_ms', 'components_ms')},
                   all_phase_pc={k: percentiles([r.get(k, 0) for r in timings]) for k in timings[0] if k.endswith('_ms')},
                   warmup_pc={k: percentiles([r.get(k, 0) for r in all_timings if r['status']=='prefix_warmup'])
                              for k in ('frontend_ms','end_to_end_ms')},
                   detailed_profile=profile, quantile_method='numpy percentile linear interpolation',
                   loop_timing_scope='read/processing/ledger/JSON/buffered write; excludes timing recorder, final flush, startup SHA and shutdown; CLI wall recorded separately',
                   subphase_scope='read_io includes header time; write_io includes ledger digest; source_lift is label_components only; merge work remains in components',
                   component_statistics=dict(component_count=distribution(component_counts),
                       largest_component_points=distribution(largest_counts),
                       retained_component_count=distribution(retained_counts),
                       ready_with_retained_components=sum(r > 0 for r in retained_counts),
                       ready_without_retained_components=sum(r == 0 for r in retained_counts)),
                   rejected=rejected, algorithm_output_sha256=digest.hexdigest(),
                   frames_sha256=sha256_file(out / 'frames.jsonl'),
                   reference_run=str(reference_run) if reference_run else None,
                   reference_frames_sha256=sha256_file(reference_run / 'target_frames.jsonl') if reference_run else None,
                   reference_frames=len(checks),
                   reference_diagnostics=reference_summary(checks),
                   source_sha256={str(p.relative_to(ROOT)): sha256_file(p) for p in sources},
                   human_point_retention='UNKNOWN', human_precision_recall='UNKNOWN',
                   fall_effectiveness='UNKNOWN', board_performance='UNKNOWN', deployed=False)
    write_json(out / 'SUMMARY.json', summary)
    print(json.dumps(dict(frames=count, frontend_pc=summary['frontend_pc'],
                          reference_diagnostics=summary['reference_diagnostics'])), flush=True)
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--session', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--empty-prefix-frames', type=int, required=True)
    parser.add_argument('--azimuth', type=Path, default=CALIBRATION / 'ifw192s_azimuth_192x256.csv')
    parser.add_argument('--elevation', type=Path, default=CALIBRATION / 'ifw192s_elevation_192x256.csv')
    parser.add_argument('--reference-run', type=Path)
    parser.add_argument('--save-arrays', action='store_true')
    parser.add_argument('--limit', type=int)
    parser.add_argument('--min-neighbours', type=int, default=2)
    parser.add_argument('--profile', action='store_true', help='nested decode/source lift timing; independent unprofiled control required')
    parser.add_argument('--merge-ground', type=Path, help='optional conservative 3D merge; existing source-frame ground JSON')
    args = parser.parse_args()
    run(args.session, args.out, empty_prefix_frames=args.empty_prefix_frames,
        azimuth=args.azimuth, elevation=args.elevation, reference_run=args.reference_run,
        save_arrays=args.save_arrays, limit=args.limit, min_neighbours=args.min_neighbours,
        merge_ground=args.merge_ground, profile=args.profile)

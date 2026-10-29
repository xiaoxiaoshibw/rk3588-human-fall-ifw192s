#!/usr/bin/env python3
"""Dynamic-ROI ablation harness (offline, PC only).

Runs the fixed single-target chain (composition on, ROI A/C arms) over a bound
session and writes per-frame rows, ROI diagnostics and stage timings. The ROI is
never enabled here unless the arm says so; nothing in this script touches the
board, the network or ``data/`` (read-only session input).

Arms:

- ``A``: fixed full view (no ROI section) - the stage-1 frozen baseline.
- ``C``: dynamic ROI with the shipped defaults.
- ``C1``..``C4``/``CPRIME``: documented single-parameter variants.
- ``B``: not implemented here by design; it reuses ``current/run.py``'s existing
  ``--search-bounds`` semantics with a fixed RAW axis-aligned box (offline prior).

Usage (repo root):

    python -B -W error src/human_fall_detection/scripts/roi_ablation.py run \
        --sid cap_20261018_110029 --arm A --out docs/evidence/<dir>/dev/A
"""
import argparse
import gzip
import hashlib
import json
import math
import os
import sys
import time
from pathlib import Path

import numpy as np

CORE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CORE))
sys.path.insert(0, str(CORE / 'scripts'))

from core.capture_input import canonical_source_xyz, read_source_meta, validate_frames
from core.lidar_candidates import build_background, prepare_background
from core.pipeline import ReplayPipeline
from core.roi import DEFAULT_SETTINGS as ROI_DEFAULTS

REPO = CORE.parents[1]
DEFAULT_GROUND = (REPO / 'docs/human_fall/evidence/2026-10-18_hfus_project_dev_r1'
                  / 'leveling_02/TRANSFORM.json')
DEFAULT_CANDIDATES = CORE / 'config/single_target_geometry_v2.json'
ROI_CONFIG = CORE / 'config/perception_roi_v1.yaml'
FROZEN_CONFIG = CORE / 'config/perception_single_target_v3.yaml'


def load_yml(path):
    import yaml
    return yaml.safe_load(Path(path).read_text(encoding='utf8')) or {}
ARMS = {
    'A': None,
    'C': {},
    'C1': dict(prediction=False),
    'C2': dict(margin_m=0.5),
    'C3': dict(margin_m=1.0),
    'C4': dict(base_radius_m=2.0),
    'CPRIME': dict(before_stride=True),
}


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        for block in iter(lambda: handle.read(4 * 1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def load_session(session_dir):
    meta_path = session_dir / 'meta.json'
    bin_path = session_dir / 'points.bin'
    raw_meta = meta_path.read_bytes()
    declared_frame = None
    meta_json = json.loads(raw_meta.decode('utf8'))
    declared_frame = meta_json['sensor']['frame_id']
    meta = read_source_meta(raw_meta, declared_frame, 'm')
    frames = validate_frames(meta)
    points, _ = canonical_source_xyz(frames, bin_path.read_bytes())
    stamps = [int(frame['stamp_sec']) * 10 ** 9 + int(frame['stamp_nanosec'])
              for frame in frames]
    relative = [(value - stamps[0]) / 1e9 for value in stamps]
    return dict(meta=meta, meta_sha256=sha256_file(meta_path),
                bin_sha256=sha256_file(bin_path), frames=frames,
                points=points.astype(np.float64), times=relative,
                frame_id=declared_frame, sid=session_dir.name)


def load_ground(path):
    """Ground plane in the ReplayPipeline source frame (``R[2] . p + t[2] = 0``).

    The stored transform maps RAW/innolidar into a ground frame; the plane record
    for the downstream chain is therefore the *source* frame ('innolidar', the
    frame label ReplayPipeline builds snapshots with). The label is not cosmetic:
    a mismatched frame would make the ground ineligible and silently disable every
    height-dependent gate.
    """
    artifact = json.loads(Path(path).read_text(encoding='utf8'))
    rotation = np.asarray(artifact['R'], dtype=float)
    translation = np.asarray(artifact['t'], dtype=float)
    if rotation.shape != (3, 3) or translation.shape != (3,):
        raise ValueError('invalid ground transform shape')
    if not np.allclose(rotation @ rotation.T, np.eye(3), atol=1e-10, rtol=0):
        raise ValueError('ground transform is not a proper rotation')
    if artifact.get('from_frame') != 'RAW/innolidar':
        raise ValueError('ground transform is not bound to the RAW source frame')
    return dict(status='valid', frame='innolidar',
                normal=rotation[2].tolist(), offset_m=float(translation[2]))


def load_roi_section():
    """The shipped ROI section, parsed with the same YAML reader as the node."""
    document = load_yml(ROI_CONFIG)
    section = dict(document.get('roi') or {})
    if not section:
        raise SystemExit('perception_roi_v1.yaml has no roi section')
    return section


def build_arm_settings(arm, arm_overrides=None):
    candidates = json.loads(DEFAULT_CANDIDATES.read_text(encoding='utf8'))
    acquisition = dict(load_yml(FROZEN_CONFIG).get('acquisition') or {})
    acquisition.setdefault('human_entry_gate', True)
    settings = dict(candidates=candidates, acquisition=acquisition)
    if arm in (None, 'A'):
        # A is the stage-1 frozen baseline: no roi section at all.
        return settings
    if arm == 'A_NOCOMPOSE':
        # Timing-only control: the stage-1 chain with fragment composition off.
        acquisition['composition'] = dict(acquisition.get('composition') or {},
                                          enabled=False)
        return settings
    roi = dict(load_roi_section())
    roi['enabled'] = True
    roi.update(ARMS.get(arm) or {})
    roi.update(arm_overrides or {})
    settings['roi'] = roi
    return settings


def run_arm(session, arm, out_dir, *, empty_prefix_frames=50, arms_overrides=None,
            warmup_runs=1, measured_runs=3, ground_path=DEFAULT_GROUND,
            max_frames=None, reference_rows=None):
    if out_dir.exists() and any(out_dir.iterdir()):
        raise SystemExit('refusing to write into a non-empty output directory: ' + str(out_dir))
    out_dir.mkdir(parents=True, exist_ok=False)
    settings = build_arm_settings(arm, arms_overrides)
    ground = load_ground(ground_path)
    from core.roi import roi_mask
    frame_count = len(session['frames']) if max_frames is None else min(
        max_frames, len(session['frames']))
    records = []
    runs = []
    for run_index in range(warmup_runs + measured_runs):
        pipeline = ReplayPipeline(session['sid'], settings, target_mode='automatic')
        pipeline.ground = dict(ground)
        pipeline.background = None
        pipeline.timing_sink = {}
        background = None
        stage_totals = {}
        step_times = []
        run_records = []
        for index in range(frame_count):
            frame = session['frames'][index]
            start = frame['offset_points']
            stop = start + frame['count_points']
            cloud = session['points'][start:stop]
            if index < empty_prefix_frames:
                if index + 1 == empty_prefix_frames:
                    background = prepare_background(build_background(
                        [session['points'][session['frames'][k]['offset_points']:
                                          session['frames'][k]['offset_points']
                                          + session['frames'][k]['count_points']]
                         for k in range(empty_prefix_frames)],
                        settings.get('candidates'), frame_id='RAW/innolidar',
                        note='declared empty prefix; development assumption'))
                    pipeline.background = background
                cloud = np.empty((0, 3))
            pipeline.timing_sink.clear()
            began = time.perf_counter()
            result = pipeline.step(cloud, session['times'][index], 0, index)
            elapsed = time.perf_counter() - began
            step_times.append(elapsed)
            for key, value in pipeline.timing_sink.items():
                stage_totals[key] = stage_totals.get(key, 0.0) + float(value)
            if run_index >= warmup_runs:
                ledger = ((result['acquisition'] or {}).get('candidate_history')
                          or {}).get('candidates') or []
                rejected = ((result['acquisition'] or {}).get('rejected') or {})
                reference = (reference_rows or {}).get(index)
                reference_total = 0 if not reference else len(reference)
                reference_excluded = None
                if reference:
                    local = np.asarray(reference, dtype=np.int64) - start
                    decision = result.get('roi') or {}
                    mask, _ = roi_mask(cloud, decision, ground,
                                       frame_id='RAW/innolidar',
                                       settings=decision.get('settings'))
                    reference_excluded = int(np.count_nonzero(~mask[local]))
                run_records.append(dict(
                    frame=index, source_stamp_s=session['times'][index],
                    seq=frame['seq'], row_offset=start, point_count=int(frame['count_points']),
                    track_status=result['track']['track_status'],
                    track_id=result['track']['track_id'],
                    track_predicted=result['track']['position_predicted'],
                    acquisition_status=result['acquisition']['status'] if result['acquisition'] else None,
                    acquisition_reason=result['acquisition']['reason'] if result['acquisition'] else None,
                    history_reset_reason=result['track'].get('history_reset_reason'),
                    candidate_count=len(rejected),
                    ledger_count=len(ledger),
                    target_rows=[int(start + row) for row in result['target_source_rows']],
                    target_count=len(result['target_source_rows']),
                    reference_rows_total=reference_total,
                    reference_rows_excluded=reference_excluded,
                    fall_status=result['fall']['fall_status'],
                    roi=result.get('roi'),
                    step_s=elapsed,
                    stages_s=dict(pipeline.timing_sink)))
        runs.append(dict(step_s=step_times, stages_s=stage_totals, records=run_records))
    # Deterministic payload is identical across measured runs; keep the last copy.
    records = runs[-1]['records']
    timed_from = min(empty_prefix_frames, frame_count)
    timing = dict(
        warmup_runs=warmup_runs, measured_runs=measured_runs,
        frames=frame_count, timed_from_frame=timed_from,
        pc_only=True, scope='full ReplayPipeline.step (snapshot+acquisition+features+fall)',
        python=sys.version.split()[0], numpy=np.__version__,
        per_run=[dict(
            step_p50_ms=float(np.quantile(run['step_s'][timed_from:], 0.50) * 1000),
            step_p95_ms=float(np.quantile(run['step_s'][timed_from:], 0.95) * 1000),
            step_max_ms=float(np.max(run['step_s'][timed_from:]) * 1000),
            total_s=float(np.sum(run['step_s'][timed_from:])),
            stages_total_s={key: float(value) for key, value in run['stages_s'].items()},
            stages_p95_ms={key: float(np.quantile(
                [record['stages_s'].get(key, 0.0) for record in run['records'][timed_from:]],
                0.95) * 1000)
                for key in (run['records'][0]['stages_s'] if run['records'] else {})})
            for run in runs[warmup_runs:]])
    summary = dict(
        arm=arm, settings=settings, ground=ground,
        session=dict(sid=session['sid'], frames=frame_count,
                     meta_sha256=session['meta_sha256'],
                     bin_sha256=session['bin_sha256'],
                     frame_id=session['frame_id']),
        empty_prefix_frames=empty_prefix_frames,
        track_counts={}, fall_counts={}, roi_states={}, roi_rejections={},
        first_lock_s=None)
    for record in records:
        summary['track_counts'][record['track_status']] = \
            summary['track_counts'].get(record['track_status'], 0) + 1
        summary['fall_counts'][record['fall_status']] = \
            summary['fall_counts'].get(record['fall_status'], 0) + 1
        roi = record['roi'] or {}
        if roi:
            summary['roi_states'][roi.get('state')] = \
                summary['roi_states'].get(roi.get('state'), 0) + 1
            if not roi.get('applied'):
                reason = roi.get('reason')
                summary['roi_rejections'][reason] = \
                    summary['roi_rejections'].get(reason, 0) + 1
        if summary['first_lock_s'] is None and record['track_status'] == 'locked':
            summary['first_lock_s'] = record['source_stamp_s']
    reference_frames = [record for record in records
                        if record.get('reference_rows_total')]
    if reference_frames:
        fractions = [record['reference_rows_excluded'] / record['reference_rows_total']
                     for record in reference_frames
                     if record.get('reference_rows_excluded') is not None]
        total_rows = sum(record['reference_rows_total'] for record in reference_frames)
        total_excluded = sum(record['reference_rows_excluded'] or 0
                             for record in reference_frames)
        summary['reference_mask_exclusion'] = dict(
            frames=len(fractions),
            rows=total_rows, excluded_rows=total_excluded,
            ratio=(None if not total_rows else total_excluded / total_rows),
            p95=None if not fractions else float(np.quantile(fractions, 0.95)),
            max=None if not fractions else float(np.max(fractions)))
    with gzip.open(out_dir / 'frames.jsonl.gz', 'wt', encoding='utf8') as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True, separators=(',', ':'),
                                    allow_nan=False) + '\n')
    (out_dir / 'TIMING.json').write_text(
        json.dumps(timing, ensure_ascii=False, indent=1), encoding='utf8')
    (out_dir / 'SUMMARY.json').write_text(
        json.dumps(summary, ensure_ascii=False, indent=1), encoding='utf8')
    (out_dir / 'SHA256.json').write_text(json.dumps({
        name: sha256_file(out_dir / name)
        for name in ('frames.jsonl.gz', 'TIMING.json', 'SUMMARY.json')},
        ensure_ascii=False, indent=1), encoding='utf8')
    print(json.dumps(dict(arm=arm, frames=frame_count,
                          track_counts=summary['track_counts'],
                          first_lock_s=summary['first_lock_s'],
                          p95_ms=timing['per_run'][-1]['step_p95_ms']),
                     ensure_ascii=False))


def load_arm(out_dir):
    with gzip.open(out_dir / 'frames.jsonl.gz', 'rt', encoding='utf8') as handle:
        records = [json.loads(line) for line in handle]
    return records


def payload(record):
    """Deterministic per-frame payload used for equivalence (no timings)."""
    return {key: value for key, value in record.items()
            if key not in ('step_s', 'stages_s')}


def compare_arms(a_dir, b_dir, out_path=None):
    """G1 equivalence and A/C point-set/tracking metrics for two arm outputs."""
    a = load_arm(a_dir)
    b = load_arm(b_dir)
    if len(a) != len(b):
        raise SystemExit('frame count mismatch: %d vs %d' % (len(a), len(b)))
    equivalent = all(payload(x) == payload(y) for x, y in zip(a, b))
    metrics = []
    for x, y in zip(a, b):
        a_rows = set(x['target_rows'])
        b_rows = set(y['target_rows'])
        missing = 0.0 if not a_rows else len(a_rows - b_rows) / len(a_rows)
        extra = 0.0 if not b_rows else len(b_rows - a_rows) / len(b_rows)
        roi = y.get('roi') or {}
        metrics.append(dict(
            frame=x['frame'], t=x['source_stamp_s'],
            a_track=x['track_status'], b_track=y['track_status'],
            a_id=x['track_id'], b_id=y['track_id'],
            a_count=len(a_rows), b_count=len(b_rows),
            a_locked=x['track_status'] == 'locked',
            b_locked=y['track_status'] == 'locked',
            missing=missing, extra=extra,
            roi_state=roi.get('state'), roi_applied=roi.get('applied'),
            roi_radius=roi.get('radius_m'), roi_reason=roi.get('reason'),
            roi_dropped=roi.get('dropped_points')))
    locked = [m for m in metrics if m['a_locked']]
    missing = np.asarray([m['missing'] for m in locked]) if locked else np.zeros(0)
    extra = np.asarray([m['extra'] for m in locked]) if locked else np.zeros(0)
    new_unlocked = [m['frame'] for m in metrics if m['a_locked'] and not m['b_locked']]
    lost_frames = [m['frame'] for m in metrics if m['a_track'] != 'lost'
                   and m['b_track'] == 'lost']
    ambiguous_frames = [m['frame'] for m in metrics if m['a_track'] != 'ambiguous'
                        and m['b_track'] == 'ambiguous']
    id_mismatch = sorted({m['b_id'] for m in metrics if m['b_id'] is not None}
                         - {m['a_id'] for m in metrics if m['a_id'] is not None})
    below_min = [m['frame'] for m in locked if m['b_count'] < 30]
    report = dict(
        a=str(a_dir), b=str(b_dir), frames=len(metrics),
        equivalent=equivalent,
        equivalent_excluded=[] if equivalent else None,
        a_locked_frames=len(locked),
        missing=dict(p50=float(np.quantile(missing, 0.5)) if len(missing) else None,
                     p95=float(np.quantile(missing, 0.95)) if len(missing) else None,
                     max=float(np.max(missing)) if len(missing) else None),
        extra=dict(p50=float(np.quantile(extra, 0.5)) if len(extra) else None,
                   p95=float(np.quantile(extra, 0.95)) if len(extra) else None,
                   max=float(np.max(extra)) if len(extra) else None),
        a_locked_but_b_unlocked=new_unlocked,
        new_lost=lost_frames, new_ambiguous=ambiguous_frames,
        new_track_ids=id_mismatch,
        b_below_effective_minimum=below_min,
        roi_applied_frames=sum(1 for m in metrics if m['roi_applied']),
        roi_states={},
        frame_metrics=metrics)
    for m in metrics:
        if m['roi_state']:
            report['roi_states'][m['roi_state']] = \
                report['roi_states'].get(m['roi_state'], 0) + 1
    destination = out_path or (Path(b_dir) / 'COMPARE.json')
    Path(destination).write_text(json.dumps(report, ensure_ascii=False, indent=1),
                                 encoding='utf8')
    print(json.dumps({key: report[key] for key in (
        'frames', 'a_locked_frames', 'missing', 'extra', 'new_lost', 'new_ambiguous',
        'new_track_ids', 'b_below_effective_minimum', 'roi_applied_frames',
        'roi_states', 'equivalent')}, ensure_ascii=False))
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    run = sub.add_parser('run')
    run.add_argument('--sid', required=True)
    run.add_argument('--session-dir', default=None)
    run.add_argument('--arm', required=True, choices=sorted(ARMS))
    run.add_argument('--out', required=True, type=Path)
    run.add_argument('--empty-prefix-frames', type=int, default=50)
    run.add_argument('--max-frames', type=int, default=None)
    run.add_argument('--warmup-runs', type=int, default=1)
    run.add_argument('--measured-runs', type=int, default=3)
    run.add_argument('--ground', default=str(DEFAULT_GROUND))
    run.add_argument('--roi-override', action='append', default=[],
                     metavar='KEY=JSON')
    run.add_argument('--reference-arm', default=None, type=Path,
                     help='completed A-arm output; records how many of its target rows '
                          'the ROI mask would exclude (no re-run of A)')
    compare = sub.add_parser('compare')
    compare.add_argument('--a', required=True, type=Path)
    compare.add_argument('--b', required=True, type=Path)
    compare.add_argument('--out', default=None, type=Path)
    args = parser.parse_args(argv)
    if args.command == 'compare':
        compare_arms(args.a, args.b, args.out)
        return 0
    session_dir = Path(args.session_dir) if args.session_dir else \
        REPO / 'data/sessions' / args.sid
    overrides = {}
    for item in args.roi_override:
        key, _, value = item.partition('=')
        overrides[key] = json.loads(value)
    session = load_session(session_dir)
    reference = None
    if args.reference_arm is not None:
        reference = {record['frame']: record['target_rows']
                     for record in load_arm(args.reference_arm)}
    run_arm(session, args.arm, args.out, empty_prefix_frames=args.empty_prefix_frames,
            arms_overrides=overrides, warmup_runs=args.warmup_runs,
            measured_runs=args.measured_runs, ground_path=args.ground,
            max_frames=args.max_frames, reference_rows=reference)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
#!/usr/bin/env python3
"""Interleaved A/C timing for the dynamic ROI (PC, offline, serial).

The same in-memory session frames are replayed alternately per arm and per round so
thermal drift, page cache and run order cannot systematically favour one arm. Each
round reports the per-frame full ``ReplayPipeline.step`` time (snapshot +
acquisition/composition + features + fall), P50/P95/max over the frames after the
declared empty prefix. The reported statistic is the median of the rounds plus the
worst-case round; both are kept.

Usage:
    python -B -W error src/human_fall_detection/scripts/roi_timing.py \
        --sid cap_20261018_110029 --out docs/evidence/<dir>/dev/TIMING.json
"""
import argparse
import json
import statistics
import sys
import time
from pathlib import Path

import numpy as np

CORE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CORE))
sys.path.insert(0, str(CORE / 'scripts'))

from core.lidar_candidates import build_background, prepare_background
from core.pipeline import ReplayPipeline
import roi_ablation as harness


def replay(session, settings, ground, empty_prefix_frames, frame_count):
    pipeline = ReplayPipeline(session['sid'], settings, target_mode='automatic')
    pipeline.ground = dict(ground)
    pipeline.background = None
    pipeline.timing_sink = {}
    stages = {}
    times = []
    cpu_times = []
    payload = []
    for index in range(frame_count):
        frame = session['frames'][index]
        start = frame['offset_points']
        cloud = session['points'][start:start + frame['count_points']]
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
        cpu_before = time.process_time()
        began = time.perf_counter()
        result = pipeline.step(cloud, session['times'][index], 0, index)
        elapsed = time.perf_counter() - began
        cpu_elapsed = time.process_time() - cpu_before
        if index >= empty_prefix_frames:
            times.append(elapsed)
            cpu_times.append(cpu_elapsed)
        for key, value in pipeline.timing_sink.items():
            stages[key] = stages.get(key, 0.0) + float(value)
        payload.append({
            'track': result['track']['track_status'],
            'id': result['track']['track_id'],
            'rows': [int(start + row) for row in result['target_source_rows']],
            'fall': result['fall']['fall_status'],
            'roi_applied': bool((result.get('roi') or {}).get('applied'))})
    times = np.asarray(times)
    cpu_times = np.asarray(cpu_times)
    return dict(
        step_p50_ms=float(np.quantile(times, 0.50) * 1000),
        step_p95_ms=float(np.quantile(times, 0.95) * 1000),
        step_max_ms=float(np.max(times) * 1000),
        total_s=float(np.sum(times)),
        cpu_p50_ms=float(np.quantile(cpu_times, 0.50) * 1000),
        cpu_p95_ms=float(np.quantile(cpu_times, 0.95) * 1000),
        cpu_total_s=float(np.sum(cpu_times)),
        frames=int(len(times)),
        times_s=[float(value) for value in times],
        stages_total_s={key: float(value) for key, value in stages.items()},
        payload=payload)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sid', required=True)
    parser.add_argument('--session-dir', default=None)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--arms', default='A,C')
    parser.add_argument('--rounds', type=int, default=5)
    parser.add_argument('--empty-prefix-frames', type=int, default=50)
    parser.add_argument('--max-frames', type=int, default=None)
    parser.add_argument('--ground', default=str(harness.DEFAULT_GROUND))
    args = parser.parse_args(argv)
    session_dir = Path(args.session_dir) if args.session_dir else \
        harness.REPO / 'data/sessions' / args.sid
    session = harness.load_session(session_dir)
    ground = harness.load_ground(args.ground)
    frame_count = len(session['frames']) if args.max_frames is None else min(
        args.max_frames, len(session['frames']))
    arms = [name.strip() for name in args.arms.split(',') if name.strip()]
    results = {name: [] for name in arms}
    payloads = {name: None for name in arms}
    for name in arms:  # one warm-up replay per arm before any measurement
        warm = replay(session, harness.build_arm_settings(name), ground,
                      args.empty_prefix_frames, frame_count)
        payloads[name] = warm['payload']
    for round_index in range(args.rounds):
        for name in arms:
            measured = replay(session, harness.build_arm_settings(name), ground,
                              args.empty_prefix_frames, frame_count)
            if measured['payload'] != payloads[name]:
                raise SystemExit('arm %s payload is not deterministic' % name)
            results[name].append({key: value for key, value in measured.items()
                                  if key not in ('payload', 'times_s')})
            results[name][-1]['times_s'] = measured['times_s']
    pooled = {}
    for name in arms:
        values = np.asarray([value for run in results[name]
                             for value in run['times_s']])
        cpu_values = np.asarray([run['cpu_p95_ms'] for run in results[name]])
        pooled[name] = dict(
            samples=int(len(values)),
            p50_ms=float(np.quantile(values, 0.50) * 1000),
            p95_ms=float(np.quantile(values, 0.95) * 1000),
            max_ms=float(np.max(values) * 1000),
            cpu_p95_median_ms=float(statistics.median(cpu_values)))
    summary = {name: dict(
        rounds=len(results[name]),
        p50_ms=[round(item['step_p50_ms'], 3) for item in results[name]],
        p95_ms=[round(item['step_p95_ms'], 3) for item in results[name]],
        max_ms=[round(item['step_max_ms'], 3) for item in results[name]],
        cpu_p95_ms=[round(item['cpu_p95_ms'], 3) for item in results[name]],
        p95_median_ms=round(statistics.median(
            [item['step_p95_ms'] for item in results[name]]), 3),
        p95_worst_ms=round(max(item['step_p95_ms'] for item in results[name]), 3),
        p50_median_ms=round(statistics.median(
            [item['step_p50_ms'] for item in results[name]]), 3),
        total_s_median=round(statistics.median(
            [item['total_s'] for item in results[name]]), 4),
        stages_total_s={key: round(float(value), 4) for key, value in
                        results[name][-1]['stages_total_s'].items()},
        frames=results[name][-1]['frames'])
        for name in arms}
    ratios = {}
    if 'A' in pooled and len(arms) > 1:
        for name in arms:
            if name == 'A':
                continue
            ratios[name] = dict(
                pooled_p95_ratio=round(pooled[name]['p95_ms'] / pooled['A']['p95_ms'], 4),
                pooled_p95_reduction=round(1.0 - pooled[name]['p95_ms']
                                           / pooled['A']['p95_ms'], 4),
                pooled_p50_ratio=round(pooled[name]['p50_ms'] / pooled['A']['p50_ms'], 4),
                cpu_p95_ratio=round(summary[name]['cpu_p95_ms'][-1]
                                    / summary['A']['cpu_p95_ms'][-1], 4)
                if summary['A']['cpu_p95_ms'][-1] else None)
    report = dict(
        sid=session['sid'], frames=frame_count,
        empty_prefix_frames=args.empty_prefix_frames,
        rounds=args.rounds, interleaved=True, warmup_replays_per_arm=1,
        python=sys.version.split()[0], numpy=np.__version__,
        scope='PC, serial, same in-memory frames; full ReplayPipeline.step; '
              'includes ROI controller/mask and composition; board UNKNOWN',
        arms=summary, pooled=pooled, ratios=ratios)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=1),
                        encoding='utf8')
    print(json.dumps(dict(pooled={name: {key: round(value, 3) for key, value in
                                         pooled[name].items() if key != 'samples'}
                              for name in arms}, ratios=ratios), ensure_ascii=False))


if __name__ == '__main__':
    raise SystemExit(main())
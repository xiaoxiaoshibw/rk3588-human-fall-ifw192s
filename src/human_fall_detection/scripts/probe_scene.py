#!/usr/bin/env python3
"""Read-only applicability probe for the frozen ground/background artifacts.

Answers a single field question: *do the bound ground and frozen background still
describe this installation?* It subscribes to the live cloud, applies the same
shared functions the node uses (``build_snapshot`` with the effective config),
and reports:

* ground: how many points sit within 5 cm of the plane and the residual
  distribution of those points (a stale/mis-leveled plane shows large residuals
  and a collapsed support fraction);
* background: how many points the frozen background removes versus how many
  foreground points remain (a moved/added object shows persistent foreground);
* candidates: how many geometry candidates survive, and the largest one's size,
  so "empty scene" can be told apart from "static furniture not in the
  background".

It writes JSON only and publishes nothing; it is a diagnostics tool, not a
second algorithm. No semantic claim is made about people: an empty-room check
still needs an actual empty room.
"""

import argparse
import json
import sys
import time

import numpy as np


def _percentile(values, fraction):
    if not len(values):
        return None
    ordered = np.sort(np.asarray(values, dtype=np.float64))
    index = int(round(fraction * (len(ordered) - 1)))
    return float(ordered[max(0, min(index, len(ordered) - 1))])


def summarize(frames):
    """Aggregate per-frame probe records into one applicability summary."""
    if not frames:
        return {'frames': 0, 'verdict': 'NO_DATA'}
    def collect(key):
        return [frame[key] for frame in frames if frame.get(key) is not None]

    ground_fraction = collect('ground_point_fraction')
    ground_p95 = collect('ground_residual_abs_p95_m')
    foreground = collect('foreground_points')
    largest = collect('largest_candidate_points')
    summary = {
        'frames': len(frames),
        'points_median': _percentile(collect('points'), 0.5),
        'foreground_rows_median': _percentile(collect('foreground_rows'), 0.5),
        'ground_frame_eligible': frames[-1].get('ground_frame_eligible'),
        'ground_point_fraction_median': _percentile(ground_fraction, 0.5),
        'ground_point_fraction_min': min(ground_fraction) if ground_fraction else None,
        'ground_residual_abs_p95_m_p50': _percentile(ground_p95, 0.5),
        'ground_residual_abs_p95_m_max': max(ground_p95) if ground_p95 else None,
        'foreground_points_median': _percentile(foreground, 0.5),
        'foreground_points_max': max(foreground) if foreground else None,
        'candidates_median': _percentile(collect('candidates'), 0.5),
        'largest_candidate_points_max': max(largest) if largest else None,
        'frames_with_large_candidate': sum(1 for value in largest if value >= 80),
        'last_frame': frames[-1],
    }
    problems = []
    if not summary['ground_frame_eligible']:
        problems.append('ground_not_eligible_for_frame')
    if summary['ground_point_fraction_median'] is None or \
            summary['ground_point_fraction_median'] < 0.05:
        problems.append('ground_support_too_low')
    if summary['ground_residual_abs_p95_m_p50'] is not None and \
            summary['ground_residual_abs_p95_m_p50'] > 0.05:
        problems.append('ground_residual_too_large')
    if summary['frames_with_large_candidate'] == len(frames) and len(frames) >= 5:
        problems.append('persistent_large_foreground_object')
    summary['problems'] = problems
    summary['verdict'] = 'CONSISTENT' if not problems else 'REVIEW'
    summary['caveat'] = ('Consistency is software/geometry evidence for these frozen '
                         'artifacts; it is not a physical leveling verification and '
                         'says nothing about human identity or fall effect.')
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--config', required=True,
                        help='effective node YAML (same file the node runs with)')
    parser.add_argument('--perception', required=True,
                        help='perception YAML (same file the node runs with)')
    parser.add_argument('--frames', type=int, default=30)
    parser.add_argument('--timeout', type=float, default=30.0)
    parser.add_argument('--out', required=True)
    parser.add_argument('--jsonl', default=None)
    args = parser.parse_args(argv)

    sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parents[1]))
    sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parent))
    from human_fall_node import load_ground_context, load_yaml
    from core.lidar_candidates import (build_snapshot, foreground_mask,
                                       ground_frame_eligible, ground_plane_basis,
                                       resolve_settings)
    from sensor_health import _load_xyz_from_cloud, stamp_pair

    config = load_yaml(args.config)
    config_dir = str(__import__('pathlib').Path(args.config).resolve().parent)
    ground, calibration, background = load_ground_context(
        config.get('geometry', {}), config_dir)
    if calibration is not None:
        ground = calibration.get('ground')
    # The probe must use the same candidate settings as the node, otherwise its
    # foreground/candidate numbers describe a different pipeline.
    settings = resolve_settings((load_yaml(args.perception).get('candidates') or {}))

    import rospy
    from sensor_msgs.msg import PointCloud2

    topics = config.get('topics', {})
    cloud_topic = topics.get('cloud', '/innolidar_points')
    expected_frame = (config.get('checks') or {}).get('expected_cloud_frame') or 'innolidar'

    xyz_from_cloud, calibration_error = _load_xyz_from_cloud()
    if xyz_from_cloud is None:
        print('point-cloud decoder unavailable: %s' % calibration_error, file=sys.stderr)
        return 2

    frames = []
    state = {'done': False}

    def on_cloud(msg):
        if state['done'] or len(frames) >= args.frames:
            return
        try:
            points = xyz_from_cloud(msg, 0.0, preserve_rows=True)
        except (ValueError, calibration_error) as exc:  # type: ignore[misc]
            print('decode failed: %s' % exc, file=sys.stderr)
            return
        frame_id = msg.header.frame_id or None
        if points is None or not len(points):
            record = {'points': 0, 'reason': 'empty_cloud', 'frame_id': frame_id}
            frames.append(record)
            return
        array = np.asarray(points, dtype=np.float64).reshape(-1, 3)
        eligible = ground_frame_eligible(ground, frame_id or expected_frame)
        basis = ground_plane_basis(ground) if eligible else None
        residual = None
        ground_fraction = None
        if basis is not None:
            heights = array @ basis[0] + float(ground['offset_m'])
            absolute = np.abs(heights)
            near = absolute <= 0.05
            ground_fraction = float(np.count_nonzero(near)) / float(len(array))
            if np.any(near):
                residual = {'p50': _percentile(absolute[near], 0.5),
                            'p95': _percentile(absolute[near], 0.95),
                            'max': float(np.max(absolute[near]))}
        mask = foreground_mask(array, background) if background else np.ones(len(array), bool)
        foreground = int(np.count_nonzero(mask))
        stamped = stamp_pair(msg.header.stamp)
        snapshot = None
        try:
            snapshot = build_snapshot(
                array, settings, session_id='scene_probe', time_epoch=time.time(),
                snapshot_id='probe-%d' % len(frames), seq=getattr(msg.header, 'seq', None),
                stamp_secs=stamped[0], stamp_nsecs=stamped[1],
                source_stamp_s=stamped[0] + stamped[1] * 1e-9,
                frame_id=frame_id or expected_frame, ground=ground,
                calibration=calibration, background=background, note='scene probe')
        except Exception as exc:  # noqa: BLE001 - probe must keep going
            record = {'points': int(len(array)), 'reason': 'snapshot_failed: %r' % exc}
            frames.append(record)
            return
        candidates = snapshot.get('candidates') or []
        foreground_rows = len(snapshot.get('foreground_indices') or [])
        largest = max([int(c.get('point_count') or 0) for c in candidates] or [0])
        record = {
            'points': int(len(array)),
            'foreground_rows': foreground_rows,
            'background_removed_rows': int(len(array)) - foreground_rows,
            'frame_id': frame_id,
            'ground_frame_eligible': bool(eligible),
            'ground_point_fraction': ground_fraction,
            'ground_residual_abs_p95_m': None if residual is None else residual['p95'],
            'ground_residual_abs_max_m': None if residual is None else residual['max'],
            'background_removed': int(np.count_nonzero(~mask)),
            'foreground_points': foreground,
            'candidates': len(candidates),
            'rejected_clusters': len(snapshot.get('rejected_clusters') or []),
            'largest_candidate_points': largest,
        }
        frames.append(record)
        if len(frames) >= args.frames:
            state['done'] = True

    rospy.init_node('scene_applicability_probe', anonymous=True, disable_signals=True)
    rospy.Subscriber(cloud_topic, PointCloud2, on_cloud, queue_size=1, buff_size=2 ** 24)
    deadline = time.time() + max(2.0, args.timeout)
    while time.time() < deadline and not state['done']:
        time.sleep(0.05)
    rospy.signal_shutdown('probe done')

    summary = summarize(frames)
    summary.update({
        'kind': 'scene_applicability_probe',
        'schema_version': 1,
        'checked_wall': time.time(),
        'config_path': args.config,
        'cloud_topic': cloud_topic,
        'ground_bound': bool(ground),
        'background_bound': bool(background),
        'requested_frames': args.frames,
        'received_frames': len(frames),
    })
    with open(args.out, 'w', encoding='utf-8') as handle:
        json.dump(summary, handle, sort_keys=True, indent=1)
        handle.write('\n')
    if args.jsonl:
        with open(args.jsonl, 'w', encoding='utf-8') as handle:
            for record in frames:
                handle.write(json.dumps(record, sort_keys=True) + '\n')
    print(json.dumps({'verdict': summary['verdict'], 'problems': summary['problems'],
                      'frames': len(frames),
                      'ground_fraction_median': summary['ground_point_fraction_median'],
                      'out': args.out}))
    return 0 if summary['verdict'] == 'CONSISTENT' else 4


if __name__ == '__main__':
    sys.exit(main())
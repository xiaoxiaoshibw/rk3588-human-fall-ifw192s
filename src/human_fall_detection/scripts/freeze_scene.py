#!/usr/bin/env python3
"""Freeze the site ground + background from an explicitly empty live window.

This is the **initialisation step** for a new site profile; it does not change
any algorithm. It reuses the existing core functions:

* ``core.ground.fit_ground_plane`` -- the same plane fit the calibration tool uses;
* ``core.lidar_candidates.build_background`` -- the same frozen-background builder
  the node consumes (no online update path exists);
* the same display-ground convention as the 2026-10-19 artifact: ``R = [u, v, n]``
  maps the fitted normal to ``+z`` and ``t = (0, 0, offset_m)``. It is a display
  transform only: ``physical_verified`` / ``runtime_eligible`` stay **false**.

Refusals (by design):

* fewer than the requested frames, or frames whose ``(seq, stamp)`` repeats
  (a looping replay must not be frozen as "the site");
* a non-static window: cells learned from the first half do not cover the second
  half (someone walking through, a moving fan, a door). ``--allow-nonstatic``
  exists for diagnostics but should not be used for a field profile;
* a ground fit that is not valid.

Outputs are written with a manifest recording every input frame header, the
settings, the output SHAs and the guard results.
"""

import argparse
import hashlib
import json
import os
import sys
import time

import numpy as np

PACKAGE_DIR = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                           os.pardir))
if PACKAGE_DIR not in sys.path:
    sys.path.insert(0, PACKAGE_DIR)

from core.ground import fit_ground_plane, ground_is_valid
from core.node_runtime import derive_ground_calibration
from core.lidar_candidates import (build_background, foreground_mask,
                                   resolve_settings, _voxel_cells)


def _sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        for block in iter(lambda: handle.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def _write_json(path, payload):
    directory = os.path.dirname(os.path.abspath(path)) or '.'
    os.makedirs(directory, exist_ok=True)
    text = json.dumps(payload, sort_keys=True, indent=1, ensure_ascii=False) + '\n'
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8', newline='\n') as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)
    return _sha256_bytes(text.encode('utf-8'))


def display_ground_from_plane(ground, calibration_id, ground_sha256,
                              source_frame):
    """Build the display-only transform from a fitted plane (existing convention)."""
    normal = np.asarray(ground['normal'], dtype=np.float64)
    normal = normal / np.linalg.norm(normal)
    u = np.array([normal[2], 0.0, -normal[0]], dtype=np.float64)
    if np.linalg.norm(u) < 1e-6:
        u = np.array([1.0, 0.0, 0.0])
    u = u / np.linalg.norm(u)
    u = u - normal * float(np.dot(u, normal))
    u = u / np.linalg.norm(u)
    v = np.cross(normal, u)
    rotation = [list(map(float, u)), list(map(float, v)), list(map(float, normal))]
    offset = float(ground['offset_m'])
    return {
        'kind': 'display_ground_candidate',
        'schema_version': 1,
        'source_frame': source_frame,
        'to_frame': 'ground_local',
        'units': 'm',
        'calibration_id': calibration_id,
        'ground_sha256': ground_sha256,
        'R': rotation,
        't': [0.0, 0.0, offset],
        'reference_axis_source': [1.0, 0.0, 0.0],
        'physical_verified': False,
        'runtime_eligible': False,
        'scope': 'fresh live points; display only; source boxes rigidly transformed',
        'effect_metrics': 'UNKNOWN',
    }


def static_check(frames, settings):
    """Half-window coverage: how much of the later frames the earlier cells explain."""
    if len(frames) < 4:
        return {'checked': False, 'reason': 'too_few_frames'}
    resolved = resolve_settings(settings)
    half = len(frames) // 2
    early = [np.asarray(frame, dtype=np.float64) for frame in frames[:half]]
    late = [np.asarray(frame, dtype=np.float64) for frame in frames[half:]]
    cells = set()
    for array in early:
        if len(array):
            cells.update(map(tuple, _voxel_cells(
                array, resolved['background_cell_m'],
                resolved['background_z_cell_m']).tolist()))
    covered = 0
    total = 0
    for array in late:
        if not len(array):
            continue
        grid = _voxel_cells(array, resolved['background_cell_m'],
                            resolved['background_z_cell_m'])
        unique = set(map(tuple, grid.tolist()))
        total += len(unique)
        covered += sum(1 for cell in unique if cell in cells)
    fraction = (covered / total) if total else None
    return {'checked': True, 'early_frames': half, 'late_frames': len(frames) - half,
            'late_cell_coverage': fraction,
            'static': bool(fraction is not None and fraction >= 0.995)}


def fit_ground_ladder(frames, frame_id, ground_settings_ladder, z_max=0.0):
    """Try the provided ground settings in order; the holdout gate still decides.

    A tilted sensor sees walls and ceiling too, so the floor can cover far less
    than the default 20 % of the whole cloud; the fit input is therefore limited
    to points below the sensor (``z <= z_max``, the same "lower-sensor points"
    region the 2026-10-19 field artifact used) and to ``range_max_m``. The ladder
    only relaxes the *fit input* gate; ``fit_ground_plane`` still validates the
    plane on a holdout set, and the runtime only consumes the resulting plane.
    Every attempt is recorded for the operator.
    """
    attempts = []
    stacked_frames = [np.asarray(frame, dtype=np.float64) for frame in frames
                      if len(frame)]
    for settings in ground_settings_ladder:
        stacked = np.concatenate(stacked_frames, axis=0)
        range_max = settings.get('range_max_m')
        if range_max:
            ranges = np.linalg.norm(stacked, axis=1)
            stacked = stacked[ranges <= float(range_max)]
        if z_max is not None:
            stacked = stacked[stacked[:, 2] <= float(z_max)]
        ground = fit_ground_plane(stacked, settings, frame=frame_id)
        attempts.append({'settings': dict(settings), 'z_max': z_max,
                         'status': ground.get('status'),
                         'reason': ground.get('reason'),
                         'inlier_fraction': ground.get('inlier_fraction'),
                         'point_count': ground.get('point_count')})
        if ground_is_valid(ground):
            return ground, attempts
    return None, attempts


def build_artifacts(frames, frame_id, ground_settings=None, candidate_settings=None,
                    note=None, ground_ladder=None, ground_z_max=0.0):
    """Pure part: fit ground, freeze background (the display transform is separate)."""
    if not frames:
        raise ValueError('no frames to freeze')
    if ground_ladder is None:
        ground_ladder = [ground_settings or {}]
    ground, attempts = fit_ground_ladder(frames, frame_id, ground_ladder,
                                         z_max=ground_z_max)
    if ground is None:
        raise ValueError('ground fit invalid in every attempt: %s'
                         % [(item['reason'], item.get('inlier_fraction'))
                            for item in attempts])
    background = build_background(frames, candidate_settings, frame_id=frame_id,
                                  note=note)
    return ground, background, attempts
    background = build_background(frames, candidate_settings, frame_id=frame_id,
                                  note=note)
    return ground, background, attempts


def collect_live(topic, frames_wanted, timeout_s, min_range_m=0.0):
    """Subscribe once and return decoded frames plus their source headers."""
    import rospy
    from sensor_msgs.msg import PointCloud2
    from sensor_health import _load_xyz_from_cloud, stamp_pair

    xyz_from_cloud, calibration_error = _load_xyz_from_cloud()
    if xyz_from_cloud is None:
        raise RuntimeError('point-cloud decoder unavailable: %s' % calibration_error)

    collected = []

    def on_cloud(msg):
        if len(collected) >= frames_wanted:
            return
        try:
            points = xyz_from_cloud(msg, min_range_m, preserve_rows=True)
        except (ValueError, calibration_error) as exc:  # type: ignore[misc]
            sys.stderr.write('decode failed: %s\n' % exc)
            return
        if points is None or not len(points):
            return
        secs, nsecs = stamp_pair(msg.header.stamp)
        collected.append({
            'points': np.asarray(points, dtype=np.float64).reshape(-1, 3),
            'seq': getattr(msg.header, 'seq', None),
            'stamp_secs': secs, 'stamp_nsecs': nsecs,
            'frame_id': msg.header.frame_id or None,
            'received_wall': time.time(),
        })

    rospy.init_node('hf_freeze_scene', anonymous=True, disable_signals=True)
    rospy.Subscriber(topic, PointCloud2, on_cloud, queue_size=1, buff_size=2 ** 24)
    deadline = time.time() + max(5.0, timeout_s)
    while time.time() < deadline and len(collected) < frames_wanted:
        time.sleep(0.05)
    rospy.signal_shutdown('freeze done')
    return collected


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--config', required=True,
                        help='effective node YAML (topics + frame id)')
    parser.add_argument('--perception', required=True,
                        help='perception YAML (candidate settings for the background)')
    parser.add_argument('--frames', type=int, default=50)
    parser.add_argument('--timeout', type=float, default=90.0)
    parser.add_argument('--out-dir', required=True)
    parser.add_argument('--calibration-id', default=None,
                        help='optional assertion: must match the node-derived ground id')
    parser.add_argument('--note', default=None)
    parser.add_argument('--allow-nonstatic', action='store_true')
    parser.add_argument('--ground-range-max', type=float, default=8.0,
                        help='fit the ground only inside this range (default 8 m)')
    parser.add_argument('--ground-z-max', type=float, default=0.0,
                        help='fit only points below the sensor (sensor-frame z <= this)')
    parser.add_argument('--ground-min-inlier-fractions', default='default,0.1,0.06,0.04',
                        help='ladder of fit-input inlier fractions tried in order')
    args = parser.parse_args(argv)

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from human_fall_node import load_yaml

    config = load_yaml(args.config)
    perception = load_yaml(args.perception)
    topics = config.get('topics', {})
    cloud_topic = topics.get('cloud', '/innolidar_points')
    frame_id = (config.get('checks') or {}).get('expected_cloud_frame') or 'innolidar'
    candidate_settings = perception.get('candidates') or {}

    collected = collect_live(cloud_topic, args.frames, args.timeout)
    if len(collected) < args.frames:
        sys.stderr.write('REFUSING: collected %d/%d frames\n'
                         % (len(collected), args.frames))
        return 4
    keys = [(item['seq'], item['stamp_secs'], item['stamp_nsecs'])
            for item in collected]
    if len(set(keys)) != len(keys):
        sys.stderr.write('REFUSING: repeated (seq, stamp) in the window '
                         '(looping replay is not a site)\n')
        return 4
    frame_ids = {item['frame_id'] for item in collected}
    if frame_ids != {frame_id}:
        sys.stderr.write('REFUSING: frame ids %r do not match %r\n'
                         % (sorted(str(f) for f in frame_ids), frame_id))
        return 4

    frames = [item['points'] for item in collected]
    guard = static_check(frames, candidate_settings)
    if guard.get('checked') and not guard['static'] and not args.allow_nonstatic:
        sys.stderr.write('REFUSING: window is not static (late coverage %s); '
                         'an empty, still scene is required\n'
                         % guard.get('late_cell_coverage'))
        return 4

    ladder = []
    for token in str(args.ground_min_inlier_fractions).split(','):
        token = token.strip()
        if not token:
            continue
        settings = {'range_max_m': float(args.ground_range_max)}
        if token != 'default':
            settings['min_inlier_fraction'] = float(token)
        ladder.append(settings)
    if not ladder:
        ladder = [{'range_max_m': float(args.ground_range_max)}]
    args.ground_ladder = ladder

    os.makedirs(args.out_dir, exist_ok=True)
    ground_path = os.path.join(args.out_dir, 'ground_candidate.json')
    background_path = os.path.join(args.out_dir, 'declared_empty_background.json')
    display_path = os.path.join(args.out_dir, 'display_ground.json')
    manifest_path = os.path.join(args.out_dir, 'FREEZE_MANIFEST.json')

    ground, background, ground_attempts = build_artifacts(
        frames, frame_id, candidate_settings=candidate_settings,
        ground_ladder=args.ground_ladder, ground_z_max=args.ground_z_max,
        note=args.note or 'frozen from %d live frames via freeze_scene.py' % len(frames))
    calibration = derive_ground_calibration(ground, frame_id)
    if calibration is None:
        parser.error('could not derive the node ground calibration')
    calibration_id = calibration['calibration_id']
    if args.calibration_id is not None and args.calibration_id != calibration_id:
        parser.error('--calibration-id must match the node-derived id: %s'
                     % calibration_id)
    ground_sha = _write_json(ground_path, ground)
    background_sha = _write_json(background_path, background)
    if _sha256_file(ground_path) != ground_sha:
        sys.stderr.write('REFUSING: ground file hash is not stable\n')
        return 5
    display = display_ground_from_plane(ground, calibration_id, ground_sha, frame_id)
    display_sha = _write_json(display_path, display)

    # Post-freeze residual on the same window: a still, empty scene should leave
    # almost nothing after the frozen background is applied.
    residuals = []
    for frame in frames:
        mask = foreground_mask(frame, background)
        residuals.append(int(np.count_nonzero(mask)))
    manifest = {
        'schema_version': 1,
        'kind': 'scene_freeze_manifest',
        'created_wall': time.time(),
        'cloud_topic': cloud_topic,
        'frame_id': frame_id,
        'frames_requested': args.frames,
        'frames_used': len(frames),
        'window_seconds': (collected[-1]['received_wall']
                           - collected[0]['received_wall']),
        'static_guard': guard,
        'source_headers': [{k: item[k] for k in
                            ('seq', 'stamp_secs', 'stamp_nsecs', 'frame_id',
                             'received_wall')} for item in collected],
        'candidate_settings': candidate_settings,
        'artifacts': {
            'ground': {'path': os.path.abspath(ground_path), 'sha256': ground_sha},
            'background': {'path': os.path.abspath(background_path),
                           'sha256': background_sha},
            'display_ground': {'path': os.path.abspath(display_path),
                               'sha256': display_sha},
        },
        'ground': {'status': ground.get('status'), 'reason': ground.get('reason'),
                   'inlier_fraction': ground.get('inlier_fraction'),
                   'normal': ground.get('normal'), 'offset_m': ground.get('offset_m'),
                   'valid_region': ground.get('valid_region'),
                   'fit_residual': ground.get('fit_residual'),
                   'holdout_support': ground.get('holdout_support'),
                   'fit_attempts': ground_attempts},
        'background': {'cell_count': background.get('cell_count'),
                       'frame_count': background.get('frame_count'),
                       'point_count': background.get('point_count')},
        'post_freeze_foreground_points': {
            'median': float(np.median(residuals)), 'max': int(max(residuals))},
        'physical_verified': False,
        'runtime_eligible': False,
        'effect_metrics': 'UNKNOWN',
        'note': args.note,
    }
    _write_json(manifest_path, manifest)
    print(json.dumps({
        'ground_sha256': ground_sha, 'background_sha256': background_sha,
        'display_ground_sha256': display_sha,
        'frames': len(frames),
        'static': guard.get('static'),
        'foreground_median': manifest['post_freeze_foreground_points']['median'],
        'foreground_max': manifest['post_freeze_foreground_points']['max'],
        'out_dir': os.path.abspath(args.out_dir)}))
    return 0


if __name__ == '__main__':
    sys.exit(main())

"""单人几何相容性离线摸底：在真实会话上逐帧跑同一条 core 链，再用 human_prior 复算。

链路与 `session_compare.py` 完全一致（同一 `RangeRuntime`、同一非因果背景、同一离线地面），
本脚本只额外做两件事：

1. 对每帧**所有已跟踪轨迹**计算 `core.human_prior.describe`，看单人场景下到底有几条
   轨迹"几何上能是一个人"；
2. 用 `core.human_prior.choose_single` 复算单人选择，与跟踪器实际输出的
   `target_track_id` 逐帧对比，量化"如果接入这个策略，会改变哪些帧、会在哪些帧宁可不锁"。

边界：几何相容不等于人体真值；本脚本不产出准确率/召回率，只产出行为差异计数。

用法：
  python -B pc_apps/range_fall/human_prior_probe.py \
      --session data/sessions/cap_20261028_houdao \
      --out docs/evidence/2026-10-28_single_person_prior/replay_houdao
"""

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
HF = ROOT / 'src' / 'human_fall_detection'
for extra in (str(HF), str(HF / 'scripts'), str(Path(__file__).resolve().parent)):
    if extra not in sys.path:
        sys.path.insert(0, extra)

from core.capture_input import ROW_DTYPE, sha256_file  # noqa: E402
from core.human_prior import choose_single, describe, quick_screen  # noqa: E402
from core.range_contract import binding_tuple, source_binding  # noqa: E402
from core.range_offline import QuantileBackground, fit_declared_plane  # noqa: E402
from core.range_runtime import RangeRuntime  # noqa: E402
from core.range_tracker import SETTINGS  # noqa: E402
import session_compare as sc  # noqa: E402

SCHEMA = 'human_prior_probe_v2'


def describe_tracks(frame, record, ground):
    """把跟踪器当前所有实测轨迹转成 human_prior 条目。

    选择条目只来自 ``status == 'tracked'`` 的轨迹，与生产选择口径一致
    （``range_tracker`` 只把 tracked 轨迹放进 ``prior_entries``）；``tentative``
    轨迹仍写进逐帧明细，但**不参与**策略复算，否则会高估"锁定时可选的目标"。
    """
    entries, details = [], []
    for track in record.get('tracks') or []:
        if not track.get('observed') or track.get('position_predicted'):
            continue
        rows = track.get('source_rows') or []
        if not rows:
            continue
        height = track.get('features') or {}
        detail = {'track_id': track['track_id'], 'status': track.get('status'),
                  'point_count': len(rows),
                  'selection_score': round(float(track.get('selection_score') or 0.0), 4),
                  'center_m': None if track.get('position_m') is None
                  else [round(float(v), 3) for v in track['position_m']],
                  'height_m': None if not height.get('height_m') else
                  {key: None if height['height_m'].get(key) is None
                   else round(float(height['height_m'][key]), 4)
                   for key in ('min', 'p10', 'median', 'p90', 'max')},
                  'horizontal_extent_m': None if height.get('horizontal_extent_m') is None
                  else round(float(height['horizontal_extent_m']), 4)}
        try:
            prior = describe(frame, rows, ground)
        except ValueError as exc:
            detail['error'] = str(exc)
            details.append(detail)
            continue
        detail.update({'class': prior['class'], 'compatible': prior['compatible'],
                       'reason': prior['reason'],
                       'top_m': None if prior['features'] is None else prior['features']['top_m'],
                       'bottom_m': None if prior['features'] is None else prior['features']['bottom_m'],
                       'footprint_area_m2': (None if prior['features'] is None
                                             else prior['features']['footprint_area_m2']),
                       'horizontal_span_m': (None if prior['features'] is None
                                             else prior['features']['horizontal_span_m']),
                       'verticality': None if prior['features'] is None
                       else prior['features']['verticality']})
        details.append(detail)
        if track.get('status') == 'tracked':
            entries.append(dict(track_id=track['track_id'], compatible=prior['compatible'],
                                score=track.get('selection_score') or 0.0,
                                point_count=len(rows), **{'class': prior['class']}))
    return entries, details


def build_inputs(session, limit=None):
    """两遍解码：第一遍只收集背景分位与地面采样（与 session_compare 同口径）。"""
    meta, meta_sha = sc.session_meta(session)
    points_sha = sha256_file(session / 'points.bin')
    grid = sc.load_grid()
    identity = source_binding(session, meta, meta_sha, points_sha, grid)
    identity['azimuth_sha256'] = sha256_file(sc.CALIBRATION / 'ifw192s_azimuth_192x256.csv')
    identity['elevation_sha256'] = sha256_file(sc.CALIBRATION / 'ifw192s_elevation_192x256.csv')
    binding = binding_tuple(identity)
    count = len(meta['frames']) if limit is None else int(limit)
    if not 1 <= count <= len(meta['frames']):
        raise SystemExit('回放帧数越界')
    stack = np.empty((count, grid.shape[0], grid.shape[1]), dtype=np.float32)
    observed = np.zeros(grid.shape, dtype=np.int32)
    ground_sample = []
    for index, info, frame in sc._iter_decoded(session, meta, grid, binding):
        if index >= count:
            break
        stack[index] = frame.range_m.astype(np.float32)
        observed += frame.valid
        if index in (0, count // 4, count // 2, (3 * count) // 4, count - 1):
            rows = frame.source_rows[frame.valid]
            with np.errstate(invalid='ignore'):
                kept = np.isfinite(frame.range_m[frame.valid]) & (frame.range_m[frame.valid] > 0.3)
            ground_sample.append(frame.xyz[rows][kept].astype(np.float64))
        del frame
    if len(ground_sample) < 3:
        raise SystemExit('可用于拟合地面的帧太少')
    ground = fit_declared_plane(np.concatenate(ground_sample), binding=identity,
                                frame=identity['coordinate'][4:], seed=sc.SEED)
    ground['source'] = dict(meta_sha256=meta_sha, points_sha256=points_sha,
                            frame=ground['frame'], coordinate=identity['coordinate'])
    background = QuantileBackground.from_stack(stack, observed, binding=binding,
                                              grid_sha256=grid.sha256)
    del stack, ground_sample
    ground_sha = hashlib.sha256(json.dumps(ground, sort_keys=True, allow_nan=False).encode()).hexdigest()
    runtime = RangeRuntime(grid, identity, empty_prefix_frames=None, ground=ground,
                           ground_sha=ground_sha, background=background)
    return meta, identity, binding, count, ground, runtime


def run_session(session, out, limit=None):
    meta, identity, binding, count, ground, runtime = build_inputs(session, limit)
    frames, component_mix = [], {}
    base_time = meta['frames'][0]['stamp_sec'] + meta['frames'][0]['stamp_nanosec'] / 1e9
    previous_choice = None
    with (session / 'points.bin').open('rb') as stream:
        for index, info in enumerate(meta['frames'][:count]):
            size = info['count_points'] * ROW_DTYPE.itemsize
            raw = stream.read(size)
            if len(raw) != size:
                raise SystemExit('points.bin 在帧 %d 处被截断' % index)
            stamp = info['stamp_sec'] + info['stamp_nanosec'] / 1e9
            result, frame, components = runtime.update(raw, stamp, index)
            record = result['tracking']
            bound = sc_bound(frame, ground)
            # 全组件廉价筛查：量出"这一帧里有多少碎片/平面结构"
            for component in components:
                if not component.get('retained'):
                    continue
                quick = quick_screen(frame.xyz[component['source_rows']], bound)
                component_mix[quick['class']] = component_mix.get(quick['class'], 0) + 1
            entries, details = describe_tracks(frame, record, bound)
            policy = choose_single(entries, previous_track_id=previous_choice)
            if policy['chosen_track_id'] is not None:
                previous_choice = policy['chosen_track_id']
            target = record.get('target_track_id')
            rule = result['rule']
            state = rule['state']
            baseline = rule.get('baseline') or {}
            posture = rule.get('posture') or {}
            target_class = next((d.get('class') for d in details
                                 if d.get('track_id') == target), None)
            row = {
                'i': index,
                't': round(stamp - base_time, 3),
                'tracker_target': target,
                'target_class': target_class,
                'policy_choice': policy['chosen_track_id'],
                'policy_reason': policy['reason'],
                'policy_ambiguous': policy['ambiguous'],
                'compatible_count': policy['compatible_count'],
                'tracks': details,
                'agrees': (target == policy['chosen_track_id']),
                'track_status': state.get('track_status'),
                'continuity': record.get('continuity_track_id'),
                'reset_reason': record.get('reset_reason'),
                'state': state.get('state'),
                'rs': list(state.get('reason_codes') or []),
                'posture': posture.get('state'),
                'posture_duration_s': posture.get('durationSec'),
                'baseline_status': baseline.get('status'),
                'baseline': {'status': baseline.get('status'),
                             'reason': baseline.get('reason'),
                             'sample_count': baseline.get('sample_count'),
                             'ready': bool(baseline.get('baseline'))},
            }
            frames.append(row)
    summary = summarize(frames, component_mix)
    payload = {'schema': SCHEMA, 'session': session.name, 'frames': count,
               'config': {'runtime_sha256': runtime.config_sha,
                          'tracker': dict(SETTINGS),
                          'lock': bool(SETTINGS['single_person_lock']),
                          'human_prior_enabled': bool(SETTINGS['human_prior_enabled']),
                          'drop_fragment_candidates': bool(SETTINGS['drop_fragment_candidates'])},
               'source': {'meta_sha256': identity['meta_sha256'],
                          'points_sha256': identity['points_sha256'],
                          'grid_sha256': identity['grid_sha256']},
               'ground': {'status': ground.get('status'), 'frame': ground.get('frame'),
                          'physical_verified': bool(ground.get('physical_verified')),
                          'offline_only': True},
               'summary': summary, 'rows': frames,
               'honesty': {'human_gt': 'UNKNOWN', 'fall_gt': 'UNKNOWN',
                           'semantic': 'geometric_compatibility_only_not_identity',
                           'note': '几何相容计数不是人体准确率；背景非因果、地面未物理验证'}}
    out.mkdir(parents=True, exist_ok=True)
    with (out / 'PROBE.json').open('w', encoding='utf-8') as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=1, sort_keys=True)
        handle.write('\n')
    print('%-22s frames=%3d target=%3d agree=%3d no_compat=%3d amend=%3d ambiguous=%3d'
          % (session.name, summary['frames'], summary['tracker_target_frames'],
             summary['agree_frames'], summary['policy_no_compatible_frames'],
             summary['policy_differs_frames'], summary['policy_ambiguous_frames']))
    print('%-22s components=%s' % ('', json.dumps(summary['component_mix'], sort_keys=True)))
    print('%-22s target_classes=%s' % ('', json.dumps(summary['tracker_target_classes'], sort_keys=True)))
    return payload


def sc_bound(frame, ground):
    from core.range_features import bound_ground
    return bound_ground(frame, ground)


def summarize(frames, component_mix):
    target_frames = [row for row in frames if row['tracker_target']]
    classes = {}
    for row in target_frames:
        for detail in row['tracks']:
            if detail.get('track_id') == row['tracker_target']:
                classes[detail['class']] = classes.get(detail['class'], 0) + 1
    compatible_hist = {}
    for row in frames:
        key = str(row['compatible_count'])
        compatible_hist[key] = compatible_hist.get(key, 0) + 1

    def histogram(field):
        out = {}
        for row in frames:
            key = str(row.get(field))
            out[key] = out.get(key, 0) + 1
        return out

    return {
        'frames': len(frames),
        'tracker_target_frames': len(target_frames),
        'agree_frames': sum(1 for row in frames if row['agrees'] and row['tracker_target']),
        'policy_differs_frames': sum(1 for row in frames if row['tracker_target']
                                     and row['policy_choice'] != row['tracker_target']),
        'policy_no_compatible_frames': sum(1 for row in frames
                                           if row['policy_reason'] == 'no_human_compatible_target'),
        'policy_ambiguous_frames': sum(1 for row in frames if row['policy_ambiguous']),
        'frames_policy_no_target_but_tracker_has_target': sum(
            1 for row in frames if row['tracker_target'] and row['policy_choice'] is None),
        'frames_policy_target_but_tracker_none': sum(
            1 for row in frames if not row['tracker_target'] and row['policy_choice'] is not None),
        'tracker_target_classes': classes,
        'component_mix': component_mix,
        'compatible_track_histogram': compatible_hist,
        'state_histogram': histogram('state'),
        'posture_histogram': histogram('posture'),
        'target_class_histogram': histogram('target_class'),
        'track_status_histogram': histogram('track_status'),
        'baseline_status_histogram': histogram('baseline_status'),
        'baseline_ready_frames': sum(1 for row in frames if row['baseline']['ready']),
        'target_changed_frames': sum(1 for row in frames
                                     if 'target_changed' in row.get('rs', [])),
        'held_frames': sum(1 for row in frames if row.get('track_status') == 'held'),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--session', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--limit', type=int, default=None)
    parser.add_argument('--lock', action='store_true',
                        help='打开 single_person_lock（含释放/切换去抖）做 A/B')
    parser.add_argument('--no-prior', action='store_true',
                        help='关闭 human_prior 影子计算，回到改动前口径')
    parser.add_argument('--max-point-ratio', type=float, default=None,
                        help='覆盖关联点数比上限（默认 4.0）')
    parser.add_argument('--release-hold-s', type=float, default=None,
                        help='覆盖锁定释放去抖窗口（秒）')
    args = parser.parse_args(argv)
    if args.lock:
        SETTINGS['single_person_lock'] = True
    if args.no_prior:
        SETTINGS['human_prior_enabled'] = False
    if args.max_point_ratio is not None:
        SETTINGS['max_point_ratio'] = float(args.max_point_ratio)
    if args.release_hold_s is not None:
        SETTINGS['release_hold_s'] = float(args.release_hold_s)
    session = args.session.resolve()
    out = args.out.resolve()
    for protected in (ROOT / 'data', ROOT / 'captures'):
        protected = protected.resolve()
        if out == protected or protected in out.parents or out in protected.parents:
            raise SystemExit('输出目录不能落在数据根内：%s' % out)
    run_session(session, out, args.limit)
    return 0


if __name__ == '__main__':
    sys.exit(main())

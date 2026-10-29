"""Read-only full IFW192S replay with sampled target-point inference sidecar."""
import argparse
import hashlib
import json
from pathlib import Path
import time

import numpy as np
import torch

from human_pointset import TargetPointCache
from prepare_human_pointset import dump, sha
from replay_causal_lidar import harness, roi_timing, ReplayPipeline, ROW_DTYPE, POINT_STRIDE_BYTES, percentiles
from train_deep_lidar import CausalPointNet


def run(session_dir, checkpoint, out):
    out.mkdir(parents=True, exist_ok=False)
    torch.set_num_threads(4)
    model = CausalPointNet().eval()
    model.load_state_dict(torch.load(checkpoint, map_location='cpu', weights_only=True))
    session = harness.load_session(session_dir)
    ground = harness.load_ground(harness.DEFAULT_GROUND)
    calibration = sha(harness.DEFAULT_GROUND)
    original = ReplayPipeline.step
    runs = []
    for enabled in [False, True]:
        cache = TargetPointCache()
        digest = hashlib.sha256()
        ready, observed, frame_count = 0, 0, 0
        inference_times = []
        with (session_dir/'points.bin').open('rb') as source, (out/('target_frames.jsonl' if enabled else 'baseline_frames.jsonl')).open('x', encoding='utf-8') as ledger:
            def step(self, cloud, stamp, epoch, index):
                nonlocal ready, observed, frame_count
                frame_count += 1
                frame = session['frames'][index]
                source.seek(frame['offset_points']*POINT_STRIDE_BYTES)
                raw = source.read(frame['count_points']*POINT_STRIDE_BYTES)
                if len(raw) != frame['count_points']*POINT_STRIDE_BYTES:
                    raise ValueError('Truncated raw frame')
                packed = np.frombuffer(raw, dtype=ROW_DTYPE)
                xyz = np.column_stack([packed[k] for k in ['x', 'y', 'z']]).astype(np.float64)
                np.testing.assert_array_equal(xyz, session['points'][frame['offset_points']:frame['offset_points']+frame['count_points']])
                result = original(self, cloud, stamp, epoch, index)
                digest.update(json.dumps({'result': result, 'baseline': self.baseline}, sort_keys=True, allow_nan=False).encode())
                if enabled:
                    track = result['track']
                    rows = result['target_source_rows']
                    record = {'frame': index, 'time_s': stamp, 'target_source_rows': rows, 'track': track}
                    if len(rows) < 10:
                        cache.clear()
                        record['status'] = 'insufficient_observed_target'
                        window = None
                    else:
                        window = cache.push(xyz, rows, stamp, (session['sid'], track['track_id']),
                                            (epoch, track['action_generation'], track['selection_version']),
                                            (calibration, track['calibration_version']),
                                            '%s/frame%d' % (session['sid'], index),
                                            locked=track['track_status'] == 'locked', predicted=track['position_predicted'])
                        record['status'] = 'ready' if window is not None else 'warming_or_unobserved'
                    record['sample_source_rows'] = cache.last_sample_rows.tolist()
                    record['cached_frames'] = len(cache.frames)
                    if len(cache.frames):
                        observed += 1
                        np.testing.assert_array_equal(cache.frames[-1], xyz[cache.last_sample_rows].astype(np.float32))
                    if window is not None:
                        began = time.perf_counter()
                        with torch.no_grad():
                            probability = torch.softmax(model(torch.from_numpy(window[None]))[0, -1], dim=-1).numpy()
                        inference_times.append(time.perf_counter()-began)
                        ready += 1
                        record.update(window_sha256=hashlib.sha256(window.tobytes()).hexdigest(),
                                      probabilities=probability.tolist(), prediction=int(probability.argmax())+1)
                    ledger.write(json.dumps(record, allow_nan=False)+'\n')
                else:
                    ledger.write(json.dumps({'frame': index, 'output_prefix_sha256': digest.hexdigest()})+'\n')
                return result
            ReplayPipeline.step = step
            try:
                roi_timing.replay(session, harness.build_arm_settings('A'), ground, 50, len(session['frames']))
            finally:
                ReplayPipeline.step = original
        runs.append({'sidecar': enabled, 'frames': frame_count, 'observed_frames': observed, 'ready_windows': ready,
                     'complete_output_sha256': digest.hexdigest(), 'inference_pc': percentiles(inference_times)})
        print(json.dumps(runs[-1]), flush=True)
    if runs[0]['complete_output_sha256'] != runs[1]['complete_output_sha256']:
        raise AssertionError('Sidecar changed geometry chain')
    summary = {'session': session['sid'], 'meta_sha256': sha(session_dir/'meta.json'),
               'points_sha256': sha(session_dir/'points.bin'), 'checkpoint_sha256': sha(checkpoint),
               'checkpoint': str(checkpoint), 'calibration_sha256': calibration, 'runs': runs,
               'complete_geometry_parity': True, 'point_budget': 256, 'window_frames': 30, 'max_gap_s': 0.5,
               'scope': 'frozen WHOLE-SCENE model on observed target input; distribution-shift plumbing diagnostic only',
               'background': 'first 50 frames declared empty by existing development harness; not independent GT',
               'IFW192S_action_accuracy': 'UNKNOWN', 'fall_recall': 'UNKNOWN', 'sensor_alignment': 'UNKNOWN',
               'board_performance': 'UNKNOWN', 'deployment': 'NOT_DEPLOYED'}
    dump(out/'SUMMARY.json', summary)
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--session', type=Path, required=True)
    parser.add_argument('--checkpoint', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    run(args.session, args.checkpoint, args.output)

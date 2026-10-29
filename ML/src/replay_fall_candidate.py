"""Raw IFW192S full-chain replay with the binary fall sidecar; never sends alarms."""
import argparse
import hashlib
import json
from pathlib import Path
import time

import numpy as np

from fall_candidate_runtime import load_candidate_runtime
from prepare_human_pointset import dump, sha
from replay_causal_lidar import harness, roi_timing, ReplayPipeline, ROW_DTYPE, POINT_STRIDE_BYTES, percentiles


def run(session_dir, manifest, out):
    out.mkdir(parents=True, exist_ok=False)
    session = harness.load_session(session_dir)
    ground = harness.load_ground(harness.DEFAULT_GROUND)
    calibration = sha(harness.DEFAULT_GROUND)
    original = ReplayPipeline.step
    runs, raw_inputs = [], []
    for enabled in [False, True]:
        runtime = load_candidate_runtime(manifest, ground=ground)
        digest = hashlib.sha256()
        timings, events, predictions = [], [], 0
        with (session_dir/'points.bin').open('rb') as source, (out/('candidate_frames.jsonl' if enabled else 'baseline_frames.jsonl')).open('x', encoding='utf-8') as ledger:
            def step(self, cloud, stamp, epoch, index):
                nonlocal predictions
                frame = session['frames'][index]
                source.seek(frame['offset_points']*POINT_STRIDE_BYTES)
                raw = source.read(frame['count_points']*POINT_STRIDE_BYTES)
                if len(raw) != frame['count_points']*POINT_STRIDE_BYTES:
                    raise ValueError('Truncated input')
                packed = np.frombuffer(raw, dtype=ROW_DTYPE)
                xyz = np.column_stack([packed[k] for k in ['x', 'y', 'z']]).astype(np.float64)
                np.testing.assert_array_equal(xyz, session['points'][frame['offset_points']:frame['offset_points']+frame['count_points']])
                result = original(self, cloud, stamp, epoch, index)
                digest.update(json.dumps({'result': result, 'baseline': self.baseline}, sort_keys=True, allow_nan=False).encode())
                record = {'frame': index, 'output_prefix_sha256': digest.hexdigest()}
                if enabled:
                    track, rows = result['track'], np.asarray(result['target_source_rows'], dtype=np.int64)
                    if (rows < 0).any() or (rows >= len(xyz)).any() or len(np.unique(rows)) != len(rows):
                        raise ValueError('Invalid target provenance')
                    observed = len(rows) >= 10 and track['track_status'] == 'locked' and not track['position_predicted']
                    began = time.perf_counter()
                    prediction = runtime.push(xyz[rows], stamp, (session['sid'], track['track_id']),
                        (epoch, track['action_generation'], track['selection_version']),
                        (calibration, track['calibration_version']), observed=observed)
                    timings.append(time.perf_counter()-began)
                    if prediction['fall_probability'] is not None:
                        predictions += 1
                    if prediction['new_event']:
                        events.append(dict(prediction['new_event'], source_stamp_s=stamp, frame=index))
                    record.update(source_stamp_s=stamp, target_source_rows=rows.tolist(), track=track,
                                  model_output=prediction, geometry_fall=result['fall']['fall_status'])
                    raw_inputs.append({'frame': index, 'raw_sha256': hashlib.sha256(raw).hexdigest()})
                ledger.write(json.dumps(record, allow_nan=False)+'\n')
                return result
            ReplayPipeline.step = step
            try:
                roi_timing.replay(session, harness.build_arm_settings('A'), ground, 50, len(session['frames']))
            finally:
                ReplayPipeline.step = original
        runs.append({'model_enabled': enabled, 'frames': len(session['frames']),
                     'ready_windows': predictions, 'candidate_events': events,
                     'complete_output_sha256': digest.hexdigest(), 'sidecar_pc_timing': percentiles(timings)})
        print(json.dumps({k: v for k, v in runs[-1].items() if k != 'candidate_events'}), flush=True)
    if runs[0]['complete_output_sha256'] != runs[1]['complete_output_sha256']:
        raise AssertionError('Binary sidecar changed complete pipeline output')
    dump(out/'RAW_INPUTS.json', raw_inputs)
    summary = {'sid': session['sid'], 'meta_sha256': sha(session_dir/'meta.json'),
               'points_sha256': sha(session_dir/'points.bin'), 'manifest_sha256': sha(manifest),
               'calibration_sha256': calibration, 'runs': runs, 'complete_geometry_parity': True,
               'background': 'first 50 frames declared empty by existing development harness, not person GT',
               'scope': 'PC raw file decode + full chain + manifest-bound binary candidate; no sensor alignment established',
               'fall_recall': 'UNKNOWN', 'false_alarm_rate': 'UNKNOWN', 'board_performance': 'UNKNOWN',
               'confirmed_enabled': False, 'deployment': 'NOT_DEPLOYED'}
    summary['model_task'] = runtime.manifest['task']
    summary['training_status'] = runtime.manifest.get('training_status', 'legacy_model')
    dump(out/'SUMMARY.json', summary)
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--session', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    run(args.session, args.manifest, args.output)

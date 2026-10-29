"""Read raw IFW192S session twice; verify geometric sidecar leaves full chain intact."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

import numpy as np

from fall_candidate_runtime import file_sha256
from fall_geometry import FallGeometryRuntime

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src/human_fall_detection'))
sys.path.insert(0, str(ROOT / 'src/human_fall_detection/scripts'))
import roi_ablation as harness
import roi_timing
from core.pipeline import ReplayPipeline
from core.capture_input import ROW_DTYPE, POINT_STRIDE_BYTES


def run(session_dir, out):
    out.mkdir(parents=True, exist_ok=False)
    session = harness.load_session(session_dir)
    ground = harness.load_ground(harness.DEFAULT_GROUND)
    calibration_sha = file_sha256(harness.DEFAULT_GROUND)
    original = ReplayPipeline.step
    runs = []
    for enabled in (False, True):
        runtime = FallGeometryRuntime(ground['normal'], ground['offset_m'])
        digest, events, times, states = hashlib.sha256(), [], [], {}
        with (session_dir / 'points.bin').open('rb') as source, \
                (out / ('geometry_frames.jsonl' if enabled else 'baseline_frames.jsonl')).open('x', encoding='utf-8') as ledger:
            def step(self, cloud, stamp, epoch, index):
                frame = session['frames'][index]
                source.seek(frame['offset_points'] * POINT_STRIDE_BYTES)
                raw = source.read(frame['count_points'] * POINT_STRIDE_BYTES)
                if len(raw) != frame['count_points'] * POINT_STRIDE_BYTES:
                    raise ValueError('Truncated raw frame')
                packed = np.frombuffer(raw, dtype=ROW_DTYPE)
                xyz = np.column_stack([packed[k] for k in ('x', 'y', 'z')]).astype(np.float64)
                np.testing.assert_array_equal(xyz, session['points'][frame['offset_points']:frame['offset_points']+frame['count_points']])
                result = original(self, cloud, stamp, epoch, index)
                digest.update(json.dumps(dict(result=result, baseline=self.baseline), sort_keys=True, allow_nan=False).encode())
                record = dict(frame=index, timestamp_s=stamp, output_prefix_sha256=digest.hexdigest())
                if enabled:
                    track = result['track']
                    rows = np.asarray(result['target_source_rows'], dtype=np.int64)
                    if (rows < 0).any() or (rows >= len(xyz)).any() or len(np.unique(rows)) != len(rows):
                        raise ValueError('Invalid target row provenance')
                    observed = track['track_status'] == 'locked' and not track['position_predicted']
                    binding = ((session['sid'], track['track_id']),
                               (epoch, track['action_generation'], track['selection_version']),
                               (calibration_sha, track['calibration_version']))
                    began = time.perf_counter()
                    output = runtime.push(xyz[rows], stamp, *binding, observed=observed)
                    times.append(time.perf_counter()-began)
                    states[output['state']] = states.get(output['state'], 0) + 1
                    if output['new_event']:
                        events.append(output['new_event'])
                    record.update(target_source_rows=rows.tolist(), binding=binding, track=track,
                                  raw_sha256=hashlib.sha256(raw).hexdigest(), geometry=output)
                ledger.write(json.dumps(record, allow_nan=False)+'\n')
                return result
            ReplayPipeline.step = step
            try:
                roi_timing.replay(session, harness.build_arm_settings('A'), ground, 50, len(session['frames']))
            finally:
                ReplayPipeline.step = original
        runs.append(dict(sidecar=enabled, frames=len(session['frames']), states=states, events=events,
                         complete_output_sha256=digest.hexdigest(),
                         pc_sidecar_p95_ms=float(np.percentile(times, 95)*1000) if times else None))
        print(json.dumps(runs[-1]), flush=True)
    if runs[0]['complete_output_sha256'] != runs[1]['complete_output_sha256']:
        raise AssertionError('Geometry sidecar changed production chain')
    summary = dict(session=session['sid'], meta_sha256=file_sha256(session_dir/'meta.json'),
                   points_sha256=file_sha256(session_dir/'points.bin'), calibration_sha256=calibration_sha,
                   settings=runtime.settings, runs=runs, complete_output_parity=True,
                   frame_schema='fall_geometry_frames_v1',
                   frames_sha256=file_sha256(out/'geometry_frames.jsonl'),
                   background='existing development harness declares first 50 frames empty; not person GT',
                   calibration_scope='existing development plane; physical applicability UNKNOWN',
                   IFW192S_effectiveness='UNKNOWN', board_performance='UNKNOWN', deployed=False,
                   source_sha256={p.name: file_sha256(p) for p in
                                  (Path(__file__), Path(__file__).with_name('fall_geometry.py'))})
    with (out/'SUMMARY.json').open('x', encoding='utf-8') as stream:
        json.dump(summary, stream, ensure_ascii=False, indent=2, allow_nan=False)
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--session', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    run(args.session, args.output)

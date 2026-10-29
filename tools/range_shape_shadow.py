"""2D形状离线旁路：固定原W1/W2/规则，保存描述子与逐帧摘要，不复制点云。"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import platform
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src/human_fall_detection'))
sys.path.insert(0, str(ROOT/'src/human_fall_detection/scripts'))
from core.capture_input import ROW_DTYPE, sha256_file
from core.range_contract import source_binding, load_ground
from core.range_image import ScanGrid
from core.range_runtime import RangeRuntime, serial
from core.range_shape import ShapeObserver
from replay_range_frontend import session_meta, CALIBRATION


def digest(value):
    return hashlib.sha256(serial(value).encode()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')


def distribution(values):
    return dict(n=len(values), **{k:float(np.percentile(values, p)) if values else None
        for k, p in (('p50', 50), ('p95', 95), ('p99', 99), ('max', 100))})


class ExploratoryP98:
    """仅复现无空场126帧的非因果研究条件，不可冒称在线背景。"""
    def __init__(self, grid, binding, session, frames):
        stack = []
        with (session/'points.bin').open('rb') as stream:
            for info in frames:
                stream.seek(info['offset_points']*ROW_DTYPE.itemsize)
                stack.append(grid.decode(stream.read(info['count_points']*ROW_DTYPE.itemsize), binding).range_m)
        stack = np.stack(stack)
        known = np.isfinite(stack).any(axis=0)
        self.background = np.full(grid.shape, np.nan)
        self.background[known] = np.nanpercentile(stack[:, known], 98, axis=0)

    def foreground(self, frame):
        with np.errstate(invalid='ignore'):
            mask = frame.valid & np.isfinite(self.background) & (self.background-frame.range_m > .30)
        return dict(mask=mask, status='exploratory_noncausal_p98')


def run(session, out, *, empty_prefix_frames=None, ground_path=None, limit=None, rounds=3,
        exploratory_p98=False):
    session, out = Path(session).resolve(), Path(out).resolve()
    if any(out == p or p in out.parents or out in session.parents
           for p in (session, (ROOT/'data').resolve(), (ROOT/'captures').resolve())):
        raise ValueError('output must be outside source data')
    if type(rounds) is not int or rounds < 1:
        raise ValueError('rounds must be positive')
    meta, msha = session_meta(session)
    count = len(meta['frames']) if limit is None else limit
    if type(count) is not int or not 1 <= count <= len(meta['frames']):
        raise ValueError('invalid frame count')
    if exploratory_p98:
        if empty_prefix_frames is not None:
            raise ValueError('p98 exploration must not declare an empty prefix')
        prefix = 1
    else:
        prefix = empty_prefix_frames
        if type(prefix) is not int or not 1 <= prefix < count:
            raise ValueError('explicit empty prefix required for causal mode')
    grid = ScanGrid.from_csv(CALIBRATION/'ifw192s_azimuth_192x256.csv',
                             CALIBRATION/'ifw192s_elevation_192x256.csv')
    identity = source_binding(session, meta, msha, sha256_file(session/'points.bin'), grid)
    identity.update(azimuth_sha256=sha256_file(CALIBRATION/'ifw192s_azimuth_192x256.csv'),
                    elevation_sha256=sha256_file(CALIBRATION/'ifw192s_elevation_192x256.csv'))
    ground = load_ground(ground_path, identity) if ground_path else None
    ground_sha = sha256_file(ground_path) if ground_path else None
    paths = [Path(__file__), ROOT/'src/human_fall_detection/scripts/replay_range_frontend.py',
             *sorted((ROOT/'src/human_fall_detection/core').glob('*.py')),
             CALIBRATION/'ifw192s_azimuth_192x256.csv', CALIBRATION/'ifw192s_elevation_192x256.csv',
             session/'meta.json', session/'points.bin']
    if ground_path:
        paths += [Path(ground_path), Path(ground['provenance']['source'])]
    pinned = {str(p.resolve()):sha256_file(p) for p in paths}
    out.mkdir(parents=True, exist_ok=False)
    write_json(out/'CONFIG.json', dict(source_binding=identity, source_sha256=pinned,
        ground_sha256=ground_sha, frames=count, rounds=rounds, empty_prefix_frames=empty_prefix_frames,
        noncausal_exploration=exploratory_p98, background_scope_frames=len(meta['frames']) if exploratory_p98 else prefix,
        mode='shadow_only', python=sys.version, numpy=np.__version__, platform=platform.platform(),
        shape_window_s=1.2, shape_max_gap_s=.3, history_capacity=128,
        timing_scope='baseline then shadow rounds, serial; source hashes/mutation audit/JSON outside stage timers; no display or device latency'))
    bg = None
    # 绑定复用运行时自身生成的tuple，避免第二套身份序列化。
    template = RangeRuntime(grid, identity, empty_prefix_frames=prefix, ground=ground, ground_sha=ground_sha)
    if exploratory_p98:
        bg = ExploratoryP98(grid, template.binding, session, meta['frames'])
    first_ns = meta['frames'][0]['stamp_sec']*10**9+meta['frames'][0]['stamp_nanosec']
    baseline, expected_shadow, runs = [], [], []
    for iteration in range(rounds+1):
        enabled = iteration > 0
        runtime = RangeRuntime(grid, identity, empty_prefix_frames=prefix, ground=ground, ground_sha=ground_sha)
        if bg is not None:
            runtime.background = bg
        observer = ShapeObserver()
        timings, events, differences = [], Counter(), []
        inference = hashlib.sha256()
        name = 'shadow_%d'%iteration if enabled else 'baseline'
        with (session/'points.bin').open('rb') as stream, (out/(name+'.jsonl')).open('x', encoding='utf-8') as ledger:
            for i, info in enumerate(meta['frames'][:count]):
                stream.seek(info['offset_points']*ROW_DTYPE.itemsize)
                packed = stream.read(info['count_points']*ROW_DTYPE.itemsize)
                stamp = (info['stamp_sec']*10**9+info['stamp_nanosec']-first_ns)/1e9
                result, frame, components = runtime.update(packed, stamp, i)
                record = result['tracking']
                pure = dict(tracking=record, rule=result['rule'], status=result['status'])
                before = digest(pure)
                row_sha = hashlib.sha256(np.asarray(record['target_source_rows'], dtype='<i8').tobytes()).hexdigest()
                array_sha = hashlib.sha256(frame.source_rows.tobytes()+frame.valid.tobytes()+frame.range_m.tobytes()+frame.xyz.tobytes()).hexdigest()
                inference.update(record['inference_sha256'].encode())
                shadow, elapsed = None, None
                if enabled:
                    start = time.perf_counter()
                    labels = np.full(grid.shape, -1, dtype=np.int32)
                    for c in components:
                        labels.ravel()[c['cells']] = c['component_id']
                    shadow = observer.update(frame, record, labels)
                    elapsed = (time.perf_counter()-start)*1000
                    after_arrays = hashlib.sha256(frame.source_rows.tobytes()+frame.valid.tobytes()+frame.range_m.tobytes()+frame.xyz.tobytes()).hexdigest()
                    if digest(pure) != before or array_sha != after_arrays:
                        raise ValueError('shadow mutated baseline record or decoded arrays')
                    if baseline[i] != before:
                        differences.append(dict(frame=i, kind='baseline_output'))
                    if iteration == 1:
                        expected_shadow.append(digest(shadow))
                    elif expected_shadow[i] != digest(shadow):
                        differences.append(dict(frame=i, kind='shadow_repeat'))
                    events['available' if shadow['available'] else 'unavailable'] += 1
                    if shadow['available']:
                        s = shadow['shape']
                        events['boundary_contact'] += int(s['touches_grid_boundary'])
                        events['multiple_inherited_components'] += int(s['fragment_count'] > 1)
                else:
                    baseline.append(before)
                cost = result['timings']
                timings.append(dict(frame=i, status=result['status'], event_chain_ms=cost['event_chain_ms'],
                    background_init_ms=cost['background_init_ms'], shape_shadow_ms=elapsed,
                    available=shadow['available'] if enabled else False))
                ledger.write(serial(dict(frame=i, time_s=stamp, baseline_sha256=before,
                    inference_sha256=record['inference_sha256'], target_rows_sha256=row_sha,
                    target_track_id=record['target_track_id'], target_points=len(record['target_source_rows']),
                    rule_state=result['rule']['state']['state'], shape_shadow=shadow, timings=timings[-1]))+'\n')
        ready = [t for t in timings if t['status'] != 'prefix_warmup']
        runs.append(dict(name=name, differences=differences, counts=dict(events), inference_sha256=inference.hexdigest(),
            event_chain_ms=distribution([t['event_chain_ms'] for t in ready]),
            shape_shadow_ms=distribution([t['shape_shadow_ms'] for t in ready]) if enabled else None,
            measured_shape_shadow_ms=distribution([t['shape_shadow_ms'] for t in ready if t['available']]) if enabled else None,
            event_plus_shadow_ms=distribution([t['event_chain_ms']+t['shape_shadow_ms'] for t in ready]) if enabled else None,
            background_init_ms=distribution([t['background_init_ms'] for t in timings])))
    if pinned != {p:sha256_file(p) for p in pinned}:
        raise ValueError('input/source changed during replay')
    summary = dict(software_status='PASS' if not any(r['differences'] for r in runs) else 'FAIL',
        source_binding=identity, frames=count, noncausal_exploration=exploratory_p98, runs=runs,
        human_completeness_occlusion_fall_accuracy='UNKNOWN', board_performance='UNKNOWN',
        scope='W1/W2 shadow, not production B0 comparison; no rule gates changed')
    write_json(out/'SUMMARY.json', summary)
    return summary


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--session', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--empty-prefix-frames', type=int)
    p.add_argument('--ground', type=Path)
    p.add_argument('--limit', type=int)
    p.add_argument('--rounds', type=int, default=3)
    p.add_argument('--exploratory-p98', action='store_true')
    a = p.parse_args()
    result = run(a.session, a.out, empty_prefix_frames=a.empty_prefix_frames, ground_path=a.ground,
                 limit=a.limit, rounds=a.rounds, exploratory_p98=a.exploratory_p98)
    print(serial(dict(status=result['software_status'], frames=result['frames'])))


if __name__ == '__main__':
    main()

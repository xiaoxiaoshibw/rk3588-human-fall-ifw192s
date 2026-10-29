"""Offline RAW-only TCMS diagnostic. All writes require a new evidence folder."""
import argparse
from collections import Counter
import gzip
import json
from pathlib import Path
import platform
import sys
import time
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CONTRACT = ROOT/'sidequests/human_fusion_lab_next/pointset/r01/next_contract.py'
sys.path.insert(0, str(CONTRACT.parent))
from next_contract import validate_meta, sha
from tcms import Window, support, calibrate, active

EMPTY = 'cap_20261014_221808'
SESSIONS = ['cap_20261013_'+s for s in ('082623', '082717', '082829', '082906', '083044', '083120', '083218', '083254')]


def write(path, value):
    with path.open('x', encoding='utf8') as f:
        json.dump(value, f, ensure_ascii=False, allow_nan=False, indent=2)


def load(folder):
    meta_path, points_path = folder/'meta.json', folder/'points.bin'
    binding = {str(p): sha(p) for p in (meta_path, points_path)}
    meta = json.loads(meta_path.read_text(encoding='utf8'))
    validate_meta(meta, points_path.stat().st_size)
    if meta.get('session_id') != folder.name:
        raise ValueError('Session ID mismatch')
    layout = meta.get('point_layout', {})
    if (layout.get('fields', [])[:3] != ['x', 'y', 'z'] or
            layout.get('dtypes', [])[:3] != ['<f4']*3 or layout.get('stride_bytes') != 28 or
            layout.get('endian') != 'little'):
        raise ValueError('Unsupported XYZ layout; unknown bytes never interpreted')
    buffer = np.memmap(points_path, dtype='u1', mode='r')
    xyz = np.ndarray((meta['total_points'], 3), dtype='<f4', buffer=buffer, strides=(28, 4))
    return meta, xyz, binding


def summarize(values):
    if not len(values): return {'n': 0, 'p50': None, 'p95': None, 'p99': None}
    q = np.quantile(values, [.5, .95, .99])
    return dict(n=len(values), p50=float(q[0]), p95=float(q[1]), p99=float(q[2]))


def band(tile, size):
    return min(2, int(np.linalg.norm((np.array(tile)+.5)*round(1.2/size)*size)//4))


def noise_probe(cache, stamps, size):
    """Exploratory hit statistics; no free-space, phase or physical point matches."""
    results = []
    for r in range(3):
        observed = [{v for tile, (cells, _) in f.items() if band(tile, size) == r for v in cells}
                    for f in cache]
        counts = np.array([len(v) for v in observed], dtype=float)
        by_lag = {}
        for lag in (1, 5, 10, 20):
            overlap, dt = [], []
            for i in range(lag, len(observed)):
                a, b = observed[i-lag], observed[i]
                if a or b:
                    overlap.append(len(a & b)/len(a | b))
                    dt.append(stamps[i]-stamps[i-lag])
            by_lag[str(lag)] = dict(hit_jaccard=summarize(overlap), delta_seconds=summarize(dt))
        spectrum = np.abs(np.fft.rfft(counts-counts.mean()))**2
        peak = int(np.argmax(spectrum[1:])+1) if len(spectrum) > 1 and np.any(spectrum[1:]) else None
        results.append(dict(range_bin=r, observed_cells=summarize(counts), lags=by_lag,
                            exploratory_peak_period_s=len(counts)*float(np.median(np.diff(stamps)))/peak if peak else None,
                            phase_status='UNKNOWN_NO_BEAM_PHASE; FFT_APPROX_MEDIAN_DT_NOT_PHASE_PROOF'))
    return results


def process(cache, stamps, indices, size, window, thresholds, metrics, members, sid, frames):
    state = Window(size, window)
    collected, timing, durations = [], [], []
    counts, active_frames = Counter(), Counter()
    for fi in indices:
        started = time.perf_counter()
        rows, status = state.update(cache[fi], stamps[fi])
        timing.append((time.perf_counter()-started)*1000)
        counts[status['state']] += 1
        counts['unknown_tiles'] += status.get('unknown_current_tiles', len(cache[fi]))
        counts['eligible_tiles'] += len(rows)
        if status['span_s'] is not None: durations.append(status['span_s'])
        current = dict(fi=fi, time=stamps[fi], status=status, rows=rows)
        metrics.write(json.dumps(current, allow_nan=False, separators=(',', ':'))+'\n')
        collected.extend(rows)
        if thresholds is None: continue
        any_active = Counter()
        for row in rows:
            methods = [m for m in ('B1', 'B2', 'B3') if active(row, thresholds, m)]
            for method in methods:
                counts[method+'_active_tiles'] += 1
                any_active[method] = 1
            if 'B3' not in methods: continue
            ids = cache[fi][tuple(row['tile'])][1].astype('<u4')
            record = dict(session_id=sid, frame_index=fi, device_time=stamps[fi], tile=row['tile'],
                          methods=methods, semantic='UNKNOWN', interpretation='MOTION_HYPOTHESIS_REGION_NOT_POINTWISE_MOTION',
                          frame_offset_points=frames[fi]['offset_points'], source_rows=ids.tolist(),
                          member_sha256=__import__('hashlib').sha256(ids.tobytes()).hexdigest(), scores=row)
            members.write(json.dumps(record, allow_nan=False, separators=(',', ':'))+'\n')
        active_frames.update(any_active)
    eligible = counts['eligible_tiles']
    result = dict(counts=dict(counts), active_frames=dict(active_frames), scored_frames=counts['SCORED'],
                  activation_rate_per_eligible_tile={m: counts[m+'_active_tiles']/eligible if eligible else None
                                                     for m in ('B1', 'B2', 'B3')},
                  algorithm_ms=summarize(timing), observed_horizon_s=summarize(durations),
                  score_distributions={str(r): {m: summarize([x[m] for x in collected if x['range_bin'] == r and x[m] is not None])
                                               for m in ('B1', 'B2', 'B3')} for r in range(3)})
    return collected, result


def run(output):
    # Only a direct child of this evidence item may receive experiment writes.
    evidence = ROOT/'docs/human_fall/evidence/2026-10-16_hfus_tcms_01_r1'
    output = output.resolve()
    if output.parent != evidence.resolve(): raise ValueError('Output must be new direct child of TCMS evidence')
    output.mkdir(exist_ok=False)
    started = time.perf_counter()
    bindings = {str(p): sha(p) for p in (HERE/'tcms.py', HERE/'run_experiment.py', CONTRACT)}
    manifest = dict(schema='hfus-tcms/1', coordinate='RAW_METERS_NO_LEVELING_NO_PHYSICAL_Z_CLAIM',
                    unknown_fields='bytes12..27 opaque', grid=[.12, .15], windows=[5, 10, 20],
                    window_definition='two equal adjacent windows, each W frames; causal horizon 2W frames',
                    penalty=.03, tile_m=1.2, range_bins_m=[0, 4, 8, 12], minimum_hit_cells=8,
                    max_gap_s=.5, calibration='CAL per-band p99; strict greater; <30 samples UNKNOWN',
                    python=platform.python_version(), numpy=np.__version__, code=bindings.copy(),
                    sources={}, split={}, independent_test_sessions=[], trusted_human_gt=0,
                    empty_label='HISTORICAL_DECLARATION_NOT_CURRENT_HUMAN_REVIEW',
                    production_integration='NOT_RUN', data_usage='ALL_DIAGNOSTIC_PRIOR_DEVELOPMENT_EXPOSURE')
    summary, noise = {}, {}
    limits = {}
    for sid in [EMPTY]+SESSIONS:
        print('READ', sid, flush=True)
        meta, xyz, hashes = load(ROOT/'data/sessions'/sid)
        manifest['sources'][sid] = hashes
        bindings.update(hashes)
        frames = meta['frames']
        stamps = [f['stamp_sec']+f['stamp_nanosec']*1e-9 for f in frames]
        manifest['split'][sid] = ({'FIT': [0, len(frames)//3], 'CAL': [len(frames)//3, 2*len(frames)//3],
                                   'REPORT': [2*len(frames)//3, len(frames)]} if sid == EMPTY else {'DIAGNOSTIC': [0, len(frames)]})
        for size in manifest['grid']:
            cache, preprocessing, rejected = [], [], []
            for frame in frames:
                start = frame['offset_points']; stop = start+frame['count_points']
                t0 = time.perf_counter()
                hits, invalid = support(xyz[start:stop], size)
                preprocessing.append((time.perf_counter()-t0)*1000)
                cache.append(hits); rejected.append(invalid)
            if sid == EMPTY:
                noise[str(size)] = noise_probe(cache, stamps, size)
            for window in manifest['windows']:
                tag = 'v{}_w{}'.format(size, window)
                for split, (a, b) in manifest['split'][sid].items():
                    with gzip.open(output/(sid+'_'+tag+'_'+split+'_metrics.jsonl.gz'), 'wt', encoding='utf8') as metrics, \
                         gzip.open(output/(sid+'_'+tag+'_'+split+'_members.jsonl.gz'), 'wt', encoding='utf8') as members:
                        rows, stats = process(cache, stamps, range(a, b), size, window,
                                              limits.get(tag) if split not in ('FIT', 'CAL') else None,
                                              metrics, members, sid, frames)
                    if split == 'CAL': limits[tag] = calibrate(rows)
                    summary[sid+'_'+tag+'_'+split] = dict(stats, preprocessing_ms=summarize(preprocessing[a:b]),
                                                         rejected_points=sum(rejected[a:b]), source_frames=b-a)
                print('DONE', sid, tag, flush=True)
            del cache
    write(output/'MANIFEST.json', manifest)
    write(output/'THRESHOLDS.json', limits)
    write(output/'NOISE.json', noise)
    write(output/'SUMMARY.json', summary)
    changes = {p: {'before': h, 'after': sha(p)} for p, h in bindings.items() if sha(p) != h}
    write(output/'INTEGRITY.json', dict(changes=changes, verified_files=len(bindings), elapsed_wall_s=time.perf_counter()-started,
                                       sha256=bindings, peak_memory='NOT_MEASURED', CPU_utilization='NOT_MEASURED'))
    if changes: raise ValueError('Input/code drift, run invalid')
    print('FINISHED', round(time.perf_counter()-started, 2), 'seconds', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    run(parser.parse_args().output)

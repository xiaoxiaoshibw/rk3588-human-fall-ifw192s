"""Bound geometry ledger + video-time annotation -> masked second-based cache.

Keeps every frame, including UNKNOWN. Missing features are NaN with an explicit
mask, never fabricated zeros. Inference must not feed NaNs directly to a model.
"""
import argparse
import json
from pathlib import Path

import numpy as np

from fall_annotation import event_windows, load, validate
from fall_candidate_runtime import file_sha256

FEATURES = ('centroid_height_m', 'inclination_deg', 'vertical_span_m',
            'vertical_velocity_m_s', 'points', 'dt_s', 'observed', 'valid')


def prepare(frames_path, annotation_path, out):
    doc = load(annotation_path)
    validate(doc)
    clock = doc.get('clock')
    if clock is None or clock['uncertainty_s'] > .2:
        raise ValueError('Cache requires explicit clock with uncertainty <= 0.2 s')
    summary_path = frames_path.parent/'SUMMARY.json'
    summary = json.loads(summary_path.read_text(encoding='utf-8'))
    if summary.get('frame_schema') != 'fall_geometry_frames_v1' or summary.get('session') != doc['session']:
        raise ValueError('Ledger schema/session mismatch')
    if file_sha256(frames_path) != summary.get('frames_sha256'):
        raise ValueError('Geometry ledger SHA mismatch')
    rows = [json.loads(line) for line in frames_path.read_text(encoding='utf-8').splitlines()]
    times = np.asarray([r['timestamp_s'] for r in rows], dtype=np.float64)
    if not len(times) or not np.isfinite(times).all() or np.any(np.diff(times) <= 0):
        raise ValueError('Empty, invalid or non-increasing ledger')
    if [r['frame'] for r in rows] != list(range(len(rows))) or len(rows) != summary['runs'][-1]['frames']:
        raise ValueError('Missing/duplicated ledger frames')
    X = np.full((len(rows), len(FEATURES)), np.nan, dtype=np.float64)
    bindings = []
    segments = np.full(len(rows), -1, dtype=np.int64)
    segment, previous_binding, previous_valid = -1, None, False
    for i, row in enumerate(rows):
        output = row['geometry']
        evidence = output.get('evidence') or {}
        values = dict(evidence, dt_s=output.get('dt_s'), observed=float(output['observed']),
                      valid=float(evidence.get('valid', False)))
        if 'target_source_rows' in row:
            values['points'] = len(row['target_source_rows'])
        for j, key in enumerate(FEATURES):
            if values.get(key) is not None:
                X[i, j] = values[key]
        binding = json.dumps(row['binding'], sort_keys=True)
        bindings.append(binding)
        current_valid = bool(values['observed'] and values['valid'])
        if current_valid:
            if not previous_valid or binding != previous_binding:
                segment += 1
            segments[i] = segment
        previous_binding, previous_valid = binding, current_valid
    windows = event_windows(doc)
    for window in windows:
        for name in ('window_start', 'event_start', 'event_end', 'window_end','event_impact'):
            if window.get(name) is not None:
                window[name] += clock['offset_s']
        window['clock_uncertainty_s']=clock['uncertainty_s']
        window['begin_index'] = int(np.searchsorted(times, window['window_start'], side='left'))
        window['end_index'] = int(np.searchsorted(times, window['window_end'], side='right'))
        window['supervision_eligible'] = (window['label'] is not None and
                                          window['begin_index'] < window['end_index'])
        window['continuous_segment_ids'] = sorted(set(int(s) for s in
            segments[window['begin_index']:window['end_index']] if s >= 0))
        window['time_basis'] = 'lidar_seconds = video_seconds + offset_s'
    out.mkdir(parents=True, exist_ok=False)
    np.savez_compressed(out/'frames.npz', timestamps_s=times, features=X, feature_mask=np.isfinite(X),
                        bindings=np.asarray(bindings), frame_index=np.arange(len(rows)), segment_index=segments)
    members = {p.name: file_sha256(p) for p in (frames_path, annotation_path, summary_path)}
    manifest = dict(schema='fall_event_cache_v1', session=doc['session'], subject=doc['subject'],
                    feature_names=FEATURES, frames=len(rows), windows=windows, source_summary=summary,
                    frame_cache_sha256=file_sha256(out/'frames.npz'),
                    source_sha256=members, generator_sha256=file_sha256(Path(__file__)),
                    code_sha256={p.name:file_sha256(p) for p in (Path(__file__),
                                  Path(__file__).with_name('fall_annotation.py'))},
                    missing_value='NaN + feature_mask; no zero-filled missing measurements',
                    temporal_contract='Never construct model context across segment_index boundaries; -1 is unknown',
                    geometry_gate_used_for_eligibility=False)
    for name, value in (('INPUT.json', manifest), ('MEMBERS.json', members)):
        with (out/name).open('x', encoding='utf-8') as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--frames', type=Path, required=True)
    parser.add_argument('--annotation', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = prepare(args.frames, args.annotation, args.output)
    print('frames', result['frames'], 'events', len(result['windows']))

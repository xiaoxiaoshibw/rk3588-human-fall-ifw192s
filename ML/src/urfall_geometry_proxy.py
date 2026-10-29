"""Causal UR Fall author-feature proxy, not raw-depth or IFW192S validation.

Author H and D are mm; features are sparse and joined by exact frame IDs to
official timestamps. Pose labels are evaluation-only; no synthetic PCA angles,
camera intrinsics, people IDs or missing feature rows are invented.
"""
import argparse
import csv
import json
from pathlib import Path
import struct
import zipfile

import numpy as np

from fall_candidate_runtime import file_sha256
from fall_geometry import FallGeometryRuntime

SOURCE = 'https://fenix.ur.edu.pl/~mkepski/ds/uf.html'
RULE = dict(upright_height_m=1.2, upright_centroid_m=.65,
            low_height_m=1.1, low_centroid_m=.6, low_floor_fraction=.5)


def feature_evidence(values):
    """No labels or standing-normalized HHmaxRatio (potential future context)."""
    values = np.asarray(values, dtype=np.float64)
    if values.shape != (8,) or not np.isfinite(values).all():
        return dict(valid=False, reason='invalid_author_features')
    h, d, p40 = float(values[5]/1000), float(values[6]/1000), float(values[7])
    if h <= 0 or d < 0 or not 0 <= p40 <= 1:
        return dict(valid=False, reason='invalid_author_geometry')
    upright = h >= RULE['upright_height_m'] and d >= RULE['upright_centroid_m']
    low = (h <= RULE['low_height_m'] and d <= RULE['low_centroid_m'] and
           p40 >= RULE['low_floor_fraction'])
    return dict(valid=True, centroid_height_m=d, author_height_m=h, floor_fraction=p40,
                upright=upright, low=low, middle=not upright and not low,
                representation='author_depth_height_v1')


def read_sync(path):
    with path.open(encoding='utf-8', newline='') as stream:
        rows = list(csv.reader(stream))
    frames, times = [], []
    for row in rows:
        frames.append(int(row[0])); times.append(float(row[1])/1000)
    if (not times or len(set(frames)) != len(frames) or
            not np.isfinite(times).all() or np.any(np.diff(times) <= 0) or
            any(b <= a for a, b in zip(frames, frames[1:]))):
        raise ValueError('Invalid synchronization table')
    return dict(zip(frames, times))


def run(root, out):
    out.mkdir(parents=True, exist_ok=False)
    protocol = dict(source=SOURCE, license='CC BY-NC-SA 4.0; academic non-commercial',
                    representation='author-provided H,D,P40; not raw depth geometry', rules=RULE,
                    runtime=FallGeometryRuntime().settings,
                    label_input=False, HHmaxRatio_input=False,
                    onset_reference='first 0 posture label before first 1; a proxy, not impact GT',
                    subject_split='UNKNOWN: no subject IDs in downloaded tables',
                    threshold_selection='fixed before inference, no sweep; all 70 are development data')
    (out/'PROTOCOL.json').write_text(json.dumps(protocol, indent=2), encoding='utf-8')
    by_sequence, sources = {}, {}
    for name in ('urfall-cam0-falls.csv', 'urfall-cam0-adls.csv'):
        path = root/name
        sources[name] = file_sha256(path)
        with path.open(encoding='utf-8', newline='') as stream:
            for row in csv.reader(stream):
                if len(row) != 11:
                    raise ValueError('Unexpected author feature columns')
                seq, frame, label = row[0], int(row[1]), int(row[2])
                if label not in (-1, 0, 1) or frame in by_sequence.setdefault(seq, {}):
                    raise ValueError('Invalid label or duplicate feature row')
                by_sequence[seq][frame] = (label, [float(v) for v in row[3:]])
    expected = {'%s-%02d' % (kind, i) for kind, count in (('fall', 30), ('adl', 40)) for i in range(1, count+1)}
    if set(by_sequence) != expected:
        raise ValueError('Missing/extra sequences; do not shrink denominator')
    results = []
    with (out/'FRAMES.jsonl').open('x', encoding='utf-8') as ledger:
        for seq in sorted(expected):
            path = root/(seq+'-data.csv')
            sources[path.name] = file_sha256(path)
            times = read_sync(path)
            features = by_sequence[seq]
            unmapped = sorted(set(features)-set(times))
            runtime = FallGeometryRuntime()
            events, missing, zero_times, low_times = [], [], [], []
            for frame, stamp in times.items():
                if frame not in features:
                    missing.append(frame)
                    output = runtime.push(np.empty((0, 3)), stamp, seq, 1, sources[path.name], observed=False)
                    label = None
                else:
                    label, values = features[frame]
                    evidence = feature_evidence(values)
                    output = runtime.push(None, stamp, seq, 1, sources[path.name], measurements=evidence)
                    if label == 0:
                        zero_times.append(stamp)
                    elif label == 1:
                        low_times.append(stamp)
                if output['new_event']:
                    events.append(output['new_event'])
                ledger.write(json.dumps(dict(sequence=seq, frame=frame, timestamp_s=stamp,
                                              evaluation_only_pose_label=label, output=output), allow_nan=False)+'\n')
            for frame in unmapped:
                ledger.write(json.dumps(dict(sequence=seq, frame=frame, timestamp_s=None,
                                              evaluation_only_pose_label=features[frame][0],
                                              output=dict(state='unknown', reason='missing_sync_timestamp')))+'\n')
            first_low = min(low_times) if low_times else None
            starts = [t for t in zero_times if first_low is not None and t < first_low]
            onset = min(starts) if starts else None
            matching = [e for e in events if onset is not None and onset <= e['alarm_s'] <= first_low+1.5]
            results.append(dict(sequence=seq, frames=len(times), feature_frames=len(features),
                                missing_feature_frames=missing, events=events,
                                feature_rows_without_timestamp=unmapped,
                                posture_transition_proxy_s=onset, first_lying_label_s=first_low,
                                proxy_matched=bool(matching) if seq.startswith('fall') else None,
                                proxy_latency_s=matching[0]['alarm_s']-onset if matching else None))
    depth = []
    for path in sorted(root.glob('*-cam0-d.zip')):
        members = []
        with zipfile.ZipFile(path) as archive:
            if archive.testzip() is not None:
                raise ValueError('Depth ZIP CRC failure')
            for name in archive.namelist():
                if not name.endswith('.png'):
                    continue
                raw = archive.read(name)
                if raw[:8] != b'\x89PNG\r\n\x1a\n' or raw[12:16] != b'IHDR':
                    raise ValueError('Invalid PNG header')
                width, height, bits, color = struct.unpack('>IIBB', raw[16:26])
                if bits != 16 or color != 0:
                    raise ValueError('Expected 16-bit grayscale depth')
                members.append(dict(name=name, bytes=len(raw), width=width, height=height, bits=bits))
        depth.append(dict(path=str(path), sha256=file_sha256(path), frames=len(members),
                          header=members[0] if members else None,
                          depth_scale_mm=6000 if path.name.startswith('fall') else 7000,
                          intrinsics='UNKNOWN; no metric XYZ reconstructed'))
    falls = [r for r in results if r['sequence'].startswith('fall')]
    adls = [r for r in results if r['sequence'].startswith('adl')]
    summary = dict(fall_sequences=30, adl_sequences=40, frames=sum(r['frames'] for r in results),
                   feature_frames=sum(r['feature_frames'] for r in results),
                   feature_rows_without_timestamp=sum(len(r['feature_rows_without_timestamp']) for r in results),
                   proxy_matched_falls=sum(r['proxy_matched'] for r in falls),
                   fall_sequences_with_any_candidate=sum(bool(r['events']) for r in falls),
                   adl_sequences_with_candidate=sum(bool(r['events']) for r in adls),
                   falls_without_posture_transition_reference=sum(r['posture_transition_proxy_s'] is None for r in falls),
                   sequences=results, depth_audit=depth, sources_sha256=sources,
                   code_sha256={p.name:file_sha256(p) for p in (Path(__file__),Path(__file__).with_name('fall_geometry.py'))},
                   physical_event_recall='UNKNOWN', IFW192S_effectiveness='UNKNOWN',
                   performance_scope='author-segmented depth feature proxy; exploratory method diagnostic')
    (out/'SUMMARY.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    print(json.dumps({k:v for k,v in summary.items() if k not in ('sequences','sources_sha256','depth_audit','code_sha256')}, allow_nan=False))
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    run(args.root, args.output)

"""Source-audited causal binary RF training for synthetic and LaserAct sequences.

Labels describe a whole action clip, never exact fall frames. Invalid frames
break windows. All clips remain in the denominator, including unobservable ones.
"""
import argparse
from collections import defaultdict
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import tarfile

import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier

from evaluate_fall_candidate import EPISODE, scores, breakdown
from export_lidar_rf import export
from fall_candidate_runtime import FallEpisodeLatch
from lidar_numpy_runtime import frame_feature, summarize, summarize_ordered
from prepare_human_pointset import dump, sha
from train_public_lidar import ordered_names, synthetic_xyz


PARAMS = dict(n_estimators=200, max_depth=16, min_samples_leaf=2,
              class_weight='balanced', n_jobs=4, random_state=42)


def segments(features):
    good = np.isfinite(features).all(1)
    indices = np.flatnonzero(good)
    return [part for part in np.split(indices, np.flatnonzero(np.diff(indices) != 1)+1) if len(part)]


def matrix(cache, records, stride=1, feature_schema='sequence_xyz_v1'):
    if feature_schema not in ('sequence_xyz_v1', 'sequence_ordered_xyz_v1'):
        raise ValueError('Invalid feature schema')
    pool = summarize if feature_schema == 'sequence_xyz_v1' else summarize_ordered
    X, rows = [], []
    for record in records:
        seq = record['sequence']
        ff = cache[seq]
        for segment in segments(ff):
            for last in range(9, len(segment), stride):
                end = int(segment[last])+1
                begin = max(int(segment[0]), end-30)
                X.append(pool(ff[begin:end]))
                rows.append(dict(record, begin_index=begin, end_index_exclusive=end))
    return np.asarray(X, dtype=np.float32).reshape(-1, 114), rows


def prepare_synthetic(archive, source, out):
    import zipfile
    out.mkdir(parents=True, exist_ok=False)
    prior = json.loads((source/'DATA_AUDIT.json').read_text(encoding='utf-8'))
    arrays, records = {}, []
    with zipfile.ZipFile(archive) as z:
        by_sequence = defaultdict(list)
        for name in z.namelist():
            if re.search(r'_frame_\d+\.csv$', name):
                by_sequence[name.rsplit('/', 1)[0]].append(name)
        if set(by_sequence) != {r['sequence'] for r in prior}:
            raise ValueError('Synthetic membership differs from frozen audit')
        for r in prior:
            features, hashes = [], []
            for name in ordered_names(by_sequence[r['sequence']], 'synthetic'):
                raw = z.read(name)
                hashes.append(hashlib.sha256(raw).hexdigest())
                features.append(frame_feature(synthetic_xyz(raw)))
            if hashlib.sha256(''.join(hashes).encode()).hexdigest() != r['content_sha256']:
                raise ValueError('Synthetic source SHA changed')
            arrays[r['sequence']] = np.asarray(features)
            records.append({k: r[k] for k in ['sequence', 'group', 'label']})
            if len(records) % 100 == 0: print('synthetic frame cache', len(records), flush=True)
    np.savez_compressed(out/'frames.npz', **arrays)
    dump(out/'INPUT.json', {'dataset': 'synthetic', 'archive': str(archive), 'archive_sha256': sha(archive),
         'records': records, 'frozen_fold_source': str(source), 'frame_labels': 'UNKNOWN',
         'feature_schema': 'sequence_xyz_v1'})


def decode_person_npz(raw, aggregate_packets=1, return_metadata=False):
    if not isinstance(aggregate_packets, int) or isinstance(aggregate_packets, bool) or aggregate_packets < 1:
        raise ValueError('Positive integer packet aggregation required')
    with np.load(io.BytesIO(raw), allow_pickle=False) as z:
        points, offsets, stamps = z['points'], z['frame_offsets'], z['timestamps_bag']
        if (points.ndim != 2 or points.shape[1] != 4 or not np.isfinite(points).all() or
                offsets.ndim != 1 or offsets.dtype.kind not in 'iu' or len(offsets) != len(stamps)+1 or
                not len(offsets) or offsets[0] != 0 or offsets[-1] != len(points) or
                (np.diff(offsets.astype(np.int64)) < 0).any() or
                stamps.ndim != 1 or not np.isfinite(stamps).all() or (np.diff(stamps) <= 0).any()):
            raise ValueError('Invalid person stream offsets, time or XYZ')
        spans = [(begin, min(begin+aggregate_packets, len(stamps))) for begin in range(0, len(stamps), aggregate_packets)]
        features = np.full((len(spans), 19), np.nan)
        native_counts = np.diff(offsets).astype(int)
        counts, effective_stamps = [], []
        for i, (begin, end) in enumerate(spans):
            count = int(offsets[end]-offsets[begin])
            counts.append(count); effective_stamps.append(float(stamps[end-1]))
            if count >= 10 and not np.any(np.diff(stamps[begin:end]) > .5):
                features[i] = frame_feature(points[offsets[begin]:offsets[end], :3])
        # A long source-time gap also breaks a causal segment, preserving the gap frame as UNKNOWN.
        features[np.flatnonzero(np.diff(effective_stamps) > .5)+1] = np.nan
        result = (features, counts, effective_stamps)
        if return_metadata:
            return (*result, {'native_point_counts': native_counts.tolist(), 'native_timestamps_bag': stamps.tolist(),
                              'source_packet_spans': spans, 'aggregate_packets': aggregate_packets})
        return result


def prepare_laseract(archive, core, out, expected, sensor='velodyne'):
    if sha(archive) != expected:
        raise ValueError('Complete LaserAct archive must match author SHA before reading for training')
    if sha(core) != '89a5dd0a9ddd78911ada257999298efd23b1355734a28d9cf28d1bc7e5edd90c':
        raise ValueError('Core archive SHA mismatch')
    out.mkdir(parents=True, exist_ok=False)
    with tarfile.open(core, 'r:') as tar:
        def table(name):
            with tar.extractfile(name) as stream:
                return list(csv.DictReader(io.StringIO(stream.read().decode('utf-8'))))
        labels = table('labels.csv')
        train, test = table('splits/xsub_train.csv'), table('splits/xsub_test.csv')
    by_path = {r['relpath']: r for r in labels}
    split = {r['seq_id']: 'train' for r in train}
    if set(split) & {r['seq_id'] for r in test}:
        raise ValueError('Official split sequence overlap')
    if {r['person'] for r in train} & {r['person'] for r in test}:
        raise ValueError('Official split person overlap')
    split.update({r['seq_id']: 'test' for r in test})
    if set(split) != {r['seq_id'] for r in labels}: raise ValueError('Incomplete official split')
    arrays, records, inputs = {}, [], []
    with tarfile.open(archive, 'r:') as tar:
        for member in tar:
            if not member.isfile() or not member.name.endswith('/%s_person.npz' % sensor): continue
            parent = member.name.rsplit('/', 1)[0]
            if parent not in by_path: raise ValueError('Unknown stream path')
            label = by_path[parent]
            with tar.extractfile(member) as stream: raw = stream.read()
            ff, counts, stamps, native = decode_person_npz(raw, aggregate_packets=3 if sensor == 'livox' else 1,
                                                         return_metadata=True)
            seq = label['seq_id']
            if seq in arrays: raise ValueError('Duplicate stream')
            arrays[seq] = ff
            records.append({'sequence': seq, 'group': label['person'], 'label': int(label['action'] == 'Falling'),
                            'action': label['action'], 'split': split[seq]})
            inputs.append({'sequence': seq, 'member': member.name, 'sha256': hashlib.sha256(raw).hexdigest(),
                           'frames': len(ff), 'point_counts': counts, 'timestamps_bag': stamps,
                           'invalid_feature_frames': np.flatnonzero(~np.isfinite(ff).all(1)).tolist(), **native})
            if len(records) % 200 == 0: print('LaserAct frame cache', sensor, len(records), flush=True)
    missing = sorted(set(split)-set(arrays))
    # Missing streams remain unobservable entries, not easy negative predictions or excluded positives.
    for seq in missing:
        label = next(r for r in labels if r['seq_id'] == seq)
        arrays[seq] = np.empty((0, 19))
        records.append({'sequence': seq, 'group': label['person'], 'label': int(label['action'] == 'Falling'),
                        'action': label['action'], 'split': split[seq]})
    np.savez_compressed(out/'frames.npz', **arrays)
    dump(out/'MEMBERS.json', inputs)
    dump(out/'INPUT.json', {'dataset': 'laseract', 'sensor': sensor, 'archive': str(archive),
         'packet_aggregation': 3 if sensor == 'livox' else 1,
         'archive_sha256': expected, 'core_sha256': sha(core), 'records': sorted(records, key=lambda r: r['sequence']),
         'missing_streams': missing, 'frame_labels': 'UNKNOWN', 'feature_schema': 'sequence_xyz_v1',
         'person_crop': 'author camera-derived union of actors; not independent point-level person GT',
         'label_mapping': 'Falling=1; every other labelled action, including Lying/Stumbling,=0'})


def train(cache_dir, out, models):
    out.mkdir(parents=True, exist_ok=False)
    models.mkdir(parents=True, exist_ok=False)
    doc = json.loads((cache_dir/'INPUT.json').read_text(encoding='utf-8'))
    records = doc['records']
    dump(out/'PROTOCOL.json', {'parameters': PARAMS, 'minimum_frames': 10, 'max_frames': 30,
         'train_stride': 5, 'test_stride': 1, 'episode': EPISODE,
         'label_kind': 'inherited sequence label, not frame fall GT', 'selection': 'fixed; no heldout tuning',
         'input_sha256': sha(cache_dir/'frames.npz'), 'metadata_sha256': sha(cache_dir/'INPUT.json')})
    if doc['dataset'] == 'synthetic':
        folds = [joblib.load(Path(doc['frozen_fold_source'])/('fold_%d.joblib' % i)) for i in range(5)]
        splits = [(str(i), [r for r in records if r['group'] in fold['train_groups']],
                   [r for r in records if r['group'] in fold['test_groups']]) for i, fold in enumerate(folds)]
    else:
        splits = [('xsub', [r for r in records if r['split'] == 'train'], [r for r in records if r['split'] == 'test'])]
    all_results = []
    with np.load(cache_dir/'frames.npz', allow_pickle=False) as cache:
        for name, tr, te in splits:
            if {r['group'] for r in tr} & {r['group'] for r in te}: raise ValueError('Person/group overlap')
            X, rows = matrix(cache, tr, stride=5)
            y = np.asarray([r['label'] for r in rows])
            if set(y) != {0, 1}: raise ValueError('Both training classes required')
            model = RandomForestClassifier(**PARAMS).fit(X, y)
            artifact = models/('fold_%s.joblib' % name)
            joblib.dump({'model': model, 'feature_schema': 'sequence_xyz_v1', 'dataset': doc['dataset'],
                         'train_groups': sorted({r['group'] for r in tr}),
                         'test_groups': sorted({r['group'] for r in te})}, artifact)
            numeric = models/('fold_%s.npz' % name)
            export(model, numeric)
            task = 'synthetic_sequence_fall_vs_nonfall' if doc['dataset'] == 'synthetic' else 'laseract_sequence_falling_vs_other'
            dump(models/('fold_%s.json' % name), {'task': task, 'feature_schema': 'sequence_xyz_v1',
                 'positive_class': 1, 'model': numeric.name, 'model_sha256': sha(numeric),
                 'window_frames': 30, 'minimum_frames': 10, 'max_gap_s': .5, 'episode': EPISODE,
                 'IFW192S_validity': 'UNKNOWN', 'deployment': 'NOT_DEPLOYED'})
            tx, test_rows = matrix(cache, te)
            model.n_jobs = 1
            p = model.predict_proba(tx)[:, 1] if len(tx) else np.empty(0)
            loaded = joblib.load(artifact)['model']; loaded.n_jobs = 1
            from lidar_numpy_runtime import NumpyForest
            if len(tx):
                np.testing.assert_array_equal(p, loaded.predict_proba(tx)[:, 1])
                np.testing.assert_allclose(p, NumpyForest(numeric).predict_proba(tx)[:, 1], atol=1e-14, rtol=0)
            by_sequence = defaultdict(list)
            for row, probability in zip(test_rows, p): by_sequence[row['sequence']].append((row, float(probability)))
            results = []
            with (out/('fold_%s_windows.jsonl' % name)).open('x', encoding='utf-8') as stream:
                for r in te:
                    observations = by_sequence[r['sequence']]
                    latch, events, last = FallEpisodeLatch(**EPISODE), [], None
                    for row, probability in observations:
                        end = row['end_index_exclusive']
                        if last is not None and end != last+1: latch.gap()
                        result = latch.update(probability, r['sequence'])
                        if result['new_event']: events.append(end-1)
                        stream.write(json.dumps(dict(row, **result))+'\n')
                        last = end
                    probabilities = [v for _, v in observations]
                    results.append(dict(r, fold=name, observable=bool(observations),
                        mean_probability=float(np.mean(probabilities)) if probabilities else None,
                        mean_prediction=int(np.mean(probabilities) >= .5) if probabilities else None,
                        candidate_prediction=int(bool(events)) if probabilities else None,
                        event_end_frames_0based=events, windows=len(observations)))
            dump(out/('fold_%s_sequences.json' % name), results)
            all_results.extend(results)
            print('trained fold', name, 'train windows', len(X), 'test windows', len(tx), flush=True)
    observable = [r for r in all_results if r['observable']]
    result = {'dataset': doc['dataset'], 'total_sequences': len(all_results), 'observable_sequences': len(observable),
              'unknown_sequences': [r['sequence'] for r in all_results if not r['observable']],
              'conditional_mean': scores([r['label'] for r in observable], [r['mean_prediction'] for r in observable]),
              'conditional_any_candidate': scores([r['label'] for r in observable], [r['candidate_prediction'] for r in observable]),
              'fall_sequence_coverage_including_unknown': {'detected': sum(r['candidate_prediction'] == 1 for r in all_results if r['label'] == 1),
                   'total_positive_sequences': sum(r['label'] == 1 for r in all_results)},
              'breakdown': breakdown(all_results, 'candidate_prediction'),
              'frame_fall_accuracy': 'UNKNOWN', 'fall_onset_latency': 'UNKNOWN', 'IFW192S_validity': 'UNKNOWN',
              'scope': 'sequence-level scripted/synthetic action labels; correlated windows do not create independent examples',
              'deployment': 'NOT_DEPLOYED'}
    dump(out/'SUMMARY.json', result)
    print(json.dumps(result), flush=True)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['prepare-synthetic', 'prepare-laseract', 'train'])
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--source', type=Path, default=Path('ML/models/public_lidar_20261022/synthetic'))
    parser.add_argument('--models', type=Path)
    parser.add_argument('--core', type=Path, default=Path('data/downloads/deep_lidar_20261022/laseract_core.tar'))
    parser.add_argument('--sha256', default='2c2229a943cd02d2c5a73e2a27ec5083ee9f04ad313bdd248f113db7dedf2644')
    parser.add_argument('--sensor', choices=['velodyne', 'livox', 'cepton'], default='velodyne')
    args = parser.parse_args()
    if args.mode == 'prepare-synthetic': prepare_synthetic(args.input, args.source, args.output)
    elif args.mode == 'prepare-laseract': prepare_laseract(args.input, args.core, args.output, args.sha256, args.sensor)
    else: train(args.input, args.output, args.models)

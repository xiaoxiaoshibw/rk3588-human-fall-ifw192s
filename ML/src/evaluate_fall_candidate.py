"""Frozen synthetic fall RF: full-sequence parity and causal window assessment.

No training and no per-frame/onset labels inferred from a sequence label.
"""
import argparse
from collections import defaultdict
import hashlib
import json
from pathlib import Path
import re
import zipfile

import joblib
import numpy as np
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score, precision_score, recall_score

from export_lidar_rf import export
from fall_candidate_runtime import FallEpisodeLatch
from lidar_numpy_runtime import NumpyForest, frame_feature, summarize
from prepare_human_pointset import dump, sha
from train_public_lidar import ordered_names, synthetic_xyz


EPISODE = dict(high=0.8, low=0.2, positive_windows=3, release_windows=5)


def scores(truth, prediction):
    if not len(truth):
        return {'sequences': 0, 'accuracy': None, 'macro_f1': None, 'fall_precision': None,
                'fall_recall': None, 'confusion_0_nonfall_1_fall': [[0, 0], [0, 0]],
                'reason': 'no_observable_labelled_sequences'}
    return {'sequences': len(truth), 'accuracy': float(accuracy_score(truth, prediction)),
            'macro_f1': float(f1_score(truth, prediction, average='macro', zero_division=0)),
            'fall_precision': float(precision_score(truth, prediction, zero_division=0)) if any(prediction) else None,
            'fall_recall': float(recall_score(truth, prediction, zero_division=0)) if any(truth) else None,
            'confusion_0_nonfall_1_fall': confusion_matrix(truth, prediction, labels=[0, 1]).tolist()}


def breakdown(records, prediction_key):
    result = {}
    for field in ['group', 'action']:
        if not all(field in r for r in records): continue
        grouped = {}
        for key in sorted({r[field] for r in records}):
            rows = [r for r in records if r[field] == key]
            grouped[key] = {'sequences': len(rows), 'positive_sequences': sum(r['label'] == 1 for r in rows),
                'detected_positive': sum(r['label'] == 1 and r.get(prediction_key) == 1 for r in rows),
                'negative_sequences': sum(r['label'] == 0 for r in rows),
                'alerted_negative': sum(r['label'] == 0 and r.get(prediction_key) == 1 for r in rows),
                'unknown_sequences': sum(not r['observable'] for r in rows)}
        result[field] = grouped
    return result


def export_bundle(source, out, context='fixed'):
    out.mkdir(parents=True, exist_ok=False)
    for name in ['final_model', *['fold_%d' % i for i in range(5)]]:
        doc = joblib.load(source/(name+'.joblib'))
        if doc['dataset'] != 'synthetic' or not np.array_equal(doc['model'].classes_, [0, 1]):
            raise ValueError('Wrong dataset or binary label mapping')
        path = out/(name+'.npz')
        export(doc['model'], path)
        dump(out/(name+'.json'), {'task': 'synthetic_sequence_fall_vs_nonfall',
             'feature_schema': doc['feature_schema'], 'positive_class': 1,
             'model': path.name, 'model_sha256': sha(path), 'source_sha256': sha(source/(name+'.joblib')),
             'window_frames': 256 if context == 'expanding' else 30, 'minimum_frames': 30,
             'context': context, 'max_gap_s': 0.5, 'episode': EPISODE,
             'IFW192S_validity': 'UNKNOWN', 'frame_fall_onset': 'UNKNOWN', 'deployment': 'NOT_DEPLOYED'})


def run(archive, source, out, context='fixed'):
    if context not in ('fixed', 'expanding'):
        raise ValueError('Invalid context policy')
    out.mkdir(parents=True, exist_ok=False)
    # The protocol is persisted before any new inference is performed.
    dump(out/'PROTOCOL.json', {'context': context, 'minimum_frames': 30,
         'max_frames': 256 if context == 'expanding' else 30, 'stride': 1, 'episode': EPISODE,
         'validation_status': 'exploratory post-failure hypothesis' if context == 'expanding' else 'fixed initial policy',
         'selection': 'fixed constants before this run; frozen full-sequence models, no tuning/fitting',
         'label_kind': 'synthetic complete-sequence binary label only',
         'metrics': 'sequence mean probability >=0.5 and any candidate event; no frame accuracy/detection latency',
         'folds': 'reuse original 5 parent-animation-directory heldouts; ancestry/near-duplicates UNKNOWN'})
    exports = out/'exports'
    export_bundle(source, exports, context)
    prior = json.loads((source/'DATA_AUDIT.json').read_text(encoding='utf-8'))
    frozen_predictions = {r['sequence']: r['prediction'] for r in
                          map(json.loads, (source/'predictions.jsonl').read_text(encoding='utf-8').splitlines())}
    folds = [joblib.load(source/('fold_%d.joblib' % i)) for i in range(5)]
    for doc in folds:
        if set(doc['train_groups']) & set(doc['test_groups']):
            raise ValueError('Frozen split group leakage')
        doc['model'].n_jobs = 1
    runtimes = [NumpyForest(exports/('fold_%d.npz' % i)) for i in range(5)]
    records, max_error, frame_total = [], 0., 0
    with zipfile.ZipFile(archive) as z, (out/'windows.jsonl').open('x', encoding='utf-8') as ledger:
        by_sequence = defaultdict(list)
        for name in z.namelist():
            if re.search(r'_frame_\d+\.csv$', name):
                by_sequence[name.rsplit('/', 1)[0]].append(name)
        if set(by_sequence) != {r['sequence'] for r in prior}:
            raise ValueError('Raw sequence membership changed')
        for record in prior:
            sequence, group = record['sequence'], record['group']
            eligible_folds = [i for i, doc in enumerate(folds) if group in doc['test_groups']]
            if len(eligible_folds) != 1 or not record['eligible']:
                raise ValueError('Missing/ambiguous heldout fold or invalid source sequence')
            fold = eligible_folds[0]
            features, hashes = [], []
            for name in ordered_names(by_sequence[sequence], 'synthetic'):
                raw = z.read(name)
                hashes.append(hashlib.sha256(raw).hexdigest())
                features.append(frame_feature(synthetic_xyz(raw)))
            if hashlib.sha256(''.join(hashes).encode()).hexdigest() != record['content_sha256']:
                raise ValueError('Raw source content differs from frozen audit')
            ff = np.asarray(features)
            spans = [(max(0, end-(256 if context == 'expanding' else 30)), end)
                     for end in range(30, len(ff)+1)]
            X = np.asarray([summarize(ff[begin:end]) for begin, end in spans])
            if not len(X):
                raise ValueError('Short source sequence; keep explicit, not silently exclude')
            full = summarize(ff)[None]
            expected = folds[fold]['model'].predict_proba(np.concatenate([full, X]))
            actual = runtimes[fold].predict_proba(np.concatenate([full, X]))
            error = float(np.abs(expected-actual).max())
            max_error = max(max_error, error)
            np.testing.assert_allclose(actual, expected, atol=1e-14, rtol=0)
            if int(actual[0].argmax()) != frozen_predictions[sequence]:
                raise ValueError('Complete-sequence frozen prediction changed')
            latch, events = FallEpisodeLatch(**EPISODE), []
            for (begin, end), p in zip(spans, actual[1:, 1]):
                result = latch.update(float(p), sequence)
                if result['new_event']:
                    events.append(end-1)
                ledger.write(json.dumps(dict(sequence=sequence, fold=fold, begin_index=begin,
                                            end_index_exclusive=end, **result))+'\n')
            records.append({'sequence': sequence, 'group': group, 'fold': fold, 'truth': record['label'],
                            'frames': len(ff), 'windows': len(X), 'full_prediction': int(actual[0].argmax()),
                            'mean_fall_probability': float(actual[1:, 1].mean()),
                            'mean_prediction': int(actual[1:, 1].mean() >= 0.5),
                            'candidate_event_prediction': int(bool(events)), 'event_end_frames_0based': events,
                            'label_kind': 'complete_sequence_only', 'source_content_sha256': record['content_sha256']})
            frame_total += len(ff)
            if len(records) % 100 == 0:
                print('fall evaluation', len(records), flush=True)
    dump(out/'SEQUENCES.json', records)
    truth = [r['truth'] for r in records]
    result = {'context': context, 'source_archive_sha256': sha(archive), 'raw_frames': frame_total,
              'full_frozen': scores(truth, [r['full_prediction'] for r in records]),
              'causal_window_mean': scores(truth, [r['mean_prediction'] for r in records]),
              'sequence_any_candidate': scores(truth, [r['candidate_event_prediction'] for r in records]),
              'numpy_export_max_probability_error': max_error, 'frame_accuracy': 'UNKNOWN',
              'fall_onset_detection_latency': 'UNKNOWN', 'IFW192S_effectiveness': 'UNKNOWN',
              'scope': 'synthetic sequence-level grouped holdout; sliding windows inherited no frame labels',
              'near_duplicate_animation_ancestry': 'UNKNOWN', 'deployment': 'NOT_DEPLOYED'}
    dump(out/'SUMMARY.json', result)
    print(json.dumps(result), flush=True)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--source', type=Path, default=Path('ML/models/public_lidar_20261022/synthetic'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--context', choices=['fixed', 'expanding'], default='fixed')
    args = parser.parse_args()
    run(args.archive, args.source, args.output, args.context)

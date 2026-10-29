"""Causal MM-Fi windows with the frozen XYZ/RF baseline; PC research only."""
import argparse
from collections import defaultdict
import io
import json
from pathlib import Path
import time
import zipfile

import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, confusion_matrix, f1_score
from train_public_lidar import frame_feature, ordered_names, sha

WINDOWS = (10, 20, 30, 60)
STRIDE = 10
PARAMS = dict(n_estimators=200, max_depth=16, min_samples_leaf=2,
              class_weight='balanced', n_jobs=4, random_state=42)


def summarize(features):
    x = np.array(features, dtype=np.float64, copy=True)
    if x.ndim != 2 or x.shape[1] != 19 or len(x) < 5 or not np.isfinite(x).all():
        raise ValueError('Expected at least five finite 19-dimensional frame features')
    x[:, 1:4] -= x[0, 1:4]
    return np.concatenate((x.mean(0), x.std(0), np.percentile(x, [10, 90], axis=0).ravel(),
                           np.abs(np.diff(x, axis=0)).mean(0), x[-1]-x[0])).astype(np.float32)


def bounds(length, window):
    # Fixed cadence; no future-dependent tail alignment or padding.
    return [(end-window, end) for end in range(window, length+1, STRIDE)]


def dump(path, value):
    with Path(path).open('x', encoding='utf-8') as f:
        json.dump(value, f, indent=2, ensure_ascii=False)


def extract(archive, out):
    out.mkdir(parents=True, exist_ok=False)
    grouped = defaultdict(list)
    records, cache = [], {}
    with zipfile.ZipFile(archive) as z:
        for name in z.namelist():
            if '/lidar/' in name and name.endswith('.bin'):
                grouped['/'.join(name.split('/')[:3])].append(name)
        for seq, names in sorted(grouped.items()):
            names = ordered_names(names, 'mmfi')
            ids = [int(n.rsplit('frame', 1)[1][:-4]) for n in names]
            if ids != list(range(ids[0], ids[0]+len(ids))):
                raise ValueError('Frame gap: '+seq)
            gt = np.load(io.BytesIO(z.read(seq+'/ground_truth.npy')), allow_pickle=False)
            if gt.shape != (len(names), 17, 3) or not np.isfinite(gt).all():
                raise ValueError('GT alignment: '+seq)
            ff, counts, members = [], [], []
            for name in names:
                raw = z.read(name)  # zipfile verifies CRC
                if len(raw) % 24:
                    raise ValueError('Invalid float64 XYZ bytes')
                points = np.frombuffer(raw, dtype='<f8').reshape(-1, 3)
                ff.append(frame_feature(points)); counts.append(len(points))
                import hashlib
                members.append({'path': name, 'sha256': hashlib.sha256(raw).hexdigest()})
            cache[seq] = np.asarray(ff)
            records.append({'sequence': seq, 'subject': seq.split('/')[1],
                            'label': int(seq.split('/')[2][1:]), 'frames': len(names),
                            'first_source_frame': ids[0], 'point_min': min(counts),
                            'point_max': max(counts), 'point_mean': float(np.mean(counts)),
                            'gt_sha256': __import__('hashlib').sha256(z.read(seq+'/ground_truth.npy')).hexdigest(),
                            'members': members})
            if len(records) % 30 == 0:
                print('extracted', len(records), seq, flush=True)
    np.savez_compressed(out/'frames.npz', **cache)
    dump(out/'INPUT.json', {'archive': str(archive), 'sha256': sha(archive), 'sequences': records,
                           'labels': 'inherited_sequence_action; action intervals UNKNOWN',
                           'gt_use': 'shape/alignment audit only; never feature input'})


def matrix(cache, window):
    rows, X, y, groups, sequences = [], [], [], [], []
    for seq in sorted(cache.files):
        for begin, end in bounds(len(cache[seq]), window):
            X.append(summarize(cache[seq][begin:end])); y.append(int(seq.split('/')[2][1:]))
            groups.append(seq.split('/')[1]); sequences.append(seq)
            rows.append({'sequence': seq, 'subject': groups[-1], 'truth': y[-1],
                         'begin_index': begin, 'end_index_exclusive': end,
                         'label_kind': 'inherited_sequence_action'})
    return np.asarray(X), np.asarray(y), np.asarray(groups), np.asarray(sequences), rows


def scores(y, p):
    pred = np.argmax(p, axis=1)+1
    return {'samples': len(y), 'accuracy': float(accuracy_score(y, pred)),
            'macro_f1': float(f1_score(y, pred, labels=list(range(1, 28)), average='macro', zero_division=0)),
            'confusion_matrix': confusion_matrix(y, pred, labels=list(range(1, 28))).tolist()}


def report(out, stem, rows, y, probabilities, sequences, groups):
    seq_y, seq_p, seq_groups, seq_rows = [], [], [], []
    with (out/(stem+'_windows.jsonl')).open('x', encoding='utf-8') as f:
        for row, p in zip(rows, probabilities):
            f.write(json.dumps(dict(row, prediction=int(np.argmax(p)+1), probabilities=p.tolist()))+'\n')
    for seq in sorted(set(sequences)):
        mask = sequences == seq
        p = probabilities[mask].mean(0)
        truth = int(y[mask][0]); group = str(groups[mask][0])
        seq_y.append(truth); seq_p.append(p); seq_groups.append(group)
        seq_rows.append({'sequence': seq, 'subject': group, 'truth': truth,
                         'prediction': int(np.argmax(p)+1), 'probabilities': p.tolist(),
                         'windows': int(mask.sum())})
    dump(out/(stem+'_sequences.json'), seq_rows)
    result = {'window': scores(y, probabilities), 'sequence_mean_probability': scores(seq_y, np.asarray(seq_p)),
              'per_subject': {}, 'units': 'correlated windows; independent unit is subject/sequence, no window CI'}
    for group in sorted(set(groups)):
        sm = np.asarray(seq_groups) == group; wm = groups == group
        result['per_subject'][group] = {'window': scores(y[wm], probabilities[wm]),
                                       'sequence': scores(np.asarray(seq_y)[sm], np.asarray(seq_p)[sm])}
    dump(out/(stem+'_scores.json'), result)
    return result


def develop(cache_path, baseline, models, evidence):
    models.mkdir(parents=True, exist_ok=False)
    folds = [joblib.load(p) for p in sorted(baseline.glob('fold_*.joblib'))]
    if len(folds) != 5:
        raise ValueError('Expected five frozen baseline folds')
    results, splits = {}, []
    with np.load(cache_path, allow_pickle=False) as cache:
        for window in WINDOWS:
            X, y, groups, seq, rows = matrix(cache, window)
            short_p = np.full((len(y), 27), np.nan); full_p = short_p.copy()
            seen = np.zeros(len(y), dtype=int)
            for fold, original in enumerate(folds):
                tr = np.isin(groups, original['train_groups']); te = np.isin(groups, original['test_groups'])
                assert not set(groups[tr]) & set(groups[te]) and np.all(tr | te)
                model = RandomForestClassifier(**PARAMS).fit(X[tr], y[tr])
                assert model.classes_.tolist() == list(range(1, 28))
                short_p[te] = model.predict_proba(X[te]); full_p[te] = original['model'].predict_proba(X[te])
                seen[te] += 1
                artifact = models/('w%d_fold_%d.joblib' % (window, fold))
                joblib.dump({'model': model, 'window': window, 'train_groups': original['train_groups'],
                             'test_groups': original['test_groups']}, artifact)
                loaded = joblib.load(artifact)['model']
                np.testing.assert_allclose(short_p[te], loaded.predict_proba(X[te]), atol=1e-14, rtol=0)
                np.testing.assert_array_equal(np.argmax(short_p[te], axis=1), np.argmax(loaded.predict_proba(X[te]), axis=1))
                splits.append({'window': window, 'fold': fold, 'train_groups': original['train_groups'],
                               'test_groups': original['test_groups'], 'train_windows': int(tr.sum()),
                               'test_windows': int(te.sum()), 'test_sequences': sorted(set(seq[te]))})
                print('trained', window, fold, flush=True)
            assert np.all(seen == 1) and np.isfinite(short_p).all()
            results[str(window)] = {}
            for kind, p in [('full_train', full_p), ('window_train', short_p)]:
                results[str(window)][kind] = report(evidence, 'E01_w%d_%s' % (window, kind), rows, y, p, seq, groups)
            # All four predeclared comparisons frozen, primary remains the requested 30 frames.
            final = RandomForestClassifier(**PARAMS).fit(X, y)
            joblib.dump({'model': final, 'window': window, 'schema': 'sequence_xyz_v1'}, models/('w%d_final.joblib' % window))
            np.savez_compressed(evidence/('E01_w%d_features.npz' % window), X=X, y=y, groups=groups, sequences=seq)
            print('result', window, {k: {s:v[s]['accuracy'] for s in ['window','sequence_mean_probability']}
                                      for k,v in results[str(window)].items()}, flush=True)
    dump(evidence/'SPLITS.json', splits)
    dump(evidence/'E01_COMPARISON.json', results)
    dump(evidence/'FREEZE.json', {'created_unix_s': time.time(), 'primary_window': 30, 'windows': WINDOWS,
         'stride': STRIDE, 'parameters': PARAMS, 'scaling': 'none', 'threshold_fitting': 'none; argmax',
         'aggregation': 'mean probabilities over causal windows, retrospective sequence summary only',
         'selection': 'predeclared 30; E01 exploratory comparisons, no E02 selection',
         'label_mapping': list(range(1, 28)), 'action_intervals': 'UNKNOWN; inherited sequence labels',
         'models': {p.name: sha(p) for p in models.glob('*.joblib')},
         'source': {p.name: sha(p) for p in Path(__file__).parent.glob('*public_lidar*.py')},
         'frames_sha256': sha(cache_path), 'baseline_models': {p.name: sha(p) for p in baseline.glob('*.joblib')}})


def external(cache_path, models, evidence, freeze):
    frozen = json.loads(freeze.read_text(encoding='utf-8'))
    results = {}
    with np.load(cache_path, allow_pickle=False) as cache:
        for window in WINDOWS:
            path = models/('w%d_final.joblib' % window)
            assert sha(path) == frozen['models'][path.name]
            X, y, groups, seq, rows = matrix(cache, window)
            model = joblib.load(path)['model']
            p = model.predict_proba(X)
            results[str(window)] = report(evidence, 'E02_w%d' % window, rows, y, p, seq, groups)
            np.savez_compressed(evidence/('E02_w%d_features.npz' % window), X=X, y=y, groups=groups, sequences=seq)
            print('external', window, results[str(window)]['sequence_mean_probability']['accuracy'], flush=True)
    dump(evidence/'E02_RESULTS.json', {'freeze_sha256': sha(freeze), 'results': results,
         'scope': 'E01 to untouched E02; environment and participant shift confounded; no tuning on E02'})


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('mode', choices=['extract', 'develop', 'external'])
    ap.add_argument('--input', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--models', type=Path)
    ap.add_argument('--baseline', type=Path, default=Path('ML/models/public_lidar_20261022/mmfi'))
    ap.add_argument('--freeze', type=Path)
    a = ap.parse_args()
    if a.mode == 'extract': extract(a.input, a.output)
    elif a.mode == 'develop': develop(a.input, a.baseline, a.models, a.output)
    else: external(a.input, a.models, a.output, a.freeze)

"""Multiple-instance learning: a fall clip needs an event somewhere, not in every window.

Only complete-sequence labels supervise the bag maximum. No pseudo frame labels,
onset claims, test-driven epoch selection, or device changes.
"""
import argparse
import json
from pathlib import Path
import time

import joblib
import numpy as np
import torch
from torch import nn
from torch.nn import functional as F

from evaluate_fall_candidate import EPISODE, scores, breakdown
from fall_candidate_runtime import FallEpisodeLatch
from fall_mil_numpy import NumpyMIL
from prepare_human_pointset import dump, sha
from train_causal_fall import matrix


class WindowScorer(nn.Module):
    def __init__(self):
        super().__init__()
        self.layers = nn.Sequential(nn.Linear(114, 64), nn.ReLU(), nn.Linear(64, 16), nn.ReLU(), nn.Linear(16, 1))

    def forward(self, x):
        return self.layers(x).squeeze(-1)


def export(model, mean, scale, path):
    arrays = {'mean': mean, 'scale': scale}
    for i, layer in enumerate([model.layers[0], model.layers[2], model.layers[4]]):
        arrays['weight%d' % i] = layer.weight.detach().numpy()
        arrays['bias%d' % i] = layer.bias.detach().numpy()
    with path.open('xb') as stream: np.savez_compressed(stream, **arrays)


def consecutive_starts(spans, count=3):
    """Indices of full causal vote runs; missing observations break a run."""
    ends = np.asarray([r['end_index_exclusive'] for r in spans], dtype=np.int64)
    return [i for i in range(len(ends)-count+1)
            if np.all(np.diff(ends[i:i+count]) == 1)]


def sustained_logit(logits, starts, count=3):
    if not starts:
        raise ValueError('No contiguous vote run for positive bag')
    return torch.stack([logits[i:i+count].min() for i in starts]).max()


def feature_mask(profile):
    if profile not in ('all', 'motion_only'):
        raise ValueError('Invalid feature profile')
    mask = np.ones(114, dtype=np.float32)
    if profile == 'motion_only':
        # summarize: mean, std, p10, p90, mean(abs(diff)), last-first.
        mask[:] = 0
        for block in (1, 4, 5):
            mask[block*19+1:(block+1)*19] = 1
        for block in (0, 2, 3):
            mask[block*19+1:block*19+4] = 1  # relative centroid trajectory
    return mask


def train(cache_dir, out, models, epochs=40, supervision='bag_max', training_person_lopo=False, feature_profile='all', feature_schema='sequence_xyz_v1'):
    if epochs < 1: raise ValueError('Positive epoch budget required')
    if supervision not in ('bag_max', 'every_window', 'bag_sustained'): raise ValueError('Invalid supervision')
    mask = feature_mask(feature_profile)
    if feature_schema not in ('sequence_xyz_v1', 'sequence_ordered_xyz_v1'):
        raise ValueError('Invalid feature schema')
    if feature_schema != 'sequence_xyz_v1' and feature_profile != 'all':
        raise ValueError('Moment-specific mask cannot be applied to ordered bins')
    out.mkdir(parents=True, exist_ok=False)
    models.mkdir(parents=True, exist_ok=False)
    doc = json.loads((cache_dir/'INPUT.json').read_text(encoding='utf-8'))
    records = doc['records']
    if training_person_lopo:
        if doc['dataset'] != 'laseract': raise ValueError('Training-person LOPO requires official LaserAct split')
        records = [r for r in records if r['split'] == 'train']
    dump(out/'PROTOCOL.json', {'supervision': supervision,
         'loss': {'bag_max': 'bag-max BCE', 'every_window': 'per-window BCE averaged within each clip (weak-label control)',
                  'bag_sustained': 'positive: max contiguous three-window minimum; negative: max window; BCE'}[supervision],
         'network': '114-64-ReLU-16-ReLU-1', 'optimizer': 'AdamW lr0.001 wd0.01, clip5, bags/batch16',
         'epoch_budget': epochs, 'seed': 42, 'context': '10..30 observed frames, stride1',
         'training_person_lopo': training_person_lopo,
         'feature_profile': feature_profile, 'retained_feature_indices': np.flatnonzero(mask).tolist(),
         'feature_schema': feature_schema,
         'episode': EPISODE, 'selection': 'fixed final epoch, no heldout use during fitting',
         'normalization': 'training-window mean/std only; floor1e-6',
         'input_sha256': sha(cache_dir/'frames.npz'), 'metadata_sha256': sha(cache_dir/'INPUT.json'),
         'frame_onset_GT': 'UNKNOWN', 'scope': 'weakly supervised sequence event candidate, not frame-labelled fall detector'})
    if doc['dataset'] == 'synthetic':
        priors = [joblib.load(Path(doc['frozen_fold_source'])/('fold_%d.joblib' % i)) for i in range(5)]
        splits = [(str(i), [r for r in records if r['group'] in prior['train_groups']],
                   [r for r in records if r['group'] in prior['test_groups']]) for i, prior in enumerate(priors)]
    elif training_person_lopo:
        splits = [(person, [r for r in records if r['group'] != person],
                   [r for r in records if r['group'] == person]) for person in sorted({r['group'] for r in records})]
    else:
        splits = [('xsub', [r for r in records if r['split'] == 'train'], [r for r in records if r['split'] == 'test'])]
    bags, spans_by_sequence, starts_by_sequence = {}, {}, {}
    with np.load(cache_dir/'frames.npz', allow_pickle=False) as cache:
        for r in records:
            seq = r['sequence']
            bags[seq], spans_by_sequence[seq] = matrix(cache, [r], feature_schema=feature_schema)
            bags[seq] *= mask
            starts_by_sequence[seq] = consecutive_starts(spans_by_sequence[seq], EPISODE['positive_windows'])
    torch.set_num_threads(4)
    torch.use_deterministic_algorithms(True)
    all_results, export_error = [], 0.
    for name, training, testing in splits:
        assert not {r['group'] for r in training} & {r['group'] for r in testing}
        usable = [r for r in training if len(bags[r['sequence']]) and
                  (supervision != 'bag_sustained' or not r['label'] or starts_by_sequence[r['sequence']])]
        X = np.concatenate([bags[r['sequence']] for r in usable])
        mean = X.mean(0, dtype=np.float64).astype(np.float32)
        scale = np.maximum(X.std(0, dtype=np.float64), 1e-6).astype(np.float32)
        scale[mask == 0] = 1.
        arrays = {r['sequence']: torch.from_numpy((bags[r['sequence']]-mean)/scale) for r in usable}
        labels = np.asarray([r['label'] for r in usable])
        if set(labels) != {0, 1}: raise ValueError('Both training bag classes needed')
        positive_weight = torch.tensor(float((labels == 0).sum()/(labels == 1).sum()))
        torch.manual_seed(42)
        model = WindowScorer()
        optimizer = torch.optim.AdamW(model.parameters(), lr=.001, weight_decay=.01)
        started = time.perf_counter()
        history = []
        for epoch in range(epochs):
            order = np.random.default_rng([42, epoch]).permutation(len(usable))
            total = 0.
            model.train()
            for begin in range(0, len(order), 16):
                ix = order[begin:begin+16]
                items = [arrays[usable[i]['sequence']] for i in ix]
                window_logits = model(torch.cat(items))
                target = torch.from_numpy(labels[ix].astype(np.float32))
                split_logits = torch.split(window_logits, [len(v) for v in items])
                if supervision in ('bag_max', 'bag_sustained'):
                    bag_logits = torch.stack([
                        sustained_logit(v, starts_by_sequence[usable[j]['sequence']], EPISODE['positive_windows'])
                        if supervision == 'bag_sustained' and labels[j] else v.max()
                        for j, v in zip(ix, split_logits)])
                    loss = F.binary_cross_entropy_with_logits(bag_logits, target, pos_weight=positive_weight)
                else:
                    loss = torch.stack([F.binary_cross_entropy_with_logits(v, target[i].expand_as(v),
                                        pos_weight=positive_weight) for i, v in enumerate(split_logits)]).mean()
                if not torch.isfinite(loss): raise ValueError('Nonfinite MIL loss')
                optimizer.zero_grad(set_to_none=True)
                loss.backward(); torch.nn.utils.clip_grad_norm_(model.parameters(), 5.); optimizer.step()
                total += float(loss.detach())*len(ix)
            history.append({'epoch': epoch+1, 'train_loss': total/len(usable)})
            if (epoch+1) % 10 == 0: print('MIL', name, epoch+1, history[-1], flush=True)
        path = models/('fold_%s.npz' % name)
        # Fold the zeroed feature columns into weights: same input schema/runtime.
        with torch.no_grad(): model.layers[0].weight.mul_(torch.from_numpy(mask))
        export(model.eval(), mean, scale, path)
        runtime = NumpyMIL(path)
        task = 'synthetic_sequence_fall_vs_nonfall' if doc['dataset'] == 'synthetic' else 'laseract_sequence_falling_vs_other'
        dump(models/('fold_%s.json' % name), {'task': task, 'model_format': 'numpy_mil_v1',
             'feature_schema': feature_schema, 'positive_class': 1, 'model': path.name, 'model_sha256': sha(path),
             'window_frames': 30, 'minimum_frames': 10, 'max_gap_s': .5, 'episode': EPISODE,
             'training_supervision': supervision,
             'feature_profile': feature_profile,
             'IFW192S_validity': 'UNKNOWN', 'deployment': 'NOT_DEPLOYED'})
        results = []
        with (out/('fold_%s_windows.jsonl' % name)).open('x', encoding='utf-8') as stream:
            for r in testing:
                data = bags[r['sequence']]
                if not len(data):
                    results.append(dict(r, fold=name, observable=False, prediction=None, event_end_frames_0based=[]))
                    continue
                runtime_data = data
                if feature_profile != 'all':
                    with np.load(cache_dir/'frames.npz', allow_pickle=False) as cache:
                        runtime_data = matrix(cache, [r], feature_schema=feature_schema)[0]
                p = runtime.predict_proba(runtime_data)[:, 1]
                with torch.no_grad(): expected = torch.sigmoid(model(torch.from_numpy((data-mean)/scale))).numpy()
                err = float(np.abs(p-expected).max()); export_error = max(export_error, err)
                np.testing.assert_allclose(p, expected, atol=1e-5, rtol=1e-5)
                # Rebuild span metadata without re-reading source or fitting anything.
                spans = spans_by_sequence[r['sequence']]
                latch, events, last = FallEpisodeLatch(**EPISODE), [], None
                for row, probability in zip(spans, p):
                    end = row['end_index_exclusive']
                    if last is not None and end != last+1: latch.gap()
                    candidate = latch.update(float(probability), r['sequence'])
                    if candidate['new_event']: events.append(end-1)
                    stream.write(json.dumps(dict(row, **candidate))+'\n'); last = end
                results.append(dict(r, fold=name, observable=True, max_fall_probability=float(p.max()),
                                    prediction=int(p.max() >= .5), candidate_prediction=int(bool(events)),
                                    event_end_frames_0based=events))
        dump(out/('fold_%s_sequences.json' % name), results)
        dump(out/('fold_%s_training.json' % name), {'history': history, 'elapsed_s': time.perf_counter()-started,
             'train_groups': sorted({r['group'] for r in training}), 'test_groups': sorted({r['group'] for r in testing}),
             'excluded_positive_without_vote_run': [r['sequence'] for r in training if r['label'] and
                 len(bags[r['sequence']]) and not starts_by_sequence[r['sequence']]] if supervision == 'bag_sustained' else [],
             'unobservable_training_sequences': [r['sequence'] for r in training if not len(bags[r['sequence']])]})
        all_results.extend(results)
    visible = [r for r in all_results if r['observable']]
    summary = {'dataset': doc['dataset'], 'supervision': supervision, 'feature_profile': feature_profile, 'feature_schema': feature_schema, 'total_sequences': len(all_results), 'observable_sequences': len(visible),
               'conditional_bag_max': scores([r['label'] for r in visible], [r['prediction'] for r in visible]),
               'conditional_any_candidate': scores([r['label'] for r in visible], [r['candidate_prediction'] for r in visible]),
               'all_positive_sequences': sum(r['label'] for r in all_results),
               'detected_positive_sequences': sum(r.get('candidate_prediction') == 1 for r in all_results if r['label'] == 1),
               'unobservable_sequences': [r['sequence'] for r in all_results if not r['observable']],
               'numpy_export_max_probability_error': export_error, 'frame_GT': 'UNKNOWN', 'onset_latency': 'UNKNOWN',
               'breakdown': breakdown(all_results, 'candidate_prediction'),
               'IFW192S_validity': 'UNKNOWN', 'deployment': 'NOT_DEPLOYED'}
    dump(out/'SUMMARY.json', summary); print(json.dumps(summary), flush=True)
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--models', type=Path, required=True)
    parser.add_argument('--epochs', type=int, default=40)
    parser.add_argument('--supervision', choices=['bag_max', 'every_window', 'bag_sustained'], default='bag_max')
    parser.add_argument('--training-person-lopo', action='store_true')
    parser.add_argument('--feature-profile', choices=['all', 'motion_only'], default='all')
    parser.add_argument('--feature-schema', choices=['sequence_xyz_v1', 'sequence_ordered_xyz_v1'], default='sequence_xyz_v1')
    args = parser.parse_args()
    train(args.input, args.output, args.models, args.epochs, args.supervision, args.training_person_lopo, args.feature_profile, args.feature_schema)

"""Verify NumPy MIL exports and all decision thresholds on heldout source windows."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import torch

from fall_candidate_runtime import FallCandidateRuntime
from prepare_human_pointset import dump, sha
from train_causal_fall import matrix
from train_fall_mil import WindowScorer


def run(cache_dir, models, training, output):
    doc = json.loads((cache_dir/'INPUT.json').read_text(encoding='utf-8'))
    checks = []
    paths = sorted(models.glob('fold_*.npz'))
    if not paths:
        raise ValueError('No MIL exports found')
    torch.set_num_threads(4)
    with np.load(cache_dir/'frames.npz', allow_pickle=False) as cache:
        for path in paths:
            name = path.stem
            bound = FallCandidateRuntime(path.with_suffix('.json'))
            manifest = bound.manifest
            if (manifest.get('model_format') != 'numpy_mil_v1' or
                    (path.parent/manifest['model']).resolve() != path.resolve()):
                raise ValueError('Manifest must bind this MIL export')
            # matrix currently implements this fixed source-window contract only.
            if (bound.cache.window, bound.minimum_frames, bound.cache.max_gap_s) != (30, 10, .5):
                raise ValueError('Unsupported validation context; matrix requires 10..30 frames and gap0.5s')
            split = json.loads((training/(name+'_training.json')).read_text(encoding='utf-8'))
            records = [r for r in doc['records'] if r['group'] in split['test_groups']]
            if {r['group'] for r in records} & set(split['train_groups']):
                raise ValueError('Split overlap')
            X, rows = matrix(cache, records, feature_schema=manifest['feature_schema'])
            if not len(rows):
                raise ValueError('No observable heldout windows')
            runtime = bound.model
            model = WindowScorer().eval()
            with torch.no_grad():
                for layer, weight, bias in zip([model.layers[0], model.layers[2], model.layers[4]], runtime.weights, runtime.biases):
                    layer.weight.copy_(torch.from_numpy(weight)); layer.bias.copy_(torch.from_numpy(bias))
                expected = torch.sigmoid(model(torch.from_numpy((X-runtime.mean)/runtime.scale))).numpy()
            actual = runtime.predict_proba(X)[:, 1]
            np.testing.assert_allclose(actual, expected, atol=1e-5, rtol=1e-5)
            decisions = {}
            for threshold in [.2, .5, .8]:
                np.testing.assert_array_equal(actual >= threshold, expected >= threshold)
                np.testing.assert_array_equal(actual <= threshold, expected <= threshold)
                decisions[str(threshold)] = True
            checks.append({'model': str(path), 'sha256': sha(path), 'heldout_windows': len(rows),
                           'manifest_sha256': bound.manifest_sha256, 'feature_schema': manifest['feature_schema'],
                           'feature_matrix_sha256': hashlib.sha256(X.tobytes()).hexdigest(),
                           'max_probability_error': float(np.abs(actual-expected).max()),
                           'all_threshold_decisions_equal': decisions})
    result = {'checks': checks, 'cache_sha256': sha(cache_dir/'frames.npz'),
              'scope': 'PC NumPy-vs-PyTorch heldout source windows, not native board execution',
              'native_python38_numpy117': 'UNKNOWN'}
    dump(output, result)
    print(json.dumps(result), flush=True)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--models', type=Path, required=True)
    parser.add_argument('--training', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    run(args.input, args.models, args.training, args.output)

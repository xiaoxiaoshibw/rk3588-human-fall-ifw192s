"""Frozen candidate inference only. No training/import of old training runner."""
import argparse
import hashlib
import json
from pathlib import Path
import numpy as np
import torch
from torch import nn
import onnxruntime as ort
import xgboost as xgb

ROOT = Path(__file__).resolve().parents[3]
LAB = ROOT / 'sidequests/human_fusion_lab'


def preprocess(points):
    cloud = np.asarray(points, dtype=np.float32).copy()
    if cloud.ndim != 3 or cloud.shape[1:] != (256, 3) or not np.isfinite(cloud).all():
        raise ValueError('expected finite sampled Nx256x3')
    cloud -= cloud.mean(axis=1, keepdims=True)
    return cloud.transpose(0, 2, 1).copy()


class ShadowPointNet(nn.Module):
    def __init__(self):
        super().__init__()
        self.point = nn.Sequential(nn.Conv1d(3, 32, 1), nn.ReLU(), nn.Conv1d(32, 64, 1), nn.ReLU(), nn.Conv1d(64, 128, 1), nn.ReLU())
        self.head = nn.Sequential(nn.Linear(128, 64), nn.ReLU(), nn.Linear(64, 1))

    def forward(self, x):
        return self.head(self.point(x).amax(dim=2)).squeeze(1)


def digest(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda: f.read(1048576), b''):
            h.update(b)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('fixed_js')
    parser.add_argument('output')
    args = parser.parse_args()
    out = Path(args.output)
    if out.exists():
        raise FileExistsError(out)
    audit = json.loads((LAB / 'results/AUDIT.json').read_text(encoding='utf8'))
    files = [LAB / 'results' / (sid + '.jsonl') for sids in audit['splits'].values() for sid in sids]
    assets = files + [LAB / 'models' / n for n in ['pointnet_shadow.pt', 'pointnet_shadow.onnx', 'xgb69_native.ubj', 'xgb69_candidate.json', 'rf51_candidate.json', 'rf69_candidate.json']] + [Path(__file__), Path(args.fixed_js).resolve()]
    hashes = {str(p.relative_to(ROOT)): digest(p) for p in assets if p.exists()}
    rows = [json.loads(line) for p in files if p.exists() for line in p.read_text(encoding='utf8').splitlines() if line.strip()]
    known = [r for r in rows if r['label'] is not None]
    assert len(known) == 859
    native = [r['points'] for r in known]
    centered = preprocess(native)
    float32 = preprocess(np.asarray(native, dtype=np.float32))
    assert np.array_equal(centered, float32)
    torch.set_num_threads(4)
    model = ShadowPointNet()
    model.load_state_dict(torch.load(LAB / 'models/pointnet_shadow.pt', map_location='cpu', weights_only=True))
    model.eval()
    options = ort.SessionOptions()
    options.intra_op_num_threads = 4
    options.inter_op_num_threads = 1
    session = ort.InferenceSession(str(LAB / 'models/pointnet_shadow.onnx'), sess_options=options, providers=['CPUExecutionProvider'])

    def infer(x):
        logits = np.concatenate([session.run(['logit'], {'points': x[s:s + 64]})[0].reshape(-1) for s in range(0, len(x), 64)])
        return logits

    logits = infer(centered)
    native_diff = float(np.max(np.abs(logits - infer(float32))))
    with torch.no_grad():
        forward = np.concatenate([model(torch.from_numpy(centered[s:s + 64])).numpy() for s in range(0, len(centered), 64)])
    forward_diff = float(np.max(np.abs(logits - forward)))
    assert forward_diff <= 1e-5, forward_diff
    centered_prob = 1 / (1 + np.exp(-logits))
    wrong = np.asarray(native, np.float32).transpose(0, 2, 1).copy()
    wrong_prob = 1 / (1 + np.exp(-infer(wrong)))

    def metrics(ix, probabilities):
        y = np.asarray([known[i]['label'] for i in ix])
        p = probabilities[ix] >= .55
        return dict(n=len(ix), tp=int((p & (y == 1)).sum()), fp=int((p & (y == 0)).sum()), fn=int((~p & (y == 1)).sum()), tn=int((~p & (y == 0)).sum()))

    split_metrics = {}
    for split, sids in audit['splits'].items():
        ix = [i for i, r in enumerate(known) if r['sid'] in sids]
        if ix:
            split_metrics[split] = {'centered': metrics(ix, centered_prob), 'legacy_uncentered': metrics(ix, wrong_prob)}
    js = json.loads(Path(args.fixed_js).read_text(encoding='utf8'))
    assert [(r['sid'], r['frame_index'], r['id']) for r in known] == [(r['sid'], r['frame_index'], r['id']) for r in js['results']]
    native_model = xgb.Booster()
    native_model.load_model(bytearray((LAB / 'models/xgb69_native.ubj').read_bytes()))
    fv = np.asarray([r['features'] + r['extended'] for r in known], np.float32)
    native_prob = native_model.predict(xgb.DMatrix(fv))
    js_prob = np.asarray([r['probs']['xgb69_candidate'] for r in js['results']])
    xgb_diff = float(np.max(np.abs(native_prob - js_prob)))
    assert xgb_diff <= 1e-6, xgb_diff
    decisions_changed = int(((native_prob >= .55) != (js_prob >= .55)).sum())
    assert decisions_changed == 0
    result = {'status': 'PASS', 'known_candidates': 859, 'native_float32_input_maxdiff': native_diff, 'forward_onnx_logit_maxdiff': forward_diff, 'XGB_native_JS_maxdiff': xgb_diff, 'XGB_decision_changes': decisions_changed, 'splits': split_metrics, 'source_model_input_sha256': hashes, 'versions': {'numpy': np.__version__, 'torch': torch.__version__, 'onnxruntime': ort.__version__, 'xgboost': xgb.__version__}, 'limits': ['All frozen rows come from exposed development sessions, not independent detection test.', 'Candidate labels overlap-derived, not new human negative qualification.', 'Existing PointNet weights unchanged; corrected shadow consumer, no training/model replacement.']}
    out.write_text(json.dumps(result, indent=2), encoding='utf8')
    assert all(digest(ROOT / p) == h for p, h in hashes.items())
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()

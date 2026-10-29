"""NumPy inference for a weakly supervised fall-window scorer, Python 3.8."""
import numpy as np


class NumpyMIL:
    def __init__(self, path):
        with np.load(path, allow_pickle=False) as data:
            self.mean, self.scale = data['mean'].copy(), data['scale'].copy()
            self.weights = [data['weight%d' % i].copy() for i in range(3)]
            self.biases = [data['bias%d' % i].copy() for i in range(3)]
        if (self.mean.shape != (114,) or self.scale.shape != (114,) or
                not np.isfinite(self.mean).all() or not np.isfinite(self.scale).all() or
                (self.scale <= 0).any()):
            raise ValueError('Invalid MIL normalizer')
        sizes = [114, 64, 16, 1]
        for i, (weight, bias) in enumerate(zip(self.weights, self.biases)):
            if (weight.shape != (sizes[i+1], sizes[i]) or bias.shape != (sizes[i+1],) or
                    not np.isfinite(weight).all() or not np.isfinite(bias).all()):
                raise ValueError('Invalid MIL weights')
        self.classes = np.array([0, 1])

    def predict_proba(self, features):
        raw = np.asarray(features, dtype=np.float64)
        if raw.ndim != 2 or raw.shape[1] != 114 or not np.isfinite(raw).all() or (np.abs(raw) > np.finfo(np.float32).max).any():
            raise ValueError('Invalid MIL input')
        with np.errstate(over='raise', invalid='raise', divide='raise'):
            x = (raw.astype(np.float32)-self.mean)/self.scale
            for i, (weight, bias) in enumerate(zip(self.weights, self.biases)):
                x = x @ weight.T + bias
                if i < 2: x = np.maximum(x, 0)
            logits = x[:, 0]
            exp = np.exp(-np.abs(logits))
            p = np.where(logits >= 0, 1/(1+exp), exp/(1+exp))
        return np.column_stack([1-p, p])

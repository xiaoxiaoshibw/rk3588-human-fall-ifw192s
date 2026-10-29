"""Python 3.8, stdlib + NumPy RF inference and causal feature cache. No device I/O."""
from collections import deque
import math
import numpy as np


def frame_feature(points):
    # Frozen sequence_xyz_v1 formula, parity-tested against the training implementation.
    p = np.asarray(points, dtype=np.float64)
    if p.ndim != 2 or p.shape[1] != 3 or len(p) < 10 or not np.isfinite(p).all():
        raise ValueError('A frame needs at least 10 finite XYZ points')
    center = np.median(p, axis=0)
    q = p-center
    eigen = np.maximum(np.linalg.eigvalsh(np.cov(q.T)), 0)[::-1]
    return np.concatenate(([np.log1p(len(p))], center,
                           np.percentile(q, [10, 50, 90], axis=0).reshape(-1),
                           eigen, eigen/max(eigen.sum(), 1e-12)))


def summarize(features):
    x = np.array(features, dtype=np.float64, copy=True)
    if x.ndim != 2 or x.shape[1] != 19 or len(x) < 5 or not np.isfinite(x).all():
        raise ValueError('Expected finite frame features')
    x[:, 1:4] -= x[0, 1:4]
    return np.concatenate((x.mean(0), x.std(0), np.percentile(x, [10, 90], axis=0).ravel(),
                           np.abs(np.diff(x, axis=0)).mean(0), x[-1]-x[0])).astype(np.float32)


def summarize_ordered(features):
    """Six chronological bin means, only over observed past frames."""
    x = np.array(features, dtype=np.float64, copy=True)
    if x.ndim != 2 or x.shape[1] != 19 or len(x) < 6 or not np.isfinite(x).all():
        raise ValueError('Expected at least six finite frame features')
    x[:, 1:4] -= x[0, 1:4]
    return np.concatenate([part.mean(0) for part in np.array_split(x, 6)]).astype(np.float32)


class NumpyForest:
    def __init__(self, path):
        with np.load(path, allow_pickle=False) as data:
            self.classes = data['classes'].copy()
            self.left = data['left'].copy(); self.right = data['right'].copy()
            self.feature = data['feature'].copy(); self.threshold = data['threshold'].copy()
            self.value = data['value'].copy(); self.roots = data['roots'].copy()
            self.n_features = int(data['n_features'])
        n = len(self.left)
        if (not n or self.n_features != 114 or len(self.roots) == 0 or
                self.right.shape != (n,) or self.feature.shape != (n,) or
                self.threshold.shape != (n,) or self.value.shape != (n,len(self.classes)) or
                not np.isfinite(self.threshold).all() or not np.isfinite(self.value).all() or
                (self.value < 0).any()):
            raise ValueError('Invalid forest arrays')
        branch = self.left != -1
        if (np.any(self.right[~branch] != -1) or np.any(self.left[branch] < 0) or
                np.any(self.left[branch] >= n) or np.any(self.right[branch] < 0) or
                np.any(self.right[branch] >= n) or np.any(self.roots < 0) or np.any(self.roots >= n) or
                np.any(self.feature[branch] < 0) or np.any(self.feature[branch] >= self.n_features)):
            raise ValueError('Invalid tree indices')
        # Exported trees use preorder indices; this also rejects cycles.
        if np.any(self.left[branch] <= np.flatnonzero(branch)) or np.any(self.right[branch] <= np.flatnonzero(branch)):
            raise ValueError('Non-forward tree edge')
        if not np.allclose(self.value[~branch].sum(1),1,atol=1e-12):
            raise ValueError('Invalid leaf probabilities')

    def predict_proba(self, features):
        raw = np.asarray(features, dtype=np.float64)
        if (raw.ndim != 2 or raw.shape[1] != self.n_features or not np.isfinite(raw).all()
                or np.any(np.abs(raw) > np.finfo(np.float32).max)):
            raise ValueError('Expected finite float32-representable model input')
        x = raw.astype(np.float32)  # sklearn tree predict casts before comparing float64 thresholds
        out = np.zeros((len(x),len(self.classes)), dtype=np.float64)
        for i, row in enumerate(x):
            nodes = self.roots.copy()
            active = self.left[nodes] != -1
            while np.any(active):
                a = nodes[active]
                nodes[active] = np.where(row[self.feature[a]] <= self.threshold[a], self.left[a], self.right[a])
                active = self.left[nodes] != -1
            out[i] = self.value[nodes].sum(0)/len(nodes)
        return out

    def predict(self, features):
        return self.classes[np.argmax(self.predict_proba(features),axis=1)]


class CausalCache:
    def __init__(self, window=30, max_gap_s=0.5):
        if not isinstance(window,int) or window < 5 or not math.isfinite(max_gap_s) or max_gap_s <= 0:
            raise ValueError('Invalid window/gap')
        self.window = window; self.max_gap_s = max_gap_s
        self.frames = deque(maxlen=window); self.key = None; self.last_time = None

    def clear(self):
        self.frames.clear(); self.key = None; self.last_time = None

    def push(self, points, timestamp, identity, generation, calibration):
        key = (identity, generation, calibration)
        try:
            if (identity is None or generation is None or calibration is None or
                    not math.isfinite(timestamp)):
                raise ValueError('Missing stream binding or invalid time')
            feature = frame_feature(points)
        except (TypeError, ValueError):
            self.clear()
            raise ValueError('Invalid frame; causal history cleared')
        if (key != self.key or self.last_time is None or timestamp <= self.last_time or
                timestamp-self.last_time > self.max_gap_s):
            self.clear()
        self.key = key; self.last_time = timestamp; self.frames.append(feature)
        return summarize(self.frames) if len(self.frames) == self.window else None

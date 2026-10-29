"""PC-only sklearn exporter; output uses only numeric NPZ arrays."""
import argparse
from pathlib import Path
import joblib
import numpy as np


def export(model, path):
    left, right, features, thresholds, values, roots = [], [], [], [], [], []
    offset = 0
    for estimator in model.estimators_:
        t = estimator.tree_; roots.append(offset)
        left.extend(np.where(t.children_left < 0, -1, t.children_left+offset))
        right.extend(np.where(t.children_right < 0, -1, t.children_right+offset))
        features.extend(t.feature); thresholds.extend(t.threshold)
        v = t.value[:,0,:].astype(np.float64)
        values.extend(v/v.sum(1,keepdims=True))
        offset += t.node_count
    # Exclusive file creation; never replace a prior candidate.
    with Path(path).open('xb') as f:
        np.savez_compressed(f, classes=model.classes_,left=np.asarray(left,dtype=np.int64),
                            right=np.asarray(right,dtype=np.int64),feature=np.asarray(features,dtype=np.int64),
                            threshold=np.asarray(thresholds),value=np.asarray(values),
                            roots=np.asarray(roots,dtype=np.int64),n_features=np.asarray(model.n_features_in_))


if __name__ == '__main__':
    p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('output',type=Path)
    a=p.parse_args();export(joblib.load(a.source)['model'],a.output)

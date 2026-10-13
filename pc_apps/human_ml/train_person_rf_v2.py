"""HUMAN-UNIFY-FUSION R2: frozen GT -> offline candidate; never replace v1."""
import argparse
import pathlib
import platform

import numpy as np
import sklearn
from sklearn.ensemble import RandomForestClassifier

from dump_rf_json import tree_to_dict
from frame_feature import FEAT_DIM, FEAT_NAMES
from frozen_gt import REPO, SIDS, audit_session, export_samples, read_json, sha, write_json

SPLITS = {"train": SIDS[:2] + SIDS[3:5], "val": [SIDS[2]],
          "test": SIDS[6:8], "stress": [SIDS[5]], "blocked": [SIDS[8]]}
THRESHOLD = 0.55


def predict_json(model, X):
    prob = np.zeros(len(X))
    for tree in model["trees"]:
        for i, fv in enumerate(X):
            node = 0
            while tree["feature"][node] >= 0:
                feature = tree["feature"][node]
                node = tree["children_left" if fv[feature] <= tree["threshold"][node] else "children_right"][node]
            v = tree["value"][node]
            prob[i] += v[1] / sum(v) if sum(v) else 0
    return prob / len(model["trees"])


def metrics(y, p):
    hit = p >= THRESHOLD
    tp, fp = int(((y == 1) & hit).sum()), int(((y == 0) & hit).sum())
    fn, tn = int(((y == 1) & ~hit).sum()), int(((y == 0) & ~hit).sum())
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "recall": tp / (tp + fn) if tp + fn else None,
            "precision": tp / (tp + fp) if tp + fp else None}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--outdir", type=pathlib.Path, required=True)
    ap.add_argument("--store", type=pathlib.Path, default=REPO / "pc_apps/human_replay/gt_store")
    ap.add_argument("--capture", type=pathlib.Path, default=REPO / "captures/remote")
    args = ap.parse_args()
    if args.outdir.exists() and any(args.outdir.iterdir()):
        raise ValueError("nonempty outdir; refuses overwrite")
    if args.outdir.resolve().is_relative_to((REPO / "pc_apps/human_replay").resolve()):
        raise ValueError("candidate may not write production directory")
    args.outdir.mkdir(parents=True, exist_ok=True)
    records, samples = [], []
    for sid in SIDS:
        r, doc, meta = audit_session(sid, args.store, args.capture)
        rows, details = export_samples(r, doc, meta, args.capture)
        r["export"] = details
        records.append(r)
        samples.extend(rows)
        print(sid, "eligible", r["eligible"], "objects", len(doc["objects"]), "samples", len(rows), flush=True)
    write_json(args.outdir / "GT_AUDIT.json", {"sessions": records})
    write_json(args.outdir / "GT_POS.json", {"samples": [s for s in samples if s["label"] == 1]})
    write_json(args.outdir / "GT_FURN_HARD_NEG.json", {"samples": [s for s in samples if s["label"] == 0]})
    split_doc = {"splits": SPLITS, "threshold": THRESHOLD, "threshold_source": "frozen v1 0.55; no tuning",
                 "gt_sources": records, "sample_files_sha256": {n: sha(args.outdir / n) for n in ("GT_POS.json", "GT_FURN_HARD_NEG.json")},
                 "limits": ["S1 negatives train-only; no independent furniture test", "same actor/scene independence unknown",
                            "unannotated frames UNKNOWN", "S9 unbound and excluded"]}
    write_json(args.outdir / "SPLITS.json", split_doc)  # frozen before fit
    v1_path = REPO / "pc_apps/human_replay/rf_person_v1.json"
    frozen = {str(p): sha(p) for p in (v1_path, REPO / "pc_apps/human_ml/frame_feature.py",
                                      REPO / "pc_apps/human_replay/rf_person.js")}
    X = np.asarray([s["fv"] for s in samples], dtype=np.float32)
    y = np.asarray([s["label"] for s in samples])
    tr = np.asarray([s["session_id"] in SPLITS["train"] for s in samples])
    if X.shape[1] != FEAT_DIM or not np.isfinite(X).all() or set(y[tr]) != {0, 1}:
        raise ValueError("invalid features/classes")
    clf = RandomForestClassifier(n_estimators=100, max_depth=20, n_jobs=-1, random_state=0, class_weight="balanced")
    clf.fit(X[tr], y[tr])
    candidate = {"n_features": FEAT_DIM, "feature_names": FEAT_NAMES, "classes": clf.classes_.tolist(),
                 "n_trees": len(clf.estimators_), "trees": [tree_to_dict(t) for t in clf.estimators_],
                 "model_source": "HUMAN-UNIFY-FUSION-R1 R2 frozen GT candidate", "splits_sha256": sha(args.outdir / "SPLITS.json")}
    write_json(args.outdir / "rf_person_v2.json", candidate)
    p1, p2 = predict_json(read_json(v1_path), X), predict_json(candidate, X)
    sklearn_p = clf.predict_proba(X)[:, 1]
    parity = float(np.max(np.abs(p2 - sklearn_p)))
    if parity > 1e-5:
        raise ValueError("export probability parity failed: " + str(parity))
    results = []
    for sid in SIDS:
        use = np.asarray([s["session_id"] == sid for s in samples])
        split = next(k for k, ids in SPLITS.items() if sid in ids)
        results.append({"sid": sid, "split": split, "n": int(use.sum()),
                        "v1": metrics(y[use], p1[use]), "v2": metrics(y[use], p2[use])})
    write_json(args.outdir / "RF_MODEL_COMPARISON.json", {"runs": results, "threshold": THRESHOLD,
               "v1_sha256": sha(v1_path), "v2_sha256": sha(args.outdir / "rf_person_v2.json"),
               "export_probability_max_diff": parity, "split_sha256": candidate["splits_sha256"],
               "python": platform.python_version(), "numpy": np.__version__, "sklearn": sklearn.__version__,
               "model_promotion": "BLOCKED; no independent negative test or actor/scene separation"})
    write_json(args.outdir / "RF_PROBABILITIES.json", {"samples": [{**s, "v1_prob": float(a), "v2_prob": float(b)}
                                                                 for s, a, b in zip(samples, p1, p2)]})
    if any(sha(pathlib.Path(p)) != h for p, h in frozen.items()):
        raise ValueError("frozen v1 contract changed during training")
    print("TRAIN_COMPLETE", len(samples), "export_max_diff", parity, flush=True)


if __name__ == "__main__":
    main()

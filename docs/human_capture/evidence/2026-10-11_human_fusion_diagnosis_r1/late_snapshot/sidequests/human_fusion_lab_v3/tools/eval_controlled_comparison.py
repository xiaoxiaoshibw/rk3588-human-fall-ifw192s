# -*- coding: utf-8 -*-
"""eval_controlled_comparison.py — HUMAN-FUSION-BG-V3 阶段5: 四模型 + PointNet 影子 受控同点集对照.

纪律: 对每行冻结候选 (A 链 jsonl) 同 point/features 向量, 各模型独立评分 (0.55 门),
不跨帧不tracker不改权重. 统计按 splits 分框, 诚实报告哪 split 无 neg (spec UNKNOWN).
PointNet 影子: 输入 (batch,3,256) logit → sigmoid; 行列 points[256,3] 是同 jsonl.
输出 results/CONTROLLED_COMPARISON.json
"""
import json
import numpy as np
from pathlib import Path
import onnxruntime as ort

LAB2 = Path(__file__).resolve().parent.parent.parent / "human_fusion_lab"
RESULTS = LAB2 / "results"
AUDIT = json.loads((RESULTS / "AUDIT.json").read_text())
SPLITS = AUDIT["splits"]
THR = 0.55


def tree_xgb(t, x):
    # JS detector.js treeXGB: object 节点, 走 split/split_condition/yes/no/missing → leaf
    while "leaf" not in t:
        ix = int(t["split"].lstrip("f"))
        v = x[ix]
        if not np.isfinite(v):
            nxt = t["missing"]
        else:
            nxt = t["yes"] if v < np.float32(t["split_condition"]) else t["no"]
        t = next(c for c in t["children"] if c["nodeid"] == nxt)
    return float(t["leaf"])


def tree_rf(t, x):
    n = 0
    while t["feature"][n] >= 0:
        n = t["children_left"][n] if x[t["feature"][n]] <= t["threshold"][n] else t["children_right"][n]
    v = t["value"][n]
    return v[1] / max(1e-12, v[0] + v[1])


def rf_score(m, x):
    return sum(tree_rf(t, x) for t in m["trees"]) / len(m["trees"])


def xgb_score(m, x):
    s = m.get("base_margin", 0.0) + sum(tree_xgb(t, x) for t in m["trees"])
    return 1.0 / (1.0 + np.exp(-s))


def metric(labels, probs, thr=THR):
    labels = np.asarray(labels); probs = np.asarray(probs)
    tp = int(((probs >= thr) & (labels == 1)).sum())
    fn = int(((probs < thr) & (labels == 1)).sum())
    fp = int(((probs >= thr) & (labels == 0)).sum())
    tn = int(((probs < thr) & (labels == 0)).sum())
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "recall": tp / max(1, tp + fn), "precision": tp / max(1, tp + fp),
            "specificity": (tn / max(1, tn + fp)) if (tp + fn + fp + tn) else None,
            "specificity_known": tn + fp > 0}


def main():
    rows = []
    for sid in sum(SPLITS.values(), []):
        p = RESULTS / f"{sid}.jsonl"
        if not p.exists():
            continue
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
    print(f"total rows: {len(rows)}")

    models = {}
    models["rf51_baseline"] = ("rf", json.loads((LAB2 / "human_replay/rf_person_v1.json").read_text()), 51)
    models["rf51_candidate"] = ("rf", json.loads((LAB2 / "models/rf51_candidate.json").read_text()), 51)
    models["rf69_candidate"] = ("rf", json.loads((LAB2 / "models/rf69_candidate.json").read_text()), 69)
    models["xgb69_candidate"] = ("xgb", json.loads((LAB2 / "models/xgb69_candidate.json").read_text()), 69)
    pnn_sess = ort.InferenceSession(str(LAB2 / "models/pointnet_shadow.onnx"), providers=["CPUExecutionProvider"])
    pnn_dual = ort.InferenceSession(str(LAB2 / "models/dual_pointnet_shadow.onnx"), providers=["CPUExecutionProvider"])

    def score(name, kind, m, r):
        feat = np.array(r["features"] + r["extended"], np.float32)
        if name.startswith("rf"):
            return rf_score(m, feat[:m.get("n_features", 51)])
        if name.startswith("xgb"):
            return xgb_score(m, feat)
        return None

    Xpnn = np.array([np.array(r["points"], np.float32).T for r in rows])  # (N,3,256)

    def pnn_pred(sess, X):
        outs = []
        B = 64
        for i in range(0, len(X), B):
            logits = sess.run(["logit"], {"points": X[i:i+B]})[0]
            outs.extend(1.0 / (1.0 + np.exp(-logits)))
        return np.array(outs)

    pnn_shadow = pnn_pred(pnn_sess, Xpnn)
    pnn_dual_v = pnn_pred(pnn_dual, Xpnn)

    report = {"task": "V3 四模型+PointNet影子 同点集受控对照", "date": "2026-10-11", "thr": THR, "splits": {}}
    for split in SPLITS:
        if split == "blocked":
            continue
        ix = [i for i, r in enumerate(rows) if r["label"] is not None and r["sid"] in SPLITS.get(split, [])]
        if not ix:
            report["splits"][split] = {"note": "no labeled rows"}
            continue
        labels = np.array([rows[i]["label"] for i in ix])
        sp = {"n": len(ix), "pos": int((labels == 1).sum()), "neg": int((labels == 0).sum()), "models": {}}
        for name, (kind, m, _) in models.items():
            probs = np.array([score(name, kind, m, rows[i]) for i in ix])
            sp["models"][name] = metric(labels, probs)
        sp["models"]["pointnet_shadow"] = metric(labels, pnn_shadow[ix])
        sp["models"]["dual_pointnet_shadow"] = metric(labels, pnn_dual_v[ix])
        report["splits"][split] = sp
        print(f"{split}: n={len(ix)} pos={sp['pos']} neg={sp['neg']}")
        for name, mm in sp["models"].items():
            print(f"  {name:24s} R={mm['recall']:.3f} P={mm['precision']:.3f} Spec={mm['specificity'] if mm['specificity'] is not None else 'UNKNOWN'}")
    out = Path(__file__).resolve().parent.parent / "results" / "CONTROLLED_COMPARISON.json"
    out.write_text(json.dumps(report, indent=1))
    print("wrote", out)


if __name__ == "__main__":
    main()

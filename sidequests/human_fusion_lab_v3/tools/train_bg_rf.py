# -*- coding: utf-8 -*-
"""train_bg_rf.py — HUMAN-FUSION-BG-V3 阶段5: 受控对照训练 (不挑参数).

诚实约束 (C1 教训):
  A 链冻结行: train (S1 566 neg + 3 人会话 137 pos),
    val/test/stress 全部 neg=0 (无负样本 → 任何独立负样本泛化 UNKNOWN).
  V3 B 组新行: S1 608 neg (B 残差家具, 与 A 566 同源会话, 非独立会话)
    S9 488 blocked 行无 GT → 全部不用于训练, 仅记录为 suppressed UNKNOWN.

受控对照设计:
  1) base_A_only: 只用 A 链 train (与 V2 rf51_candidate 同参数同种子重训) — 对照基线
  2) comb_A_plus_B: A 链 train + B 组 S1 家具 neg (同会话不同提取 → 非"独立会话泛化",
     是"同会话不同 BG 提取下的家具"重启证据)
  两者权重均冻结后再冻结, 在"同一冻结候选行"上评估 (eval_controlled_comparison.js).
  不根据结果反调超参 (一次性, n_estimators=96/max_depth=8/min_samples_leaf=3/seed=20261011).
"""
import json, time, hashlib
import numpy as np
from pathlib import Path
from sklearn.ensemble import RandomForestClassifier

LAB = Path(__file__).resolve().parent.parent
LAB2 = LAB.parent / "human_fusion_lab"
RESULTS = LAB2 / "results"
AUDIT = json.loads((RESULTS / "AUDIT.json").read_text())
SPLITS = AUDIT["splits"]
SEED = 20261011


def load_A():
    rows = []
    for sid in sum(SPLITS.values(), []):
        p = RESULTS / f"{sid}.jsonl"
        if not p.exists():
            continue
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.strip():
                rows.append(json.loads(line))
    return rows


def load_B(sid):
    p = LAB / "results" / f"{sid}_bg.jsonl"
    if not p.exists():
        return []
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def tree_dict(t):
    return {
        "children_left": t.children_left.tolist(),
        "children_right": t.children_right.tolist(),
        "feature": t.feature.tolist(),
        "threshold": t.threshold.tolist(),
        "value": t.value[:, 0, :].tolist(),
    }


def evaluate(m, rows, X, thr=0.55):
    ix = [i for i, r in enumerate(rows) if r["label"] is not None]
    tp = fp = fn = tn = 0
    for i in ix:
        p = m.predict_proba(X[i:i+1, :51])[0, 1] >= thr
        l = rows[i]["label"]
        if l == 1 and p: tp += 1
        elif l == 1: fn += 1
        elif l == 0 and p: fp += 1
        else: tn += 1
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "recall": tp / max(1, tp + fn), "precision": tp / max(1, tp + fp),
            "specificity": tn / max(1, tn + fp)}


def main():
    A = load_A()
    X_A = np.array([r["features"] + r["extended"] for r in A], np.float32)
    train_ix = [i for i, r in enumerate(A) if r["label"] is not None and r["sid"] in SPLITS["train"]]
    y_tr = np.array([A[i]["label"] for i in train_ix])

    B_rows = load_B("cap_20261010_175227")
    B_neg = [r for r in B_rows if r["label"] == 0]
    X_B_neg = np.array([r["features"] + r["extended"] for r in B_neg], np.float32) if B_neg else np.zeros((0, 69), np.float32)
    print(f"A train: pos={int(y_tr.sum())} neg={int((y_tr==0).sum())}; B S1 neg (同会话不同 BG): {len(B_neg)}")

    # 1) A only (V2 同参重训)
    t0 = time.perf_counter()
    base = RandomForestClassifier(n_estimators=96, max_depth=8, min_samples_leaf=3,
                                  random_state=SEED, n_jobs=4).fit(X_A[train_ix][:, :51], y_tr)
    # 2) A + B neg
    X_c = np.vstack([X_A[train_ix][:, :51], X_B_neg[:, :51]])
    y_c = np.concatenate([y_tr, np.zeros(len(B_neg), int)])
    comb = RandomForestClassifier(n_estimators=96, max_depth=8, min_samples_leaf=3,
                                  random_state=SEED, n_jobs=4).fit(X_c, y_c)
    print(f"trained: base_A_only and comb_A_plus_Bneg in {time.perf_counter()-t0:.1f}s")

    report = {"splits_eval": {}}
    for split in ["train", "validation", "test", "stress"]:
        ix = [i for i, r in enumerate(A) if r["label"] is not None and r["sid"] in SPLITS.get(split, [])]
        if not ix:
            report["splits_eval"][split] = {"note": "no labeled rows"}
            continue
        sub_rows = [A[i] for i in ix]
        X_sub = X_A[ix]
        report["splits_eval"][split] = {
            "base_A_only": evaluate(base, sub_rows, X_sub),
            "comb_A_plus_Bneg": evaluate(comb, sub_rows, X_sub),
        }
        b = report["splits_eval"][split]["base_A_only"]
        c = report["splits_eval"][split]["comb_A_plus_Bneg"]
        print(f"  {split}: base R={b['recall']:.3f} P={b['precision']:.3f}; +B R={c['recall']:.3f} P={c['precision']:.3f}")

    def export(m):
        return {"kind": "rf", "n_features": 51, "trees": [tree_dict(t.tree_) for t in m.estimators_]}
    out = LAB / "models"
    out.mkdir(exist_ok=True)
    (out / "rf51_baseline_retrain_A_only.json").write_text(json.dumps(export(base)))
    (out / "rf51_bg_candidate.json").write_text(json.dumps(export(comb)))
    report["n_B_neg_added"] = int(len(B_neg))
    report["caveat"] = "+B_neg 来自同会话 S1 不同 BG 提取, 不是独立会话家具泛化"
    report["train_sha"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    (LAB / "results" / "TRAIN_BG_REPORT.json").write_text(json.dumps(report, indent=1))
    print("wrote models/rf51_bg_candidate.json")


if __name__ == "__main__":
    main()

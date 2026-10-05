# -*- coding: utf-8 -*-
"""train_rf_v0.py — LI-DATA fall/nofall 二分类 RandomForest baseline.

跑法：
    python train_rf_v0.py                 # 全量 5-fold (LI-DATA 完整一遍大概 20 分钟）
    python train_rf_v0.py --fast          # 每类 1000 帧， 总 2000 帧 (≈1 分钟）
    python train_rf_v0.py --out ML/docs/rf_v0_report.md
"""
import argparse
import json
import os
import time

import numpy as np

from lidata_load import LidarDataLoader, LABEL_FALL, LABEL_NO_FALL
from frame_feature import FEAT_DIM, FEAT_NAMES, build_matrix


def run(n_per_class, out_md=None):
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import StratifiedKFold
    from sklearn.metrics import (
        accuracy_score, confusion_matrix, f1_score, precision_score, recall_score)

    print("load features...")
    with LidarDataLoader() as ld:
        gen = ld.iter_frames()
        # 凑齐 n_per_class 两类各取
        X_rows = []
        y_rows = []
        paths = []
        cnt = {LABEL_FALL: 0, LABEL_NO_FALL: 0}
        for xyz, lab, path in gen:
            if cnt[lab] >= n_per_class:
                continue
            cnt[lab] += 1
            from frame_feature import extract_features
            X_rows.append(extract_features(xyz))
            y_rows.append(lab)
            paths.append(path)
            if cnt[LABEL_FALL] >= n_per_class and cnt[LABEL_NO_FALL] >= n_per_class:
                break
    X = np.asarray(X_rows, dtype=np.float32)
    y = np.asarray(y_rows, dtype=np.int32)
    print("X:", X.shape, "fall:", int((y == LABEL_FALL).sum()),
          "nofall:", int((y == LABEL_NO_FALL).sum()))

    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=0)
    metrics = []
    feature_imps = np.zeros(FEAT_DIM, dtype=np.float64)
    for fold, (tr, te) in enumerate(skf.split(X, y)):
        st = time.perf_counter()
        clf = RandomForestClassifier(n_estimators=100, max_depth=20,
                                      n_jobs=-1, random_state=fold)
        clf.fit(X[tr], y[tr])
        pred = clf.predict(X[te])
        acc = accuracy_score(y[te], pred)
        f1 = f1_score(y[te], pred)
        prec = precision_score(y[te], pred)
        rec = recall_score(y[te], pred)
        cm = confusion_matrix(y[te], pred)
        metrics.append({"fold": fold, "acc": acc, "f1": f1,
                         "prec": prec, "rec": rec,
                         "cm": cm.tolist(),
                         "elapsed_sec": round(time.perf_counter() - st, 1)})
        feature_imps += clf.feature_importances_
        print("  fold %d: acc=%.3f f1=%.3f prec=%.3f rec=%.3f  (%.1fs)" % (
            fold, acc, f1, prec, rec, time.perf_counter() - st))
    feature_imps /= 5
    avg = {
        "acc": float(np.mean([m["acc"] for m in metrics])),
        "f1": float(np.mean([m["f1"] for m in metrics])),
        "prec": float(np.mean([m["prec"] for m in metrics])),
        "rec": float(np.mean([m["rec"] for m in metrics])),
    }
    print("=== avg: acc=%.3f f1=%.3f prec=%.3f rec=%.3f" % (
        avg["acc"], avg["f1"], avg["prec"], avg["rec"]))

    top_k = 15
    top = sorted(zip(FEAT_NAMES, feature_imps), key=lambda kv: -kv[1])[: top_k]
    print()
    print("Top %d features:" % top_k)
    for name, imp in top:
        print("  %s  %.4f" % (name.ljust(22), imp))

    if out_md:
        os.makedirs(os.path.dirname(out_md), exist_ok=True)
        with open(out_md, "w", encoding="utf-8") as fh:
            fh.write("# HR-08 v0 — LI-DATA fall/nofall RandomForest baseline\n\n")
            fh.write("## 数据\n")
            fh.write("- 每类 %d 帧， 总 %d 帧， 5-fold stratified\n" % (n_per_class, len(X)))
            fh.write("- 特征： %d 维 (见 `pc_apps/human_ml/frame_feature.py`)\n\n" % FEAT_DIM)
            fh.write("## 平均指标\n")
            for k, v in avg.items():
                fh.write("- %s: %.3f\n" % (k, v))
            fh.write("\n## 每 fold\n")
            fh.write("| fold | acc | f1 | prec | rec | cm |\n")
            fh.write("|---|---|---|---|---|---|\n")
            for m in metrics:
                fh.write("| %d | %.3f | %.3f | %.3f | %.3f | %s |\n" % (
                    m["fold"], m["acc"], m["f1"], m["prec"], m["rec"],
                    m["cm"]))
            fh.write("\n## Top %d 特征重要性\n" % top_k)
            for name, imp in top:
                fh.write("- `%s`  %.4f\n" % (name, imp))
            fh.write("\n训练时间： %s\n" % time.strftime("%Y-%m-%d %H:%M:%S"))
        print("wrote", out_md)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fast", action="store_true", help="每类 1000 帧 smoke")
    ap.add_argument("--n-per-class", type=int, default=None)
    ap.add_argument("--out", default=None,
                     help="输出 markdown 报告路径")
    args = ap.parse_args()
    if args.fast:
        n = args.n_per_class or 1000
    elif args.n_per_class:
        n = args.n_per_class
    else:
        n = 40000  # 全量
    out = args.out or (r"D:\Code\ldiar\ML\docs\rf_v0_report.md")
    run(n, out_md=out)


if __name__ == "__main__":
    main()

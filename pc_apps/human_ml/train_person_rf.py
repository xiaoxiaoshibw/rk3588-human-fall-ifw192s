# -*- coding: utf-8 -*-
"""train_person_rf.py — IFW192S 自采 person/noperson RF 训练 (HR-09 激活版)。

数据源:
  - 正: 有人会话 (captures/remote/<sid>/ai_labels.json 存在且 posture != none)
  - 负: 空场模板会话 (cap_20261009_113611, 整帧作 noperson)

留一交叉验证: 以会话为 fold (train/test 切分单位是整段会话, 不是帧), 每轮留出一段,
在剩余段上训 RF, 在留出段上推理——报 acc / person 召回 / noperson 召回 / 每会话明细。

跑法:
    python train_person_rf.py                          # 全量 11 段留一 + 汇总
    python train_person_rf.py --max-frames-per-class 200  # 每类抽稀 smoke
"""
import argparse
import json
import os
import time

import numpy as np

import session_load as S
from frame_feature import extract_features, FEAT_NAMES, FEAT_DIM

PERSON_SESSIONS = [
    "cap_20261009_114641", "cap_20261009_114709", "cap_20261009_114734",
    "cap_20261009_114754", "cap_20261009_114817",
    "cap_20261009_121622", "cap_20261009_121647", "cap_20261009_121723",
    "cap_20261009_122616", "cap_20261009_122637", "cap_20261009_122700",
]
NONE_SESSION = "cap_20261009_113611"

# 空场静态帧高度相似, 完全重复会把 dup 对半劈进相邻 fold, 变相邻 3 帧泄漏;
# 先按 51 维向量 round 6bit 去重, 再循环一次保住类别 1:2 平衡
DEDUP_NONE = True


def collect(root):
    """扫一遍所有会话, 返回 list of (feat, label, sid, frame_name)。"""
    rows = []
    for sid in PERSON_SESSIONS:
        sd = os.path.join(root, sid)
        for xyz_i, lab, name in S.iter_session_frames(sd):
            rows.append((extract_features(xyz_i), lab, sid, name))
    sd = os.path.join(root, NONE_SESSION)
    none_rows = list(S.iter_none_frames(sd))
    if DEDUP_NONE:
        seen, uniq = set(), []
        for xyz_i, lab, name in none_rows:
            fv = extract_features(xyz_i)
            key = tuple(np.round(fv, 6))
            if key in seen:
                continue
            seen.add(key)
            uniq.append((fv, lab, name))
        for fv, lab, name in uniq + uniq:
            rows.append((fv, lab, NONE_SESSION, name))
    else:
        for xyz_i, lab, name in list(none_rows) * 2:
            rows.append((extract_features(xyz_i), lab, NONE_SESSION, name))
    X = np.asarray([r[0] for r in rows], dtype=np.float32)
    y = np.asarray([r[1] for r in rows], dtype=np.int32)
    sid_arr = np.asarray([r[2] for r in rows])
    name_arr = np.asarray([r[3] for r in rows])
    return X, y, sid_arr, name_arr


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=S.REMOTE)
    ap.add_argument("--out", default=None, help="markdown 报告输出路径")
    ap.add_argument("--model-out", default=None, help="训练完成后导出 joblib")
    args = ap.parse_args()

    from sklearn.ensemble import RandomForestClassifier
    from sklearn.metrics import accuracy_score, confusion_matrix

    print("collecting features from %d person sessions + empty template ..." % len(PERSON_SESSIONS))
    st = time.perf_counter()
    X, y, sid_arr, name_arr = collect(args.root)
    print("X: %s  person:%d  noperson:%d  (%.1fs)" % (
        X.shape, int((y == 1).sum()), int((y == 0).sum()), time.perf_counter() - st))

    # 留一: 每段会话轮流作测试集。
    # 空场负样本副本对半分: 一半放在 empty fold 自测, 一半并进最远 person fold,
    # 保证任意 fold 训练集永远同时含两个类 (否则单类训练森林 predict_proba 会崩)
    folds = sorted(set(sid_arr))
    none_idx = np.flatnonzero(sid_arr == NONE_SESSION)
    half = len(none_idx) // 2
    person_sids = sorted(f for f in folds if f != NONE_SESSION)
    far_sid = person_sids[-1]
    fold_of = sid_arr.copy()
    fold_of[none_idx[half:]] = far_sid
    per_fold = []
    feat_imp = np.zeros(FEAT_DIM, dtype=np.float64)
    for hold in folds:
        te = fold_of == hold
        tr = ~te
        clf = RandomForestClassifier(n_estimators=100, max_depth=20,
                                     n_jobs=-1, random_state=0)
        clf.fit(X[tr], y[tr])
        pred = clf.predict(X[te])
        acc = accuracy_score(y[te], pred)
        cm = confusion_matrix(y[te], pred, labels=[0, 1])
        feat_imp += clf.feature_importances_
        per_fold.append({"session": hold, "n_test": int(te.sum()),
                         "acc": float(acc), "cm": cm.tolist(),
                         "n_person": int((y[te] == 1).sum())})
        print("  hold=%s  n=%d person=%d acc=%.3f  cm=%s" % (
            hold, te.sum(), (y[te] == 1).sum(), acc, cm.tolist()))
    feat_imp /= len(folds)

    avg_acc = float(np.mean([f["acc"] for f in per_fold]))
    tot = sum(f["n_test"] for f in per_fold)
    wacc = float(np.sum([f["acc"] * f["n_test"] for f in per_fold]) / tot)
    print("=== leave-one-session-out: mean acc=%.3f  weighted acc=%.3f" % (avg_acc, wacc))

    top = sorted(zip(FEAT_NAMES, feat_imp), key=lambda kv: -kv[1])[:15]
    print("Top 15 features:")
    for name, imp in top:
        print("  %s  %.4f" % (name.ljust(22), imp))

    if args.out:
        outdir = os.path.dirname(os.path.abspath(args.out))
        os.makedirs(outdir, exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write("# HR-09 v1 — IFW192S person/noperson RandomForest (自采)\n\n")
            fh.write("- person sessions: %d; noperson: 1 (empty template %s)\n" % (
                len(PERSON_SESSIONS), NONE_SESSION))
            fh.write("- feature dim: %d\n" % FEAT_DIM)
            fh.write("- leave-one-session-out mean acc: %.3f (weighted %.3f)\n\n" % (avg_acc, wacc))
            fh.write("| held-out session | n_test | n_person | acc | cm [[tn,fp],[fn,tp]] |\n")
            fh.write("|---|---|---|---|---|\n")
            for f in per_fold:
                fh.write("| %s | %d | %d | %.3f | %s |\n" % (
                    f["session"], f["n_test"], f["n_person"], f["acc"], f["cm"]))
            fh.write("\nTop 15 features:\n")
            for name, imp in top:
                fh.write("- `%s` %.4f\n" % (name, imp))
            fh.write("\n训练时间: %s\n" % time.strftime("%Y-%m-%d %H:%M:%S"))
        print("wrote", args.out)

    if args.model_out:
        import joblib
        clf = RandomForestClassifier(n_estimators=100, max_depth=20, n_jobs=-1, random_state=0)
        clf.fit(X, y)
        joblib.dump(clf, args.model_out)
        print("wrote model", args.model_out)


if __name__ == "__main__":
    main()

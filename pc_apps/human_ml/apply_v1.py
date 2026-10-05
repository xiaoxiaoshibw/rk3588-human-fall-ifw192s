# -*- coding: utf-8 -*-
"""apply_v1.py — 用训练好的 RF v0 在我们 IFW192S 会话上 inference.

跨域实验： LI-DATA 是虚拟贴地雷达， 我们是实际高装 192 线雷达。
v1 结果告诉这场仗到底是"特征跨域不动"还是"特征不能跨域"。
"""
import argparse
import json
import os
import time

import numpy as np

from lidata_load import LidarDataLoader, LABEL_FALL, LABEL_NO_FALL
from frame_feature import extract_features, FEAT_DIM, FEAT_NAMES


def load_real_session_frame(session_dir, fi, meta, raw):
    f = meta["frames"][fi]
    seg = raw[f["offset_points"]: f["offset_points"] + f["count_points"]]
    f32v = seg.view(np.float32).reshape(-1, 7)
    xyz = f32v[:, :3]
    inten = f32v[:, 3]
    return np.column_stack([xyz, inten]).astype(np.float32)


def load_real_session(session_dir):
    meta = json.load(open(os.path.join(session_dir, "meta.json"), encoding="utf-8"))
    raw = np.memmap(os.path.join(session_dir, "points.bin"),
                     dtype=np.uint8, mode="r").reshape(-1, 28)
    return meta, raw


def train_rf_full(n_per_class=4000):
    """全量 RF 训练 — 用这次 inference 的版本。
    smoke 用 1000 帧/类； 完整版用全量。"""
    from sklearn.ensemble import RandomForestClassifier
    print("train RF on %d frames/class..." % n_per_class)
    with LidarDataLoader() as ld:
        X_rows = []
        y_rows = []
        cnt = {LABEL_FALL: 0, LABEL_NO_FALL: 0}
        for xyz, lab, path in ld.iter_frames():
            if cnt[lab] >= n_per_class:
                continue
            cnt[lab] += 1
            X_rows.append(extract_features(xyz))
            y_rows.append(lab)
            if cnt[LABEL_FALL] >= n_per_class and cnt[LABEL_NO_FALL] >= n_per_class:
                break
    X = np.asarray(X_rows, dtype=np.float32)
    y = np.asarray(y_rows, dtype=np.int32)
    clf = RandomForestClassifier(n_estimators=100, max_depth=20, n_jobs=-1, random_state=0)
    clf.fit(X, y)
    print("done training")
    return clf


def apply_session(clf, session_dir, save=True):
    meta, raw = load_real_session(session_dir)
    n = len(meta["frames"])
    out_frames = []
    st = time.perf_counter()
    for fi in range(n):
        xyz_i = load_real_session_frame(session_dir, fi, meta, raw)
        fv = extract_features(xyz_i).reshape(1, -1)
        proba = clf.predict_proba(fv)[0]
        label = int(proba[1] >= 0.5)
        out_frames.append({
            "frame": fi,
            "label": "fall" if label == 1 else "nofall",
            "prob_fall": float(proba[1]),
        })
    dt = time.perf_counter() - st
    n_fall = sum(1 for f in out_frames if f["label"] == "fall")
    result = {
        "session_id": meta.get("session_id"),
        "algo": "rf_v0_lidata_fall_nofall",
        "n_frames": n,
        "n_fall": n_fall,
        "n_nofall": n - n_fall,
        "avg_prob_fall": float(np.mean([f["prob_fall"] for f in out_frames])),
        "per_frame_ms": round(dt * 1000 / max(1, n), 1),
        "frames": out_frames,
    }
    if save:
        p = os.path.join(session_dir, "ml_labels.json")
        with open(p, "w", encoding="utf-8") as fh:
            json.dump(result, fh, ensure_ascii=False)
        print("wrote", p)
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sessions", nargs="+",
                     help="session 目录列表")
    ap.add_argument("--n-per-class", type=int, default=4000,
                     help="RF 训练集大小 （每类）")
    ap.add_argument("--model", default=None,
                     help="复用现成 joblib model 不训练")
    args = ap.parse_args()

    if args.model and os.path.isfile(args.model):
        import joblib
        clf = joblib.load(args.model)
        print("loaded model from", args.model)
    else:
        clf = train_rf_full(args.n_per_class)

    for sd in args.sessions:
        res = apply_session(clf, sd)


if __name__ == "__main__":
    main()

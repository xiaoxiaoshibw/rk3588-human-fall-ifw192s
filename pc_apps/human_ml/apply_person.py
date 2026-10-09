# -*- coding: utf-8 -*-
"""apply_person.py — 用训好的 person/noperson RF 在 IFW192S 会话上 inference.

对每个会话产出 person_labels.json:
  {session_id, model_sha256, n_frames, per_frame: [{frame, person_prob, person}]}
空场金标检查: 期望 empty 会话 person 概率低; 有人会话 person 概率高.
"""
import argparse
import hashlib
import json
import os
import sys

import numpy as np

from frame_feature import extract_features
from session_load import load_level_frames, crop_roi


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for blk in iter(lambda: fh.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()


def apply_session(clf, session_dir, roi=None):
    """roi: None → 整帧 (裁掉地板杂波); (x,y,r) → 先裁圆柱再特征。"""
    out = {"session_id": os.path.basename(session_dir.rstrip("\\/")),
           "roi": roi, "frames": []}
    for xyz_i, fi in load_level_frames(session_dir):
        if roi is not None:
            x, y, r = roi
            frame = crop_roi(xyz_i, x, y, r)
        else:
            frame = xyz_i[xyz_i[:, 2] >= 0.05]
        if len(frame) < 10:
            out["frames"].append({"frame": fi, "person_prob": None, "person": None})
            continue
        fv = extract_features(frame).reshape(1, -1)
        prob = float(clf.predict_proba(fv)[0, 1])
        out["frames"].append({"frame": fi, "person_prob": prob, "person": int(prob >= 0.5)})
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sessions", nargs="+", help="captures/remote 下的会话目录")
    ap.add_argument("--model", required=True, help="joblib RF 模型")
    ap.add_argument("--save", action="store_true", help="写 person_labels.json 回会话目录")
    args = ap.parse_args()

    import joblib
    clf = joblib.load(args.model)
    msha = sha256(args.model)
    for sd in args.sessions:
        res = apply_session(clf, sd)
        res["model_sha256"] = msha
        probs = [f["person_prob"] for f in res["frames"] if f["person_prob"] is not None]
        if not probs:
            print("%s: no frames" % sd)
            continue
        probs = np.asarray(probs)
        n_person = sum(1 for f in res["frames"] if f.get("person") == 1)
        print("%s  n=%d person=%d  P(person) mean=%.3f p90=%.3f" % (
            sd, len(probs), n_person, probs.mean(), np.percentile(probs, 90)))
        if args.save:
            out = os.path.join(sd, "person_labels.json")
            with open(out, "w", encoding="utf-8") as fh:
                json.dump(res, fh, ensure_ascii=False)
            print("  wrote", out)


if __name__ == "__main__":
    main()

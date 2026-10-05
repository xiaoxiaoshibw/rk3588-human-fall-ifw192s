# -*- coding: utf-8 -*-
"""run_session_limb.py <session_dir> — 用 ai_labels.json 当 ROI seed + 验证集跑 limb。

逻辑：
  - 若有 ai_labels.json: 按帧读取 (posture, x, y, r_xy), 当 LimbTracker 的 hint seed;
    posture==none 的帧跳过 limb 检测直接输出 detected=False
  - 否则 fallback: 旧逻辑 (limb_lock.json 或完全自适应)
"""
import json
import os
import sys
import time

import numpy as np

from limb_lib import LimbTracker, detect_frame


def load_session(session_dir):
    meta = json.load(open(os.path.join(session_dir, "meta.json"), encoding="utf-8"))
    binp = os.path.join(session_dir, "points.bin")
    raw = np.memmap(binp, dtype=np.uint8, mode="r").reshape(-1, 28)
    f32 = raw.view(np.float32).reshape(len(raw), 7)
    return meta, f32


def frame_xyz(meta, f32, fi):
    f = meta["frames"][fi]
    off = f["offset_points"]; cnt = f["count_points"]
    seg = f32[off:off+cnt]
    return seg[:, :3].astype(np.float32, copy=True)


def load_ai_labels(session_dir, n_frames):
    """从 ai_labels.json 读真值， 返回 per-frame list[dict(posture, x, y, r_xy) | None]."""
    p = os.path.join(session_dir, "ai_labels.json")
    if not os.path.isfile(p):
        return None
    doc = json.load(open(p, encoding="utf-8"))
    fr = doc.get("frames") or {}
    per_frame = [None] * n_frames
    for rng, lab in fr.items():
        if rng == "range_syntax":
            continue
        if "-" not in rng:
            continue
        a_s, b_s = rng.split("-", 1)
        a, b = int(a_s), int(b_s)
        for fi in range(max(0, a), min(n_frames, b + 1)):
            per_frame[fi] = lab
    return per_frame


def main(session_dir):
    meta, f32 = load_session(session_dir)
    n_frames = len(meta["frames"])
    ai_labels = load_ai_labels(session_dir, n_frames)

    out_frames = []
    n_det = 0

    # 旧用户 pin 兜底
    lock_seed = None
    lock_path = os.path.join(session_dir, "limb_lock.json")
    if ai_labels is None and os.path.isfile(lock_path):
        try:
            j = json.load(open(lock_path, encoding="utf-8"))
            x, y = j.get("x"), j.get("y")
            if isinstance(x, (int, float)) and isinstance(y, (int, float)):
                lock_seed = (float(x), float(y))
        except (OSError, ValueError):
            pass

    tracker = LimbTracker(alpha=0.65, lock_seed=lock_seed)
    st = time.perf_counter()
    for fi in range(n_frames):
        xyz = frame_xyz(meta, f32, fi)
        # 每帧 hint: 优先 ai_labels （硬约束）, 否则 tracker.roi_xy （软）
        hint = None
        hint_r = None
        if ai_labels is not None:
            lab = ai_labels[fi]
            if lab is None or lab.get("posture") == "none" or lab.get("x") is None:
                rec = {"frame": fi, "detected": False, "reason": "ai_label_none",
                       "torso_tilt_deg": None,
                       "ai_label_posture": lab.get("posture") if lab else None}
                out_frames.append(rec)
                continue
            hint = (float(lab["x"]), float(lab["y"]))
            hint_r = float(lab.get("r_xy") or 0.7)
        elif tracker.roi_xy:
            hint = tracker.roi_xy
        prev = None
        if hint:
            prev = {"roi_xy": hint, "roi_r": hint_r}
        raw = detect_frame(xyz, prev=prev)
        sm = tracker.smooth(raw)
        if sm["detected"]:
            n_det += 1
        rec = {"frame": fi, "detected": sm["detected"], "reason": sm["reason"],
               "torso_tilt_deg": sm["torso_tilt_deg"],
               "torso_tilt_raw_deg": sm.get("torso_tilt_raw_deg")}
        if ai_labels is not None and ai_labels[fi]:
            rec["ai_label_posture"] = ai_labels[fi].get("posture")
        if sm["keypoints"]:
            rec["keypoints"] = {k: list(v) if v else None
                                 for k, v in sm["keypoints"].items()}
            rec["bones"] = sm["bones"]
            rec["torso_axis"] = sm["torso_axis"]
            rec["torso_centroid"] = sm["torso_centroid"]
        out_frames.append(rec)
    dt = time.perf_counter() - st
    result = {
        "session_id": meta.get("session_id"),
        "algo": "human_limb_v2_ai_hint",
        "generated_iso": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "uses_ai_labels": ai_labels is not None,
        "frames": out_frames,
        "stats": {
            "frames_total": n_frames,
            "frames_detected": n_det,
            "processing_sec": round(dt, 2),
            "per_frame_ms": round(dt * 1000.0 / max(1, n_frames), 1),
        },
    }
    out_json = os.path.join(session_dir, "limb_labels.json")
    with open(out_json, "w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False)
    out_js = os.path.join(session_dir, "limb_labels.js")
    with open(out_js, "w", encoding="utf-8") as fh:
        fh.write("window.LIMB_LABELS = ")
        json.dump(result, fh, ensure_ascii=False)
        fh.write(";\n")
    print("frames:", n_frames, "detected:", n_det,
          "elapsed", round(dt, 2), "s", "per-frame",
          out_frames and round(dt * 1000 / n_frames, 1), "ms")
    print("uses_ai_labels:", ai_labels is not None)
    print("wrote", out_json)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    main(sys.argv[1])

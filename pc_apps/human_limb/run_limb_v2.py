# -*- coding: utf-8 -*-
"""run_limb_v2.py — 对一段会话跑 limb_v2 并生成报告。

输出：
  <sid>/limb_v2_labels.json — 完整 per-frame events (state, keypoints, conf)
  <sid>/limb_v2_report.md — 人类可读报告

可跟 ai_labels.json 比对：
  ai_posture = none → 算法 state == none
  ai_posture = stand → state in (stand, lean)
  ai_posture = bend → state == bend
  一致率 = 吻合帧数 / ai_labeled_frame 总数
"""
import json
import os
import sys
import time

import numpy as np

from limb_v2 import BODY_KP6, detect_frame_v2


def load_session(session_dir):
    meta = json.load(open(os.path.join(session_dir, "meta.json"), encoding="utf-8"))
    raw = np.memmap(os.path.join(session_dir, "points.bin"),
                     dtype=np.uint8, mode="r").reshape(-1, 28)
    return meta, raw


def frame_xyzi_rt(raw, fi, meta):
    f = meta["frames"][fi]
    seg = raw[f["offset_points"]: f["offset_points"] + f["count_points"]]
    f32v = seg.view(np.float32).reshape(-1, 7)
    u16v = seg.view(np.uint16).reshape(-1, 14)
    xyz = f32v[:, :3]
    i_int = f32v[:, 3]
    ring = u16v[:, 8].astype(np.float32)   # @16 字节 → col 8
    t = f32v[:, 5]                          # @20 字节 → col 5
    return np.column_stack([xyz, i_int, ring, t]).astype(np.float32)


def load_ai_labels(session_dir, n):
    p = os.path.join(session_dir, "ai_labels.json")
    if not os.path.isfile(p):
        return None
    doc = json.load(open(p, encoding="utf-8"))
    fr = (doc.get("frames") or {})
    out = [None] * n
    for rng, lab in fr.items():
        if rng == "range_syntax" or "-" not in rng:
            continue
        a, b = rng.split("-", 1)
        for fi in range(max(0, int(a)), min(n, int(b) + 1)):
            out[fi] = lab
    return out


def main(session_dir):
    meta, raw = load_session(session_dir)
    n = len(meta["frames"])
    ai = load_ai_labels(session_dir, n)

    # 会话级固定地面 z0 (整个会话内一致）
    all_z = raw.view(np.float32).reshape(-1, 7)[:, 2]
    all_z = all_z[(all_z > -1.5) & (all_z < 1.5)]
    counts, edges = np.histogram(all_z, bins=100, range=(-1.5, 1.5))
    i0 = int(np.argmax(np.convolve(counts, np.ones(3) / 3, mode="same")))
    z0 = float(0.5 * (edges[i0] + edges[i0 + 1]))
    ground_z_fn = lambda q: np.full(q.shape[0], z0)

    out_frames = []
    ref_ir = None      # 参考帧存储， 每 20 帧才更新
    ref_idx = 0
    prev_axis = None
    st_t = time.perf_counter()
    n_stand = n_bend = n_none = 0
    for fi in range(n):
        xyz_ir = frame_xyzi_rt(raw, fi, meta)
        if ref_ir is None:
            ref_ir = xyz_ir
            ref_idx = fi
        elif fi - ref_idx >= 20:
            ref_ir = xyz_ir
            ref_idx = fi
        prev_arg = {"xyz_ir_prev": ref_ir, "axis": prev_axis} if (fi != ref_idx) else None
        r = detect_frame_v2(xyz_ir, prev=prev_arg, ground_z_fn=ground_z_fn)
        axis_raw = r.pop("axis", None)
        if axis_raw is not None:
            prev_axis = np.asarray(axis_raw)
        r.pop("xyz_ir_prev", None)
        if axis_raw is not None:
            r["axis"] = [float(v) for v in np.asarray(axis_raw)]
        if ai and ai[fi]:
            r["ai_label"] = ai[fi].get("posture")
        out_frames.append(r)
        if r["state"] == "stand":
            n_stand += 1
        elif r["state"] == "bend":
            n_bend += 1
        elif r["state"] in ("lean",):
            n_stand += 1
        else:
            n_none += 1
    dt = time.perf_counter() - st_t

    # 弯腰事件
    events = []
    cur = None
    for i, r in enumerate(out_frames):
        if r["state"] == "bend" and (r.get("bend_deg") or 0) >= 45 and (r.get("conf") or 0) >= 0.30:
            if cur is None:
                cur = {"start": i, "peak": r.get("bend_deg"), "peak_conf": r.get("conf")}
            else:
                cur["peak"] = max(cur["peak"], r.get("bend_deg"))
                cur["peak_conf"] = max(cur["peak_conf"], r.get("conf"))
        else:
            if cur and (i - cur["start"]) >= 3:
                cur["end"] = i - 1
                events.append(cur)
            cur = None
    if cur and (n - cur["start"]) >= 3:
        cur["end"] = n - 1
        events.append(cur)

    # 跟 ai_labels 验证
    verify = None
    if ai:
        n_eval = 0
        n_match = 0
        for i, r in enumerate(out_frames):
            lab = ai[i]
            if not lab:
                continue
            n_eval += 1
            ap = lab.get("posture")
            st = r["state"]
            if ap == "none" and st == "none":
                n_match += 1
            elif ap == "stand" and st in ("stand", "lean"):
                n_match += 1
            elif ap == "bend" and st == "bend":
                n_match += 1
        verify = {"frames_evaluated": n_eval, "frames_match": n_match,
                   "match_rate": round(n_match / max(1, n_eval), 3)}

    result = {
        "session_id": meta.get("session_id"),
        "algo": "limb_v2_chan_dynamic",
        "generated_iso": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "ground_z0": z0,
        "frames": out_frames,
        "stats": {
            "frames_total": n,
            "n_stand": n_stand,
            "n_bend": n_bend,
            "n_none": n_none,
            "bend_events": events,
            "verify_vs_ai_labels": verify,
            "processing_sec": round(dt, 2),
            "per_frame_ms": round(dt * 1000 / max(1, n), 1),
        },
    }
    out_json = os.path.join(session_dir, "limb_v2_labels.json")
    with open(out_json, "w", encoding="utf-8") as fh:
        json.dump(result, fh, ensure_ascii=False)

    # Markdown 报告
    rep = os.path.join(session_dir, "limb_v2_report.md")
    with open(rep, "w", encoding="utf-8") as fh:
        fh.write("# limb_v2 报告 — %s\n\n" % meta.get("session_id"))
        fh.write("- 帧总数： %d\n" % n)
        fh.write("- stand/lean: %d\n- bend: %d\n- none: %d\n" % (n_stand, n_bend, n_none))
        fh.write("- 弯腰事件： %d 个\n" % len(events))
        for e in events:
            fh.write("  - f%d..f%d  peak=%.1f°  conf=%.2f\n" % (
                e["start"], e["end"], e["peak"], e["peak_conf"]))
        if verify:
            fh.write("- vs ai_labels: %d/%d = %.1f%%\n" % (
                verify["frames_match"], verify["frames_evaluated"],
                verify["match_rate"] * 100))
        fh.write("- 耗时： %.2f s  (%.1f ms/帧）\n" % (dt, dt * 1000 / max(1, n)))
    print("frames:", n, "stand:", n_stand, "bend:", n_bend, "none:", n_none,
          "events:", len(events), "per-frame", round(dt * 1000 / max(1, n), 1), "ms")
    if verify:
        print("vs ai_labels match: %.1f%%" % (verify["match_rate"] * 100))
    print("wrote", out_json)
    print("wrote", rep)


if __name__ == "__main__":
    main(sys.argv[1])

# -*- coding: utf-8 -*-
"""audit_fusion_sessions.py — HUMAN-UNIFY-FUSION-R1 F0: 新 9 会话入库审计 (只读).

逐会话:
  - meta 契约 (point_file/stride/layout/frames 连续性, 复用 data_loader.js 同律)
  - 帧数/有效帧数/采样周期 (bag_time 中位间隔 + 缺口)
  - points.bin / meta.json SHA256
  - 点数分布、坐标范围 (raw 传感系) 与 leveled (REF R/T, 同 render_person_label) 可用性统计
  - GT 状态: meta.human_annotations / ai_labels.json / 无 → HUMAN_UNVERIFIED / PSEUDO_LABEL / UNKNOWN
  - 文件名 display_name ↔ 工单 S1..S9 活动类型核对

不修改任何会话文件。输出 SESSION_DATASET_MANIFEST.json (默认写工单证据目录)。
跑法:  python audit_fusion_sessions.py [--root captures/remote] [--out <manifest.json>]
"""
import argparse
import hashlib
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from render_person_label import R, T  # noqa: E402  (leveled 契约同源)

# 工单 §F0 给定的 9 会话 (sid ↔ 工单显示名 ↔ 帧数, 已与工单表格核对一致)
EXPECTED = [
    ("cap_20261010_175227", "S1-empty-with-furniture", 304),
    ("cap_20261010_175429", "S3-walk-x-near", 258),
    ("cap_20261010_175553", "S3-walk-y-far", 464),
    ("cap_20261010_175804", "S4-walk-stop-walk", 239),
    ("cap_20261010_175943", "S5-turn-in-place", 202),
    ("cap_20261010_180235", "S6-occlusion", 238),
    ("cap_20261010_180337", "S7-far-5m", 251),
    ("cap_20261010_180557", "S8-still-retention-long", 523),
    ("cap_20261010_180751", "S9-two-person-cross", 126),
]
# 活动类型 (来自 NEW_CAPTURE_NOTES.md 九类 + 工单 §0 表格)
ACTIVITY = {
    "S1-empty-with-furniture": "empty_with_furniture",
    "S3-walk-x-near": "walk_x_near",
    "S3-walk-y-far": "walk_y_far_roundtrip",
    "S4-walk-stop-walk": "walk_stop_walk",
    "S5-turn-in-place": "turn_in_place",
    "S6-occlusion": "occlusion_reappear",
    "S7-far-5m": "far_distance_ladder",
    "S8-still-retention-long": "still_retention_60s",
    "S9-two-person-cross": "two_person_cross",
}
STRIDE = 28


def sha256_file(path, _buf=bytearray(1 << 20)):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for blk in iter(lambda: fh.readinto(_buf), 0):
            h.update(_buf[:blk])
    return h.hexdigest()


def gt_status(session_dir, meta):
    if isinstance(meta.get("human_annotations"), list) and meta["human_annotations"]:
        return {"level": "HUMAN_UNVERIFIED", "source": "meta.human_annotations",
                "count": len(meta["human_annotations"])}
    p = os.path.join(session_dir, "ai_labels.json")
    if os.path.isfile(p):
        d = json.load(open(p, encoding="utf-8"))
        return {"level": "PSEUDO_LABEL", "source": "ai_labels.json (%s)" % d.get("labelled_by", "?"),
                "count": len(d.get("frames", {}))}
    return {"level": "UNKNOWN", "source": "no labels", "count": 0}


def audit_session(root, sid, display, expect_frames):
    sd = os.path.join(root, sid)
    rec = {"session_id": sid, "display_name_expected": display,
           "activity": ACTIVITY[display], "dir": os.path.relpath(sd).replace("\\", "/"),
           "checks": {}, "issues": []}
    meta_path = os.path.join(sd, "meta.json")
    points_path = os.path.join(sd, "points.bin")
    meta_body = open(meta_path, "rb").read()
    meta = json.loads(meta_body.decode("utf-8"))
    rec["meta_sha256"] = hashlib.sha256(meta_body).hexdigest()
    rec["points_sha256"] = sha256_file(points_path)
    # --- meta 契约 ---
    assert meta["point_file"] == "points.bin" and meta["point_stride_bytes"] == STRIDE, "契约 stride"
    assert meta["point_layout"]["fields"] == ["x", "y", "z", "intensity", "ring", "timestamp"], "契约 fields"
    frames = meta["frames"]
    n_frames = len(frames)
    total = meta["total_points"]
    end = 0
    gaps = []
    prev_t = None
    for i, f in enumerate(frames):
        if f["offset_points"] != end:
            rec["issues"].append("frame %d offset 非连续" % i)
        end += f["count_points"]
        if prev_t is not None and f["bag_time_sec"] < prev_t:
            rec["issues"].append("frame %d 时间回退" % i)
        prev_t = f["bag_time_sec"]
    if end != total:
        rec["issues"].append("帧点数和 != total_points")
    size = os.path.getsize(points_path)
    if size != total * STRIDE:
        rec["issues"].append("points.bin 尺寸 %d != total_points*28 %d" % (size, total * STRIDE))
    # --- 采样周期 ---
    ts = np.array([f["bag_time_sec"] for f in frames], dtype=np.float64)
    dt = np.diff(ts)
    med_dt = float(np.median(dt)) if len(dt) else 0.0
    big_gaps = [[int(i + 1), float(d)] for i, d in enumerate(dt) if d > 2.5 * med_dt and len(dt)]
    seq_missing = None
    if "seq" in frames[0]:
        seqs = np.array([f["seq"] for f in frames], dtype=np.int64)
        seq_missing = int((np.diff(seqs) > 1).sum()) if len(seqs) > 1 else 0
    # --- 点数/坐标统计 ---
    counts = np.array([f["count_points"] for f in frames], dtype=np.int64)
    raw = np.memmap(points_path, dtype=np.uint8, mode="r").reshape(-1, STRIDE).view(np.float32).reshape(-1, 7)
    # 全帧扫量太大 (~23M 点/会话 × 9); 用 ≥strided 采样估计坐标范围 + 精确统计首/中/末帧
    idx_frames = sorted(set([0, n_frames // 2, n_frames - 1]))
    xyz_min = np.full(3, np.inf)
    xyz_max = np.full(3, -np.inf)
    lv_min = np.full(3, np.inf)
    lv_max = np.full(3, -np.inf)
    n_valid = 0
    n_seen = 0
    z_ground_band = []
    for fi in idx_frames:
        f = frames[fi]
        seg = raw[f["offset_points"]: f["offset_points"] + f["count_points"]]
        xyz = seg[:, :3].astype(np.float64)
        v = np.isfinite(xyz).all(axis=1) & np.any(xyz != 0, axis=1)
        n_valid += int(v.sum())
        n_seen += len(xyz)
        xv = xyz[v]
        if not len(xv):
            continue
        xyz_min = np.minimum(xyz_min, xv.min(axis=0))
        xyz_max = np.maximum(xyz_max, xv.max(axis=0))
        lv = xv @ R.T + T
        lv_min = np.minimum(lv_min, lv.min(axis=0))
        lv_max = np.maximum(lv_max, lv.max(axis=0))
        z = lv[:, 2]
        z_ground_band.append(float(((z > -0.15) & (z < 0.15)).mean()))
    rec["checks"] = {
        "n_frames": n_frames, "n_frames_expected": expect_frames,
        "frames_match_workorder": n_frames == expect_frames,
        "total_points": int(total),
        "duration_sec": round(float(ts[-1] - ts[0]), 2),
        "median_dt_sec": round(med_dt, 4),
        "fps_median": round(1.0 / med_dt, 2) if med_dt > 0 else None,
        "dt_gaps_gt_2.5x_median": big_gaps,
        "seq_jump_count": seq_missing,
        "display_name_meta": meta.get("display_name", meta.get("name")),
        "display_name_match": meta.get("display_name", meta.get("name")) == display,
        "meta_leveling_flag": bool(meta.get("leveling")),
        "points_per_frame": {"min": int(counts.min()), "p50": int(np.median(counts)), "max": int(counts.max())},
        "valid_point_ratio_sampled": round(n_valid / max(n_seen, 1), 5),
        "raw_xyz_min": [round(float(v), 3) for v in xyz_min],
        "raw_xyz_max": [round(float(v), 3) for v in xyz_max],
        "leveled_xyz_min": [round(float(v), 3) for v in lv_min],
        "leveled_xyz_max": [round(float(v), 3) for v in lv_max],
        "leveled_ground_band_ratio_sampled": round(float(np.mean(z_ground_band)), 4),
        "leveling_rt": {"source": "render_person_label.R/T (REF)", "sampled_frames": idx_frames},
    }
    rec["gt"] = gt_status(sd, meta)
    rec["checks"]["contract_ok"] = not rec["issues"]
    if not rec["checks"]["display_name_match"]:
        rec["issues"].append("display_name 与工单不符: %s" % rec["checks"]["display_name_meta"])
    if not rec["checks"]["frames_match_workorder"]:
        rec["issues"].append("帧数 %d 与工单 %d 不符" % (n_frames, expect_frames))
    return rec


def main():
    ap = argparse.ArgumentParser()
    here = os.path.dirname(os.path.abspath(__file__))
    ap.add_argument("--root", default=os.path.normpath(os.path.join(here, "..", "..", "captures", "remote")))
    ap.add_argument("--out", default=os.path.normpath(os.path.join(
        here, "..", "..", "docs", "human_capture", "evidence",
        "2026-10-10_human_unify_fusion_r1", "SESSION_DATASET_MANIFEST.json")))
    args = ap.parse_args()
    sessions = [audit_session(args.root, sid, disp, nf) for sid, disp, nf in EXPECTED]
    manifest = {
        "format_version": 1,
        "work_order": "HUMAN-UNIFY-FUSION-R1 F0",
        "generated_by": "pc_apps/human_ml/audit_fusion_sessions.py",
        "root": os.path.relpath(args.root).replace("\\", "/"),
        "readonly_inputs": True,
        "n_sessions": len(sessions),
        "n_frames_total": int(sum(s["checks"]["n_frames"] for s in sessions)),
        "sessions": sessions,
        "all_issues": [{"session_id": s["session_id"], "issues": s["issues"]}
                       for s in sessions if s["issues"]],
    }
    manifest["contract_all_ok"] = all(s["checks"]["contract_ok"] for s in sessions)
    manifest["display_all_match"] = all(s["checks"]["display_name_match"] for s in sessions)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=1)
    print("sessions=%d frames=%d contract_ok=%s display_match=%s" % (
        manifest["n_sessions"], manifest["n_frames_total"],
        manifest["contract_all_ok"], manifest["display_all_match"]))
    for a in manifest["all_issues"]:
        print("ISSUE", a["session_id"], a["issues"])
    print("wrote", args.out)


if __name__ == "__main__":
    main()

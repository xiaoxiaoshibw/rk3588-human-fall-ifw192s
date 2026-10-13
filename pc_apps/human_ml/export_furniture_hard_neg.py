# -*- coding: utf-8 -*-
"""export_furniture_hard_neg.py — HUMAN-UNIFY-FUSION-R1 F3: 家具硬负样本数据入口 (可复现).

设计 (工单 §5 + NOT_GT 语义):
  - 输入: S1-empty-with-furniture 会话 (cap_20261010_175227) 或任何 GT 已冻结的 FURNITURE ROIs
  - 输出: pc_apps/human_ml/furniture_hard_neg.json (样本) + 对应 meta (session/frame_range/xy/半径/label/SHA/GT_version/裁剪算法版本)
  - 可复现: 相同 GT 文件 + 相同本脚本 → 相同家具样本 SHA

跑法 (依赖 GT 后启用):
    python export_furniture_hard_neg.py --gt docs/.../gt_frozen.json --out pc_apps/human_ml/furniture_hard_neg.json

跑法 (无 GT 上下文自动导出 = 仅作工作流演练, 标 UNKNOWN, 不可作为训练数据):
    python export_furniture_hard_neg.py --auto-from-empty-sid cap_20261010_175227 --out <path>
"""
import argparse
import hashlib
import io
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from render_person_label import R, T  # noqa: E402
from frame_feature import extract_features, FEAT_NAMES, FEAT_DIM  # noqa: E402

STRIDE = 28
CROP_VER = "crop_s1_leveled_ref_rt_v1"


def sha256_file(path, _buf=bytearray(1 << 20)):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for blk in iter(lambda: fh.readinto(_buf), 0):
            h.update(_buf[:blk])
    return h.hexdigest()


def _frame_leveled(root, sid, fi):
    meta = json.load(open(os.path.join(root, sid, "meta.json"), encoding="utf-8"))
    raw = np.memmap(os.path.join(root, sid, "points.bin"), dtype=np.uint8, mode="r"
                    ).reshape(-1, STRIDE).view(np.float32).reshape(-1, 7)
    f = meta["frames"][fi]
    seg = raw[f["offset_points"]: f["offset_points"] + f["count_points"]]
    xyz = seg[:, :3].astype(np.float64)
    v = np.isfinite(xyz).all(axis=1) & np.any(xyz != 0, axis=1)
    lv = xyz[v] @ R.T + T
    return np.column_stack([lv, seg[v, 3]]).astype(np.float32)


def crop_roi(xyz_i, x, y, r_xy, z_min=0.05, z_max=2.6):
    dxy = np.sqrt((xyz_i[:, 0] - x) ** 2 + (xyz_i[:, 1] - y) ** 2)
    keep = (dxy <= r_xy) & (xyz_i[:, 2] >= z_min) & (xyz_i[:, 2] <= z_max)
    return xyz_i[keep]


def export_from_gt(root, gt_path):
    """GT 冻结后的正式入口. GT schema 与 gt_workbench TEMPLATE_DOC 一致."""
    gt = json.load(io.open(gt_path, encoding="utf-8"))
    recs = []
    for sid, sdoc in gt["sessions"].items():
        sha = sdoc["session_sha256"]
        for fi_s, fdoc in sdoc["frames"].items():
            fi = int(fi_s)
            for roi in fdoc["rois"]:
                if roi["cls"] != "FURNITURE":
                    continue
                xyzi = _frame_leveled(root, sid, fi)
                crop = crop_roi(xyzi, roi["x"], roi["y"], roi["r_xy"])
                if len(crop) < 30:
                    continue
                recs.append({
                    "session_id": sid, "frame_range": [fi, fi],
                    "xy_center": [roi["x"], roi["y"]], "r_xy": roi["r_xy"],
                    "label": "FURNITURE", "visibility": roi.get("visibility"),
                    "session_sha256": sha, "gt_version": sdoc.get("gt_version"),
                    "crop_algorithm": CROP_VER,
                    "point_count": int(len(crop)),
                    "fv": np.round(extract_features(crop), 8).tolist(),
                })
    return recs


def auto_from_empty_sid(root, sid):
    """无 GT 时的自动导出 (仅用于流程演练; source 标 auto_envelope_unknown).

    用 5cm bg envelope 的 z95 + 0.25m 自身差, 把「背景之上热点簇」视为家具占位.
    不进入模型训练, 只供管线 dry-run 使用.
    """
    from auto_person_label import background_envelope, components
    meta = json.load(open(os.path.join(root, sid, "meta.json"), encoding="utf-8"))
    raw = np.memmap(os.path.join(root, sid, "points.bin"), dtype=np.uint8, mode="r"
                    ).reshape(-1, STRIDE).view(np.float32).reshape(-1, 7)
    cells = background_envelope(root, empty_sid=sid)
    recs = []
    n_frames = len(meta["frames"])
    stride = max(1, n_frames // 20)
    for fi in range(0, n_frames, stride):
        f = meta["frames"][fi]
        seg = raw[f["offset_points"]: f["offset_points"] + f["count_points"]]
        xyz = seg[:, :3].astype(np.float64)
        v = np.isfinite(xyz).all(axis=1) & np.any(xyz != 0, axis=1)
        lv = xyz[v] @ R.T + T
        iv = seg[v, 3]
        if not len(lv):
            continue
        gx = np.floor(lv[:, 0] / 0.05).astype(np.int32)
        gy = np.floor(lv[:, 1] / 0.05).astype(np.int32)
        key = gx * 4096 + gy
        bg = np.array([cells.get(int(k), -10.0) for k in key], dtype=np.float64)
        hot = (lv[:, 2] > bg + 0.25) & (lv[:, 2] > 0.1) & (lv[:, 2] < 2.3)
        if int(hot.sum()) < 30:
            continue
        comps = components(lv[hot, 0], lv[hot, 1])
        for ci, acc in enumerate(comps[:4]):
            if len(acc) < 30:
                continue
            acc = np.asarray(acc, dtype=np.int32)
            pts = lv[hot][acc]
            inten_c = iv[hot][acc]
            xyzi = np.column_stack([pts, inten_c]).astype(np.float32)
            cx, cy = float(np.median(pts[:, 0])), float(np.median(pts[:, 1]))
            r90 = float(np.percentile(np.hypot(pts[:, 0] - cx, pts[:, 1] - cy), 90))
            recs.append({
                "session_id": sid, "frame_range": [fi, fi],
                "xy_center": [round(cx, 3), round(cy, 3)],
                "r_xy": round(max(0.6, min(1.4, 2.0 * r90)), 3),
                "label": "FURNITURE", "visibility": "unknown",
                "session_sha256": {"points": sha256_file(os.path.join(root, sid, "points.bin")),
                                   "meta": sha256_file(os.path.join(root, sid, "meta.json"))},
                "gt_version": "none_auto_envelope",
                "crop_algorithm": CROP_VER + "_pure_env",
                "source": "auto_envelope_unknown (NOT GT, 不可训练)",
                "point_count": int(len(acc)),
                "fv": np.round(extract_features(xyzi), 8).tolist(),
            })
    return recs


def main():
    ap = argparse.ArgumentParser()
    here = os.path.dirname(os.path.abspath(__file__))
    repo = os.path.normpath(os.path.join(here, "..", ".."))
    ap.add_argument("--root", default=os.path.join(repo, "captures", "remote"))
    ap.add_argument("--gt", default=None, help="GT 冻结 JSON (GT_COVERAGE_REPORT §5 格式)")
    ap.add_argument("--auto-from-empty-sid", default=None)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    if args.gt:
        recs = export_from_gt(args.root, args.gt)
        src = "gt"
    elif args.auto_from_empty_sid:
        recs = auto_from_empty_sid(args.root, args.auto_from_empty_sid)
        src = "auto"
    else:
        print("缺 --gt 或 --auto-from-empty-sid")
        sys.exit(2)

    out = {
        "schema": "furniture_hard_neg/v1",
        "source": src,
        "crop_algorithm": CROP_VER,
        "feat_dim": FEAT_DIM, "feat_names": FEAT_NAMES,
        "samples": recs,
        "n_samples": len(recs),
        "note": "样本 fv 已是 extract_features 复算输出, 不是原始裁剪点",
    }
    blob = json.dumps(out, ensure_ascii=False).encode("utf-8")
    out["samples_sha256"] = hashlib.sha256(blob).hexdigest()
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(out, fh, ensure_ascii=False, indent=1)
    print("wrote", args.out, "n=", len(recs), "sha=", out["samples_sha256"])


if __name__ == "__main__":
    main()

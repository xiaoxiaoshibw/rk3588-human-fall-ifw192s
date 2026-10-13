# -*- coding: utf-8 -*-
"""gt_workbench_export.py — HUMAN-UNIFY-FUSION-R1 F0: GT 标注工作台导出 (只读会话数据).

为 9 个新会话生成一个人工标注交付目录 (默认 docs/.../gt_workbench/), 内容:
  - work_order.json            会话索引 + 工单口径
  - <sid>/frames_index.json    帧号/时间戳索引 (人工对照标注用)
  - <sid>/GT_v1.json.template  空 GT 契约模板 (含 session_sha 锚定占位)
  - <sid>/AUTO_CANDIDATES.json 自动前置候选 (--auto 时生成; PSEUDO_LABEL, 非 GT)

契约 schema 与 GT_COVERAGE_REPORT.md §3 一致, 版本 gt_workbench/1。
不写会话目录, 不改任何已存在导出 (--force 才覆盖重算 AUTO_CANDIDATES; 模板/索引已存在即跳过)。

跑法:
  python gt_workbench_export.py                 # 索引+模板 (快)
  python gt_workbench_export.py --auto          # 追加自动候选 (慢, 全帧扫)
"""
import argparse
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from render_person_label import R, T  # noqa: E402
from auto_person_label import background_envelope, components  # noqa: E402

STRIDE = 28
GT_VERSION = "gt_workbench/1"

TEMPLATE_DOC = {
    "schema": GT_VERSION,
    "session_id": "",
    "session_sha256": {"points": "<填 SESSION_DATASET_MANIFEST.json 对应值>", "meta": "<同上>"},
    "annotator": None,
    "annotated_at": None,
    "review_status": "draft",
    "review": {"reviewer": None, "reviewed_at": None, "notes": None},
    "annotation_method": None,
    "frames": {
        "<frame_idx>": {
            "rois": [{"cls": "PERSON|FURNITURE|BACKGROUND|UNKNOWN",
                      "x": 0.0, "y": 0.0, "r_xy": 0.0,
                      "track_id": "P1 (仅 PERSON 必填, 会话内持久)",
                      "visibility": "visible|partial|occluded|null"}],
            "note": None,
        }
    },
    "episodes": [{"track_id": "P1", "born_frame": 0, "exit_frame": None,
                  "still_frames": [[0, 0]], "moving_frames": [[0, 0]], "note": None}],
    "uncertain_intervals": [{"start": 0, "end": 0, "reason": "occlusion|blur|out_of_fov|…"}],
    "_rules": [
        "全帧默认 UNKNOWN — 未标帧不参与任何指标",
        "PERSON 必须 track_id 且同帧唯一; 双人独立 P1/P2",
        "FURNITURE 逐件标注, 供硬负样本 ROI 裁剪",
        "AUTO_CANDIDATES 只是加速建议, 逐帧确认/改正后才算 GT",
        "本文件由人工编辑; review_status 变 reviewed 后才可冻结 SPLITS",
    ],
}


def load_manifest(path):
    m = json.load(open(path, encoding="utf-8"))
    return m["sessions"]


def frames_index(root, sid):
    meta = json.load(open(os.path.join(root, sid, "meta.json"), encoding="utf-8"))
    out = []
    for i, f in enumerate(meta["frames"]):
        out.append({"frame": i, "t": round(f["bag_time_sec"], 3),
                    "n_points": f["count_points"], "rel_s": None})
    t0 = out[0]["t"] if out else 0.0
    for r in out:
        r["rel_s"] = round(r["t"] - t0, 3)
    return out


def auto_candidates(root, sid, empty_sid, max_clusters=8):
    """每帧全部过阈簇 (不套时序门限). 返回 {frame_idx: [cand...]}."""
    print("  %s: 构建空场包络 (%s) ..." % (sid, empty_sid))
    cells = background_envelope(root, empty_sid=empty_sid)
    meta = json.load(open(os.path.join(root, sid, "meta.json"), encoding="utf-8"))
    raw = np.memmap(os.path.join(root, sid, "points.bin"), dtype=np.uint8, mode="r"
                    ).reshape(-1, STRIDE).view(np.float32).reshape(-1, 7)
    out = {}
    step = 1
    for fi in range(0, len(meta["frames"]), step):
        f = meta["frames"][fi]
        seg = raw[f["offset_points"]: f["offset_points"] + f["count_points"]]
        xyz = seg[:, :3].astype(np.float64)
        v = np.isfinite(xyz).all(axis=1) & np.any(xyz != 0, axis=1)
        lv = xyz[v] @ R.T + T
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
        cands = []
        for acc in comps[:max_clusters]:
            if len(acc) < 30:
                continue
            acc = np.asarray(acc, dtype=np.int32)
            hx, hy = lv[hot][acc, 0], lv[hot][acc, 1]
            cx, cy = float(np.median(hx)), float(np.median(hy))
            r90 = float(np.percentile(np.hypot(hx - cx, hy - cy), 90))
            cands.append({"x": round(cx, 3), "y": round(cy, 3),
                          "r_xy": round(max(0.6, min(1.4, 2.0 * r90)), 3),
                          "n_pts": int(len(acc)),
                          "z_max": round(float(lv[hot][acc, 2].max()), 3)})
        if cands:
            out[str(fi)] = cands
    return out


def main():
    ap = argparse.ArgumentParser()
    here = os.path.dirname(os.path.abspath(__file__))
    repo = os.path.normpath(os.path.join(here, "..", ".."))
    ap.add_argument("--root", default=os.path.join(repo, "captures", "remote"))
    ap.add_argument("--manifest", default=os.path.join(
        repo, "docs", "human_capture", "evidence", "2026-10-10_human_unify_fusion_r1",
        "SESSION_DATASET_MANIFEST.json"))
    ap.add_argument("--out", default=os.path.join(
        repo, "docs", "human_capture", "evidence", "2026-10-10_human_unify_fusion_r1",
        "gt_workbench"))
    ap.add_argument("--empty-sid", default="cap_20261010_175227",
                    help="同场景新空场 (S1) 作背景包络")
    ap.add_argument("--auto", action="store_true", help="生成 AUTO_CANDIDATES.json (全帧扫)")
    ap.add_argument("--force", action="store_true", help="允许重算覆盖 AUTO_CANDIDATES")
    args = ap.parse_args()

    sessions = load_manifest(args.manifest)
    os.makedirs(args.out, exist_ok=True)
    wo_path = os.path.join(args.out, "work_order.json")
    work_order = {
        "schema": GT_VERSION,
        "work_order": "HUMAN-UNIFY-FUSION-R1 F0 GT 标注交付包",
        "generated_by": "pc_apps/human_ml/gt_workbench_export.py",
        "readonly_sessions": True,
        "sessions": [{
            "session_id": s["session_id"], "display_name": s["display_name_expected"],
            "activity": s["activity"], "n_frames": s["checks"]["n_frames"],
            "duration_sec": s["checks"]["duration_sec"],
            "session_sha256": {"points": s["points_sha256"], "meta": s["meta_sha256"]},
        } for s in sessions],
    }
    if not os.path.exists(wo_path):
        with open(wo_path, "w", encoding="utf-8") as fh:
            json.dump(work_order, fh, ensure_ascii=False, indent=1)
    for s in sessions:
        sid, disp = s["session_id"], s["display_name_expected"]
        sd = os.path.join(args.out, sid)
        os.makedirs(sd, exist_ok=True)
        idx_path = os.path.join(sd, "frames_index.json")
        if not os.path.exists(idx_path):
            with open(idx_path, "w", encoding="utf-8") as fh:
                json.dump({"session_id": sid, "display_name": disp,
                           "frames": frames_index(args.root, sid)}, fh, ensure_ascii=False, indent=1)
        tpl_path = os.path.join(sd, "GT_v1.json.template")
        if not os.path.exists(tpl_path):
            tpl = dict(TEMPLATE_DOC)
            tpl["session_id"] = sid
            tpl["session_sha256"] = {"points": s["points_sha256"], "meta": s["meta_sha256"]}
            tpl["display_name"] = disp
            tpl["n_frames"] = s["checks"]["n_frames"]
            with open(tpl_path, "w", encoding="utf-8") as fh:
                json.dump(tpl, fh, ensure_ascii=False, indent=1)
        ac_path = os.path.join(sd, "AUTO_CANDIDATES.json")
        if args.auto and (args.force or not os.path.exists(ac_path)):
            cands = auto_candidates(args.root, sid, args.empty_sid)
            with open(ac_path, "w", encoding="utf-8") as fh:
                json.dump({"schema": GT_VERSION, "session_id": sid, "display_name": disp,
                           "source": "auto_candidate (PSEUDO_LABEL, 非GT)",
                           "method": "bg_envelope(%s)+hot(z>bg+0.25, z∈[0.1,2.3])+5cm连通分量, 无单簇/时序门限" % args.empty_sid,
                           "frames": cands}, fh, ensure_ascii=False, indent=1)
            print("  %s: AUTO_CANDIDATES %d 帧有候选" % (sid, len(cands)))
        print("%s 导出完成" % sid)
    print("wrote workbench ->", args.out)


if __name__ == "__main__":
    main()

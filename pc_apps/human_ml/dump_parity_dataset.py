# -*- coding: utf-8 -*-
"""dump_parity_dataset.py — HUMAN-UNIFY-FUSION-R1 F1: 真实簇特征对拍数据集导出 (Python 侧).

从 9 个新会话逐帧跑「新空场 S1 背景 + 5cm 连通分量」得到候选簇 (与 gt_workbench_export
--auto 同源), 每簇:
  - leveled 点集 (float32, 4 位小数) + fv (Python extract_features 51 维, 8 位小数)
  - sid/frame/n_pts/xy/z_max
同时导出边界断面 (edge cases) 的 Python 参考值 (JS 侧用相同输入重算对比):
  n=10 平面簇 (ev2≈0) / n=10 共线簇 (ev1=ev2≈0) / n=9 (<10 全零) /
  n=20 零方差球 (近似各向同性) / n=11 全同强度 / 理想直立人形 (评估已训练模型
  对历史 az 顺序的敏感度: 同一簇两种排序喂 v1 模型的概率差)

输出: docs/human_capture/evidence/2026-10-10_human_unify_fusion_r1/parity_dataset.json
只读会话数据。跑法: python dump_parity_dataset.py [--per-session-cap 60]
"""
import argparse
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from render_person_label import R, T  # noqa: E402
from auto_person_label import background_envelope, components  # noqa: E402
from frame_feature import extract_features, FEAT_NAMES, FEAT_DIM  # noqa: E402
from gt_workbench_export import auto_candidates  # noqa: E402  同源候选生成

STRIDE = 28
NEW_SIDS = [
    ("cap_20261010_175227", "S1-empty-with-furniture"),
    ("cap_20261010_175429", "S3-walk-x-near"),
    ("cap_20261010_175553", "S3-walk-y-far"),
    ("cap_20261010_175804", "S4-walk-stop-walk"),
    ("cap_20261010_175943", "S5-turn-in-place"),
    ("cap_20261010_180235", "S6-occlusion"),
    ("cap_20261010_180337", "S7-far-5m"),
    ("cap_20261010_180557", "S8-still-retention-long"),
    ("cap_20261010_180751", "S9-two-person-cross"),
]
EMPTY_SID = "cap_20261010_175227"


def session_clusters(root, sid, cells, per_session_cap):
    """同 gt_workbench_export.auto_candidates, 但回传簇点集本身 (leveled xyzi)。"""
    meta = json.load(open(os.path.join(root, sid, "meta.json"), encoding="utf-8"))
    raw = np.memmap(os.path.join(root, sid, "points.bin"), dtype=np.uint8, mode="r"
                    ).reshape(-1, STRIDE).view(np.float32).reshape(-1, 7)
    out = []
    n_frames = len(meta["frames"])
    stride = max(1, n_frames // per_session_cap)
    for fi in range(0, n_frames, stride):
        if len(out) >= per_session_cap:
            break
        f = meta["frames"][fi]
        seg = raw[f["offset_points"]: f["offset_points"] + f["count_points"]]
        xyz = seg[:, :3].astype(np.float64)
        inten = seg[:, 3]
        v = np.isfinite(xyz).all(axis=1) & np.any(xyz != 0, axis=1)
        lv = xyz[v] @ R.T + T
        iv = inten[v].astype(np.float32)
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
            fv = extract_features(xyzi)
            out.append({"sid": sid, "frame": int(fi), "cluster": ci,
                        "n_pts": int(len(acc)),
                        "z_max": round(float(pts[:, 2].max()), 3),
                        "x": round(float(np.median(pts[:, 0])), 3),
                        "y": round(float(np.median(pts[:, 1])), 3),
                        "xyzi": np.round(xyzi, 4).tolist(),
                        "fv_py": np.round(fv, 8).tolist()})
    return out


def edge_cases():
    """边界断面: (name, xyzi float32)。JS 侧将在同输入上重算。"""
    rng = np.random.RandomState(7)
    cases = []
    # 1) n=10 平面簇 (z 恒 1.0): ev2 应 ≈ 0
    pts = np.column_stack([2.0 + 0.3 * rng.randn(10), 1.0 + 0.3 * rng.randn(10),
                           np.ones(10), 500 + 100 * rng.rand(10)]).astype(np.float32)
    cases.append(("n10_planar", pts))
    # 2) n=10 共线簇: ev1 = ev2 ≈ 0
    t = np.linspace(0, 1, 10)
    pts = np.column_stack([2.0 + 0.5 * t, 1.0 + 0.5 * t, 1.0 + 1.5 * t,
                           np.full(10, 800.0)]).astype(np.float32)
    cases.append(("n10_collinear", pts))
    # 3) n=9 → 全零
    pts = np.column_stack([rng.randn(9), rng.randn(9), np.abs(rng.randn(9)),
                           rng.rand(9) * 100]).astype(np.float32)
    cases.append(("n9_below_min", pts))
    # 4) n=30 近似零方差球 (两 ev 近重根)
    u = rng.randn(30, 3)
    u /= np.linalg.norm(u, axis=1, keepdims=True)
    pts = np.column_stack([2.0 + 0.20 * u[:, 0], 1.0 + 0.20 * u[:, 1],
                           1.2 + 0.20 * u[:, 2], 400 + 50 * rng.rand(30)]).astype(np.float32)
    cases.append(("n30_isotropic", pts))
    # 5) n=11 全同强度
    pts = np.column_stack([2.0 + 0.4 * rng.rand(11), 1.0 + 0.4 * rng.rand(11),
                           0.2 + 1.6 * rng.rand(11), np.full(11, 666.0)]).astype(np.float32)
    cases.append(("n11_const_intensity", pts))
    # 6) 理想直立人形 (z 柱 + 头), 供 az 顺序敏感度观测
    nb, nh = 400, 60
    body = np.column_stack([
        2.0 + 0.22 * rng.randn(nb), 1.0 + 0.22 * rng.randn(nb),
        0.15 + 1.45 * rng.rand(nb)])
    head = np.column_stack([
        2.0 + 0.11 * rng.randn(nh), 1.0 + 0.11 * rng.randn(nh),
        1.62 + 0.22 * rng.rand(nh)])
    pts = np.vstack([body, head])
    pts = np.column_stack([pts, 300 + 500 * rng.rand(len(pts))]).astype(np.float32)
    cases.append(("ideal_upright_person", pts))
    out = []
    for name, xyzi in cases:
        fv = extract_features(xyzi)
        out.append({"name": name, "n_pts": int(len(xyzi)),
                    "xyzi": np.round(xyzi, 4).tolist(),
                    "fv_py": np.round(fv, 8).tolist()})
    return out


def main():
    ap = argparse.ArgumentParser()
    here = os.path.dirname(os.path.abspath(__file__))
    repo = os.path.normpath(os.path.join(here, "..", ".."))
    ap.add_argument("--root", default=os.path.join(repo, "captures", "remote"))
    ap.add_argument("--out", default=os.path.join(
        repo, "docs", "human_capture", "evidence", "2026-10-10_human_unify_fusion_r1",
        "parity_dataset.json"))
    ap.add_argument("--per-session-cap", type=int, default=60)
    args = ap.parse_args()

    print("构建空场包络 %s ..." % EMPTY_SID)
    cells = background_envelope(args.root, empty_sid=EMPTY_SID)
    records = []
    for sid, disp in NEW_SIDS:
        if sid == EMPTY_SID:
            # S1 是空场: bg 即自身, 热点预期 ≈ 0 — 跳过候选提取, 只记录空集
            print("  %s (%s): 空场模板本体, 跳过候选" % (sid, disp))
            continue
        got = session_clusters(args.root, sid, cells, args.per_session_cap)
        print("  %s (%s): %d 候选簇" % (sid, disp, len(got)))
        records.extend(got)
    ds = {
        "schema": "fusion_parity/v1",
        "feat_dim": FEAT_DIM, "feat_names": FEAT_NAMES,
        "source": {"sessions": [s for s, _ in NEW_SIDS], "background_sid": EMPTY_SID,
                   "method": "bg hot(z>bg+0.25, z∈[0.1,2.3]) + 5cm 连通分量, ≤4簇/帧",
                   "fv_round_decimals": {"fv_py": 8, "xyzi": 4}},
        "clusters": records,
        "edge_cases": edge_cases(),
    }
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(ds, fh, ensure_ascii=False)
    print("clusters=%d edge=%d -> %s" % (len(records), len(ds["edge_cases"]), args.out))


if __name__ == "__main__":
    main()

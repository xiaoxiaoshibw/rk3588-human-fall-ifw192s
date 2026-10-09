# -*- coding: utf-8 -*-
"""session_load.py — IFW192S 自采会话 loader (HR-09 person/noperson)。

与 lidata_load.py 对偶： 遍历 captures/remote 下带 ai_labels.json 的会话,
按帧 yield (xyz_i (N,4) 已按 AI 判读 ROI 裁剪, label 1=person / 0=noperson, name)。

标签源契约 (ai_labels.json, 由 AI 读 render_person_label 图得出):
  {"session_id": "...", "frames": {"<fi>": {"posture": "stand|none",
                                            "x": 2.6, "y": 2.4, "r_xy": 0.8}}}
  posture=="none" 或缺帧 → 该帧不入训练集 (person_session) 或整段作 noperson (none_session)。

坐标约定: 会话原始 bin 为雷达系; 本 loader 用与空场模板一致的 leveled R/T
把每帧点云换到 z=0 地面系再按 (x,y,r_xy) 裁圆柱 ROI, 再喂 frame_feature。
"""
import json
import os

import numpy as np

from render_person_label import R, T

REMOTE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                      "captures", "remote")

PERSON = 1
NOPERSON = 0


def load_level_frames(session_dir):
    """生成器： 每帧 (xyz_i (N,4) leveled [x,y,z,intensity], frame_idx)。meta 顺序。"""
    meta = json.load(open(os.path.join(session_dir, "meta.json"), encoding="utf-8"))
    raw = np.memmap(os.path.join(session_dir, "points.bin"), dtype=np.uint8, mode="r"
                    ).reshape(-1, 28).view(np.float32).reshape(-1, 7)
    for fi, f in enumerate(meta["frames"]):
        seg = raw[f["offset_points"]: f["offset_points"] + f["count_points"]]
        xyz = seg[:, :3].astype(np.float64)
        v = np.isfinite(xyz).all(axis=1) & np.any(xyz != 0, axis=1)
        lv = xyz[v] @ R.T + T
        inten = seg[v, 3]
        yield np.column_stack([lv, inten]).astype(np.float32), fi


def crop_roi(xyz_i, x, y, r_xy, z_min=0.05, z_max=2.6):
    """裁圆柱 ROI: 水平半径 r_xy 内, z ∈ [z_min, z_max] (leveled, 地面=0)。"""
    dxy = np.sqrt((xyz_i[:, 0] - x) ** 2 + (xyz_i[:, 1] - y) ** 2)
    keep = (dxy <= r_xy) & (xyz_i[:, 2] >= z_min) & (xyz_i[:, 2] <= z_max)
    return xyz_i[keep]


def iter_session_frames(session_dir):
    """有人会话： 按 ai_labels 逐帧裁 ROI 后 yield (xyz_i, PERSON, name)。

    ai_labels 缺失或该帧 posture=="none" → 跳过该帧。
    """
    labels_path = os.path.join(session_dir, "ai_labels.json")
    if not os.path.isfile(labels_path):
        return
    labels = json.load(open(labels_path, encoding="utf-8")).get("frames", {})
    sid = os.path.basename(session_dir.rstrip("\\/"))
    for xyz_i, fi in load_level_frames(session_dir):
        rec = labels.get(str(fi))
        if not rec or rec.get("posture") in (None, "none"):
            continue
        x, y, r = rec.get("x"), rec.get("y"), rec.get("r_xy")
        if x is None or y is None or r is None:
            continue
        roi = crop_roi(xyz_i, float(x), float(y), float(r))
        if len(roi) < 30:
            continue  # 点数太少, 特征不可信
        yield roi, PERSON, "%s#f%04d" % (sid, fi)


def iter_none_frames(session_dir, max_frames=None):
    """空场会话： 整帧(裁掉 z<0.05 的地板杂波)作 NOPERSON。name 带帧号。

    每帧就是一整幅场景, 不裁 ROI——noperson 的定义就是「没有裁剪后人形」。
    """
    sid = os.path.basename(session_dir.rstrip("\\/"))
    n = 0
    for xyz_i, fi in load_level_frames(session_dir):
        keep = xyz_i[:, 2] >= 0.05
        frame = xyz_i[keep]
        if len(frame) < 30:
            continue
        yield frame, NOPERSON, "%s#f%04d" % (sid, fi)
        n += 1
        if max_frames is not None and n >= max_frames:
            return

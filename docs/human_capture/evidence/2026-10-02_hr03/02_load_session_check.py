# -*- coding: utf-8 -*-
"""HR-03 R5：产物按 README §2 AI 读法走通（load_session 参考实现的伪代码逐行照抄）。"""
import json, sys
import numpy as np

dst = sys.argv[1] if len(sys.argv) > 1 else \
    r"D:\Code\ldiar\captures\remote\cap_20261002_165321_clip_1989287-1989294"

# README §2 原文（一字不改）
meta = json.load(open(dst + r"\meta.json"))
pts = np.memmap(dst + r"\points.bin", dtype="<f4")
f = meta["frames"][3]  # 抽中间帧

# README 用 stride=4（16B 版本）；板上真实是 stride=7（28B）。
# AI 读法应当按 meta.point_layout.stride_bytes 走，这里两种都跑通。
stride_bytes = meta.get("point_stride_bytes") or \
               meta.get("point_layout", {}).get("stride_bytes", 28)
stride_f32 = stride_bytes // 4

cloud = pts[f["offset_points"]*stride_f32:
            (f["offset_points"]+f["count_points"])*stride_f32].reshape(-1, stride_f32)

boxes = [a for a in meta["human_annotations"]
         if a.get("frame_valid", False) and a.get("frame_seq") == f["seq"]]

print("meta keys:", sorted(meta.keys()))
print("frames n:", len(meta["frames"]))
print("f[3] seq:", f["seq"], " count:", f["count_points"], " offset:", f["offset_points"])
print("cloud shape:", cloud.shape, " dtype:", cloud.dtype)
print("intensity p2/p98:", np.percentile(cloud[:, 3], [2, 98]))
print("boxes (frame_valid):", len(boxes))
print("human_annotations:", meta["human_annotations"])
print("extraction.tool:", meta["extraction"]["tool"])
print("OK")

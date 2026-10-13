# -*- coding: utf-8 -*-
"""render_with_gt_box.py — 把 C1.5 带刻度渲染 + GT 人形框叠加.

用法: python render_with_gt_box.py <sid> <frame_idx> <out_png>
输入: C1.5 gt_labels/<sid>.chunk*.json (top_xy=[cx,cy], conf, activity)
框形: 以 (cx,cy) 为圆心, r_xy=0.5m 的人形簇范围圈 -- 在 top 视图画黄色圆,
      conf=high 亮黄, medium 橙, uncertain 红虚线.
"""
import importlib.util
import io
import json
import math
import os
import sys

import numpy as np

HR_ML = "D:/Code/ldiar/pc_apps/human_ml/render_person_label.py"
C15_WS = "D:/Code/ldiar/docs/human_capture/evidence/2026-10-10_c15_gt_validation/workspace"
SESSION_ROOT = "D:/Code/ldiar/captures/remote"

spec = importlib.util.spec_from_file_location("rpl", HR_ML)
rpl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rpl)
R, T = rpl.R, rpl.T
TOP_X0, TOP_X1 = rpl.TOP_X0, rpl.TOP_X1
TOP_Y0, TOP_Y1 = rpl.TOP_Y0, rpl.TOP_Y1
TOP_W, TOP_H = rpl.TOP_W, rpl.TOP_H

# 从 C1.5 render_axis.py 拿 annotate + 字模
spec2 = importlib.util.spec_from_file_location("rax", os.path.join(C15_WS, "render_axis.py"))
rax = importlib.util.module_from_spec(spec2)
spec2.loader.exec_module(rax)


def gather_gt(sid):
    """按帧号合并所有 chunk*.json (排除 *_verdict) → {frame_idx: frame_dict}"""
    out = {}
    gdir = os.path.join(C15_WS, "gt_labels")
    for fn in sorted(os.listdir(gdir)):
        if not fn.startswith(sid) or not fn.endswith(".json") or "verdict" in fn:
            continue
        d = json.load(io.open(os.path.join(gdir, fn), encoding="utf-8"))
        for k, v in d.get("frames", {}).items():
            out[int(k)] = v
    return out


def draw_circle(img, cx_px, cy_px, r_px, color, dash=False):
    """在 img 上画圆 ( 顶视), 圆心 (cx_px, cy_px) 半径 r_px 像素."""
    H, W = img.shape[0], img.shape[1]
    steps = int(2 * math.pi * max(r_px, 8) * 2)
    for i in range(steps):
        if dash and (i // 4) % 2 == 1:
            continue  # 虚线: 跳过一半
        a = 2 * math.pi * i / steps
        x = int(round(cx_px + r_px * math.cos(a)))
        y = int(round(cy_px + r_px * math.sin(a)))
        if 0 <= y < H and 0 <= x < W:
            img[y, x] = color


def draw_centroid(img, cx_px, cy_px, color):
    """画 5x5 十字."""
    H, W = img.shape[0], img.shape[1]
    for dx in range(-2, 3):
        for dy in range(-2, 3):
            if dx == 0 or dy == 0:
                x, y = cx_px + dx, cy_px + dy
                if 0 <= y < H and 0 <= x < W:
                    img[y, x] = color


def render_with_gt(sid, fi, out_path):
    """先按 render_axis.render 渲一份基础图, 再把 GT 框叠上去."""
    # 1) 基础帧 (复制 render_axis.render 像素逻辑)
    sdir = os.path.join(SESSION_ROOT, sid)
    meta = json.load(io.open(os.path.join(sdir, "meta.json"), encoding="utf-8"))
    raw = np.memmap(os.path.join(sdir, "points.bin"), dtype=np.uint8, mode="r"
                    ).reshape(-1, 28).view(np.float32).reshape(-1, 7)
    f = meta["frames"][fi]
    seg = raw[f["offset_points"]: f["offset_points"] + f["count_points"]]
    xyz = seg[:, :3].astype(np.float64)
    v = np.isfinite(xyz).all(axis=1) & np.any(xyz != 0, axis=1)
    lv = (xyz[v] @ R.T) + T

    img = np.zeros((rpl.PANEL_H, rpl.PANEL_W, 3), dtype=np.uint8)
    z0 = rpl.ground_peak(lv[:, 2])
    z = lv[:, 2] - z0
    sx = TOP_W / (TOP_X1 - TOP_X0)
    sy = TOP_H / (TOP_Y1 - TOP_Y0)
    # 顶视网格
    for xm in range(0, int(TOP_X1) + 1):
        img[0:TOP_H, max(0, int((xm - TOP_X0) * sx)):int((xm - TOP_X0) * sx) + 1] = (34, 34, 34)
    for ym in range(int(TOP_Y0), int(TOP_Y1) + 1):
        py = TOP_H - 1 - int((ym - TOP_Y0) * sy)
        img[max(0, py):py + 1, 0:TOP_W] = (34, 34, 34)
    ox, oy = int((0 - TOP_X0) * sx), TOP_H - 1 - int((0 - TOP_Y0) * sy)
    img[max(0, oy - 2):oy + 3, max(0, ox - 2):ox + 3] = (255, 255, 255)
    order = np.argsort(z)
    pts, zs = lv[order], z[order]
    px = ((pts[:, 0] - TOP_X0) * sx).astype(np.int32)
    py = (TOP_H - 1 - (pts[:, 1] - TOP_Y0) * sy).astype(np.int32)
    ok = (px >= 0) & (px < TOP_W) & (py >= 0) & (py < TOP_H)
    idx = np.nonzero(ok)[0]
    img[py[idx], px[idx]] = [rpl.tint(vv) for vv in zs[idx]]
    # 侧视
    y0 = TOP_H + rpl.PAD
    sh = rpl.SIDE_H / (rpl.SIDE_Z1 - rpl.SIDE_Z0)
    for zm in (0.0, 0.4, 0.8, 1.2, 1.6, 2.0):
        pz = y0 + rpl.SIDE_H - 1 - int((zm - rpl.SIDE_Z0) * sh)
        img[max(y0, pz):pz + 1, 0:rpl.PANEL_W] = (50, 50, 50) if zm == 0 else (30, 30, 30)
    for xm in range(0, int(TOP_X1) + 1):
        gx = int((xm - TOP_X0) * sx)
        img[y0:y0 + rpl.SIDE_H, max(0, gx):gx + 1] = (34, 34, 34)
    px = ((pts[:, 0] - TOP_X0) * sx).astype(np.int32)
    pz = (rpl.SIDE_H - 1 - (zs - rpl.SIDE_Z0) * sh).astype(np.int32) + y0
    ok2 = (px >= 0) & (px < rpl.PANEL_W) & (pz >= y0) & (pz < y0 + rpl.SIDE_H)
    idx2 = np.nonzero(ok2)[0]
    img[pz[idx2], px[idx2]] = [rpl.tint(vv) for vv in zs[idx2]]
    rax.annotate(img)

    # 2) 叠加 GT 框 (仅在 top 视图)
    gt = gather_gt(sid).get(fi)
    if gt and gt.get("present") and gt.get("top_xy"):
        cx, cy = gt["top_xy"]
        cxp = int((cx - TOP_X0) * sx)
        cyp = TOP_H - 1 - int((cy - TOP_Y0) * sy)
        rp_m = 0.5  # 人形簇 0.5m 半径 (GT_SPEC §2 判据 1: 直径<0.6m)
        rp = int(rp_m * sx)
        conf = gt.get("conf", "high")
        act = gt.get("activity", "stand")
        if act == "uncertain":
            color = (255, 80, 80); dash = True     # 红虚线: 不确定
        elif conf == "high":
            color = (255, 255, 0); dash = False    # 黄实线: 高置信
        elif conf == "medium":
            color = (255, 165, 0); dash = False    # 橙实线
        else:
            color = (200, 200, 0); dash = False
        draw_circle(img, cxp, cyp, rp, color, dash=dash)
        draw_centroid(img, cxp, cyp, color)

        # 帧号 + activity 标签 (左上角)
        rax.draw_text(img, TOP_W - 60, 2, str(fi), color=(255, 255, 255), scale=2)
        # activity 简写 (S/W/U)
        abbrev = {"stand": "S", "walk": "W", "uncertain": "?", "empty": "E"}.get(act, act[:1].upper())
        rax.draw_text(img, TOP_W - 60, 24, abbrev, color=color, scale=2)

    rpl.write_png(out_path, img)


if __name__ == "__main__":
    sid, fi = sys.argv[1], int(sys.argv[2])
    out = sys.argv[3] if len(sys.argv) > 3 else None
    if out is None:
        os.makedirs("frames", exist_ok=True)
        out = os.path.join("frames", "%s_f%04d_box.png" % (sid, fi))
    render_with_gt(sid, fi, out)
    print("wrote", out)

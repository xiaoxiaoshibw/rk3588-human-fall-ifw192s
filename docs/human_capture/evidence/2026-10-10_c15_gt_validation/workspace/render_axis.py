# -*- coding: utf-8 -*-
"""render_axis.py — C1.5 坐标轴刻度渲染 (生产零改动, 独立离线渲染器)。

复用 render_person_label.py 的着色/投影, 叠加 3x5 位图数字坐标刻度:
  x 轴 0..6m, y 轴 -2..10m 每米打数字, 使 GT 判读坐标可与生产探针质心 (传感器米) 对齐。
解决: 旧渲染只画网格线无坐标数字, 导致多标注员"数格"给出互斥坐标 (C1.5 GT 质量根因)。
"""
import importlib.util
import io
import json
import os
import sys

import numpy as np

HR_ML = "D:/Code/ldiar/pc_apps/human_ml/render_person_label.py"
SESSION_ROOT = "D:/Code/ldiar/captures/remote"
spec = importlib.util.spec_from_file_location("rpl", HR_ML)
rpl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rpl)
R, T = rpl.R, rpl.T

TOP_X0, TOP_X1 = rpl.TOP_X0, rpl.TOP_X1
TOP_Y0, TOP_Y1 = rpl.TOP_Y0, rpl.TOP_Y1
TOP_W, TOP_H = rpl.TOP_W, rpl.TOP_H

# 3x5 数字字模 (0-9 与 '-')
FONT = {
    "0": ["111", "101", "101", "101", "111"],
    "1": ["010", "110", "010", "010", "111"],
    "2": ["111", "001", "111", "100", "111"],
    "3": ["111", "001", "111", "001", "111"],
    "4": ["101", "101", "111", "001", "001"],
    "5": ["111", "100", "111", "001", "111"],
    "6": ["111", "100", "111", "101", "111"],
    "7": ["111", "001", "001", "010", "010"],
    "8": ["111", "101", "111", "101", "111"],
    "9": ["111", "101", "111", "001", "111"],
    "-": ["000", "000", "111", "000", "000"],
}


def draw_text(img, x, y, s, color=(255, 255, 0), scale=2):
    cx = x
    for ch in s:
        glyph = FONT.get(ch)
        if glyph:
            for gy, row in enumerate(glyph):
                for gx, bit in enumerate(row):
                    if bit == "1":
                        for dy in range(scale):
                            for dx in range(scale):
                                yy, xx = y + gy * scale + dy, cx + gx * scale + dx
                                if 0 <= yy < img.shape[0] and 0 <= xx < img.shape[1]:
                                    img[yy, xx] = color
        cx += 4 * scale


def annotate(img):
    sx = TOP_W / (TOP_X1 - TOP_X0)
    sy = TOP_H / (TOP_Y1 - TOP_Y0)
    # x 轴数字 (顶边)
    for xm in range(int(TOP_X0), int(TOP_X1) + 1):
        px = int((xm - TOP_X0) * sx)
        draw_text(img, max(0, px - 4), 2, str(xm))
    # y 轴数字 (左边), 顶视 y 向上
    for ym in range(int(TOP_Y0), int(TOP_Y1) + 1):
        py = TOP_H - 1 - int((ym - TOP_Y0) * sy)
        draw_text(img, 2, max(0, py - 6), str(ym))


def render(sid, frame_idx, out_path):
    sdir = os.path.join(SESSION_ROOT, sid)
    meta = json.load(io.open(os.path.join(sdir, "meta.json"), encoding="utf-8"))
    raw = np.memmap(os.path.join(sdir, "points.bin"), dtype=np.uint8, mode="r"
                    ).reshape(-1, 28).view(np.float32).reshape(-1, 7)
    f = meta["frames"][frame_idx]
    seg = raw[f["offset_points"]: f["offset_points"] + f["count_points"]]
    xyz = seg[:, :3].astype(np.float64)
    v = np.isfinite(xyz).all(axis=1) & np.any(xyz != 0, axis=1)
    lv = (xyz[v] @ R.T) + T
    # 复制 rpl.render_frame 的像素逻辑, 但先落点再 annotate
    img = np.zeros((rpl.PANEL_H, rpl.PANEL_W, 3), dtype=np.uint8)
    z0 = rpl.ground_peak(lv[:, 2])
    z = lv[:, 2] - z0
    sx = TOP_W / (TOP_X1 - TOP_X0); sy = TOP_H / (TOP_Y1 - TOP_Y0)
    for xm in range(0, int(TOP_X1) + 1):
        img[0:TOP_H, max(0, int((xm - TOP_X0) * sx)):int((xm - TOP_X0) * sx) + 1] = (34, 34, 34)
    for ym in range(int(TOP_Y0), int(TOP_Y1) + 1):
        py = TOP_H - 1 - int((ym - TOP_Y0) * sy)
        img[max(0, py):py + 1, 0:TOP_W] = (34, 34, 34)
    ox, oy = int((0 - TOP_X0) * sx), TOP_H - 1 - int((0 - TOP_Y0) * sy)
    img[max(0, oy - 2):oy + 3, max(0, ox - 2):ox + 3] = (255, 255, 255)
    order = np.argsort(z); pts, zs = lv[order], z[order]
    px = ((pts[:, 0] - TOP_X0) * sx).astype(np.int32)
    py = (TOP_H - 1 - (pts[:, 1] - TOP_Y0) * sy).astype(np.int32)
    ok = (px >= 0) & (px < TOP_W) & (py >= 0) & (py < TOP_H); idx = np.nonzero(ok)[0]
    img[py[idx], px[idx]] = [rpl.tint(vv) for vv in zs[idx]]
    y0 = TOP_H + rpl.PAD; sh = rpl.SIDE_H / (rpl.SIDE_Z1 - rpl.SIDE_Z0)
    for zm in (0.0, 0.4, 0.8, 1.2, 1.6, 2.0):
        pz = y0 + rpl.SIDE_H - 1 - int((zm - rpl.SIDE_Z0) * sh)
        img[max(y0, pz):pz + 1, 0:rpl.PANEL_W] = (50, 50, 50) if zm == 0 else (30, 30, 30)
    for xm in range(0, int(TOP_X1) + 1):
        gx = int((xm - TOP_X0) * sx)
        img[y0:y0 + rpl.SIDE_H, max(0, gx):gx + 1] = (34, 34, 34)
    px = ((pts[:, 0] - TOP_X0) * sx).astype(np.int32)
    pz = (rpl.SIDE_H - 1 - (zs - rpl.SIDE_Z0) * sh).astype(np.int32) + y0
    ok2 = (px >= 0) & (px < rpl.PANEL_W) & (pz >= y0) & (pz < y0 + rpl.SIDE_H); idx2 = np.nonzero(ok2)[0]
    img[pz[idx2], px[idx2]] = [rpl.tint(vv) for vv in zs[idx2]]
    annotate(img)
    rpl.write_png(out_path, img)


if __name__ == "__main__":
    # smoke: 重渲一张关键争议帧验证可读
    out_dir = sys.argv[1] if len(sys.argv) > 1 else "renders_axis"
    os.makedirs(out_dir, exist_ok=True)
    for sid, fi in [("cap_20261007_154007", 24), ("cap_20261007_143945", 40), ("cap_20261007_143945", 10)]:
        p = os.path.join(out_dir, "%s_f%04d.png" % (sid, fi))
        render(sid, fi, p)
        print("wrote", p)

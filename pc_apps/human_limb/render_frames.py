# -*- coding: utf-8 -*-
"""render_frames.py — 把会话逐帧渲染成「顶视 + 侧视」拼图 PNG，供 AI 逐帧判读。

输出到 <session>/film/m_fAAA_fBBB.png（每张 4 帧并排）。
坐标约定（AI 读图前必读）：
  - 顶视（每帧上半部）: x 向右 [0..6m]，y 向上 [-3..+3m]，雷达在原点（白点）
  - 侧视（每帧下半部）: x 向右 [0..6m]，z 向上 [-0.2..2.2m]，横线为 z=0.4/0.8/1.2/1.6/2.0 带边界
  - 颜色按离地高度 z0 分段： z<0.15 暗蓝（地）、0.15-0.6 青、0.6-1.2 绿、1.2-1.8 黄、>1.8 红
"""
import json
import os
import struct
import sys
import zlib

import numpy as np

TOP_X0, TOP_X1 = 0.0, 6.0
TOP_Y0, TOP_Y1 = -3.0, 3.0
TOP_W = 400                      # px
TOP_H = 400
SIDE_Z0, SIDE_Z1 = -0.2, 2.2
SIDE_H = 140
PAD = 8
PANEL_W = TOP_W
PANEL_H = TOP_H + PAD + SIDE_H   # 548
SEP = 2
PER_ROW = 4


def write_png(path, arr):
    H, W = arr.shape[:2]
    raw = b"".join(b"\x00" + arr[i].tobytes() for i in range(H))
    def chunk(typ, data):
        c = struct.pack(">I", len(data)) + typ + data
        return c + struct.pack(">I", zlib.crc32(typ + data) & 0xffffffff)
    ihdr = struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0)
    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
           + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))
    with open(path, "wb") as fh:
        fh.write(png)


def tint(z):
    """离地高度 → RGB。"""
    if z < 0.15:
        return (34, 54, 84)
    if z < 0.60:
        return (60, 190, 225)
    if z < 1.20:
        return (80, 220, 120)
    if z < 1.80:
        return (235, 220, 75)
    return (240, 95, 70)


def render_panel(xyz, z0):
    """单帧 → (PANEL_H, PANEL_W, 3) uint8 顶视+侧视"""
    img = np.zeros((PANEL_H, PANEL_W, 3), dtype=np.uint8)

    # ---- 顶视 ----
    sx = PANEL_W / (TOP_X1 - TOP_X0)
    sy = TOP_H / (TOP_Y1 - TOP_Y0)
    # 网格： 每 1m
    for xm in range(int(TOP_X0), int(TOP_X1) + 1):
        px = int((xm - TOP_X0) * sx)
        img[0:TOP_H, max(0, px - 0):px + 1] = (28, 28, 28)
    for ym in range(int(TOP_Y0), int(TOP_Y1) + 1):
        py = TOP_H - 1 - int((ym - TOP_Y0) * sy)
        img[max(0, py):py + 1, 0:TOP_W] = (28, 28, 28)
    # 雷达原点标记 (白色 5px 方块）
    ox = int((0 - TOP_X0) * sx)
    oy = TOP_H - 1 - int((0 - TOP_Y0) * sy)
    img[max(0, oy - 2):oy + 3, max(0, ox - 2):ox + 3] = (255, 255, 255)

    # 点： 先低 z 后高 z（高 z 覆盖在上层）
    z = xyz[:, 2] - z0
    order = np.argsort(z)
    pts = xyz[order][:: 2]           # 抽稀一半
    zs = z[order][:: 2]
    px = ((pts[:, 0] - TOP_X0) * sx).astype(np.int32)
    py = (TOP_H - 1 - (pts[:, 1] - TOP_Y0) * sy).astype(np.int32)
    ok = (px >= 0) & (px < TOP_W) & (py >= 0) & (py < TOP_H)
    for i in np.nonzero(ok)[0]:
        img[py[i], px[i]] = tint(zs[i])

    # ---- 侧视 ----
    y0 = TOP_H + PAD
    sw = PANEL_W / (TOP_X1 - TOP_X0)
    sh = SIDE_H / (SIDE_Z1 - SIDE_Z0)
    for zm in (0.0, 0.4, 0.8, 1.2, 1.6, 2.0):
        pz = y0 + SIDE_H - 1 - int((zm - SIDE_Z0) * sh)
        img[max(y0, pz):pz + 1, 0:PANEL_W] = (45, 45, 45) if zm == 0 else (30, 30, 30)
    for xm in range(int(TOP_X0), int(TOP_X1) + 1):
        px = int((xm - TOP_X0) * sw)
        img[y0:y0 + SIDE_H, max(0, px):px + 1] = (28, 28, 28)

    pts = xyz[:: 2]
    zs = z[:: 2]
    px = ((pts[:, 0] - TOP_X0) * sw).astype(np.int32)
    pz = (SIDE_H - 1 - (zs - SIDE_Z0) * sh).astype(np.int32) + y0
    ok = (px >= 0) & (px < PANEL_W) & (pz >= y0) & (pz < y0 + SIDE_H)
    for i in np.nonzero(ok)[0]:
        img[pz[i], px[i]] = tint(zs[i])
    return img


def ground_z0(xyz):
    """复用 limb_lib 思路： 强制平地 —— z 直方图最高峰。"""
    zs = xyz[(xyz[:, 2] > -1.5) & (xyz[:, 2] < 1.5), 2]
    if len(zs) < 300:
        return 0.0
    counts, edges = np.histogram(zs, bins=100, range=(-1.5, 1.5))
    smooth = np.convolve(counts, np.ones(3) / 3, mode="same")
    i = int(np.argmax(smooth))
    return float(0.5 * (edges[i] + edges[i + 1]))


def main(session_dir):
    meta = json.load(open(os.path.join(session_dir, "meta.json"), encoding="utf-8"))
    raw = np.memmap(os.path.join(session_dir, "points.bin"),
                     dtype=np.uint8, mode="r").reshape(-1, 28).view(np.float32).reshape(-1, 7)
    film = os.path.join(session_dir, "film")
    os.makedirs(film, exist_ok=True)

    panels = []
    for fi, f in enumerate(meta["frames"]):
        xyz = raw[f["offset_points"]:f["offset_points"] + f["count_points"], :3].astype(np.float32)
        panels.append(render_panel(xyz, ground_z0(xyz)))

    n = len(panels)
    for start in range(0, n, PER_ROW):
        grp = panels[start:start + PER_ROW]
        while len(grp) < PER_ROW:
            grp.append(np.zeros_like(panels[0]))
        W = PER_ROW * PANEL_W + (PER_ROW - 1) * SEP
        sheet = np.full((PANEL_H, W, 3), 12, dtype=np.uint8)
        for k, p in enumerate(grp):
            c0 = k * (PANEL_W + SEP)
            sheet[:, c0:c0 + PANEL_W] = p
        name = "m_f%03d_f%03d.png" % (start, min(start + PER_ROW - 1, n - 1))
        write_png(os.path.join(film, name), sheet)
    print("wrote %d montages → %s" % ((n + PER_ROW - 1) // PER_ROW, film))


if __name__ == "__main__":
    main(sys.argv[1])

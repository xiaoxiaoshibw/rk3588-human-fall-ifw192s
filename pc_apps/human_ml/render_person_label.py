# -*- coding: utf-8 -*-
"""render_person_label.py — 每帧顶视+侧视拼图，供 AI 判读人体 ROI (HR-09 person/noperson 标签源)。

复用 render_frames.py 的纯 python PNG + z 直方图地面思路；改造点：
  - 坐标系固定为 leveled (R/t 与空场模板 632eff1e tls 一致)，z=0 即地面
  - 顶/侧视 y 量程放宽到 [-2..10.5]（本房间长轴 ~10m）
  - 顶视画 1m 网格 + 原点雷达白点；侧视画 z 分带
  - 抽稀每帧全部点不砍半（人小目标远端点数少，砍半会丢证据）

输出 <session>/film_person/f%04d.png （单帧一张，便于 AI 逐帧读）。
"""
import json
import os
import struct
import sys
import zlib

import numpy as np

# leveled 变换： 空场模板 job 632eff1e189945d8915eb5af7a9ddcf9 tls/transform.json
R = np.array([[0.893544, 0.0, 0.448975],
              [-0.014337, 0.99949, 0.028533],
              [-0.448746, -0.031932, 0.893089]])
T = np.array([0.0, 0.0, 1.380286])

TOP_X0, TOP_X1 = 0.0, 6.0       # 雷达x正前
TOP_Y0, TOP_Y1 = -2.0, 10.5     # 房间 y 轴长 ~10m
SIDE_Z0, SIDE_Z1 = -0.4, 2.4
TOP_W = 460
TOP_H = 460
SIDE_H = 120
PAD = 6
PANEL_W = TOP_W
PANEL_H = TOP_H + PAD + SIDE_H


def write_png(path, arr):
    H, W = arr.shape[:2]
    raw = b"".join(b"\x00" + arr[i].tobytes() for i in range(H))

    def chunk(typ, data):
        c = struct.pack(">I", len(data)) + typ + data
        return c + struct.pack(">I", zlib.crc32(typ + data) & 0xffffffff)

    png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0))
           + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))
    with open(path, "wb") as fh:
        fh.write(png)


def tint(z):
    if z < 0.15:
        return (40, 60, 92)
    if z < 0.60:
        return (66, 200, 235)
    if z < 1.20:
        return (90, 228, 128)
    if z < 1.80:
        return (240, 224, 84)
    return (245, 104, 78)


def ground_peak(zl):
    zin = zl[(zl > -1.5) & (zl < 1.5)]
    if len(zin) < 200:
        return 0.0
    counts, edges = np.histogram(zin, bins=120, range=(-1.5, 1.5))
    i = int(np.argmax(np.convolve(counts, np.ones(3) / 3, mode="same")))
    return float(0.5 * (edges[i] + edges[i + 1]))


def render_frame(xyz_lv, out_path):
    img = np.zeros((PANEL_H, PANEL_W, 3), dtype=np.uint8)
    z0 = ground_peak(xyz_lv[:, 2])
    z = xyz_lv[:, 2] - z0

    sx = TOP_W / (TOP_X1 - TOP_X0)
    sy = TOP_H / (TOP_Y1 - TOP_Y0)
    # 网格 + 原点
    for xm in range(0, int(TOP_X1) + 1):
        px = int((xm - TOP_X0) * sx)
        img[0:TOP_H, max(0, px):px + 1] = (34, 34, 34)
    for ym in range(int(TOP_Y0), int(TOP_Y1) + 1):
        py = TOP_H - 1 - int((ym - TOP_Y0) * sy)
        img[max(0, py):py + 1, 0:TOP_W] = (34, 34, 34)
    ox, oy = int((0 - TOP_X0) * sx), TOP_H - 1 - int((0 - TOP_Y0) * sy)
    img[max(0, oy - 2):oy + 3, max(0, ox - 2):ox + 3] = (255, 255, 255)

    order = np.argsort(z)
    pts, zs = xyz_lv[order], z[order]
    px = ((pts[:, 0] - TOP_X0) * sx).astype(np.int32)
    py = (TOP_H - 1 - (pts[:, 1] - TOP_Y0) * sy).astype(np.int32)
    ok = (px >= 0) & (px < TOP_W) & (py >= 0) & (py < TOP_H)
    idx = np.nonzero(ok)[0]
    img[py[idx], px[idx]] = [tint(v) for v in zs[idx]]

    # 侧视
    y0 = TOP_H + PAD
    sh = SIDE_H / (SIDE_Z1 - SIDE_Z0)
    for zm in (0.0, 0.4, 0.8, 1.2, 1.6, 2.0):
        pz = y0 + SIDE_H - 1 - int((zm - SIDE_Z0) * sh)
        img[max(y0, pz):pz + 1, 0:PANEL_W] = (50, 50, 50) if zm == 0 else (30, 30, 30)
    for xm in range(0, int(TOP_X1) + 1):
        gx = int((xm - TOP_X0) * sx)
        img[y0:y0 + SIDE_H, max(0, gx):gx + 1] = (34, 34, 34)
    px = ((pts[:, 0] - TOP_X0) * sx).astype(np.int32)
    pz = (SIDE_H - 1 - (zs - SIDE_Z0) * sh).astype(np.int32) + y0
    ok2 = (px >= 0) & (px < PANEL_W) & (pz >= y0) & (pz < y0 + SIDE_H)
    idx2 = np.nonzero(ok2)[0]
    img[pz[idx2], px[idx2]] = [tint(v) for v in zs[idx2]]

    write_png(out_path, img)


def main(session_dir):
    meta = json.load(open(os.path.join(session_dir, "meta.json"), encoding="utf-8"))
    raw = np.memmap(os.path.join(session_dir, "points.bin"), dtype=np.uint8, mode="r"
                    ).reshape(-1, 28).view(np.float32).reshape(-1, 7)
    out = os.path.join(session_dir, "film_person")
    os.makedirs(out, exist_ok=True)
    for fi, f in enumerate(meta["frames"]):
        seg = raw[f["offset_points"]: f["offset_points"] + f["count_points"]]
        xyz = seg[:, :3].astype(np.float64)
        v = np.isfinite(xyz).all(axis=1) & np.any(xyz != 0, axis=1)
        lv = (xyz[v] @ R.T) + T
        render_frame(lv, os.path.join(out, "f%04d.png" % fi))
    print("wrote %d panels -> %s" % (len(meta["frames"]), out))


if __name__ == "__main__":
    main(sys.argv[1])

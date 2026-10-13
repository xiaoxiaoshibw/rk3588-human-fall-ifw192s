# -*- coding: utf-8 -*-
"""结构证据可行性探针：垂直剖面 + 头/颈/躯干/腿特征，人 vs WD01 vs 箱子堆。
全部用现成 leveled 数据；只读，仅打印。"""
import json
from pathlib import Path

import numpy as np

LV = Path(r"D:\Code\ldiar\captures\leveled")
J_215540 = "21666bec7e7b44b2bdbbaa790bf4501b"
J_215607 = "2ed2cf6a4d2342ebb87f4e7fa68fdf3c"
J_223757 = "015df3ff4e9743e38ea2236ea7da2d74"


def load(job):
    d = LV / job / "tls"
    meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
    raw = np.memmap(d / "points.bin", dtype="u1", mode="r")
    xyz = np.ndarray((meta["total_points"], 3), dtype="<f4", buffer=raw, strides=(28, 4))
    return np.concatenate([xyz[f["offset_points"]:f["offset_points"] + f["count_points"]] for f in meta["frames"]])


def kmeans1d(v, iters=25):
    a, b = np.percentile(v, 25), np.percentile(v, 75)
    for _ in range(iters):
        la = np.abs(v - a) < np.abs(v - b)
        if la.sum() == 0 or (~la).sum() == 0:
            break
        a, b = v[la].mean(), v[~la].mean()
    return abs(a - b), min(la.mean(), 1 - la.mean())


def profile(name, p):
    zmax = p[:, 2].max()
    print(f"== {name}: n={len(p)}  zmax={zmax:.2f}  zmin={p[:,2].min():.2f}")
    for lo in np.arange(0.0, 2.0, 0.1):
        m = (p[:, 2] >= lo) & (p[:, 2] < lo + 0.1)
        if m.sum() < 15:
            continue
        q = p[m]
        print(f"   z {lo:.1f}-{lo+0.1:.1f}: n={m.sum():6d}  sx={q[:,0].std():.3f} sy={q[:,1].std():.3f}  c=({q[:,0].mean():5.2f},{q[:,1].mean():5.2f})")
    def band(zl, zh):
        m = (p[:, 2] >= zl) & (p[:, 2] < zh)
        return p[m] if m.sum() >= 15 else None
    head = band(max(0, zmax - 0.25), zmax + 0.01)
    neck = band(max(0, zmax - 0.50), zmax - 0.25)
    torso = band(0.80, 1.40)
    legs = band(0.15, 0.60)
    fmt = lambda q: "—" if q is None else f"n={len(q)} spread=({q[:,0].std():.3f},{q[:,1].std():.3f})"
    print(f"   head(顶0.25m): {fmt(head)}")
    print(f"   neck(下0.25m): {fmt(neck)}")
    print(f"   torso(0.8-1.4): {fmt(torso)}")
    print(f"   legs(0.15-0.6): {fmt(legs)}")
    if head is not None and neck is not None:
        hw = max(head[:, 0].std(), head[:, 1].std())
        nw = min(neck[:, 0].std(), neck[:, 1].std())
        print(f"   neck/head width ratio = {nw/hw:.2f}（人应<1：颈缩；平坦柜顶≈1+）")
    if legs is not None and len(legs) > 50:
        xy = legs[:, :2] - legs[:, :2].mean(0)
        w, v = np.linalg.eigh(np.cov(xy.T))
        proj = xy @ v[:, -1]
        a, b = np.percentile(proj, 25), np.percentile(proj, 75)
        for _ in range(25):
            la = np.abs(proj - a) < np.abs(proj - b)
            if la.sum() == 0 or (~la).sum() == 0:
                break
            a, b = proj[la].mean(), proj[~la].mean()
        d = abs(a - b); bal = min(la.mean(), 1 - la.mean())
        cw = (proj[la].std() + proj[~la].std()) / 2
        print(f"   legs 双柱: 分离 d={d:.3f}m  均衡度={bal:.2f}  列内σ={cw:.3f}m（人=细柱；板/箱=厚）")
    # 剖面 cv（0.2-1.2m 的 sy 序列）
    sv = []
    for lo in np.arange(0.2, 1.2, 0.1):
        m = (p[:, 2] >= lo) & (p[:, 2] < lo + 0.1)
        if m.sum() >= 15:
            sv.append(p[m][:, 1].std())
    if len(sv) >= 5:
        sv = np.array(sv)
        print(f"   sy 剖面 cv(0.2-1.2) = {sv.std()/sv.mean():.2f}（人=渐变；均匀板≈0）")
    if head is not None:
        hc = head[:, :2].mean(0)
        hi = p[(p[:, 2] > zmax - 0.45) & (p[:, 2] < zmax + 0.01)]
        off = np.hypot(hi[:, 0] - hc[0], hi[:, 1] - hc[1])
        print(f"   顶部区横向偏置 p90={np.percentile(off,90):.2f}m（举手臂→大偏置）")


pts540 = load(J_215540)
pts607 = load(J_215607)
pts757 = load(J_223757)

person = pts540[(np.abs(pts540[:, 0] - 2.10) < 0.55) & (np.abs(pts540[:, 1] + 0.57) < 0.55) & (pts540[:, 2] > 0.05) & (pts540[:, 2] < 2.0)]
armup = pts607[(np.abs(pts607[:, 0] - 2.13) < 0.55) & (np.abs(pts607[:, 1] + 0.50) < 0.55) & (pts607[:, 2] > 0.05) & (pts607[:, 2] < 2.1)]
wd01 = pts757[(np.abs(pts757[:, 0] - 3.50) < 0.55) & (np.abs(pts757[:, 1] + 0.76) < 0.55) & (pts757[:, 2] > 0.05) & (pts757[:, 2] < 2.0)]
crates = pts540[(pts540[:, 0] > 2.35) & (pts540[:, 0] < 3.30) & (pts540[:, 1] > -1.25) & (pts540[:, 1] < -0.50) & (pts540[:, 2] > 0.05) & (pts540[:, 2] < 1.6)]

profile("人(215540, 站)", person)
profile("人(215607, 举手臂)", armup)
profile("WD01(223757, 1.74m 家具)", wd01)
profile("箱子堆(215540)", crates)

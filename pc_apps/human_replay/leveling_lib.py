"""P03 R1 — 算法自动找地面域（detect_ground_domain）。纯函数，stdlib+NumPy。

不复制 leveling.py/leveling_estimators：只做「从点云自动产出 4 个互不重叠 ROI」
一件事，然后由既有 run_job/freeze_domain/compare 走 GLW01 同一管线。
失败显式（ground_auto_candidate_invalid / ground_auto_regions_invalid），
不静默回落、不裁数据、不降阈。
"""
import math

import numpy as np

from leveling_estimators import ESTIMATORS
from leveling_quality import rotation


def _grid_ranges(points, cell=1.0, min_count=30, top_k=4):
    """对地内点按 XY 1m 网格分箱，取点数 top_k 个互不重叠的 bbox。
    返回 [(xl, xh, yl, yh, count), ...]（保持低开销直方图，凸包不做）。"""
    if not len(points):
        return []
    xy = points[:, :2]
    lo = np.floor(xy.min(axis=0)).astype(int)
    hi = np.ceil(xy.max(axis=0)).astype(int)
    span = hi - lo
    if span[0] <= 0 or span[1] <= 0:
        return []
    hist, _, _ = np.histogram2d(xy[:, 0], xy[:, 1], bins=(span[0], span[1]),
                                range=[[lo[0], hi[0]], [lo[1], hi[1]]])
    flat = hist.ravel()
    order = np.argsort(flat)[::-1]
    cells = []
    for idx in order:
        if len(cells) >= top_k or flat[idx] < min_count:
            break
        i, j = divmod(idx, span[1])
        xl, xh = lo[0] + i, lo[0] + i + 1
        yl, yh = lo[1] + j, lo[1] + j + 1
        # 1m 格还能相贴：相邻格若 XY 都有交集会与 leveling 的"区域不重叠"冲突；
        # 只保留与已选格不相交的格（简单贪心，无 scipy.ndimage）。
        ok = True
        for c in cells:
            if min(xh, c[1]) > max(xl, c[0]) and min(yh, c[3]) > max(yl, c[2]):
                ok = False
                break
        if ok:
            cells.append((float(xl), float(xh), float(yl), float(yh), int(flat[idx])))
    return cells


def detect_ground_domain(points, nominal_pitch_deg, nominal_roll_deg, anchor):
    """有限点集 → 4 个互不重叠 ROI（display 系 XY）。

    points: float64 (N,3) 源点（已 finite/nonzero）。
    anchor: 名义显示系 z 轴（3,），用来强制平面法向朝上传感器一侧。
    nominal_pitch/roll: 仅用于把点转到 display 系切 ROI；门不依赖它。

    返回 {'regions': [[xl,xh,yl,yh]...4], 'candidate': {...}}；
    失败抛 ValueError('ground_auto_*: ...')，不返回部分结果。
    """
    points = np.asarray(points, dtype=np.float64)
    if points.ndim != 2 or points.shape[1] != 3 or not len(points):
        raise ValueError("ground_auto_candidate_invalid: 空域")
    anchor = np.asarray(anchor, dtype=np.float64)
    if anchor.shape != (3,) or not np.isfinite(anchor).all():
        raise ValueError("ground_auto_candidate_invalid: 方向锚点非法")
    anchor = anchor / np.linalg.norm(anchor)

    # 复用 GLW01 raw RANSAC（seed20261001/861/0.05m）。同家族、不改迭代。
    normal, offset = ESTIMATORS["ransac"](points)
    norm = float(np.linalg.norm(normal))
    normal, offset = normal / norm, offset / norm
    alignment = float(normal @ anchor)
    if abs(alignment) < .1:
        raise ValueError("ground_auto_candidate_invalid: 方向锚点歧义")
    if alignment < 0:
        normal, offset = -normal, -offset
    if normal[2] < .85:
        raise ValueError("ground_auto_candidate_invalid: 主面法向不朝上 (n_z=%.4f)" % normal[2])
    if not (.8 <= offset <= 1.8):
        raise ValueError("ground_auto_candidate_invalid: 平面偏移超出门范围 (d=%.4f)" % offset)
    residuals = np.einsum("ij,j->i", points, normal) + offset
    support = float(np.mean(np.abs(residuals) <= .08))
    if support < .3:
        raise ValueError("ground_auto_candidate_invalid: 主面支持率过低 (%.4f)" % support)
    in_band = points[np.abs(residuals) <= .08]

    pitch = math.degrees(math.atan2(-normal[0], normal[2]))
    roll = math.degrees(math.asin(float(np.clip(normal[1], -1, 1))))
    # ROI 必须在名义 display 系切：freeze_domain 用同一名义 R 解释 regions（GL-W01 契约）。
    # 用估计 R 会与下游错位（复审 DEFECT-1 根因修复）。
    display = in_band @ rotation(nominal_pitch_deg, nominal_roll_deg).T

    cells = _grid_ranges(display, cell=1.0, min_count=30, top_k=4)
    if len(cells) < 4:
        raise ValueError("ground_auto_regions_invalid: 连通域不足 4 个 (%d)" % len(cells))
    candidate = {"normal_source": normal.tolist(), "offset_source_m": offset,
                 "pitch_deg": pitch, "roll_deg": roll, "support_ratio": support,
                 "points_in_band": len(in_band),
                 "basis": "auto RANSAC861/seed20261001/.08 support=%.4f" % support}
    return {"regions": [[c[0], c[1], c[2], c[3]] for c in cells], "candidate": candidate}

# -*- coding: utf-8 -*-
"""_harness_lib.py — CLUSTER-ADAPTIVE-SPIKE-R1 共享核心 (B1 find_clusters 复现).
任务文档: docs/human_capture/evidence/2026-10-10_spike_cluster_r1/ (本轮产物)

不可变核心原则:
  1) 完全复现 pc_apps/human_replay/detect_overlay.js 的 find_clusters/grid_key 行为;
     包括其 "gy % 4096" 在负数 gy 下的 JS 语义 (向零取余). Python 需用 math.trunc 模拟,
     否则两个 key universe 不等价.
  2) 所有变体 (A/B/C) 只在"邻域扩张规则"上分支; 其它 (grid cell size, min_pts, top_k)
     与 A 对齐, 保证单变量对照.
  3) 每帧耗时/候选点数/簇数全记录, 供性能分层.

v1 (2026-10-10 冻结):
  - GRID_CELL_M = 0.05 (与 B1 BG_CELL, 与 bg_envelope 分辨率一致)
  - KEY_MOD     = 4096 (grid_key 模数)
  - NEIGH_A     = 8 邻 (官方旗舰店 B1: dx,dy ∈ {-1,0,1}² ∖ {(0,0)})
  - MIN_POINTS  = 30
  - TOP_K       = 4
"""
import json
import math
import time

GRID_CELL_M = 0.05
KEY_MOD = 4096
INV = 1.0 / GRID_CELL_M


def _js_mod(a, b):
    """JavaScript % 在负数时是向零取余; Python 是向下. 不统一 -> 键空间错位会嫁祸给计数."""
    return a - math.trunc(a / b) * b


def grid_key(x, y):
    """复现 detect_overlay.js grid_key: floor(x*20)*4096 + js_mod(floor(y*20), 4096).
    注意与 dump_bg_envelope.py (纯 gx*4096+gy) 在 gy<0 时错位——忠实复现 JS 侧, 不修复 P2."""
    gx = math.floor(x * INV)
    gy = math.floor(y * INV)
    return gx * KEY_MOD + _js_mod(gy, KEY_MOD)


def grid_xy(key):
    """key -> (gx, gy_mod). gy_mod 已 %4096, 不能反推真实米坐标; 仅用于邻域展开."""
    gy = _js_mod(key, KEY_MOD)
    gx = (key - gy) // KEY_MOD
    return gx, gy


def _bfs_expand(grid, seed, allow_fn):
    """8 邻洪水 (A 邻域) 或 allow_fn(key_cur, key_nei) 限定扩张 (B/C).
    返回该连通分量的成员点索引集. allow_fn=None 等价于 8 邻固定."""
    seen = {seed}
    stack = [seed]
    members = []
    while stack:
        cur = stack.pop()
        members.extend(grid[cur])
        cgx, cgy = grid_xy(cur)
        rmax = 1 if allow_fn is None else allow_fn(cur, None, True)
        for dx in range(-rmax, rmax + 1):
            for dy in range(-rmax, rmax + 1):
                if dx == 0 and dy == 0:
                    continue
                nk = (cgx + dx) * KEY_MOD + _js_mod(cgy + dy, KEY_MOD)
                if nk in grid and nk not in seen:
                    if allow_fn is None or allow_fn(cur, nk, False):
                        seen.add(nk)
                        stack.append(nk)
    return members, seen


def find_clusters_A(xs, ys, hot_idx, min_points=30, top_k=4):
    """忠实复现 B1 现状: 5cm 网格 8 邻洪水 + min 30 点 + top4."""
    t0 = time.perf_counter()
    grid = {}
    for pt in hot_idx:
        grid.setdefault(grid_key(xs[pt], ys[pt]), []).append(pt)
    seen = set()
    comps = []
    for seed in grid:
        if seed in seen:
            continue
        members, comp_seen = _bfs_expand(grid, seed, None)
        seen |= comp_seen
        comps.append(members)
    dt = time.perf_counter() - t0
    comps = [m for m in comps if len(m) >= min_points]
    comps.sort(key=len, reverse=True)
    stats = dict(n_hot=len(hot_idx), n_cells=len(grid), n_comps=len(comps),
                 ms_cluster=dt * 1000.0)
    return comps[:top_k], stats


def find_clusters_BC(xs, ys, zs, hot_idx, eps_fn, min_points=30, top_k=4,
                     bridge_policy=None, wall_bands=None, symmetric=True):
    """B/C 距离自适应 (eps_fn(r_m)) 网格洪水.

    关键实现选择 (调研后选定):
      * 所有 cell 预先算 cell_r (均值距离) 和 cell_z (均值 z);
      * eps(nei_r) 决定从 cur 出发能扩到几个 Chebyshev 半径 (cell);
      * symmetric=True 时同时要求 eps(cur_r) 门也过 — 保守并簇, 避免高 eps 单侧链式;
      * bridge_policy="height_band" 时, cur/nei 的 cell_z 分带不同则不 union (C 的剪枝);
      * neiborbound cell 探查次数 = (2*ceil(eps/CELL)+1)^2 - 1 每 cell, 是代价热点.
    """
    t0 = time.perf_counter()
    grid = {}
    for pt in hot_idx:
        grid.setdefault(grid_key(xs[pt], ys[pt]), []).append(pt)
    cell_r = {}
    cell_z = {}
    for key, members in grid.items():
        sr = 0.0
        sz = 0.0
        for pt in members:
            sr += math.sqrt(xs[pt] * xs[pt] + ys[pt] * ys[pt])
            sz += zs[pt]
        n = len(members)
        cell_r[key] = sr / n
        cell_z[key] = sz / n

    def band_of(z):
        if not wall_bands:
            return 0
        for i, (lo, hi) in enumerate(wall_bands):
            if lo <= z < hi:
                return i + 1
        return 0

    def eps_m(key):
        return eps_fn(cell_r[key])

    def band_of_key(key):
        return band_of(cell_z.get(key, -999.0))

    def allow_fn(cur, nei, is_scope_query):
        """is_scope_query=True: 返回 cur 的 Chebyshev 探查半径 (cell 数).
        is_scope_query=False: 判定 cur→nei 是否可 union."""
        if is_scope_query:
            return math.ceil(eps_m(cur) / GRID_CELL_M)
        # 距离门: min(eps_cur, eps_nei) 是对称保守门
        if symmetric:
            eps_ref = min(eps_m(cur), eps_m(nei))
        else:
            eps_ref = eps_m(cur)
        cgx_c, cgy_c = grid_xy(cur)
        cgx_n, cgy_n = grid_xy(nei)
        d_cell = max(abs(cgx_n - cgx_c), abs(cgy_n - cgy_c))
        if d_cell * GRID_CELL_M > eps_ref + GRID_CELL_M:     # +1 cell 中心距半宽容忍
            return False
        if bridge_policy == "height_band":
            b_cur = band_of_key(cur)
            b_nei = band_of_key(nei)
            if b_cur > 0 and b_nei > 0 and b_cur != b_nei:
                return False
        return True

    seen = set()
    comps = []
    for seed in grid:
        if seed in seen:
            continue
        members, comp_seen = _bfs_expand(grid, seed, allow_fn)
        seen |= comp_seen
        comps.append(members)
    dt = time.perf_counter() - t0
    comps = [m for m in comps if len(m) >= min_points]
    comps.sort(key=len, reverse=True)
    stats = dict(n_hot=len(hot_idx), n_cells=len(grid), n_comps=len(comps),
                 ms_cluster=dt * 1000.0)
    return comps[:top_k], stats


def cluster_summary(comp, xs, ys, zs):
    n = len(comp)
    xs_ = sorted(xs[pt] for pt in comp)
    ys_ = sorted(ys[pt] for pt in comp)
    cx = xs_[n // 2]
    cy = ys_[n // 2]
    r2s = sorted((xs[pt] - cx) ** 2 + (ys[pt] - cy) ** 2 for pt in comp)
    r90 = math.sqrt(r2s[int(n * 0.9)])
    zmax = max(zs[pt] for pt in comp)
    return dict(cx=cx, cy=cy, r90=r90, zmax=zmax, n=n)


def make_eps_fn(k, eps_min):
    def fn(r):
        return max(eps_min, k * r)
    return fn, dict(k=k, eps_min=eps_min, form="max(eps_min,k*r)")


def load_bg_envelope(path):
    with open(path, encoding="utf-8") as fh:
        d = json.load(fh)
    return {int(k): float(v) for k, v in d.items()}


def find_hot_js(xs, ys, zs, bg, z_lo, z_hi):
    """忠实复现 detect_overlay.js find_hot: z∈(z_lo,z_hi) ∧ 有 BG ∧ z>BG+0.25."""
    hot = []
    for i in range(len(xs)):
        z = zs[i]
        if z <= z_lo or z >= z_hi:
            continue
        bg_v = bg.get(grid_key(xs[i], ys[i]), -10.0)
        if bg_v < -9:
            continue
        if z > bg_v + 0.25:
            hot.append(i)
    return hot

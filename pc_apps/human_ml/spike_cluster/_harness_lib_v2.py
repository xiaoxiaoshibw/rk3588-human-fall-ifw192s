# -*- coding: utf-8 -*-
"""_harness_lib_v2.py — B/C 聚类实现 v2 (修 v1 的 z-band 平均填塞误). 与 v1 并存.

v1 的缺陷 (test_4 暴露):
  find_clusters_BC 用 cell 的 mean z 判定 height_band,
  当一 cell 跨带 (x,y 同格, 有 z=1.0 和 z=1.8 两组点) 时 mean 归 1.4 -> 属于 band (1.0,2.0),
  C 无法拆开这两组， 失去防并簇意义.

v2 修复:
  将 (key, z-band) 二复合作为子 cell — 同一 (x,y) cell 的点按 z 分带独立成子簇,
  防并簇判定在两子簇之间做. 这等价于点级 z-band 限制, 不依赖均值近似.

  其它: 保持 v1 的全接口 (find_clusters_A 不变量, B 不变), 只新增 find_clusters_C_pointband.
"""
import math
import time
from collections import defaultdict

from _harness_lib import (GRID_CELL_M, KEY_MOD, _js_mod, grid_key, grid_xy,
                          _bfs_expand, cluster_summary, make_eps_fn,
                          find_clusters_A, find_clusters_BC, load_bg_envelope,
                          find_hot_js)


def subcell_key(global_cell_key, z, wall_bands):
    """sub cell = key * band_constant + band_id. band_constant=8 容纳 band ids 0..7."""
    if not wall_bands:
        return global_cell_key * 8
    for i, (lo, hi) in enumerate(wall_bands):
        if lo <= z < hi:
            return global_cell_key * 8 + i + 1     # band 0 reserved: non-band
    return global_cell_key * 8


def band_of_subkey(sk):
    return sk % 8


def cell_of_subkey(sk):
    return sk // 8


def find_clusters_C_pointband(xs, ys, zs, hot_idx, eps_fn,
                              min_points=30, top_k=4, wall_bands=None):
    """C 聚类 (点级 z-band 防并簇):
    1. 把 hot 点按 (grid_key, z-band) 双键归 subcell;
    2. subcell 之间按 eps(r_cur_subcell) 确定 Chebyshev 最大 cell 探查,
       BFS 只扩同 sign (高度相容: 带带交叉不互连);
    3. Chebyshev r 计算以 cell 网格做, 两个 subcell 的"邻接"以所属 mother cell 的差为准.
    """
    t0 = time.perf_counter()
    # 1. 分 subcell (m_key, band_id) 桶
    subgrid = defaultdict(list)   # subcell_key -> [pts]
    cell_r = {}
    band_id = {}
    for pt in hot_idx:
        key = grid_key(xs[pt], ys[pt])
        sk = subcell_key(key, zs[pt], wall_bands)
        subgrid[sk].append(pt)
    # 2. 预算每个 subcell 的 mean r / 所在母 cell
    for sk, members in subgrid.items():
        sr = sum(math.sqrt(xs[pt] * xs[pt] + ys[pt] * ys[pt]) for pt in members)
        cell_r[sk] = sr / len(members)
        band_id[sk] = band_of_subkey(sk)

    def allow_fn(cur_sk, nei_sk, is_scope_query):
        if is_scope_query:
            return math.ceil(eps_fn(cell_r[cur_sk]) / GRID_CELL_M)
        # 对称距离门
        eps_ref = min(eps_fn(cell_r[cur_sk]), eps_fn(cell_r[nei_sk]))
        cur_cell = cell_of_subkey(cur_sk)
        nei_cell = cell_of_subkey(nei_sk)
        cgx_c, cgy_c = grid_xy(cur_cell)
        cgx_n, cgy_n = grid_xy(nei_cell)
        d_cell = max(abs(cgx_n - cgx_c), abs(cgy_n - cgy_c))
        if d_cell * GRID_CELL_M > eps_ref + GRID_CELL_M:
            return False
        # z-band 相容性
        b_cur = band_id[cur_sk]
        b_nei = band_id[nei_sk]
        if b_cur > 0 and b_nei > 0 and b_cur != b_nei:
            return False
        return True

    # 3. BFS 在 subcell 图
    seen = set()
    comps = []
    for seed_sk in subgrid:
        if seed_sk in seen:
            continue
        stack = [seed_sk]
        members = []
        seen.add(seed_sk)
        while stack:
            cur_sk = stack.pop()
            members.extend(subgrid[cur_sk])
            cur_cell = cell_of_subkey(cur_sk)
            cgx, cgy = grid_xy(cur_cell)
            rmax = allow_fn(cur_sk, None, True)
            for dx in range(-rmax, rmax + 1):
                for dy in range(-rmax, rmax + 1):
                    if dx == 0 and dy == 0:
                        continue
                    nei_cell = (cgx + dx) * KEY_MOD + _js_mod(cgy + dy, KEY_MOD)
                    # 列出所有该 cell 的 subcells (band 0..7)
                    for b in range(8):
                        nei_sk = nei_cell * 8 + b
                        if nei_sk in subgrid and nei_sk not in seen and allow_fn(cur_sk, nei_sk, False):
                            seen.add(nei_sk)
                            stack.append(nei_sk)
        comps.append(members)
    dt = time.perf_counter() - t0
    comps = [m for m in comps if len(m) >= min_points]
    comps.sort(key=len, reverse=True)
    stats = dict(n_hot=len(hot_idx), n_cells=len(subgrid), n_comps=len(comps),
                 ms_cluster=dt * 1000.0)
    return comps[:top_k], stats

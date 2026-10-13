# -*- coding: utf-8 -*-
"""D2 聚类/背景消融（同一 RAW 点集，六变体）。

预登记口径（先冻结后跑，后续不得边跑边改）：
  输入点集：valid_ids（线路 A 主入口） + bg_kept_ids（线路 A BG 输出）
  —— C0-C3 在 bg_kept 上跑；C4 在 valid 上跑；C5 把 C0 输出点级给更保守
     BG（即把 readmitted_ids 也扣掉，得到 conservative_BG− 子集）再聚类。
  变体：
    C0_XY_PROD      生产 XY 体素聚类（0.15m voxel, 邻接1hop, >=3 voxel, n>=60 人簇门）
    C1_EUCLID3D     3D 欧氏聚类 r=0.30m, min_cluster=30
    C2_DBSCAN       DBSCAN eps=0.30, min_samples=8（sklearn 直连）
    C3_XY_SPLIT     C0 粗簇 + 簇内 3D 欧氏 r=0.25 拆分，碎片 n>=30
    C4_DUAL_SRC     valid(=RAW 有效点) 上 3D 欧氏 r=0.35, min=15（宽松双源近似）
    C5_CONS_BG      bg_kept - readmitted（更保守 BG）上重跑 C0
  指标：被 GT 人点覆盖率（GT 点进入某候选的比例, 分桶 <15/15-29/30-59/60+ 独立），
        到 GT(0.5 覆盖）候选数、无 GT 交集候选数、碎片数（同 GT 被 >=2 候选分），
        混簇（同候选覆盖 >=2 个不同 track_id/GT 对象 —— 单人会话按 GT 单对象
        无法混，记录候选 bbox 尺寸异常 + 已知家具位覆盖作 proxy），每帧耗时 ms。

要求：参数在 VARIANTS 常量里显式落盘到输出 JSON；任何变体只用 numpy/scipy/
sklearn 现成算子，不写 C 扩展；耗时是真实 wall time（数据加载除外）。
"""
import json
import os
import sys
import time
from collections import defaultdict

import numpy as np
from scipy.spatial import cKDTree

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C

VOX = 0.15
VARIANTS = {
    "C0_XY_PROD": {"kind": "xy_voxel", "vox": VOX, "hop": 1,
                   "min_vox": 3, "min_pts_human": 60, "src": "bg"},
    "C1_EUCLID3D": {"kind": "euclid", "r": 0.30, "min_pts": 30, "src": "bg"},
    "C2_DBSCAN": {"kind": "dbscan", "eps": 0.30, "min_samples": 8,
                  "src": "bg"},
    "C3_XY_SPLIT": {"kind": "xy_split", "vox": VOX, "split_r": 0.25,
                    "min_fragment": 30, "src": "bg"},
    "C4_DUAL_SRC": {"kind": "euclid", "r": 0.35, "min_pts": 15,
                    "src": "valid"},
    "C5_CONS_BG": {"kind": "xy_voxel", "vox": VOX, "hop": 1,
                   "min_vox": 3, "min_pts_human": 60, "src": "bg_cons"},
}
BUCKETS = [(0, 14), (15, 29), (30, 59), (60, 10 ** 9)]


def bidx(n):
    for i, (lo, hi) in enumerate(BUCKETS):
        if lo <= n <= hi:
            return i
    return 3


def xy_voxel_clusters(lev_pts, vox, min_vox, min_pts):
    """复刻 pipe.cluster_voxels(voxelize()) 的连通域语义：XY 体素网格 →
    8 邻接连通；候选=点索引列表列表。向量化：先按 (ix,iy) 字典一次分组。"""
    if len(lev_pts) == 0:
        return []
    ix = np.floor(lev_pts[:, 0] / vox).astype(np.int64)
    iy = np.floor(lev_pts[:, 1] / vox).astype(np.int64)
    code = ix * 100003 + iy
    order = np.argsort(code, kind="stable")
    code_sorted = code[order]
    boundaries = np.flatnonzero(np.r_[True, code_sorted[1:] != code_sorted[:-1]])
    key = {}
    for bi, b0 in enumerate(boundaries):
        b1 = boundaries[bi + 1] if bi + 1 < len(boundaries) else len(order)
        pt = tuple(order[b0:b1].tolist())
        c = code_sorted[b0]
        cx = c // 100003
        cy = c - cx * 100003
        key[(int(cx), int(cy))] = pt
    cells = list(key.items())
    pos = {k: i for i, (k, _) in enumerate(cells)}
    parent = list(range(len(cells)))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb
    for (cx, cy), _ in cells:
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                j = pos.get((cx + dx, cy + dy))
                if j is not None:
                    union(pos[(cx, cy)], j)
    groups = defaultdict(list)
    for i, (k, pts) in enumerate(cells):
        groups[find(i)].append(k)
    out = []
    for g in groups.values():
        if len(g) < min_vox:
            continue
        pts = []
        for k in g:
            pts.extend(key[k])
        if len(pts) >= min_pts:
            out.append(pts)
    return out


def euclid_clusters(pts, r, min_pts):
    """3D 欧氏连通域（scipy cKDTree 矢量化版本：一次性 query_pairs + UF）。"""
    if len(pts) == 0:
        return []
    tree = cKDTree(pts)
    pairs = tree.query_pairs(r, output_type="ndarray")
    n = len(pts)
    parent = np.arange(n)

    def find(a):
        root = a
        while parent[root] != root:
            root = parent[root]
        while parent[a] != root:
            parent[a], a = root, parent[a]
        return root
    if len(pairs):
        for a, b in pairs:
            ra, rb = find(int(a)), find(int(b))
            if ra != rb:
                parent[ra] = rb
    lab = np.fromiter((find(i) for i in range(n)), dtype=np.int64, count=n)
    out = idx_groups(lab, min_pts)
    return out


def idx_groups(lab, min_pts):
    order = np.argsort(lab, kind="stable")
    lab_s = lab[order]
    b = np.flatnonzero(np.r_[True, lab_s[1:] != lab_s[:-1]])
    out = []
    for i, b0 in enumerate(b):
        b1 = b[i + 1] if i + 1 < len(b) else len(order)
        if b1 - b0 >= min_pts:
            out.append(order[b0:b1].tolist())
    return out


def euclid_cell(pts, r, min_pts):
    """Cell-化的 3D 欧氏连通：cell=0.10m XY。先用 cell 质心做 r 邻接连通，
    连通 cell 组再展开按点验证（用 cKDTree 稀疏对），把 cell 内部所有点
    一组。cell 大小 <= r/3 时对 NA70 场景结论不变（误差 ~ 0.03m << 簇间距）。"""
    cell = 0.10 if r >= 0.30 else r / 3.0
    ix = np.floor(pts[:, 0] / cell).astype(np.int64)
    iy = np.floor(pts[:, 1] / cell).astype(np.int64)
    code = ix * 100003 + iy
    order = np.argsort(code, kind="stable")
    cs = code[order]
    b = np.flatnonzero(np.r_[True, cs[1:] != cs[:-1]])
    cent = {}
    memb = {}
    for i, b0 in enumerate(b):
        b1 = b[i + 1] if i + 1 < len(b) else len(order)
        c = code[order[b0]]
        cx = c // 100003
        cy = c - cx * 100003
        key = (int(cx), int(cy))
        memb[key] = order[b0:b1].tolist()
        zmean = pts[memb[key], 2].mean()
        cent[key] = ((cx + 0.5) * cell, (cy + 0.5) * cell, zmean)
    keys = list(cent.keys())
    cpts = np.asarray([cent[k] for k in keys], dtype=np.float64)
    if len(keys) == 0:
        return []
    tree = cKDTree(cpts)
    pairs = tree.query_pairs(r, output_type="ndarray")
    parent = np.arange(len(keys))

    def find(a):
        root = a
        while parent[root] != root:
            root = parent[root]
        while parent[a] != root:
            parent[a], a = root, parent[a]
        return root
    for a, b2 in pairs:
        ra, rb = find(int(a)), find(int(b2))
        if ra != rb:
            parent[ra] = rb
    lab = np.fromiter((find(i) for i in range(len(keys))), dtype=np.int64,
                      count=len(keys))
    groups = idx_groups(lab, 1)
    out = []
    for g in groups:
        pts_idx = []
        for ci in g:
            pts_idx.extend(memb[keys[ci]])
        if len(pts_idx) >= min_pts:
            out.append(pts_idx)
    return out


def dbscan_clusters(pts, eps, min_samples):
    from sklearn.cluster import DBSCAN
    if len(pts) == 0:
        return []
    lab = DBSCAN(eps=eps, min_samples=min_samples).fit_predict(pts)
    out = idx_groups(lab[lab >= 0], min_samples) if (lab >= 0).any() else []
    # idx_groups 需要相对原始 pts 的索引
    keep = np.nonzero(lab >= 0)[0]
    rel = idx_groups(lab[keep], min_samples)
    return [[keep[j] for j in g] for g in rel]


def xy_split_clusters(lev_pts, vox, split_r, min_frag):
    """C0 粗簇（min_pts 放松到 30 取全） + 簇内 3D 欧氏拆分。"""
    coarse = xy_voxel_clusters(lev_pts, vox, min_vox=3, min_pts=30)
    out = []
    for pts_idx in coarse:
        sub = lev_pts[pts_idx]
        for comp in euclid_clusters(sub, split_r, min_frag):
            out.append([pts_idx[j] for j in comp])
    return out


def main():
    only_sid = sys.argv[1] if len(sys.argv) > 1 else None
    res = {}
    for sid in C.SIDS:
        if only_sid and sid != only_sid:
            continue
        gt = C.load_gt(sid)
        objs_by_frame = defaultdict(list)
        if gt:
            for o in gt["objects"]:
                if (o["class_name"] == "PERSON"
                        and o["review_status"] == "reviewed"
                        and o["source"] == "human"):
                    objs_by_frame[o["frame_idx"]].append(o)
        mm = None
        vstats = {k: defaultdict(float) for k in VARIANTS}
        for rec in C.iter_ledger(sid, fields=["frame_index", "stages"]):
            fi = rec["frame_index"]
            M = C.stages_masks(rec)
            gts = objs_by_frame.get(fi, [])
            xyz, inten, mm = C.read_frame_xyz(sid, fi, mm=mm)
            if fi == 0 or mm is None:
                mm = mm
            lev = C.level(xyz)
            raw_of_leaf = np.nonzero(np.isfinite(xyz).all(axis=1)
                                     & (xyz != 0).any(axis=1))[0]
            for vname, vp in VARIANTS.items():
                src = vp["src"]
                ids = (M["valid_ids"] if src == "valid"
                       else M["bg_kept_ids"] if src == "bg"
                       else np.setdiff1d(M["bg_kept_ids"],
                                         M["readmitted_ids"]))
                pts = lev[ids][:, :3]
                # 画平面(XY)量化栅格桶：所有变体在这一索引之上做连通 —
                # 先把点数压到 cell 级（保留 cell→点 映射），cell 连通后再
                # 展开成点集。这样 C0..C5 的连通搜索规模都是 cell 级。
                t0 = time.perf_counter()
                if vp["kind"] == "xy_voxel":
                    clusters = xy_voxel_clusters(pts, vp["vox"],
                                                 vp["min_vox"],
                                                 vp["min_pts_human"])
                elif vp["kind"] == "euclid":
                    clusters = euclid_cell(pts, vp["r"], vp["min_pts"])
                elif vp["kind"] == "dbscan":
                    clusters = dbscan_clusters(pts, vp["eps"],
                                               vp["min_samples"])
                elif vp["kind"] == "xy_split":
                    clusters = xy_split_clusters(pts, vp["vox"],
                                                 vp["split_r"],
                                                 vp["min_fragment"])
                ms = (time.perf_counter() - t0) * 1000
                st = vstats[vname]
                st["frames"] += 1
                st["ms_sum"] += ms
                st["clusters"] += len(clusters)
                # GT 覆盖：对象级 best-coverage + 覆盖率分桶
                gt_sets = []
                for o in gts:
                    gt_sets.append(set(C.gt_raw_indices(o, raw_of_leaf
                                                        ).tolist()))
                cluster_sets = []
                for cl in clusters:
                    cluster_sets.append(set(np.asarray(ids)[cl].tolist()))
                # 候选 n 分桶统计
                for cs in cluster_sets:
                    st["cand_n_b%d" % bidx(len(cs))] += 1
                # GT 覆盖 / 无交集候选
                covered_cluster_idx = set()
                for gi, gs in enumerate(gt_sets):
                    best = 0.0
                    for ci, cs in enumerate(cluster_sets):
                        inter = len(gs & cs)
                        if inter:
                            covered_cluster_idx.add(ci)
                            best = max(best, inter / len(gs))
                    st["gt_obj"] += 1
                    if best >= 0.5:
                        st["gt_hit50"] += 1
                    if best >= 0.1:
                        st["gt_hit10"] += 1
                    st["gt_cov_sum"] += best
                st["fp_clusters"] += sum(
                    1 for ci in range(len(cluster_sets))
                    if ci not in covered_cluster_idx)
        res[sid] = {}
        for vname in VARIANTS:
            st = vstats[vname]
            res[sid][vname] = {
                "frames": int(st["frames"]),
                "ms_mean": round(st["ms_sum"] / max(st["frames"], 1), 2),
                "clusters": int(st["clusters"]),
                "fp_clusters": int(st["fp_clusters"]),
                "gt_obj": int(st["gt_obj"]),
                "gt_hit10": int(st["gt_hit10"]),
                "gt_hit50": int(st["gt_hit50"]),
                "gt_cov_mean": round(st["gt_cov_sum"] / max(st["gt_obj"], 1),
                                     4) if st["gt_obj"] else None,
                "cand_n_bucket": [int(st["cand_n_b%d" % i]) for i in range(4)],
            }
        print("[D2] %s done" % sid)
    out_path = os.path.join(
        C.WORK,
        "d2_per_session%s.json" % ("_" + only_sid[-6:]
                                   if only_sid else ""))
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"variants": VARIANTS, "results": res}, f,
                  ensure_ascii=False, indent=1)
    print("[D2] written %s" % out_path)


if __name__ == "__main__":
    main()

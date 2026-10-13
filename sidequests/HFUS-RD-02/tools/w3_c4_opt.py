# -*- coding: utf-8 -*-
"""HFUS-RD-02 工作三：C4 性能/精度优化变体对比（重写版）。

基线 C4_FROZEN 与六变体在同一批帧、同一 GT 上对比。共享核 = cell 化
3D 欧氏连通（0.10m XY cell 压缩 + cKDTree query_pairs + 并查集），与
HFUS-RD-01 d2_cluster_ablation.euclid_cell 同语义。

变体（预登记，先冻结后跑）：
  C4_FROZEN   valid 全点, cell欧氏 r=0.35 min=15             [基线]
  C4A_ROI     z∈[0.05,2.5] & r_xy≤8m 后再 C4                  [局部ROI+空间索引]
  C4B_XY2D    XY cell(0.15) 2D粗连通(r=0.30) → 簇内 3D r=0.35  [XY粗+3D细分]
  C4C_RAWFG   C4(valid) ∪ C0式XY体素(FG) 候选并集             [RAW/FG双来源]
  C4D_ADAPT   两段局部 r：r1=0.22 粗聚 → 稀疏小簇局部 r2=0.45   [自适应邻域]
  C4E_SLIDE   静态区缓存：暖帧只对"未静区"残点重聚，静区复用      [减跨帧重复]
  C4F_KDCELL  0.05m 体素下采样 → 质心上 C4 → 挂回原点           [高效3D邻域]
  C4G_SPLIT   C4 后对 ≥800 点簇用 r=0.20 二次拆分              [治静态大物/混簇]

指标：GT 对象级召回@cov0.5、GT 点级覆盖均值、GT命中簇纯度均值、
  无GT交集候选数（误候选）、静态大物候选(≥2000点)、混簇(≥2GT)、
  碎片(同GT≥2候选)、帧均/P50/P95 耗时(ms, 不含数据加载)。

ponytail: 复用 HFUS-RD-01 common.py；FG 只在 C4C 需要时按帧号流式取。
输出 work/w3_frames.jsonl + evidence/W3_C4_OPT.json。
"""
import json
import os
import re
import sys
import time
from collections import defaultdict

import numpy as np
from scipy.spatial import cKDTree

_RD1 = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                    "..", "..", "HFUS-RD-01", "tools")
sys.path.insert(0, os.path.abspath(_RD1))
import common as C  # noqa: E402
from d2_cluster_ablation import xy_voxel_clusters  # noqa: E402 生产同源粗聚

EVID = os.path.join(C.REPO, "docs", "sidequests", "evidence",
                    "2026-10-12_HFUS_RD_02_r1")
WORK = os.path.join(C.REPO, "sidequests", "HFUS-RD-02", "work")
os.makedirs(EVID, exist_ok=True)
os.makedirs(WORK, exist_ok=True)

R = 0.35
MIN = 15
STATIC_BIG = 2000
BIG_SPLIT = 800
ROI_Z = (0.05, 2.5)
ROI_XY = 8.0
C4C_SIDS = ["cap_20261010_175429", "cap_20261010_175943",
            "cap_20261010_180557"]  # FG 流式读取代价大 → 只跑 3 代表会话

VARIANTS = ["C4_FROZEN", "C4A_ROI", "C4B_XY2D", "C4C_RAWFG", "C4D_ADAPT",
            "C4E_SLIDE", "C4F_KDCELL", "C4G_SPLIT", "C4G2_SPLIT25",
            "C4H_SCIPY_UF"]


# ---------- 共享核 ----------

def cell_groups(pts, cell=0.10):
    """pts (N,3) → (keys, memb, centroids)。XY cell 化压缩。"""
    if len(pts) == 0:
        return [], {}, np.empty((0, 3))
    ix = np.floor(pts[:, 0] / cell).astype(np.int64)
    iy = np.floor(pts[:, 1] / cell).astype(np.int64)
    code = ix * 100003 + iy
    order = np.argsort(code, kind="stable")
    cs = code[order]
    b = np.flatnonzero(np.r_[True, cs[1:] != cs[:-1]])
    keys, memb, cent = [], {}, []
    for i, b0 in enumerate(b):
        b1 = b[i + 1] if i + 1 < len(b) else len(order)
        c = int(code[order[b0]])
        cx, cy = c // 100003, c - (c // 100003) * 100003
        key = (int(cx), int(cy))
        keys.append(key)
        memb[key] = order[b0:b1]
        cent.append(((cx + 0.5) * cell, (cy + 0.5) * cell,
                     float(pts[memb[key], 2].mean())))
    return keys, memb, np.asarray(cent) if cent else np.empty((0, 3))


def uf_labels(n, pairs):
    parent = np.arange(n)

    def find(a):
        root = a
        while parent[root] != root:
            root = parent[root]
        while parent[a] != root:
            parent[a], a = root, parent[a]
        return root
    for a, b in pairs:
        ra, rb = find(int(a)), find(int(b))
        if ra != rb:
            parent[ra] = rb
    return np.fromiter((find(i) for i in range(n)), dtype=np.int64, count=n)


def expand(lab, keys, memb, min_pts):
    """cell 标签 → 点索引列表（cell 内局部索引，调用侧映射回原点域）。"""
    ordr = np.argsort(lab, kind="stable")
    ls = lab[ordr]
    bb = np.flatnonzero(np.r_[True, ls[1:] != ls[:-1]])
    out = []
    for i, b0 in enumerate(bb):
        b1 = bb[i + 1] if i + 1 < len(bb) else len(ordr)
        pts_idx = []
        for ci in ordr[b0:b1]:
            pts_idx.extend(memb[keys[int(ci)]].tolist())
        if len(pts_idx) >= min_pts:
            out.append(np.asarray(pts_idx, dtype=np.int64))
    return out


def c4_core(pts, r=R, min_pts=MIN, uf="py"):
    """基线核：cell 化欧氏。uf='scipy' 用 csgraph 连通（替代 Python UF 环）。
    Python UF 环在 ~1e5 对上是热点——这是"高效3D邻域搜索"的可测项。"""
    keys, memb, cent = cell_groups(pts)
    if not keys:
        return []
    pairs = cKDTree(cent).query_pairs(r, output_type="ndarray")
    if uf == "scipy" and len(pairs):
        from scipy.sparse import coo_matrix
        from scipy.sparse.csgraph import connected_components
        n = len(keys)
        g = coo_matrix((np.ones(len(pairs), dtype=np.int8),
                        (pairs[:, 0], pairs[:, 1])), shape=(n, n))
        _nc, lab = connected_components(g, directed=False)
        lab = lab.astype(np.int64)
    else:
        lab = uf_labels(len(keys), pairs)
    return expand(lab, keys, memb, min_pts)


# ---------- 变体实现（输入 pts 局部点集，输出局部点索引列表） ----------

def v_roi(pts):
    m = ((pts[:, 2] >= ROI_Z[0]) & (pts[:, 2] <= ROI_Z[1])
         & (np.hypot(pts[:, 0], pts[:, 1]) <= ROI_XY))
    sub = np.nonzero(m)[0]
    return [sub[np.asarray(g, dtype=np.int64)] for g in c4_core(pts[sub])]


def v_xy2d(pts):
    """XY cell(0.15) 2D 连通（矢量化 KD pairs）→ 簇内 3D 欧氏细分。"""
    keys, memb, cent = cell_groups(pts, cell=0.15)
    if not keys:
        return []
    pairs = cKDTree(cent[:, :2]).query_pairs(0.30, output_type="ndarray")
    lab = uf_labels(len(keys), pairs)
    coarse = expand(lab, keys, memb, 1)
    out = []
    for comp in coarse:
        comp = np.asarray(comp, dtype=np.int64)
        for frag in c4_core(pts[comp], r=R, min_pts=MIN):
            out.append(comp[np.asarray(frag, dtype=np.int64)])
    return out


def v_adapt(pts):
    """两段局部 r：r1=0.22 粗聚；点数<30 的稀疏簇局部 r2=0.45 重连。"""
    if len(pts) < MIN:
        return []
    coarse = c4_core(pts, r=0.22, min_pts=max(5, MIN // 3))
    out = []
    for comp in coarse:
        comp = np.asarray(comp, dtype=np.int64)
        r2 = 0.45 if len(comp) < 30 else 0.22
        for frag in c4_core(pts[comp], r=r2, min_pts=MIN):
            out.append(comp[np.asarray(frag, dtype=np.int64)])
    return out


def v_kdcell(pts, vox=0.05):
    """体素下采样 → 质心上 C4 → 挂回原点（邻域规模从点级降到体素级）。"""
    if len(pts) < MIN:
        return []
    key = np.floor(pts / vox).astype(np.int64)
    code = ((key[:, 0] * 73856093) ^ (key[:, 1] * 19349663)
            ^ (key[:, 2] * 83492791))
    order = np.argsort(code, kind="stable")
    cs = code[order]
    b = np.flatnonzero(np.r_[True, cs[1:] != cs[:-1]])
    groups, cents = [], []
    for i, b0 in enumerate(b):
        b1 = b[i + 1] if i + 1 < len(b) else len(order)
        g = order[b0:b1]
        groups.append(g)
        cents.append(pts[g].mean(axis=0))
    cents = np.asarray(cents)
    out = []
    for comp in c4_core(cents, r=R, min_pts=1):
        idx = np.concatenate([groups[int(j)] for j in comp])
        if len(idx) >= MIN:
            out.append(np.sort(idx))
    return out


def v_split_big(pts, big=BIG_SPLIT, r_split=0.20, frag_min=None):
    """C4 后对 ≥big 点簇 r_split 二次拆分。frag_min: 碎片点数下限
    （默认 MIN；调小以保 GT 点不被碎丢）。"""
    fm = MIN if frag_min is None else frag_min
    out = []
    for comp in c4_core(pts):
        comp = np.asarray(comp, dtype=np.int64)
        if len(comp) < big:
            out.append(comp)
            continue
        for frag in c4_core(pts[comp], r=r_split, min_pts=fm):
            out.append(comp[np.asarray(frag, dtype=np.int64)])
    return out


def v_slide(pts, state):
    """跨帧复用：静态区（≥2000 点、质心稳定）bbox 内的点免重聚，直接
    复用为上帧静簇；只对残点重聚。返回 (clusters, state, cold_bool)。"""
    regions = state["regions"]
    if not regions:                       # 冷帧：全量 C4 + 注册静区
        cl = c4_core(pts)
        _update_regions(state, pts, cl)
        return cl, state, True
    # 暖帧：静区掩码
    static_mask = np.zeros(len(pts), dtype=bool)
    for r_ in regions:
        mn, mx = r_["bbox_min"], r_["bbox_max"]
        static_mask |= np.all((pts >= mn) & (pts <= mx), axis=1)
    res_idx = np.nonzero(~static_mask)[0]
    out = []
    for comp in c4_core(pts[res_idx]):
        out.append(res_idx[np.asarray(comp, dtype=np.int64)])
    # 静区点仍作为候选复用（按注册序）
    for r_ in regions:
        mn, mx = r_["bbox_min"], r_["bbox_max"]
        m = np.all((pts >= mn) & (pts <= mx), axis=1)
        idx = np.nonzero(m)[0]
        if len(idx) >= MIN:
            out.append(idx)
    _update_regions(state, pts, out)
    return out, state, False


def _update_regions(state, pts, clusters, cap=40):
    regions = state["regions"]
    new = []
    for comp in clusters:
        comp = np.asarray(comp, dtype=np.int64)
        if len(comp) < STATIC_BIG:
            continue
        p = pts[comp]
        c = p.mean(axis=0)
        new.append({"bbox_min": p.min(axis=0).tolist(),
                    "bbox_max": p.max(axis=0).tolist(),
                    "centroid": c.tolist(), "n": int(len(comp))})
    # 与旧区按质心邻近合并（只在 bbox 略胀时不无限增长）
    for r_ in regions:
        oc = np.asarray(r_["centroid"])
        for n_ in new:
            if np.linalg.norm(np.asarray(n_["centroid"]) - oc) < 0.10:
                n_["bbox_min"] = np.minimum(n_["bbox_min"],
                                            r_["bbox_min"]).tolist()
                n_["bbox_max"] = np.maximum(n_["bbox_max"],
                                            r_["bbox_max"]).tolist()
                n_["centroid"] = (np.asarray(n_["bbox_min"])
                                  + np.asarray(n_["bbox_max"])).tolist()
                break
    state["regions"] = new[:cap]


# ---------- FG 流式读取（只为 C4C） ----------

_FRAME_RE = re.compile(r'"frame_index"\s*:\s*(\d+)')


def load_fg_bg_kept(sid, frames):
    """{frame: bg_kept_ids(int 数组)}，仅对请求帧 json.loads 整行。"""
    need = set(int(f) for f in frames)
    out = {}
    path = C.LEDGER_PATHS[sid]
    with open(path, encoding="utf-8") as f:
        for line in f:
            m = _FRAME_RE.search(line, 0, 400)
            if not m:
                continue
            fi = int(m.group(1))
            if fi not in need:
                continue
            rec = json.loads(line)
            M = C.stages_masks(rec)
            out[fi] = M.get("bg_kept_ids", np.array([], dtype=np.int64))
            need.discard(fi)
            if not need:
                break
    return out


# ---------- 评估 ----------

def frame_metrics(clusters_raw, gt_sets):
    """clusters_raw: list of raw-域索引数组；gt_sets: list of raw 索引集。"""
    cl_sets = [set(cr.tolist()) for cr in clusters_raw]
    gt_hit = mixed = big = no_inter = frag = 0
    pur_sum = pur_n = 0
    for cs in cl_sets:
        n = len(cs)
        if n >= STATIC_BIG:
            big += 1
        hits = [gs for gs in gt_sets
                if len(cs & gs) >= max(1, len(gs) // 10)]
        if len(hits) >= 2:
            mixed += 1
        if hits:
            gt_hit += 1
            best = max(len(cs & gs) for gs in hits)
            pur_sum += best / n          # GT命中簇纯度 = 最大GT交集/簇大小
            pur_n += 1
        else:
            no_inter += 1
    cov_sum = 0.0
    gt_cov50 = 0
    for gs in gt_sets:
        best = max((len(cs & gs) / len(gs) for cs in cl_sets), default=0.0)
        cov_sum += best
        if best >= 0.5:
            gt_cov50 += 1
        if sum(1 for cs in cl_sets
               if len(cs & gs) >= max(1, len(gs) // 10)) >= 2:
            frag += 1
    return {
        "clusters": len(cl_sets), "gt_hit": gt_hit, "mixed": mixed,
        "big_static": big, "no_intersect": no_inter, "frag_gt": frag,
        "gt_total": len(gt_sets), "gt_cov50": gt_cov50,
        "cov_mean": (cov_sum / len(gt_sets)) if gt_sets else None,
        "purity_mean": (pur_sum / pur_n) if pur_n else None,
    }


def eval_frame(sid, pts_local_all, valid_ids, gt_sets, slide_state,
               fg_ids=None):
    """跑全部变体，返回 {vname: metrics+ms}。pts_local_all=valid 局部点。"""
    out = {}
    for vname in VARIANTS:
        if vname == "C4C_RAWFG" and sid not in C4C_SIDS:
            continue
        t0 = time.perf_counter()
        if vname == "C4_FROZEN":
            cl = c4_core(pts_local_all)
        elif vname == "C4A_ROI":
            cl = v_roi(pts_local_all)
        elif vname == "C4B_XY2D":
            cl = v_xy2d(pts_local_all)
        elif vname == "C4C_RAWFG":
            cl = c4_core(pts_local_all)
            if fg_ids is not None and len(fg_ids):
                # FG 子集重聚（C0 式 XY 体素，生产同源），并集去重：
                # FG 簇若被某 C4 簇完全包含则弃（无新信息）
                fg_lev = pts_local_all[fg_ids]
                c4_sets = [set(g.tolist()) for g in cl]
                for fg_comp in xy_voxel_clusters(fg_lev, 0.15, 3, 60):
                    comp = fg_ids[np.asarray(fg_comp, dtype=np.int64)]
                    s = set(comp.tolist())
                    if not any(s <= cs for cs in c4_sets):
                        cl.append(np.sort(comp))
        elif vname == "C4D_ADAPT":
            cl = v_adapt(pts_local_all)
        elif vname == "C4E_SLIDE":
            cl, slide_state, _cold = v_slide(pts_local_all, slide_state)
        elif vname == "C4F_KDCELL":
            cl = v_kdcell(pts_local_all)
        elif vname == "C4G_SPLIT":
            cl = v_split_big(pts_local_all)
        elif vname == "C4G2_SPLIT25":
            cl = v_split_big(pts_local_all, big=BIG_SPLIT, r_split=0.25,
                             frag_min=MIN)
        elif vname == "C4H_SCIPY_UF":
            cl = c4_core(pts_local_all, uf="scipy")
        else:
            raise ValueError(vname)
        ms = (time.perf_counter() - t0) * 1000
        clusters_raw = [valid_ids[np.asarray(g, dtype=np.int64)]
                        for g in cl]
        m = frame_metrics(clusters_raw, gt_sets)
        m["ms"] = ms
        out[vname] = m
    return out, slide_state


def main():
    only = sys.argv[1] if len(sys.argv) > 1 else None
    per_f = open(os.path.join(WORK, "w3_frames.jsonl"), "w", encoding="utf-8")
    agg = {sid: {v: defaultdict(float) for v in VARIANTS} for sid in C.SIDS}
    times = {sid: {v: [] for v in VARIANTS} for sid in C.SIDS}
    slide_cold = {sid: [] for sid in C.SIDS}
    for sid in C.SIDS:
        if only and sid != only:
            continue
        gt = C.load_gt(sid)
        objs_by_frame = defaultdict(list)
        if gt and sid != "cap_20261010_180751":   # S9 INVALID_BINDING
            for o in gt["objects"]:
                if (o["class_name"] == "PERSON"
                        and o["review_status"] == "reviewed"
                        and o["source"] == "human"):
                    objs_by_frame[o["frame_idx"]].append(o)
        meta = C.load_meta(sid)
        nfr = len(meta["frames"])
        gt_frames = sorted(objs_by_frame.keys())
        pad = sorted(set(range(0, nfr, max(1, nfr // 10))) - set(gt_frames))[:10]
        sample = sorted(set(gt_frames) | set(pad))[:40]
        fg_map = {}
        if sid in C4C_SIDS:
            print("[w3] %s: loading FG (ledger stream)..." % C.SID_SHORT[sid])
            fg_map = load_fg_bg_kept(sid, sample)
        mm = None
        state = {"regions": []}
        for fi in sample:
            xyz, _i, mm = C.read_frame_xyz(sid, fi, mm=mm)
            lev = C.level(xyz)
            mask = np.isfinite(lev).all(axis=1) & (lev != 0).any(axis=1)
            valid_ids = np.nonzero(mask)[0]
            pts = lev[valid_ids]
            raw_of_leaf = np.nonzero(np.isfinite(xyz).all(axis=1)
                                     & (xyz != 0).any(axis=1))[0]
            gt_sets = [set(C.gt_raw_indices(o, raw_of_leaf).tolist())
                       for o in objs_by_frame.get(fi, [])]
            fg_local = None
            if fi in fg_map and len(fg_map[fi]):
                # ledger raw 帧域 → valid 局部域：valid_ids 升序，searchsorted
                pos = np.searchsorted(valid_ids, fg_map[fi])
                pos = np.clip(pos, 0, len(valid_ids) - 1)
                ok = valid_ids[pos] == fg_map[fi]
                fg_local = np.unique(pos[ok]) if ok.any() else None
            t0 = time.perf_counter()
            res, state = eval_frame(sid, pts, valid_ids, gt_sets, state,
                                    fg_local)
            for vname, m in res.items():
                a = agg[sid][vname]
                for k, v in m.items():
                    if k == "ms":
                        times[sid][vname].append(v)
                    elif v in (None,):
                        continue
                    else:
                        a[k] += v
                a["frames_"] += 1
            if "C4E_SLIDE" in res:
                slide_cold[sid].append(res["C4E_SLIDE"]["ms"])
            per_f.write(json.dumps({"sid": sid, "frame": fi, "variants": res})
                        + "\n")
        print("[w3] %s done (%d frames)" % (C.SID_SHORT[sid], len(sample)))
    per_f.close()
    summary = {}
    for sid in C.SIDS:
        if only and sid != only:
            continue
        summary[sid] = {}
        for v in VARIANTS:
            a = agg[sid][v]
            if not a.get("frames_"):
                summary[sid][v] = {"status": "NOT_RUN"}
                continue
            t = np.array(times[sid][v])
            summary[sid][v] = {
                "frames": int(a["frames_"]),
                "obj_recall_cov50": (a["gt_cov50"] / a["gt_total"]
                                     if a["gt_total"] else None),
                "gt_cov_mean": (a["cov_mean"] / a["frames_"]),
                "purity_mean": (a["purity_mean"] / a["frames_"]),
                "clusters": int(a["clusters"]),
                "no_intersect_cand": int(a["no_intersect"]),
                "big_static_cand": int(a["big_static"]),
                "mixed_clusters": int(a["mixed"]),
                "frag_gt": int(a["frag_gt"]),
                "ms_mean": float(t.mean()),
                "ms_p50": float(np.percentile(t, 50)),
                "ms_p95": float(np.percentile(t, 95)),
            }
    op = os.path.join(EVID, "W3_C4_OPT.json")
    with open(op, "w", encoding="utf-8") as f:
        json.dump({
            "date": "2026-10-12",
            "head": "026e06303f60ed1bbe4ddc4d037836db68da6d27",
            "params": {"r": R, "min_pts": MIN, "static_big": STATIC_BIG,
                       "big_split": BIG_SPLIT, "split_r": 0.20,
                       "split_r_G2": 0.25, "roi_z": ROI_Z,
                       "roi_xy": ROI_XY, "c4c_sids": C4C_SIDS,
                       "uf_scipy": "C4H_SCIPY_UF=csgraph 连通（替代 py UF）",
                       "sampling": "GT帧全取 + 均匀补 ~10 帧, ≤40 帧/会话"},
            "variants": VARIANTS,
            "per_session": summary,
        }, f, ensure_ascii=False, indent=2, default=str)
    print("[w3] written", op)


if __name__ == "__main__":
    main()

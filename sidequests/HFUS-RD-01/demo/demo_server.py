#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HFUS-RD-01 对照工作台服务器（默认 :8930）。

设计目标：
  1. GET /          → 本目录 demo_compare.html
  2. GET /api/meta  → 会话列表 + 变体 + 桶
  3. GET /api/frame?sid=S&fi=N → 该帧的 mainline 候选 / D2 变体候选（懒算）
     / GT 人点（compact→raw） / Void 下点诊断 / 主链 RF/扩展特征
  4. GET /points/<sid>?offset=&count=  → points.bin Range
  5. GET /api/casebook → CASEBOOK.md 注册的成功/失败案例表

只读生产输入，不动任何 captures/GT/ledger。数据全部按请求现算，
服务器内部对帧级重计算结果做小缓存。
"""
import json
import os
import sys
import threading
from http import server as http_server
from pathlib import Path
from socketserver import ThreadingTCPServer

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent.parent
sys.path.insert(0, str(HERE.parent / "tools"))

import numpy as np  # noqa: E402
import common as C  # noqa: E402

from scipy.spatial import cKDTree  # noqa: E402

PORT = 8930
SIDS = C.SIDS
VARIANTS = ["mainline", "C0", "C1", "C2", "C3", "C4", "C5"]
VDESC = {
    "mainline": "D05 R04 fast mainline 提案/接受态",
    "C0": "XY 体素聚类（生产同）",
    "C1": "3D 欧氏 r=0.30",
    "C2": "DBSCAN eps=0.30 min=8",
    "C3": "XY 粗簇+3D 内拆分",
    "C4": "RAW(valid)放宽双源 r=0.35",
    "C5": "保守BG（不 readmit）",
}

cache = {}
cache_lock = threading.Lock()
meta_cache = {}
mm_cache = {}


def load_meta(sid):
    if sid not in meta_cache:
        meta_cache[sid] = C.load_meta(sid)
    return meta_cache[sid]


def frame_xyz(sid, fi):
    if sid not in mm_cache:
        _, _, mm_cache[sid] = C.read_frame_xyz(sid, 0)
    xyz, inten, _ = C.read_frame_xyz(sid, fi, mm=mm_cache[sid])
    return xyz, inten


def get_rec(sid, fi):
    for rec in C.iter_ledger(sid, fields=["frame_index", "candidates",
                                          "gt", "stages", "tracks"]):
        if rec["frame_index"] == fi:
            return rec
    return None


def variant_clusters(pts, vname):
    v = vname
    if len(pts) == 0:
        return []
    if v == "C0":
        return _xy_voxel(pts, 0.15, 3, 60)
    if v == "C1":
        return _euclid(pts, 0.30, 30)
    if v == "C2":
        from sklearn.cluster import DBSCAN
        lab = DBSCAN(eps=0.30, min_samples=8).fit_predict(pts)
        keep = np.nonzero(lab >= 0)[0]
        rel = _groups(lab[keep], 8)
        return [[keep[j] for j in g] for g in rel]
    if v == "C3":
        coarse = _xy_voxel(pts, 0.15, 3, 30)
        out = []
        for idx in coarse:
            sub = pts[idx]
            for comp in _euclid(sub, 0.25, 30):
                out.append([idx[j] for j in comp])
        return out
    if v == "C4":
        return _euclid(pts, 0.35, 15)
    if v == "C5":
        return _xy_voxel(pts, 0.15, 3, 60)
    return []


def _xy_voxel(pts, vox, min_vox, min_pts):
    ix = np.floor(pts[:, 0] / vox).astype(np.int64)
    iy = np.floor(pts[:, 1] / vox).astype(np.int64)
    code = ix * 100003 + iy
    order = np.argsort(code, kind="stable")
    cs = code[order]
    b = np.flatnonzero(np.r_[True, cs[1:] != cs[:-1]])
    key = {}
    for i, b0 in enumerate(b):
        b1 = b[i + 1] if i + 1 < len(b) else len(order)
        c = code[order[b0]]
        cx = c // 100003
        cy = c - cx * 100003
        key[(int(cx), int(cy))] = order[b0:b1].tolist()
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
    groups = {}
    for i, (k, _) in enumerate(cells):
        groups.setdefault(find(i), []).append(k)
    out = []
    for g in groups.values():
        if len(g) < min_vox:
            continue
        pts_idx = []
        for k in g:
            pts_idx.extend(key[k])
        if len(pts_idx) >= min_pts:
            out.append(pts_idx)
    return out


def _euclid(pts, r, min_pts):
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
    lab = np.fromiter((find(i) for i in range(n)), dtype=np.int64,
                      count=n)
    return _groups(lab, min_pts)


def _groups(lab, min_pts):
    order = np.argsort(lab, kind="stable")
    lab_s = lab[order]
    b = np.flatnonzero(np.r_[True, lab_s[1:] != lab_s[:-1]])
    out = []
    for i, b0 in enumerate(b):
        b1 = b[i + 1] if i + 1 < len(b) else len(order)
        if b1 - b0 >= min_pts:
            out.append(order[b0:b1].tolist())
    return out


def frame_payload(sid, fi):
    key = (sid, fi)
    with cache_lock:
        if key in cache:
            return cache[key]
    rec = get_rec(sid, fi)
    if rec is None:
        return None
    xyz, inten = frame_xyz(sid, fi)
    lev = C.level(xyz).astype(np.float32)
    # GT (compact→raw)  projected to xyz list
    gt = C.load_gt(sid)
    gt_objs = []
    if gt is not None:
        raw_of_leaf = np.nonzero(np.isfinite(xyz).all(axis=1)
                                 & (xyz != 0).any(axis=1))[0]
        for o in gt["objects"]:
            if (o["frame_idx"] == fi and o["class_name"] == "PERSON"
                    and o["review_status"] == "reviewed"):
                raw_idx = raw_of_leaf[o["indices"]]
                gt_objs.append({"id": o["id"], "track_id": o["track_id"],
                                "pts": lev[raw_idx].tolist()})
    # mainline candidates
    cands_mainline = []
    for c in rec.get("candidates", []):
        cands_mainline.append({
            "id": c["id"], "prob": c["prob"], "n": c["n"],
            "decision": c["decision"], "src": c.get("source"),
            "pts": lev[np.asarray(c["raw_indices"], dtype=np.int64)
                       ].tolist(),
            "gt_cov": max((h["coverage"] for h in
                           (c.get("gt_hits") or [])), default=0.0)})
    # 各变体候选在同一 valid 点上快算
    xyz_inten_flat = lev[:, :3]
    variants = {}
    for vn in ["C0", "C1", "C2", "C3", "C4", "C5"]:
        src_valid = (vn == "C4")
        ids = rec["stages"]["valid_ids"] if src_valid \
            else rec["stages"]["bg_kept_ids"]
        pts = xyz_inten_flat[np.asarray(ids, dtype=np.int64)]
        clusters = variant_clusters(pts, vn)
        variants[vn] = [
            {"id": "%s_%d" % (vn, ci), "n": len(cl),
             "pts": pts[np.asarray(cl, dtype=np.int64)].tolist()}
            for ci, cl in enumerate(clusters)]
    # stages 诊断点集
    st = rec["stages"]
    diag = {}
    for name in ["valid_ids", "bg_kept_ids", "bg_deleted_ids",
                 "final_ids", "readmitted_ids"]:
        arr = np.asarray(st.get(name, []), dtype=np.int64)
        if arr.size:
            diag[name] = xyz_inten_flat[arr[::max(1, len(arr) // 5000)]
                                        ].tolist()
        else:
            diag[name] = []
    payload = {"sid": sid, "frame": fi, "gt": gt_objs,
               "mainline": cands_mainline, "variants": variants,
               "diag": diag,
               "tracks": rec.get("tracks", [])}
    with cache_lock:
        if len(cache) > 60:
            cache.pop(next(iter(cache)))
        cache[key] = payload
    return payload


class H(http_server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send_json(self, obj, code=200):
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        u = self.path.split("?", 1)
        path = u[0]
        qs = dict(p.split("=", 1) for p in (u[1].split("&") if len(u) > 1
                                            else []) if "=" in p)
        if path == "/":
            html = (HERE / "demo_compare.html").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html)))
            self.end_headers()
            self.wfile.write(html)
        elif path == "/api/meta":
            self._send_json({
                "sids": [{"sid": s, "short": C.SID_SHORT[s],
                          "frames": len(load_meta(s)["frames"])}
                         for s in SIDS],
                "variants": VARIANTS,
                "variant_desc": VDESC})
        elif path == "/api/frame":
            sid = qs.get("sid", "")
            fi = int(qs.get("fi", "0"))
            p = frame_payload(sid, fi)
            if p is None:
                self._send_json({"error": "no frame"}, 404)
            else:
                self._send_json(p)
        elif path == "/api/casebook":
            cb = ROOT / "sidequests" / "HFUS-RD-01" / "docs" / \
                "CASEBOOK.md"
            self._send_json({"text": cb.read_text(encoding="utf-8")
                             if cb.exists() else ""})
        else:
            self._send_json({"error": "not found"}, 404)


def main():
    print("Serving HFUS-RD-01 compare workbench on http://127.0.0.1:%d"
          % PORT)
    ThreadingTCPServer(("127.0.0.1", PORT), H).serve_forever()


if __name__ == "__main__":
    main()

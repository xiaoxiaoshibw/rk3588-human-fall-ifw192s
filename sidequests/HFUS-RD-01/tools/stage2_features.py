# -*- coding: utf-8 -*-
"""STAGE2：为全部 mainline 候选抽取 RF51（JS 复刻一致）+ 18 维扩展特征。

候选标签（三态，不冒充）：
  P   = 与 reviewed PERSON GT 有交集（ledger gt_hits）
  N   = 空场 S1（cap_20261010_175227，无 GT 人）全部候选
  UNK = 其余（未审/无 GT 覆盖帧的候选）——不进训练、不进负例指标
输出 work/candidates_stage2.jsonl，每行含 51+18 维特征、rf_prob、分桶。
"""
import json
import os
import subprocess
import sys
import tempfile

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C

NODE_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "rf_extract_node.js")


def extract18(xyz, inten, prob):
    """RF51 之外的结构扩展特征（18 维，来源注释见每行）。"""
    n = len(xyz)
    out = np.zeros(18, dtype=np.float32)
    if n < 10:
        return out
    z = xyz[:, 2]
    c = xyz.mean(axis=0)
    cov = np.cov((xyz - c).T) if n > 3 else np.eye(3) * 1e-9
    w = np.clip(np.linalg.eigvalsh(cov), 0, None)
    s = w.sum()
    out[0] = (w[2] - w[1]) / s if s > 0 else 0          # 线性度
    out[1] = (w[1] - w[0]) / s if s > 0 else 0          # 平面度
    out[2] = w[0] / s if s > 0 else 0                   # 散射度(≈曲率代理)
    r = np.hypot(xyz[:, 0] - c[0], xyz[:, 1] - c[1])
    out[3] = float(r.max())                              # 最大弦半径
    out[4] = float(r.mean())
    out[5] = float(r.std())
    zb = np.floor((z - z.min()) / 0.10).astype(int)
    bc = np.bincount(zb)
    out[6] = float(len(bc))                              # 10cm 带占用层数
    out[7] = float(bc.max()) / n                         # 最密带占比
    step = max(1, n // 300)
    sub = xyz[::step]
    d2 = ((sub[:, None, :] - xyz[None, :, :]) ** 2).sum(-1)
    d2.sort(axis=1)
    k = min(9, d2.shape[1] - 1)
    out[8] = float(np.sqrt(d2[:, 1:k + 1].mean()))       # 局部密度(8NN)
    zc = z - z.mean()
    out[9] = float((zc ** 4).mean() /
                   max((zc ** 2).mean() ** 2, 1e-12))    # z 峰度
    w2 = np.linalg.eigvalsh(np.cov((xyz[:, :2] - c[:2]).T))
    out[10] = float(w2[0] / max(w2[1], 1e-9))            # XY 特征值比
    out[11] = float(np.hypot(c[0], c[1]))                # 距雷达
    out[12] = float(np.arctan2(c[1], c[0]))              # 方位角
    out[13] = float(np.percentile(inten, 90) -
                    np.percentile(inten, 10))            # 强度跨度
    out[14] = float(np.log10(n))                         # log n
    out[15] = float((z > 1.3).mean())                    # 上体占比
    out[16] = float((z > 0.1).mean())                    # 离地占比
    out[17] = float(prob)                                # RF51 prob（堆叠参考）
    return out


def main():
    rows = []
    for sid in C.SIDS:
        for rec in C.iter_ledger(sid, fields=["frame_index", "sid",
                                              "candidates"]):
            fi = rec["frame_index"]
            for c in rec.get("candidates", []):
                hits = c.get("gt_hits") or []
                lab = ("P_FP_S1" if (hits and sid == "cap_20261010_175227")
                       else "P" if hits else
                       ("N" if sid == "cap_20261010_175227" else "UNK"))
                rows.append({
                    "sid": sid, "frame": fi, "cand": c["id"],
                    "decision": c["decision"], "ledger_prob": c["prob"],
                    "n": c["n"], "raw": c["raw_indices"], "label": lab,
                    "cov": round(max((h["coverage"] for h in hits),
                                     default=0.0), 4),
                    "pur": round(max((h["purity"] for h in hits),
                                     default=0.0), 4),
                })
    print("[S2] candidates=%d" % len(rows))

    out_path = os.path.join(C.WORK, "candidates_stage2.jsonl")
    fout = open(out_path, "w", encoding="utf-8")
    by_sf = {}
    for i, r in enumerate(rows):
        by_sf.setdefault((r["sid"], r["frame"]), []).append(i)

    mm_cache = {}
    done = 0
    for (sid, fi), idxs in sorted(by_sf.items()):
        xyz, inten, mm = C.read_frame_xyz(sid, fi, mm=mm_cache.get(sid))
        mm_cache[sid] = mm
        lev = C.level(xyz)
        batch = []
        for i in idxs:
            idx = np.asarray(rows[i]["raw"], dtype=np.int64)
            b = np.empty((len(idx), 4), dtype=np.float32)
            b[:, :3] = lev[idx]
            b[:, 3] = inten[idx]
            batch.append(b)
        cat = np.concatenate(batch, axis=0)
        counts = [len(b) for b in batch]
        with tempfile.NamedTemporaryFile(suffix=".npy", delete=False) as tf:
            np.save(tf, cat)
            tf_path = tf.name
        try:
            spec = json.dumps({"file": tf_path.replace("\\", "/"),
                               "counts": counts})
            proc = subprocess.run(["node", NODE_SCRIPT, spec],
                                  capture_output=True, text=True, timeout=600)
            if proc.returncode != 0:
                raise RuntimeError("node failed: %s" % proc.stderr[:400])
            res = json.loads(proc.stdout)
        finally:
            os.unlink(tf_path)
        for j, i in enumerate(idxs):
            r = rows[i]
            r["f51"] = [round(v, 6) for v in res["features"][j]]
            r["rf_prob"] = round(res["probs"][j], 6)
            r["x18"] = [round(float(v), 6) for v in
                        extract18(batch[j][:, :3], batch[j][:, 3],
                                  res["probs"][j])]
            r.pop("raw")
            fout.write(json.dumps(r, ensure_ascii=False) + "\n")
        done += len(idxs)
        if done % 2000 < len(idxs):
            print("[S2] %d/%d" % (done, len(rows)))
    fout.close()
    print("[S2] written %s (%d rows)" % (out_path, len(rows)))


if __name__ == "__main__":
    main()

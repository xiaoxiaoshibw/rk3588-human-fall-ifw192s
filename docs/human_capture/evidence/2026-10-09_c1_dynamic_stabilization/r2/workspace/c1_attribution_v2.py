#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""c1_attribution_v2.py — C1.2 完整逐帧漏检归因 + 轨迹稳定性 (含 far-session 变体 A/B/C).

与 c1_miss_attribution.py 区别:
- 变体 v_p (生产探针拓扑): BG→cluster→RF→Track
- 变体 v_raw_p (原始点云 不剔): 屡败矿但定点到 person ROI 照入源, 对 stand 共生_MASK 没意义
- 变体 v_airoi (AI-ROI): 原始点云 → AI-ROI 裁窗 → ≥30 点聚类 → RF → Trackage ≥3
- 变体 v_geom (几何注正则): BG→cluster→RF 默认, 但同步打"几何人形阈 (H, z_range, upright)" 标记
输出/重构: 报表 与 v1 分开 (attribution_v2/), 不改 v1 census 文件 (不污染对照).
"""
import json, math, os, sys, collections

EVID = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
ROOT = os.path.abspath(os.path.join(EVID, "..", "..", "..", ".."))
RAW = os.path.join(EVID, "workspace", "shadow_raw")
OUT = os.path.join(EVID, "attribution_v2")
sys.path.insert(0, os.path.join(ROOT, "pc_apps", "human_ml"))

import numpy as np
from frame_feature import extract_features

RF_V1 = json.load(open(os.path.join(ROOT, "pc_apps", "human_replay", "rf_person_v1.json"),
                       encoding="utf-8"))
SIX = ["cap_20261009_122637", "cap_20261009_122616", "cap_20261009_122700",
       "cap_20261009_121647", "cap_20261009_121622", "cap_20261009_121723"]
NAMES = dict(zip(SIX, ["男近", "男中", "男远", "女近", "女中", "女远"]))
LEVT = np.array([[0.893544, 0.0, 0.448975],
                 [-0.014337, 0.99949, 0.028533],
                 [-0.448746, -0.031932, 0.893089]])
LEVT_T = np.array([0.0, 0.0, 1.380286])
Z_LO, Z_HI = 0.1, 2.3
GATE_AIROI = 0.8          # AI-ROI 变体簇门
GEOMP = {"z_range_min": 0.80, "upright_min": 0.015}  # 人形几何判仪 (经验下限)
THRS = {"0.55": 0.55, "0.65": 0.65, "0.80": 0.80}


def rf_predict(fv):
    s = 0.0
    for t in RF_V1["trees"]:
        node = 0
        while True:
            fi = t["feature"][node]
            if fi == -2:
                break
            node = t["children_left"][node] if fv[fi] <= t["threshold"][node] \
                else t["children_right"][node]
        v = t["value"][node]
        tot = v[0] + v[1]
        if tot > 0:
            s += v[1] / tot
    return s / len(RF_V1["trees"])


def person_xy_median(sid):
    al = json.load(open(os.path.join(ROOT, "captures", "remote", sid, "ai_labels.json"),
                        encoding="utf-8"))
    xs, ys = [], []
    for v in al.get("frames", {}).values():
        if v.get("posture") not in (None, "none"):
            xs.append(v.get("x")); ys.append(v.get("y"))
    xs.sort(); ys.sort()
    return (xs[len(xs) // 2], ys[len(ys) // 2])


def run(sid):
    mem = np.memmap(os.path.join(ROOT, "captures", "remote", sid, "points.bin"),
                    dtype=np.uint8, mode="r").reshape(-1, 28).view(np.float32).reshape(-1, 7)
    meta = json.load(open(os.path.join(ROOT, "captures", "remote", sid, "meta.json"),
                          encoding="utf-8"))
    cl_by_frame = {}
    for ln in open(os.path.join(RAW, sid + ".clusters.jsonl"), encoding="utf-8"):
        o = json.loads(ln)
        cl_by_frame.setdefault(o["frame"], []).append(o)
    tracks = [json.loads(l) for l in open(os.path.join(RAW, sid + ".tracks.jsonl"),
                                          encoding="utf-8")]
    px, py = person_xy_median(sid)

    rows = []
    for tr in tracks:
        fi = tr["frame"]
        f = meta["frames"][fi]
        seg = mem[f["offset_points"]: f["offset_points"] + f["count_points"]]
        xyz = seg[:, :3].astype(np.float64)
        valid = np.isfinite(xyz).all(axis=1)
        lev = xyz[valid] @ LEVT.T + LEVT_T
        inten = seg[valid, 3]
        z = lev[:, 2]
        band = (z > Z_LO) & (z < Z_HI)
        lev, inten, z = lev[band], inten[band], z[band]

        # v_p: 从探针 jsonl (点不严格复算, 因为探针已在 shadow_raw)
        recs = cl_by_frame.get(fi, [])
        person_cl = None
        for r in recs:
            if r.get("rank", -1) >= 0 and math.hypot(r["cx"] - px, r["cy"] - py) <= 0.75:
                person_cl = r
                break
        pt = tr["per_thr"]["0.55"]
        vp = "shown" if pt["confirmed"] else (
            "track_age_lt3" if person_cl and person_cl.get("person_prob", 0) >= 0.55 else
            ("rf_reject" if person_cl else
             ("cluster_no_person" if recs and any(r.get("rank", -1) >= 0 for r in recs)
              else "bg_or_cluster_none")))

        # v_airoi: AI-ROI 裁窗 (x,y,r_xy,r 取自 ai_labels 当前帧, 缺中位)
        al = json.load(open(os.path.join(ROOT, "captures", "remote", sid, "ai_labels.json"),
                            encoding="utf-8")).get("frames", {})
        rec = al.get(str(fi), {})
        x_roi = rec.get("x", px); y_roi = rec.get("y", py); r_roi = rec.get("r_xy", 0.8)
        dxy = np.hypot(lev[:, 0] - x_roi, lev[:, 1] - y_roi)
        keep = (dxy <= r_roi) & (z >= 0.05) & (z <= 2.6)
        airoi_n = int(keep.sum())
        if airoi_n >= 30:
            fv = extract_features(np.column_stack([lev[keep], inten[keep]]).astype(np.float32))
            airoi_prob = float(rf_predict(fv))
        else:
            airoi_prob = None
        vai = ("shown" if (airoi_prob is not None and airoi_prob >= 0.55)
               else ("rf_reject" if airoi_prob is not None else "cluster_or_roi_fail"))

        # v_geom: 合成探针人簇的几何人形判仪 (用 z_range / upright 独立信息
        # — 从 leveled 全帧 ROI 重算, 比 jsonl 的 prob/q 多另外 2 个信号)
        zsel = lev[(dxy <= r_roi) & (z >= 0.05) & (z <= 2.6), 2]
        if zsel.size >= 30:
            p10, p90 = np.percentile(zsel, 10), np.percentile(zsel, 90)
            zr = p90 - p10
            up = ((zsel > 1.2) & (zsel < 2.2)).sum()
            mid = ((zsel >= 0.4) & (zsel < 1.2)).sum()
            upright = up / max(mid, 1)
            geomp = bool(zr >= GEOMP["z_range_min"] and upright >= GEOMP["upright_min"])
        else:
            geomp = None

        rows.append({
            "frame": fi,
            "vp": vp,
            "vai": vai, "airoi_prob": airoi_prob,
            "airoi_n": airoi_n, "geomp_ok": geomp,
            "person_prob": person_cl.get("person_prob") if person_cl else None,
        })
    return rows, (px, py)


def main():
    os.makedirs(OUT, exist_ok=True)
    sums = []
    for sid in SIX:
        rows, (px, py) = run(sid)
        n = len(rows)
        def cnt(key, val):
            return sum(1 for r in rows if r[key] == val)
        vp = collections.Counter(r["vp"] for r in rows)
        vai = collections.Counter(r["vai"] for r in rows)
        geo_ok = sum(1 for r in rows if r["geomp_ok"] is True)
        geo_no = sum(1 for r in rows if r["geomp_ok"] is False)
        rec = {
            "sid": NAMES[sid], "frames": n,
            "person_xy": [round(px, 3), round(py, 3)],
            "v_p": dict(vp), "v_airoi": dict(vai),
            "geomp_pass": geo_ok, "geomp_fail": geo_no,
            "vp_shown_pct": round(100.0 * vp.get("shown", 0) / n, 1),
            "vai_shown_pct": round(100.0 * vai.get("shown", 0) / n, 1),
        }
        sums.append(rec)
        json.dump(rows, open(os.path.join(OUT, sid + ".frames.jsonl"), "w", encoding="utf-8"),
                  ensure_ascii=False)
        print("[%s]" % sid, rec)
    with open(os.path.join(OUT, "summary.md"), "w", encoding="utf-8") as fh:
        fh.write("# C1.2 逐帧漏检归因 v2 (生产拓扑 vs AI-ROI 拓扑)\n\n")
        fh.write("| 会话 | 帧数 | **v_p**: 生产拓扑 显示/漏 (%) | **v_airoi**: AI-ROI拓扑 显示/漏 (%) | 几何人形通过 |\n|---|---|---|---|---|\n")
        for r in sums:
            vp, vai = r["v_p"], r["v_airoi"]
            fh.write("| %s | %d | shown %d (%.1f) / rf拒 %d / 无簇 %d | shown %d (%.1f) / rf拒 %d / ROI<30点 %d | %d/%d |\n" % (
                r["sid"], r["frames"],
                vp.get("shown", 0), r["vp_shown_pct"], vp.get("rf_reject", 0), vp.get("bg_or_cluster_none", 0),
                vai.get("shown", 0), r["vai_shown_pct"], vai.get("rf_reject", 0), vai.get("cluster_or_roi_fail", 0),
                r["geomp_pass"], r["frames"]))
        fh.write("\n人坐标 = ai_labels median; paar 是 per-frame attribution.\n")
    print("attribution_v2 →", OUT)


if __name__ == "__main__":
    main()

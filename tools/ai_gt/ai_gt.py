"""AI-GT 工具 v1：label / selfcheck / crosscheck / audit。

协议依据：docs/human_fall/evidence/2026-10-18_hfus_gt_protocol_01_r1/AI_GT_PROTOCOL_V1.md
PC 侧离线工具（stdlib + NumPy + Pillow 渲染）；板端不运行。
设计要点：
- 渲染输出中性视图（无类别着色、无算法叠加，仅淡网格），标签输入 schema 白名单（盲标保护）。
- selfcheck：合成场景（精确已知真值）→ 渲染 → 盲标 → 评分 → 误差包络；
  render 与 score 分离，truth.json 不打印 stdout，标注阶段不读取。
- 所有命令写 RUN_<mode>.json（argv/耗时/工具 SHA），stdout 仅输出计数器/结果摘要。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

# ---------- 冻结相机（PROTOCOL_V1.json） ----------
W, H = 1280, 720
VFOV_DEG, PITCH_DEG, CAM_Z = 40.0, 8.0, 1.6
F_PX = (H / 2.0) / math.tan(math.radians(VFOV_DEG) / 2.0)

FORBIDDEN_META_KEYS = {"candidates", "foreground", "predictions", "tracks", "skeleton",
                       "regions", "nodes", "overlay", "score", "labels"}


def default_camera() -> dict:
    p = math.radians(PITCH_DEG)
    return {
        "W": W, "H": H, "vfov_deg": VFOV_DEG, "pitch_down_deg": PITCH_DEG,
        "C": [0.0, 0.0, CAM_Z],
        "f": [math.cos(p), 0.0, -math.sin(p)],
        "r": [0.0, -1.0, 0.0],
        "u": [math.sin(p), 0.0, math.cos(p)],
        "f_px": F_PX,
    }


def _cam(cam: dict):
    return (np.asarray(cam["C"], float), np.asarray(cam["f"], float),
            np.asarray(cam["r"], float), np.asarray(cam["u"], float),
            float(cam["f_px"]), int(cam["W"]), int(cam["H"]))


def project(points, cam: dict):
    """世界点 -> 像素；返回 (u, v, ok)。"""
    c, f, r, up, fpx, w, h = _cam(cam)
    v = np.asarray(points, float) - c
    zc = v @ f
    xc = v @ r
    yc = v @ up
    ok = zc > 1e-9
    zs = np.where(ok, zc, 1.0)
    u = w / 2.0 + fpx * xc / zs
    vp = h / 2.0 - fpx * yc / zs
    return u, vp, ok


def ray_dir(cam: dict, u: float, v: float) -> np.ndarray:
    c, f, r, up, fpx, w, h = _cam(cam)
    d = f + r * ((u - w / 2.0) / fpx) + up * (-(v - h / 2.0) / fpx)
    return d / np.linalg.norm(d)


def nearest_point(points, cam: dict, u: float, v: float):
    """像素射线 -> 最近点索引与垂距（米）。"""
    pts = np.asarray(points, float)
    c, _, _, _, _, _, _ = _cam(cam)
    d = ray_dir(cam, u, v)
    rel = pts - c
    t = rel @ d
    perp = np.linalg.norm(rel - t[:, None] * d[None, :], axis=1)
    perp[(~np.isfinite(perp)) | (t <= 0)] = np.inf
    i = int(np.argmin(perp))
    return i, float(perp[i])


# ---------- 合成场景 ----------
def _floor(rng) -> np.ndarray:
    xs = np.arange(1.5, 9.5 + 1e-9, 0.2)
    ys = np.arange(-3.0, 3.0 + 1e-9, 0.2)
    gx, gy = np.meshgrid(xs, ys, indexing="ij")
    pts = np.column_stack([gx.ravel(), gy.ravel(), np.zeros(gx.size)])
    pts[:, :2] += rng.normal(0.0, 0.005, (len(pts), 2))
    return pts


def _cylinder(rng, cx, cy, n=700) -> np.ndarray:
    th = rng.uniform(0.0, 2.0 * math.pi, n)
    z = rng.uniform(0.05, 1.75, n)
    return np.column_stack([cx + 0.18 * np.cos(th), cy + 0.18 * np.sin(th), z])


def _box(rng, cx, cy, n=250, half=(0.30, 0.25, 0.27), zc=0.27) -> np.ndarray:
    pts = np.column_stack([rng.uniform(-half[0], half[0], n),
                           rng.uniform(-half[1], half[1], n),
                           rng.uniform(-half[2], half[2], n)])
    face = rng.integers(0, 6, n)
    axis = face // 2
    sign = np.where(face % 2 == 0, -1.0, 1.0)
    for a in range(3):
        m = axis == a
        pts[m, a] = sign[m] * half[a]
    pts[:, 0] += cx
    pts[:, 1] += cy
    pts[:, 2] += zc
    return pts


def make_case(rng, has_person: bool, adjacent: bool = False) -> dict:
    d = float(rng.uniform(4.0, 8.0))
    az = math.radians(float(rng.uniform(-25.0, 25.0)))
    cx, cy = d * math.cos(az), d * math.sin(az)
    parts = [_floor(rng)]
    truth = None
    if has_person:
        person = _cylinder(rng, cx, cy)
        truth = person.mean(axis=0)
        parts.append(person)
    want_furniture = (has_person and adjacent) or (float(rng.random()) < 0.6)
    if want_furniture:
        if has_person and adjacent:
            ang = float(rng.uniform(0.0, 2.0 * math.pi))
            fx, fy = cx + 0.7 * math.cos(ang), cy + 0.7 * math.sin(ang)
        else:
            fd = float(rng.uniform(4.0, 8.0))
            fa = math.radians(float(rng.uniform(-30.0, 30.0)))
            fx, fy = fd * math.cos(fa), fd * math.sin(fa)
            if has_person and math.hypot(fx - cx, fy - cy) < 1.2:
                fx, fy = cx + 1.5, cy + 1.2
        parts.append(_box(rng, fx, fy))
    pts = np.vstack(parts)
    return {"points": pts, "rows": np.arange(len(pts), dtype=np.int64), "truth": truth}


def build_suite(seed: int = 20261018) -> list:
    rng = np.random.default_rng(seed)
    kinds = ["person"] * 9 + ["adjacent"] + ["empty", "empty"]
    order = rng.permutation(len(kinds))
    cases = []
    for idx in order:
        kind = kinds[int(idx)]
        cases.append(make_case(rng, has_person=(kind != "empty"), adjacent=(kind == "adjacent")))
    return cases


def render(points, cam: dict, path: Path) -> None:
    u, v, ok = project(points, cam)
    im = Image.new("RGB", (W, H), (10, 12, 16))
    dr = ImageDraw.Draw(im)
    for x in range(0, W + 1, 100):
        dr.line([(x, 0), (x, H)], fill=(26, 30, 38))
    for y in range(0, H + 1, 100):
        dr.line([(0, y), (W, y)], fill=(26, 30, 38))
    for ui, vi in zip(u[ok], v[ok]):
        if -3.0 <= ui <= W + 3.0 and -3.0 <= vi <= H + 3.0:
            dr.ellipse([ui - 2, vi - 2, ui + 2, vi + 2], fill=(232, 236, 240))
    im.save(path, "PNG")


# ---------- 统计 ----------
def _stats(vals) -> dict | None:
    a = np.asarray(vals, float)
    if a.size == 0:
        return None
    return {"n": int(a.size), "min": float(a.min()), "p50": float(np.percentile(a, 50)),
            "p95": float(np.percentile(a, 95)), "max": float(a.max())}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _write_run(out: Path, mode: str, argv, t0: float, extra: dict | None = None) -> None:
    rec = {"mode": mode, "argv": list(argv), "seconds": round(time.time() - t0, 3),
           "tool_sha256": sha256_file(Path(__file__)), "python": "3.12"}
    if extra:
        rec.update(extra)
    (out / f"RUN_{mode}.json").write_text(json.dumps(rec, indent=1, ensure_ascii=False), encoding="utf-8")


# ---------- selfcheck ----------
def cmd_selfcheck_render(args) -> int:
    t0 = time.time()
    out = Path(args.out)
    (out / "renders").mkdir(parents=True, exist_ok=True)
    (out / "truth").mkdir(parents=True, exist_ok=True)
    cam = default_camera()
    (out / "camera.json").write_text(json.dumps(cam, indent=1), encoding="utf-8")
    suite = build_suite(args.seed)
    truth = {"seed": args.seed, "camera": cam, "cases": []}
    for i, case in enumerate(suite):
        name = f"case_{i:03d}"
        render(case["points"], cam, out / "renders" / f"{name}.png")
        t = case["truth"]
        entry = {"case": name, "has_person": t is not None}
        if t is not None:
            u, v, _ = project(np.asarray([t]), cam)
            rr = float(np.linalg.norm(np.asarray(t) - np.asarray(cam["C"], float)))
            dd = (np.asarray(t) - np.asarray(cam["C"], float)) / rr
            entry.update({"truth_xyz": [float(x) for x in t], "truth_px": [float(u[0]), float(v[0])],
                          "range_m": rr, "dir": [float(x) for x in dd]})
        truth["cases"].append(entry)
    tf = out / "truth" / "truth.json"
    tf.write_text(json.dumps(truth, indent=1), encoding="utf-8")
    (out / "truth" / "truth.sha256").write_text(sha256_file(tf) + "\n", encoding="utf-8")
    _write_run(out, "selfcheck_render", args._argv, t0, {"cases": len(suite), "seed": args.seed})
    print(json.dumps({"cases": len(suite), "renders": len(suite), "truth_written": True}, ensure_ascii=False))
    return 0


def _score_case(case: dict, pick: dict | None, cam: dict) -> dict:
    c = np.asarray(cam["C"], float)
    if not case["has_person"]:
        if pick is not None and pick.get("u") is not None:
            return {"case": case["case"], "status": "FP", "px": None, "angle_deg": None, "lateral_m": None}
        return {"case": case["case"], "status": "TN", "px": None, "angle_deg": None, "lateral_m": None}
    if pick is None or pick.get("u") is None:
        return {"case": case["case"], "status": "FN", "px": None, "angle_deg": None, "lateral_m": None}
    u, v = float(pick["u"]), float(pick["v"])
    tpx = case["truth_px"]
    px = math.hypot(u - tpx[0], v - tpx[1])
    rd = ray_dir(cam, u, v)
    td = np.asarray(case["dir"], float)
    ang = math.degrees(math.atan2(float(np.linalg.norm(np.cross(rd, td))), float(np.dot(rd, td))))
    lat = case["range_m"] * math.tan(math.radians(ang))
    return {"case": case["case"], "status": "TP", "px": px, "angle_deg": ang, "lateral_m": lat,
            "range_m": case["range_m"], "pick": [u, v], "truth_px": tpx}


def cmd_selfcheck_score(args) -> int:
    t0 = time.time()
    out = Path(args.out)
    truth = json.loads((out / "truth" / "truth.json").read_text(encoding="utf-8"))
    picks = json.loads(Path(args.picks).read_text(encoding="utf-8"))
    cam = truth["camera"]
    bycase = {p["case"]: p for p in picks["picks"]}
    rows = [_score_case(c, bycase.get(c["case"]), cam) for c in truth["cases"]]
    tp = [r for r in rows if r["status"] == "TP"]
    px = [r["px"] for r in tp]
    ang = [r["angle_deg"] for r in tp]
    lat = [r["lateral_m"] for r in tp]
    bins = [[4.0, 5.5], [5.5, 7.0], [7.0, 8.5]]
    by_range = []
    for lo, hi in bins:
        sel = [r for r in tp if lo <= r["range_m"] < hi]
        by_range.append({"bin_m": [lo, hi], "n": len(sel),
                         "px": _stats([r["px"] for r in sel]),
                         "lateral_m": _stats([r["lateral_m"] for r in sel])})
    scores = {"item": "HFUS-AI-GT-TOOL-01", "n_cases": len(rows),
              "tp": len(tp), "fn": sum(r["status"] == "FN" for r in rows),
              "fp": sum(r["status"] == "FP" for r in rows), "tn": sum(r["status"] == "TN" for r in rows),
              "px_err": _stats(px), "angle_deg": _stats(ang), "lateral_m": _stats(lat),
              "by_range": by_range, "per_case": rows,
              "annotator": picks.get("annotator"),
              "tool_sha256": sha256_file(Path(__file__)),
              "truth_sha256": sha256_file(out / "truth" / "truth.json"),
              "picks_sha256": sha256_file(Path(args.picks))}
    (out / "SELFCHECK.json").write_text(json.dumps(scores, indent=1), encoding="utf-8")
    env = {k: scores[k] for k in ("tp", "fn", "fp", "tn", "px_err", "angle_deg", "lateral_m", "by_range",
                                  "annotator", "tool_sha256", "truth_sha256", "picks_sha256")}
    env.update({"item": "HFUS-AI-GT-TOOL-01", "n_cases": len(rows), "small_sample": True,
                "not_confidence_interval": True,
                "render_spec": {"W": cam["W"], "H": cam["H"], "vfov_deg": cam["vfov_deg"],
                                "pitch_down_deg": cam["pitch_down_deg"], "neutral": True},
                "limits": ["12 例小样本，P95 接近最大值", "单标注者实例；跨模型 NOT_RUN",
                           "几何量（px/lateral）来自射线角度；lateral=range*tan(angle)",
                           "合成几何与真实人体不同，仅作工具链路检定"]})
    (out / "ENVELOPE.json").write_text(json.dumps(env, indent=1), encoding="utf-8")
    _write_run(out, "selfcheck_score", args._argv, t0, {"picks": str(args.picks)})
    print(json.dumps({"tp": scores["tp"], "fn": scores["fn"], "fp": scores["fp"], "tn": scores["tn"],
                      "px_p50": scores["px_err"]["p50"] if scores["px_err"] else None,
                      "envelope": "ENVELOPE.json"}, ensure_ascii=False))
    return 0


# ---------- label ----------
def cmd_label(args) -> int:
    points = np.load(args.points)
    rows = np.load(args.rows)
    meta = json.loads(Path(args.meta).read_text(encoding="utf-8"))
    bad = FORBIDDEN_META_KEYS & set(meta)
    if bad:
        raise SystemExit(f"blind 保护：meta 含管线输出字段 {sorted(bad)}")
    picks = json.loads(Path(args.picks).read_text(encoding="utf-8"))
    cam = json.loads(Path(args.camera).read_text(encoding="utf-8")) if args.camera else default_camera()
    labels = []
    for p in picks["picks"]:
        if p.get("u") is None:
            labels.append({"case": p["case"], "class": p.get("class", "person"), "absent": True})
            continue
        i, dist = nearest_point(points, cam, float(p["u"]), float(p["v"]))
        labels.append({"case": p["case"], "class": p.get("class", "person"),
                       "target_id": p.get("target_id", "main"),
                       "u": float(p["u"]), "v": float(p["v"]),
                       "xyz": [float(x) for x in points[i]], "source_row": int(rows[i]),
                       "nearest_dist_m": dist, "confidence": p.get("confidence")})
    out = {"schema": "ai_gt_labels_v1", "blind": True,
           "annotator": {"model_id": args.model_id, "model_version": args.model_version,
                         "prompt_sha256": args.prompt_sha},
           "render_sha256": args.render_sha,
           "inputs": {"sid": meta.get("sid"), "meta_sha256": meta.get("meta_sha256"),
                      "points_sha256": meta.get("points_sha256")},
           "created": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "labels": labels}
    Path(args.out).write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps({"labels": len(labels), "out": str(args.out)}, ensure_ascii=False))
    return 0


# ---------- crosscheck ----------
def _norm_entries(doc: dict) -> dict:
    out = {}
    for e in doc.get("labels", doc.get("picks", [])):
        absent = bool(e.get("absent")) or e.get("u") is None
        out[(e["case"], e.get("target_id", "main"))] = None if absent else (float(e["u"]), float(e["v"]))
    return out


def cmd_crosscheck(args) -> int:
    a = _norm_entries(json.loads(Path(args.a).read_text(encoding="utf-8")))
    b = _norm_entries(json.loads(Path(args.b).read_text(encoding="utf-8")))
    keys = sorted(set(a) | set(b))
    agree, dis = [], []
    for k in keys:
        pa, pb = a.get(k, "missing"), b.get(k, "missing")
        if pa == "missing" or pb == "missing":
            dis.append({"case": k[0], "target_id": k[1], "reason": "present_in_one_only"})
            continue
        if pa is None and pb is None:
            agree.append((k[0], k[1]))
        elif pa is None or pb is None:
            dis.append({"case": k[0], "target_id": k[1], "reason": "presence_mismatch"})
        else:
            dist = math.hypot(pa[0] - pb[0], pa[1] - pb[1])
            if dist <= args.tol_px:
                agree.append((k[0], k[1]))
            else:
                dis.append({"case": k[0], "target_id": k[1], "reason": "px_distance", "px": dist})
    rep = {"n_keys": len(keys), "agree": len(agree), "disagree": len(dis),
           "agree_rate": (len(agree) / len(keys)) if keys else None,
           "tol_px": args.tol_px, "disagreements": dis}
    Path(args.out).write_text(json.dumps(rep, indent=1), encoding="utf-8")
    print(json.dumps({k: rep[k] for k in ("n_keys", "agree", "disagree", "agree_rate")}, ensure_ascii=False))
    return 0


# ---------- audit ----------
def cmd_audit(args) -> int:
    doc = json.loads(Path(args.labels).read_text(encoding="utf-8"))
    flags = []
    if not doc.get("blind"):
        flags.append({"type": "not_blind"})
    if not (doc.get("annotator") or {}).get("model_id"):
        flags.append({"type": "missing_model_id"})
    if not doc.get("render_sha256"):
        flags.append({"type": "missing_render_sha256"})
    seen = set()
    per_target = {}
    for lbl in doc.get("labels", []):
        case = lbl.get("case", "?")
        tid = lbl.get("target_id", "main")
        key = (case, tid, lbl.get("frame"))
        if key in seen:
            flags.append({"type": "duplicate_target", "case": case, "target_id": tid})
        seen.add(key)
        if lbl.get("absent"):
            continue
        u, v = lbl.get("u"), lbl.get("v")
        if u is None or v is None:
            flags.append({"type": "missing_pick", "case": case, "target_id": tid})
            continue
        if not (0 <= u < W and 0 <= v < H):
            flags.append({"type": "out_of_bounds", "case": case, "target_id": tid, "uv": [u, v]})
        xyz = lbl.get("xyz")
        if xyz is None:
            flags.append({"type": "missing_xyz", "case": case, "target_id": tid})
        elif not all(np.isfinite(xyz)):
            flags.append({"type": "non_finite_xyz", "case": case, "target_id": tid})
        elif not (-0.2 <= xyz[2] <= 2.4):
            flags.append({"type": "z_placement", "case": case, "target_id": tid, "z": xyz[2]})
        if lbl.get("frame") is not None and xyz is not None:
            per_target.setdefault((case, tid), []).append((int(lbl["frame"]), np.asarray(xyz, float)))
    for key, seq in per_target.items():
        seq.sort()
        for (f0, p0), (f1, p1) in zip(seq, seq[1:]):
            step = float(np.linalg.norm(p1 - p0))
            if step > args.max_step_m:
                flags.append({"type": "jitter", "case": key[0], "target_id": key[1],
                              "frames": [f0, f1], "step_m": step})
    out = {"pass": len(flags) == 0, "n_flags": len(flags), "flags": flags, "max_step_m": args.max_step_m}
    Path(args.out).write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(json.dumps({"pass": out["pass"], "n_flags": out["n_flags"]}, ensure_ascii=False))
    return 0


# ---------- CLI ----------
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="ai_gt", description="AI-GT 工具 v1（label/selfcheck/crosscheck/audit）")
    sub = ap.add_subparsers(dest="mode", required=True)

    p = sub.add_parser("selfcheck", help="合成场景自检")
    ssub = p.add_subparsers(dest="stage", required=True)
    r = ssub.add_parser("render", help="生成套件渲染与 truth")
    r.add_argument("--out", required=True)
    r.add_argument("--seed", type=int, default=20261018)
    s = ssub.add_parser("score", help="读取 picks 评分并写包络")
    s.add_argument("--out", required=True)
    s.add_argument("--picks", required=True)

    p = sub.add_parser("label", help="生产标注：picks -> 世界坐标/源行标签")
    p.add_argument("--points", required=True)
    p.add_argument("--rows", required=True)
    p.add_argument("--picks", required=True)
    p.add_argument("--meta", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--camera")
    p.add_argument("--model-id", default="unset")
    p.add_argument("--model-version", default="unset")
    p.add_argument("--prompt-sha", default="unset")
    p.add_argument("--render-sha", default="unset")

    p = sub.add_parser("crosscheck", help="双标注一致率")
    p.add_argument("--a", required=True)
    p.add_argument("--b", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--tol-px", type=float, default=12.0)

    p = sub.add_parser("audit", help="标注一致性审查")
    p.add_argument("--labels", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--max-step-m", type=float, default=0.25)

    args = ap.parse_args(argv)
    args._argv = ["ai_gt"] + list(argv if argv is not None else sys.argv[1:])
    if args.mode == "selfcheck":
        return cmd_selfcheck_render(args) if args.stage == "render" else cmd_selfcheck_score(args)
    if args.mode == "label":
        return cmd_label(args)
    if args.mode == "crosscheck":
        return cmd_crosscheck(args)
    if args.mode == "audit":
        return cmd_audit(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

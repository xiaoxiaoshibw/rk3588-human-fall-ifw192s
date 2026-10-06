# -*- coding: utf-8 -*-
"""P3 只读旁路 ROI Selector A/B Probe（不进生产链路）。

对照：
  A = CURRENT v1  四象限最近格贪心（floor_detector.detect_floor_regions 逐字执行）。
  B = SHADOW      v1 同一连通组件内，把「每象限只取最近 1 格」放宽为「每象限最近 K 格候选池」，
                  组合枚举 → sep/cond 门（cond 复用 v3 定义）→ low-RMS 优先排序（v3 同哲学）。
                  SHADOW 只重排 v1 已认组件内的 clean cells，不引入新格、不改身份层。

下游：复用生产 leveling.freeze_domain 的掩码语义 + leveling_quality.compare。
产出：results.json / results_table.md / determinism.md（在 evidence 目录）。

只读：不写 captures、不改任何生产/测试文件。
"""
import itertools
import json
import sys
import time
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "pc_apps" / "human_replay"))

import numpy as np  # noqa: E402

import floor_detector as FD  # noqa: E402
import floor_sheet as FS  # noqa: E402
import floor_roi as FR  # noqa: E402
import leveling as W  # noqa: E402
import leveling_quality as Q  # noqa: E402

REMOTE = ROOT / "captures" / "remote"
EVID = ROOT / "docs" / "human_fall" / "evidence" / "2026-10-06_roi_ab_probe_r1"

GOLDENS = [
    ("cap_20261004_202456", 26.0, 0.0, "v1"),
    ("cap_20261004_203135", 26.0, 0.0, "v1"),
    ("cap_20261004_203349", 26.0, 0.0, "v1"),
    ("cap_20261002_223757", 26.0, 0.0, "v3"),  # control
]

QUADRANTS = ((.25, .25), (.75, .25), (.25, .75), (.75, .75))
SHADOW_K = 4                 # 每象限候选池大小（小固定常量）
SEP_GATE = .50               # 复用 v3 FINE_PROFILE["roi_min_separation_m"]
COND_GATE = .10              # 复用 v3 FINE_PROFILE["condition_min"]
DET_REPEATS = 20


# ---------------------------------------------------------------- 数据加载
def load_fit_frames(sid):
    """与 leveling.run_job auto 分支完全一致的 fit 帧抽取（剔除 3 个 holdout）。"""
    directory = REMOTE / sid
    meta = json.loads((directory / "meta.json").read_text(encoding="utf-8"))
    raw = np.memmap(directory / "points.bin", dtype="u1", mode="r")
    xyz = np.ndarray((meta["total_points"], 3), dtype="<f4", buffer=raw, strides=(28, 4))
    frames = meta["frames"]
    n = len(frames)
    excluded = {(n - 1) // 3, 2 * (n - 1) // 3, n - 1}
    chunks, ids = [], []
    for ordinal, frame in enumerate(frames):
        if ordinal in excluded:
            continue
        lo, count = frame["offset_points"], frame["count_points"]
        seg = xyz[lo:lo + count].astype(np.float64)
        valid = np.isfinite(seg).all(axis=1) & np.any(seg != 0, axis=1)
        chunks.append(seg[valid])
        ids.append(np.full(int(valid.sum()), ordinal, dtype="i4"))
    return meta, np.concatenate(chunks), np.concatenate(ids)


def load_all_frames(directory, meta):
    raw = np.memmap(directory / "points.bin", dtype="u1", mode="r")
    return np.ndarray((meta["total_points"], 3), dtype="<f4", buffer=raw, strides=(28, 4))


# ---------------------------------------------------------------- v1 内部截获
def run_current_v1(points, frame_ids, pitch, roll):
    """调生产 v1；同时用 patch 截获 clean dict 与选中组件，供 SHADOW 复用同一组件。

    截获点：floor_detector.components 被调用时的入参 floor_cells（dict）。
    v1 对每个水平面假设都调一次 components；我们记录最后一次成功返回前的
    clean/floor_cells 与最大组件。由于 v1 结构是「对每平面循环、首个满足跨度
    的组件即 return」，我们 patch components 记录其输入，取最后一次调用。
    """
    seen = {}

    real_components = FD.components

    def spy(cells):
        seen["floor_cells"] = cells
        return real_components(cells)

    with mock.patch.object(FD, "components", side_effect=spy):
        result = FD.detect_floor_regions(points, frame_ids, pitch, roll)

    floor_cells = seen["floor_cells"]
    # 复刻 v1 选中组件：最大且满足跨度门的 group
    groups = sorted(real_components(floor_cells), key=lambda g: (-len(g), min(g)))
    chosen_group = None
    for group in groups:
        xy = np.array(group)
        span = (np.ptp(xy, axis=0) + 1) * FD.PROFILE["cell_m"]
        if len(group) < FD.PROFILE["min_component_cells"] or span.min() < FD.PROFILE["min_component_axis_m"]:
            continue
        chosen_group = group
        break
    return result, floor_cells, chosen_group


# ---------------------------------------------------------------- 几何工具
def grid_condition(centers_xy):
    pts = np.asarray(centers_xy, dtype="f8")
    s = np.linalg.svd(pts - pts.mean(axis=0), compute_uv=False)
    return float(max(0., s[-1] / max(s[0], 1e-30)))


def pairwise_min_sep(centers_xy):
    pts = np.asarray(centers_xy, dtype="f8")
    d = np.hypot(pts[:, None, 0] - pts[None, :, 0], pts[:, None, 1] - pts[None, :, 1])
    np.fill_diagonal(d, np.inf)
    return float(d.min())


def regions_to_centers(regions):
    return np.array([[(r[0] + r[1]) / 2, (r[2] + r[3]) / 2] for r in regions])


# ---------------------------------------------------------------- SHADOW
def shadow_select(floor_cells, group, cell_m):
    """在 v1 选中组件 group 内，按 quadrant 候选池 + 组合 + v3 哲学选 4 格。

    返回 (regions, picked_keys, debug) 或 None（无可行组合）。
    """
    xy = np.array(group)
    centers_grid = (xy + .5) * cell_m
    lo, hi = centers_grid.min(axis=0), centers_grid.max(axis=0)

    # 每象限取距目标最近 K 格（同一组件内）
    pools = []
    for fx, fy in QUADRANTS:
        target = lo + (hi - lo) * [fx, fy]
        order = sorted(group,
                       key=lambda k: (float(np.linalg.norm((np.array(k) + .5) * cell_m - target)),
                                      -floor_cells[k]["min_frame_count"], k))
        pools.append(order[:SHADOW_K])

    best = None
    for combo in itertools.product(*pools):
        if len(set(combo)) != 4:
            continue  # 去重：4 个 ROI 必须是 4 个不同格
        centers = [(np.array(k) + .5) * cell_m for k in combo]
        sep = pairwise_min_sep(centers)
        if sep < SEP_GATE:
            continue
        cond = grid_condition(centers)
        if cond < COND_GATE:
            continue
        rms = [floor_cells[k]["local_rms_m"] for k in combo]
        # v3 哲学字典序：max_rms↓ mean_rms↓ cond↑ sep↑，确定性 tie-break 用 key
        key = (-max(rms), -sum(rms) / 4., cond, sep, tuple(sorted(combo)))
        if best is None or key > best[0]:
            best = (key, combo)
    if best is None:
        return None
    combo = best[1]
    picked = sorted(combo)
    regions = [[k[0] * cell_m, (k[0] + 1) * cell_m, k[1] * cell_m, (k[1] + 1) * cell_m]
               for k in picked]
    debug = {"combo_keys_sorted": [list(map(int, k)) for k in picked],
             "pool_sizes": [len(p) for p in pools],
             "combos_enumerated": int(np.prod([len(p) for p in pools]))}
    return regions, picked, debug


# ---------------------------------------------------------------- downstream
def evaluate(sid, meta, regions, pitch, roll):
    """把 4 个 display 系 ROI 用生产 freeze_domain 掩码语义 + compare 评估。

    返回 {roi_geometry, domain_geometry, estimators, pairwise, holdout, recommended}。
    """
    directory = REMOTE / sid
    xyz = load_all_frames(directory, meta)
    initial = Q.rotation(pitch, roll)
    anchor = initial[2].copy()
    frames = meta["frames"]
    n = len(frames)
    held_indices = [(n - 1) // 3, 2 * (n - 1) // 3, n - 1]

    fit_pts, fit_codes, held = [], [], []
    for ordinal, frame in enumerate(frames):
        lo, count = frame["offset_points"], frame["count_points"]
        seg = xyz[lo:lo + count].astype(np.float64)
        valid = np.isfinite(seg).all(axis=1) & np.any(seg != 0, axis=1)
        seg = seg[valid]
        display = seg @ initial.T
        membership = np.zeros(len(seg), dtype=np.uint8)
        for region, (xl, xh, yl, yh) in enumerate(regions, 1):
            mask = ((display[:, 0] >= xl) & (display[:, 0] < xh)
                    & (display[:, 1] >= yl) & (display[:, 1] < yh))
            membership[mask] = region
        keep = membership > 0
        if ordinal in held_indices:
            held.append({"ordinal": ordinal, "points": seg[keep], "regions": membership[keep]})
        else:
            fit_pts.append(seg[keep])
            fit_codes.append(membership[keep])
    points = np.concatenate(fit_pts)
    codes = np.concatenate(fit_codes)

    comparison = Q.compare(points, codes, held, anchor)

    centers = regions_to_centers(regions)
    est = comparison["estimators"]
    pairwise = comparison["pairwise"]
    # holdout worst region rms
    worst_holdout = None
    for e in est.values():
        for h in e.get("holdouts", []):
                for rk, st in h["regions"].items():
                    if st["rms_m"] is not None and (worst_holdout is None or st["rms_m"] > worst_holdout):
                        worst_holdout = st["rms_m"]
    out = {
        "regions": [list(map(float, r)) for r in regions],
        "centers": [list(map(float, c)) for c in centers],
        "min_pairwise_sep_m": pairwise_min_sep(centers),
        "condition": grid_condition(centers),
        "fit_points": int(len(points)),
        "region_counts": {str(i): int(np.count_nonzero(codes == i)) for i in range(1, 5)},
        "domain_geometry": comparison["domain_geometry"],
        "recommended": comparison["recommended"],
        "consensus": comparison["consensus"],
        "pairwise": [{"a": p["a"], "b": p["b"], "angle_deg": p["angle_deg"],
                      "offset_gap_m": p["offset_gap_m"], "status": p["status"]} for p in pairwise],
        "estimators": {name: {
            "valid": e["valid"], "reject_reasons": e["reject_reasons"],
            "pitch_deg": e["pitch_deg"], "roll_deg": e["roll_deg"],
            "offset_source_m": e["offset_source_m"],
            "full_rms_m": e["full"]["rms_m"] if e.get("full") else None,
            "full_p95_m": e["full"]["p95_m"] if e.get("full") else None,
            "full_support": e["full"]["support_ratio"] if e.get("full") else None,
        } for name, e in est.items()},
        "holdout_worst_region_rms_m": worst_holdout,
        "valid_estimator_count": sum(1 for e in est.values() if e["valid"]),
    }
    return out


# ---------------------------------------------------------------- 主流程
def main():
    EVID.mkdir(parents=True, exist_ok=True)
    results = {}
    determinism = {}

    for sid, pitch, roll, layer in GOLDENS:
        t0 = time.monotonic()
        meta, points, frame_ids = load_fit_frames(sid)

        # ---- A = CURRENT v1（生产逐字） ----
        cur = {"layer_expected": layer}
        try:
            v1_result, floor_cells, group = run_current_v1(points, frame_ids, pitch, roll)
            cur["v1_ok"] = True
            cur["clean_cells"] = len(floor_cells)
            cur["component_cells"] = len(group)
            cur["v1_regions"] = [list(map(float, r)) for r in v1_result["regions"]]
        except ValueError as exc:
            cur["v1_ok"] = False
            cur["v1_error"] = str(exc)
            v1_result = None

        # 223757 control：确认生产语义 v1/v2 fail → v3
        if layer == "v3":
            try:
                FS.detect_floor_regions_v2(points, frame_ids, pitch, roll)
                cur["v2_result"] = "unexpected_success"
            except ValueError as exc:
                cur["v2_result"] = str(exc)[:80]
            v3 = FR.detect_floor_regions_v3(points, frame_ids, pitch, roll)
            cur["v3_kind"] = v3["candidate"]["kind"]
            cur["v3_eval"] = evaluate(sid, meta, v3["regions"], pitch, roll)
            results[sid] = {"role": "control_v3", "current": cur,
                            "seconds": round(time.monotonic() - t0, 2)}
            continue

        # ---- 三个 v1 session：A/B 对照 ----
        if not v1_result or not cur["v1_ok"]:
            results[sid] = {"role": "v1_ab", "current": cur, "shadow": None,
                            "note": "v1 未成功，无 A/B 可比", "seconds": round(time.monotonic() - t0, 2)}
            continue

        cur_regions = v1_result["regions"]
        cur_eval = evaluate(sid, meta, cur_regions, pitch, roll)

        # CURRENT v1 ROI 的 local rms（来自 floor_cells）
        cell_m = FD.PROFILE["cell_m"]
        cur_keys = [tuple((int(round(r[0] / cell_m)), int(round(r[2] / cell_m)))) for r in cur_regions]
        cur_rms = [floor_cells[k]["local_rms_m"] for k in cur_keys]
        cur_eval["local_rms"] = [float(x) for x in cur_rms]
        cur_eval["max_rms"] = float(max(cur_rms))
        cur_eval["mean_rms"] = float(sum(cur_rms) / len(cur_rms))
        cur_eval["min_frame_count"] = int(min(floor_cells[k]["min_frame_count"] for k in cur_keys))
        cur["eval"] = cur_eval

        # ---- B = SHADOW ----
        sh = shadow_select(floor_cells, group, cell_m)
        shadow_rec = {"K": SHADOW_K, "sep_gate": SEP_GATE, "cond_gate": COND_GATE}
        if sh is None:
            shadow_rec["ok"] = False
            shadow_rec["note"] = "无可行组合（sep/cond 门未过）"
        else:
            sh_regions, sh_keys, sh_debug = sh
            sh_eval = evaluate(sid, meta, sh_regions, pitch, roll)
            sh_rms = [floor_cells[k]["local_rms_m"] for k in sh_keys]
            sh_eval["local_rms"] = [float(x) for x in sh_rms]
            sh_eval["max_rms"] = float(max(sh_rms))
            sh_eval["mean_rms"] = float(sum(sh_rms) / len(sh_rms))
            sh_eval["min_frame_count"] = int(min(floor_cells[k]["min_frame_count"] for k in sh_keys))
            shadow_rec.update(ok=True, eval=sh_eval, debug=sh_debug,
                              changed=(sorted(map(list, cur_regions)) != sorted(map(list, sh_regions))))

        results[sid] = {"role": "v1_ab", "current": cur, "shadow": shadow_rec,
                        "seconds": round(time.monotonic() - t0, 2)}

        # ---- determinism：重跑 CURRENT+SHADOW DET_REPEATS 次 ----
        sig_cur = json.dumps(cur_eval["regions"], sort_keys=True)
        sig_sh = json.dumps(shadow_rec.get("eval", {}).get("regions"), sort_keys=True) if shadow_rec.get("ok") else None
        stable = True
        for _ in range(DET_REPEATS):
            r2, fc2, g2 = run_current_v1(points, frame_ids, pitch, roll)
            if json.dumps(evaluate(sid, meta, r2["regions"], pitch, roll)["regions"], sort_keys=True) != sig_cur:
                stable = False
            if shadow_rec.get("ok"):
                s2 = shadow_select(fc2, g2, cell_m)
                if json.dumps(s2[0], sort_keys=True) != sig_sh:
                    stable = False
        determinism[sid] = {"repeats": DET_REPEATS, "byte_stable": stable}

    # ---- 写盘 ----
    payload = {"goldens": results, "determinism": determinism,
               "params": {"SHADOW_K": SHADOW_K, "SEP_GATE": SEP_GATE, "COND_GATE": COND_GATE}}
    (EVID / "04_results.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1),
                                          encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()

"""GL-S02 follow-up probe (read-only): is the region-2 deviation physical, sensor angular bias, or pipeline?

Criterion 1 (moving object): per-frame z-extent of the R2 box -> stable means static.
Criterion 2 (angular column vs spatial strip): bucket deviations by azimuth/range.
    Angular bias -> deviation follows a beam column everywhere.
    Physical     -> deviation lives in one spatial vicinity only.
Criterion 3 (cross-session): same box region in cap_20261004_203135 (r1 CENTER is empty there)
    -> if the beam column is bent there too, sensor; if flat there, physical in 223757.
"""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "pc_apps" / "human_replay"))
from leveling_quality import rotation  # noqa: E402

OUT = Path(__file__).resolve().parent
R2 = (0.9, 1.05, -0.45, -0.3)  # display box (x lo/hi, y lo/hi) selected as region 2
FIT_EXCLUDE = lambda n: {(n - 1) // 3, 2 * (n - 1) // 3, n - 1}


def load(sid, fit_only=True):
    directory = ROOT / "captures" / "remote" / sid
    meta = json.loads((directory / "meta.json").read_text(encoding="utf-8"))
    raw = np.memmap(directory / "points.bin", dtype="u1", mode="r")
    xyz = np.ndarray((meta["total_points"], 3), dtype="<f4", buffer=raw, strides=(28, 4))
    frames = meta["frames"]
    excluded = FIT_EXCLUDE(len(frames)) if fit_only else set()
    chunks, ids = [], []
    for ordinal, frame in enumerate(frames):
        if ordinal in excluded:
            continue
        lo, count = frame["offset_points"], frame["count_points"]
        seg = xyz[lo:lo + count].astype("f8")
        valid = np.isfinite(seg).all(axis=1) & np.any(seg != 0, axis=1)
        chunks.append(seg[valid])
        ids.append(np.full(int(valid.sum()), ordinal, dtype="i4"))
    return np.concatenate(chunks), np.concatenate(ids)


def sheet_plane(sid):
    from floor_sheet import _discover_planes
    work, ids = load(sid)
    initial = rotation(26., 0.)
    planes = _discover_planes(work, initial[2])
    chosen = max(planes, key=lambda p: p["offset_m"])
    return np.asarray(chosen["normal"]), chosen["offset_m"], work, ids


def box_stats(sid, normal, offset):
    work, ids = load(sid)
    display = work @ rotation(26., 0.).T
    xl, xh, yl, yh = R2
    inside = ((display[:, 0] >= xl) & (display[:, 0] < xh)
              & (display[:, 1] >= yl) & (display[:, 1] < yh))
    resid = (work @ normal + offset)[inside]
    frames = ids[inside]
    per_frame = []
    for f in np.unique(frames):
        r = resid[frames == f]
        if len(r):
            per_frame.append([int(f), float(np.median(r)), float(np.max(r) - np.min(r))])
    return {"n_points": int(len(resid)), "n_frames": int(len(per_frame)),
            "median_resid_m": float(np.median(resid)),
            "p95_abs_m": float(np.percentile(np.abs(resid), 95)),
            "per_frame_median_span_m": [round(max(fr[2] for fr in per_frame), 4),
                                        round(float(np.percentile([fr[2] for fr in per_frame], 95)), 4)],
            "frame_medians_sample": per_frame[:3] + per_frame[-3:]}


def angular_map(sid, plane_cache):
    from floor_sheet import _discover_planes  # noqa: F401
    normal, offset, work, ids = plane_cache
    display = work @ rotation(26., 0.).T
    resid = np.abs(work @ normal + offset)
    near = resid <= .08
    w, d = work[near], display[near]
    az = np.degrees(np.arctan2(w[:, 2], w[:, 0]))
    rg = np.hypot(d[:, 0], d[:, 1])
    dev = np.abs(w @ normal + offset)  # signed would hide sign; use signed below
    signed = w @ normal + offset
    med = np.median(signed)
    signed = signed - med  # recenter so map is relative to local plane trend
    grid = np.full((9, 6), np.nan)
    for i, alo in enumerate(range(-135, 135, 30)):
        for j, rlo in enumerate(np.arange(.8, 2.6, .3)):
            m = (az >= alo) & (az < alo + 30) & (rg >= rlo) & (rg < rlo + .3)
            if m.sum() >= 30:
                grid[i, j] = float(np.median(signed[m]))
    return {"grid_1000x_median_signed_m": grid.tolist(),
            "azimuth_edges_deg": list(range(-135, 135, 30)),
            "range_edges_m": list(np.arange(.8, 2.6, .3))}


def main():
    normal, offset, work, ids = sheet_plane("cap_20261002_223757")
    r2 = box_stats("cap_20261002_223757", normal, offset)
    ang = angular_map("cap_20261002_223757", (normal, offset, work, ids))
    r1 = box_stats("cap_20261002_223757", normal, offset | 0) if False else box_stats(
        "cap_20261002_223757", normal, offset)  # placeholder; unchanged
    # cross-session: same DISPLAY box in 203135 where r1 says empty
    n31, o31, w31, i31 = sheet_plane("cap_20261004_203135")
    r2_31 = box_stats("cap_20261004_203135", n31, o31)
    out = {"r2_box_223757": r2, "azimuth_range_map_223757_recentred": ang,
           "same_box_203135_empty_expectation": r2_31,
           "note": "R1 in 223757 is (0.3..0.45, 0.75..0.9) display; deviation map recentred by local median."}
    (OUT / "10_r2_rootcause_probe.json").write_text(json.dumps(out, ensure_ascii=False, indent=1),
                                                    encoding="utf-8")
    print(json.dumps({k: (v if k != "azimuth_range_map_223757_recentred" else {"grid_rows": len(v)})
                      for k, v in out.items()}, ensure_ascii=False, indent=1), flush=True)


if __name__ == "__main__":
    main()

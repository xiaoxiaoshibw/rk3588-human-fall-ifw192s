"""Independent positive/usefulness + baseline parity probe (read-only)."""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(r"D:/Code/ldiar")
PACKAGE = ROOT / "src/human_fall_detection"
RESEARCH = ROOT / "docs/human_fall/evidence/2026-10-03_gl_i04_r1/research_01"
sys.path[:0] = [str(PACKAGE), str(PACKAGE / "scripts"), str(RESEARCH)]
from core import ground as g
from search_prototype import search


def scene(kind, seed, permute):
    rng = np.random.RandomState(seed)
    n = 500
    xy = rng.uniform(-3, 3, (n, 2))
    z = np.full(n, -1.4)
    if kind == "noise":
        z += rng.normal(0, 0.008, n)
    elif kind == "high_noise":
        z += rng.normal(0, 0.035, n)
    fit = np.column_stack([xy, z])
    if permute:
        fit = fit[rng.permutation(n)]
    holds = [np.column_stack([rng.uniform(-3, 3, (80, 2)), np.full(80, -1.4)]) for _ in range(3)]
    points = np.vstack([fit] + holds)
    regions = [{"region_id": "v%d" % i, "frame_group": "hold%d" % i,
                "indices": list(range(n + 80 * i, n + 80 * (i + 1)))} for i in range(3)]
    return points, np.arange(n), regions


out = {}
for kind in ("clean", "noise", "high_noise"):
    rows = {}
    for seed in (7, 19, 41):
        for permute in (False, True):
            points, fit_rows, regions = scene(kind, seed, permute)
            st = g.resolve_constrained_settings({"seed": seed, "spatial_cell_m": .05,
                                                 "max_points_per_cell": 8})
            base = g.fit_ground_plane_constrained(points, st, "fixture", np.array([0., 0., 1.]),
                                                  (.5, 2.), fit_rows, "fit", regions)
            proto = search(points, fit_rows, np.array([0., 0., 1.]), (.5, 2.), st)
            rows["seed%d_perm%s" % (seed, permute)] = {
                "baseline_status": base["status"], "prototype": proto["status"],
                "closed": proto["status"] == "seen_sequence_closed_single",
                "peak_retained": proto["counts"]["peak_retained"]}
    statuses = sorted({v["prototype"] for v in rows.values()})
    base_statuses = sorted({v["baseline_status"] for v in rows.values()})
    out[kind] = {"cases": rows, "prototype_statuses": statuses, "baseline_statuses": base_statuses}

out["ok"] = (out["clean"]["prototype_statuses"] == ["seen_sequence_closed_single"]
             and out["noise"]["prototype_statuses"] == ["seen_sequence_closed_single"]
             and out["high_noise"]["prototype_statuses"] == ["unresolved"]
             and "valid" in out["clean"]["baseline_statuses"]
             and "valid" in out["noise"]["baseline_statuses"])
print(json.dumps(out, indent=2))
print("\nALL_OK:", out["ok"])

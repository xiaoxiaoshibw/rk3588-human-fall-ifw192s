"""Independent edge probes: empty frames, hand residual stats, pca degeneracy."""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(r"D:/Code/ldiar")
PACKAGE = ROOT / "src/human_fall_detection"
TESTS = PACKAGE / "tests"
for p in (str(PACKAGE), str(TESTS)):
    if p not in sys.path:
        sys.path.insert(0, p)
from test_gli02_candidate import BOUNDS
from core.ground_diagnostics import observe_boxes, pca_plane, residual_stats

out = {}

# --- empty frame explicitly count0/null, no cross-frame pooling -------------
points = np.array([[0, 0, 0.0], [0.25, 0.25, 0.1], [-0.001, 0, -0.1], [1, 1, 0.0]])
manifest = {"points": {"shape": [4, 3]}, "frame_groups": {
    "a": {"rows": [0, 3], "ordinal": 0, "seq": 10},
    "empty": {"rows": [3, 3], "ordinal": 1, "seq": 11},
    "b": {"rows": [3, 4], "ordinal": 2, "seq": 12}}}
plane = {"normal": [0.0, 0.0, 1.0], "offset_m": 0.0}
r1, sc1, _ = observe_boxes(points, manifest, [("FIT", BOUNDS)], plane, 1)
r99, sc99, _ = observe_boxes(points, manifest, [("FIT", BOUNDS)], plane, 99)
out["empty_frame_and_display_invariance"] = {
    "empty_count": r1[1]["stats"]["count"], "empty_rms": r1[1]["stats"]["rms_m"],
    "empty_reason": r1[1]["stats"]["reason"], "empty_sidecar_rows": len([s for s in sc1 if s["frame_group"] == "empty"]),
    "stats_budget_invariant": [r["stats"] for r in r1] == [r["stats"] for r in r99],
    "display_count_budget1": [r["display_count"] for r in r1],
    "sidecar_map": [(s["pooled_row"], s["frame_row"], s["frame_ordinal"], s["seq"]) for s in sc1],
    "ok": r1[1]["stats"]["count"] == 0 and r1[1]["stats"]["rms_m"] is None
          and r1[1]["stats"]["reason"] == "no_finite_selected_points"
          and [r["stats"] for r in r1] == [r["stats"] for r in r99]
          and len(sc1) == 4}

# --- hand residual stats ----------------------------------------------------
res = residual_stats([[0, 0, -0.1], [0, 0, 0], [0, 0, 0.1], [float("nan"), 0, 0]], [0, 0, 1], 0)
out["hand_residual_stats"] = {
    "stats": {k: res[k] for k in ("count", "finite_count", "nonfinite_count", "zero_count",
                                  "rms_m", "p95_m", "signed_median_m", "signed_min_m",
                                  "signed_max_m", "support_count", "support_fraction",
                                  "high_tail_count", "low_tail_count")},
    "ok": res["count"] == 4 and res["finite_count"] == 3 and res["nonfinite_count"] == 1
          and res["zero_count"] == 1 and abs(res["rms_m"] - np.sqrt(0.02 / 3)) < 1e-15
          and abs(res["p95_m"] - 0.1) < 1e-15 and res["signed_median_m"] == 0
          and (res["low_tail_count"], res["high_tail_count"], res["support_count"]) == (1, 1, 1)}
empty = residual_stats(np.empty((0, 3)), [0, 0, 1], 1)
out["empty_residual_stats"] = {"rms": empty["rms_m"], "reason": empty["reason"],
                               "ok": empty["rms_m"] is None and empty["reason"] == "no_finite_selected_points"}

# --- pca degenerate ---------------------------------------------------------
line = np.column_stack([np.linspace(-1, 1, 10), np.zeros(10), np.zeros(10)])
deg_raised = False
try:
    pca_plane(line, [0, 0, 1])
except ValueError:
    deg_raised = True
out["pca_collinear_refused"] = {"raised": deg_raised, "ok": deg_raised}

out["ok"] = all(v["ok"] for k, v in out.items() if isinstance(v, dict) and "ok" in v)
print(json.dumps(out, indent=2, default=str))
print("\nALL_OK:", out["ok"])

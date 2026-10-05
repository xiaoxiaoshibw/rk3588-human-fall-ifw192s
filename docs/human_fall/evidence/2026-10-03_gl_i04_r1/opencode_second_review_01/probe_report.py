"""Independent reviewer recomputation from the real rerun report (read-only)."""
import collections
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(r"D:/Code/ldiar")
PACKAGE = ROOT / "src/human_fall_detection"
sys.path.insert(0, str(PACKAGE))
from core.capture_input import load_adapted, select_group_region

RUN = ROOT / "docs/human_fall/evidence/2026-10-03_gl_i04_r1"
OUT = RUN / "opencode_second_review_01/12_real_final_rerun"
report = json.loads((OUT / "diagnostic.json").read_text(encoding="utf-8"))
manifest, points = load_adapted(str(
    ROOT / "docs/human_fall/evidence/2026-10-03_gl_i02_r1/08_real/real_candidate.adapted.npz"))
results = {}

# --- L02 rotation conditions ------------------------------------------------
rot = report["rotation"]
R = np.asarray(rot["R_source_to_world"])
inv = np.asarray(rot["world_up_expressed_in_source_R_transpose"])
z = np.array([0.0, 0.0, 1.0])
results["L02_rotation"] = {
    "R_times_source_z": rot["R_times_source_z_in_world"],
    "R_T_worldz": inv.tolist(),
    "R_is_Ry_plus90": np.allclose(R, [[0, 0, 1], [0, 1, 0], [-1, 0, 0]]),
    "inverse_recovers_world_z": np.allclose(R @ inv, z),
    "extrinsic_status": report["extrinsic"]["status"],
    "physical_verified": report["physical_verified"],
    "ok": np.allclose(R, [[0, 0, 1], [0, 1, 0], [-1, 0, 0]])
          and np.allclose(R @ inv, z) and report["extrinsic"]["status"] == "unknown"
          and report["physical_verified"] is False}

# --- L05 frozen vs replay parity and early returns --------------------------
parity = {}
for exp in report["experiments"]:
    a, r = exp["actual_frozen_fit"], exp["replay"]
    parity[exp["label"]] = {
        "status": a["status"], "reason": a["reason"],
        "sampled_equal": a["sampled_fit_count"] == r["sampled_fit_count"],
        "raw_equal": a["raw_candidates"] == r["raw_candidates"],
        "cand_equal": a["candidates"] == r["candidates"],
        "trunc_equal": a.get("competition_truncated", False) == r["competition_truncated"],
        "native_validation": exp["native_validation_executed"],
        "replay_angle_rejects": r["counters"].get("angle", 0),
        "replay_degenerate": r["counters"].get("sample_area", 0) + r["counters"].get("sample_separation", 0),
        "degenerate_samples": a["degenerate_samples"],
    }
approved = parity["approved"]
negx = parity["WHAT_IF_negative_X"]
results["L05_frozen_replay_parity"] = {
    "cases": parity,
    "approved_degenerate_but_angle_rejections": approved["reason"] == "ground_degenerate"
        and approved["replay_angle_rejects"] > 0,
    "no_native_validation_real": not any(p["native_validation"] for p in parity.values()),
    "ok": all(p["sampled_equal"] and p["raw_equal"] and p["cand_equal"] and p["trunc_equal"]
              for p in parity.values())
          and approved["reason"] == "ground_degenerate" and approved["replay_angle_rejects"] > 0
          and negx["reason"] == "ground_competition_unresolved"
          and not any(p["native_validation"] for p in parity.values())}

# --- L03/L04 independent sidecar + box/frame recomputation ------------------
draft = report["approved_draft"]
boxes = {"FIT": draft["fit_region"]["bounds"]}
boxes.update({r["region_id"]: r["bounds"] for r in draft["validation_regions"]})
normal = np.asarray(report["observation_plane"]["normal"])
offset = report["observation_plane"]["offset_m"]
thr = report["support_tail_threshold_m"]
threshold = thr

mapped = collections.defaultdict(list)
sidecar_rows = 0
nonfinite = 0
with (OUT / "source_indices.jsonl").open(encoding="utf-8") as fh:
    for line in fh:
        row = json.loads(line)
        sidecar_rows += 1
        g = manifest["frame_groups"][row["frame_group"]]
        assert g["rows"][0] <= row["pooled_row"] < g["rows"][1]
        assert row["frame_row"] == row["pooled_row"] - g["rows"][0]
        assert row["frame_ordinal"] == g["ordinal"] and row["seq"] == g["seq"]
        if row["source_xyz_m"] is None:
            nonfinite += 1
        else:
            assert row["source_xyz_m"] == points[row["pooled_row"]].astype(float).tolist()
        mapped[(row["box"], row["frame_group"])].append(row)

frame_groups = list(manifest["frame_groups"])
records = report["box_frame_records"]
assert len(records) == 4 * len(frame_groups) == 356
stat_mismatch = []
bin_mismatch = []
display_mismatch = []
empty = 0
for rec in records:
    key = (rec["box"], rec["frame_group"])
    selector = dict(boxes[key[0]], frame_group=key[1])
    rows = select_group_region(points, manifest, selector)
    if rows.tolist() != [r["pooled_row"] for r in mapped[key]]:
        stat_mismatch.append(("rowmap", key))
        continue
    s = rec["stats"]
    assert len(rows) == s["count"]
    assert sum(c["stats"]["count"] for c in rec["source_xyz_bins"]) == len(rows)
    if len(rows):
        signed = points[rows].astype(float) @ normal + offset
        exp_rms = float(np.sqrt(np.mean(signed ** 2)))
        exp_p95 = float(np.percentile(np.abs(signed), 95))
        exp_sup = int(np.count_nonzero(np.abs(signed) <= threshold))
        if not (abs(s["rms_m"] - exp_rms) < 1e-12 and abs(s["p95_m"] - exp_p95) < 1e-12
                and s["support_count"] == exp_sup):
            stat_mismatch.append(key)
        if rec["display_count"] != len(rec["display_rows"]) or \
                not set(rec["display_rows"]).issubset({r["pooled_row"] for r in mapped[key]}):
            display_mismatch.append(key)
        cells = {}
        for r in rows.tolist():
            xyz = points[r].astype(float)
            cell = tuple(np.floor(xyz / 0.25).astype(np.int64).tolist())
            cells[cell] = cells.get(cell, 0) + 1
        got = {tuple(c["cell"]): c["stats"]["count"] for c in rec["source_xyz_bins"]}
        if got != cells:
            bin_mismatch.append(key)
    else:
        empty += 1
        if s["rms_m"] is not None or s["count"] != 0:
            stat_mismatch.append(("empty", key))

results["L03_L04_recompute"] = {
    "sidecar_rows": sidecar_rows, "expected_sidecar": report["sidecar_count"],
    "nonfinite_sidecar": nonfinite, "records": len(records), "empty_records": empty,
    "stat_mismatches": stat_mismatch[:10], "display_mismatches": display_mismatch[:10],
    "bin_mismatches": bin_mismatch[:10],
    "ok": sidecar_rows == report["sidecar_count"] == 351255 and not stat_mismatch
          and not display_mismatch and not bin_mismatch}

# --- display invariance: budget-independent statistics ----------------------
results["L04_display_invariance"] = {
    "budget": report["display_budget_per_box_frame"],
    "display_count_le_budget": all(r["display_count"] <= report["display_budget_per_box_frame"]
                                   for r in records),
    "one_render_rule_per_record": all(r["display_rule"].startswith("source-row stride")
                                      for r in records),
    "ok": all(r["display_count"] <= report["display_budget_per_box_frame"] for r in records)}

# --- temporal reproducibility ----------------------------------------------
temporal = report["temporal"]
results["L04_temporal"] = {
    "temporal": temporal,
    "ok": all(v["nonempty_frames"] > 0 for v in temporal.values())}

print(json.dumps(results, indent=2, default=str))
print("\nALL_OK:", all(v.get("ok", True) for v in results.values()))

#!/usr/bin/env python3
"""Exclusive offline geometry diagnostic; no calibration or runtime writes."""
import argparse
import json
import os
from pathlib import Path
import sys

import numpy as np

PACKAGE = Path(__file__).resolve().parents[1]
for path in (PACKAGE, PACKAGE / "scripts"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from core import ground as g
from core.capture_input import check_declared_frame, gate_selection, load_adapted, sha256_file
from core.ground_diagnostics import (observe_boxes, pca_plane, replay_frozen_search,
                                     residual_stats, rotation_conditions)
from evaluate_gli02_candidate import _draft_region, _load_constrained_settings, _load_draft


def verify_draft(draft, manifest):
    if type(draft.get("schema")) is not int or draft["schema"] != 1 or draft.get("kind") != "gli02_capture_selection_draft":
        raise ValueError("unsupported draft schema/kind")
    if draft.get("status") != "pending_human_review" or draft.get("source_kind") not in ("capture_export", "synthetic_fixture"):
        raise ValueError("invalid draft status/source kind")
    review = draft.get("review")
    if not isinstance(review, dict) or not isinstance(review.get("by"), str) or not review["by"] or not isinstance(review.get("at_utc"), str) or not review["at_utc"]:
        raise ValueError("explicit reviewed draft required")
    source = draft.get("source")
    expected = dict(manifest["declared"], meta_sha256=manifest["source"]["meta_sha256"],
                    bin_sha256=manifest["source"]["bin_sha256"],
                    manifest_points_sha256=manifest["points"]["sha256"])
    for key in ("frame", "units", "time_domain", "meta_sha256", "bin_sha256", "manifest_points_sha256"):
        if not isinstance(source, dict) or source.get(key) != expected[key]:
            raise ValueError("draft source mismatch: " + key)
    g._unit_vector(draft.get("up_axis"), "up_axis")
    g._height_interval(draft.get("sensor_height_interval_m"))


def spatial_boxes(draft):
    regions = draft.get("validation_regions")
    if not isinstance(regions, list) or len(regions) != 3:
        raise ValueError("diagnostic requires exactly three approved validation boxes")
    boxes = []
    for label, source in [("FIT", draft.get("fit_region"))] + [(r.get("region_id"), r) for r in regions if isinstance(r, dict)]:
        # Do not let the older wrapper's indices precedence hide contradictory bounds.
        if not isinstance(source, dict) or source.get("indices") is not None:
            raise ValueError("all four diagnostic regions must be fixed spatial boxes")
        box = _draft_region(source, str(label))
        if not isinstance(label, str) or not label or label in [name for name, _ in boxes]:
            raise ValueError("unique nonempty box ids required")
        boxes.append((label, box))
    if len(boxes) != 4:
        raise ValueError("four boxes required")
    return boxes


def local_svg(sidecar, threshold=0.05):
    shown = [entry for entry in sidecar if entry["displayed"] and entry["source_xyz_m"] is not None]
    # ponytail: two fixed source projections, no interactive 3D dependency.
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="620" viewBox="0 0 1200 620">',
             '<rect width="1200" height="620" fill="white"/>',
             '<text x="20" y="25">Source XYZ: X/Y left, X/Z right. Red high / blue low geometric tail; gray support.</text>']
    for panel, axis in enumerate((1, 2)):
        if not shown:
            continue
        xyz = np.asarray([entry["source_xyz_m"] for entry in shown])
        low, high = xyz.min(axis=0), xyz.max(axis=0)
        scale = np.maximum(high - low, 1e-9)
        for entry in shown:
            point = np.asarray(entry["source_xyz_m"])
            x = 30 + panel * 600 + (point[0] - low[0]) / scale[0] * 540
            y = 580 - (point[axis] - low[axis]) / scale[axis] * 520
            residual = entry["signed_residual_m"]
            color = "#d94f35" if residual > threshold else "#226ac7" if residual < -threshold else "#777777"
            title = "row=%s frame=%s local=%s box=%s xyz=%s signed=%s" % (
                entry["pooled_row"], entry["frame_ordinal"], entry["frame_row"], entry["box"], point.tolist(), residual)
            import html
            parts.append('<circle cx="%.3f" cy="%.3f" r="1.5" fill="%s"><title>%s</title></circle>' % (x, y, color, html.escape(title)))
        parts.append('<text x="%d" y="610">X source m, vertical %s source m; bounds %s to %s</text>' % (30 + panel * 600, "YZ"[panel], low.tolist(), high.tolist()))
    return "\n".join(parts + ['</svg>'])


def run(args):
    output = Path(args.output_dir).absolute()
    if output.exists() or output.is_symlink():
        raise ValueError("exclusive output directory already exists")
    paths = [Path(args.prepared_npz).resolve(), Path(args.draft).resolve(),
             Path(__file__).resolve(), PACKAGE / "core/ground_diagnostics.py",
             PACKAGE / "core/ground.py", PACKAGE / "core/capture_input.py",
             PACKAGE / "scripts/evaluate_gli02_candidate.py", PACKAGE / "scripts/sensor_health.py"]
    if args.constrained_config:
        paths.append(Path(args.constrained_config).resolve())
    before = {str(path): sha256_file(str(path)) for path in paths}
    manifest, points = load_adapted(args.prepared_npz)
    for key in ("meta_path", "bin_path"):
        path = manifest["source"][key]
        paths.append(Path(path))
        before[path] = sha256_file(path)
        expected = manifest["source"]["meta_sha256" if key == "meta_path" else "bin_sha256"]
        if before[path] != expected:
            raise ValueError("source changed after loader snapshot")
        for protected in (Path(path).resolve().parent, PACKAGE.resolve()):
            if protected == output.resolve() or protected in output.resolve().parents:
                raise ValueError("output must be outside capture and production package")
    draft = _load_draft(args.draft)
    verify_draft(draft, manifest)
    boxes = spatial_boxes(draft)
    fit_box = boxes[0][1]
    regions = [dict(box, region_id=label) for label, box in boxes[1:]]
    rows, resolved_regions = gate_selection(points, manifest, fit_box, None,
                                             fit_box["frame_group"], regions)
    frame = check_declared_frame(manifest, args.frame)
    settings = _load_constrained_settings(args.constrained_config)
    approved = g._unit_vector(draft["up_axis"], "up_axis")
    plane = pca_plane(points[rows], approved)
    what_if = approved.copy()
    what_if[0] *= -1
    hypotheses = [("approved", approved), ("WHAT_IF_negative_X", what_if),
                  ("WHAT_IF_FIT_PCA_normal", np.asarray(plane["normal"]))]
    fits = []
    for label, up in hypotheses:
        actual = g.fit_ground_plane_constrained(points, settings=settings, frame=frame,
            up_axis=up, sensor_height_interval_m=draft["sensor_height_interval_m"],
            fit_indices=rows, fit_frame_group=fit_box["frame_group"], validation_regions=resolved_regions)
        replay = replay_frozen_search(points, rows, up, draft["sensor_height_interval_m"], settings)
        for key in ("sampled_fit_count", "raw_candidates", "candidates"):
            if actual[key] != replay[key]:
                raise ValueError("frozen/replay mismatch: " + label + "/" + key)
        if actual.get("competition_truncated", False) != replay["competition_truncated"]:
            raise ValueError("frozen/replay truncation mismatch")
        model = actual.get("competition_candidates", [])
        diagnostic_plane = model[0] if model else plane
        posthoc = [{"region_id": region["region_id"], "origin": "posthoc_all_selected_rows",
                    "stats": residual_stats(points[region["indices"]], diagnostic_plane["normal"],
                                             diagnostic_plane["offset_m"], settings["inlier_threshold_m"])}
                   for region in resolved_regions]
        fits.append({"label": label, "up_axis": up.tolist(), "physical_verified": False,
                     "actual_frozen_fit": actual, "replay": replay, "posthoc_holdout": posthoc,
                     "posthoc_plane": diagnostic_plane,
                     "native_validation_executed": bool(actual["validation_regions"]),
                     "PCA_angle_to_prior_deg": g._angle_deg(plane["normal"], up)})
    # Prefer the frozen refined plane for observation; early return falls back to explicit PCA.
    observation_plane = next((f["posthoc_plane"] for f in fits if f["actual_frozen_fit"].get("competition_candidates")), plane)
    records, sidecar, temporal = observe_boxes(points, manifest, boxes, observation_plane,
                                             args.display_budget, threshold=settings["inlier_threshold_m"])
    report = {"schema": 1, "kind": "gli04_geometry_diagnostic", "physical_verified": False,
              "frame": frame, "units": "m", "source_manifest": manifest,
              "approved_draft": draft, "source_hashes": before,
              "settings": settings, "settings_origin": args.constrained_config or "frozen_defaults",
              "rotation": rotation_conditions(), "conditional_26deg": rotation_conditions(26),
              "extrinsic": {"status": "unknown", "recording_binding": None,
                            "reason": "source metadata has no recording-bound extrinsic/config identity"},
              "PCA_reference": plane, "observation_plane": observation_plane,
              "observation_plane_origin": "frozen_refined_when_available_else_FIT_PCA; not physical",
              "experiments": fits, "box_frame_records": records, "temporal": temporal,
              "spatial_bins": {"axes": "source XYZ", "size_m": 0.25, "rule": "floor(xyz/size); no residual selection"},
              "sidecar_count": len(sidecar), "sidecar": "source_indices.jsonl",
              "display_budget_per_box_frame": args.display_budget,
              "support_tail_threshold_m": settings["inlier_threshold_m"],
              "tail_identity": "geometric high/low tails only; physical identity unknown"}
    encoded = json.dumps(report, ensure_ascii=False, allow_nan=False, indent=2)
    encoded_rows = [json.dumps(row, ensure_ascii=False, allow_nan=False) + "\n" for row in sidecar]
    svg = local_svg(sidecar, settings["inlier_threshold_m"])
    lines = ["# GL-I04 offline diagnostic", "", "physical_verified=false; recording extrinsic unknown.",
             "Source XYZ projections and oriented model residuals; high/low tails have no physical identity.",
             "Actual frozen fit, independent replay and posthoc holdout are separate JSON fields.", "",
             "| hypothesis | native status/reason | sample | native validation | PCA angle |", "|---|---|---|---|---|"]
    for experiment in fits:
        actual = experiment["actual_frozen_fit"]
        lines.append("| %s | %s / %s | %s | %s | %.6f |" % (
            experiment["label"], actual["status"], actual["reason"], actual["sampled_fit_count"],
            experiment["native_validation_executed"], experiment["PCA_angle_to_prior_deg"]))
    lines += ["", "## Full fixed-box temporal observations", "", "```json", json.dumps(temporal, indent=2), "```",
              "", "No pooled fit or residual filtering of validation. All selected rows are in source_indices.jsonl.",
              "Display stride indices and full statistics are separately recorded. Inspect local_source.svg point titles."]
    for path in paths:
        if sha256_file(str(path)) != before[str(path)]:
            raise ValueError("input/code changed while computing: " + str(path))
    # Publication is fail-closed: computation/serialization precede exclusive mkdir.
    os.mkdir(str(output))
    with (output / "diagnostic.json").open("x", encoding="utf-8") as handle:
        handle.write(encoded)
    with (output / "source_indices.jsonl").open("x", encoding="utf-8") as handle:
        handle.writelines(encoded_rows)
    with (output / "diagnostic.md").open("x", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")
    with (output / "local_source.svg").open("x", encoding="utf-8") as handle:
        handle.write(svg)
    print(json.dumps({"output_dir": str(output), "kind": report["kind"],
                      "physical_verified": False, "box_frame_records": len(records),
                      "sidecar_count": len(sidecar)}))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared-npz", required=True)
    parser.add_argument("--draft", required=True)
    parser.add_argument("--frame")
    parser.add_argument("--constrained-config")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--display-budget", type=int, default=300)
    args = parser.parse_args(argv)
    try:
        return run(args)
    except (OSError, ValueError, TypeError, OverflowError) as exc:
        print("GL-I04 diagnostic refused: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""GL-I02 offline candidate ground-plane evaluation (thin orchestration only).

This is a *thin* wrapper over the existing GL-I01 / core public API. It never
reimplements ROI selection or ground fitting; it only wires the humans-reviewed
selection draft into the already-tested constrained path:

    load_adapted -> check_declared_frame -> gate_selection ->
    fit_ground_plane_constrained -> validate_constrained_ground ->
    build_input_info -> build_geometry_calibration -> save_exclusive_json

The produced artifact is a *candidate* (``status.ground = "candidate"``,
``ground.status = "valid"``, no ``ground_derived``, physical flags still false).
It never fits the real capture automatically: a filled ``--draft`` is required,
and every missing fit/validation/up-axis/height field is refused with no
artifact (``exit 2``). Adapted NPZ input only; a non-adapted (legacy) input is
refused outright instead of falling back to the legacy route. It is read-only
with respect to the capture directory and never touches the GL-02 lifecycle,
production config, driver or webui.
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
PACKAGE_DIR = os.path.abspath(os.path.join(HERE, os.pardir))
for _path in (PACKAGE_DIR, HERE):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from core.calibration import (GeometryCalibrationError,
                              build_geometry_calibration,
                              validate_geometry_calibration)
from core.capture_input import (CaptureInputError, build_input_info,
                                check_declared_frame, classify_npz,
                                gate_selection, load_adapted, prepare_npz)
from core.ground import (fit_ground_plane_constrained, ground_is_valid,
                         resolve_constrained_settings,
                         validate_constrained_ground)
from calibrate_sensors import save_exclusive_json
from sensor_health import load_config

DRAFT_KIND = "gli02_capture_selection_draft"
DRAFT_STATUS = "pending_human_review"
DEFAULT_REFUSAL = "no_auto_ground_selection"
BOUND_KEYS = ("x_min_m", "x_max_m", "y_min_m", "y_max_m", "z_min_m", "z_max_m")


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture-dir", default=None,
                        help="read-only GL-I01 capture export dir "
                             "(meta.json + points.bin)")
    parser.add_argument("--prepared-npz", default=None,
                        help="existing GL-I01 adapted NPZ (takes precedence "
                             "over --capture-dir)")
    parser.add_argument("--frame", default=None,
                        help="declared frame (required to prepare a capture "
                             "dir; must match the manifest otherwise)")
    parser.add_argument("--units", default="m",
                        help="declared length unit for prepare (only 'm')")
    parser.add_argument("--draft", default=None,
                        help="human-filled capture selection draft JSON")
    parser.add_argument("--constrained-config", default=None,
                        help="explicit constrained ground YAML; omit to keep "
                             "the frozen defaults")
    parser.add_argument("--emit-draft", action="store_true",
                        help="write a blank pending draft to --draft-out and stop")
    parser.add_argument("--draft-out", default=None,
                        help="exclusive output path for --emit-draft")
    parser.add_argument("--source-kind",
                        choices=("capture_export", "synthetic_fixture"),
                        default="capture_export")
    parser.add_argument("--output", required=True,
                        help="exclusive output path for the candidate artifact")
    parser.add_argument("--calibration-id", default=None)
    parser.add_argument("--note", default=None)
    return parser.parse_args(argv)


def _load_points(args):
    """Return ``(manifest, points)`` from the adapted NPZ, refusing legacy."""
    if args.prepared_npz:
        if classify_npz(args.prepared_npz) != "adapted":
            raise CaptureInputError(
                "input is not an adapted capture-input NPZ; the legacy route "
                "is not available here: " + str(args.prepared_npz))
        return load_adapted(args.prepared_npz)
    if not args.frame:
        raise CaptureInputError("--frame is required to prepare --capture-dir")
    adapted = os.path.splitext(os.path.abspath(args.output))[0] + ".adapted.npz"
    prepare_npz(args.capture_dir, args.frame, args.units, adapted)
    return load_adapted(adapted)


def _blank_draft(manifest, source_kind):
    source = manifest.get("source") or {}
    declared = manifest.get("declared") or {}
    groups = manifest.get("frame_groups") or {}
    return {
        "schema": 1,
        "kind": DRAFT_KIND,
        "status": DRAFT_STATUS,
        "source_kind": source_kind,
        "source": {
            "capture_dir": os.path.dirname(source.get("meta_path") or ""),
            "meta_sha256": source.get("meta_sha256"),
            "bin_sha256": source.get("bin_sha256"),
            "frame": declared.get("frame"),
            "units": declared.get("units"),
            "time_domain": declared.get("time_domain"),
            "adapted_npz": None,
            "manifest_points_sha256": (manifest.get("points") or {}).get("sha256"),
        },
        "frame_scope": {
            "total_points": int(manifest["points"]["shape"][0]),
            "frames": len(manifest.get("frames") or []),
            "frame_groups": list(groups),
        },
        "up_axis": None,
        "sensor_height_interval_m": None,
        "fit_region": {"frame_group": None, "indices": None, "bounds": None},
        "validation_regions": [],
        "default_refusal": DEFAULT_REFUSAL,
        "review": {"required": True, "by": None, "at_utc": None},
    }


def _load_draft(path):
    try:
        with open(path, encoding="utf-8") as handle:
            draft = json.load(handle)
    except (OSError, ValueError) as exc:
        raise CaptureInputError("cannot read selection draft: " + str(exc))
    if not isinstance(draft, dict):
        raise CaptureInputError("selection draft must decode to an object")
    return draft


def _draft_region(region, label):
    """Translate a human draft region into the group-first selector shape.

    The draft keeps an optional nested ``bounds`` object; the selector expects
    the six bound keys at the top level (or explicit ``indices``).
    """
    if not isinstance(region, dict):
        raise CaptureInputError(label + " must be an object")
    group_id = region.get("frame_group")
    if not isinstance(group_id, str) or not group_id:
        raise CaptureInputError(label + " needs an explicit frame_group")
    resolved = {"frame_group": group_id}
    if region.get("indices") is not None:
        resolved["indices"] = region["indices"]
        return resolved
    bounds = region.get("bounds")
    if isinstance(bounds, dict):
        missing = [key for key in BOUND_KEYS if key not in bounds]
        if missing:
            raise CaptureInputError(label + " bounds are incomplete: "
                                    + ", ".join(missing))
        resolved.update({key: bounds[key] for key in BOUND_KEYS})
        return resolved
    present = [key for key in BOUND_KEYS if key in region]
    if len(present) == len(BOUND_KEYS):
        resolved.update({key: region[key] for key in BOUND_KEYS})
        return resolved
    raise CaptureInputError(label + " needs indices or complete x/y/z bounds")


def _load_constrained_settings(path):
    """Load an explicit variant without changing defaults or draft emission."""
    if path is None:
        return resolve_constrained_settings(None)
    try:
        import yaml
    except ImportError as exc:
        raise CaptureInputError("constrained config requires PyYAML: " + str(exc))
    try:
        config = load_config(path)
        if not isinstance(config, dict) or not isinstance(
                config.get("ground_constrained"), dict):
            raise ValueError("config needs a ground_constrained mapping")
        return resolve_constrained_settings(config["ground_constrained"])
    except (OSError, ValueError, OverflowError, RuntimeError, yaml.YAMLError) as exc:
        raise CaptureInputError("constrained config refused: " + str(exc))


def _run_candidate(args, manifest, points):
    draft = _load_draft(args.draft)
    up_axis = draft.get("up_axis")
    height = draft.get("sensor_height_interval_m")
    fit_region = _draft_region(draft.get("fit_region"), "fit_region")
    validation_regions = draft.get("validation_regions")
    if not isinstance(validation_regions, list) or len(validation_regions) < 3:
        raise CaptureInputError("at least three validation_regions are required")
    resolved_regions_in = [
        _draft_region(region, "validation region %d" % index)
        for index, region in enumerate(validation_regions)]
    for region, source in zip(resolved_regions_in, validation_regions):
        region["region_id"] = source.get("region_id")

    frame = check_declared_frame(manifest, args.frame)
    fit_rows, resolved_regions = gate_selection(
        points, manifest, fit_region, None, fit_region["frame_group"],
        resolved_regions_in)
    resolved = _load_constrained_settings(args.constrained_config)
    try:
        result = fit_ground_plane_constrained(
            points, settings=resolved, frame=frame, up_axis=up_axis,
            sensor_height_interval_m=height, fit_indices=fit_rows,
            fit_frame_group=fit_region["frame_group"],
            validation_regions=resolved_regions)
        if result is not None:
            validate_constrained_ground(result, expected_frame=frame)
    except ValueError as exc:
        raise CaptureInputError("constrained fit refused: " + str(exc))
    if result is None or not ground_is_valid(result):
        reason = (result or {}).get("reason", "invalid fit")
        raise CaptureInputError("candidate ground was not produced: " + reason)

    input_info = build_input_info(manifest, args.draft, None, args.draft)
    input_info["source"] = args.source_kind
    input_info["synthetic"] = args.source_kind == "synthetic_fixture"
    created = datetime.now(timezone.utc).isoformat()
    calibration_id = args.calibration_id or (
        "gli02_candidate_" + time.strftime("%Y%m%d_%H%M%S"))
    artifact = build_geometry_calibration(
        calibration_id, created, frame, ground=result, input_info=input_info,
        statuses={"ground": "candidate", "geometry_params": "candidate"},
        note=args.note)
    artifact["constrained_ground"] = result
    validate_geometry_calibration(artifact)
    save_exclusive_json(args.output, artifact)
    summary = {"output": args.output, "status": artifact["status"],
               "ground_status": result["status"], "source": args.source_kind,
               "points": int(len(points)),
               "sensor_height_m": result["sensor_height_m"],
               "fit_frame_group": fit_region["frame_group"],
               "validation_regions": len(resolved_regions)}
    print(json.dumps(summary, allow_nan=False))
    return 0


def main(argv=None):
    args = parse_args(argv)
    if not args.capture_dir and not args.prepared_npz:
        print("one of --capture-dir or --prepared-npz is required",
              file=sys.stderr)
        return 2
    if args.capture_dir and args.prepared_npz:
        print("both --capture-dir and --prepared-npz given; using --prepared-npz",
              file=sys.stderr)
    try:
        manifest, points = _load_points(args)
    except (CaptureInputError, OSError, ValueError) as exc:
        print("gli02 input refused: " + str(exc), file=sys.stderr)
        return 2

    if args.emit_draft:
        if not args.draft_out:
            print("--emit-draft requires --draft-out", file=sys.stderr)
            return 2
        try:
            save_exclusive_json(args.draft_out,
                                _blank_draft(manifest, args.source_kind))
        except GeometryCalibrationError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        print(json.dumps({"draft_out": args.draft_out, "status": DRAFT_STATUS},
                         allow_nan=False))
        return 0

    if not args.draft:
        print("--draft is required to produce a candidate artifact "
              "(no automatic ground selection)", file=sys.stderr)
        return 2
    try:
        return _run_candidate(args, manifest, points)
    except (CaptureInputError, GeometryCalibrationError, OSError, ValueError) as exc:
        print("gli02 candidate refused: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())

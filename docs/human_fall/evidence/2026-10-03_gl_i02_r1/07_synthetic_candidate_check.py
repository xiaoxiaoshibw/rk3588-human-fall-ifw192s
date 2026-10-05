# GL-I02 synthetic candidate end-to-end evidence (read-only wrt production).
# Builds a synthetic 7-frame planar capture export, emits the draft template,
# fills it, and runs the real wrapper CLI to a candidate artifact. All outputs
# live under this evidence directory; no production source or capture is written.
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np

REPO = Path(os.getcwd())
PKG = REPO / "src" / "human_fall_detection"
WRAPPER = PKG / "scripts" / "evaluate_gli02_candidate.py"
EV = REPO / "docs" / "human_fall" / "evidence" / "2026-10-03_gl_i02_r1"
WORK = EV / "07_synthetic"
WORK.mkdir(parents=True, exist_ok=True)

ROW = np.dtype([("x", "<f4"), ("y", "<f4"), ("z", "<f4"), ("intensity", "<f4"),
                ("ring", "<u2"), ("_pad1", "<u2"), ("timestamp", "<f4"),
                ("_pad2", "<f4")])
BOUNDS = {"x_min_m": -1e9, "x_max_m": 1e9, "y_min_m": -1e9, "y_max_m": 1e9,
          "z_min_m": -1e9, "z_max_m": 1e9}
CHECKS = []


def check(name, ok, detail=""):
    CHECKS.append(ok)
    print("%-56s %s %s" % (name, "PASS" if ok else "FAIL", detail))


def write_export(directory, counts=(400, 100, 100, 100, 10, 10, 10)):
    directory.mkdir(parents=True, exist_ok=True)
    rng = np.random.RandomState(7)
    rows = np.zeros(int(sum(counts)), dtype=ROW)
    frames, offset = [], 0
    for index, count in enumerate(counts):
        rows["x"][offset:offset + count] = rng.uniform(-4.0, 4.0, count)
        rows["y"][offset:offset + count] = rng.uniform(-4.0, 4.0, count)
        rows["z"][offset:offset + count] = -1.0 + rng.uniform(-0.005, 0.005, count)
        frames.append({"seq": 1979000 + index, "stamp_sec": 100 + index,
                       "stamp_nanosec": 1000 + index,
                       "bag_time_sec": 1.0 + index, "offset_points": offset,
                       "count_points": count, "dropped_points": 0})
        offset += count
    (directory / "points.bin").write_bytes(rows.tobytes())
    meta = {
        "format": "human_capture_session", "format_version": 1,
        "session_id": "cap_synthetic_gli02", "created_iso": "2026-10-03T00:00:00+08:00",
        "sensor": {"model": "IFW192S", "frame_id": "innolidar"},
        "time_domain": "device_stamp_s_unanchored",
        "point_layout": {"fields": ["x", "y", "z", "intensity", "ring", "timestamp"],
                         "dtypes": ["<f4", "<f4", "<f4", "<f4", "<u2", "<f4"],
                         "stride_bytes": 28, "endian": "little",
                         "pad_offsets_bytes": [18, 24]},
        "point_file": "points.bin", "point_stride_bytes": 28,
        "total_points": int(sum(counts)), "total_dropped_points": 0,
        "frames": frames,
        "extraction": {"tool": "bag2session/0.1.0", "source_bag": "/x/y.bag",
                       "source_bag_sha256": "ab" * 32, "point_step_bytes_src": 26,
                       "dropped_frames": 0},
    }
    (directory / "meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    return meta


def run(args):
    completed = subprocess.run([sys.executable, str(WRAPPER)] + args,
                               capture_output=True, text=True)
    print("$ %s\n  rc=%d stdout=%s stderr=%s" %
          (" ".join(args), completed.returncode, completed.stdout.strip(),
           completed.stderr.strip()))
    return completed.returncode


def main():
    cap = WORK / "cap"
    write_export(cap)
    output = WORK / "candidate.json"
    template = WORK / "draft_template.json"
    rc = run(["--capture-dir", str(cap), "--frame", "innolidar", "--units", "m",
              "--output", str(output), "--emit-draft", "--draft-out", str(template),
              "--source-kind", "synthetic_fixture"])
    check("emit-draft exit 0", rc == 0, "rc=%d" % rc)

    draft = json.loads(template.read_text(encoding="utf-8"))
    gids = draft["frame_scope"]["frame_groups"]
    check("draft status pending_human_review",
          draft["status"] == "pending_human_review", draft["status"])
    check("draft default_refusal no_auto_ground_selection",
          draft["default_refusal"] == "no_auto_ground_selection",
          draft["default_refusal"])
    check("draft is null until human fills",
          draft["up_axis"] is None and draft["sensor_height_interval_m"] is None
          and draft["fit_region"]["frame_group"] is None)

    draft["up_axis"] = [0.0, 0.0, 1.0]
    draft["sensor_height_interval_m"] = [0.5, 1.5]
    draft["fit_region"] = {"frame_group": gids[0], "bounds": dict(BOUNDS)}
    draft["validation_regions"] = [
        {"region_id": "v%d" % i, "frame_group": gids[i], "bounds": dict(BOUNDS)}
        for i in (1, 2, 3)]
    filled = WORK / "draft_filled.json"
    filled.write_text(json.dumps(draft, indent=1), encoding="utf-8")

    adapted = WORK / "candidate.adapted.npz"
    rc = run(["--prepared-npz", str(adapted), "--draft", str(filled),
              "--output", str(output), "--source-kind", "synthetic_fixture"])
    check("candidate exit 0", rc == 0, "rc=%d" % rc)
    check("candidate artifact exists", output.exists())
    if not output.exists():
        return 1
    artifact = json.loads(output.read_text(encoding="utf-8"))
    check("status.ground == candidate", artifact["status"]["ground"] == "candidate",
          artifact["status"]["ground"])
    check("ground.status == valid", artifact["ground"]["status"] == "valid",
          artifact["ground"]["status"])
    check("verification.ground_physical_verified is false",
          artifact["verification"]["ground_physical_verified"] is False)
    check("no GROUND_DERIVED_KEY", "ground_derived" not in artifact)
    check("input.source == synthetic_fixture",
          artifact["input"]["source"] == "synthetic_fixture")
    check("input.synthetic is true", artifact["input"]["synthetic"] is True)
    provenance = artifact["input"]["input_manifest"]["provenance"]
    check("manifest provenance physical_verified false",
          provenance["physical_verified"] is False)
    check("manifest point_index_domain capture_export_row",
          provenance["point_index_domain"] == "capture_export_row")

    passed = sum(1 for ok in CHECKS if ok)
    print("synthetic checks: %d/%d" % (passed, len(CHECKS)))
    return 0 if passed == len(CHECKS) else 1


if __name__ == "__main__":
    sys.exit(main())

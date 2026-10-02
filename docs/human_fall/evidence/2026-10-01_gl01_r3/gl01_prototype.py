#!/usr/bin/env python3
"""GL-01 constrained ground prototype evidence runner (R3, synthetic only).

Runs the synthetic fixtures A-G from the reviewed protocol plus the extra
failure branches, compares the old and new paths on the same sample, exports
the fit/validation support points and a small SVG. Nothing here is a device or
physical result: real ROI identity and sensor height stay BLOCKED.

R3 fixes the R1/R2 manifest generator bug: the ``core/ground.py`` hash key was
the leaked loop variable ``name`` (it showed up as ``L_group_leak``). R1/R2
outputs are preserved untouched.
"""

import argparse
import hashlib
import json
import math
import os
import subprocess
import sys
import tempfile
import time

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(HERE, os.pardir, os.pardir, os.pardir,
                                         os.pardir))
PACKAGE_DIR = os.path.join(REPO_ROOT, "src", "human_fall_detection")
SCRIPTS = os.path.join(PACKAGE_DIR, "scripts")
for path in (PACKAGE_DIR, SCRIPTS):
    if path not in sys.path:
        sys.path.insert(0, path)

from core.ground import fit_ground_plane, fit_ground_plane_constrained


def tangent_basis(up):
    up = np.asarray(up, dtype=np.float64)
    up = up / np.linalg.norm(up)
    reference = np.array([1.0, 0.0, 0.0])
    if abs(float(up @ reference)) > 0.9:
        reference = np.array([0.0, 1.0, 0.0])
    first = np.cross(up, reference)
    first = first / np.linalg.norm(first)
    return first, np.cross(up, first)


def plane_points(up, height, count, extent=12.0, noise=0.02, seed=5):
    up = np.asarray(up, dtype=np.float64)
    up = up / np.linalg.norm(up)
    first, second = tangent_basis(up)
    rng = np.random.RandomState(seed)
    spread = (rng.rand(count, 2) - 0.5) * extent
    points = spread[:, :1] * first + spread[:, 1:] * second - float(height) * up
    return points + rng.randn(count, 3) * noise


def tilt_axis(tilt_deg):
    tilt = math.radians(tilt_deg)
    return np.array([math.sin(tilt), 0.0, math.cos(tilt)])


def split_regions(indices, groups=3):
    chunks = np.array_split(np.asarray(indices), groups)
    return [{"region_id": "region_%d" % i, "indices": chunk.tolist(),
             "frame_group": "g%d" % (i + 1)} for i, chunk in enumerate(chunks)
            if len(chunk)]


def clean_scene(tilt_deg=0.0, height=1.2, seed=5):
    up = tilt_axis(tilt_deg)
    fit_points = plane_points(up, height, 3000, seed=seed)
    val_points = plane_points(up, height, 900, seed=seed + 100)
    points = np.vstack([fit_points, val_points])
    fit = np.arange(0, len(fit_points))
    regions = split_regions(np.arange(len(fit_points), len(points)))
    return points, up, fit, regions


def shortest(result):
    keys = ("status", "reason", "sensor_height_m", "tilt_rad", "fit_inlier_count",
            "inlier_fraction", "ambiguous", "sampled_fit_count", "iterations",
            "iterations_cap", "degenerate_samples", "valid_point_count",
            "fit_index_count")
    summary = {key: result.get(key) for key in keys}
    summary["normal"] = result.get("normal")
    summary["offset_m"] = result.get("offset_m")
    summary["candidates"] = result.get("candidates")
    summary["validation_regions"] = [
        {key: item.get(key) for key in ("region_id", "usable", "passed", "count",
                                        "rms_m", "p95_m", "support_fraction")}
        for item in result.get("validation_regions", [])]
    return summary


def timed(func):
    started = time.perf_counter()
    result = func()
    return result, time.perf_counter() - started


def build_fixtures():
    fixtures = {}

    for tilt in (0.0, 15.0, 25.0):
        fixtures["A_clean_floor_%d" % int(tilt)] = clean_scene(tilt)
    fixtures["E_tilted_floor_30"] = clean_scene(30.0)

    up = np.array([0.0, 0.0, 1.0])
    floor_fit = plane_points(up, 1.2, 3000, seed=7)
    floor_val = plane_points(up, 1.2, 600, seed=8)
    rng = np.random.RandomState(9)
    wall = np.column_stack([np.full(6000, 3.0), rng.uniform(-4, 4, 6000),
                            rng.uniform(-2.5, 0.5, 6000)])
    fixtures["B_wall_dominant"] = (
        np.vstack([floor_fit, floor_val, wall]), up,
        np.concatenate([np.arange(0, 3000), np.arange(3600, 9600)]),
        split_regions(np.arange(3000, 3600)))

    floor_fit = plane_points(up, 1.2, 3000, seed=11)
    floor_val = plane_points(up, 1.2, 300, seed=13)
    desk = plane_points(up, 0.45, 2500, extent=8.0, noise=0.01, seed=12)
    desk_points = np.vstack([floor_fit, floor_val, desk])
    fixtures["C_desk_no_roi"] = (desk_points, up,
                                 np.concatenate([np.arange(0, 3000),
                                                 np.arange(3300, 5800)]),
                                 split_regions(np.arange(3000, 3300)))
    fixtures["C_desk_with_roi"] = (desk_points, up, np.arange(0, 3000),
                                   split_regions(np.arange(3000, 3300)))

    rng = np.random.RandomState(41)
    fixtures["D_missing_ground"] = (
        (rng.rand(6300, 3) - 0.5) * 10.0, up, np.arange(0, 6000),
        split_regions(np.arange(6000, 6300)))

    rng = np.random.RandomState(43)
    along = np.linspace(0.0, 20.0, 400)
    collinear = np.column_stack([along, rng.randn(400) * 5e-4,
                                 rng.randn(400) * 5e-4])
    fixtures["F_degenerate"] = (collinear, up, np.arange(0, 300),
                                split_regions(np.arange(300, 400)))

    floor = plane_points(up, 1.2, 3000, seed=31)
    val = plane_points(up, 1.2, 300, seed=32)
    bad = np.vstack([floor, [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0]], val,
                     [[np.nan, 0.0, 0.0], [np.inf, 0.0, 0.0]]])
    fixtures["G_bad_values"] = (bad, up, np.arange(0, 3002),
                                split_regions(np.arange(3002, 3302)))

    a_normal = tilt_axis(6.0)
    b_normal = tilt_axis(-6.0)
    a_fit = plane_points(a_normal, 1.0, 3000, seed=61)
    a_val = plane_points(a_normal, 1.0, 300, seed=62)
    b_fit = plane_points(b_normal, 1.4, 2900, seed=63)
    fixtures["H_normal_ambiguity"] = (
        np.vstack([a_fit, a_val, b_fit]), up,
        np.concatenate([np.arange(0, 3000), np.arange(3300, 6200)]),
        split_regions(np.arange(3000, 3300)))

    floor_fit = plane_points(up, 1.2, 3000, seed=51)
    floor_val = plane_points(up, 1.2, 300, seed=52)
    fixtures["I_height_conflict"] = (
        np.vstack([floor_fit, floor_val]), up, np.arange(0, 3000),
        split_regions(np.arange(3000, 3300)))

    fit_points = plane_points(up, 1.2, 3000, seed=71)
    good = plane_points(up, 1.2, 200, seed=72)
    off = plane_points(up, 1.5, 200, seed=73)
    fixtures["J_validation_region_fails"] = (
        np.vstack([fit_points, good, off]), up, np.arange(0, 3000),
        [{"region_id": "r1", "frame_group": "g1",
          "indices": np.arange(3000, 3100).tolist()},
         {"region_id": "r2", "frame_group": "g2",
          "indices": np.arange(3100, 3200).tolist()},
         {"region_id": "r3", "frame_group": "g3",
          "indices": np.arange(3200, 3400).tolist()}])

    points, up_clean, fit, regions = clean_scene()
    fixtures["K_overlap"] = (points, up_clean, fit,
                             [dict(regions[0], indices=fit[:50].tolist()),
                              regions[1], regions[2]])
    fixtures["L_group_leak"] = (points, up_clean, fit,
                                [dict(regions[0], frame_group="fit"),
                                 regions[1], regions[2]])
    return fixtures


INTERVALS = {
    "C_desk_no_roi": (0.4, 1.4),
    "C_desk_with_roi": (0.4, 1.4),
    "I_height_conflict": (0.5, 0.9),
    "F_degenerate": (0.0, 10.0),
}


def run_fixture(points, up, fit, regions, name):
    interval = INTERVALS.get(name, (0.5, 1.6))
    result, elapsed = timed(lambda: fit_ground_plane_constrained(
        points, frame="innolidar", up_axis=up,
        sensor_height_interval_m=list(interval), fit_indices=fit,
        fit_frame_group="fit", validation_regions=regions))
    summary = shortest(result)
    summary["elapsed_s"] = elapsed
    return result, summary


def old_new_comparison(points, up, fit, regions, name):
    interval = INTERVALS.get(name, (0.5, 1.6))
    old, old_elapsed = timed(lambda: fit_ground_plane(
        points, settings={"range_min_m": 0.0}, frame="innolidar"))
    new, new_elapsed = timed(lambda: fit_ground_plane_constrained(
        points, frame="innolidar", up_axis=up,
        sensor_height_interval_m=list(interval), fit_indices=fit,
        fit_frame_group="fit", validation_regions=regions))
    return {"fixture": name, "same_sample_points": int(len(points)),
            "old": {"status": old["status"], "reason": old["reason"],
                    "normal": old["normal"], "offset_m": old["offset_m"],
                    "fit_inlier_count": old["fit_inlier_count"],
                    "elapsed_s": old_elapsed},
            "new": {"status": new["status"], "reason": new["reason"],
                    "normal": new["normal"], "offset_m": new["offset_m"],
                    "fit_inlier_count": new["fit_inlier_count"],
                    "elapsed_s": new_elapsed,
                    "sampled_fit_count": new["sampled_fit_count"],
                    "iterations": new["iterations"]}}


def export_support(result, points, out_dir):
    rows = [["role", "region_id", "frame_group", "source_index", "x", "y", "z",
             "residual_m"]]
    normal = np.asarray(result["normal"], dtype=np.float64)
    offset = float(result["offset_m"])
    for index in result["fit_support_indices"]:
        point = points[index]
        rows.append(["fit_support", "", result["fit_frame_group"], str(index)] +
                    ["%.6f" % value for value in point] +
                    ["%.6f" % abs(float(point @ normal) + offset)])
    for region in result["validation_regions"]:
        if not region.get("usable"):
            continue
        for index in region["indices"]:
            point = points[index]
            rows.append(["validation", region["region_id"],
                         region.get("frame_group") or "", str(index)] +
                        ["%.6f" % value for value in point] +
                        ["%.6f" % abs(float(point @ normal) + offset)])
    with open(os.path.join(out_dir, "12_support_points.csv"), "w",
              encoding="utf-8") as handle:
        handle.write("\n".join(",".join(row) for row in rows) + "\n")
    return len(rows) - 1


def write_svg(result, points, out_dir):
    up = np.asarray(result["up_axis"], dtype=np.float64)
    first, second = tangent_basis(up)
    def project(pts, horizontal):
        if horizontal:
            return pts @ first, pts @ second
        return pts @ first, pts @ up
    width, height, scale = 640, 320, 26.0
    panels = []
    for label, horizontal in (("top", True), ("side", False)):
        x, y = project(points, horizontal)
        def to_svg(px, py):
            return (80 + px * scale, height - 60 + py * scale)
        parts = []
        for index in result["fit_support_indices"]:
            sx, sy = to_svg(x[index], y[index])
            parts.append('<circle cx="%.1f" cy="%.1f" r="1.2" fill="#2563eb"/>'
                         % (sx, sy))
        for region in result["validation_regions"]:
            color = "#16a34a" if region.get("passed") else "#dc2626"
            for index in region.get("indices", []):
                sx, sy = to_svg(x[index], y[index])
                parts.append('<circle cx="%.1f" cy="%.1f" r="1.6" fill="%s"/>'
                             % (sx, sy, color))
        panels.append('<text x="80" y="30" font-size="14">%s view</text>%s'
                      % (label, "".join(parts)))
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" '
           'viewBox="0 0 %d %d"><rect width="100%%" height="100%%" fill="#fff"/>'
           '%s</svg>' % (width, 2 * height, width, 2 * height, "".join(panels)))
    with open(os.path.join(out_dir, "13_support_viz.svg"), "w",
              encoding="utf-8") as handle:
        handle.write(svg)


def cli_smoke(out_dir):
    points, up, fit, regions = clean_scene()
    with tempfile.TemporaryDirectory() as directory:
        np.savez(os.path.join(directory, "cloud.npz"), points=points)
        np.save(os.path.join(directory, "fit.npy"), np.asarray(fit))
        with open(os.path.join(directory, "regions.json"), "w",
                  encoding="utf-8") as handle:
            json.dump(regions, handle)
        command = [
            sys.executable,
            os.path.join(SCRIPTS, "calibrate_sensors.py"), "--constrained",
            "--points", os.path.join(directory, "cloud.npz"),
            "--config", os.path.join(PACKAGE_DIR, "config",
                                     "geometry_constrained.yaml"),
            "--up-axis", "0", "0", "1",
            "--sensor-height-interval", "0.5", "1.6",
            "--fit-indices", os.path.join(directory, "fit.npy"),
            "--validation-regions", os.path.join(directory, "regions.json"),
            "--fit-frame-group", "fit", "--frame", "innolidar",
            "--calibration-id", "gl01_cli_smoke",
            "--output", os.path.join(directory, "geometry.json"),
            "--diagnostics", os.path.join(directory, "diagnostics.json")]
        completed = subprocess.run(command, capture_output=True, text=True)
        artifact = None
        artifact_path = os.path.join(directory, "geometry.json")
        if os.path.exists(artifact_path):
            with open(artifact_path, encoding="utf-8") as handle:
                artifact = json.load(handle)
        return {"command": command, "returncode": completed.returncode,
                "stdout": completed.stdout.strip(),
                "stderr": completed.stderr.strip(),
                "artifact": artifact}


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=HERE)
    args = parser.parse_args()
    out_dir = os.path.abspath(args.out)
    os.makedirs(out_dir, exist_ok=True)

    fixtures = build_fixtures()
    report = {}
    support_result = None
    for name in sorted(fixtures):
        points, up, fit, regions = fixtures[name]
        result, summary = run_fixture(points, up, fit, regions, name)
        report[name] = summary
        if name == "A_clean_floor_0":
            support_result = (result, points)

    comparisons = [old_new_comparison(*fixtures[name], name)
                   for name in ("A_clean_floor_0", "A_clean_floor_15",
                                "B_wall_dominant", "C_desk_with_roi")]

    with open(os.path.join(out_dir, "10_fixtures.json"), "w",
              encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, ensure_ascii=False, allow_nan=False)
    with open(os.path.join(out_dir, "11_old_vs_new.json"), "w",
              encoding="utf-8") as handle:
        json.dump(comparisons, handle, indent=2, ensure_ascii=False,
                  allow_nan=False)

    exported = export_support(support_result[0], support_result[1], out_dir)
    write_svg(support_result[0], support_result[1], out_dir)
    smoke = cli_smoke(out_dir)
    with open(os.path.join(out_dir, "14_cli_smoke.json"), "w",
              encoding="utf-8") as handle:
        json.dump(smoke, handle, indent=2, ensure_ascii=False, allow_nan=False)

    hashes = {"core/ground.py": sha256(os.path.join(PACKAGE_DIR, "core",
                                                   "ground.py")),
              "config/geometry_constrained.yaml": sha256(
                  os.path.join(PACKAGE_DIR, "config",
                               "geometry_constrained.yaml")),
              "scripts/calibrate_sensors.py": sha256(
                  os.path.join(PACKAGE_DIR, "scripts", "calibrate_sensors.py"))}
    with open(os.path.join(out_dir, "15_manifest.json"), "w",
              encoding="utf-8") as handle:
        json.dump({"hashes": hashes, "support_rows": exported,
                   "cli_returncode": smoke["returncode"]}, handle, indent=2,
                  ensure_ascii=False, allow_nan=False)

    print(json.dumps({"out": out_dir, "fixtures": list(sorted(report)),
                      "support_rows": exported,
                      "cli_returncode": smoke["returncode"]},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())

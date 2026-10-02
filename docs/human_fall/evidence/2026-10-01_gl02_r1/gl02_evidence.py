#!/usr/bin/env python3
"""GL-02 software evidence: math checks, artifact sample, monitor/lifecycle.

Synthetic only. No real ground/installation/physical claim is made here.
"""

import json
import math
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.abspath(os.path.join(HERE, "..", "..", "..", "..", "src",
                                   "human_fall_detection"))
sys.path.insert(0, PKG)
sys.path.insert(0, os.path.join(PKG, "scripts"))

from core.calibration import (apply_ground_derived, build_geometry_calibration,
                              build_ground_derived, ground_derived_inverse,
                              ground_derived_status, validate_ground_derived)
from core.ground import GroundMonitor, monitor_ground_residual
from core.node_runtime import FallNodeCore


def normal_from(tilt_deg, azimuth_deg=0.0):
    tilt, az = math.radians(tilt_deg), math.radians(azimuth_deg)
    axis = np.array([math.cos(az), math.sin(az), 0.0])
    return math.cos(tilt) * np.array([0.0, 0.0, 1.0]) + math.sin(tilt) * axis


def ground(normal, offset):
    normal = np.asarray(normal, float)
    normal = normal / np.linalg.norm(normal)
    return {
        "kind": "ground_plane", "status": "valid", "valid": True, "reason": None,
        "frame": "innolidar", "normal": [float(v) for v in normal],
        "offset_m": float(offset), "sensor_height_m": float(offset),
        "holdout_residual": {"count": 30, "rms_m": 0.01, "max_m": 0.03},
        "holdout_support": {"count": 30, "rms_m": 0.01, "max_m": 0.03,
                            "fraction": 0.8},
        "valid_region": {"x_min_m": -3.0, "x_max_m": 3.0, "y_min_m": -3.0,
                         "y_max_m": 3.0, "z_min_m": -3.0, "z_max_m": 3.0,
                         "range_min_m": 0.1, "range_max_m": 30.0,
                         "point_count": 100},
    }


def math_checks():
    rng = np.random.RandomState(3)
    rows = []
    worst_z = worst_inverse = worst_foot = worst_origin = 0.0
    for tilt in (0.0, 15.0, 30.0):
        for azimuth in (0.0, 45.0, 120.0):
            for height in (1.0, 1.2, 1.5):
                n = normal_from(tilt, azimuth)
                block = build_ground_derived(ground(n, height), [1.0, 0.0, 0.0])
                validate_ground_derived(block, expected_from_frame="innolidar")
                p = (rng.rand(128, 3) - 0.5) * 6.0
                m = apply_ground_derived(p, block)
                e_z = float(np.max(np.abs(m[:, 2] - (p @ n + height))))
                inv = ground_derived_inverse(block)
                rec = m @ np.asarray(inv["R"]).T + np.asarray(inv["t"])
                e_inv = float(np.max(np.abs(rec - p)))
                e_foot = float(np.max(np.abs(apply_ground_derived(
                    (-height * n)[None, :], block)[0])))
                e_org = float(np.max(np.abs(apply_ground_derived(
                    np.zeros((1, 3)), block)[0] - [0.0, 0.0, height])))
                worst_z = max(worst_z, e_z)
                worst_inverse = max(worst_inverse, e_inv)
                worst_foot = max(worst_foot, e_foot)
                worst_origin = max(worst_origin, e_org)
                rows.append({"tilt_deg": tilt, "azimuth_deg": azimuth,
                             "height_m": height,
                             "id": block["ground_derived_id"],
                             "max_abs_ground_z_err_m": e_z,
                             "max_abs_inverse_err_m": e_inv})
    return {"cases": len(rows), "worst_ground_z_err_m": worst_z,
            "worst_inverse_err_m": worst_inverse, "worst_foot_err_m": worst_foot,
            "worst_sensor_origin_z_err_m": worst_origin, "rows": rows}


def artifact_sample():
    g = ground(normal_from(25.0, 30.0), 1.3)
    block = build_ground_derived(
        g, [1.0, 0.0, 0.0], created_at_utc="2026-10-01T00:00:00Z",
        source={"path": "synthetic.npy", "sha256": "0" * 64,
                "frame": "innolidar", "kind": "synthetic_evidence"})
    artifact = build_geometry_calibration(
        "gl02-evidence", "2026-10-01T00:00:00Z", "innolidar", ground=g,
        ground_derived=block, input_info={"source": "synthetic_evidence"})
    return artifact, ground_derived_status(block)


def monitor_samples():
    g = ground([0.0, 0.0, 1.0], 1.2)
    block = build_ground_derived(g, [1.0, 0.0, 0.0])
    inv = ground_derived_inverse(block)
    rng = np.random.RandomState(9)

    def source(local):
        return local @ np.asarray(inv["R"]).T + np.asarray(inv["t"])

    xy = rng.uniform(-1.5, 1.5, size=(400, 2))
    clean = np.column_stack([xy, rng.randn(400) * 0.005])
    shifted = clean.copy()
    shifted[:40, 2] = 0.3
    monitor = GroundMonitor({"sustained_frames": 3, "history_frames": 5})
    first = monitor.feed(source(clean), block)
    runs = [monitor.feed(source(shifted), block) for _ in range(3)]
    return {"ok": first, "degraded_transient": runs[0],
            "sustained": runs[-1],
            "insufficient_support": monitor_ground_residual(
                source(clean[:5]), block)}


def lifecycle():
    g = ground([0.0, 0.0, 1.0], 1.2)
    first = build_ground_derived(g, [1.0, 0.0, 0.0])
    second = build_ground_derived(g, [0.0, 1.0, 0.0])
    artifact = build_geometry_calibration(
        "cal-a", "2026-10-01T00:00:00Z", "innolidar", ground=g,
        ground_derived=first)
    core = FallNodeCore("s1", {}, ground=g, calibration=artifact)
    core.process(np.array([[3.0, 0.0, -1.4], [3.0, 0.0, 0.1]]), 1.0, seq=1,
                 stamp_secs=100, stamp_nsecs=0, frame_id="innolidar", now=1.0)
    before = core._latest_valid_snapshot["source"]
    core.baseline.start("t1", artifact["calibration_id"])
    record = core.apply_ground_context(
        calibration={**artifact, "ground_derived": second})
    return {"first_id": first["ground_derived_id"],
            "second_id": second["ground_derived_id"], "record": record,
            "baseline_status": core.baseline.status,
            "baseline_reason": core.baseline.reason,
            "snapshot_cleared": core._latest_valid_snapshot is None,
            "source_before": before}


def write(name, payload):
    path = os.path.join(HERE, name)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True, allow_nan=False)
    return path


if __name__ == "__main__":
    artifact, status = artifact_sample()
    write("01_math_checks.json", math_checks())
    write("02_artifact_sample.json", artifact)
    write("03_monitor_and_lifecycle.json",
          {"monitor": monitor_samples(), "lifecycle": lifecycle(),
           "derived_status": status})
    print("gl02 evidence written")

#!/usr/bin/env python3
"""Convert one LI-DATA (Blender+LiDAR) pose sequence into a fall_replay .npz.

Read-only on the zip; writes a single ``.npz``. The source CSVs are sparse
(~50-200 points/frame) synthetic scans, so this is for algorithmic regression
and preview only -- never for tuning ``perception.yaml`` thresholds.

Axis mapping (source Blender scan -> ROS REP-103 body frame):
    ros_x (forward) = |source XYZ|     (true slant range; the CSV ``distance``
                                        column carries a constant +5 m offset)
    ros_y (left)    = -source X        (repulsive -> left positive)
    ros_z (up)      = source Z

Usage:
    python3 lidata_to_replay.py --zip "/path/Dataset.zip" \
        --pose "Fall Data 500 poses/50FallData_PoseSet part 1/Pose_000_OriginalPose" \
        --output pose000.npz
"""

import argparse
import csv
import io
import json
import os
import zipfile

import numpy as np

SCHEMA_VERSION = 1


def _load_frame(handle):
    rows = []
    text = io.TextIOWrapper(handle, encoding="utf-8", errors="replace")
    reader = csv.reader(text, delimiter=";")
    header = next(reader, None)
    if header is None or "X" not in header[2]:
        raise ValueError("unexpected CSV header: %r" % (header,))
    for parts in reader:
        if len(parts) < 6:
            continue
        try:
            cat = float(parts[0])
            x, y, zc = float(parts[2]), float(parts[3]), float(parts[4])
        except ValueError:
            continue
        depth = (x * x + y * y + zc * zc) ** 0.5
        rows.append((cat, depth, -x, zc))
    if not rows:
        raise ValueError("frame produced zero points")
    arr = np.asarray(rows, dtype=np.float64)
    return arr[:, 1:4], arr[:, 0]


def convert(zip_path, pose_prefix, output, times_dt, human_cats):
    with zipfile.ZipFile(zip_path) as archive:
        prefix = pose_prefix.rstrip("/") + "/"
        names = sorted(
            (n for n in archive.namelist()
             if n.startswith(prefix) and n.lower().endswith(".csv")),
            key=lambda n: int(n.rsplit("_frame_", 1)[-1].split(".")[0]),
        )
        if not names:
            raise SystemExit("no CSV frames under prefix: %s" % prefix)
        frames = []
        cats = []
        for name in names:
            with archive.open(name) as handle:
                pts, cat = _load_frame(handle)
            frames.append(pts)
            cats.append(cat)
    times = np.arange(len(frames), dtype=np.float64) * float(times_dt)
    np.savez(output,
             frames=np.asarray(frames, dtype=object),
             times=times,
             categories=np.asarray(cats, dtype=object),
             allow_pickle=True)
    return {"kind": "lidata_to_replay", "schema_version": SCHEMA_VERSION,
            "pose": pose_prefix, "frame_count": len(frames),
            "points_min": int(min(len(f) for f in frames)),
            "points_max": int(max(len(f) for f in frames)),
            "output": os.path.abspath(output)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--zip", required=True, help="LI-DATA dataset zip")
    parser.add_argument("--pose", required=True,
                        help="pose folder path inside the zip (activity/pose dir)")
    parser.add_argument("--output", required=True, help="destination .npz")
    parser.add_argument("--dt", type=float, default=0.1,
                        help="synthetic frame period in seconds (default 0.1)")
    parser.add_argument("--human-cats", default="5,6",
                        help="comma-separated category IDs treated as human")
    args = parser.parse_args(argv)
    summary = convert(args.zip, args.pose, args.output, args.dt, args.human_cats)
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

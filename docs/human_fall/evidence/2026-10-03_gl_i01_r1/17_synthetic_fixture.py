#!/usr/bin/env python3
"""Build a synthetic bag2session-format capture and prepare an adapted NPZ.

Synthetic-only: a clean horizontal ground plane z = -1.2 m with small noise,
five non-empty frames plus one leading and one trailing empty frame. This makes
the constrained CLI fit reproducible without touching the real capture.
"""
import json
import os
import struct
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, os.pardir, os.pardir, os.pardir,
                                    os.pardir))
sys.path.insert(0, os.path.join(REPO, "src", "human_fall_detection"))

from core.capture_input import prepare_npz  # noqa: E402

ROW = np.dtype([
    ("x", "<f4"), ("y", "<f4"), ("z", "<f4"), ("intensity", "<f4"),
    ("ring", "<u2"), ("_pad1", "<u2"), ("timestamp", "<f4"), ("_pad2", "<f4"),
])


def plane(count, seed):
    rng = np.random.default_rng(seed)
    x = rng.uniform(-4.0, 4.0, count)
    y = rng.uniform(-3.0, 3.0, count)
    z = -1.2 + rng.normal(0.0, 0.002, count)
    return x, y, z


def build(root):
    os.makedirs(root, exist_ok=True)
    counts = [0, 400, 400, 400, 400, 400, 0]
    rows = []
    frames = []
    offset = 0
    stamp = 1000
    for ordinal, count in enumerate(counts):
        x, y, z = plane(count, ordinal) if count else (
            np.zeros(0), np.zeros(0), np.zeros(0))
        for i in range(count):
            rows.append((x[i], y[i], z[i], 1.0, i % 16, 0, float(i), 0.0))
        frames.append({
            "seq": ordinal, "count_points": count,
            "offset_points": offset, "dropped_points": 0,
            "stamp_sec": stamp + ordinal,
            "stamp_nanosec": (ordinal * 1_000_000) % 1_000_000_000,
            "bag_time_sec": 1.0e9 + ordinal,
        })
        offset += count
    array = np.zeros(len(rows), dtype=ROW)
    for i, (px, py, pz, inten, ring, pad1, ts, pad2) in enumerate(rows):
        array[i] = (px, py, pz, inten, ring, pad1, ts, pad2)
    with open(os.path.join(root, "points.bin"), "wb") as handle:
        handle.write(array.tobytes())
    meta = {
        "format": "human_capture_session",
        "format_version": 1,
        "point_layout": {
            "dtypes": ["<f4", "<f4", "<f4", "<f4", "<u2", "<f4"],
            "endian": "little",
            "fields": ["x", "y", "z", "intensity", "ring", "timestamp"],
            "pad_offsets_bytes": [18, 24],
            "stride_bytes": 28,
        },
        "point_file": "points.bin",
        "point_stride_bytes": 28,
        "sensor": {"frame_id": "innolidar", "model": "IFW192S"},
        "time_domain": "device_stamp_s_unanchored",
        "frames": frames,
        "extraction": {
            "dropped_frames": 0,
            "point_step_bytes_src": 26,
            "tool": "bag2session/0.1.0",
            "source_bag_sha256": "0" * 64,
        },
        "total_dropped_points": 0,
        "total_points": offset,
    }
    with open(os.path.join(root, "meta.json"), "w", encoding="utf-8") as handle:
        json.dump(meta, handle)
    return root


def main():
    work = os.path.join(HERE, "synthetic")
    src = build(os.path.join(work, "cap_synthetic_01"))
    npz = os.path.join(work, "cap_synthetic_01.npz")
    if os.path.exists(npz):
        os.remove(npz)
    prepare_npz(src, "innolidar", "m", npz)
    sys.path.insert(0, os.path.join(REPO, "src", "human_fall_detection"))
    from core.capture_input import load_adapted
    manifest, points = load_adapted(npz)
    gids = list(manifest["frame_groups"])
    full = lambda g: {"x_min_m": -1e9, "x_max_m": 1e9, "y_min_m": -1e9,
                      "y_max_m": 1e9, "z_min_m": -1e9, "z_max_m": 1e9,
                      "frame_group": g}
    with open(os.path.join(work, "fit_region.json"), "w") as handle:
        json.dump(full(gids[1]), handle)
    regions = [dict(full(gids[2]), region_id="r1"),
               dict(full(gids[3]), region_id="r2"),
               dict(full(gids[4]), region_id="r3")]
    with open(os.path.join(work, "validation_regions.json"), "w") as handle:
        json.dump(regions, handle)
    print(json.dumps({
        "npz": npz, "points": int(points.shape[0]),
        "frames": len(manifest["frames"]), "groups": len(gids),
        "fit_frame_group": gids[1],
    }))


if __name__ == "__main__":
    main()

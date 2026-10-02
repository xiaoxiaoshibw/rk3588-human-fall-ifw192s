#!/usr/bin/env python3
"""GL-03 O01/G06 exploratory offline connection analysis (read-only).

This is an exploratory diagnosis over the two GL-00 local artifacts, NOT a
single-frame replay and NOT a human/robot identity conclusion:

- ``14_current_roi_points.csv``: ROI-limited subset with frame_seq/point_index,
  capped (roi_export_capped=true, 6000 rows) so it is not the full frame.
- ``14_current_sample.csv.tgz``: a cross-frame (47-frame) POOL with only x,y,z
  and no frame id / no original point index. It cannot be treated as one frame
  and cannot reconstruct original indices.

It reports, honestly framed:
1. sampling provenance (SHA, row counts, frame membership, ROI cap);
2. a same-input member / horizontal-cell connection baseline on the pool;
3. a LABELLED suspected-ground-plane ablation (only when a trusted synthetic/
   explicit plane is available), to see whether a near-ground layer bridges
   separate clusters;
4. a conservative fallback statement: with no trusted real-plane condition and
   no full-frame evidence, minimal separation stays default-off and the real
   single-frame large-candidate root cause stays BLOCKED.

No production imports; no writes outside the output JSON.
"""
import hashlib
import json
import sys
import tarfile
from collections import Counter

import numpy as np

ROI_CSV = ("docs/human_fall/evidence/2026-10-01_gl00_r1/"
           "14_current_roi_points.csv")
POOL_TGZ = ("docs/human_fall/evidence/2026-10-01_gl00_r1/"
            "14_current_sample.csv.tgz")
POOL_MEMBER = "14_current_sample.csv"
OUT_JSON = ("docs/human_fall/evidence/2026-10-02_gl03_r1/"
            "61_o01_explore.json")
PLANE_BAND_M = 0.05
CELL_M = 0.25


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_roi():
    rows = np.genfromtxt(ROI_CSV, delimiter=",", names=True,
                         dtype=None, encoding="utf-8")
    frame = np.asarray(rows["frame_seq"], dtype=np.int64)
    index = np.asarray(rows["point_index"], dtype=np.int64)
    xyz = np.column_stack((rows["x_m"], rows["y_m"], rows["z_m"])).astype(float)
    counts = Counter(frame.tolist())
    return {"row_count": int(len(frame)),
            "frame_count": int(len(counts)),
            "frame_seq_min": int(frame.min()),
            "frame_seq_max": int(frame.max()),
            "rows_per_frame_min": int(min(counts.values())),
            "rows_per_frame_max": int(max(counts.values())),
            "point_index_min": int(index.min()),
            "point_index_max": int(index.max())}


def load_pool():
    with tarfile.open(POOL_TGZ, "r:gz") as tar:
        handle = tar.extractfile(POOL_MEMBER)
        data = np.loadtxt(handle, delimiter=",", skiprows=1)
    return data


def horizontal_cells(points, cell_m):
    """Same-input horizontal-cell member baseline (no ground assumption)."""
    if not len(points):
        return 0, 0
    flat = np.floor(points[:, :2] / cell_m).astype(np.int64)
    occupied = set(map(tuple, flat.tolist()))
    if not occupied:
        return 0, 0
    visited = set()
    components = 0
    for start in occupied:
        if start in visited:
            continue
        components += 1
        stack = [start]
        visited.add(start)
        while stack:
            cx, cy = stack.pop()
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    nb = (cx + dx, cy + dy)
                    if nb in occupied and nb not in visited:
                        visited.add(nb)
                        stack.append(nb)
    return len(occupied), components


def main():
    roi = load_roi()
    roi["sha256"] = sha256_file(ROI_CSV)
    roi["sampling"] = "per-frame ROI subset, capped export (roi_export_capped)"
    roi["limitation"] = ("ROI-limited and point-capped; frame_seq is known but "
                         "this is not the full frame and has no full-cloud "
                         "background/range context")

    pool = load_pool()
    pool_sha = sha256_file(POOL_TGZ)
    ranges = np.linalg.norm(pool, axis=1)
    cell_count, cell_components = horizontal_cells(pool, CELL_M)

    # A suspected horizontal layer is only used for a *labelled ablation*: if it
    # is removed, do the remaining points that were connected through it split?
    # The layer normal is a pool estimate, not a trusted real ground identity.
    z = pool[:, 2]
    med_z, mad = float(np.median(z)), float(np.median(np.abs(z - np.median(z))))
    band = np.abs(z - med_z) <= max(PLANE_BAND_M, 3.0 * mad)
    band_count = int(np.count_nonzero(band))
    non_band = pool[~band] if band_count else pool
    nb_cells, nb_components = horizontal_cells(non_band, CELL_M)

    result = {
        "analysis": "GL-03 O01/G06 exploratory connection baseline",
        "roi_points": roi,
        "pool": {
            "path": POOL_TGZ,
            "member": POOL_MEMBER,
            "sha256": pool_sha,
            "row_count": int(len(pool)),
            "frame_provenance": "cross-frame pool (metadata.frames=47)",
            "has_frame_id": False,
            "has_original_index": False,
            "sampling": "header x,y,z only, no frame or index",
            "limitation": ("cannot be treated as a single frame and cannot "
                           "reconstruct original point indices"),
            "aabb_min_m": [float(v) for v in pool.min(axis=0)],
            "aabb_max_m": [float(v) for v in pool.max(axis=0)],
            "range_m": {"min": float(ranges.min()),
                        "p50": float(np.median(ranges)),
                        "max": float(ranges.max())},
        },
        "baseline_connection_pool": {
            "cell_m": CELL_M,
            "occupied_cells": int(cell_count),
            "components": int(cell_components),
        },
        "labelled_suspected_plane_ablation": {
            "enabled": bool(band_count),
            "normal_assumption": "none (z-band only)",
            "band_definition": ("|z - median_z| <= max(%.3f, 3*MAD)"
                                % PLANE_BAND_M),
            "band_median_z_m": med_z,
            "band_mad_m": mad,
            "band_count": band_count,
            "band_fraction_of_pool": float(band_count / len(pool)),
            "remaining_cells": int(nb_cells),
            "remaining_components": int(nb_components),
            "components_delta": int(nb_components - cell_components),
            "trusted_real_plane_available": False,
            "note": ("this is a pool-level hypothesis only; with no trusted real "
                     "ground identity and no single-frame evidence the ablation "
                     "cannot confirm the current-frame large-candidate root "
                     "cause"),
        },
        "separation_decision": {
            "default_off": True,
            "enabled": False,
            "reason": ("no trusted real ground condition and no full-frame "
                       "evidence; minimal separation stays default-off and the "
                       "real single-frame root cause / robot identity stays "
                       "BLOCKED"),
        },
    }
    with open(OUT_JSON, "w") as handle:
        json.dump(result, handle, indent=1, sort_keys=True, allow_nan=False)
    print(json.dumps(result, indent=1, sort_keys=True))


if __name__ == "__main__":
    main()

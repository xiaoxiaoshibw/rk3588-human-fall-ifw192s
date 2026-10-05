#!/usr/bin/env python3
"""GL-03 R2 O01 corrected plane-support ablation (read-only, exploratory).

Replaces the R1 misnomer: R1 ``60_o01_explore.py`` removed a ``median(raw-Z)``
+/-3*MAD band and called it a "suspected plane ablation". That z-band is not a
tilted-plane support set, so it cannot say anything about ground bridging. This
script instead uses the *recorded, unverified* candidate planes in
``14_current_planes.json`` as explicit hypotheses and removes points whose
plane-support ``abs(n.p + d) <= plane_band_m`` (the documented 0.05 m band) to
see whether the plane supports the connection of otherwise separate clusters.

Honest scope:
- ``14_current_sample.csv.tgz`` is a cross-frame XY Z pool (47 frames) whose row
  index is NOT an original frame point index; it cannot reconstruct a frame.
- ``14_current_roi_points.csv`` is only 2 truncated ROI frames.
- The candidate planes are provisional/unconfirmed (``normal``/``offset_m``),
  never a trusted ground identity. This cannot confirm the current single-frame
  large-candidate root cause, nor any human/robot identity.

The connection step reuses the production candidate implementation
(``ground_plane_basis`` / ``_horizontal_coords`` / ``_connected_clusters``) so
the ablation is not a second, divergent copy. Separation stays default-off.
"""
import hashlib
import json
import sys
import tarfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
sys.path[:0] = [str(ROOT / "src/human_fall_detection")]
from core.lidar_candidates import (_connected_clusters, _horizontal_coords,
                                   ground_plane_basis)

GL00 = ROOT / "docs/human_fall/evidence/2026-10-01_gl00_r1"
ROI_CSV = GL00 / "14_current_roi_points.csv"
POOL_TGZ = GL00 / "14_current_sample.csv.tgz"
PLANES_JSON = GL00 / "14_current_planes.json"
POOL_MEMBER = "14_current_sample.csv"
OUT = ROOT / "docs/human_fall/evidence/2026-10-02_gl03_r2/21_o01_planes_ablation.json"

PLANE_BAND_M = 0.05   # documented threshold, same units as normal/offset (m)
CELL_M = 0.25         # same horizontal cell used in all pairs of a comparison


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_pool():
    with tarfile.open(POOL_TGZ, "r:gz") as tar:
        handle = tar.extractfile(POOL_MEMBER)
        return np.loadtxt(handle, delimiter=",", skiprows=1)


def as_basis(normal, offset):
    """Production ground-basis record for one candidate plane (valid status)."""
    return ground_plane_basis({"status": "valid", "normal": list(normal),
                              "offset_m": float(offset)})


def components(points, basis):
    if not len(points):
        return []
    horizontal = _horizontal_coords(points, basis)
    return _connected_clusters(horizontal, CELL_M)


def component_report(points, clusters):
    sizes = sorted((len(c) for c in clusters), reverse=True)
    largest = None
    if clusters:
        big = max(clusters, key=len)
        block = points[np.asarray(big)]
        largest = {"size": int(len(big)),
                   "aabb_min_m": [float(v) for v in block.min(axis=0)],
                   "aabb_max_m": [float(v) for v in block.max(axis=0)]}
    return {"component_count": len(clusters),
            "sizes_desc": sizes[:10],
            "largest": largest}


def support_mask(points, normal, offset):
    normal = np.asarray(normal, dtype=np.float64)
    normal = normal / np.linalg.norm(normal)
    return np.abs(points @ normal + float(offset)) <= PLANE_BAND_M


def main():
    pool = load_pool()
    roi_sha = sha256_file(ROI_CSV)
    planes = json.loads(PLANES_JSON.read_text())
    pool_sha = sha256_file(POOL_TGZ)

    ablations = []
    for index, plane in enumerate(planes["competing_planes"]):
        normal, offset = plane["normal"], plane["offset_m"]
        basis = as_basis(normal, offset)
        support = support_mask(pool, normal, offset)
        non_plane = pool[~support]
        full = component_report(pool, components(pool, basis))
        ablated = component_report(non_plane, components(non_plane, basis))
        ablations.append({
            "plane_index": index,
            "normal": [float(v) for v in normal],
            "offset_m": float(offset),
            "horizontal_candidate": bool(plane["horizontal_candidate"]),
            "residual_rms_m": float(plane["residual_rms_m"]),
            "support_fraction_of_pool": float(plane["support_fraction_of_pool"]),
            "support_band_m": PLANE_BAND_M,
            "support_count_in_pool": int(np.count_nonzero(support)),
            "all_points": full,
            "non_plane_points": ablated,
            "components_delta": ablated["component_count"]
            - full["component_count"],
        })

    horizontal = [a for a in ablations if a["horizontal_candidate"]]
    result = {
        "analysis": "GL-03 R2 O01 plane-support ablation (exploratory)",
        "supersedes": ("R1 60_o01_explore.py median raw-Z +/-3MAD band, which was "
                       "mis-named a plane ablation and cannot support any "
                       "ground-bridging conclusion"),
        "pool": {
            "path": str(POOL_TGZ.relative_to(ROOT)).replace("\\", "/"),
            "member": POOL_MEMBER,
            "sha256": pool_sha,
            "row_count": int(len(pool)),
            "provenance": "cross-frame pool (metadata.frame_count=47)",
            "row_index_is_original_frame_index": False,
            "sampling": "header x,y,z only; no frame id and no original index",
            "note": ("pool rows cannot be treated as one frame nor mapped back to "
                     "original point indices"),
        },
        "roi_points": {
            "path": str(ROI_CSV.relative_to(ROOT)).replace("\\", "/"),
            "sha256": roi_sha,
            "limitation": ("ROI-limited, capped export of only 2 truncated frames "
                           "(1142510/1142511); not a full frame"),
        },
        "planes_source": {
            "path": str(PLANES_JSON.relative_to(ROOT)).replace("\\", "/"),
            "sha256": sha256_file(PLANES_JSON),
            "trusted": False,
            "note": "provisional/unconfirmed candidate normals and offsets",
        },
        "comparison_controls": {
            "same_input": "identical pool array for every pair",
            "same_sampling": "no resampling; every point kept in all-points arm",
            "same_cell_m": CELL_M,
            "same_projection_basis": ("each arm projects with the same candidate "
                                      "plane basis from ground_plane_basis"),
            "same_band_m": PLANE_BAND_M,
        },
        "ablations": ablations,
        "horizontal_candidate_summary": horizontal,
        "separation_decision": {
            "default_off": True,
            "enabled": False,
            "reason": ("no trusted real ground identity and no full-frame evidence; "
                       "a pool-level unverified-plane ablation cannot confirm the "
                       "current single-frame large-candidate root cause or any "
                       "human/robot identity"),
        },
        "real_conclusion": "BLOCKED (no full frame / no trusted ground truth)",
    }
    OUT.write_text(json.dumps(result, indent=1, sort_keys=True, allow_nan=False))
    print(json.dumps(result, indent=1, sort_keys=True))


if __name__ == "__main__":
    main()

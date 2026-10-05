#!/usr/bin/env python3
"""GL-03 R3 O01 corrected plane-support statistics (read-only, exploratory).

R2 (``2026-10-02_gl03_r2/20_o01_planes_ablation.py``) added the correct
production-connection ablation but its report mixed the old GL00 per-plane
*peeled* ``support_fraction_of_pool``/``residual_rms_m`` from
``14_current_planes.json`` with the new full-pool mask counts. This R3 script
keeps the R2 output untouched and recomputes every current number from the
complete 47-frame pool under the same single mask:

- support count / fraction / untruncated RMS of ``abs(n.p + d) <= 0.05 m`` on
  the whole pool (not the sequential peeled subset);
- full vs non-plane component reports on identical input/sampling/projection/
  cell=0.25 m parameters, reusing the production connection implementation;
- a cross-check that the R2 component counts/members/AABB still match (they are
  only cited, never re-labelled);
- old peeled values are kept as ``historical_peeled_*`` with an explicit note
  that their member set differs.

Physical semantics stay honest: all six planes are unverified hypotheses.
``horizontal_candidate`` is only a SOURCE-Z near-normal hint (abs(nz) > 0.94),
never world-Z or a ground identity; a plane's removal changing pool
connectivity cannot identify ground/wall/furniture and cannot exclude ground
bridging. No trusted truth -> separation stays default-off, no trust/physical
flag changes, real single-frame root cause remains BLOCKED.
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
R2_JSON = ROOT / "docs/human_fall/evidence/2026-10-02_gl03_r2/21_o01_planes_ablation.json"
ROI_CSV = GL00 / "14_current_roi_points.csv"
POOL_TGZ = GL00 / "14_current_sample.csv.tgz"
PLANES_JSON = GL00 / "14_current_planes.json"
METADATA_JSON = GL00 / "14_current_capture_metadata.json"
POOL_MEMBER = "14_current_sample.csv"
OUT = ROOT / "docs/human_fall/evidence/2026-10-02_gl03_r3/21_o01_planes_ablation_r3.json"

PLANE_BAND_M = 0.05
CELL_M = 0.25
HORIZONTAL_NZ = 0.94


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
    return ground_plane_basis({"status": "valid", "normal": list(normal),
                               "offset_m": float(offset)})


def components(points, basis):
    if not len(points):
        return []
    return _connected_clusters(_horizontal_coords(points, basis), CELL_M)


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


def support_stats(points, normal, offset):
    unit = np.asarray(normal, dtype=np.float64)
    unit = unit / np.linalg.norm(unit)
    residual = points @ unit + float(offset)
    mask = np.abs(residual) <= PLANE_BAND_M
    count = int(np.count_nonzero(mask))
    rms = float(np.sqrt(np.mean(residual[mask] ** 2))) if count else None
    return mask, count, (count / len(points) if len(points) else None), rms


def main():
    pool = load_pool()
    metadata = json.loads(METADATA_JSON.read_text(encoding="utf-8-sig"))
    planes = json.loads(PLANES_JSON.read_text(encoding="utf-8-sig"))
    r2 = json.loads(R2_JSON.read_text(encoding="utf-8-sig"))
    r2_by_index = {a["plane_index"]: a for a in r2["ablations"]}
    rows = int(len(pool))

    ablations = []
    for index, plane in enumerate(planes["competing_planes"]):
        normal, offset = plane["normal"], plane["offset_m"]
        basis = as_basis(normal, offset)
        mask, count, fraction, rms = support_stats(pool, normal, offset)
        non_plane = pool[~mask]
        full = component_report(pool, components(pool, basis))
        ablated = component_report(non_plane, components(non_plane, basis))
        r2_arm = r2_by_index.get(index, {})
        cross_check = {
            "r2_component_counts_match": (
                r2_arm.get("all_points", {}).get("component_count")
                == full["component_count"]
                and r2_arm.get("non_plane_points", {}).get("component_count")
                == ablated["component_count"]),
            "r2_sizes_match": (
                r2_arm.get("all_points", {}).get("sizes_desc") == full["sizes_desc"]
                and r2_arm.get("non_plane_points", {}).get("sizes_desc")
                == ablated["sizes_desc"]),
            "r2_largest_match": (
                r2_arm.get("all_points", {}).get("largest") == full["largest"]
                and r2_arm.get("non_plane_points", {}).get("largest")
                == ablated["largest"]),
        }
        ablations.append({
            "plane_index": index,
            "normal": [float(v) for v in normal],
            "offset_m": float(offset),
            "horizontal_candidate": bool(plane["horizontal_candidate"]),
            "abs_normal_source_z": float(abs(np.asarray(normal)[2]
                                             / np.linalg.norm(normal))),
            "horizontal_hint_is_source_z_only": True,
            "role": "unknown_unverified_hypothesis",
            "support_band_m": PLANE_BAND_M,
            "current_pool_support_count": count,
            "current_pool_support_fraction": fraction,
            "current_pool_support_rms_m": rms,
            "historical_peeled_support_count": int(plane.get("support_count", 0)),
            "historical_peeled_fraction_of_pool": float(
                plane.get("support_fraction_of_pool", 0.0)),
            "historical_peeled_residual_rms_m": float(
                plane.get("residual_rms_m", 0.0)),
            "historical_note": ("GL00 sequential peeled statistics over the "
                                "remaining points after earlier planes; a "
                                "different member set from the current full-pool "
                                "same-mask numbers"),
            "all_points": full,
            "non_plane_points": ablated,
            "components_delta": ablated["component_count"]
            - full["component_count"],
            "r2_cross_check": cross_check,
        })

    result = {
        "analysis": "GL-03 R3 O01 corrected current-pool plane-support stats",
        "supersedes": ("R2 report text mixed the historical peeled "
                       "support_fraction/RMS with the current pool mask; this "
                       "recomputes every current number from the full pool and "
                       "keeps the old values as historical_peeled_*"),
        "kept_outputs": [
            "docs/human_fall/evidence/2026-10-01_gl00_r1/60_o01_explore.py",
            "docs/human_fall/evidence/2026-10-02_gl03_r2/20_o01_planes_ablation.py",
            "docs/human_fall/evidence/2026-10-02_gl03_r2/21_o01_planes_ablation.json",
            "docs/human_fall/evidence/2026-10-02_gl03_r3/04_o01_independent_audit.md",
        ],
        "pool": {
            "path": str(POOL_TGZ.relative_to(ROOT)).replace("\\", "/"),
            "member": POOL_MEMBER,
            "sha256": sha256_file(POOL_TGZ),
            "row_count": rows,
            "frame_count": int(metadata.get("frames", 0)),
            "provenance": ("per-frame finite + non-zero filter, every 20th valid "
                           "point kept, 47 frames concatenated, saved with 4 "
                           "decimal places (gl00_readonly_analyze.py POOL_STRIDE=20)"),
            "not_complete_pipeline": ("not the complete production candidate "
                                      "filter chain and not per-frame raw data; "
                                      "row index is not an original frame index"),
        },
        "roi_points": {
            "path": str(ROI_CSV.relative_to(ROOT)).replace("\\", "/"),
            "sha256": sha256_file(ROI_CSV),
            "limitation": ("ROI-limited, capped export of only 2 truncated frames "
                           "(6000 rows); not a full frame"),
        },
        "planes_source": {
            "path": str(PLANES_JSON.relative_to(ROOT)).replace("\\", "/"),
            "sha256": sha256_file(PLANES_JSON),
            "trusted": False,
            "note": ("six provisional/unconfirmed candidate normals and offsets; "
                     "all roles unknown"),
        },
        "comparison_controls": {
            "same_input": "identical pool array for every full/non-plane pair",
            "same_sampling": "no resampling; every point kept in the full arm",
            "same_cell_m": CELL_M,
            "same_projection_basis": ("each arm projects with the same candidate "
                                      "plane basis from ground_plane_basis"),
            "same_band_m": PLANE_BAND_M,
        },
        "horizontal_hint_rule": {
            "field": "horizontal_candidate",
            "rule": "abs(normal_source_z) > " + str(HORIZONTAL_NZ),
            "meaning": ("SOURCE-Z near-normal hint only (lidar looks downward, "
                        "angle unmeasured): NOT world-Z and NOT a ground "
                        "identity; cannot single out one plane as the ground nor "
                        "exclude ground bridging"),
        },
        "corrected_claims": {
            "current_stats_recomputed_from_full_pool": True,
            "all_six_planes_role": "unknown_unverified_hypothesis",
            "ground_bridging_excluded": False,
            "r2_member_counts_and_aabb_still_valid": all(
                all(a["r2_cross_check"].values()) for a in ablations),
        },
        "ablations": ablations,
        "separation_decision": {
            "default_off": True,
            "enabled": False,
            "trust_or_physical_flags_changed": False,
            "reason": ("no trusted real ground identity and no full-frame/raw-"
                       "index evidence; a pool-level unverified-plane ablation "
                       "cannot confirm the current single-frame large-candidate "
                       "root cause or any human/robot identity"),
        },
        "real_conclusion": "BLOCKED (no full frame / no trusted ground truth)",
    }
    OUT.write_text(json.dumps(result, indent=1, sort_keys=True, allow_nan=False),
                   encoding="utf-8")
    print(json.dumps(result, indent=1, sort_keys=True))


if __name__ == "__main__":
    main()

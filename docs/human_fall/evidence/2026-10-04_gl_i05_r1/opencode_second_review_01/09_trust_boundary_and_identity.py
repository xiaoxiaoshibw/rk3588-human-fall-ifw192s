"""GL-I05 R1 second review: independent trust-boundary and plane-identity probes.

Verifies (do not copy Codex):
  * whether the author oracle accepts non-finite settings / non-unit or zero
    normals when called directly (bypassing resolve_constrained_settings);
  * whether source_review's `approved` plane is the human draft prior or a
    posthoc PCA of the approved FIT rows;
  * whether the source_view plane selector changes residuals (color) or only
    the info label; and whether a point-read handler exists.
Writes only into this review directory.
"""
import importlib.util
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
AUTHOR = ROOT / "docs" / "human_fall" / "evidence" / "2026-10-03_gl_i05_r1" / "research_01"
I04 = ROOT / "docs" / "human_fall" / "evidence" / "2026-10-03_gl_i04_r1" / "12_real_final"
PACKAGE = ROOT / "src" / "human_fall_detection"
sys.path[:0] = [str(PACKAGE), str(AUTHOR), str(HERE)]

import numpy as np                                                  # noqa: E402
from oracle_analysis import oracle as author_oracle                 # noqa: E402

results = []


def check(name, ok, detail=None):
    results.append({"name": name, "ok": bool(ok), "detail": detail})


def w(normal, offset, support):
    return {"normal": list(normal), "offset_m": float(offset),
            "support_count": int(support)}


def main():
    # ---- non-finite settings accepted by the direct oracle call -----------
    two_orthogonal_same_offset = [w([0, 0, 1], 1.0, 100), w([1, 0, 0], 1.0, 100)]
    good = {"distinct_normal_deg": 10.0, "distinct_offset_m": 0.05,
            "support_close_ratio": 0.8}
    nan_deg = dict(good, distinct_normal_deg=float("nan"))
    nan_off = dict(good, distinct_offset_m=float("nan"))
    res_good = author_oracle(two_orthogonal_same_offset, good)["status"]
    res_nan_deg = author_oracle(two_orthogonal_same_offset, nan_deg)["status"]
    check("nan_deg_changes_status", res_nan_deg != res_good,
          {"good": res_good, "nan_deg": res_nan_deg})
    check("nan_deg_accepted_and_closes", res_nan_deg == "seen_pairwise_closed",
          {"status": res_nan_deg})

    two_same_dir = [w([0, 0, 1], 1.0, 100), w([0, 0, 2.0], 1.0, 100)]
    check("nonunit_normal_accepted",
          author_oracle(two_same_dir, good)["status"] == "seen_pairwise_closed",
          author_oracle(two_same_dir, good)["status"])
    two_zero = [w([0, 0, 0], 1.0, 100), w([0, 0, 0], 1.2, 100)]
    check("zero_normal_accepted_as_witness",
          isinstance(author_oracle(two_zero, good), dict),
          author_oracle(two_zero, good)["status"])
    zero_orth = [w([0, 0, 0], 1.0, 100), w([0, 0, 1], 1.0, 100)]
    # zero normal dot anything = 0 -> treated as 90 deg distinct
    check("zero_normal_treated_as_orthogonal",
          author_oracle(zero_orth, good)["status"] == "unresolved",
          author_oracle(zero_orth, good)["status"])

    # ---- approved plane provenance ----------------------------------------
    diag = json.loads((I04 / "diagnostic.json").read_text(encoding="utf-8"))
    draft = diag["approved_draft"]
    up = np.asarray(draft["up_axis"], dtype=float)
    exp = {e["label"]: e for e in diag["experiments"]}
    appr = np.asarray(exp["approved"]["posthoc_plane"]["normal"], dtype=float)
    appr_off = exp["approved"]["posthoc_plane"]["offset_m"]
    angle_to_prior = math.degrees(math.acos(
        max(-1.0, min(1.0, float(up @ appr / (np.linalg.norm(up) * np.linalg.norm(appr)))))))
    check("approved_posthoc_plane_is_not_up_axis", angle_to_prior > 0.5,
          {"angle_to_up_axis_deg": angle_to_prior,
           "posthoc_origin": exp["approved"]["posthoc_plane"].get("origin")})
    # recompute PCA over approved FIT rows and compare to the stored plane
    from core.capture_input import load_adapted, gate_selection
    from evaluate_gli02_candidate import _load_draft, _draft_region
    base = ROOT / "docs" / "human_fall" / "evidence" / "2026-10-03_gl_i02_r1"
    manifest, points = load_adapted(str(base / "08_real" / "real_candidate.adapted.npz"))
    d = _load_draft(str(base / "codex_review_01" / "work" / "filled_real_draft.json"))
    fit = _draft_region(d["fit_region"], "FIT")
    regions = [dict(_draft_region(r, "validation"), region_id=r["region_id"])
               for r in d["validation_regions"]]
    rows, resolved = gate_selection(points, manifest, fit, None, fit["frame_group"], regions)
    fit_points = np.asarray(points[rows], dtype=float)
    center = fit_points.mean(axis=0)
    _, vecs = np.linalg.eigh((fit_points - center).T @ (fit_points - center))
    pca_normal = vecs[:, 0]
    if pca_normal @ up < 0:
        pca_normal = -pca_normal
    angle_pca = math.degrees(math.acos(max(-1.0, min(1.0, float(pca_normal @ appr)))))
    pca_off = -float(pca_normal @ center)
    check("approved_plane_matches_fit_pca", angle_pca < 0.5
          and abs(pca_off - appr_off) < 1e-3,
          {"angle_to_fit_pca_deg": angle_pca, "offset_delta": pca_off - appr_off})
    check("approved_plane_label_matches_provenance",
          exp["approved"]["posthoc_plane"].get("origin", "").startswith("posthoc"),
          exp["approved"]["posthoc_plane"].get("origin"))

    # ---- source view selector / point read --------------------------------
    regen = (HERE / "04_source_review_regen.html").read_text(encoding="utf-8")
    check("source_view_color_uses_stored_residual", "color(r[6],lim)" in regen,
          "color(r[6]) present" if "color(r[6],lim)" in regen else "not found")
    check("source_view_no_point_read_handler",
          ("onclick" not in regen) and ("mousemove" not in regen)
          and ("onmousemove" not in regen),
          {"onclick": "onclick" in regen, "mousemove": "mousemove" in regen})
    check("source_view_recomputes_residual_for_plane",
          "p.normal" in regen and "residual" in regen
          and ("r[3]*p.normal[0]" in regen or "dot" in regen),
          "no per-plane residual recompute found")

    passed = sum(1 for r in results if r["ok"])
    out = {"kind": "gli05_second_review_trust_boundary",
           "passed": passed, "total": len(results), "results": results}
    with (HERE / "09_trust_boundary_and_identity.json").open("x", encoding="utf-8") as handle:
        json.dump(out, handle, ensure_ascii=False, allow_nan=False, indent=2)
    print("SUMMARY %d/%d PASS" % (passed, len(results)))
    for r in results:
        print(("PASS " if r["ok"] else "FAIL ") + r["name"],
              "" if r["ok"] else json.dumps(r["detail"], ensure_ascii=False)[:300])


if __name__ == "__main__":
    main()

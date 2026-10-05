"""Corrected A06 validation-group/row-coverage + freeze-exposure ordering check.

Revision 2 because rev 1 wrongly required 3 validation groups for degenerate
(collinear/narrow_band) cases that produce empty W and therefore no plane.
"""
import hashlib
import json
import sys
from pathlib import Path
from datetime import datetime, timezone

RUN = Path(r"D:\Code\ldiar\docs\human_fall\evidence\2026-10-04_gl_i06_r1")
HERE = RUN / "research_01"
OUT = RUN / "opencode_review_01"
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(RUN.parents[3] / "src/human_fall_detection"))
sys.path.insert(0, str(RUN.parents[3] / "docs/human_fall/evidence/2026-10-04_gl_i05_r2/research_01"))


def mtime(p):
    return datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc).isoformat()


def main():
    summary = json.loads((HERE / "r1_summary_02.json").read_text(encoding="utf-8"))
    fails, scanned, skipped = [], 0, 0
    for row in summary["results"]:
        for v in row["variants"]:
            if not v["validation"]:
                skipped += 1
                continue
            scanned += 1
            groups = [r["frame_group"] for r in v["validation"]]
            if len(groups) != 3 or len(set(groups)) != 3 or "fit" in groups:
                fails.append(("groups", row["case"], groups))
            for r in v["validation"]:
                if "source_xyz_bounds" not in r or r["stats"]["count"] != 80:
                    fails.append(("row_count_or_bounds", row["case"],
                                  r["stats"].get("count")))
    # region indices disjoint from FIT and cover the 240 holdout rows
    import r0_01
    geom_fails = []
    for kind in ("clean", "high_noise", "table"):
        pts, fit_rows, regions = r0_01.scene(kind, 7, False)
        idx = [i for r in regions for i in r["indices"]]
        if set(idx) & set(fit_rows.tolist()):
            geom_fails.append(("overlap", kind))
        if sorted(idx) != list(range(len(fit_rows), len(fit_rows) + 240)):
            geom_fails.append(("coverage", kind, len(idx)))
        for r in regions:
            if len(r["indices"]) != 80:
                geom_fails.append(("region_size", kind, len(r["indices"])))
    # final holdout kind/seed coverage and degenerate accounting
    fh = json.loads((HERE / "final_holdout_summary_01.json").read_text(encoding="utf-8"))
    kinds = sorted({r["case"].rsplit("_", 1)[0][len("final_"):] for r in fh["results"]})
    seeds = sorted({int(r["case"].rsplit("_", 1)[1]) for r in fh["results"]})
    fh_fails = []
    if seeds != [1707, 1719, 1741]:
        fh_fails.append(("seeds", seeds))
    if len(fh["results"]) != 30:
        fh_fails.append(("count", len(fh["results"])))
    deg = []
    closed = []
    for r in fh["results"]:
        for v in r["variants"]:
            if v["status"] == "unresolved" and not v["worst_W_gt_error"]:
                deg.append(r["case"])
            if v["status"] != "unresolved":
                closed.append(r["case"])
        if len(r["variants"]) != 3:
            fh_fails.append(("variants", r["case"]))
    # temporal order: freeze file before first final numerical file
    freeze_m = mtime(HERE / "method_freeze_01.json")
    first_final = min((mtime(p) for p in HERE.glob("final_*_K*_01.json")))
    summary_m = mtime(HERE / "final_holdout_summary_01.json")
    order_fail = []
    if not (freeze_m <= first_final):
        order_fail.append(("freeze_after_final", freeze_m, first_final))
    if not (summary_m >= first_final):
        order_fail.append(("summary_before_final", summary_m, first_final))
    out = dict(a06_validation=dict(scanned=scanned, skipped_empty_W=skipped,
                                   fail_count=len(fails), failures=fails[:40]),
               region_geometry=dict(fail_count=len(geom_fails), failures=geom_fails),
               final_holdout=dict(fail_count=len(fh_fails), failures=fh_fails,
                                  kinds=sorted(kinds), seeds=seeds,
                                  closed_cases=closed, unresolved_no_worst=len(deg)),
               freeze_order=dict(freeze_mtime=freeze_m, first_final_mtime=first_final,
                                 summary_mtime=summary_m, fail_count=len(order_fail),
                                 failures=order_fail),
               note="degenerate collinear/narrow_band produce empty W and no plane; "
                    "their independent-region scoring is undefined, not a false closure")
    (OUT / "06_probe_a06_validation_02.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("A06 validation scanned", scanned, "skipped(emptyW)", skipped, "fails", len(fails))
    print("region geometry fails", len(geom_fails))
    print("final holdout fails", len(fh_fails), "kinds", sorted(kinds), "seeds", seeds)
    print("closed cases", closed[:10], "count", len(closed))
    print("freeze order fails", len(order_fail), freeze_m, "<=", first_final, "<= sum", summary_m)


if __name__ == "__main__":
    main()

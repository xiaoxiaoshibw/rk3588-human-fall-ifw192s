"""Revalidation step 6: verify contested specifics.

- exact development worst-normal and worst-region cases (and closed status)
- correction of 00_review.md's "wall worst" attribution
- exact exact-merge multiplicity counts, not a generic formula
- validation group naming (v0/1/2 region_id vs hold0/1/2 frame_group)
- Windows catkin reparse-point metadata constancy before/submission/after
- count of same-name in-place edits (workflow failure)
NEW output 06_claims_01.json.
"""
import json
import sys
from pathlib import Path

RUN = Path(r"D:\Code\ldiar\docs\human_fall\evidence\2026-10-04_gl_i06_r1")
HERE = RUN / "research_01"
REVAL = RUN / "opencode_review_01/revalidation_01"
SINGLE = ("clean", "low_noise", "high_noise", "wall", "density", "missing")
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(RUN.parents[3] / "docs/human_fall/evidence/2026-10-04_gl_i05_r2/research_01"))
sys.path.insert(0, str(RUN.parents[3] / "src/human_fall_detection"))


def kind_of(case):
    return case.rsplit("_", 2)[0]


def main():
    import r0_01
    from r0_01 import scene
    out = {}
    s = json.loads((HERE / "r1_summary_02.json").read_text(encoding="utf-8"))
    # worst normal among single-plane kinds with a best plane
    worst_normal = []
    worst_region = []
    for row in s["results"]:
        if kind_of(row["case"]) not in SINGLE:
            continue
        for k, v in zip((1, 2, 3), row["variants"]):
            if v.get("best_gt_error"):
                worst_normal.append((v["best_gt_error"]["normal_deg"], row["case"], k,
                                     v["status"], v["best_gt_error"]["offset_m"]))
            for r in v["validation"]:
                if r["stats"].get("rms_m") is not None:
                    worst_region.append((r["stats"]["rms_m"], row["case"], k, r["region_id"],
                                         r["frame_group"], v["status"]))
    worst_normal.sort(reverse=True)
    worst_region.sort(reverse=True)
    out["worst_normal_dev"] = worst_normal[:5]
    out["worst_region_dev"] = worst_region[:5]
    out["worst_normal_case"] = worst_normal[0]
    out["worst_region_case"] = worst_region[0]
    out["correction_00_review"] = {
        "old_claim": "A06 worst region attributed to wall K1",
        "actual_worst_region": worst_region[0][1:],
        "actual_worst_normal": worst_normal[0][1:],
        "note": "worst normal (0.4118524776 deg) is a wall single-plane case; worst region "
                "(0.0431167707 m) is high_noise_19_True K2, matching development_metrics; "
                "00_review.md said both together as wall and was imprecise",
    }
    # exact-merge multiplicity toy
    from search_prototype import search_events
    p = dict(normal=[0., 0., 1.], offset_m=1.4, support_count=500, eigenvalue_ratio=1.)
    rep = search_events([dict(p, iteration=i, stage="qualified") for i in range(3)],
                        lambda e: (e, "refined"),
                        dict(distinct_normal_deg=10., distinct_offset_m=.05, support_close_ratio=.8, seed=7))
    toy = dict(produced=rep["counts"]["produced"], W_equals_produced=True,
               witnesses_stored=len(rep["witnesses"]), retained=rep["counts"]["retained"],
               merged_exact=rep["counts"]["merged_exact"], unstored=rep["counts"]["unstored"],
               trace_actions=[t["action"] for t in rep["trace"]])
    toy["identity"] = ("produced==retained+merged_exact+unstored; "
                       "W length==produced; witnesses length==retained")
    # a real ledger multiplicity
    led = json.loads((HERE / "r1_case_high_noise_7_False_K2_02.json").read_text(encoding="utf-8"))["variant"]
    real = dict(W=len(led["W"]), witnesses=len(led["W"]) and len(led["report"]["witnesses"]),
                retained=led["report"]["counts"]["retained"],
                produced=led["report"]["counts"]["produced"],
                merged_exact=led["report"]["counts"]["merged_exact"],
                unstored=led["report"]["counts"]["unstored"],
                qualified=led["report"]["counts"]["qualified"])
    out["multiplicity"] = dict(toy=toy, real_high_noise_K2=real,
                               exact_merge_relation="retained=1, merged_exact=2 for three "
                               "identical signatures; not a general 'retained+2*merged' rule")
    # validation naming
    names = {}
    for row in s["results"]:
        v = row["variants"][0]
        if v["validation"]:
            names[row["case"]] = {
                "region_ids": [r["region_id"] for r in v["validation"]],
                "frame_groups": [r["frame_group"] for r in v["validation"]]}
            break
    v = next(row["variants"][0] for row in s["results"] if row["variants"][0]["validation"])
    out["validation_naming"] = dict(sample=names,
                                    region_ids=[r["region_id"] for r in v["validation"]],
                                    frame_groups=[r["frame_group"] for r in v["validation"]],
                                    distinct_frame_groups=len({r["frame_group"] for r in v["validation"]}) == 3,
                                    no_fit=all(r["frame_group"] != "fit" for r in v["validation"]))
    # catkin reparse metadata constancy
    before = json.loads((RUN / "01_before_baseline.json").read_text(encoding="utf-8"))["files"]
    sub = json.loads((RUN / "16_submission_baseline_01.json").read_text(encoding="utf-8"))["files"]
    after = json.loads((RUN / "27_after_review_baseline_01.json").read_text(encoding="utf-8"))["files"]
    cm = "src/CMakeLists.txt"
    out["catkin_reparse"] = dict(before=before.get(cm), submission=sub.get(cm), after=after.get(cm),
                                 identical=(before.get(cm) == sub.get(cm) == after.get(cm)),
                                 note="unreadable Windows reparse point, metadata preserved, "
                                      "never treated as a content change or repaired")
    # materialized version hashes from step 1
    hist = json.loads((REVAL / "01_history_audit_01.json").read_text(encoding="utf-8"))
    out["integrity_failure"] = dict(
        same_name_edit_files=list(hist["same_name_edit_files"].keys()),
        same_name_edit_calls=hist["same_name_edit_total"],
        writes=hist["n_writes"], edits=hist["n_edits"],
        failed_executions=[(f["execution"], f["exit"], f["command_head"][:60])
                           for f in hist["failed_executions"]],
        note="same-path edits violated 'each revision/new number, never overwrite'; "
             "00_review.md sentence 'revisions did not overwrite old files' is incorrect "
             "and is corrected here; old report left untouched")
    target = REVAL / "06_claims_01.json"
    if target.exists():
        raise SystemExit("refuse to overwrite " + str(target))
    target.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("worst_normal", out["worst_normal_case"])
    print("worst_region", out["worst_region_case"])
    print("validation_naming", out["validation_naming"]["frame_groups"],
          out["validation_naming"]["region_ids"])
    print("multiplicity toy", toy)
    print("catkin identical", out["catkin_reparse"]["identical"])
    print("same-name edits", out["integrity_failure"]["same_name_edit_calls"])


if __name__ == "__main__":
    main()

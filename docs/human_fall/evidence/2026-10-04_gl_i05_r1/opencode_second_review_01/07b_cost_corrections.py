"""GL-I05 R1 second review: corrected budget fixture and cost-evidence audit.

07_* used a too-small candidate_budget=64 for the clean/noise close fixture
(the ledger deliberately uses min(512, unique+8)); and the slow ledger stores
its oracle/search time under prototype.elapsed_s, not entry.elapsed_s. This
new script corrects both and records the slow-vs-final timing that IS in the
artifacts, plus the discrepancy with the narrative "46s/case".

Writes only into this review directory.
"""
import importlib.util
import json
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
AUTHOR = ROOT / "docs" / "human_fall" / "evidence" / "2026-10-03_gl_i05_r1" / "research_01"
PACKAGE = ROOT / "src" / "human_fall_detection"
sys.path[:0] = [str(PACKAGE), str(PACKAGE / "scripts"), str(AUTHOR), str(HERE)]

import numpy as np                                                  # noqa: E402
import experiment                                                   # noqa: E402
from core import ground as g                                       # noqa: E402
from search_prototype import search                                # noqa: E402

results = []


def check(name, ok, detail=None):
    results.append({"name": name, "ok": bool(ok), "detail": detail})


def unique_count(witnesses):
    return len({(tuple(w["normal"]), w["offset_m"], w["support_count"])
                for w in witnesses})


def close_fixture():
    for kind, seed in (("clean", 7), ("noise", 7), ("noise", 41)):
        points, rows, regions = experiment.scene(kind, seed, False)
        settings = g.resolve_constrained_settings({"seed": seed, "spatial_cell_m": .05,
                                                   "max_points_per_cell": 8})
        up = [0., 0., 1.]
        base = g.fit_ground_plane_constrained(points, settings, "fixture", up, (.5, 2.),
                                              rows, "fit", regions)
        sampled, valid_rows, events = __import__("core.ground_diagnostics",
                                                 fromlist=["replay_sequence"]).replay_sequence(
            points, rows, np.asarray(up, dtype=float), (.5, 2.), settings)
        refined = []
        from core.ground_diagnostics import refine_hypothesis
        for event in events:
            if event["stage"] == "qualified":
                item, _ = refine_hypothesis(points, sampled, valid_rows, event,
                                            np.asarray(up, dtype=float), (.5, 2.), settings)
                if item is not None:
                    refined.append(item)
        budget = min(512, unique_count(refined) + 8)
        rep = search(points, rows, up, (.5, 2.), settings, candidate_budget=budget)
        check("close_fixture_%s_%d" % (kind, seed),
              rep["status"] in ("seen_pairwise_closed", "seen_dominant_pool_closed")
              and not rep["reasons"],
              {"status": rep["status"], "reasons": rep["reasons"],
               "budget": budget, "unique": len(refined),
               "baseline_status": base["status"]})


def cost_audit():
    slow = json.loads((AUTHOR / "experiment_results_oracle_pairwise_slow.json").read_text(encoding="utf-8"))
    final = json.loads((AUTHOR / "experiment_results_final.json").read_text(encoding="utf-8"))

    def proto_times(doc, section):
        return [e["prototype"]["elapsed_s"] for e in doc[section]]

    s_syn = proto_times(slow, "synthetic")
    f_syn = proto_times(final, "synthetic")
    s_real = proto_times(slow, "real_WHAT_IF")
    f_real = proto_times(final, "real_WHAT_IF")
    detail = {"synthetic": {"slow_median": statistics.median(s_syn),
                            "slow_max": max(s_syn),
                            "final_median": statistics.median(f_syn),
                            "final_max": max(f_syn)},
              "real": {"slow": s_real, "final": f_real}}
    check("synthetic_vectorised_search_faster",
          statistics.median(f_syn) < statistics.median(s_syn), detail)
    # no per-case timing anywhere near the narrative "46s/case"
    max_recorded = max(s_syn + s_real)
    check("narrative_46s_not_in_slow_artifact", max_recorded < 46.0,
          {"max_recorded_seconds": max_recorded,
           "note": "return/00_diag say 46s/case oracle; preserved slow ledger "
                   "max prototype.elapsed_s is %.2fs" % max_recorded})
    # entry.elapsed_s (staged) exists only in the final ledger
    check("staged_timing_only_in_final",
          "elapsed_s" not in final["synthetic"][0] is False
          and "elapsed_s" not in slow["synthetic"][0],
          {"final_has_staged": "elapsed_s" in final["synthetic"][0],
           "slow_has_staged": "elapsed_s" in slow["synthetic"][0]})


def main():
    close_fixture()
    cost_audit()
    passed = sum(1 for r in results if r["ok"])
    out = {"kind": "gli05_second_review_cost_corrections",
           "passed": passed, "total": len(results), "results": results}
    with (HERE / "07b_cost_corrections.json").open("x", encoding="utf-8") as handle:
        json.dump(out, handle, ensure_ascii=False, allow_nan=False, indent=2)
    print(json.dumps(out, ensure_ascii=False, indent=1)[:2500])


if __name__ == "__main__":
    main()

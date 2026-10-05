"""GL-I05 R1 second review: ledger validation, coverage, staging, repeats, memory.

Read-only. Recomputes the three metrics over every stored prototype witness set
with the independent scalar oracle (from 02), checks the processing-count
identities and case coverage, re-runs representative cases through the real
`refine_hypothesis` path to confirm repeatability/counters, and records a
tracemalloc peak for the ungenerated no-cache prototype. Writes only into this
review directory.
"""
import importlib.util
import json
import sys
import time
import tracemalloc
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
AUTHOR = ROOT / "docs" / "human_fall" / "evidence" / "2026-10-03_gl_i05_r1" / "research_01"
PACKAGE = ROOT / "src" / "human_fall_detection"
sys.path[:0] = [str(PACKAGE), str(PACKAGE / "scripts"), str(AUTHOR), str(HERE)]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


scalar = load("gl_i05_rev02", HERE / "02_independent_oracle.py")
import experiment                                                  # noqa: E402
from search_prototype import search                                # noqa: E402
from core import ground as g                                       # noqa: E402

SETTINGS = {"distinct_normal_deg": 10.0, "distinct_offset_m": 0.05,
            "support_close_ratio": 0.8}
results = []


def check(name, ok, detail=None):
    results.append({"name": name, "ok": bool(ok), "detail": detail})


def main():
    ledger_path = AUTHOR / "experiment_results_final.json"
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    entries = ledger["synthetic"] + ledger["real_WHAT_IF"]

    # --- coverage -----------------------------------------------------------
    expected = {"%s_seed%d_permute%s" % (k, s, p)
                for k in ("clean", "noise", "high_noise", "dual", "close")
                for s in (7, 19, 41) for p in ("False", "True")}
    got = {e["case"] for e in ledger["synthetic"]}
    check("coverage_30_synthetic", expected == got,
          {"missing": sorted(expected - got), "extra": sorted(got - expected)})
    check("coverage_real_labels",
          [e["case"] for e in ledger["real_WHAT_IF"]] == ["approved", "negative_X"],
          [e["case"] for e in ledger["real_WHAT_IF"]])
    check("ledger_physical_false", ledger.get("physical_verified") is False)
    check("ledger_local_runtime_board_false",
          ledger.get("local_runtime", {}).get("board_run") is False)

    # --- per-case independent re-derivation ---------------------------------
    status_mismatch, metric_mismatch, count_mismatch, oracle_flag_mismatch = [], [], [], []
    for entry in entries:
        ws = entry["prototype"]["witnesses"]
        witnesses = [scalar.w(x["normal"], x["offset_m"], x["support_count"]) for x in ws]
        mine = scalar.scalar_oracle(witnesses, SETTINGS)
        proto = entry["prototype"]
        if mine["status"] != proto["status"]:
            status_mismatch.append({"case": entry["case"], "mine": mine["status"],
                                    "recorded": proto["status"]})
        for key in ("ALL", "NEAR", "BEST_ONLY"):
            my_holds = not (
                (mine["all_pairs"] if key == "ALL" else
                 mine["near_pairs"] if key == "NEAR" else mine["best_only_pairs"]))
            if my_holds != proto["metrics"][key]["holds"]:
                metric_mismatch.append({"case": entry["case"], "metric": key,
                                        "mine": my_holds,
                                        "recorded": proto["metrics"][key]["holds"]})
        c = proto["counts"]
        ok = (c["qualified"] == c["unprocessed"] + c["refined_calls"]
              and c["refined_calls"] == c["rejected"] + c["produced"]
              and c["produced"] == c["merged_exact"] + c["retained"] + c["unstored"]
              and c["peak_stored"] <= entry["candidate_budget_used"])
        if not ok:
            count_mismatch.append({"case": entry["case"], "counts": c})
        # author's own oracle_match flag must agree with recorded statuses
        if entry["oracle_match"] != (proto["status"] == entry["oracle"]["status"]):
            oracle_flag_mismatch.append(entry["case"])
    check("status_matches_independent_scalar", not status_mismatch, status_mismatch[:5])
    check("ALL_NEAR_metrics_match", not metric_mismatch,
          {"mismatches": metric_mismatch[:8]})
    check("counts_identities_hold", not count_mismatch, count_mismatch[:5])
    check("oracle_match_flag_consistent", not oracle_flag_mismatch, oracle_flag_mismatch[:5])

    # every closure-safe flag must be consistent with an unresolved gap or parity
    unsafe = [e["case"] for e in entries
              if e["closure_safe"] is not True and e["prototype"]["status"]
              in ("seen_pairwise_closed", "seen_dominant_pool_closed")]
    check("no_closed_case_without_safe_flag", not unsafe, unsafe)

    # --- representative rerun: repeatability + real counters + memory -------
    points, rows, regions = experiment.scene("noise", 7, False)
    settings = g.resolve_constrained_settings({"seed": 7, "spatial_cell_m": .05,
                                               "max_points_per_cell": 8})
    up = [0., 0., 1.]
    tracemalloc.start()
    first = search(points, rows, up, (.5, 2.), settings, candidate_budget=64)
    peak = tracemalloc.get_traced_memory()[1]
    tracemalloc.stop()
    second = search(points, rows, up, (.5, 2.), settings, candidate_budget=64)
    deterministic = ({k: v for k, v in first.items() if k != "elapsed_s"}
                     == {k: v for k, v in second.items() if k != "elapsed_s"})
    check("search_repeat_deterministic", deterministic)
    check("search_memory_peak_recorded", peak > 0, {"peak_bytes": peak})

    # stage timing split must be present and additive
    entry = ledger["synthetic"][0]
    timing_ok = (set(entry["elapsed_s"]) ==
                 {"baseline_fit", "research_search", "scoreboard_total"}
                 and abs(entry["elapsed_s"]["scoreboard_total"]
                         - (entry["elapsed_s"]["baseline_fit"]
                            + entry["elapsed_s"]["research_search"])) < 1e-9
                 and abs(entry["elapsed_s"]["baseline_fit"]
                         - entry["baseline_elapsed_s"]) < 1e-9)
    check("stage_timing_split_additive", timing_ok, entry["elapsed_s"])

    # slow-oracle ledger preserved as cost counterexample
    slow = AUTHOR / "experiment_results_oracle_pairwise_slow.json"
    slow_ok = slow.is_file()
    slow_size = slow.stat().st_size if slow_ok else 0
    check("slow_oracle_counterexample_present", slow_ok, {"size": slow_size})

    passed = sum(1 for r in results if r["ok"])
    out = {"kind": "gli05_second_review_ledger",
           "passed": passed, "total": len(results),
           "peak_bytes_no_cache_search": peak,
           "results": results}
    with (HERE / "03_ledger_and_budget.json").open("x", encoding="utf-8") as handle:
        json.dump(out, handle, ensure_ascii=False, allow_nan=False, indent=2)
    print("SUMMARY %d/%d PASS peak=%d" % (passed, len(results), peak))


if __name__ == "__main__":
    main()

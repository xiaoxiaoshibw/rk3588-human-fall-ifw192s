"""GL-I05 R1 second review: budget/gap fixtures, per-event trace mapping,
frozen-baseline/replay parity, Python 3.8 AST, no-cache audit and cost evidence.

Read-only. Writes only into this review directory.
"""
import ast
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
from search_prototype import search, search_events                 # noqa: E402

results = []


def check(name, ok, detail=None):
    results.append({"name": name, "ok": bool(ok), "detail": detail})


def plane(offset, support, up_deg=0.0):
    import math
    return {"normal": [math.sin(math.radians(up_deg)), 0.0,
                       math.cos(math.radians(up_deg))],
            "offset_m": offset, "support_count": support}


def events(planes):
    return [dict(p, iteration=i, stage="qualified") for i, p in enumerate(planes)]


def identity_refine(event):
    return ({"normal": list(event["normal"]), "offset_m": event["offset_m"],
             "support_count": event["support_count"]}, "refined")


SETTINGS = g.resolve_constrained_settings({"seed": 7, "spatial_cell_m": .05,
                                           "max_points_per_cell": 8})


def gap_semantics():
    # a processing gap (unprocessed qualified hypothesis) must not vanish when
    # a later, stronger best arrives.
    late = [plane(1.0, 200)] * 4 + [plane(1.0, 900)] + [plane(1.14, 200)]
    rep = search_events(events(late), identity_refine, SETTINGS, refine_budget=4)
    check("late_strong_best_cannot_heal_gap",
          rep["status"] == "unresolved" and rep["counts"]["unprocessed"] == 2
          and "unprocessed_qualified_hypothesis" in rep["reasons"],
          {"status": rep["status"], "counts": rep["counts"]})
    # trace budget gap with late best
    rep2 = search_events(events([plane(1.0, 200)] * 4 + [plane(1.0, 900)]),
                         identity_refine, SETTINGS, trace_budget=3)
    check("trace_gap_blocks_late_best",
          rep2["status"] == "unresolved"
          and "trace_budget_incomplete" in rep2["reasons"], rep2["reasons"])
    # candidate budget unstored distinct witness
    rep3 = search_events(events([plane(1.0, 200), plane(1.14, 200)]),
                         identity_refine, SETTINGS, candidate_budget=1)
    check("candidate_gap_blocks_closure",
          rep3["status"] == "unresolved" and rep3["counts"]["unstored"] == 1
          and "candidate_budget_incomplete" in rep3["reasons"], rep3["counts"])
    # iteration budget: qualified event beyond iteration budget
    many = [plane(1.0, 200)] * 6
    rep4 = search_events(events(many), identity_refine, SETTINGS, iteration_budget=3)
    check("iteration_gap_blocks_closure",
          rep4["status"] == "unresolved"
          and "iteration_budget_incomplete" in rep4["reasons"], rep4["reasons"])


def trace_mapping():
    points, rows, regions = experiment.scene("noise", 7, False)
    up = [0., 0., 1.]
    rep = search(points, rows, up, (.5, 2.), SETTINGS, candidate_budget=64)
    trace = rep["trace"]
    c = rep["counts"]
    check("trace_draws_seen_identity",
          c["draws_seen"] == len(trace) + c["trace_unrecorded"],
          {"draws": c["draws_seen"], "trace": len(trace),
           "unrecorded": c["trace_unrecorded"]})
    indices = [r["sequence_index"] for r in trace]
    check("trace_indices_monotonic", indices == sorted(indices)
          and indices == list(range(len(trace))), indices[:5])
    actions = {}
    for r in trace:
        actions[r["action"]] = actions.get(r["action"], 0) + 1
    check("trace_action_counts_consistent",
          actions.get("refined_rejected", 0) == c["rejected"]
          and actions.get("budget_unprocessed", 0) == c["unprocessed"]
          and (actions.get("retained_witness", 0)
               + actions.get("merged_exact", 0)
               + actions.get("candidate_budget_unstored", 0)) == c["produced"],
          {"actions": actions, "counts": c})
    check("clean_low_noise_closes",
          rep["status"] in ("seen_pairwise_closed", "seen_dominant_pool_closed"),
          {"status": rep["status"], "reasons": rep["reasons"]})


def baseline_parity():
    for kind, seed in (("clean", 7), ("high_noise", 19), ("dual", 41)):
        try:
            points, rows, regions = experiment.scene(kind, seed, False)
            settings = g.resolve_constrained_settings({"seed": seed,
                                                       "spatial_cell_m": .05,
                                                       "max_points_per_cell": 8})
            entry = experiment.compare("%s_seed%d" % (kind, seed), points, rows,
                                       regions, np.array([0., 0., 1.]), (.5, 2.),
                                       settings)
        except AssertionError as exc:
            check("baseline_parity_%s_%d" % (kind, seed), False, repr(exc))
            continue
        check("baseline_parity_%s_%d" % (kind, seed), entry["oracle_match"],
              {"status": entry["prototype"]["status"],
               "oracle": entry["oracle"]["status"],
               "safe": entry["closure_safe"]})


def python38_ast():
    allowed_roots = {"math", "json", "hashlib", "itertools", "random", "sys",
                     "time", "pathlib", "traceback", "numpy", "core",
                     "oracle_analysis", "search_prototype",
                     "evaluate_gli02_candidate", "experiment"}
    for name in ("oracle_analysis.py", "search_prototype.py", "experiment.py",
                 "test_gli05_research.py", "source_review.py"):
        source = (AUTHOR / name).read_text(encoding="utf-8")
        try:
            tree = ast.parse(source, filename=name, feature_version=(3, 8))
        except SyntaxError as exc:
            check("py38_ast_" + name, False, repr(exc))
            continue
        roots = set()
        local = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                roots.add(node.module.split(".")[0])
        bad = roots - allowed_roots
        check("py38_ast_" + name, not bad, {"unexpected_imports": sorted(bad)})


def no_cache_audit():
    text = ""
    for name in ("oracle_analysis.py", "search_prototype.py", "experiment.py",
                 "test_gli05_research.py", "source_review.py"):
        text += (AUTHOR / name).read_text(encoding="utf-8")
    lowered = text.lower()
    markers = ["lru_cache", "functools.cache", "cache[", "cache =", "cache=",
               "cache_key", "cache_hit", "cache_miss", "_cache"]
    hits = [m for m in markers if m in lowered]
    check("no_persistent_or_refine_cache", not hits, {"markers": hits})
    # negative evidence: the slow oracle ledger is preserved
    check("slow_oracle_ledger_preserved",
          (AUTHOR / "experiment_results_oracle_pairwise_slow.json").is_file())


def cost_evidence():
    final = json.loads((AUTHOR / "experiment_results_final.json").read_text(encoding="utf-8"))
    slow = json.loads((AUTHOR / "experiment_results_oracle_pairwise_slow.json").read_text(encoding="utf-8"))

    def collect(doc):
        out = []
        for entry in doc.get("synthetic", []):
            el = entry.get("elapsed_s", {})
            if isinstance(el, dict) and "research_search" in el:
                out.append(el["research_search"])
            elif isinstance(el, dict) and "search_total" in el:
                out.append(el["search_total"])
        return out

    fast = collect(final)
    slowt = collect(slow)
    check("final_ledger_has_search_times", len(fast) == 30, len(fast))
    check("slow_ledger_present_times", len(slowt) > 0,
          {"count": len(slowt),
           "median": statistics.median(slowt) if slowt else None})
    ratios = final.get("synthetic", [{}])[0].get("elapsed_s", {})
    check("vectorised_faster_than_slow",
          bool(slowt) and bool(fast) and statistics.median(fast) < statistics.median(slowt),
          {"fast_median": statistics.median(fast) if fast else None,
           "slow_median": statistics.median(slowt) if slowt else None})


def main():
    gap_semantics()
    trace_mapping()
    baseline_parity()
    python38_ast()
    no_cache_audit()
    cost_evidence()
    passed = sum(1 for r in results if r["ok"])
    out = {"kind": "gli05_second_review_budget_trace_ast",
           "passed": passed, "total": len(results), "results": results}
    with (HERE / "07_budget_trace_ast.json").open("x", encoding="utf-8") as handle:
        json.dump(out, handle, ensure_ascii=False, allow_nan=False, indent=2)
    print("SUMMARY %d/%d PASS" % (passed, len(results)))
    for r in results:
        if not r["ok"]:
            print("FAIL", r["name"], r["detail"])


if __name__ == "__main__":
    main()

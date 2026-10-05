"""GL-I05 R1 second review: GL-I04-prototype comparison + reason attribution.

Checks whether the submitted experiment directly runs the GL-I04 research
envelope prototype on the same sequence (TASK stage 2 / acceptance C02), and
whether the prototype `reasons` distinguish actual near-pool competition from
budget/certificate gaps (TASK attribution / C03+C05). Writes only here.
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
AUTHOR = ROOT / "docs" / "human_fall" / "evidence" / "2026-10-03_gl_i05_r1" / "research_01"
I04_PROTO = ROOT / "docs" / "human_fall" / "evidence" / "2026-10-03_gl_i04_r1" / "research_01" / "search_prototype.py"

results = []


def check(name, ok, detail=None):
    results.append({"name": name, "ok": bool(ok), "detail": detail})


def main():
    sources = {}
    for name in ("oracle_analysis.py", "search_prototype.py", "experiment.py",
                 "test_gli05_research.py", "source_review.py"):
        sources[name] = (AUTHOR / name).read_text(encoding="utf-8")
    joined = "\n".join(sources.values())
    check("i04_prototype_module_exists", I04_PROTO.is_file())
    check("experiment_imports_i04_prototype",
          "2026-10-03_gl_i04_r1" in joined and "gli04" in joined.lower()
          and "search_prototype" in sources["experiment.py"]
          and "gl_i04" in sources["experiment.py"],
          {"mentions_gl_i04": "gl_i04" in joined.lower(),
           "replay_frozen_search_used": "replay_frozen_search" in sources["experiment.py"]})
    check("replay_frozen_search_is_not_envelope_prototype",
          "replay_frozen_search" in sources["experiment.py"]
          and "similarity_envelope_not_closed" not in joined,
          {"envelope_reason_present": "similarity_envelope_not_closed" in joined})

    ledger = json.loads((AUTHOR / "experiment_results_final.json").read_text(encoding="utf-8"))
    entries = ledger["synthetic"] + ledger["real_WHAT_IF"]
    unresolved = [e for e in entries if e["prototype"]["status"] == "unresolved"]
    # Does an unresolved case ever report actual NEAR distinct but no reason?
    silent = []
    budget_only = []
    for e in unresolved:
        near = e["prototype"]["metrics"]["NEAR"]
        has_near_distinct = near["distinct_pair_count"] > 0
        reasons = set(e["prototype"]["reasons"])
        if has_near_distinct and not reasons:
            silent.append({"case": e["case"],
                           "near_distinct": near["distinct_pair_count"]})
        if reasons and not has_near_distinct:
            budget_only.append({"case": e["case"], "reasons": sorted(reasons)})
    check("unresolved_actual_competition_has_no_reason", not silent,
          {"silent_actual_competition": silent[:6],
           "note": "actual near-pool distinct is not added to reasons; it is only "
                   "visible in metrics.NEAR.distinct_pairs"})
    reason_vocab = sorted({r for e in entries for r in e["prototype"]["reasons"]})
    check("no_certificate_insufficient_reason",
          "similarity_envelope_not_closed" not in reason_vocab,
          {"reason_vocabulary": reason_vocab})

    # aggregation: how many unresolved are strictly budget-gap vs actual distinct
    actual = [e["case"] for e in unresolved
              if e["prototype"]["metrics"]["NEAR"]["distinct_pair_count"] > 0]
    gaps = [e["case"] for e in unresolved
            if e["prototype"]["reasons"]]
    check("unresolved_case_count", len(unresolved) == 18,
          {"unresolved": len(unresolved), "actual_near_distinct": len(actual),
           "with_reasons": len(gaps)})

    passed = sum(1 for r in results if r["ok"])
    out = {"kind": "gli05_second_review_comparison_reasons",
           "passed": passed, "total": len(results),
           "unresolved_actual_distinct_cases": actual,
           "unresolved_with_reasons_cases": gaps,
           "results": results}
    with (HERE / "10_comparison_and_reasons.json").open("x", encoding="utf-8") as handle:
        json.dump(out, handle, ensure_ascii=False, allow_nan=False, indent=2)
    print("SUMMARY %d/%d PASS" % (passed, len(results)))
    for r in results:
        print(("PASS " if r["ok"] else "FAIL ") + r["name"],
              "" if r["ok"] else json.dumps(r["detail"], ensure_ascii=False)[:400])


if __name__ == "__main__":
    main()

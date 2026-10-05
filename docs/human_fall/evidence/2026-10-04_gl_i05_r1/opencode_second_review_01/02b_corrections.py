"""GL-I05 R1 second review: corrected expectations for the two mislabelled
hand fixtures in 02_independent_oracle.py (my test labels were wrong; the
author oracle and my scalar oracle already agreed). The genuine BEST_ONLY
finding is re-confirmed here and scanned across the submitted ledger.

New numbered script/output; does not overwrite 02_*.
"""
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


m = load("gl_i05_rev02", "02_independent_oracle.py")
results = []


def check(name, ok, detail=None):
    results.append({"name": name, "ok": bool(ok), "detail": detail})


# corrected expectations
cases = [
    ("boundary_inside_080", [m.plane(1.0, 500), m.plane(1.2, 400)], "unresolved"),
    ("boundary_outside_0799", [m.plane(1.0, 500), m.plane(1.2, 399)],
     "seen_dominant_pool_closed"),
    ("below_pool_similar", [m.plane(1.0, 500), m.plane(1.01, 399)],
     "seen_pairwise_closed"),
]
for name, witnesses, expected in cases:
    mine = m.scalar_oracle(witnesses)
    author = m.author_oracle(witnesses, m.SETTINGS)
    check("corrected_%s" % name,
          mine["status"] == expected and author["status"] == expected,
          {"mine": mine["status"], "author": author["status"], "want": expected})

# genuine BEST_ONLY finding: best at index 1, distinct near member at index 0.
witnesses = [m.plane(1.2, 450), m.plane(1.0, 500)]
mine = m.scalar_oracle(witnesses)
author = m.author_oracle(witnesses, m.SETTINGS)
author_best_only = {tuple(sorted(p)) for p in
                    author["metrics"]["BEST_ONLY"]["distinct_pairs"]}
check("best_only_holds_masks_best_vs_earlier_near",
      bool(mine["best_only_pairs"]) and author["metrics"]["BEST_ONLY"]["holds"] is True
      and not author_best_only,
      {"my_best_only_pairs": mine["best_only_pairs"],
       "author_best_only_pairs": sorted(author_best_only),
       "author_holds": author["metrics"]["BEST_ONLY"]["holds"]})

# scan the submitted ledger: for every case, recompute an independent
# BEST_ONLY over the stored prototype witnesses and compare with the recorded
# author BEST_ONLY. A mismatch is the index-asymmetry defect surfacing in
# submitted evidence.
ledger_path = HERE.parents[1] / "2026-10-03_gl_i05_r1" / "research_01" / "experiment_results_final.json"
ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
settings = dict(m.SETTINGS)
mismatches = []
for entry in ledger["synthetic"] + ledger["real_WHAT_IF"]:
    ws = entry["prototype"]["witnesses"]
    # rebuild witness dicts with the keys the metrics need
    norm = [x["normal"] for x in ws]
    offs = [x["offset_m"] for x in ws]
    sups = [x["support_count"] for x in ws]
    witnesses = [m.w(n, o, s) for n, o, s in zip(norm, offs, sups)]
    mine = m.scalar_oracle(witnesses, settings)
    my_holds = not mine["best_only_pairs"]
    rec = entry["prototype"]["metrics"]["BEST_ONLY"]
    if my_holds != rec["holds"] or len(mine["best_only_pairs"]) != rec["distinct_pair_count"]:
        mismatches.append({"case": entry["case"],
                           "my_holds": my_holds, "recorded_holds": rec["holds"],
                           "my_count": len(mine["best_only_pairs"]),
                           "recorded_count": rec["distinct_pair_count"],
                           "status": entry["prototype"]["status"]})
check("ledger_best_only_consistent", not mismatches,
      {"mismatch_count": len(mismatches), "examples": mismatches[:8]})

out = {"kind": "gli05_second_review_corrections",
       "passed": sum(1 for r in results if r["ok"]), "total": len(results),
       "results": results}
with (HERE / "02b_corrections.json").open("x", encoding="utf-8") as handle:
    json.dump(out, handle, ensure_ascii=False, allow_nan=False, indent=2)
print(json.dumps({"passed": out["passed"], "total": out["total"],
                  "ledger_best_only_mismatches": len(mismatches),
                  "examples": mismatches[:5]}, ensure_ascii=False))

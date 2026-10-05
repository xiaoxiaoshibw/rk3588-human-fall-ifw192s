"""GL-I05 R1 second review: corrected staged-timing check.

07b_* used a chained comparison (`a not in b is False`) that evaluated False.
This new script states the intended property directly: the staged
baseline_fit/research_search/scoreboard_total timing exists only in the final
ledger, not the earlier slow-oracle ledger.
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AUTHOR = HERE.parents[1] / "2026-10-03_gl_i05_r1" / "research_01"
final = json.loads((AUTHOR / "experiment_results_final.json").read_text(encoding="utf-8"))
slow = json.loads((AUTHOR / "experiment_results_oracle_pairwise_slow.json").read_text(encoding="utf-8"))
final_has = "elapsed_s" in final["synthetic"][0]
slow_has = "elapsed_s" in slow["synthetic"][0]
ok = final_has and not slow_has
out = {"kind": "gli05_second_review_staged_timing",
       "passed": 1 if ok else 0, "total": 1,
       "final_staged": final_has, "slow_staged": slow_has,
       "results": [{"name": "staged_timing_only_in_final", "ok": ok,
                    "detail": {"final_staged": final_has, "slow_staged": slow_has}}]}
with (HERE / "07c_staged_timing_check.json").open("x", encoding="utf-8") as handle:
    json.dump(out, handle, ensure_ascii=False, allow_nan=False, indent=2)
print(json.dumps(out, ensure_ascii=False))

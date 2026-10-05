import collections
import json
from pathlib import Path
import statistics

OUT = Path(__file__).resolve().parent
data = json.loads((OUT / "research_01/experiment_results.json").read_text(encoding="utf-8"))
summary = {}
for kind in ("clean", "noise", "high_noise", "dual", "close"):
    rows = [row for row in data["synthetic"] if row["case"].startswith(kind + "_")]
    summary[kind] = {"prototype_statuses": dict(collections.Counter(row["prototype"]["status"] for row in rows)),
                     "oracle_statuses": dict(collections.Counter(row["oracle"]["status"] for row in rows)),
                     "baseline_status_reasons": dict(collections.Counter(str(row["baseline"]["status"]) + "/" + str(row["baseline"]["reason"]) for row in rows)),
                     "prototype_median_seconds": statistics.median(row["prototype"]["elapsed_s"] for row in rows),
                     "baseline_median_seconds": statistics.median(row["baseline_elapsed_s"] for row in rows),
                     "max_retained": max(row["prototype"]["counts"]["peak_retained"] for row in rows),
                     "max_refined": max(row["prototype"]["counts"]["refined"] for row in rows)}
summary["real_WHAT_IF"] = [{"label": row["case"], "prototype_status": row["prototype"]["status"],
                             "reasons": row["prototype"]["reasons"], "counts": row["prototype"]["counts"],
                             "baseline_status": row["baseline"]["status"], "baseline_reason": row["baseline"]["reason"],
                             "oracle": row["oracle"]} for row in data["real_WHAT_IF"]]
with (OUT / "16_research_summary.json").open("x", encoding="utf-8") as handle:
    json.dump(summary, handle, indent=2)
print(json.dumps(summary, indent=2))

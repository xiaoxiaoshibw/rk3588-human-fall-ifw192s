"""Planning only: recompute metrics from the closed GL-I04 ledger, no new draws."""
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
SOURCE = ROOT / "docs/human_fall/evidence/2026-10-03_gl_i04_r1/research_01/experiment_results_final.json"
raw = SOURCE.read_bytes()
ledger = json.loads(raw)
records = []
for record in ledger["synthetic"] + ledger["real_WHAT_IF"]:
    prototype = record["prototype"]
    items = [event["refined"] for event in prototype["trace"] if event.get("refined")]
    maximum = max((item["support_count"] for item in items), default=0)
    near = [item for item in items if item["support_count"] >= .8 * maximum]
    top = [item for item in items if item["support_count"] == maximum]
    def count_distinct(first, second, upper=False):
        if not first or not second:
            return 0
        normals_a = np.asarray([item["normal"] for item in first])
        normals_b = np.asarray([item["normal"] for item in second])
        offsets_a = np.asarray([item["offset_m"] for item in first])
        offsets_b = np.asarray([item["offset_m"] for item in second])
        angle = np.degrees(np.arccos(np.clip(normals_a @ normals_b.T, -1, 1)))
        distinct = (angle > 10.) | (np.abs(offsets_a[:, None] - offsets_b[None, :]) > .05)
        return int(np.count_nonzero(np.triu(distinct, 1) if upper else distinct))
    assert prototype["counts"]["trace_unrecorded"] == 0
    assert prototype["counts"]["qualified"] == prototype["counts"]["refined"]
    records.append({"case": record["case"], "seed": record["seed"],
                    "refined": len(items), "best_support": maximum,
                    "near_pool_count": len(near), "top_tie_count": len(top),
                    "all_pair_distinct_count": count_distinct(items, items, True),
                    "near_pool_distinct_count": count_distinct(near, near, True),
                    "top_to_near_distinct_count": count_distinct(top, near),
                    "I04_status": prototype["status"], "I04_reasons": prototype["reasons"],
                    "scope": "same recorded finite sequence only; pair count includes repeated witnesses"})
assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == hashlib.sha256(raw).hexdigest()
result = {"kind": "gli05_planning_existing_trace_audit", "new_experiments_run": False,
          "source_path": str(SOURCE), "source_sha256": hashlib.sha256(raw).hexdigest(),
          "rules": {"near_ratio": .8, "distinct_deg": 10., "distinct_offset_m": .05,
                    "note": "metrics only, no changed I04 result/production gate/validation point selection"},
          "runtime": {"python": sys.version, "numpy": np.__version__}, "records": records}
with (OUT / "02_existing_trace_audit.json").open("x", encoding="utf-8") as handle:
    json.dump(result, handle, ensure_ascii=False, indent=2, allow_nan=False)
print(json.dumps({"records": len(records), "new_experiments_run": False,
                  "unsafe_top_only_counterexamples": [record["case"] for record in records
                      if record["top_to_near_distinct_count"] == 0 and record["near_pool_distinct_count"] > 0]}))

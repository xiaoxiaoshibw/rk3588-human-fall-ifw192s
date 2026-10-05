"""GL-I05 R1 second review: corrected source-view checks.

The only mismatch in 04_* was my comparison `payload["stats_count_mismatches"] == 0`
against the author's empty *list* (correct value is `[]`). This new numbered
script re-checks the two affected properties from the already-regenerated
payload; it does not overwrite 04_* outputs.
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
payload_html = (HERE / "04_source_review_regen.html").read_text(encoding="utf-8")
start = payload_html.index("const D=") + len("const D=")
payload, _ = json.JSONDecoder().raw_decode(payload_html[start:])

results = []
mism = payload["stats_count_mismatches"]
results.append({"name": "stats_count_mismatches_empty_list", "ok": mism == [],
                "detail": {"value": mism}})
results.append({"name": "stats_count_mismatches_len_zero", "ok": len(mism) == 0,
                "detail": {"len": len(mism)}})
out = {"kind": "gli05_second_review_source_view_correction",
       "passed": sum(1 for r in results if r["ok"]), "total": len(results),
       "results": results}
with (HERE / "04b_source_review_correction.json").open("x", encoding="utf-8") as handle:
    json.dump(out, handle, ensure_ascii=False, allow_nan=False, indent=2)
print(json.dumps(out, ensure_ascii=False))

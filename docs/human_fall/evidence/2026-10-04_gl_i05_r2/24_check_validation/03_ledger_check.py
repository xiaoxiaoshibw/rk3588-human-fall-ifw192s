"""Parse the ACTIVE R2 ledger programmatically and re-derive key invariants.

Does not load the 3MB JSON into chat context; writes only a concise summary.
"""
import itertools
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
RUN = Path(__file__).resolve().parents[1]
RES = RUN / "research_01"
PACKAGE = ROOT / "src" / "human_fall_detection"
sys.path[:0] = [str(PACKAGE), str(PACKAGE / "scripts"), str(RES)]

import numpy as np
from core import ground as g
from search_prototype import search_events

LEDGER = RES / "experiment_results_identity_verified.json"


def identity_refine(event):
    return ({"normal": list(event["normal"]), "offset_m": event["offset_m"],
             "support_count": event["support_count"]}, "refined")


def unit(v):
    v = np.asarray(v, float)
    return (v / np.linalg.norm(v)).tolist()


def plane(offset, support, deg=0.0):
    return {"normal": unit([math.sin(math.radians(deg)), 0, math.cos(math.radians(deg))]),
            "offset_m": offset, "support_count": support}


def scalar_status_full(ws):
    n = len(ws)
    def dist(a, b):
        dot = max(-1., min(1., sum(x * y for x, y in zip(a["normal"], b["normal"]))))
        return math.degrees(math.acos(dot)) > 10 or abs(a["offset_m"] - b["offset_m"]) > .05
    pairs = [[i, j] for i, j in itertools.combinations(range(n), 2) if dist(ws[i], ws[j])]
    s = max(w["support_count"] for w in ws)
    near = {i for i, w in enumerate(ws) if w["support_count"] >= .8 * s}
    npairs = [p for p in pairs if set(p) <= near]
    if not ws or npairs:
        return "unresolved"
    return "seen_dominant_pool_closed" if pairs else "seen_pairwise_closed"


def counts_ok(c):
    return (c["qualified"] == c["unprocessed"] + c["refined_calls"]
            and c["refined_calls"] == c["rejected"] + c["produced"]
            and c["produced"] == c["merged_exact"] + c["retained"] + c["unstored"])


def main():
    data = json.loads(LEDGER.read_text(encoding="utf-8"))
    out = {"script": "03_ledger_check", "ledger": LEDGER.name}
    syn, real = data["synthetic"], data["real_WHAT_IF"]
    cases = syn + real
    out["synthetic_cases"] = len(syn)
    out["real_cases"] = len(real)
    out["all_oracle_match"] = all(c["oracle_match"] for c in cases)
    out["all_closure_safe"] = all(c["closure_safe"] for c in cases)
    out["all_sequence_digest_equal"] = all(
        c["old_sequence_sha256"] == c["prototype_sequence_sha256"] == c["sequence_sha256"]
        for c in cases)
    out["all_have_5_stages_3_repeats"] = all(
        len(c["cost_repeats"]) >= 3
        and all(all(k in r for k in ("sampling", "raw", "refine", "decision",
                                     "serialization", "search_total", "serialized_bytes"))
                for r in c["cost_repeats"])
        for c in cases)
    out["all_peak_positive_separate"] = all(
        c["peak_tracemalloc_bytes"] > 0 and c["memory_measurement_separate_from_timing"]
        for c in cases)
    out["all_counts_identity"] = all(
        counts_ok(c["prototype"]["counts"]) for c in cases)
    out["all_old_i04_seq_match"] = all(
        c["old_i04"]["sequence_iterations_match"] for c in cases)

    # cause attribution coverage
    attr = {"actual_near_pool_competition": 0, "old_certificate_insufficient": 0,
            "processing_budget_gap": 0}
    for c in cases:
        ra = c["rejection_attribution"]
        for k in attr:
            if ra[k]:
                attr[k] += 1
    out["attribution_counts"] = attr
    # any case where old certificate failed but scalar closure held?
    old_fail_scalar_close = [
        {"case": c["case"], "old_status": c["old_i04"]["status"],
         "old_reasons": c["old_i04"]["reasons"], "new_status": c["prototype"]["status"]}
        for c in cases
        if c["rejection_attribution"]["old_certificate_insufficient"]
        and c["prototype"]["status"] in ("seen_pairwise_closed", "seen_dominant_pool_closed")]
    out["old_cert_fail_scalar_closed"] = old_fail_scalar_close

    statuses = {}
    for c in cases:
        statuses[c["prototype"]["status"]] = statuses.get(c["prototype"]["status"], 0) + 1
    out["prototype_status_counts"] = statuses
    weak_dom = [c["case"] for c in syn if c["case"].startswith("weak")
                and c["prototype"]["status"] == "seen_dominant_pool_closed"]
    out["weak_dominant_cases"] = len(weak_dom)

    # prototype metrics vs stored full oracle metrics: contract says the
    # prototype reports exact-sig representatives; only holds/status claimed equal
    holds_mismatch = []
    for c in cases:
        for k in ("ALL", "NEAR", "BEST_ONLY"):
            if c["oracle"]["metrics"][k]["holds"] != c["prototype"]["metrics"][k]["holds"]:
                holds_mismatch.append({"case": c["case"], "metric": k,
                                       "oracle": c["oracle"]["metrics"][k]["holds"],
                                       "proto": c["prototype"]["metrics"][k]["holds"]})
    out["metric_holds_mismatch"] = holds_mismatch
    out["all_metric_holds_agree"] = not holds_mismatch

    # NO claim that pair counts are equal: report if any differ (expected)
    pair_count_diffs = sum(
        1 for c in cases for k in ("ALL", "NEAR", "BEST_ONLY")
        if c["oracle"]["metrics"][k]["distinct_pair_count"]
        != c["prototype"]["metrics"][k]["distinct_pair_count"])
    out["cases_with_pair_count_diff"] = pair_count_diffs

    # --- merge-safety independent probe: exact-signature duplicates ---
    dup_ok = True
    merge_cases = []
    base = [plane(1.0, 200), plane(1.04, 200), plane(1.2, 100)]
    variants = [base * 5, base + base[:1], base * 3]
    for ws in variants:
        ev = [dict(ws[i], iteration=i, stage="qualified") for i in range(len(ws))]
        rep = search_events(ev, identity_refine, g.resolve_constrained_settings())
        if rep["status"] != scalar_status_full(ws):
            dup_ok = False
            merge_cases.append({"proto": rep["status"], "scalar": scalar_status_full(ws)})
    out["merge_safety_ok"] = dup_ok
    out["merge_safety_detail"] = merge_cases

    out["active_ledger_matches_manifest"] = data.get("kind") == "gli05_experiment_ledger"
    out["local_runtime"] = data.get("local_runtime")

    (Path(__file__).resolve().parent / "03_ledger_check.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if k not in ("local_runtime",)},
                     ensure_ascii=False)[:1800])


if __name__ == "__main__":
    main()

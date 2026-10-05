"""Bounded conservative research only. Not imported by runtime/core/CLI.

Protocol similarity is NOT equivalence. A fixed-anchor angular envelope and
offset span certify all merged witnesses are pairwise similar. Every result
outside that sufficient certificate preserves an unresolved flag, even when
the stored representative pair alone looks similar. No moving representative.
"""
import time

from core.ground_diagnostics import refine_hypothesis, replay_sequence, similar
from core import ground as g


def search_events(events, refine, settings, candidate_budget=128,
                  refine_budget=2000, trace_budget=2000, iteration_budget=2000):
    budgets = {"candidate": candidate_budget, "refine": refine_budget,
               "trace": trace_budget, "iteration": iteration_budget}
    ceilings = {"candidate": 512, "refine": 2000, "trace": 2000, "iteration": 2000}
    for key, value in budgets.items():
        if type(value) is not int or not 0 <= value <= ceilings[key]:
            raise ValueError("invalid bounded " + key + " budget")
    settings = g.resolve_constrained_settings(settings)
    start = time.perf_counter()
    witnesses, trace, reasons = [], [], set()
    envelope = None
    counts = {"draws_seen": 0, "qualified": 0, "refined": 0, "rejected": 0,
              "retained": 0, "merged_exact": 0, "merged_certified": 0, "unprocessed": 0,
              "trace_unrecorded": 0, "unstored": 0, "peak_retained": 0}
    for event in events:
        index = counts["draws_seen"]
        counts["draws_seen"] += 1
        record = {"sequence_index": index, "iteration": event["iteration"],
                  "raw_stage": event["stage"], "action": "raw_rejected"}
        record["raw_hypothesis"] = {key: event[key] for key in
                                    ("normal", "offset_m", "support_count", "draw_rows") if key in event}
        if index >= iteration_budget:
            reasons.add("iteration_budget_incomplete")
        if event["stage"] == "qualified":
            counts["qualified"] += 1
            if index >= iteration_budget or counts["refined"] >= refine_budget:
                reasons.add("unprocessed_qualified_hypothesis")
                counts["unprocessed"] += 1
                record["action"] = "budget_unprocessed"
            else:
                counts["refined"] += 1
                item, rejection = refine(event)
                record["refine_reason"] = rejection
                record["refined"] = item
                if item is None:
                    counts["rejected"] += 1
                    record["action"] = "refined_rejected"
                else:
                    signature = tuple(item["normal"]) + (item["offset_m"], item["support_count"])
                    old = next((i for i, value in enumerate(witnesses) if
                                tuple(value["normal"]) + (value["offset_m"], value["support_count"]) == signature), None)
                    if old is not None:
                        counts["merged_exact"] += 1
                        record.update(action="merged_exact", witness_index=old)
                    elif envelope is not None and g._angle_deg(envelope["anchor_normal"], item["normal"]) <= settings["distinct_normal_deg"] / 2 and max(envelope["offset_max_m"], item["offset_m"]) - min(envelope["offset_min_m"], item["offset_m"]) <= settings["distinct_offset_m"]:
                        envelope["angle_radius_deg"] = max(envelope["angle_radius_deg"], g._angle_deg(envelope["anchor_normal"], item["normal"]))
                        envelope["offset_min_m"] = min(envelope["offset_min_m"], item["offset_m"])
                        envelope["offset_max_m"] = max(envelope["offset_max_m"], item["offset_m"])
                        envelope["member_count"] += 1
                        counts["merged_certified"] += 1
                        record["action"] = "merged_certified_envelope"
                    elif len(witnesses) < candidate_budget:
                        if envelope is not None:
                            reasons.add("similarity_envelope_not_closed")
                        record.update(action="retained_witness", witness_index=len(witnesses))
                        witnesses.append(item)
                        counts["retained"] += 1
                        counts["peak_retained"] = len(witnesses)
                        if envelope is None:
                            envelope = {"anchor_normal": list(item["normal"]), "angle_radius_deg": 0.,
                                        "offset_min_m": item["offset_m"], "offset_max_m": item["offset_m"],
                                        "member_count": 1,
                                        "proof": "sphere triangle inequality: each radius<=angle_limit/2; total offset span<=offset_limit"}
                    else:
                        reasons.add("candidate_budget_incomplete")
                        counts["unstored"] += 1
                        record["action"] = "candidate_budget_unstored"
        if len(trace) < trace_budget:
            trace.append(record)
        else:
            counts["trace_unrecorded"] += 1
            reasons.add("trace_budget_incomplete")
    if not witnesses:
        reasons.add("no_refined_witness")
    distinct_pairs, close_pairs = [], []
    # ponytail: O(cap^2) terminal all-pairs, max cap512. Envelope proof if this
    # bounded research cost ever merits optimization; never moving representatives.
    for first, a in enumerate(witnesses):
        for second in range(first + 1, len(witnesses)):
            b = witnesses[second]
            if not similar(a, b, settings):
                distinct_pairs.append([first, second])
                if min(a["support_count"], b["support_count"]) >= settings["support_close_ratio"] * max(a["support_count"], b["support_count"]):
                    close_pairs.append([first, second])
    if distinct_pairs:
        reasons.add("distinct_refined_witnesses")
    if close_pairs:
        reasons.add("close_competition")
    return {"kind": "gli04_search_research", "physical_verified": False,
            "status": "unresolved" if reasons else "seen_sequence_closed_single",
            "closure_scope": "only supplied finite seen sequence; unseen hypotheses not excluded",
            "reasons": sorted(reasons), "budgets": budgets, "counts": counts,
            "witnesses": witnesses, "trace": trace, "distinct_pairs": distinct_pairs,
            "close_pairs": close_pairs, "similarity_certificate": envelope,
            "elapsed_s": time.perf_counter() - start}


def search(points, fit_rows, up, height, settings, **budgets):
    settings = g.resolve_constrained_settings(settings)
    up = g._unit_vector(up, "up")
    height = g._height_interval(height)
    sampled, rows, events = replay_sequence(points, fit_rows, up, height, settings)
    result = search_events(events, lambda event: refine_hypothesis(
        points, sampled, rows, event, up, height, settings), settings, **budgets)
    result.update(sampled_rows=sampled.tolist(), valid_fit_rows=rows.tolist(), settings=settings)
    return result

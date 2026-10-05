"""GL-I05 bounded conservative research prototype. Not imported by runtime.

The terminal closure decision is the GL-I05 research contract over the full
refined-witness multiset of the same finite seen sequence: ALL (every pair),
NEAR (every pair inside the support>=0.8*best pool, all ties kept),
BEST_ONLY (diagnostic only, never a gate). Distinct means >10deg or >0.05m;
similar is its negation, not an equivalence (0/6/12deg chains stay distinct).

Unlike GL-I04 there is no fixed-anchor envelope merge: that certificate was
not exact for the three-metric contract (envelope members are only provably
similar to each other, never provably similar to a stored witness that failed
envelope admission, and pool membership of merged witnesses loses support
counts). The only merge kept is the exact-signature duplicate, which is
always sound. Storage is bounded by candidate_budget; an unstorable refined
witness leaves the sequence unresolved, never silently dropped from evidence.

Closure semantics are research-only (seen_pairwise_closed /
seen_dominant_pool_closed / unresolved), NOT `ground.status` and NOT
GL-I04's `seen_sequence_closed_single`. Unseen hypotheses are never excluded.
"""
import time
import copy
import numpy as np

from core import ground as g
from core.ground_diagnostics import refine_hypothesis, replay_sequence

from oracle_analysis import oracle, _validate_witness


def search_events(events, refine, settings, candidate_budget=128,
                  refine_budget=2000, trace_budget=2000, iteration_budget=2000):
    budgets = {"candidate": candidate_budget, "refine": refine_budget,
               "trace": trace_budget, "iteration": iteration_budget}
    ceilings = {"candidate": 512, "refine": 2000, "trace": 2000, "iteration": 2000}
    for key, value in budgets.items():
        if type(value) is not int or not 0 <= value <= ceilings[key]:
            raise ValueError("invalid bounded " + key + " budget")
    if settings is not None and not isinstance(settings, dict):
        raise ValueError("settings must be an object")
    settings = g.resolve_constrained_settings(settings)
    start = time.perf_counter()
    timing = {"raw": 0., "refine": 0., "decision": 0.}

    witnesses = []
    trace, reasons = [], set()
    counts = {"draws_seen": 0, "qualified": 0, "refined_calls": 0,
              "rejected": 0, "produced": 0, "merged_exact": 0, "retained": 0,
              "unstored": 0, "unprocessed": 0, "trace_unrecorded": 0,
              "peak_stored": 0}

    for event in events:
        if counts["draws_seen"] >= 2000:
            reasons.add("source_sequence_ceiling_incomplete")
            break
        raw_start = time.perf_counter()
        if not isinstance(event, dict) or type(event.get("iteration")) is not int \
                or event["iteration"] != counts["draws_seen"]:
            raise ValueError("event iteration must match sequence position")
        if event.get("stage") not in ("sample_separation", "sample_area", "angle",
                                      "height", "support", "qualified"):
            raise ValueError("unknown raw event stage")
        if event["stage"] == "qualified":
            _validate_witness(event, counts["draws_seen"])
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
            if index >= iteration_budget or counts["refined_calls"] >= refine_budget:
                reasons.add("unprocessed_qualified_hypothesis")
                counts["unprocessed"] += 1
                record["action"] = "budget_unprocessed"
            else:
                counts["refined_calls"] += 1
                refine_start = time.perf_counter()
                item, rejection = refine(event)
                refine_elapsed = time.perf_counter() - refine_start
                timing["refine"] += refine_elapsed
                record["refine_reason"] = rejection
                record["refined"] = item
                if item is None:
                    counts["rejected"] += 1
                    record["action"] = "refined_rejected"
                else:
                    _validate_witness(item, index)
                    counts["produced"] += 1
                    signature = (tuple(item["normal"]), float(item["offset_m"]),
                                 int(item["support_count"]))
                    old = next((i for i, value in enumerate(witnesses) if
                                (tuple(value["normal"]), value["offset_m"],
                                 value["support_count"]) == signature), None)
                    if old is not None:
                        counts["merged_exact"] += 1
                        record.update(action="merged_exact", witness_index=old)
                    elif len(witnesses) < candidate_budget:
                        record.update(action="retained_witness",
                                      witness_index=len(witnesses))
                        witnesses.append({"normal": list(item["normal"]),
                                          "offset_m": float(item["offset_m"]),
                                          "support_count": int(item["support_count"])})
                        counts["retained"] += 1
                        counts["peak_stored"] = len(witnesses)
                    else:
                        reasons.add("candidate_budget_incomplete")
                        counts["unstored"] += 1
                        record["action"] = "candidate_budget_unstored"
        if len(trace) < trace_budget:
            trace.append(copy.deepcopy(record))
        else:
            counts["trace_unrecorded"] += 1
            reasons.add("trace_budget_incomplete")
        timing["raw"] += time.perf_counter() - raw_start

    timing["raw"] -= timing["refine"]

    gaps = bool(reasons)
    if not witnesses:
        reasons.add("no_refined_witness")
        gaps = True

    decision_start = time.perf_counter()
    report = oracle(witnesses, settings, gaps=gaps)
    timing["decision"] = time.perf_counter() - decision_start
    if not report["metrics"]["NEAR"]["holds"]:
        reasons.add("actual_near_pool_competition")
    report.update(kind="gli05_search_research", reasons=sorted(reasons),
                  budgets=budgets, counts=counts, witnesses=witnesses,
                  trace=trace, elapsed_s=time.perf_counter() - start,
                  stage_elapsed_s=timing, cache_hits=0, cache_misses=0,
                  closure_scope=("only supplied finite seen sequence; "
                                 "unseen hypotheses not excluded"))
    return report


def search(points, fit_rows, up, height, settings, **budgets):
    started = time.perf_counter()
    if settings is not None and not isinstance(settings, dict):
        raise ValueError('settings must be an object')
    source = np.asarray(points)
    if source.ndim != 2 or source.shape[1] != 3 or source.dtype.kind not in "fiu":
        raise ValueError("points must be numeric Nx3")
    # ponytail: one full-source conversion per call; no cross-call/refine cache.
    points = np.asarray(source, dtype=np.float64)
    settings = g.resolve_constrained_settings(settings)
    up = g._unit_vector(up, "up")
    height = g._height_interval(height)
    sampled, rows, events = replay_sequence(points, fit_rows, up, height, settings)
    sampling_elapsed = time.perf_counter() - started
    raw_elapsed = [0.]
    def timed_events():
        iterator = iter(events)
        while True:
            tick = time.perf_counter()
            try:
                item = next(iterator)
            except StopIteration:
                raw_elapsed[0] += time.perf_counter() - tick
                return
            raw_elapsed[0] += time.perf_counter() - tick
            yield item
    result = search_events(timed_events(), lambda event: refine_hypothesis(
        points, sampled, rows, event, up, height, settings), settings, **budgets)
    result.update(sampled_rows=sampled.tolist(), valid_fit_rows=rows.tolist(),
                  settings=settings)
    result["stage_elapsed_s"]["sampling"] = sampling_elapsed
    result["stage_elapsed_s"]["raw"] += raw_elapsed[0]
    result["elapsed_s"] = time.perf_counter() - started
    return result

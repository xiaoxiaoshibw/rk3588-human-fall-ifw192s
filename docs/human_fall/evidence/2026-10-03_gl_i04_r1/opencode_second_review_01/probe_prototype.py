"""Independent reviewer probes for GL-I04 prototype semantics (read-only).

Does not rerun the author ledger; builds fresh adversary fixtures and calls the
prototype's pure functions directly. Also reproduces clean/high-noise closure
independently.
"""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(r"D:/Code/ldiar")
PACKAGE = ROOT / "src/human_fall_detection"
RESEARCH = ROOT / "docs/human_fall/evidence/2026-10-03_gl_i04_r1/research_01"
sys.path[:0] = [str(PACKAGE), str(PACKAGE / "scripts"), str(RESEARCH)]

from core import ground as g
from core.ground_diagnostics import replay_sequence, refine_hypothesis
from search_prototype import search, search_events

S = g.resolve_constrained_settings()
results = {}


def ev(plane):
    return dict(plane, iteration=0, stage="qualified")


def run(events, **budgets):
    events = [dict(e, iteration=i, stage="qualified") for i, e in enumerate(events)]
    return search_events(events, lambda e: (dict(e), "fixture_refined"), S, **budgets)


def plane(d, count=200, normal=(0.0, 0.0, 1.0)):
    return {"normal": list(normal), "offset_m": d, "support_count": count}


# --- R02/R04: exact duplicates, chains, late, close -------------------------
dup = run([plane(1.0)] * 40)
results["exact_duplicates"] = {"status": dup["status"], "counts": dup["counts"],
                               "expect": "seen_sequence_closed_single / merged_exact>=39",
                               "ok": dup["status"] == "seen_sequence_closed_single"
                               and dup["counts"]["merged_exact"] == 39 and dup["counts"]["retained"] == 1}

chain = run([plane(1.0), plane(1.04), plane(1.08)])
results["offset_chain_nontransitive"] = {
    "status": chain["status"], "reasons": chain["reasons"], "witness_count": len(chain["witnesses"]),
    "distinct_pairs": chain["distinct_pairs"],
    "expect": "unresolved with distinct pair A-C and envelope-not-closed",
    "ok": chain["status"] == "unresolved" and chain["distinct_pairs"] and
          "similarity_envelope_not_closed" in chain["reasons"]}

ang = [dict(plane(1.0), normal=[float(np.sin(np.radians(a))), 0.0, float(np.cos(np.radians(a)))])
       for a in (0, 6, 12)]
ach = run(ang)
results["angular_chain_nontransitive"] = {
    "status": ach["status"], "reasons": ach["reasons"], "distinct_pairs": ach["distinct_pairs"],
    "expect": "unresolved (A-C 12deg>10), never merged via moving representative",
    "ok": ach["status"] == "unresolved" and ach["distinct_pairs"] == [[0, 2]]}

late = run([plane(1.0)] * 40 + [plane(1.14)])
results["late_distinct"] = {"status": late["status"], "reasons": late["reasons"],
                            "witnesses": len(late["witnesses"]), "peak": late["counts"]["peak_retained"],
                            "expect": "unresolved, 2 witnesses, distinct retained",
                            "ok": late["status"] == "unresolved" and len(late["witnesses"]) == 2}

close = run([plane(1.0, 500), plane(1.07, 100)])
results["close_distinct_low_support"] = {
    "status": close["status"], "reasons": close["reasons"], "close_pairs": close["close_pairs"],
    "expect": "unresolved; distinct + close competition preserved",
    "ok": close["status"] == "unresolved" and
          ("distinct_refined_witnesses" in close["reasons"] or "close_competition" in close["reasons"])}

# --- certificate boundary (half angle=5deg, offset span=0.05) ---------------
def at_angle(deg):
    return [float(np.sin(np.radians(deg))), 0.0, float(np.cos(np.radians(deg)))]

b_in = run([plane(1.0), dict(plane(1.02), normal=at_angle(4.999))])
b_out = run([plane(1.0), dict(plane(1.02), normal=at_angle(5.001))])
b_off_in = run([plane(0.0), plane(0.049)])
b_off_out = run([plane(0.0), plane(0.051)])
results["certificate_boundary"] = {
    "angle_half_in": {"status": b_in["status"], "merged": b_in["counts"]["merged_certified"]},
    "angle_half_out": {"status": b_out["status"], "reasons": b_out["reasons"]},
    "offset_in": {"merged": b_off_in["counts"]["merged_certified"]},
    "offset_out": {"status": b_off_out["status"], "reasons": b_off_out["reasons"]},
    "expect": "inside half merges; just outside does not and stays unresolved",
    "ok": b_in["counts"]["merged_certified"] == 1 and b_in["status"] == "seen_sequence_closed_single"
          and b_out["status"] == "unresolved" and b_off_in["counts"]["merged_certified"] == 1
          and b_off_out["status"] == "unresolved"}

# --- adversarial: envelope member M dissimilar to a later retained witness B -
M_vs_B = run([plane(1.0),
              dict(plane(1.0), normal=at_angle(5.0)),   # M merges into envelope
              dict(plane(1.0), normal=at_angle(-8.0))])  # B retained, not certified
# angle(M,B) can be up to 13deg > 10 -> must never report closed
results["envelope_vs_retained_witness"] = {
    "status": M_vs_B["status"], "peak_retained": M_vs_B["counts"]["peak_retained"],
    "reasons": M_vs_B["reasons"],
    "expect": "unresolved (envelope_not_closed) even if witness pair looks similar",
    "ok": M_vs_B["status"] == "unresolved"}

# --- R05: budget exhaustion ------------------------------------------------
budget = {}
for key in ("candidate_budget", "refine_budget", "trace_budget", "iteration_budget"):
    for value in (0, 1):
        r = run([plane(1.0)] * 40 + [plane(1.14)], **{key: value})
        budget["%s=%d" % (key, value)] = {"status": r["status"], "reasons": r["reasons"],
                                          "draws": r["counts"]["draws_seen"],
                                          "trace": len(r["trace"]),
                                          "unrecorded": r["counts"]["trace_unrecorded"]}
        assert r["status"] == "unresolved", (key, value)
        c = r["counts"]
        assert c["qualified"] == c["refined"] + c["unprocessed"]
        assert c["refined"] == c["rejected"] + c["retained"] + c["merged_exact"] + c["merged_certified"] + c["unstored"]
        assert c["draws_seen"] == len(r["trace"]) + c["trace_unrecorded"]
results["budget_exhaustion"] = {"cases": budget, "expect": "all unresolved, counts conserve",
                                "ok": all(v["status"] == "unresolved" for v in budget.values())}

no_input = run([])
rejected = run([plane(1.0)], )
rej = search_events([dict(plane(1.0), iteration=0, stage="qualified")],
                    lambda e: (None, "refine_degenerate"), S)
results["terminal_states"] = {
    "empty_events": {"status": no_input["status"], "reasons": no_input["reasons"]},
    "all_refine_rejected": {"status": rej["status"], "rejected": rej["counts"]["rejected"]},
    "expect": "unresolved",
    "ok": no_input["status"] == "unresolved" and rej["status"] == "unresolved"
          and rej["counts"]["rejected"] == 1}

# invalid budgets refused
bad = []
for key in ("candidate_budget", "refine_budget", "trace_budget", "iteration_budget"):
    for value in (-1, True, 1.5, 100000):
        try:
            search_events([], lambda e: (None, "x"), S, **{key: value})
            bad.append((key, value))
        except ValueError:
            pass
results["invalid_budgets_refused"] = {"accepted_bad": bad, "ok": not bad}

# --- R03/R01: independent clean vs high-noise closure ----------------------
def scene(kind, seed, permute):
    rng = np.random.RandomState(seed)
    n = 500
    xy = rng.uniform(-3, 3, (n, 2))
    z = np.full(n, -1.4)
    z += rng.normal(0, 0.008 if kind == "clean" else 0.035, n)
    fit = np.column_stack([xy, z])
    if permute:
        fit = fit[rng.permutation(n)]
    holds = [np.column_stack([rng.uniform(-3, 3, (80, 2)), np.full(80, -1.4)]) for _ in range(3)]
    points = np.vstack([fit] + holds)
    regions = [{"region_id": "v%d" % i, "frame_group": "hold%d" % i,
                "indices": list(range(n + 80 * i, n + 80 * (i + 1)))} for i in range(3)]
    return points, np.arange(n), regions


summary = {}
for kind in ("clean", "high_noise"):
    statuses = []
    for seed in (7, 19, 41):
        for permute in (False, True):
            points, rows, regions = scene(kind, seed, permute)
            st = g.resolve_constrained_settings({"seed": seed, "spatial_cell_m": .05,
                                                 "max_points_per_cell": 8})
            r = search(points, rows, np.array([0., 0., 1.]), (.5, 2.), st)
            r2 = search(points, rows, np.array([0., 0., 1.]), (.5, 2.), st)
            assert {k: v for k, v in r.items() if k != "elapsed_s"} == \
                   {k: v for k, v in r2.items() if k != "elapsed_s"}, (kind, seed, permute)
            statuses.append(r["status"])
    summary[kind] = statuses
results["independent_scene_closure"] = {
    "clean": summary["clean"], "high_noise": summary["high_noise"],
    "expect": "clean 6/6 closed; high noise 6/6 unresolved (not a bug)",
    "ok": summary["clean"] == ["seen_sequence_closed_single"] * 6 and
          summary["high_noise"] == ["unresolved"] * 6}

print(json.dumps(results, indent=2, default=str))
print("\nALL_OK:", all(v.get("ok", True) for v in results.values()))

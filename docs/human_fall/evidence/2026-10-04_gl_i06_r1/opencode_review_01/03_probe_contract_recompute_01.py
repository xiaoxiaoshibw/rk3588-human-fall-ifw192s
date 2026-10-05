"""Independent contract probes + fresh recompute. Uses my own expectation model.

Imports author modules only to invoke frozen I05 search_events and active R1
entry; expectations are derived here, not copied from author checks_05.py.
"""
import itertools
import json
import math
import sys
from pathlib import Path

RUN = Path(r"D:\Code\ldiar\docs\human_fall\evidence\2026-10-04_gl_i06_r1")
HERE = RUN / "research_01"
OUT = RUN / "opencode_review_01"
REPO = RUN.parents[3]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / "docs/human_fall/evidence/2026-10-04_gl_i05_r2/research_01"))
sys.path.insert(0, str(REPO / "src/human_fall_detection"))

import numpy as np  # noqa: E402
from search_prototype import search_events  # noqa: E402


def plane(deg=0.0, support=500, offset=1.4):
    a = math.radians(deg)
    return dict(normal=[math.sin(a), 0.0, math.cos(a)], offset_m=offset,
                support_count=support, eigenvalue_ratio=1.0)


# my independent oracle (same contract, independent implementation)
def my_oracle(w, settings, gaps=False):
    ratio = settings["support_close_ratio"]
    deg = settings["distinct_normal_deg"]
    off = settings["distinct_offset_m"]
    n = len(w)
    if n:
        sup = [p["support_count"] for p in w]
        best = max(sup)
        near = [i for i in range(n) if sup[i] >= ratio * best]
        top = [i for i in range(n) if sup[i] == best]
    else:
        best, near, top = None, [], []
    near_s, top_s = set(near), set(top)

    def distinct(i, j):
        dot = sum(a * b for a, b in zip(w[i]["normal"], w[j]["normal"]))
        ang = math.degrees(math.acos(max(-1.0, min(1.0, dot))))
        return ang > deg or abs(w[i]["offset_m"] - w[j]["offset_m"]) > off

    allp, nearp, bestp = [], [], []
    for i, j in itertools.combinations(range(n), 2):
        if distinct(i, j):
            allp.append([i, j])
            if i in near_s and j in near_s:
                nearp.append([i, j])
                if i in top_s or j in top_s:
                    bestp.append([i, j])
    if gaps or not w or nearp:
        status = "unresolved"
    elif not allp:
        status = "seen_pairwise_closed"
    else:
        status = "seen_dominant_pool_closed"
    return dict(status=status, best=best, top=top, allp=allp, nearp=nearp, bestp=bestp)


def ev(pool):
    return [dict(x, iteration=i, stage="qualified") for i, x in enumerate(pool)]


def run_search(pool, **b):
    return search_events(ev(pool), lambda e: (e, "refined"),
                         dict(distinct_normal_deg=10.0, distinct_offset_m=0.05,
                              support_close_ratio=0.8, seed=7), **b)


def part_contract(out):
    settings = dict(distinct_normal_deg=10.0, distinct_offset_m=0.05,
                    support_close_ratio=0.8, seed=7)
    cases = {
        "all_similar": [plane(0), plane(4), plane(8)],
        "chain_middle_best": [plane(0, 450), plane(6, 500), plane(12, 450)],
        "ties": [plane(0), plane(6), plane(12)],
        "weak_distinct": [plane(0), plane(0, 399, 1.54)],
        "near_boundary": [plane(0), plane(0, 400, 1.54)],
        "late_best": [plane(0, 200), plane(0, 200, 1.54), plane(0, 900)],
        "late_distinct": [plane(0), plane(0), plane(12)],
        "exact_merge": [plane(0), plane(0), plane(0)],
    }
    records, fails = [], []
    for name, pool in cases.items():
        exp = my_oracle(pool, settings)
        for perm in set(itertools.permutations(range(len(pool)), len(pool))):
            sub = [pool[i] for i in perm]
            report = run_search(sub)
            mine = my_oracle(sub, settings)
            if report["status"] != mine["status"]:
                fails.append(("status", name, list(perm), report["status"], mine["status"]))
            if report["best_support"] != mine["best"]:
                fails.append(("best", name, list(perm)))
            if report["metrics"]["BEST_ONLY"]["holds"] != (not mine["bestp"]):
                fails.append(("BEST_ONLY", name, list(perm)))
            # BEST_ONLY must never gate status
            poison = run_search([dict(x, J=0.0) for x in sub])
            if poison["status"] != report["status"]:
                fails.append(("J_changed_status", name, list(perm)))
            records.append(dict(case=name, perm=list(perm), status=report["status"],
                                best=report["best_support"]))
    # budgets: zero / one-short / exact / exact+1 for each budget key
    budget_records, budget_fails = [], []
    for name in ("weak_distinct", "chain_middle_best", "exact_merge", "late_distinct"):
        pool = cases[name]
        # base status on full processing
        base = run_search(pool)["status"]
        # count required units from an unbounded run
        unb = run_search(pool)
        trace = unb["trace"]
        n_events = len(trace)
        n_qualified = sum(1 for t in trace if t["raw_stage"] == "qualified")
        signatures = {(tuple(w["normal"]), w["offset_m"], w["support_count"])
                      for w in unb["witnesses"]}
        need = {"candidate_budget": len(signatures), "refine_budget": n_qualified,
                "trace_budget": n_events, "iteration_budget": n_events}
        for key, req in need.items():
            for budget in sorted({0, max(0, req - 1), req, req + 1}):
                r = run_search(pool, **{key: budget})
                if budget < req:
                    expected_status = "unresolved"
                else:
                    expected_status = base
                if r["status"] != expected_status:
                    budget_fails.append((name, key, budget, req, r["status"], expected_status))
                budget_records.append(dict(case=name, key=key, budget=budget, required=req,
                                           status=r["status"], gaps=r["gaps_input"]))
    out["contract"] = dict(fail_count=len(fails), failures=fails[:80],
                           budget_fail_count=len(budget_fails),
                           budget_failures=budget_fails[:80], n_records=len(records))
    out["budget_records"] = budget_records
    return fails, budget_fails


def part_recompute(out):
    import r0_01
    from refinement_05 import run_variant
    from core import ground as g
    from core import ground_diagnostics as gd
    fails = []
    detail = []
    for kind, seed, perm in (("clean", 7, False), ("high_noise", 7, False),
                             ("wall", 7, False), ("dual", 7, False)):
        name = "%s_%d_%s" % (kind, seed, perm)
        r0 = json.loads((HERE / ("r0_case_%s_01.json" % name)).read_text(encoding="utf-8"))
        cloud, rows, regions = r0_01.scene(kind, seed, perm)
        if r0_01.digest(cloud) != r0["source_sha"]:
            fails.append(("source_sha_repro", name))
        s = r0_01.settings(seed)
        sampled, fit, iterator = gd.replay_sequence(cloud, rows, np.array([0., 0., 1.]), (.5, 2.), s)
        seq = list(iterator)
        if r0_01.digest(sampled) != r0["sampled_sha"]:
            fails.append(("sampled_repro", name))
        if r0_01.digest(seq) != r0["raw_sha"]:
            fails.append(("raw_repro", name))
        # native fitter vs replay candidates
        baseline = g.fit_ground_plane_constrained(cloud, s, "research_source",
                                                  np.array([0., 0., 1.]), (.5, 2.), rows, "fit", regions)
        replay = gd.replay_frozen_search(cloud, rows, np.array([0., 0., 1.]), (.5, 2.), s)
        if baseline["candidates"] != replay["candidates"]:
            fails.append(("native_vs_replay", name))
        for k in (1, 2, 3):
            led = json.loads((HERE / ("r1_case_%s_K%d_02.json" % (name, k))).read_text(encoding="utf-8"))
            v = run_variant(cloud, sampled, fit, seq, np.array([0., 0., 1.]), (.5, 2.), s, k)
            if v["W"] != led["variant"]["W"]:
                fails.append(("fresh_W", name, k))
            if v["refinement_counts"] != led["variant"]["refinement_counts"]:
                fails.append(("fresh_counts", name, k))
            detail.append(dict(case=name, k=k, W=len(v["W"]), counts=v["refinement_counts"]))
        # budget=0 full-domain vs bounded storage
        v0 = run_variant(cloud, sampled, fit, seq, np.array([0., 0., 1.]), (.5, 2.), s, 1,
                         candidate_budget=0)
        if not v0["W"]:
            fails.append(("budget0_empty_W", name))
        if v0["report"]["best_support"] != max(p["support_count"] for p in v0["W"]):
            fails.append(("budget0_best_not_max", name))
        if v0["report"]["stored_subset_diagnostics"]["best_support"] is not None:
            fails.append(("budget0_stored_not_none", name))
        if v0["report"]["status"] != "unresolved":
            fails.append(("budget0_not_unresolved", name))
    # real WHAT_IF recompute parity
    cloud, rows, regions, draft, s = r0_01.real_inputs()
    up = g._unit_vector([-draft["up_axis"][0], 0., draft["up_axis"][2]], "up")
    sampled, fit, iterator = gd.replay_sequence(cloud, rows, up, draft["sensor_height_interval_m"], s)
    seq = list(iterator)
    v = run_variant(cloud, sampled, fit, seq, up, draft["sensor_height_interval_m"], s, 1)
    led = json.loads((HERE / "r1_case_real_historical_WHAT_IF_negative_X_K1_02.json").read_text(encoding="utf-8"))
    if v["W"] != led["variant"]["W"] or v["report"]["metrics"] != led["variant"]["report"]["metrics"]:
        fails.append(("real_whatif_parity",))
    detail.append(dict(case="real_historical_WHAT_IF_negative_X", k=1, W=len(v["W"])))
    out["recompute"] = dict(fail_count=len(fails), failures=fails[:80], detail=detail)
    return fails


def main():
    out = {}
    part_contract(out)
    part_recompute(out)
    (OUT / "03_probe_contract_recompute_01.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("contract fails", out["contract"]["fail_count"],
          "budget fails", out["contract"]["budget_fail_count"])
    print("recompute fails", out["recompute"]["fail_count"])
    for f in out["contract"]["failures"][:20]:
        print("CFAIL", f)
    for f in out["contract"]["budget_failures"][:20]:
        print("BFAIL", f)
    for f in out["recompute"]["failures"][:20]:
        print("RFAIL", f)
    for d in out["recompute"]["detail"]:
        print("  ", d)


if __name__ == "__main__":
    main()

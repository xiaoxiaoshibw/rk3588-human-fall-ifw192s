"""Revalidation step 4: contract cases/budgets, fresh recompute, invalid inputs, gates.

NEW output 04_contract_01.json. Imports frozen I05 search_prototype and the
author active entry only to invoke them; expectations are derived here.
"""
import itertools
import json
import math
import sys
from pathlib import Path

RUN = Path(r"D:\Code\ldiar\docs\human_fall\evidence\2026-10-04_gl_i06_r1")
HERE = RUN / "research_01"
REVAL = RUN / "opencode_review_01/revalidation_01"
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


def my_oracle(w, gaps=False):
    n = len(w)
    if n:
        sup = [p["support_count"] for p in w]
        best = max(sup)
        near = [i for i in range(n) if sup[i] >= 0.8 * best]
        top = [i for i in range(n) if sup[i] == best]
    else:
        best, near, top = None, [], []
    ns, ts = set(near), set(top)

    def distinct(i, j):
        dot = sum(a * b for a, b in zip(w[i]["normal"], w[j]["normal"]))
        ang = math.degrees(math.acos(max(-1.0, min(1.0, dot))))
        return ang > 10.0 or abs(w[i]["offset_m"] - w[j]["offset_m"]) > 0.05

    allp, nearp, bestp = [], [], []
    for i, j in itertools.combinations(range(n), 2):
        if distinct(i, j):
            allp.append([i, j])
            if i in ns and j in ns:
                nearp.append([i, j])
                if i in ts or j in ts:
                    bestp.append([i, j])
    if gaps or not w or nearp:
        status = "unresolved"
    elif not allp:
        status = "seen_pairwise_closed"
    else:
        status = "seen_dominant_pool_closed"
    return dict(status=status, best=best, allp=allp, nearp=nearp, bestp=bestp)


def ev(pool):
    return [dict(x, iteration=i, stage="qualified") for i, x in enumerate(pool)]


def run_search(pool, **b):
    return search_events(ev(pool), lambda e: (e, "refined"),
                         dict(distinct_normal_deg=10.0, distinct_offset_m=0.05,
                              support_close_ratio=0.8, seed=7), **b)


def part_contract(out):
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
    fails, budget_fails = [], []
    for name, pool in cases.items():
        for perm in set(itertools.permutations(range(len(pool)), len(pool))):
            sub = [pool[i] for i in perm]
            rep = run_search(sub)
            mine = my_oracle(sub)
            if rep["status"] != mine["status"]:
                fails.append(("status", name, list(perm), rep["status"], mine["status"]))
            if rep["best_support"] != mine["best"]:
                fails.append(("best", name, list(perm)))
            if rep["metrics"]["BEST_ONLY"]["holds"] != (not mine["bestp"]):
                fails.append(("BEST_ONLY", name, list(perm)))
            if run_search([dict(x, J=0.0) for x in sub])["status"] != rep["status"]:
                fails.append(("J_changed_status", name, list(perm)))
        # budgets: zero / one-short / exact / exact+1
        base = run_search(pool)
        trace = base["trace"]
        n_events = len(trace)
        n_qualified = sum(1 for t in trace if t["raw_stage"] == "qualified")
        sigs = {(tuple(w["normal"]), w["offset_m"], w["support_count"]) for w in base["witnesses"]}
        need = {"candidate_budget": len(sigs), "refine_budget": n_qualified,
                "trace_budget": n_events, "iteration_budget": n_events}
        for key, req in need.items():
            for budget in sorted({0, max(0, req - 1), req, req + 1}):
                r = run_search(pool, **{key: budget})
                exp = "unresolved" if budget < req else base["status"]
                if r["status"] != exp:
                    budget_fails.append((name, key, budget, req, r["status"], exp))
    out["contract"] = dict(fail_count=len(fails), failures=fails[:60],
                           budget_fail_count=len(budget_fails), budget_failures=budget_fails[:60])


def part_recompute(out):
    import r0_01
    from refinement_05 import run_variant
    from core import ground as g
    from core import ground_diagnostics as gd
    fails, detail = [], []
    for kind, seed, perm in (("clean", 7, False), ("high_noise", 7, False),
                             ("wall", 7, False), ("dual", 7, False)):
        name = "%s_%d_%s" % (kind, seed, perm)
        r0 = json.loads((HERE / ("r0_case_%s_01.json" % name)).read_text(encoding="utf-8"))
        cloud, rows, regions = r0_01.scene(kind, seed, perm)
        if r0_01.digest(cloud) != r0["source_sha"]:
            fails.append(("source_sha", name))
        s = r0_01.settings(seed)
        sampled, fit, it = gd.replay_sequence(cloud, rows, np.array([0., 0., 1.]), (.5, 2.), s)
        seq = list(it)
        if r0_01.digest(sampled) != r0["sampled_sha"] or r0_01.digest(seq) != r0["raw_sha"]:
            fails.append(("sample_raw_sha", name))
        baseline = g.fit_ground_plane_constrained(cloud, s, "research_source", np.array([0., 0., 1.]),
                                                  (.5, 2.), rows, "fit", regions)
        replay = gd.replay_frozen_search(cloud, rows, np.array([0., 0., 1.]), (.5, 2.), s)
        if baseline["candidates"] != replay["candidates"]:
            fails.append(("native_vs_replay", name))
        for k in (1, 2, 3):
            led = json.loads((HERE / ("r1_case_%s_K%d_02.json" % (name, k))).read_text(encoding="utf-8"))
            v = run_variant(cloud, sampled, fit, seq, np.array([0., 0., 1.]), (.5, 2.), s, k)
            if v["W"] != led["variant"]["W"] or v["refinement_counts"] != led["variant"]["refinement_counts"]:
                fails.append(("fresh_variant", name, k))
            detail.append((name, k, len(v["W"]), v["refinement_counts"]["nonconverged"]))
        v0 = run_variant(cloud, sampled, fit, seq, np.array([0., 0., 1.]), (.5, 2.), s, 1, candidate_budget=0)
        if not v0["W"] or v0["report"]["best_support"] != max(p["support_count"] for p in v0["W"]) \
                or v0["report"]["stored_subset_diagnostics"]["best_support"] is not None \
                or v0["report"]["status"] != "unresolved":
            fails.append(("budget0", name))
    cloud, rows, regions, draft, s = r0_01.real_inputs()
    up = g._unit_vector([-draft["up_axis"][0], 0., draft["up_axis"][2]], "up")
    sampled, fit, it = gd.replay_sequence(cloud, rows, up, draft["sensor_height_interval_m"], s)
    v = run_variant(cloud, sampled, fit, list(it), up, draft["sensor_height_interval_m"], s, 1)
    led = json.loads((HERE / "r1_case_real_historical_WHAT_IF_negative_X_K1_02.json").read_text(encoding="utf-8"))
    if v["W"] != led["variant"]["W"] or v["report"]["metrics"] != led["variant"]["report"]["metrics"]:
        fails.append(("real_whatif",))
    out["recompute"] = dict(fail_count=len(fails), failures=fails[:60], detail=detail)


def part_invalid(out):
    import r0_01
    from refinement_05 import validate_packet, run_variant
    from core import ground as g
    from core import ground_diagnostics as gd
    from oracle_analysis import oracle
    pts, rows, _ = r0_01.scene("clean", 7)
    s = r0_01.settings(7)
    sampled, fit, it = gd.replay_sequence(pts, rows, np.array([0., 0., 1.]), (.5, 2.), s)
    seq = list(it)
    digest = r0_01.digest
    packet = dict(schema=1, units="m", frame="research_source", source_sha=digest(pts),
                  fit_sha=digest(fit), sampled_sha=digest(sampled), raw_sha=digest(seq),
                  settings_sha=digest(s))
    fails = []

    def reject(label, fn):
        try:
            fn()
        except (ValueError, TypeError):
            return
        fails.append(label)
    reject("schema_bool", lambda: validate_packet(pts, fit, sampled, seq, s, dict(packet, schema=True)))
    reject("schema_2", lambda: validate_packet(pts, fit, sampled, seq, s, dict(packet, schema=2)))
    reject("units", lambda: validate_packet(pts, fit, sampled, seq, s, dict(packet, units="cm")))
    reject("frame", lambda: validate_packet(pts, fit, sampled, seq, s, dict(packet, frame="x")))
    reject("source_change", lambda: validate_packet(pts + .01, fit, sampled, seq, s, packet))
    bad = pts.copy(); bad[0, 0] = float("nan")
    reject("nan", lambda: validate_packet(bad, fit, sampled, seq, s, packet))
    reject("settings_change", lambda: validate_packet(pts, fit, sampled, seq, dict(s, seed=19), packet))
    reject("zero_threshold", lambda: g.resolve_constrained_settings(dict(s, inlier_threshold_m=0.)))
    reject("nan_angle", lambda: g.resolve_constrained_settings(dict(s, max_angle_rad=float("nan"))))
    reject("zero_up", lambda: g._unit_vector([0., 0., 0.], "up"))
    reject("nan_height", lambda: g._height_interval([float("nan"), 2.]))
    reject("K0", lambda: run_variant(pts, sampled, fit, [], np.array([0., 0., 1.]), (.5, 2.), s, 0))
    reject("Kbool", lambda: run_variant(pts, sampled, fit, [], np.array([0., 0., 1.]), (.5, 2.), s, True))
    reject("lo_over", lambda: run_variant(pts, sampled, fit, [], np.array([0., 0., 1.]), (.5, 2.), s, 1, lo_budget=6001))
    reject("nonNx3", lambda: run_variant(pts[:, :2], sampled, fit, [], np.array([0., 0., 1.]), (.5, 2.), s, 1))
    gset = dict(distinct_normal_deg=10., distinct_offset_m=.05, support_close_ratio=.8)
    reject("w_nonunit", lambda: oracle([dict(normal=[0., 0., 2.], offset_m=1., support_count=1)], gset))
    reject("w_boolsupport", lambda: oracle([dict(normal=[0., 0., 1.], offset_m=1., support_count=True)], gset))
    reject("w_nanoff", lambda: oracle([dict(normal=[0., 0., 1.], offset_m=float("nan"), support_count=1)], gset))
    out["invalid_inputs"] = dict(checked=17, fail_count=len(fails), failures=fails)


def part_gates(out):
    import r0_01
    from refinement_05 import bounded_refine, run_variant
    s = r0_01.settings(7)
    xy = np.random.RandomState(7).uniform(-3, 3, (250, 2))
    two = np.vstack([np.column_stack([xy, np.full(250, -1.4)]),
                     np.column_stack([xy, np.full(250, -1.54)])])
    ids = np.arange(500)
    a = dict(normal=[0., 0., 1.], offset_m=1.4, support_count=250, eigenvalue_ratio=1.)
    b = dict(normal=[0., 0., 1.], offset_m=1.54, support_count=250, eigenvalue_ratio=1.)
    fails = []

    def injected(models):
        it = iter(models)
        return lambda *args: (next(it), "injected")
    _, d = bounded_refine(two, ids, ids, a, np.array([0., 0., 1.]), (.5, 2.), s, 3,
                          dict(remaining=6000), injected([b, a, b]))
    if not (d["cycle"] and d["full_k"] and d["quality_gap"]):
        fails.append("cycle")
    _, d = bounded_refine(two, ids, ids, a, np.array([0., 0., 1.]), (.5, 2.), s, 2,
                          dict(remaining=6000), injected([a, dict(a, offset_m=3.0)]))
    if not (d["violation"] == "later_round_height" and d["quality_gap"]):
        fails.append("later_height")
    last, d = bounded_refine(two, ids, ids, a, np.array([0., 0., 1.]), (.5, 2.), s, 2,
                             dict(remaining=6000), injected([dict(a, offset_m=3.0)]))
    if not (d["violation"] == "first_round_height" and last is None):
        fails.append("first_invalid")
    _, d = bounded_refine(two, ids, ids, a, np.array([0., 0., 1.]), (.5, 2.), s, 3, dict(remaining=1))
    if not d["resource_gap"]:
        fails.append("resource_gap")
    cloud, rows, _ = r0_01.scene("high_noise", 7, False)
    from core import ground_diagnostics as gd
    sample, fit, it = gd.replay_sequence(cloud, rows, np.array([0., 0., 1.]), (.5, 2.), s)
    seq = list(it)
    rg = run_variant(cloud, sample, fit, seq, np.array([0., 0., 1.]), (.5, 2.), s, 2, lo_budget=0)
    if rg["report"]["status"] != "unresolved" or not any(x["resource_gap"] for x in rg["details"]):
        fails.append("real_lo_gap")
    v2 = run_variant(cloud, sample, fit, seq, np.array([0., 0., 1.]), (.5, 2.), s, 2)
    if v2["refinement_counts"]["nonconverged"] == 0 or v2["report"]["status"] != "unresolved":
        fails.append("real_nonconverged")
    out["gates"] = dict(fail_count=len(fails), failures=fails,
                        real_nonconverged=v2["refinement_counts"]["nonconverged"])


def main():
    out = {}
    part_contract(out)
    part_recompute(out)
    part_invalid(out)
    part_gates(out)
    target = REVAL / "04_contract_01.json"
    if target.exists():
        raise SystemExit("refuse to overwrite " + str(target))
    out["overall_fail"] = sum(out[k]["fail_count"] for k in
                              ("contract", "recompute", "invalid_inputs", "gates")) \
        + out["contract"]["budget_fail_count"]
    target.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print("contract", out["contract"]["fail_count"], "budget", out["contract"]["budget_fail_count"],
          "recompute", out["recompute"]["fail_count"], "invalid", out["invalid_inputs"]["fail_count"],
          "gates", out["gates"]["fail_count"], "overall", out["overall_fail"])
    for k in ("contract", "recompute", "gates"):
        for f in out[k]["failures"][:10]:
            print(" ", k, f)


if __name__ == "__main__":
    main()

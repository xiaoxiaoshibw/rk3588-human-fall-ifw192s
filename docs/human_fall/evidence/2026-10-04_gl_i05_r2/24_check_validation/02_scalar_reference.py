"""Independent scalar reference for GL-I05 three metrics + adversarial probes.

Does NOT import the author oracle for its expected values. Builds ALL/NEAR/
BEST_ONLY and terminal status from first principles, then cross-checks the
author `oracle` and bounded `search_events` over the SAME witness sequence.
"""
import itertools
import json
import math
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
RUN = Path(__file__).resolve().parents[1]
RES = RUN / "research_01"
PACKAGE = ROOT / "src" / "human_fall_detection"
sys.path[:0] = [str(PACKAGE), str(PACKAGE / "scripts"), str(RES)]

import numpy as np
from core import ground as g
from oracle_analysis import oracle as author_oracle
from search_prototype import search_events

SETTINGS = g.resolve_constrained_settings()
D = SETTINGS["distinct_normal_deg"]
O = SETTINGS["distinct_offset_m"]
R = SETTINGS["support_close_ratio"]


def unit(normal):
    v = np.asarray(normal, dtype=float)
    return (v / np.linalg.norm(v)).tolist()


def plane(offset, support, up_deg=0.0):
    return {"normal": unit([math.sin(math.radians(up_deg)), 0.0,
                            math.cos(math.radians(up_deg))]),
            "offset_m": offset, "support_count": support}


def distinct(a, b):
    dot = max(-1.0, min(1.0, sum(x * y for x, y in zip(a["normal"], b["normal"]))))
    angle = math.degrees(math.acos(dot))
    return angle > D or abs(a["offset_m"] - b["offset_m"]) > O


def scalar(witnesses):
    n = len(witnesses)
    pairs = [[i, j] for i, j in itertools.combinations(range(n), 2)
             if distinct(witnesses[i], witnesses[j])]
    if witnesses:
        s = max(w["support_count"] for w in witnesses)
        near = {i for i, w in enumerate(witnesses) if w["support_count"] >= R * s}
        top = {i for i, w in enumerate(witnesses) if w["support_count"] == s}
    else:
        near, top = set(), set()
    all_pairs = pairs
    near_pairs = [p for p in pairs if set(p) <= near]
    best_pairs = [p for p in near_pairs if set(p) & top]
    if not witnesses or near_pairs:
        status = "unresolved"
    elif all_pairs:
        status = "seen_dominant_pool_closed"
    else:
        status = "seen_pairwise_closed"
    return {"ALL": all_pairs, "NEAR": near_pairs, "BEST_ONLY": best_pairs,
            "status": status, "near": sorted(near), "top": sorted(top)}


def events(planes):
    return [dict(planes[i], iteration=i, stage="qualified")
            for i in range(len(planes))]


def identity_refine(event):
    return ({"normal": list(event["normal"]), "offset_m": event["offset_m"],
             "support_count": event["support_count"]}, "refined")


def compare_metrics(witnesses, result):
    ref = scalar(witnesses)
    got_ok = (result["metrics"]["ALL"]["distinct_pairs"] == ref["ALL"]
              and result["metrics"]["NEAR"]["distinct_pairs"] == ref["NEAR"]
              and result["metrics"]["BEST_ONLY"]["distinct_pairs"] == ref["BEST_ONLY"]
              and result["status"] == ref["status"])
    return ref, got_ok


def main():
    out = {"script": "02_scalar_reference", "checks": [], "random_mismatch": []}

    def record(name, ok, detail=None):
        out["checks"].append({"name": name, "ok": bool(ok), "detail": detail})

    # --- fixed fixtures ---
    # 0/4/8 deg all mutually similar -> closed for every order
    allsim = [plane(1.0, 200, d) for d in (0.0, 4.0, 8.0)]
    ok = True
    for perm in itertools.permutations(allsim):
        res = author_oracle(list(perm), SETTINGS)
        ref, good = compare_metrics(list(perm), res)
        ok = ok and good and ref["status"] == "seen_pairwise_closed"
    record("0_4_8_all_similar_all_orders_closed", ok)

    # 0/6/12 deg chain -> endpoints distinct -> unresolved; BEST_ONLY 'closed'
    chain = [plane(1.0, 450, -6.0), plane(1.0, 500, 0.0), plane(1.0, 450, 6.0)]
    ok = True
    for perm in itertools.permutations(chain):
        res = author_oracle(list(perm), SETTINGS)
        ref, good = compare_metrics(list(perm), res)
        ok = ok and good and ref["status"] == "unresolved"
    record("0_6_12_chain_all_orders_unresolved", ok)
    c = author_oracle(chain, SETTINGS)
    record("chain_BEST_ONLY_diagnostic_closed", c["metrics"]["BEST_ONLY"]["holds"] is True)

    # middle-best swallowed: highest support is the middle, endpoints distinct
    mid = [plane(1.0, 500, 0.0), plane(1.0, 450, -6.0), plane(1.0, 450, 6.0)]
    r = author_oracle(mid, SETTINGS)
    record("middle_best_swallowed", r["status"] == "unresolved"
           and r["metrics"]["BEST_ONLY"]["holds"] is True
           and r["metrics"]["NEAR"]["holds"] is False
           and len(r["metrics"]["MIDDLE_BEST_SWALLOWED"]["pairs"]) > 0)

    # weak distinct dominant positive: strong pool similar + weak distinct outside
    best = plane(1.0, 500)
    near = [plane(1.0 + i * 0.001, 420) for i in range(5)]
    weak = plane(1.2, 100)
    pool = [best] + near + [weak]
    ok = True
    for perm in itertools.permutations(pool):
        res = author_oracle(list(perm), SETTINGS)
        ref, good = compare_metrics(list(perm), res)
        ok = ok and good and ref["status"] == "seen_dominant_pool_closed"
    record("weak_distinct_dominant_positive_all_orders", ok)

    # .8 boundary both sides
    b = [plane(1.0, 500), plane(1.0, 400), plane(1.2, 399)]
    r = author_oracle(b, SETTINGS)
    ref, good = compare_metrics(b, r)
    record("ratio_0p8_boundary", good and ref["near"] == [0, 1]
           and ref["status"] == "seen_dominant_pool_closed")
    r2 = author_oracle([plane(1.0, 500), plane(1.0, 399)], SETTINGS)
    record("ratio_below_floor_single_near",
           r2["near_pool_indices"] == [0] and r2["status"] == "seen_pairwise_closed")

    # top ties kept whole (3-way tie, one distinct)
    tie = [plane(1.0, 500, 0.0), plane(1.0, 500, 6.0), plane(1.0, 500, 13.0)]
    r = author_oracle(tie, SETTINGS)
    record("top_ties_whole", len(r["top_tie_indices"]) == 3
           and r["metrics"]["NEAR"]["holds"] is False)

    # --- randomized cross-check against the scalar reference ---
    rng = random.Random(20261004)
    for trial in range(4000):
        n = rng.randint(0, 9)
        ws = []
        for _ in range(n):
            axis = rng.uniform(0, 30)
            off = rng.choice([1.0, 1.0, 1.05, 1.2])
            sup = rng.choice([100, 200, 250, 320, 400, 500, 500])
            ws.append(plane(off, sup, axis))
        res = author_oracle(ws, SETTINGS)
        ref, good = compare_metrics(ws, res)
        if not good:
            out["random_mismatch"].append({"trial": trial, "ws": ws,
                                           "ref": ref["status"], "got": res["status"]})
            if len(out["random_mismatch"]) > 5:
                break
    record("random_cross_check_4000", not out["random_mismatch"])

    # --- bounded prototype terminal MUST equal scalar over same sequence ---
    proto_ok = True
    mismatch = []
    cases = {
        "clean": [plane(1.0, 200) for _ in range(3)],
        "all_similar": allsim,
        "chain": [plane(o, 200) for o in (1.0, 1.04, 1.08)],
        "weak_dom": pool,
        "tie": tie,
        "dual": [plane(1.0, 300), plane(1.2, 300)],
    }
    for name, ws in cases.items():
        budget = min(512, len({(tuple(w["normal"]), w["offset_m"],
                                 w["support_count"]) for w in ws}) + 8)
        report = search_events(events(ws), identity_refine, SETTINGS,
                               candidate_budget=budget)
        ref = scalar(ws)
        if report["status"] != ref["status"]:
            proto_ok = False
            mismatch.append({"case": name, "proto": report["status"],
                             "scalar": ref["status"], "reasons": report["reasons"]})
    record("prototype_terminal_equals_scalar", proto_ok, mismatch)

    # --- malformed events rejected ---
    def rejects(fn):
        try:
            fn()
        except (ValueError, TypeError, KeyError):
            return True
        return False
    mal = [
        (lambda: search_events([{"iteration": 0, "stage": "invented"}], identity_refine, SETTINGS)),
        (lambda: search_events([{"iteration": 5, "stage": "sample_area"}], identity_refine, SETTINGS)),
        (lambda: search_events([{"iteration": 0, "stage": "qualified",
                                 "normal": [0, 0], "offset_m": 1, "support_count": 1}],
                               identity_refine, SETTINGS)),
        (lambda: search_events([{"iteration": 0, "stage": "qualified",
                                 "normal": [0.0, 0.0, 2.0], "offset_m": 1, "support_count": 1}],
                               identity_refine, SETTINGS)),
        (lambda: search_events([{"iteration": 0, "stage": "qualified",
                                 "normal": [0.0, 0.0, 1.0], "offset_m": float("nan"),
                                 "support_count": 1}], identity_refine, SETTINGS)),
        (lambda: search_events([{"iteration": 0, "stage": "qualified",
                                 "normal": [0.0, 0.0, 1.0], "offset_m": 1,
                                 "support_count": -1}], identity_refine, SETTINGS)),
    ]
    record("malformed_events_reject", all(rejects(f) for f in mal))

    # --- oracle illegal inputs / settings ---
    def rejects2(fn):
        try:
            fn()
        except (ValueError, TypeError):
            return True
        return False
    bad = [
        lambda: author_oracle([plane(1.0, 1)], {"distinct_normal_deg": float("nan")}),
        lambda: author_oracle([plane(1.0, 1)], {"distinct_normal_deg": float("inf")}),
        lambda: author_oracle([plane(1.0, 1)], {"distinct_normal_deg": True}),
        lambda: author_oracle([plane(1.0, 1)], {"distinct_normal_deg": 0.0}),
        lambda: author_oracle([dict(plane(1.0, 1), normal=[0, 0, 0])], SETTINGS),
        lambda: author_oracle([dict(plane(1.0, 1), normal=[0, 0, 2])], SETTINGS),
        lambda: author_oracle([plane(1.0, 1)], SETTINGS, gaps="false"),
    ]
    record("oracle_rejects_illegal", all(rejects2(f) for f in bad))

    (Path(__file__).resolve().parent / "02_scalar_reference.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"checks": [(c["name"], c["ok"]) for c in out["checks"]],
                      "random_mismatch": out["random_mismatch"][:2]},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()

"""GL-I05 R1 second review: independent scalar oracle + adversarial probes.

Fully independent re-implementation of the ALL / NEAR / BEST_ONLY metrics and
the three terminal states, computed with plain scalar arithmetic (no NumPy
vectorisation, no import of the author's oracle math). Cross-checked against
the author's `oracle_analysis.oracle` and `search_prototype.search_events` on
hand-calculated fixtures, permutations, strongest-first/last orders, the exact
0.8 support boundary, ties, non-transitive chains, gaps and malformed /
non-finite inputs.

Read-only w.r.t. author files; writes only into this review directory.
"""
import itertools
import json
import math
import random
import sys
import traceback
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
AUTHOR = ROOT / "docs" / "human_fall" / "evidence" / "2026-10-03_gl_i05_r1" / "research_01"
PACKAGE = ROOT / "src" / "human_fall_detection"
sys.path[:0] = [str(PACKAGE), str(PACKAGE / "scripts"), str(AUTHOR), str(HERE)]

from oracle_analysis import oracle as author_oracle          # noqa: E402
from search_prototype import search_events                   # noqa: E402

SETTINGS = {"distinct_normal_deg": 10.0, "distinct_offset_m": 0.05,
            "support_close_ratio": 0.8}
RESULTS = []


def check(name, ok, detail=None):
    RESULTS.append({"name": name, "ok": bool(ok), "detail": detail})
    print("%s %s%s" % ("PASS" if ok else "FAIL", name,
                       (" :: " + str(detail)) if detail and not ok else ""))


def angle_deg(a, b):
    dot = max(-1.0, min(1.0, a[0] * b[0] + a[1] * b[1] + a[2] * b[2]))
    return math.degrees(math.acos(dot))


def w(normal, offset, support):
    return {"normal": list(normal), "offset_m": float(offset),
            "support_count": int(support)}


def scalar_distinct(a, b, settings=SETTINGS):
    if angle_deg(a["normal"], b["normal"]) > settings["distinct_normal_deg"]:
        return True
    return abs(a["offset_m"] - b["offset_m"]) > settings["distinct_offset_m"]


def scalar_oracle(witnesses, settings=SETTINGS, gaps=False):
    n = len(witnesses)
    all_pairs = [[i, j] for i in range(n) for j in range(i + 1, n)
                 if scalar_distinct(witnesses[i], witnesses[j], settings)]
    if n:
        best = max(x["support_count"] for x in witnesses)
        near = [i for i in range(n)
                if witnesses[i]["support_count"] >= settings["support_close_ratio"] * best]
        top = [i for i in range(n) if witnesses[i]["support_count"] == best]
    else:
        best, near, top = None, [], []
    near_pairs = [[i, j] for i, j in all_pairs if i in near and j in near]
    best_only_pairs = [[i, j] for i, j in near_pairs if i in top or j in top]
    weak_pairs = [[i, j] for i, j in all_pairs if not (i in near and j in near)]
    if gaps or n == 0 or near_pairs:
        status = "unresolved"
    elif not all_pairs:
        status = "seen_pairwise_closed"
    else:
        status = "seen_dominant_pool_closed"
    return {"status": status, "best": best, "near": near, "top": top,
            "all_pairs": all_pairs, "near_pairs": near_pairs,
            "best_only_pairs": best_only_pairs, "weak_pairs": weak_pairs}


def pairs_set(pairs):
    return {tuple(sorted(p)) for p in pairs}


def cross_check_author(name, witnesses, settings=SETTINGS, gaps=False):
    mine = scalar_oracle(witnesses, settings, gaps)
    theirs = author_oracle(witnesses, settings, gaps=gaps)
    ok = (mine["status"] == theirs["status"]
          and pairs_set(mine["all_pairs"]) == pairs_set(theirs["metrics"]["ALL"]["distinct_pairs"])
          and pairs_set(mine["near_pairs"]) == pairs_set(theirs["metrics"]["NEAR"]["distinct_pairs"])
          and pairs_set(mine["weak_pairs"]) == pairs_set(theirs["distinct_outside_near_pool"]))
    check("oracle_cross_" + name, ok,
          {"mine": {k: mine[k] for k in ("status", "all_pairs", "near_pairs")},
           "theirs_status": theirs["status"],
           "theirs_all": theirs["metrics"]["ALL"]["distinct_pairs"],
           "theirs_near": theirs["metrics"]["NEAR"]["distinct_pairs"]})
    return mine, theirs


def plane(offset, support, up_deg=0.0):
    return w([math.sin(math.radians(up_deg)), 0.0, math.cos(math.radians(up_deg))],
             offset, support)


def events(planes):
    return [dict(p, iteration=i, stage="qualified") for i, p in enumerate(planes)]


def identity_refine(event):
    return ({"normal": list(event["normal"]), "offset_m": event["offset_m"],
             "support_count": event["support_count"]}, "refined")


# ---------------------------------------------------------------- hand fixtures
def hand_fixtures():
    s = SETTINGS
    cases = [
        ("single", [plane(1.0, 100)], "seen_pairwise_closed"),
        ("two_similar", [plane(1.0, 100), plane(1.01, 100)], "seen_pairwise_closed"),
        ("two_distinct_angle", [plane(1.0, 100), plane(1.0, 100, 12.0)], "unresolved"),
        ("two_distinct_offset", [plane(1.0, 100), plane(1.2, 100)], "unresolved"),
        ("best_plus_weak_distinct", [plane(1.0, 500), plane(1.2, 79)],
         "seen_dominant_pool_closed"),
        ("middle_best_chain", [plane(1.0, 500, 6.0), plane(1.0, 450, 0.0),
                               plane(1.0, 450, 12.0)], "unresolved"),
        # 400 == 0.8*500 and distinct -> in pool -> NEAR fails.
        ("boundary_inside_080", [plane(1.0, 500), plane(1.2, 400)],
         "unresolved"),
        # 399 < 0.8*500 and distinct -> outside pool -> dominant closed.
        ("boundary_outside_0799", [plane(1.0, 500), plane(1.2, 399)],
         "seen_dominant_pool_closed"),
        # below pool but similar -> no distinct pair at all -> pairwise closed.
        ("below_pool_similar", [plane(1.0, 500), plane(1.01, 399)],
         "seen_pairwise_closed"),
        ("empty", [], "unresolved"),
    ]
    for name, witnesses, expected in cases:
        mine = scalar_oracle(witnesses, s)
        check("hand_scalar_" + name, mine["status"] == expected,
              {"got": mine["status"], "want": expected})
        cross_check_author("hand_" + name, witnesses)
    # gaps force unresolved regardless.
    cross_check_author("gap_single", [plane(1.0, 100)], gaps=True)
    check("hand_gap_single", author_oracle([plane(1.0, 100)], s, gaps=True)["status"]
          == "unresolved")


# ------------------------------------------------- strict boundary at exactly 0.8
def boundary_probe():
    s = SETTINGS
    best = plane(1.0, 500)
    inside = plane(1.2, 400)      # exactly 0.8*500, distinct -> in pool -> unresolved
    outside = plane(1.2, 399)     # below pool, distinct -> dominant closed
    for name, cand, want in (("inside", inside, "unresolved"),
                             ("outside", outside, "seen_dominant_pool_closed")):
        r = author_oracle([best, cand], s)
        check("boundary_" + name, r["status"] == want,
              {"got": r["status"], "want": want})
    # .8 - epsilon
    eps = plane(1.2, int(0.8 * 500 - 0.001) if False else 399)
    r = author_oracle([best, eps], s)
    check("boundary_below_eps", r["status"] == "seen_dominant_pool_closed", r["status"])


# ----------------------------------------------- order: strongest first / last
def order_probe():
    s = SETTINGS
    # all-similar 0/4/8 set; strongest (500) first and last
    similar = [plane(1.0, 200, 0.0), plane(1.0, 200, 4.0), plane(1.0, 200, 8.0)]
    for pos in ("first", "last"):
        pool = [dict(x) for x in similar]
        if pos == "first":
            pool[0]["support_count"] = 500
        else:
            pool[-1]["support_count"] = 500
        for perm in itertools.permutations(pool):
            ev = events(list(perm))
            rep = search_events(ev, identity_refine, s)
            if rep["status"] != "seen_pairwise_closed":
                check("order_similar_%s_%s" % (pos, "perm"), False, rep["status"])
                return
    check("order_similar_first_last_all_perms", True)

    # 0/6/12 chain: strongest either first or last; must stay unresolved.
    for pos in ("first", "last"):
        chain = [plane(1.0, 500, 6.0), plane(1.0, 450, 0.0), plane(1.0, 450, 12.0)]
        for perm in itertools.permutations(chain):
            ev = events(list(perm))
            rep = search_events(ev, identity_refine, s)
            mine = scalar_oracle(list(perm), s)
            if rep["status"] != mine["status"]:
                check("order_chain_%s" % pos, False,
                      {"got": rep["status"], "want": mine["status"]})
                return
    check("order_chain_all_perms_match_scalar", True)


# --------------------------------------- author BEST_ONLY index-asymmetry probe
def best_only_asymmetry():
    s = SETTINGS
    # best at index 1, distinct near member at index 0 (both in the pool).
    witnesses = [plane(1.2, 450), plane(1.0, 500)]
    mine = scalar_oracle(witnesses, s)
    theirs = author_oracle(witnesses, s)
    author_best_only = pairs_set([[a, b] for a, b in
                                  theirs["metrics"]["BEST_ONLY"]["distinct_pairs"]])
    my_best_only = pairs_set(mine["best_only_pairs"])
    check("best_only_detects_best_vs_earlier_near",
          my_best_only == author_best_only,
          {"my_best_only": sorted(my_best_only),
           "author_best_only": sorted(author_best_only),
           "author_holds": theirs["metrics"]["BEST_ONLY"]["holds"]})


# ------------------------------------------------------- malformed / non-finite
def malformed_probe():
    s = SETTINGS
    bad_witnesses = [
        ("not_dict", [42]),
        ("short_normal", [{"normal": [0.0, 0.0], "offset_m": 1.0, "support_count": 1}]),
        ("nan_normal", [{"normal": [float("nan"), 0.0, 1.0], "offset_m": 1.0,
                         "support_count": 1}]),
        ("inf_normal", [{"normal": [float("inf"), 0.0, 1.0], "offset_m": 1.0,
                         "support_count": 1}]),
        ("nan_offset", [{"normal": [0.0, 0.0, 1.0], "offset_m": float("nan"),
                         "support_count": 1}]),
        ("inf_offset", [{"normal": [0.0, 0.0, 1.0], "offset_m": float("inf"),
                         "support_count": 1}]),
        ("bool_support", [{"normal": [0.0, 0.0, 1.0], "offset_m": 1.0,
                           "support_count": True}]),
        ("float_support", [{"normal": [0.0, 0.0, 1.0], "offset_m": 1.0,
                            "support_count": 1.5}]),
        ("negative_support", [{"normal": [0.0, 0.0, 1.0], "offset_m": 1.0,
                               "support_count": -1}]),
        ("missing_offset", [{"normal": [0.0, 0.0, 1.0], "support_count": 1}]),
    ]
    for name, witnesses in bad_witnesses:
        try:
            author_oracle(witnesses, s)
        except (ValueError, TypeError):
            check("reject_witness_" + name, True)
        else:
            check("reject_witness_" + name, False, "accepted malformed witness")

    # settings that are non-finite / wrong type must be rejected by the
    # prototype entry (which routes through resolve_constrained_settings).
    bad_settings = [
        ("nan_ratio", {"support_close_ratio": float("nan")}),
        ("inf_ratio", {"support_close_ratio": float("inf")}),
        ("nan_deg", {"distinct_normal_deg": float("nan")}),
        ("zero_deg", {"distinct_normal_deg": 0.0}),
        ("ratio_gt1", {"support_close_ratio": 1.5}),
        ("unknown_key", {"not_a_setting": 1}),
        ("bool_seed", {"seed": True}),
    ]
    base = dict(SETTINGS, seed=7, spatial_cell_m=0.05, max_points_per_cell=8)
    for name, patch in bad_settings:
        merged = dict(base, **patch)
        try:
            search_events([], identity_refine, merged)
        except (ValueError, TypeError):
            check("reject_setting_" + name, True)
        else:
            check("reject_setting_" + name, False, "accepted malformed setting")

    # invalid budget values (bool, float, negative, over cap)
    for key in ("candidate_budget", "refine_budget", "trace_budget", "iteration_budget"):
        for value in (-1, True, 1.5, 999999):
            try:
                search_events([], identity_refine, base, **{key: value})
            except (ValueError, TypeError):
                continue
            check("reject_budget_%s_%r" % (key, value), False, "accepted")
            return
    check("reject_budget_all_invalid", True)


# ------------------------------------------------------ randomised cross-check
def randomised_cross_check(count=4000):
    rng = random.Random(20261004)
    for index in range(count):
        n = rng.randint(0, 9)
        settings = {"distinct_normal_deg": rng.choice([10.0, 5.0, 12.0]),
                    "distinct_offset_m": rng.choice([0.05, 0.02]),
                    "support_close_ratio": rng.choice([0.8, 0.5, 1.0])}
        witnesses = []
        for _ in range(n):
            deg = rng.choice([0.0, 4.0, 6.0, 8.0, 10.0, 10.0001, 12.0, 20.0])
            off = rng.choice([1.0, 1.04, 1.05, 1.0501, 1.08, 1.2])
            sup = rng.choice([100, 200, 399, 400, 450, 500])
            witnesses.append(plane(off, sup, deg))
        mine = scalar_oracle(witnesses, settings)
        theirs = author_oracle(witnesses, settings)
        if mine["status"] != theirs["status"] or \
           pairs_set(mine["all_pairs"]) != pairs_set(theirs["metrics"]["ALL"]["distinct_pairs"]) or \
           pairs_set(mine["near_pairs"]) != pairs_set(theirs["metrics"]["NEAR"]["distinct_pairs"]):
            check("random_cross", False, {"index": index, "witnesses": witnesses,
                                          "settings": settings,
                                          "mine": mine["status"], "theirs": theirs["status"]})
            return
    check("random_cross_%d" % count, True)


# ------------------------------- prototype vs independent scalar (identity refine)
def prototype_scalar_cross():
    s = dict(SETTINGS, seed=7, spatial_cell_m=0.05, max_points_per_cell=8)
    rng = random.Random(4242)
    for index in range(300):
        n = rng.randint(0, 10)
        pool = []
        for _ in range(n):
            pool.append(plane(rng.choice([1.0, 1.05, 1.2]), rng.choice([100, 450, 500]),
                              rng.choice([0.0, 6.0, 12.0])))
        rep = search_events(events(pool), identity_refine, s)
        mine = scalar_oracle(rep["witnesses"], dict(s, distinct_normal_deg=10.0,
                                                    distinct_offset_m=0.05,
                                                    support_close_ratio=0.8))
        # prototype stores raw planes with support_count; identity refine keeps them
        if rep["status"] != mine["status"]:
            check("prototype_scalar_cross", False,
                  {"index": index, "got": rep["status"], "want": mine["status"]})
            return
    check("prototype_scalar_cross_300", True)


def main():
    hand_fixtures()
    boundary_probe()
    order_probe()
    best_only_asymmetry()
    malformed_probe()
    randomised_cross_check()
    prototype_scalar_cross()
    passed = sum(1 for r in RESULTS if r["ok"])
    out = {"kind": "gli05_second_review_independent_oracle",
           "passed": passed, "total": len(RESULTS), "results": RESULTS}
    with (HERE / "02_independent_oracle.json").open("x", encoding="utf-8") as handle:
        json.dump(out, handle, ensure_ascii=False, allow_nan=False, indent=2)
    print("SUMMARY %d/%d PASS" % (passed, len(RESULTS)))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        print("ABORTED")
        raise

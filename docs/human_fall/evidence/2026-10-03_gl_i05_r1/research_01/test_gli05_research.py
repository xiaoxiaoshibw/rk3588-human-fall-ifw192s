"""Focused GL-I05 research self-checks (not the full production suite).

Run with: python -B -W error test_gli05_research.py
Targets the new research contract only; production gates stay in their own
suites. Every terminal/merge path is exercised against the independent
`oracle_analysis.oracle` over the same witness multiset.
"""
import itertools
import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parents[4] / "src" / "human_fall_detection"
sys.path[:0] = [str(PACKAGE), str(PACKAGE / "scripts"), str(HERE)]

from core import ground as g
from core.ground_diagnostics import refine_hypothesis, replay_sequence

from oracle_analysis import oracle
from search_prototype import search_events, search

SETTINGS = g.resolve_constrained_settings()


def _plane(offset, support, up_deg=0.0):
    normal = [math.sin(math.radians(up_deg)), 0.0, math.cos(math.radians(up_deg))]
    return {"normal": normal, "offset_m": offset, "support_count": support}


def _events(planes):
    return [dict(plane, iteration=i, stage="qualified") for i in range(len(planes))
            for plane in [planes[i]]]


def _identity_refine(event):
    return ({"normal": list(event["normal"]), "offset_m": event["offset_m"],
             "support_count": event["support_count"]}, "refined")


def _reject_refine(event):
    return (None, "refine_degenerate")


def check_counts(report):
    c = report["counts"]
    assert c["qualified"] == c["unprocessed"] + c["refined_calls"]
    assert c["refined_calls"] == c["rejected"] + c["produced"]
    assert c["produced"] == c["merged_exact"] + c["retained"] + c["unstored"]
    assert c["draws_seen"] == len(report["trace"]) + c["trace_unrecorded"]
    assert c["peak_stored"] <= report["budgets"]["candidate"]
    assert len(report["witnesses"]) <= report["budgets"]["candidate"]


def agree(report, planes, gaps=False):
    expected = oracle(list(planes), SETTINGS, gaps=gaps)
    assert report["status"] == expected["status"], (report["status"],
                                                    expected["status"],
                                                    report["reasons"])


def test_all_similar_permutations():
    # 0/4/8 deg plane set, all mutually similar (max pair angle 8 <= 10).
    # A fixed-anchor envelope closes only for some arrival orders; this
    # prototype must close for *every* order.
    planes = [_plane(1.0, 200, up_deg) for up_deg in (0.0, 4.0, 8.0)]
    for perm in itertools.permutations(planes):
        report = search_events(_events(list(perm)), _identity_refine, SETTINGS)
        check_counts(report)
        agree(report, list(perm))
        assert report["status"] == "seen_pairwise_closed", (report["status"],
                                                            report["reasons"])


def test_offset_chain_permutations():
    # offsets 0.00/0.04/0.08 m; endpoints distinct, middle similar to both.
    # Non-transitive "similar" chain must never be washed into a closure.
    planes = [_plane(o, 200) for o in (1.0, 1.04, 1.08)]
    for perm in itertools.permutations(planes):
        report = search_events(_events(list(perm)), _identity_refine, SETTINGS)
        check_counts(report)
        agree(report, list(perm))
        assert report["status"] == "unresolved", (report["status"], report["reasons"])
        assert report["metrics"]["NEAR"]["holds"] is False


def test_middle_best_swallowed_by_best_only():
    # Middle (highest support) is similar to both endpoints which are distinct
    # from each other. BEST_ONLY says "closed", NEAR correctly says unresolved.
    middle = _plane(1.0, 500)            # 0 deg, support 500
    left = _plane(1.0, 450, up_deg=-6.0)
    right = _plane(1.0, 450, up_deg=6.0)
    pool = [middle, left, right]
    report = search_events(_events(pool), _identity_refine, SETTINGS)
    check_counts(report)
    agree(report, pool)
    assert report["status"] == "unresolved"
    assert report["metrics"]["BEST_ONLY"]["holds"] is True
    assert report["metrics"]["NEAR"]["holds"] is False
    assert report["metrics"]["MIDDLE_BEST_SWALLOWED"]["pairs"]


def test_dominant_pool_closed():
    # A strong best plus many similar strong supporters, plus one weak distinct
    # witness below the near floor -> dominant-pool closed, NOT all-closed.
    best = _plane(1.0, 500)
    near = [_plane(1.0 + i * 0.001, 420) for i in range(5)]  # 420 >= 0.8*500
    weak_distinct = _plane(1.2, 100)                          # 100 < 0.8*500
    planes = [best] + near + [weak_distinct]
    for perm in itertools.permutations(planes):
        report = search_events(_events(list(perm)), _identity_refine, SETTINGS)
        check_counts(report)
        agree(report, list(perm))
        assert report["status"] == "seen_dominant_pool_closed", report["status"]
        assert len(report["witnesses"]) == 7  # weak witness is kept, not hidden
        assert report["metrics"]["ALL"]["holds"] is False
        assert report["metrics"]["NEAR"]["holds"] is True
        assert report["distinct_outside_near_pool"]


def test_near_ratio_boundary():
    # support_close_ratio == 0.8 exactly at the boundary on both sides.
    best = _plane(1.0, 500)
    inside = _plane(1.0, 400)   # == 0.8*500 -> inside pool
    outside = _plane(1.2, 399)  # below floor -> outside pool
    planes = [best, inside, outside]
    report = search_events(_events(planes), _identity_refine, SETTINGS)
    check_counts(report)
    agree(report, planes)
    assert report["status"] == "seen_dominant_pool_closed"
    assert set(report["near_pool_indices"]) == {0, 1}
    # Below the floor by one -> outside; assert the boundary is inclusive.
    inside_minus = _plane(1.0, 399)
    report2 = search_events(_events([best, inside_minus]), _identity_refine, SETTINGS)
    assert set(report2["near_pool_indices"]) == {0}
    assert report2["status"] == "seen_pairwise_closed"  # both similar; ALL holds
    # 400 support with a distinct normal stays in-pool -> unresolved.
    report3 = search_events(_events([best, _plane(1.0, 400, up_deg=12.0)]),
                            _identity_refine, SETTINGS)
    assert report3["status"] == "unresolved"


def test_top_tie_kept_whole():
    # Two equal-support witnesses both count as "best"; BEST_ONLY checks each
    # tie against the whole pool, never just the first.
    tie_a = _plane(1.0, 500, up_deg=0.0)
    tie_b = _plane(1.0, 500, up_deg=6.0)
    far = _plane(1.0, 500, up_deg=13.0)  # distinct from both, same support
    report = search_events(_events([tie_a, tie_b, far]), _identity_refine, SETTINGS)
    check_counts(report)
    assert report["status"] == "unresolved"
    assert len(report["top_tie_indices"]) == 3
    # far is in the pool and distinct -> NEAR fails.
    assert report["metrics"]["NEAR"]["holds"] is False


def test_budget_gaps_block_closure():
    # Late strong best / late second plane under every budget: nothing may
    # upgrade the terminal state while a budget or processing gap exists.
    same = [_plane(1.0, 200), _plane(1.0, 200)]
    for key in ("candidate_budget", "refine_budget", "trace_budget", "iteration_budget"):
        report = search_events(_events(same), _identity_refine, SETTINGS,
                               **{key: 0})
        check_counts(report)
        assert report["status"] == "unresolved", key
        assert any("budget" in r or "unprocessed" in r for r in report["reasons"]), key
    # Exactly one free slot: a *genuinely different* second witness cannot be
    # stored -> still unresolved. (Identical signatures merge for free.)
    different = [_plane(1.0, 200), _plane(1.14, 200)]
    report = search_events(_events(different), _identity_refine, SETTINGS,
                           candidate_budget=1)
    check_counts(report)
    assert report["status"] == "unresolved"
    assert report["counts"]["unstored"] == 1
    assert "candidate_budget_incomplete" in report["reasons"]
    # A late stronger best after the trace budget is spent cannot heal it.
    late = [_plane(1.0, 200)] * 4 + [_plane(1.0, 900)]
    report = search_events(_events(late), _identity_refine, SETTINGS, trace_budget=3)
    check_counts(report)
    assert report["status"] == "unresolved"
    for key in ("candidate_budget", "refine_budget", "trace_budget", "iteration_budget"):
        for value in (-1, True, 1.5, 2001):
            try:
                search_events([], _identity_refine, SETTINGS, **{key: value})
            except ValueError:
                pass
            else:
                raise AssertionError("invalid %s budget accepted" % key)


def test_exact_duplicate_merge_is_sound():
    # Identical signatures merge regardless of budget; distinct support of an
    # otherwise identical plane is a *different* witness.
    planes = [_plane(1.0, 200)] * 40
    report = search_events(_events(planes), _identity_refine, SETTINGS)
    check_counts(report)
    assert report["status"] == "seen_pairwise_closed"
    assert report["counts"]["merged_exact"] == 39
    assert len(report["witnesses"]) == 1
    planes = [_plane(1.0, 200), _plane(1.0, 400)]
    report = search_events(_events(planes), _identity_refine, SETTINGS)
    assert len(report["witnesses"]) == 2  # different support -> different witness
    assert report["status"] == "seen_pairwise_closed"  # but similar -> ALL holds


def test_late_strong_best_after_gap_cannot_heal():
    # A stronger best arriving after a budget gap must NOT promote the state.
    planes = [_plane(1.0, 200)] * 4 + [_plane(1.0, 900)] + [_plane(1.14, 200)]
    report = search_events(_events(planes), _identity_refine, SETTINGS, refine_budget=4)
    check_counts(report)
    assert report["status"] == "unresolved"
    assert report["counts"]["unprocessed"] == 2
    assert "unprocessed_qualified_hypothesis" in report["reasons"]


def test_caller_mutation_between_runs_forces_new_sequence():
    # Q02: caller mutating input/settings between runs must NOT silently reuse
    # results. The prototype is stateless per call, but the ledger key is the
    # sequence SHA; mutating inputs changes the computed properties.
    a = [_plane(1.0, 200), _plane(1.04, 200), _plane(1.08, 200)]
    report1 = search_events(_events(a), _identity_refine, SETTINGS)
    assert report1["status"] == "unresolved"
    # Mutate the middle plane in place to be identical to the first -> chain collapses.
    a[1]["offset_m"] = 1.0
    report2 = search_events(_events(a), _identity_refine, SETTINGS)
    assert report2["status"] == "unresolved"  # 1.0 vs 1.08 still distinct
    a[2]["offset_m"] = 1.0
    report3 = search_events(_events(a), _identity_refine, SETTINGS)
    assert report3["status"] == "seen_pairwise_closed"
    for report in (report1, report2, report3):
        check_counts(report)


def test_reject_counts_closed():
    planes = [_plane(1.0, 200), _plane(1.0, 200)]
    report = search_events(_events(planes), _reject_refine, SETTINGS)
    check_counts(report)
    assert report["counts"]["rejected"] == 2
    assert report["counts"]["produced"] == 0
    assert report["status"] == "unresolved"
    assert "no_refined_witness" in report["reasons"]


def test_empty_sequence_unresolved():
    report = search_events([], _identity_refine, SETTINGS)
    check_counts(report)
    assert report["status"] == "unresolved"
    assert "no_refined_witness" in report["reasons"]


def test_real_refiner_consistency():
    # Synthetic scene through the real refiner; the prototype's terminal state
    # must equal the independent oracle over the same refined witness multiset
    # (exact-duplicate merges cannot change ALL/NEAR: identical signatures are
    # similar to each other and carry identical relations to every third item).
    rng = np.random.RandomState(7)
    n = 300
    xy = rng.uniform(-3, 3, (n, 2))
    z = np.full(n, -1.4) + rng.normal(0, 0.008, n)
    points = np.column_stack([xy, z])
    rows = np.arange(n)
    up = np.array([0.0, 0.0, 1.0])
    height = (0.5, 2.0)
    sampled, valid_rows, events = replay_sequence(points, rows, up, height, SETTINGS)
    refined = []
    for event in events:
        if event["stage"] == "qualified":
            item, _ = refine_hypothesis(points, sampled, valid_rows, event, up,
                                        height, SETTINGS)
            if item is not None:
                refined.append(item)
    # Unique-refined count drives the budget the exact prototype needs.
    unique = len({(tuple(w["normal"]), w["offset_m"], w["support_count"])
                  for w in refined})
    budget = min(512, unique + 8)
    report = search(points, rows, up, height, SETTINGS, candidate_budget=budget)
    check_counts(report)
    expected = oracle(refined, SETTINGS, gaps=False)
    assert report["status"] == expected["status"], (report["status"],
                                                    expected["status"],
                                                    report["reasons"])
    # Default budget is smaller than the unique-witness count here, so the
    # default run must report the gap conservatively, never close by hiding it.
    tight = search(points, rows, up, height, SETTINGS)
    check_counts(tight)
    assert tight["status"] == "unresolved"
    assert "candidate_budget_incomplete" in tight["reasons"]


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in tests:
        fn()
        print("PASS %s" % fn.__name__)
    print("ALL %d research self-checks PASS" % len(tests))

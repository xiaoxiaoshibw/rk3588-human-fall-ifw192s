"""Focused GL-I05 research self-checks (not the full production suite).

Run with: python -B -W error test_gli05_research.py
Targets the new research contract only; production gates stay in their own
suites. Every terminal/merge path is exercised against the independent
`oracle_analysis.oracle` over the same witness multiset.
"""
import itertools
import math
import sys
import copy
import tempfile
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parents[4] / "src" / "human_fall_detection"
sys.path[:0] = [str(PACKAGE), str(PACKAGE / "scripts"), str(HERE)]

from core import ground as g
from core.ground_diagnostics import refine_hypothesis, replay_sequence

from oracle_analysis import oracle
from search_prototype import search_events, search
from source_review import build_payload, write_payload, _render

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


def test_independent_scalar_all_metrics_orders():
    # This reference never calls author's oracle for its expected relationships.
    pools = [[_plane(1., 90, 0), _plane(1., 100, 13), _plane(1., 85, 6)],
             [_plane(1., 100, 0), _plane(1., 100, 13), _plane(1., 85, 6)],
             [_plane(1., 100), _plane(1.2, 79)],
             [_plane(1., 100), _plane(1.2, 80)]]
    for pool in pools:
        for perm in itertools.permutations(pool):
            top = max(w['support_count'] for w in perm)
            near = {i for i,w in enumerate(perm) if w['support_count'] >= .8*top}
            tops = {i for i,w in enumerate(perm) if w['support_count'] == top}
            pairs = []
            for i,j in itertools.combinations(range(len(perm)),2):
                dot = sum(a*b for a,b in zip(perm[i]['normal'],perm[j]['normal']))
                angle = math.degrees(math.acos(max(-1.,min(1.,dot))))
                if angle > 10 or abs(perm[i]['offset_m']-perm[j]['offset_m']) > .05:
                    pairs.append([i,j])
            expected = {'ALL':pairs,'NEAR':[p for p in pairs if set(p)<=near],
                        'BEST_ONLY':[p for p in pairs if set(p)<=near and set(p)&tops]}
            report = oracle(list(perm),SETTINGS)
            for name in expected:
                assert report['metrics'][name]['distinct_pairs'] == expected[name]


def test_oracle_trust_boundaries_and_events():
    def rejects(fn):
        try:
            fn()
        except (ValueError,TypeError):
            return
        raise AssertionError('invalid input accepted')
    for key in ('distinct_normal_deg','distinct_offset_m','support_close_ratio'):
        for value in (float('nan'),float('inf'),True,0.):
            rejects(lambda:oracle([_plane(1.,100)],dict(SETTINGS,**{key:value})))
    for normal in ([0.,0.,0.],[0.,0.,2.],[False,0.,1.],['0',0.,1.],
                   [float('nan'),0.,1.],[1.,0.]):
        rejects(lambda:oracle([dict(_plane(1.,100),normal=normal)],SETTINGS))
    for field,value in [('offset_m',float('nan')),('support_count',True),('support_count',-1)]:
        rejects(lambda:oracle([dict(_plane(1.,100),**{field:value})],SETTINGS))
    rejects(lambda:oracle([_plane(1.,100)],[]))
    rejects(lambda:search(np.zeros((100,3)),np.arange(100),[0.,0.,1.],(.5,2.),[]))
    rejects(lambda:oracle([_plane(1.,100)],SETTINGS,gaps='false'))
    rejects(lambda:search_events([{'iteration':0,'stage':'invented'}],_identity_refine,SETTINGS))
    rejects(lambda:search_events([{'iteration':2,'stage':'sample_area'}],_identity_refine,SETTINGS))


def test_trace_snapshot_settings_and_event_ceiling():
    events = _events([_plane(1.,100),_plane(1.2,85)])
    report = search_events(events,_identity_refine,SETTINGS)
    assert report['status']=='unresolved'
    assert 'actual_near_pool_competition' in report['reasons']
    events[0]['normal'][0] = 99
    assert report['trace'][0]['raw_hypothesis']['normal'][0] == 0.
    wider = dict(SETTINGS,support_close_ratio=.9)
    rerun = search_events(_events([_plane(1.,100),_plane(1.2,85)]),_identity_refine,wider)
    assert rerun['status']=='seen_dominant_pool_closed'
    endless = (dict(_plane(1.,100),iteration=i,stage='qualified') for i in itertools.count())
    limited = search_events(endless,_identity_refine,SETTINGS)
    assert limited['status']=='unresolved'
    assert 'source_sequence_ceiling_incomplete' in limited['reasons']
    assert limited['counts']['draws_seen']==2000
    check_counts(limited)


def test_source_empty_alias_row_budget_and_exclusive_output():
    bounds = {axis+'_'+side+'_m':value for axis in 'xyz'
              for side,value in [('min',-2.),('max',2.)]}
    diagnostic = dict(schema=1,kind='gli04_geometry_diagnostic',frame='source',units='m',
        source_manifest=dict(schema=1,kind='capture_input_adaptation',
            declared=dict(frame='source',units='m'),
            frame_groups={'g':dict(ordinal=0,seq=123,rows=[0,2])}),
        approved_draft=dict(up_axis=[0.,0.,1.],fit_region=dict(bounds=bounds),
            validation_regions=[dict(region_id='v'+str(i),bounds=bounds) for i in (1,2,3)]),
        box_frame_records=[dict(box=b,frame_group='g',frame_ordinal=0,seq=123,
                               stats=dict(count=int(b=='FIT'))) for b in ('FIT','v1','v2','v3')],
        experiments=[dict(label='approved',posthoc_plane=dict(normal=[0.,0.,1.],offset_m=1.,
                            origin='posthoc_PCA_all_approved_FIT_rows_not_physical'))])
    row = dict(box='FIT',frame_group='g',pooled_row=0,frame_row=0,frame_ordinal=0,
               seq=123,source_xyz_m=[0.,0.,-1.])
    a,b = (build_payload(diagnostic,[row],cap) for cap in (0,1))
    assert a['records']==b['records'] and a['stats']==b['stats']
    assert a['frames'][0]['seq']==123
    assert len(a['stats'])==4 and a['stats']['v1\ng']['count']==0
    for change in [dict(pooled_row=2),dict(frame_row=1),dict(frame_group='foreign'),
                   dict(seq=456),dict(source_xyz_m=[float('nan'),0.,0.])]:
        try:
            build_payload(diagnostic,[dict(row,**change)])
        except ValueError:
            pass
        else:
            raise AssertionError('bad sidecar accepted')
    for kind in ('duplicate_row','alias_group','wrong_units','missing_stats'):
        d = copy.deepcopy(diagnostic)
        sidecar = [row]
        if kind=='duplicate_row':sidecar=[row,row]
        if kind=='alias_group':d['source_manifest']['frame_groups']['alias']=copy.deepcopy(d['source_manifest']['frame_groups']['g'])
        if kind=='wrong_units':d['units']='cm'
        if kind=='missing_stats':d['box_frame_records'].pop()
        try:
            build_payload(d,sidecar)
        except ValueError:
            pass
        else:
            raise AssertionError(kind+' accepted')
    with tempfile.TemporaryDirectory(dir=str(HERE)) as directory:
        output = Path(directory)/'new'
        first = write_payload(a,output).read_bytes()
        try:
            write_payload(b,output)
        except ValueError:
            pass
        else:
            raise AssertionError('existing output overwritten')
        assert (output/'source_review.html').read_bytes()==first
    try:
        write_payload(a,HERE.parents[1]/'2026-10-03_gl_i05_r1')
    except ValueError:
        pass
    else:
        raise AssertionError('old evidence output accepted')
    html = _render(a)
    assert 'C.onclick' in html and 'residual(r)' in html and 'physical_verified:false' in html


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in tests:
        fn()
        print("PASS %s" % fn.__name__)
    print("ALL %d research self-checks PASS" % len(tests))

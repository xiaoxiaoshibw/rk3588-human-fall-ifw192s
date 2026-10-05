"""Conditional bounded TLS study, separate W per K; no runtime producer."""
import collections
import copy
import time
import numpy as np
from r0_01 import digest, members, scalar_oracle, g, gd, search_events


def validate_packet(points, rows, sampled, events, settings, packet):
    if not isinstance(packet, dict) or packet.get('schema') != 1 or packet.get('units') != 'm' or packet.get('frame') != 'research_source':
        raise ValueError('unsupported research packet schema/frame/units')
    source = np.asarray(points)
    if source.ndim != 2 or source.shape[1] != 3 or source.dtype.kind not in 'fiu':
        raise ValueError('numeric Nx3 source required')
    rows = g._normalise_indices(rows, 'FIT', len(points))
    sampled = g._normalise_indices(sampled, 'sampled', len(points))
    if len(set(rows.tolist())) != len(rows) or len(set(sampled.tolist())) != len(sampled) or not set(sampled).issubset(set(rows)):
        raise ValueError('sampled must be unique subset of FIT')
    if not np.all(np.isfinite(source[rows])):
        raise ValueError('nonfinite FIT cannot silently become a different study')
    resolved = g.resolve_constrained_settings(settings)
    actual = dict(source_sha=digest(source), fit_sha=digest(rows), sampled_sha=digest(sampled),
                  raw_sha=digest(events), settings_sha=digest(resolved))
    if any(packet.get(k) != v for k,v in actual.items()):
        raise ValueError('caller/source/settings/sequence identity changed')
    return resolved


def bounded_refine(points, sampled, rows, raw, up, height, s, k, resource, step=None):
    if type(k) is not int or k not in (1,2,3):
        raise ValueError('K must be 1/2/3')
    if type(resource.get('remaining')) is not int or not 0 <= resource['remaining'] <= 6000:
        raise ValueError('invalid LO budget')
    step = gd.refine_hypothesis if step is None else step
    current = copy.deepcopy(raw)
    last, rounds, seen, cycle = None, [], [], False
    resource_gap, violation = False, None
    lo_s = 0.
    for number in range(1, k+1):
        before = members(points, sampled, current, s).tolist()
        if resource['remaining'] == 0:
            resource_gap = True
            rounds.append(dict(round=number, reason='lo_resource_unprocessed', input_members=before))
            break
        resource['remaining'] -= 1
        tick = time.perf_counter()
        p, reason = step(points, sampled, rows, current, up, height, s)
        lo_s += time.perf_counter() - tick
        record = dict(round=number, input_plane={key:current[key] for key in ('normal','offset_m')},
                      input_members=before, result=copy.deepcopy(p), reason=reason)
        rounds.append(record)
        if p is None:
            violation = reason if last is not None else None
            break
        # Recheck even injected/mock numerical solver results; fixed project gates.
        normal = g._unit_vector(p['normal'], 'round normal')
        if np.arccos(np.clip(normal @ up,-1,1)) > s['max_angle_rad']:
            violation = 'later_round_angle' if last else 'first_round_angle'
        elif not height[0] <= p['offset_m'] <= height[1]:
            violation = 'later_round_height' if last else 'first_round_height'
        elif p.get('eigenvalue_ratio',0.) < s['min_planar_eigenvalue_ratio']:
            violation = 'later_round_degenerate' if last else 'first_round_degenerate'
        elif p['support_count'] < max(s['min_inliers'], int(np.ceil(s['min_fit_inlier_fraction']*len(rows)))):
            violation = 'later_round_support' if last else 'first_round_support'
        if violation:
            record['reason'] = violation
            break
        after = members(points, sampled, p, s).tolist()
        record.update(output_members=after, changed_members=len(set(before)^set(after)),
                      normal_change_deg=g._angle_deg(current['normal'], p['normal']),
                      offset_change_m=abs(current['offset_m']-p['offset_m']), stable=before == after)
        key = tuple(after)
        if seen and key != seen[-1] and key in seen:
            cycle = True
        if not seen:
            seen.append(tuple(before))
            if key != tuple(before) and key in seen:
                cycle = True
        seen.append(key)
        last = copy.deepcopy(p)
        current = last
    executed = sum('result' in r for r in rounds)
    full_k = executed == k and not violation
    stable = bool(rounds and rounds[-1].get('stable'))
    nonconverged = k > 1 and full_k and not stable
    quality_gap = bool(resource_gap or violation or nonconverged or cycle)
    reason = ('lo_resource_unprocessed' if resource_gap else
              violation if violation else 'refinement_cycle' if cycle else
              'refinement_nonconverged' if nonconverged else
              rounds[-1]['reason'] if rounds else 'empty')
    return last, dict(rounds=rounds, requested_k=k, executed=executed, full_k=full_k,
                      stable=stable, cycle=cycle, nonconverged=nonconverged,
                      resource_gap=resource_gap, violation=violation, quality_gap=quality_gap,
                      lo_elapsed_s=lo_s, reason=reason,
                      note='last valid witness retained for diagnostics; no successful fallback after gap')


def run_variant(points, sampled, rows, events, up, height, s, k, lo_budget=6000, **budgets):
    if type(k) is not int or k not in (1,2,3):
        raise ValueError('K must be 1/2/3 even for empty sequence')
    if type(lo_budget) is not int or not 0 <= lo_budget <= 6000:
        raise ValueError('invalid LO budget even for empty sequence')
    s = g.resolve_constrained_settings(s)
    up = g._unit_vector(up, 'up')
    height = g._height_interval(height)
    source = np.asarray(points)
    if source.ndim != 2 or source.shape[1] != 3 or source.dtype.kind not in 'fiu':
        raise ValueError('numeric Nx3 source required')
    rows = g._normalise_indices(rows, 'FIT', len(source))
    sampled = g._normalise_indices(sampled, 'sampled', len(source))
    if not set(sampled).issubset(set(rows)) or not np.all(np.isfinite(source[rows])):
        raise ValueError('nonfinite FIT or foreign sampled rows')
    # ponytail: once-per-call dtype conversion, as frozen I05 search; no persistent cache.
    points = np.asarray(source, dtype=np.float64)
    resource = dict(remaining=lo_budget)
    details, w = [], []
    def refine(e):
        p, detail = bounded_refine(points, sampled, rows, e, up, height, s, k, resource)
        details.append(dict(iteration=e['iteration'], **detail))
        if p is not None:
            w.append(p)
        return p, detail['reason']
    report = search_events(events, refine, s, candidate_budget=budgets.pop('candidate_budget',512), **budgets)
    qgap = any(d['quality_gap'] for d in details)
    if qgap:
        report['status'] = 'unresolved'
        report['gaps_input'] = True
        report['reasons'] = sorted(set(report['reasons']) | {d['reason'] for d in details if d['quality_gap']})
    scalar = scalar_oracle(w,s,gaps=report['gaps_input'])
    unique = scalar_oracle(report['witnesses'],s,gaps=report['gaps_input'])
    assert report['status'] == scalar['status']
    for metric in ('ALL','NEAR','BEST_ONLY'):
        assert report['metrics'][metric]['distinct_pairs'] == unique['metrics'][metric]['distinct_pairs']
        if not report['gaps_input']:
            assert report['metrics'][metric]['holds'] == scalar['metrics'][metric]['holds']
    # Publication uses full W; bounded storage results have a different explicit domain.
    from oracle_analysis import oracle
    tick = time.perf_counter()
    full = oracle(w, s, gaps=report['gaps_input'])
    report['stage_elapsed_s']['decision'] += time.perf_counter() - tick
    report['stored_subset_diagnostics'] = {key: copy.deepcopy(report[key]) for key in
        ('best_support','near_pool_indices','top_tie_indices','metrics','witness_count')}
    for key in ('best_support','near_pool_indices','top_tie_indices','metrics','witness_count'):
        report[key] = full[key]
    report['metric_domain'] = 'full per-event W in variant.W; witnesses field is bounded exact storage subset'
    for metric in ('ALL','NEAR','BEST_ONLY'):
        assert report['metrics'][metric]['distinct_pairs'] == scalar['metrics'][metric]['distinct_pairs']
    assert report['best_support'] == max((p['support_count'] for p in w), default=None)
    counts = collections.Counter()
    for d in details:
        for key in ('full_k','stable','cycle','nonconverged','resource_gap'):
            counts[key] += int(d[key])
        counts['violation'] += int(bool(d['violation']))
        counts['tls_calls'] += d['executed']
    return dict(variant_id='sampled_tls_K%d_v1'%k, W=w, details=details, report=report,
                refinement_counts=dict(counts), lo_budget=lo_budget, lo_remaining=resource['remaining'],
                lo_elapsed_s=sum(d['lo_elapsed_s'] for d in details),
                physical_verified=False, ground_valid=False,
                comparison_domain='fixed raw sequence/sample; W changes with K; full FIT only support',
                scalar_full=dict(status=scalar['status'],best_support=scalar['best_support'],
                    metrics={key:dict(holds=v['holds'],distinct_pair_count=len(v['distinct_pairs'])) for key,v in scalar['metrics'].items()}))

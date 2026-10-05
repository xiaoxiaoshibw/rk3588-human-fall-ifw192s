"""Read-only frozen-sequence diagnostics. Output is research, never calibration."""
import collections
import hashlib
import itertools
import json
import math
from pathlib import Path
import sys
import time

import numpy as np

HERE = Path(__file__).resolve().parent
RUN = HERE.parent
ROOT = RUN.parents[3]
PACKAGE = ROOT / 'src/human_fall_detection'
I05 = ROOT / 'docs/human_fall/evidence/2026-10-04_gl_i05_r2/research_01'
sys.path[:0] = [str(PACKAGE), str(PACKAGE / 'scripts'), str(I05)]
from core import ground as g
from core import ground_diagnostics as gd
from search_prototype import search_events

SEEDS = (7, 19, 41)
KINDS = ('clean', 'low_noise', 'high_noise', 'wall', 'table', 'dual',
         'density', 'missing', 'collinear', 'narrow_band')


def digest(value):
    if isinstance(value, np.ndarray):
        value = {'shape': list(value.shape), 'dtype': str(value.dtype),
                 'bytes': hashlib.sha256(value.tobytes()).hexdigest()}
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False).encode()).hexdigest()


def write_new(path, value):
    path = Path(path)
    if path.parent.resolve() != HERE.resolve() or path.exists() or path.is_symlink():
        raise ValueError('new numbered output in research root required')
    with path.open('x', encoding='utf-8') as f:
        json.dump(value, f, ensure_ascii=False, allow_nan=False, indent=2)


def scalar_oracle(w, settings, gaps=False):
    """Independent scalar reference: no production/I05 relationship helpers."""
    best = max((p['support_count'] for p in w), default=None)
    near = [i for i, p in enumerate(w) if p['support_count'] >= settings['support_close_ratio'] * best]
    tops = [i for i, p in enumerate(w) if p['support_count'] == best]
    near_set, top_set = set(near), set(tops)
    pairs = {'ALL': [], 'NEAR': [], 'BEST_ONLY': []}
    for i, j in itertools.combinations(range(len(w)), 2):
        dot = sum(a * b for a, b in zip(w[i]['normal'], w[j]['normal']))
        angle = math.degrees(math.acos(max(-1., min(1., dot))))
        if angle > settings['distinct_normal_deg'] or abs(w[i]['offset_m'] - w[j]['offset_m']) > settings['distinct_offset_m']:
            pairs['ALL'].append([i, j])
            if i in near_set and j in near_set:
                pairs['NEAR'].append([i, j])
                if i in top_set or j in top_set:
                    pairs['BEST_ONLY'].append([i, j])
    status = ('unresolved' if gaps or not w or pairs['NEAR'] else
              'seen_dominant_pool_closed' if pairs['ALL'] else 'seen_pairwise_closed')
    return dict(best_support=best, near_pool_indices=near, top_tie_indices=tops,
                metrics={k: dict(holds=not v, distinct_pairs=v) for k, v in pairs.items()}, status=status)


def plane_error(p):
    return dict(normal_deg=math.degrees(math.acos(max(-1., min(1., p['normal'][2])))),
                offset_m=abs(p['offset_m'] - 1.4))


def scene(kind, seed, permutation=False):
    rng = np.random.RandomState(seed)
    n = 500
    xy = rng.uniform(-3., 3., (n, 2))
    noise = {'low_noise': .008, 'high_noise': .035}.get(kind, 0.)
    z = np.full(n, -1.4) + rng.normal(0., noise, n)
    if kind == 'density':
        xy[:400] = rng.uniform(-.3, .3, (400, 2))
    if kind == 'missing':
        xy[:, 0] = rng.uniform(1., 3., n)
    if kind == 'collinear':
        xy[:, 1] = 0.
    if kind == 'narrow_band':
        xy[:, 1] *= .003
    fit = np.column_stack([xy, z])
    if kind == 'table':
        fit[n // 2:, 2] = -.8
    if kind == 'dual':
        fit[n // 2:, 2] = -1.54
    if kind == 'wall':
        wall = np.column_stack([np.full(1000, 2.), rng.uniform(-3, 3, 1000), rng.uniform(-2., 1., 1000)])
        fit = np.vstack([fit, wall])
    if permutation:
        fit = fit[rng.permutation(len(fit))]
    # Source-space selection predetermined, three distinct source frames and regions.
    bounds = ((-3., -1., -3., -1.), (1., 3., -3., -1.), (-1., 1., 1., 3.))
    holds = []
    for x0, x1, y0, y1 in bounds:
        holds.append(np.column_stack([rng.uniform(x0, x1, 80), rng.uniform(y0, y1, 80),
                                      np.full(80, -1.4) + rng.normal(0., noise, 80)]))
    points = np.vstack([fit] + holds)
    regions = [dict(region_id='v%d' % i, frame_group='hold%d' % i,
                    indices=list(range(len(fit) + 80 * i, len(fit) + 80 * (i + 1))),
                    spatial_xy_bounds=list(bounds[i])) for i in range(3)]
    return points, np.arange(len(fit), dtype=np.int64), regions


def settings(seed):
    return g.resolve_constrained_settings(dict(seed=seed, spatial_cell_m=.05, max_points_per_cell=8))


def quality(points, rows, p, s):
    cloud = points[rows]
    residual = cloud @ np.asarray(p['normal']) + p['offset_m']
    cells = np.floor(cloud[:, :2] / s['spatial_cell_m']).astype(np.int64)
    inside = np.abs(residual) <= s['inlier_threshold_m']
    total = len(set(map(tuple, cells.tolist())))
    covered = len(set(map(tuple, cells[inside].tolist())))
    return dict(gd.residual_stats(cloud, p['normal'], p['offset_m'], s['inlier_threshold_m']),
                J_m2=float(np.mean(np.minimum(residual ** 2, s['inlier_threshold_m'] ** 2))),
                occupied_xy_cells=total, supported_xy_cells=covered,
                source_xy_cell_coverage=covered / total if total else 0.)


def members(points, sampled, p, s):
    return sampled[np.abs(points[sampled] @ np.asarray(p['normal']) + p['offset_m']) <= s['inlier_threshold_m']]


def frozen_actions(events, s):
    """Annotate old representative retention only; final parity checked natively."""
    candidates, trace = [], []
    for e in events:
        record = dict(iteration=e['iteration'], action='raw_rejected', source_stage=e['stage'])
        if e['stage'] == 'qualified':
            old = next((p for p in candidates if gd.similar(p, e, s)), None)
            if old is not None:
                record.update(action='representative_replace' if e['support_count'] > old['support_count'] else 'representative_merged',
                              representative_iteration=old['iteration'])
                if e['support_count'] > old['support_count']:
                    old.update(e)
            else:
                candidates.append(dict(e))
                record['action'] = 'representative_retained'
            if len(candidates) > 8:
                candidates.sort(key=lambda p: p['support_count'], reverse=True)
                record['evicted_iterations'] = [p['iteration'] for p in candidates[8:]]
                candidates = candidates[:8]
        trace.append(record)
    return trace, candidates


def r0_case(name, points, rows, regions, up, height, s, synthetic=True):
    tick = time.perf_counter()
    sampled, fit, iterator = gd.replay_sequence(points, rows, up, height, s)
    sampling = time.perf_counter() - tick
    tick = time.perf_counter()
    events = list(iterator)
    raw_time = time.perf_counter() - tick
    baseline = g.fit_ground_plane_constrained(points, s, 'research_source', up, height, rows, 'fit', regions)
    replay = gd.replay_frozen_search(points, rows, up, height, s)
    assert baseline['candidates'] == replay['candidates']
    assert baseline['sampled_fit_count'] == len(sampled)
    assert baseline.get('competition_truncated', False) == replay['competition_truncated']
    trace, w, bias = [], [], []
    def refine(e):
        p, reason = gd.refine_hypothesis(points, sampled, fit, e, up, height, s)
        trace.append(dict(iteration=e['iteration'], reason=reason, result=p))
        if p is not None:
            w.append(p)
            before, after = members(points, sampled, e, s), members(points, sampled, p, s)
            trace[-1].update(input_members=before.tolist(), output_members=after.tolist(),
                             quality=quality(points, fit, p, s))
            if synthetic and name.startswith('high_noise') and not np.array_equal(before, after):
                reference = gd.pca_plane(points[fit], up)
                err, referr = plane_error(p), plane_error(reference)
                if err['normal_deg'] > max(.1, 2 * referr['normal_deg']):
                    bias.append(dict(iteration=e['iteration'], one_tls_error=err,
                                     labeled_ground_all_tls_error=referr,
                                     changed_members=len(set(before) ^ set(after)),
                                     raw=e, once=p, gt=dict(normal=[0., 0., 1.], offset_m=1.4)))
        return p, reason
    report = search_events(events, refine, s, candidate_budget=512)
    expected = scalar_oracle(w, s, gaps=report['gaps_input'])
    unique_expected = scalar_oracle(report['witnesses'], s, gaps=report['gaps_input'])
    for metric in ('ALL', 'NEAR', 'BEST_ONLY'):
        assert report['metrics'][metric]['distinct_pairs'] == unique_expected['metrics'][metric]['distinct_pairs']
        assert report['metrics'][metric]['holds'] == expected['metrics'][metric]['holds']
    assert report['status'] == expected['status']
    old_actions, retained = frozen_actions(events, s)
    old_refine = [dict(iteration=e['iteration'], result=gd.refine_hypothesis(points, sampled, fit, e, up, height, s)) for e in retained]
    best = max(w, key=lambda p: p['support_count']) if w else None
    return dict(case=name, source_sha=digest(points), fit_sha=digest(rows), settings_sha=digest(s),
                up=up.tolist(), height=list(height), settings=s, seed=s['seed'],
                sampled_rows=sampled.tolist(), sampled_sha=digest(sampled), raw_sha=digest(events), raw=events,
                input_fit_count=len(rows), valid_fit_rows=fit.tolist(), raw_counts=dict(collections.Counter(e['stage'] for e in events)),
                frozen=dict(status=baseline['status'], reason=baseline['reason'], candidates=baseline['candidates'],
                            competition_truncated=replay['competition_truncated'], raw_actions=old_actions, refinement=old_refine),
                full_refinement=trace, W=w, report=report, scalar_full=dict(status=expected['status'],
                metrics={k: dict(holds=v['holds'], distinct_pair_count=len(v['distinct_pairs'])) for k,v in expected['metrics'].items()},
                best_support=expected['best_support'], top_tie_count=len(expected['top_tie_indices'])),
                bias_evidence=bias[:1], multiplicity_domain='W full per event; prototype metrics unique exact signatures; pair counts differ',
                best_gt_error=plane_error(best) if best and synthetic else None,
                validation=[dict(region_id=r['region_id'], frame_group=r['frame_group'],
                                 spatial_xyz_bounds=g._region(points[r['indices']]),
                                 stats=gd.residual_stats(points[r['indices']], best['normal'], best['offset_m'])) for r in regions] if best else [],
                physical_verified=False, synthetic=synthetic,
                stage_elapsed_s=dict(sampling=sampling, raw=raw_time, **{'full_'+k:v for k,v in report['stage_elapsed_s'].items()}))


def real_inputs():
    from core.capture_input import load_adapted, gate_selection
    from evaluate_gli02_candidate import _load_draft, _draft_region, _load_constrained_settings
    base = ROOT / 'docs/human_fall/evidence/2026-10-03_gl_i02_r1'
    manifest, points = load_adapted(str(base / '08_real/real_candidate.adapted.npz'))
    draft = _load_draft(str(base / 'codex_review_01/work/filled_real_draft.json'))
    fit = _draft_region(draft['fit_region'], 'FIT')
    regions = [dict(_draft_region(r, 'validation'), region_id=r['region_id']) for r in draft['validation_regions']]
    rows, regions = gate_selection(points, manifest, fit, None, fit['frame_group'], regions)
    s = _load_constrained_settings(str(PACKAGE / 'config/geometry_constrained_gli03_r1.yaml'))
    return points, rows, regions, draft, s


def main():
    results = []
    for kind, seed, perm in itertools.product(KINDS, SEEDS, (False, True)):
        points, rows, regions = scene(kind, seed, perm)
        name = '%s_%d_%s' % (kind, seed, perm)
        r = r0_case(name, points, rows, regions, np.array([0., 0., 1.]), (.5, 2.), settings(seed))
        write_new(HERE / ('r0_case_' + name + '_01.json'), r)
        results.append({k:r[k] for k in ('case','raw_counts','scalar_full','bias_evidence','best_gt_error')})
        print(name, r['scalar_full']['status'], flush=True)
    points, rows, regions, draft, s = real_inputs()
    for name, up in [('real_approved', draft['up_axis']), ('real_historical_WHAT_IF_negative_X', [-draft['up_axis'][0], 0., draft['up_axis'][2]])]:
        r = r0_case(name, points, rows, regions, g._unit_vector(up, 'up'), draft['sensor_height_interval_m'], s, False)
        write_new(HERE / ('r0_case_' + name + '_01.json'), r)
        results.append({k:r[k] for k in ('case','raw_counts','scalar_full','bias_evidence','best_gt_error')})
    found = next((r for r in results if r['bias_evidence']), None)
    if found:
        source = json.loads((HERE / ('r0_case_' + found['case'] + '_01.json')).read_text())
        kind, seed, perm = found['case'].split('_')[-3:]
        points, rows, regions = scene('high_noise', int(seed), perm == 'True')
        write_new(HERE / 'r0_minimal_bias_01.json', dict(requirement='A04/Q03', root_cause='hard inlier truncation retains raw-plane-dependent subset for one TLS',
                  source_case=found['case'], points=points[source['sampled_rows']].tolist(),
                  original_sampled_rows=source['sampled_rows'], evidence=found['bias_evidence'][0],
                  distinction='known single-plane GT; not proof of real up or ground identity'))
    write_new(HERE / 'r0_summary_01.json', dict(results=results, refinement_gate_triggered=bool(found),
              robust_gate_triggered=False, robust_reason='symmetric single-plane noise has truncation bias; wall/table/dual are explicit competing surfaces, not evidence for robust relabeling',
              observed_real_frames=89, real_use='development WHAT_IF only; not final physical holdout', physical_verified=False))


if __name__ == '__main__':
    main()

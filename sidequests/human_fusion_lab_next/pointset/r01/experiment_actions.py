"""Single-factor R2 experiments. Current-source members; bounded causal axis reference."""
import copy
import numpy as np
from scipy.spatial import cKDTree

from actions import Posture, describe_object
from core import SLOTS, EDGES, roi_mask, skeleton
from research_actions import HERE, OUT, RESULT, E, load, read, dump, sha, frame_points, masks


def recover(p, ids, foreground, fragments, dist, tau, cfg, variant):
    """One attachment to the frozen target. Never grow from newly attached points."""
    if not len(ids): return ids.copy(), []
    other = np.setdiff1d(foreground, ids)
    distances = cKDTree(p[ids]).query(p[other])[0]
    eligible = roi_mask(p[other], cfg['roi_xy'])&(p[other, 2] >= variant['z_min_m'])
    take = eligible&(distances <= variant['gap_m'])
    reasons = {int(i): 'LOCAL_FOREGROUND_POINT' for i in other[take]}
    if variant['whole_component']:
        for frag in fragments:
            if frag['count'] > cfg['fragment_max_points'] or frag['roi_fraction'] < cfg['fragment_min_roi_fraction']:
                continue
            if frag['min_target_distance_m'] > variant['gap_m'] or frag['p90_target_distance_m'] > cfg['fragment_max_p90_distance_m']:
                continue
            members = np.asarray(frag['source_indices'], dtype=int)
            safe = roi_mask(p[members], cfg['roi_xy'])&(p[members, 2] >= variant['z_min_m'])
            for i in members[safe]: reasons[int(i)] = 'LOCAL_COMPONENT_ATTACHMENT_IDENTITY_UNKNOWN'
    added = np.array(sorted(reasons), dtype=int)
    if not len(added): return ids.copy(), []
    d, nearest = cKDTree(p[ids]).query(p[added])
    records = [{'source_index': int(i), 'anchor_source_index': int(ids[a]), 'target_distance_m': float(gap),
                'background_distance_m': float(dist[i]), 'above_frozen_tolerance': bool(dist[i] > tau),
                'z_m': float(p[i, 2]), 'within_original_roi': True, 'reason': reasons[int(i)],
                'identity': 'UNKNOWN', 'provenance': 'AI_INFERRED'} for i, a, gap in zip(added, nearest, d)]
    return np.union1d(ids, added), records


def supported_regions(p, ids, axis, cfg):
    """Same frozen bands and support thresholds; a direction is not a joint prediction."""
    result = skeleton(p, ids, cfg)
    missing = lambda why: {'valid': False, 'xyz': None, 'support_source_indices': [], 'reason': why}
    nodes = {k: missing('INSUFFICIENT_CURRENT_SUPPORT') for k in SLOTS}
    lateral = np.cross(axis, [1., 0., 0.])
    if np.linalg.norm(lateral) < cfg['lateral_axis_min_norm']: lateral = np.cross(axis, [0., 1., 0.])
    lateral /= np.linalg.norm(lateral)
    local = (p-p.mean(axis=0))@np.column_stack([lateral, np.cross(lateral, axis), axis])
    low, high = np.quantile(local[:, 2], [.02, .98])
    if high-low < cfg['body_axis_min_span_m']:
        result.update(nodes=nodes, edges=[]); return result
    fraction = (local[:, 2]-low)/(high-low)
    def node(name, mask):
        support = np.flatnonzero(mask)
        if len(support) >= cfg['part_min_points']:
            nodes[name] = {'valid': True, 'xyz': p[support].mean(axis=0).tolist(),
                           'support_source_indices': ids[support].tolist(), 'reason': 'CURRENT_POINT_SUPPORTED_COARSE_REGION'}
    for name, (a, b) in zip(SLOTS[:5], cfg['body_bands']): node(name, (fraction >= a)&(fraction < b))
    for side, sign in [('A', -1), ('B', 1)]:
        for prefix, band in [('UPPER', 'upper'), ('OUTER', 'outer'), ('LOWER', 'lower'), ('END', 'end')]:
            a, b = cfg['branch_bands'][band]
            offset = cfg['outer_branch_offset_m'] if band == 'outer' else cfg['branch_offset_m']
            node(prefix+'_'+side, (sign*local[:, 0] > offset)&(fraction >= a)&(fraction < b))
    for a, b in [('LOWER_A', 'LOWER_B'), ('END_A', 'END_B')]:
        if nodes[a]['valid'] and nodes[b]['valid'] and np.linalg.norm(np.subtract(nodes[a]['xyz'], nodes[b]['xyz'])) < cfg['branch_min_separation_m']:
            nodes[a], nodes[b] = missing('BRANCHES_NOT_SEPARATED'), missing('BRANCHES_NOT_SEPARATED')
    result.update(nodes=nodes, axis=axis.tolist(), edges=[[a, b] for a, b in EDGES if nodes[a]['valid'] and nodes[b]['valid']])
    return result


class AxisHistory:
    def __init__(self, cfg):
        self.cfg = cfg; self.reliable = None; self.last_t = None; self.identity = None

    def update(self, t, fi, identity, p, ids):
        cfg = self.cfg
        if self.last_t is not None and (t <= self.last_t or t-self.last_t > cfg['max_gap_s']): self.reliable = None
        if identity != self.identity: self.reliable = None
        self.identity = identity; self.last_t = t
        if not len(ids): self.reliable = None; return None
        result = skeleton(p, ids, cfg)
        history = self.reliable
        if history and t-history['t_sec'] > cfg['axis_reference_max_age_s']: history = None
        reliable = 'axis' in result
        axis = np.array(result['axis']) if reliable else None
        source = 'CURRENT_RELIABLE_AXIS' if reliable else 'MISSING'
        diagnostics = {'reference': None, 'current_variance_fraction': None, 'axis_angle_degrees': None}
        if history:
            ref = np.array(history['axis']); vals, vecs = np.linalg.eigh(np.cov(p.T))
            principal = vecs[:, -1]
            angle = float(np.degrees(np.arccos(np.clip(abs(np.dot(ref, principal)), 0, 1))))
            variance = float(ref@np.cov(p.T)@ref/max(vals[-1], 1e-9))
            diagnostics.update(reference=history, current_variance_fraction=variance, axis_angle_degrees=angle)
            if reliable:
                if np.dot(axis, ref) < 0: axis = -axis; source = 'CURRENT_AXIS_SIGN_FROM_PAST'
            elif angle <= cfg['axis_max_angle_degrees'] and variance >= cfg['axis_min_variance_fraction']:
                axis = ref; source = 'PAST_DIRECTION_CURRENT_SUPPORT'
        if axis is not None:
            result = supported_regions(p, ids, axis, cfg)
            if reliable:
                # Fallback never refreshes reference lifetime; no chained predictions.
                self.reliable = {'fi': fi, 't_sec': t, 'axis': axis.tolist(), 'target_id': identity}
        result['direction'] = dict(source=source, **diagnostics)
        result['predicted_nodes'] = []
        result['anatomical_accuracy'] = 'UNKNOWN'
        return result


def run():
    diag = read(E/'DIAGNOSIS.json'); assert len(diag['ambiguity_frames']) == 79
    if not (E/'DIAGNOSIS_BEFORE_EXPERIMENT.md').exists(): raise ValueError('Diagnosis required first')
    exp = read(HERE/'config_research_r2.json'); cfg = read(OUT/'RUN_MANIFEST.json')['config']; cfg.update(exp)
    cat = read(OUT/'catalog.json'); prior = __import__('pathlib').Path(cfg['background_experiment'])
    tree = cKDTree(np.load(prior/'background.npz')['xyz']); tau = cat['background']['tolerance_m']
    variants = list(exp['variants'])+['axis']; totals = {k: [] for k in ['baseline']+variants}
    for rec in cat['sessions']:
        sid = rec['session_id']; meta, raw, hashes = load(sid); assert hashes == rec['source_sha256']
        reg = None if sid == cat['background']['session'] else read(prior/(sid+'_registration.json'))
        trackers = {k: Posture(cfg) for k in exp['variants']}; history = AxisHistory(cfg)
        previous = {}; previous_identity = None
        for fi in rec['available_frames']:
            row = read(OUT/sid/f'{fi:04d}.json'); diagnostic = read(RESULT/sid/f'{fi:04d}.json')
            _, p = frame_points(raw, meta['frames'][fi], reg)
            with np.load(RESULT/sid/f'{fi:04d}_sources.npz') as sets:
                fg = sets['foreground']; ids = sets['target']
            dist = np.full(len(p), np.inf); dist[fg] = tree.query(p[fg])[0]
            identity = row['body_3d'][0]['id'] if len(ids) else None
            objects = {'baseline': row['body_3d']}; added_records = {}
            for variant, rules in exp['variants'].items():
                selected, reasons = recover(p, ids, fg, diagnostic['fragments'], dist, tau, cfg, rules)
                added_records[variant] = reasons
                obj = [] if not len(selected) else [describe_object(p, selected, dist, p[np.setdiff1d(fg, selected)], tau, cfg, identity)]
                objects[variant] = obj
            axis = history.update(row['t_sec'], fi, identity, p[ids], ids)
            objects['axis'] = copy.deepcopy(row['body_3d'])
            if objects['axis']: objects['axis'][0]['skeleton'] = axis
            for variant, bodies in objects.items():
                members = np.array(bodies[0]['source_indices'], dtype=int) if bodies else np.array([], dtype=int)
                sk = bodies[0]['skeleton'] if bodies else {'nodes': {}}
                current_axis = sk.get('axis'); prev = previous.get(variant)
                adjacent = prev and fi == prev['fi']+1 and row['t_sec']-prev['t_sec'] <= cfg['max_gap_s']
                dot = float(np.dot(current_axis, prev['axis'])) if adjacent and current_axis is not None and prev['axis'] is not None else None
                membership = set(members.tolist()); baseline_members = set(ids.tolist())
                for n in sk['nodes'].values():
                    if n['valid']:
                        assert set(n['support_source_indices']) <= membership
                        assert np.allclose(n['xyz'], p[n['support_source_indices']].mean(axis=0))
                    else: assert n['xyz'] is None and not n['support_source_indices']
                if variant == 'axis' and sk.get('direction', {}).get('reference'):
                    ref = sk['direction']['reference']; assert ref['fi'] < fi and 0 < row['t_sec']-ref['t_sec'] <= cfg['axis_reference_max_age_s']
                valid_nodes = sum(n['valid'] for n in sk['nodes'].values())
                posture = trackers[variant].update(row['t_sec'], p[members] if len(members) else None) if variant in trackers else row['posture']
                assert not posture['confirmed']
                stats = {'sid': sid, 'fi': fi, 'added_count': len(membership-baseline_members), 'deleted_count': len(baseline_members-membership),
                         'target_count': len(members), 'valid_nodes': valid_nodes, 'missing_slots': 13-valid_nodes,
                         'axis_missing': bool(len(members) and current_axis is None), 'direction_flip': dot is not None and dot < 0,
                         'axis_large_turn': bool(dot is not None and abs(dot) < np.cos(np.pi/4)),
                         'remaining_fragments': sum(bool(set(f['source_indices'])-membership) for f in diagnostic['fragments']),
                         'association_interruption': bool(previous_identity is not None and identity != previous_identity),
                         'target_id': identity, 'posture_state': posture['state'], 'posture_event': posture['event'],
                         'low_added_count': sum(r['z_m'] < .04 for r in added_records.get(variant, [])),
                         'near_background_added_count': sum(r['background_distance_m'] < 2*tau for r in added_records.get(variant, [])),
                         'direction_source': sk.get('direction', {}).get('source', 'BASELINE_CURRENT_AXIS' if current_axis else 'MISSING')}
                totals[variant].append(stats)
                previous[variant] = {'fi': fi, 't_sec': row['t_sec'], 'axis': current_axis}
                if variant == 'baseline': continue
                folder = RESULT/variant/sid; folder.mkdir(parents=True, exist_ok=True)
                dump(folder/f'{fi:04d}.json', {'variant': variant, 'session_id': sid, 'frame_index': fi, 'source_sha256': hashes,
                     'body_3d': bodies, 'added_members': added_records.get(variant, []), 'deleted_source_indices': sorted(baseline_members-membership),
                     'posture': posture, 'stats': stats, 'status': 'EXPERIMENT_NOT_DEFAULT', 'human_precision': None,
                     'furniture_contamination_rate': None, 'identity_provenance': 'AI_INFERRED'})
            previous_identity = identity
        print('EXPERIMENTS', sid, len(rec['available_frames']), flush=True)
    summary = {}
    for variant, rows in totals.items():
        assert len(rows) == 1966
        action = [r for r in rows if r['sid'] != cat['background']['session']]; holdout = [r for r in rows if r['sid'] == cat['background']['session']]
        summary[variant] = {key: sum(r[key] for r in action) for key in ['added_count', 'deleted_count', 'valid_nodes', 'missing_slots',
             'axis_missing', 'direction_flip', 'axis_large_turn', 'remaining_fragments', 'association_interruption', 'low_added_count', 'near_background_added_count']}
        summary[variant].update(changed_member_frames=sum(bool(r['added_count'] or r['deleted_count']) for r in action),
             holdout_targets=sum(bool(r['target_count']) for r in holdout), holdout_added=sum(r['added_count'] for r in holdout),
             events=[{'sid': r['sid'], 'fi': r['fi'], 'event': r['posture_event']} for r in action if r['posture_event']],
             current_source_support_verified=True, human_precision=None, furniture_contamination_rate=None,
             adoption='BASELINE_RETAINED' if variant == 'baseline' else 'EXPERIMENT_ONLY_NO_IDENTITY_EVIDENCE')
    dump(E/'EXPERIMENT_COMPARISON.json', {'summary': summary, 'frames': totals, 'frozen_config_sha256': sha(HERE/'config_research_r2.json'),
         'methods_independent': True, 'holdout_not_tuned': True, 'tracking_policy': 'baseline causal track anchors held constant to isolate member recovery',
         'default': 'baseline', 'code_sha256': sha(HERE/'experiment_actions.py')})
    dump(RESULT/'experiments.json', {'summary': summary, 'default': 'baseline', 'variants': variants, 'cases': diag['cases']})


if __name__ == '__main__': run()

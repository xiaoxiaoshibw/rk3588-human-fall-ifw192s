"""HFUS-NEXT-DEV-01: exclusive, source-bound local experiments; R1 stays frozen."""
import argparse
import copy
import json
import platform
import sys
import time
from pathlib import Path

import numpy as np
import yaml
from scipy.spatial import cKDTree

from actions import HERE, ROOT, OUT, read, dump, sha, load, choose, Posture
from core import R, T, cluster, skeleton, voxelize, roi_mask
from research_actions import frame_points
from research_scene_change import domain
from scene_change import FrozenSurfaces
from scene_static import static_reference_mask
from next_contract import validate_meta

PLAN = ROOT/'docs/human_capture/evidence/2026-10-14_hfus_next_development_plan_r1'
NEW_BG = ROOT/'docs/human_capture/evidence/2026-10-14_hfus_new_empty_221808_r1'
CANDIDATES = {
    'G1_fixed': {'local': False, 'risk': False, 'radius_min_m': .10, 'radius_max_m': .17, 'support_ratio_max': 4.},
    'G2_local': {'local': True, 'risk': False, 'radius_min_m': .10, 'radius_max_m': .17, 'support_ratio_max': 4.},
    'G3_risk': {'local': True, 'risk': True, 'radius_min_m': .10, 'radius_max_m': .17, 'support_ratio_max': 4.},
}
for _rule in CANDIDATES.values():
    _rule.update(near_distance_tau_factor=2., near_vote_fraction=.5)
REASONS = ['INVALID_RAW', 'OUTSIDE_DOMAIN', 'BACKGROUND_MATCH', 'CLUSTER_REJECTED', 'UNSELECTED_CLUSTER', 'SELECTED_UNKNOWN']


def binding_equal(actual, expected):
    if actual != expected:
        raise ValueError('Version/SHA binding mismatch')


def validate_run_contract(manifest):
    if not __debug__: raise ValueError('Optimized Python is unsupported for this acceptance runner')
    if manifest.get('schema') != 'hfus-next/1': raise ValueError('Unsupported run schema')
    for n,h in manifest['code_sha256'].items(): binding_equal(sha(HERE/n),h)
    for path,h in manifest['transforms'].items(): binding_equal(sha(path),h)
    binding_equal(canonical_rules(manifest['candidates']),CANDIDATES)


def canonical_rules(rules):
    return {name:{'near_distance_tau_factor':2.,'near_vote_fraction':.5,**copy.deepcopy(rule)} for name,rule in rules.items()}


def validate_source_directory(directory):
    directory=Path(directory)
    validate_meta(read(directory/'meta.json'),(directory/'points.bin').stat().st_size)


_original_load=load
def load(sid):
    validate_source_directory(ROOT/'captures/remote'/sid)
    return _original_load(sid)


def selection_key(scores, candidate):
    return [sum(s['axis_missing'] for s in scores),
            max(s['slot_jump_m']['P95'] if s['slot_jump_m']['P95'] is not None else float('inf') for s in scores),
            max(s['cpu_ms']['P95'] for s in scores),candidate]


def source_codes(raw, nominal, cfg):
    radius = np.linalg.norm(raw, axis=1)
    valid = np.isfinite(raw).all(axis=1) & np.any(raw != 0, axis=1) & (radius > cfg['range_min_m']) & (radius < cfg['range_max_m'])
    return valid, domain(raw, nominal, cfg)


def conditional_graph(points, cfg, rule, distances, tau):
    """Symmetric bounded edges; centroids only connect, all outputs are original rows.

    ponytail: reuse installed neighborhood index on PC; a NumPy grid port needs
    separate board measurements. Normals are UNKNOWN and never identity cues.
    """
    if not len(points):
        return [], {'nodes': 0, 'edges': 0, 'rejected_edges': 0, 'sparse_nodes': 0, 'normal_status': 'UNKNOWN'}
    _, centers, inv, counts = voxelize(points, cfg['voxel_m'])
    tree = cKDTree(centers)
    k = min(cfg['cluster_min_voxels'], len(centers))
    ds, _ = tree.query(centers, k=k)
    kth = ds[:, -1] if k > 1 else np.full(len(centers), np.inf)
    sparse = kth > rule['radius_max_m']
    scale = np.clip(kth, rule['radius_min_m'], rule['radius_max_m'])
    scale[sparse] = rule['radius_min_m']
    neighbors = tree.query_pairs(rule['radius_max_m'], output_type='ndarray')
    parent = np.arange(len(centers))
    near = np.bincount(inv, weights=(distances < rule.get('near_distance_tau_factor',2.)*tau).astype(float)) / counts
    accepted = np.empty((0, 2), dtype=int)
    if len(neighbors):
        a, b = neighbors.T
        gap = np.linalg.norm(centers[a]-centers[b], axis=1)
        radius = np.sqrt(scale[a]*scale[b]) if rule['local'] else np.full(len(a), rule['radius_max_m'])
        ratio = np.maximum(counts[a], counts[b])/np.minimum(counts[a], counts[b])
        keep = (gap <= radius) & ((gap <= rule['radius_min_m']) | (ratio <= rule['support_ratio_max']))
        if rule['risk']:
            keep &= ~((gap > rule['radius_min_m']) & (near[a] > rule.get('near_vote_fraction',.5)) & (near[b] > rule.get('near_vote_fraction',.5)))
        accepted = neighbors[keep]
    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for a, b in accepted:
        x, y = find(a), find(b)
        if x != y:
            parent[max(x, y)] = min(x, y)
    labels = np.array([find(i) for i in range(len(centers))])
    groups = []
    for label in np.unique(labels):
        ids = np.flatnonzero(labels[inv] == label)
        if len(ids) >= cfg['cluster_min_points']:
            groups.append(ids)
    return groups, {'nodes': len(centers), 'edges': len(accepted), 'rejected_edges': len(neighbors)-len(accepted),
                    'sparse_nodes': int(sparse.sum()), 'normal_status': 'UNKNOWN',
                    'accepted_edges': accepted, 'candidate_edges': neighbors, 'voxel_members': inv,
                    'centers': centers, 'counts': counts, 'local_scale_m': scale}


class CausalSelection:
    def __init__(self, cfg):
        self.cfg = copy.deepcopy(cfg)
        self.last = self.seen = self.t = None
        self.generation = 0
        self.posture = Posture(copy.deepcopy(cfg))

    def update(self, t, groups, p, fg):
        reset = (self.t is not None and (t <= self.t or t-self.t > self.cfg['max_gap_s'])) or (self.seen is not None and t-self.seen > self.cfg['max_gap_s'])
        if reset:
            self.last = self.seen = None
            self.posture = Posture(copy.deepcopy(self.cfg))
        win = choose(groups, p, fg, self.cfg, self.last, None)
        ids = fg[groups[win[1]]] if win is not None else np.empty(0, int)
        if win is not None:
            if self.last is None:
                self.generation += 1
                self.posture = Posture(copy.deepcopy(self.cfg))
            self.last, self.seen = win[2][:2], t
        self.t = t
        return ids, 'GEOMETRY-'+str(self.generation) if len(ids) else None, self.posture.update(t, p[ids] if len(ids) else None), reset


def node_metrics(sk, prev, identity, t, cfg):
    consecutive = prev is not None and identity == prev['identity'] and 0 < t-prev['t'] <= cfg['max_gap_s']
    jumps = [float(np.linalg.norm(np.subtract(n['xyz'], prev['sk']['nodes'][k]['xyz'])))
             for k, n in sk['nodes'].items() if consecutive and n['valid'] and prev['sk']['nodes'][k]['valid']]
    dot = float(np.dot(sk['axis'], prev['sk']['axis'])) if consecutive and 'axis' in sk and 'axis' in prev['sk'] else None
    return {'axis_missing': 'axis' not in sk, 'valid_nodes': sum(n['valid'] for n in sk['nodes'].values()),
            'slot_jump_m': max(jumps) if jumps else None, 'unoriented_axis_angle_rad': float(np.arccos(np.clip(abs(dot), 0, 1))) if dot is not None else None,
            'sign_flip': dot is not None and dot < 0}


def preflight(e):
    if (e/'RUN_MANIFEST.json').exists():raise ValueError('Existing frozen run; read via FrozenRun. Computation requires a new evidence directory.')
    expected = read(PLAN/'DATA_PREFLIGHT.json')
    checks = []
    for rec in expected['checks']:
        sid = rec['sid']
        m, raw, hashes = load(sid)
        binding_equal(hashes, {'meta': rec['files'][0]['sha256'], 'points': rec['files'][1]['sha256']})
        assert len(m['frames']) == rec['expected_frames']
        checks.append({'sid': sid, 'frames': len(m['frames']), 'source_sha256': hashes,
                       'stride': 28, 'offset_count_monotonic_time': 'PASS',
                       'files': [{'path': str(ROOT/'captures/remote'/sid/n), 'bytes': (ROOT/'captures/remote'/sid/n).stat().st_size,
                                  'sha256': hashes[k]} for n, k in [('meta.json', 'meta'), ('points.bin', 'points')]]})
        del raw
    cfg = read(OUT/'RUN_MANIFEST.json')['config']; prior = Path(cfg['background_experiment'])
    assets = []
    for rec in expected['background_assets']:
        p = Path(rec['path']); binding_equal(sha(p), rec['sha256'])
        with np.load(p) as d:
            assert d['xyz'].ndim == 2 and d['xyz'].shape[1] == 3 and np.isfinite(d['xyz']).all()
        assets.append({'path': str(p), 'sha256': sha(p), 'bytes': p.stat().st_size})
    transforms = {str(prior/(r['sid']+'_registration.json')): sha(prior/(r['sid']+'_registration.json')) for r in checks if not r['sid'].startswith('cap_20261014')}
    preflight_record = {'checks': checks, 'background_assets': assets, 'transforms': transforms,
         'R': R.tolist(), 'T': T.tolist(), 'legacy_empty_source': 'BLOCKED' if not (ROOT/'captures/remote/cap_20261013_131958/meta.json').exists() else 'PRESENT',
         'command': sys.argv, 'stage_status': 'PREFLIGHT_CHECKS_COMPLETED', 'python': platform.python_version(), 'numpy': np.__version__}
    index=1;preflight_path=e/'DATA_PREFLIGHT.json'
    while preflight_path.exists():
        index+=1;preflight_path=e/('DATA_PREFLIGHT_R'+str(index)+'.json')
    dump(preflight_path,preflight_record)
    split = read(PLAN/'EXPERIMENT_SPLIT.json')
    new = read(NEW_BG/'NEW_EMPTY_ANALYSIS.json')
    dump(e/'RUN_MANIFEST.json', {'schema': 'hfus-next/1', 'run_id': e.name, 'acceptance_path': str(PLAN/'ACCEPTANCE_V2.md'),
         'acceptance_sha256': sha(PLAN/'ACCEPTANCE_V2.md'), 'source_sha256': {r['sid']: r['source_sha256'] for r in checks},
         'background_assets': assets, 'transforms': transforms, 'config': copy.deepcopy(cfg),
         'controls': yaml.safe_load((HERE/'config_scene_change.yaml').read_text(encoding='utf8')),
         'limits': read(HERE/'action_research_scene_static/CALIBRATION.json')['limits'],
         'old_tau': read(OUT/'catalog.json')['background']['tolerance_m'], 'new_tau': new['candidate_tolerance_m'],
         'split': split, 'empty_folds': {'FIT': list(range(0,272,3)), 'CAL': list(range(1,272,3)), 'HOLDOUT': list(range(2,272,3))},
         'candidates': CANDIDATES, 'selection': 'source/causal PASS; candidate and axis missing no increase; P95 measured slot jump no increase; NA ineligible; order axis missing, P95 jump, P95 runtime, candidate ID',
         'comparison_consumed': False, 'semantic': {'K': [], 'X': 'ALL_U_UNREVIEWED', 'precision': 'BLOCKED', 'recall': 'BLOCKED', 'IoU': 'BLOCKED'},
         'reproduction': ['python -B -W error next_dev.py preflight --evidence <new_directory>', 'python -B -W error next_dev.py run --evidence '+str(e)],
         'code_sha256': {n: sha(HERE/n) for n in ['next_dev.py', 'core.py', 'actions.py', 'scene_change.py', 'scene_static.py', 'research_actions.py', 'research_scene_change.py']}})
    print('PREFLIGHT PASS: 18 original files; 1934 actions + 272 empty', flush=True)


def quant(values):
    a = [v for v in values if v is not None]
    return {'P50': float(np.quantile(a,.5)), 'P95': float(np.quantile(a,.95)), 'max': float(max(a))} if a else {'P50': None, 'P95': None, 'max': None, 'status': 'NA'}


def aggregate(rows):
    return {'frames': len(rows), 'candidate_missing': sum(r['selected_count']==0 for r in rows), 'axis_missing': sum(r['axis_missing'] for r in rows),
            'slot_jump_m': quant([r['slot_jump_m'] for r in rows]), 'cpu_ms': quant([r['cpu_ms'] for r in rows]),
            'selected_count': quant([r['selected_count'] for r in rows]), 'foreground_count': sum(r['fg_count'] for r in rows),
            'sign_flips': sum(r['sign_flip'] for r in rows), 'axis_angle_rad': quant([r['unoriented_axis_angle_rad'] for r in rows]),
            'worst_slot_frame': max((r for r in rows if r['slot_jump_m'] is not None), key=lambda r:r['slot_jump_m'],default=None)}


def run(e):
    manifest = read(e/'RUN_MANIFEST.json');validate_run_contract(manifest)
    rules=canonical_rules(manifest['candidates'])
    cfg, controls = copy.deepcopy(manifest['config']), copy.deepcopy(manifest['controls'])
    out = e/'runs'; out.mkdir(exist_ok=False)
    models = {}
    for tag,asset,tau in [('old',manifest['background_assets'][0],manifest['old_tau']), ('new',manifest['background_assets'][1],manifest['new_tau']), ('new_oldtau',manifest['background_assets'][1],manifest['old_tau'])]:
        binding_equal(sha(asset['path']),asset['sha256'])
        with np.load(asset['path']) as d: models[tag] = FrozenSurfaces(d['xyz'].copy(),tau,copy.deepcopy(controls))
    baseline = {'A': ('old',None), 'B': ('new',None), 'B_tau': ('new_oldtau',None)}
    candidate_groups = {tag+'_'+g: (tag,g) for tag in ['old','new'] for g in rules}
    records = {g: [] for g in list(baseline)+list(candidate_groups)}
    common = e/'common'; common.mkdir()
    catalog = read(OUT/'catalog.json')
    session_catalog = []
    diagnostics = []
    for sid,hashes in manifest['source_sha256'].items():
        m, raw, actual = load(sid); binding_equal(actual, hashes)
        empty = sid == 'cap_20261014_221808'
        frames = manifest['empty_folds']['HOLDOUT'] if empty else list(range(len(m['frames'])))
        reg = None if empty else read(Path(cfg['background_experiment'])/(sid+'_registration.json'))
        if reg and reg['gate']['status'] != 'PASS': raise ValueError('Rejected historical transform')
        record = next((r for r in catalog['sessions'] if r['session_id']==sid), None)
        session_catalog.append({**(record or {}), 'session_id': sid, 'activity': record['activity'] if record else 'NEW_EMPTY_HOLDOUT',
                                'source_sha256': hashes, 'frame_count':len(m['frames']), 'available_frames': frames,
                                'duration_sec': (m['frames'][-1]['stamp_sec']+m['frames'][-1]['stamp_nanosec']*1e-9)-(m['frames'][0]['stamp_sec']+m['frames'][0]['stamp_nanosec']*1e-9),
                                'reference_status':'UNKNOWN_NO_INDEPENDENT_IDENTITY_GT'})
        states = {g:CausalSelection(cfg) for g in records}; previous = {}
        (common/sid).mkdir()
        t0 = m['frames'][0]['stamp_sec']+m['frames'][0]['stamp_nanosec']*1e-9
        for fi in frames:
            started=time.perf_counter(); f=m['frames'][fi]; q,nominal=frame_points(raw,f,reg)
            valid,nominal_domain=source_codes(q,nominal,cfg)
            anchor=static_reference_mask(nominal,nominal_domain,cfg['roi_xy'])
            _,vibration=models['old'].compensate(nominal[anchor],manifest['limits'])
            p=nominal@np.array(vibration['R']).T+vibration['t']
            fixed_domain=domain(q,p,cfg)
            preprocessing_ms=(time.perf_counter()-started)*1000
            t=f['stamp_sec']+f['stamp_nanosec']*1e-9
            np.savez_compressed(common/sid/f'{fi:04d}.npz',raw_xyz=q,nominal_xyz=nominal,xyz=p,valid=valid,
                                nominal_domain=nominal_domain,domain=fixed_domain,source_rows=np.arange(len(q)),
                                global_rows=np.arange(len(q))+f['offset_points'])
            variants=dict(baseline)
            tuning = sid in manifest['split']['tuning_sids']
            if tuning: variants.update(candidate_groups)
            split_cache={}
            for g,(tag,rule_id) in variants.items():
                started=time.perf_counter()
                if tag not in split_cache:
                    split_cache[tag]=models[tag].split_pose_hypotheses(nominal,p,fixed_domain)
                fg,matched,dist,extra,ambiguous=split_cache[tag]
                if rule_id:
                    groups, graph=conditional_graph(p[fg],cfg,rules[rule_id],dist[fg],models[tag].tau)
                else:
                    groups,_=cluster(p[fg],cfg);graph={'normal_status':'UNKNOWN','method':'FROZEN_DBSCAN'}
                ids,identity,posture,reset=states[g].update(t,groups,p,fg)
                sk=skeleton(p[ids],ids,cfg)
                metrics=node_metrics(sk,previous.get(g),identity,t,cfg); previous[g]={'identity':identity,'t':t,'sk':sk}
                all_members=np.concatenate([fg[x] for x in groups]) if groups else np.empty(0,int)
                assert len(all_members)==len(np.unique(all_members)) and not matched[all_members].any()
                codes=np.zeros(len(p),dtype='u1');codes[valid]=1;codes[fixed_domain]=2;codes[fg]=3;codes[all_members]=4;codes[ids]=5
                assert len(codes)==f['count_points'] and sum(np.count_nonzero(codes==i) for i in range(6))==len(p)
                for n in sk['nodes'].values():
                    if n['valid']:
                        assert set(n['support_source_indices']) <= set(ids.tolist())
                        assert np.allclose(n['xyz'],p[n['support_source_indices']].mean(axis=0))
                folder=out/g/sid;folder.mkdir(parents=True,exist_ok=True)
                graph_arrays={k:v for k,v in graph.items() if isinstance(v,np.ndarray)}
                cluster_ids=np.full(len(p),-1,dtype='i4')
                for ci,members in enumerate(groups):cluster_ids[fg[members]]=ci
                np.savez_compressed(folder/f'{fi:04d}_members.npz',terminal_reason=codes,cluster_id=cluster_ids,
                                    pose_ambiguous=ambiguous,background_match=matched,background_distance=dist,
                                    foreground=fg,selected=ids,**graph_arrays)
                cpu=(time.perf_counter()-started)*1000+preprocessing_ms
                body=[]
                if len(ids):
                    sample=ids[np.linspace(0,len(ids)-1,min(len(ids),cfg['display_sample_points']),dtype=int)]
                    body=[{'id':identity,'kind':'AUTOMATIC_CANDIDATE','points':p[sample].tolist(),'display_source_indices':sample.tolist(),
                           'source_indices':ids.tolist(),'point_count':len(ids),'bbox':{'min':p[ids].min(axis=0).tolist(),'max':p[ids].max(axis=0).tolist()},
                           'skeleton':sk,'semantic_identity':'UNKNOWN','independence':{'score_0_100':0,'separation_status':'UNKNOWN'},
                           'model_status':'NOT_USED','pointnet_prob':0,'rf_xyz_prob':0}]
                row={'schema':'hfus-next-frame/1','run_id':manifest['run_id'],'session_id':sid,'frame_index':fi,
                     'source_sha256':hashes,'source_frame':f,'device_time':t,'t_sec':t-t0,'variant':g,
                     'background_sha256':manifest['background_assets'][0 if tag=='old' else 1]['sha256'],
                     'transform_sha256':None if empty else manifest['transforms'][str(Path(cfg['background_experiment'])/(sid+'_registration.json'))],
                     'manifest_sha256':sha(e/'RUN_MANIFEST.json'),'member_sha256':sha(folder/f'{fi:04d}_members.npz'),
                     'common_sha256':sha(common/sid/f'{fi:04d}.npz'),'code_sha256':manifest['code_sha256'],
                     'raw_count':len(p),'fg_count':len(fg),'background_removed':int(matched.sum()),'roi_fg_count':int(roi_mask(p[fg],cfg['roi_xy']).sum()),
                     'body_3d':body,'roi_3d':body,'full_3d':body,'reference':[], 'metrics':{},
                     'foreground_display':p[fg[np.linspace(0,len(fg)-1,min(len(fg),1500),dtype=int)]].tolist() if len(fg) else [],
                     'posture':posture,'vibration':vibration,'selection':{'selected_source_indices':ids.tolist(),'candidate_count':len(groups),'uses_future_action_points':False},
                     'graph':{k:v for k,v in graph.items() if not isinstance(v,np.ndarray)},
                     'semantic':{'U_count':int(nominal_domain.sum()),'K_count':0,'X_count':int(nominal_domain.sum()),'X_fraction':1. if nominal_domain.any() else None,
                                 'prediction_unknown_fraction':1. if len(ids) else None,'prediction_outside_U':int((~nominal_domain[ids]).sum()),'precision':'BLOCKED','recall':'BLOCKED','IoU':'BLOCKED'},
                     'added_members':[], 'connection_evidence':[], 'delta':{'added_count':0,'removed_count':0}}
                dump(folder/f'{fi:04d}.json',row)
                stat={'sid':sid,'fi':fi,'device_time':t,'selected_count':len(ids),'fg_count':len(fg),'cpu_ms':cpu,'preprocessing_ms':preprocessing_ms,
                      'vibration':vibration['status'],'identity':identity,'state':posture['state'],'distance_m':float(np.linalg.norm(np.median(p[ids],axis=0))) if len(ids) else None,
                      'height_p90_m':float(np.quantile(p[ids,2],.9)) if len(ids) else None,'reset':reset,**metrics}
                records[g].append(stat)
                if fi in [119,140,232,124] and g=='A':
                    diagnostics.append({'sid':sid,'fi':fi,'source_sha256':hashes,'selection':ids.tolist(),'stats':stat,
                                        'graph_geometry_identity':'UNKNOWN','underground_rows':np.flatnonzero(fixed_domain & (p[:,2]<0)).tolist()})
            if fi%50==0:print(sid,fi,'done',flush=True)
        print('SESSION COMPLETE',sid,len(frames),flush=True)
    dump(e/'BASELINE_STATS.json',records);dump(e/'DIFFICULT_FRAMES.json',diagnostics)
    dump(e/'catalog.json',{'sessions':session_catalog,'roi_xy':cfg['roi_xy'],'default':'R1_BASELINE'})
    selection=[]
    for candidate in rules:
        reasons=[];scores=[]
        for tag,baseline_id in [('old','A'),('new','B')]:
            a=aggregate([r for r in records[baseline_id] if r['sid'] in manifest['split']['tuning_sids']])
            b=aggregate(records[tag+'_'+candidate]);scores.append(b)
            for metric in ['candidate_missing','axis_missing']:
                if b[metric]>a[metric]:reasons.append(tag+':'+metric)
            if b['slot_jump_m']['P95'] is None:reasons.append(tag+':NA')
            elif b['slot_jump_m']['P95']>a['slot_jump_m']['P95']:reasons.append(tag+':P95_SLOT_REGRESSION')
        selection.append({'id':candidate,'eligible':not reasons,'reasons':reasons,'score':selection_key(scores,candidate)})
    eligible=[r for r in selection if r['eligible']]
    chosen=min(eligible or selection,key=lambda r:r['score'])['id']
    dump(e/'SELECTION.json',{'candidates':selection,'chosen_for_C_D_diagnostic':chosen,'outcome':'GEOMETRIC_CANDIDATE' if eligible else 'NO_GEOMETRIC_WINNER',
                            'chosen_before_comparison':True,'comparison_consumed':False,'rule':manifest['selection']})
    # C/D are still delivered when selection fails; failure must not suppress the comparison.
    for group,tag,baseline_id in [('C','old','A'),('D','new','B')]:
        records[group]=[]
        for session in session_catalog:
            sid=session['session_id']; state=CausalSelection(cfg);prev=None
            for fi in session['available_frames']:
                base=read(out/baseline_id/sid/f'{fi:04d}.json');t=base['device_time'];started=time.perf_counter()
                with np.load(common/sid/f'{fi:04d}.npz') as d:p=d['xyz'].copy();valid=d['valid'];nominal_domain=d['nominal_domain']
                with np.load(out/baseline_id/sid/f'{fi:04d}_members.npz') as d:fg=d['foreground'].copy();dist=d['background_distance'].copy();matched=d['background_match'].copy();ambiguous=d['pose_ambiguous'].copy()
                groups,graph=conditional_graph(p[fg],cfg,rules[chosen],dist[fg],models[tag].tau)
                ids,identity,posture,reset=state.update(t,groups,p,fg);sk=skeleton(p[ids],ids,cfg)
                metrics=node_metrics(sk,prev,identity,t,cfg);prev={'sk':sk,'t':t,'identity':identity}
                codes=np.zeros(len(p),dtype='u1');codes[valid]=1;codes[matched]=2;codes[fg]=3
                cluster_ids=np.full(len(p),-1,dtype='i4');allids=[]
                for ci,g in enumerate(groups):codes[fg[g]]=4;cluster_ids[fg[g]]=ci;allids.extend(fg[g].tolist())
                assert len(allids)==len(set(allids)) and not matched[allids].any() and not set(fg)&set(np.flatnonzero(matched));codes[ids]=5
                folder=out/group/sid;folder.mkdir(parents=True,exist_ok=True)
                np.savez_compressed(folder/f'{fi:04d}_members.npz',terminal_reason=codes,cluster_id=cluster_ids,foreground=fg,selected=ids,
                                    background_distance=dist,background_match=matched,pose_ambiguous=ambiguous,
                                    **{k:v for k,v in graph.items() if isinstance(v,np.ndarray)})
                body=[]
                if len(ids):
                    sample=ids[np.linspace(0,len(ids)-1,min(len(ids),cfg['display_sample_points']),dtype=int)]
                    body=[{'id':identity,'kind':'AUTOMATIC_CANDIDATE','points':p[sample].tolist(),'display_source_indices':sample.tolist(),
                           'source_indices':ids.tolist(),'point_count':len(ids),'bbox':{'min':p[ids].min(axis=0).tolist(),'max':p[ids].max(axis=0).tolist()},
                           'skeleton':sk,'semantic_identity':'UNKNOWN','model_status':'NOT_USED','independence':{'score_0_100':0,'separation_status':'UNKNOWN'},'pointnet_prob':0,'rf_xyz_prob':0}]
                cpu=(time.perf_counter()-started)*1000
                oldids=np.array(base['selection']['selected_source_indices'],int)
                base.update(variant=group,body_3d=body,roi_3d=body,full_3d=body,posture=posture,
                            selection={'selected_source_indices':ids.tolist(),'candidate_count':len(groups),'uses_future_action_points':False},
                            graph={k:v for k,v in graph.items() if not isinstance(v,np.ndarray)},member_sha256=sha(folder/f'{fi:04d}_members.npz'),
                            delta={'added_count':len(np.setdiff1d(ids,oldids)),'removed_count':len(np.setdiff1d(oldids,ids))})
                base['semantic'].update(prediction_unknown_fraction=1. if len(ids) else None,prediction_outside_U=int((~nominal_domain[ids]).sum()))
                dump(folder/f'{fi:04d}.json',base)
                records[group].append({'sid':sid,'fi':fi,'device_time':t,'selected_count':len(ids),'fg_count':len(fg),'cpu_ms':cpu,'vibration':base['vibration']['status'],
                    'identity':identity,'state':posture['state'],'distance_m':float(np.linalg.norm(np.median(p[ids],axis=0))) if len(ids) else None,
                    'height_p90_m':float(np.quantile(p[ids,2],.9)) if len(ids) else None,'reset':reset,**metrics})
            print('COMPARE',group,sid,'complete',flush=True)
    dump(e/'ALL_STATS.json',records)
    summary={g:{'actions':aggregate([r for r in rs if not r['sid'].startswith('cap_20261014')]),
                'new_empty_holdout':aggregate([r for r in rs if r['sid'].startswith('cap_20261014')]),
                'by_session':{sid:aggregate([r for r in rs if r['sid']==sid]) for sid in manifest['source_sha256']},
                'by_posture':{s:aggregate([r for r in rs if r['state']==s]) for s in sorted(set(r['state'] for r in rs))},
                'by_distance':{name:aggregate([r for r in rs if r['distance_m'] is not None and lo<=r['distance_m']<hi]) for name,lo,hi in [('0_2m',0,2),('2_4m',2,4),('4plus',4,float('inf'))]}}
             for g,rs in records.items()}
    dump(e/'COMPARE_SUMMARY.json',{'groups':summary,'selection':read(e/'SELECTION.json'),'comparison_consumed':True,
         'semantic':'BLOCKED_NO_INDEPENDENT_GT','old32':'CACHED_XYZ_REGRESSION_ONLY_NOT_RERUN_HERE','production_P':'NOT_RUN_FROZEN_HORIZONTAL_GRID_NO_PRODUCTION_CLAIM',
         'performance_note':'PC wall-clock including archive writes; shared preprocessing reported separately. Not board FPS.', 'command':sys.argv,'stage_status':'COMPARISONS_COMPLETED'})
    print('ALL COMPARISONS COMPLETE',flush=True)


if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['preflight','run']);parser.add_argument('--evidence',type=Path,required=True)
    args=parser.parse_args();globals()[args.phase](args.evidence.resolve())

"""Source-preserving upstream retention research. Existing algorithms remain frozen.

Records are identified by source row, never XYZ. No label import in inference.
The reference and transforms are numerical offline assumptions, not physical GT.
"""
import argparse
from collections import deque
from pathlib import Path
import time

import numpy as np
from scipy.spatial import cKDTree

from actions import HERE, ROOT, OUT, load, read, dump, sha, choose, Posture, describe_object
from core import cluster, roi_mask, skeleton
from research_actions import frame_points, masks, display
from experiment_actions import supported_regions

E = ROOT/'docs/human_fall/evidence/2026-10-14_hf_mainline_points_r1'
RESULT = HERE/'action_research_retention'
CODE = {'NONFINITE': 1, 'ZERO': 2, 'RANGE': 3, 'HEIGHT_LOW': 4, 'HEIGHT_HIGH': 5,
        'BACKGROUND_MATCH': 6, 'VOXEL_NOISE_MIN_CLUSTER': 7,
        'CANDIDATE_QUALIFICATION': 8, 'UNSELECTED_CLUSTER': 9, 'TARGET': 10}


def context():
    cat = read(OUT/'catalog.json'); cfg = read(OUT/'RUN_MANIFEST.json')['config']
    prior = Path(cfg['background_experiment'])
    for b in read(E/'DEPENDENCY_BINDINGS.json'):
        assert sha(Path(b['path'])) == b['expected'], 'Cross-repo binding drift'
    assert sha(prior/'background.npz') == cat['background']['background_file_sha256']
    old = read(OUT/'RUN_MANIFEST.json')
    for name, h in old['code_sha256'].items(): assert sha(HERE/name) == h, name
    return cat, cfg, prior, cKDTree(np.load(prior/'background.npz')['xyz']), cat['background']['tolerance_m']


def excluded():
    h = read(ROOT/'docs/human_fall/evidence/2026-10-14_hf_mainline_points_plan_r1/CONTEXT_HOLDOUT_V2.json')
    return {r['sid']: set(r['excluded_diagnosis_context_frames']) for r in h['cases']}


def ledger(q, p, tree, tau, cfg, groups, fg, ids, previous_center=None):
    n = len(q); finite = np.isfinite(q).all(axis=1); zero = finite & ~np.any(q != 0, axis=1)
    radius = np.linalg.norm(q, axis=1)
    rg = (radius <= cfg['range_min_m']) | (radius >= cfg['range_max_m'])
    low = p[:, 2] < cfg['z_min_m']; high = p[:, 2] > cfg['z_max_m']
    valid, domain, dist, actual_fg = masks(q, p, tree, tau, cfg)
    assert np.array_equal(fg, actual_fg)
    # Background evidence outside actual height domain is explicitly COUNTERFACTUAL.
    cf = np.full(n, np.inf); nearest = np.full(n, -1, dtype='i4')
    finite_p = finite & np.isfinite(p).all(axis=1)
    cf[finite_p], nearest[finite_p] = tree.query(p[finite_p])
    flags = np.zeros(n, dtype='u2')
    for bit, pred in enumerate([~finite, zero, rg, low, high, cf <= tau]): flags |= pred.astype('u2') << bit
    stage = np.zeros(n, dtype='u1'); reached = np.zeros(n, dtype='u2')
    for code, pred in [(1, ~finite), (2, zero), (3, rg), (4, low), (5, high), (6, dist <= tau)]:
        active = stage == 0; reached[active] |= np.uint16(1 << (code-1)); stage[active & pred] = code
    labels = np.full(n, -1, dtype='i4'); stage[fg] = 7;qualification=np.zeros(n,dtype='u1')
    for gi, g in enumerate(groups):
        ix = fg[g]; labels[ix] = gi
        eligible = choose([g], p, fg, cfg, previous_center, None) is not None
        pts=p[ix];span=np.quantile(pts,.98,axis=0)-np.quantile(pts,.02,axis=0)
        reasons=[len(ix)<cfg['person_min_points'],float(roi_mask(pts,cfg['roi_xy']).mean())<cfg['person_min_roi_fraction'],
                 max(span)>cfg['person_max_span_m'],np.quantile(pts[:,2],.9)<cfg['person_min_p90_m'],
                 previous_center is not None and np.linalg.norm(np.median(pts,axis=0)[:2]-previous_center)>cfg['association_gate_m']]
        qualification[ix]=sum((1<<bit) for bit,pred in enumerate(reasons) if pred)
        stage[ix] = 9 if eligible else 8
    stage[ids] = 10
    assert np.all(stage > 0) and np.count_nonzero(stage) == n
    return dict(first_terminal_reason=stage, overlapping_predicates=flags, reached_stage_bits=reached,
                cluster_id=labels,candidate_qualification_bits=qualification, actual_background_distance_m=dist.astype('f4'),
                counterfactual_background_distance_m=cf.astype('f4'), reference_nearest_index=nearest,
                foreground=fg.astype('u4'), baseline_target=ids.astype('u4'))


def reference_support(cat, prior, tree):
    """Independent FIT frame coverage at the frozen tau, never action/HOLDOUT evidence."""
    m, raw, hashes = load(cat['background']['session'])
    assert hashes == next(r['source_sha256'] for r in cat['sessions'] if r['session_id'] == cat['background']['session'])
    bg = read(prior/'background.json'); cover = np.zeros(tree.n, dtype='u1'); cal = []
    for fi in bg['fit']:
        q, p = frame_points(raw, m['frames'][fi], None)
        finite = np.isfinite(q).all(axis=1) & np.any(q != 0, axis=1)
        # Reference occupancy is evidence at frozen centroids, not a replacement map.
        d = cKDTree(p[finite]).query(tree.data)[0]; cover += (d <= bg['tolerance_m']).astype('u1')
    for fi in bg['calibration']:
        q, p = frame_points(raw, m['frames'][fi], None)
        finite = np.isfinite(q).all(axis=1) & np.any(q != 0, axis=1)
        cal.append(float(np.quantile(tree.query(p[finite])[0], .95)))
    np.savez_compressed(E/'REFERENCE_FIT_SUPPORT.npz', fit_frame_coverage=cover)
    dump(E/'REFERENCE_RISK_MANIFEST.json', {'background_sha': sha(prior/'background.npz'),
         'FIT': bg['fit'], 'CALIBRATION': bg['calibration'], 'HOLDOUT_NOT_READ': bg['holdout'],
         'cal_frame_p95_m': cal, 'coverage_quantiles': np.quantile(cover, [0,.1,.5,.9,1]).tolist(),
         'local_thickness_normal': 'MISSING_NOT_RECONSTRUCTED', 'identity': 'UNKNOWN',
         'meaning': 'FIT coverage of original centroids within frozen tau; risk proxy only; old xyz and tau untouched'})
    return cover


def prepare(baseline_id='baseline'):
    if not (E/'BASELINE_BEFORE.json').exists(): raise ValueError('Preservation baseline must finish first')
    target = RESULT/baseline_id; target.mkdir(parents=True, exist_ok=False)
    cat, cfg, prior, tree, tau = context(); blocked = excluded(); start = time.perf_counter()
    if (E/'REFERENCE_FIT_SUPPORT.npz').exists():
        assert read(E/'REFERENCE_RISK_MANIFEST.json')['background_sha']==sha(prior/'background.npz')
        coverage=np.load(E/'REFERENCE_FIT_SUPPORT.npz')['fit_frame_coverage']
    else:coverage = reference_support(cat, prior, tree)
    stats = []; cases = []; bindings = {}
    for rec in cat['sessions']:
        sid = rec['session_id']; meta, raw, hashes = load(sid); assert hashes == rec['source_sha256']; bindings[sid] = hashes
        reg = None if sid == cat['background']['session'] else read(prior/(sid+'_registration.json'))
        folder = target/sid; folder.mkdir(); last = None; seen = None; last_t = None
        for fi in rec['available_frames']:
            f = meta['frames'][fi]; base = read(OUT/sid/f'{fi:04d}.json'); q,p = frame_points(raw,f,reg)
            _, domain, dist, fg = masks(q,p,tree,tau,cfg); groups,_ = cluster(p[fg],cfg); t = base['t_sec']
            if last_t is not None and (t <= last_t or t-last_t > cfg['max_gap_s']): last = None; seen = None
            if seen is not None and t-seen > cfg['max_gap_s']: last = None
            previous_center=last
            win = choose(groups,p,fg,cfg,last,None); ids = fg[groups[win[1]]] if win else np.empty(0,dtype=int)
            oldids = np.array(base['selection']['selected_source_indices'],dtype=int)
            assert np.array_equal(ids,oldids), (sid,fi,'R1 member drift')
            with np.load(HERE/'action_research_r2'/sid/f'{fi:04d}_sources.npz') as old:
                assert np.array_equal(fg,old['foreground'])
                assert np.array_equal(np.flatnonzero(domain & (dist <= tau)),old['background_removed'])
            if win: last = win[2][:2]; seen = t
            last_t = t
            a = ledger(q,p,tree,tau,cfg,groups,fg,ids,previous_center)
            # Offset + arange are exact identities, including duplicate coordinates.
            np.savez_compressed(folder/f'{fi:04d}.npz', raw_xyz=q.astype('f4'), xyz=p,
                 local_index=np.arange(len(q),dtype='u4'), global_row=np.arange(len(q),dtype='u8')+f['offset_points'], **a)
            row = {'sid':sid,'fi':fi,'source_frame':f,'t_sec':t,'count':len(q),
                   'terminal_counts':{k:int(np.count_nonzero(a['first_terminal_reason']==v)) for k,v in CODE.items()},
                   'target':len(ids),'fg':len(fg),'baseline_set_equal':True}
            stats.append(row)
            # No new-candidate diagnosis from excluded context or empty HOLDOUT.
            if sid != cat['background']['session'] and fi not in blocked.get(sid,set()):
                if len(ids):
                    removed = np.flatnonzero(a['first_terminal_reason']==6)
                    d = cKDTree(p[ids]).query(p[removed])[0]
                    near = removed[(d <= .12) & roi_mask(p[removed],cfg['roi_xy'])]
                    cases.append({'sid':sid,'fi':fi,'near_removed':len(near),
                        'distance_q':np.quantile(d,[.1,.5,.9]).tolist() if len(d) else [],
                        'near_z_q':np.quantile(p[near,2],[.1,.5,.9]).tolist() if len(near) else [],
                        'fit_coverage_q':np.quantile(coverage[a['reference_nearest_index'][near]],[0,.5,1]).tolist() if len(near) else []})
        print('BASELINE',sid,len(rec['available_frames']),flush=True)
    assert len(stats)==1966
    dump(E/'SOURCE_BINDINGS.json',{'sources':bindings,'config':cfg,'code':{n:sha(HERE/n) for n in ['core.py','actions.py','research_actions.py','research_retention.py']},'coordinate_frame':'empty_nominal_pointset_frame','physical_qualification':'UNVERIFIED'})
    dump(E/'BASELINE_REPRODUCTION.json',{'frames':stats,'members_equal':True,'baseline_id':baseline_id,'elapsed_s':time.perf_counter()-start})
    dump(E/'DIAGNOSIS_TRAIN_ONLY.json',{'frames':cases,'excluded_context':{k:sorted(v) for k,v in blocked.items()},'empty_holdout_not_used_for_selection':True})
    dump(E/'LEDGER_CODEBOOK.json',{'schema':'hf-source-ledger/1','first_terminal_reason':CODE,
        'overlapping_bits':['NONFINITE','ZERO','RANGE','HEIGHT_LOW','HEIGHT_HIGH','COUNTERFACTUAL_BACKGROUND_MATCH'],
        'reached_stage_bits':'bits0..5 actual checks1..6; absent bit=NOT_REACHED',
        'candidate_qualification_bits':['PERSON_MIN_POINTS','ROI_FRACTION','MAX_SPAN','MIN_P90','ASSOCIATION_GATE'],
        'stages_not_applicable':['ISOLATED_CLEANUP (Python chain has none)'],
        'ROI':'ranking/qualification, not point clipping of baseline',
        'recovery':'separate recovery_state, does not rewrite original first_terminal_reason',
        'opaque_reference':'original points.bin global_row*28 +12..27 bytes; source SHA and frame stamp in SOURCE_BINDINGS/BASELINE_REPRODUCTION',
        'units':'XYZ/distance m; timestamp sec+nanosec; offset_bytes=global_row*28',
        'range':'Python strict 0.2<raw_radius<15; height inclusive [-.25,2.6]',
        'reference_support':'nearest frozen centroid index; FIT coverage in REFERENCE_FIT_SUPPORT.npz'})


class Past:
    def __init__(self,cfg): self.cfg=cfg; self.frames=deque(); self.t=None; self.identity=None
    def reset(self,t,identity):
        if identity is None or identity != self.identity or (self.t is not None and (t<=self.t or t-self.t>self.cfg['max_gap_s'])): self.frames.clear()
        self.t=t; self.identity=identity
        while self.frames and t-self.frames[0][0]>self.cfg['past_age_s']: self.frames.popleft()
    def support(self,p):
        if not self.frames:return np.zeros(len(p),bool)
        return np.any([cKDTree(q).query(p)[0]<=self.cfg['past_radius_m'] for _,_,q in self.frames],axis=0)
    def append(self,t,fi,p):
        # Only independently selected current baseline anchors refresh evidence.
        if not len(p): self.frames.clear(); return
        self.frames.append((t,fi,p.copy()))
        while len(self.frames)>self.cfg['past_frames']:self.frames.popleft()


def recover(p, anchor, bg, cfg, nearest, coverage, past, arm):
    if not len(anchor): return np.empty(0,dtype=int), np.empty(0,dtype=int), {}
    gap=cKDTree(p[anchor]).query(p[bg])[0]
    pool=bg[(gap<=cfg['attachment_m']) & roi_mask(p[bg],cfg['roi_xy'])]
    if not len(pool):return pool,pool,{}
    local=cKDTree(p[anchor]).query_ball_point(p[pool],cfg['attachment_m'],return_length=True)>=cfg['minimum_anchor_neighbors']
    risk=coverage[nearest[pool]]<=cfg['maximum_fit_coverage']
    temporal=past.support(p[pool])
    accept={'local':local,'reference':risk,'temporal':temporal,'combined':local & risk & temporal,
            'feedback':local & risk & temporal,'r3':local & risk & temporal}[arm]
    added=pool[accept]
    return pool,added,{'local':local,'reference':risk,'temporal':temporal,'accepted':accept,
                     'past_frames':[{'t_sec':t,'fi':fi,'age_s':past.t-t} for t,fi,_ in past.frames]}


def run(run_id, config):
    cfg2=read(Path(config)); cat,cfg,prior,tree,tau=context(); cfg2['max_gap_s']=cfg['max_gap_s'];cfg2['roi_xy']=cfg['roi_xy']
    root=RESULT/run_id; root.mkdir(exist_ok=False)
    dump(root/'FROZEN_CONFIG.json',cfg2)
    dump(root/'FROZEN_SOURCE.json',{'source_sha':sha(HERE/'research_retention.py'),'config_sha':sha(Path(config)),'source_bindings_sha':sha(E/'SOURCE_BINDINGS.json'),'holdout_sha':sha(ROOT/'docs/human_fall/evidence/2026-10-14_hf_mainline_points_plan_r1/CONTEXT_HOLDOUT_V2.json'),'frozen_before_first_candidate_result':True})
    coverage=np.load(E/'REFERENCE_FIT_SUPPORT.npz')['fit_frame_coverage']; stats=[]; start=time.perf_counter()
    variants=cfg2['variants']; hold=read(ROOT/'docs/human_fall/evidence/2026-10-14_hf_mainline_points_plan_r1/CONTEXT_HOLDOUT_V2.json')
    holdset={(r['sid'],f) for r in hold['cases'] for f in r['frames']}
    for rec in cat['sessions']:
        sid=rec['session_id']; meta,raw,hashes=load(sid); assert hashes==rec['source_sha256']
        past={v:Past(cfg2) for v in variants}; post={v:Posture(cfg) for v in variants};post_identity={v:None for v in variants}
        feedback_center=None; seen=None; last_t=None; generation=0; previous={}
        for v in variants:(root/v/sid).mkdir(parents=True)
        for fi in rec['available_frames']:
            base=read(OUT/sid/f'{fi:04d}.json'); t=base['t_sec']; f=meta['frames'][fi]
            baseline_id=read(E/'BASELINE_REPRODUCTION.json')['baseline_id']
            with np.load(RESULT/baseline_id/sid/f'{fi:04d}.npz') as data:a={k:data[k] for k in data.files}
            p=a['xyz']; bg=np.flatnonzero(a['first_terminal_reason']==6); fg=a['foreground'].astype(int); baseids=a['baseline_target'].astype(int)
            if last_t is not None and (t<=last_t or t-last_t>cfg['max_gap_s']):feedback_center=None;seen=None
            if seen is not None and t-seen>cfg['max_gap_s']:feedback_center=None
            groups,_=cluster(p[fg],cfg)
            win=choose(groups,p,fg,cfg,feedback_center,None)
            feedids=fg[groups[win[1]]] if win else np.empty(0,dtype=int)
            if win:
                if feedback_center is None:generation+=1
                seen=t
            for v in variants:
                anchor=feedids if v=='feedback' else baseids
                identity=('RET-'+str(generation)) if v=='feedback' and len(anchor) else (base['body_3d'][0]['id'] if len(anchor) else None)
                hist=past[v];hist.reset(t,identity)
                pool,added,ev=recover(p,anchor,bg,cfg2,a['reference_nearest_index'],coverage,hist,v)
                downstream=anchor
                if v=='r3':
                    oldr3=read(HERE/'action_research_r3/r3_signed'/sid/f'{fi:04d}.json')
                    downstream=np.array(oldr3['body_3d'][0]['source_indices'],dtype=int) if oldr3['body_3d'] else anchor
                members=np.union1d(downstream,added).astype(int)
                assert set(added).issubset(bg) and np.all(roi_mask(p[added],cfg['roi_xy']))
                assert len(members)==len(np.unique(members))
                # Recovery stages are disjoint and refer exclusively to current records.
                state=np.zeros(len(p),dtype='u1');state[pool]=1;state[added]=2
                np.savez_compressed(root/v/sid/f'{fi:04d}_members.npz',pool=pool.astype('u4'),added=added.astype('u4'),target=members.astype('u4'),recovery_state=state,
                     local_pass=ev.get('local',np.empty(0,bool)),reference_pass=ev.get('reference',np.empty(0,bool)),temporal_pass=ev.get('temporal',np.empty(0,bool)))
                body=[]
                if len(members):
                    body=[describe_object(p,members,a['actual_background_distance_m'],p[np.setdiff1d(fg,members)],tau,cfg,identity)]
                    body[0]['semantic_identity']='UNKNOWN';body[0]['skeleton']['direction']={'source':'CURRENT_GEOMETRY_ONLY'}
                    if v=='r3' and oldr3['body_3d'] and 'axis' in oldr3['body_3d'][0]['skeleton']:
                        frozen_sk=oldr3['body_3d'][0]['skeleton']
                        body[0]['skeleton']=supported_regions(p[members],members,np.array(frozen_sk['axis']),cfg)
                        body[0]['skeleton']['direction']={'source':'FROZEN_R3_DIRECTION_CURRENT_MEMBERS','frozen_direction':frozen_sk.get('direction')}
                        body[0]['skeleton']['orientation']=frozen_sk.get('orientation')
                    for node in body[0]['skeleton']['nodes'].values():
                        assert set(node['support_source_indices']).issubset(members)
                if identity is None or identity!=post_identity[v]:post[v]=Posture(cfg)
                post_identity[v]=identity
                posture=post[v].update(t,p[members] if len(members) else None)
                center=np.median(p[members],axis=0) if len(members) else None
                oldcenter=np.median(p[baseids],axis=0) if len(baseids) else None
                delta=float(np.linalg.norm(center-oldcenter)) if center is not None and oldcenter is not None else None
                axis=body[0]['skeleton'].get('axis') if body else None
                angle=None;flip=False;jump=0.
                if v in previous and body:
                    old=previous[v]
                    if old.get('axis') is not None and axis is not None:
                        dot=float(np.clip(np.dot(old['axis'],axis),-1,1));angle=float(np.degrees(np.arccos(abs(dot))));flip=dot<0
                    for name,n in body[0]['skeleton']['nodes'].items():
                        if n['valid'] and old['nodes'][name]['valid']:jump=max(jump,float(np.linalg.norm(np.subtract(n['xyz'],old['nodes'][name]['xyz']))))
                if body:previous[v]=body[0]['skeleton']
                else:previous.pop(v,None)
                s={'sid':sid,'fi':fi,'variant':v,'pool_count':len(pool),'added_count':len(added),'deleted_count':len(np.setdiff1d(baseids,members)),
                   'target_count':len(members),'baseline_count':len(baseids),'center_offset_m':delta,'axis_missing':bool(len(members) and axis is None),
                   'axis_angle_deg':angle,'axis_flip':bool(flip),'max_slot_jump_m':jump,'valid_nodes':sum(n['valid'] for n in body[0]['skeleton']['nodes'].values()) if body else 0,
                   'direction_source':body[0]['skeleton']['direction']['source'] if body else 'MISSING','event':posture['event'],'context_holdout':(sid,fi) in holdset,
                   'unknown_added':len(added),'furniture_denominator':None,'furniture_contamination':None,'complete_human_recall':None}
                stats.append(s)
                records=[{'source_index':int(i),'global_row':int(f['offset_points']+i),'raw_xyz':a['raw_xyz'][i].tolist(),'xyz':p[i].tolist(),
                          'reason':'CURRENT_BACKGROUND_POOL_'+v.upper(),'background_distance_m':float(a['actual_background_distance_m'][i]),
                          'fit_frame_coverage':int(coverage[a['reference_nearest_index'][i]]),'identity':'UNKNOWN','past':ev.get('past_frames',[])} for i in added]
                row={'variant':'ret_'+v,'session_id':sid,'frame_index':fi,'source_sha256':hashes,'source_frame':f,'t_sec':t,'body_3d':body,'posture':posture,'stats':s,
                     'added_members':records,'connection_evidence':[], 'candidate_pool_display':display(p,pool,2000),
                     'background_risk_display':display(p,added,2000),'retention_evidence':{'pool_count':len(pool),'accepted':len(added),'reference_risk':'FIT coverage; local normals MISSING; identity UNKNOWN', 'past':ev.get('past_frames',[])},
                     'ledger_file':f'{baseline_id}/{sid}/{fi:04d}.npz','identity':'UNKNOWN','run_id':run_id,'no_future_points':True}
                dump(root/v/sid/f'{fi:04d}.json',row)
                hist.append(t,fi,p[anchor])
                if v=='feedback':feedback_center=center[:2] if center is not None else None
            last_t=t
        print('CANDIDATE',run_id,sid,len(rec['available_frames']),flush=True)
    assert len(stats)==1966*len(variants)
    dump(root/'FRAME_METRICS.json',{'frames':stats,'elapsed_s':time.perf_counter()-start,'validation_status':cfg2['validation_status']})
    dump(root/'SUMMARY.json',{v:{'frames':len([r for r in stats if r['variant']==v]),'added':sum(r['added_count'] for r in stats if r['variant']==v),
        'max_center_offset_m':max((r['center_offset_m'] or 0 for r in stats if r['variant']==v),default=0),
        'new_missing':sum(r['baseline_count']>0 and not r['target_count'] for r in stats if r['variant']==v),
        'empty_targets':sum(r['target_count']>0 for r in stats if r['variant']==v and r['sid']==cat['background']['session']),
        'axis_missing':sum(r['axis_missing'] for r in stats if r['variant']==v),
        'axis_flips':sum(r['axis_flip'] for r in stats if r['variant']==v),
        'max_slot_jump_m':max(r['max_slot_jump_m'] for r in stats if r['variant']==v)} for v in variants})


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('phase',choices=['prepare','run']);ap.add_argument('--run-id');ap.add_argument('--config');ap.add_argument('--baseline-id',default='baseline');args=ap.parse_args()
    if args.phase=='prepare':prepare(args.baseline_id)
    else:run(args.run_id,args.config)

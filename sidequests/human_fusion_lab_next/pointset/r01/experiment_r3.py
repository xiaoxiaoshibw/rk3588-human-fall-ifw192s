"""R3 current-source graph recovery, causal evidence and independent feedback replay."""
import copy
from collections import deque
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from actions import OUT, HERE, read, dump, load, sha, choose, Posture, describe_object
from core import cluster, roi_mask, skeleton, voxelize
from experiment_actions import recover, AxisHistory, supported_regions
from research_actions import RESULT as R2, frame_points, masks, display
from research_r3 import E, RESULT, shape

def graph_groups(p, ids, cfg):
    if not len(ids): return []
    pairs = cKDTree(p[ids]).query_pairs(cfg['graph_radius_m'], output_type='ndarray')
    graph = coo_matrix((np.ones(len(pairs)),(pairs[:,0],pairs[:,1])),shape=(len(ids),len(ids)))
    _, labels = connected_components(graph, directed=False)
    return [ids[labels==k] for k in np.unique(labels)]

class Past:
    def __init__(self,cfg): self.cfg=cfg; self.frames=deque(); self.last=None; self.identity=None
    def reset(self,t,identity):
        if self.last is not None and (t<=self.last or t-self.last>self.cfg['max_gap_s'] or identity!=self.identity): self.frames.clear()
        self.last=t; self.identity=identity
        while self.frames and (t-self.frames[0]['t_sec']>self.cfg['past_age_s'] or len(self.frames)>self.cfg['past_frames']): self.frames.popleft()
    def append(self,t,fi,identity,p,ids,fg):
        if not len(ids): self.frames.clear(); return
        self.frames.append({'fi':fi,'t_sec':t,'target_id':identity,'target':p[ids].copy(),'unselected':p[np.setdiff1d(fg,ids)].copy()})
        while len(self.frames)>self.cfg['past_frames']: self.frames.popleft()
    def evidence(self,q):
        rows=[]
        for f in self.frames:
            target=cKDTree(f['target']).query(q)[0]<=self.cfg['past_target_radius_m']
            u=f['unselected']; stable=cKDTree(u).query(q)[0]<=self.cfg['past_unselected_radius_m'] if len(u) else np.zeros(len(q),bool)
            rows.append({'fi':f['fi'],'t_sec':f['t_sec'],'target_id':f['target_id'],
                         'target_fraction':float(target.mean()),'unselected_fraction':float(stable.mean())})
        return rows

def recover_r3(p, ids, fg, fragments, dist, tau, cfg, switches, past):
    A,B,C,_=switches
    if not len(ids): return ids.copy(),[],[]
    others=np.setdiff1d(fg,ids); target=cKDTree(p[ids]); diagnostic=[]; accepted={}
    if A:
        groups=graph_groups(p,others,cfg)
        groups=[g for g in groups if len(g)>=cfg['minimum_graph_points'] and target.query(p[g])[0].min()<=cfg['attachment_gap_m']]
    else:
        _, old=recover(p,ids,fg,fragments,dist,tau,cfg,{'z_min_m':.04,'gap_m':.20,'whole_component':True})
        candidate=np.array([r['source_index'] for r in old],dtype=int)
        groups=graph_groups(p,candidate,cfg)
    for gi,g in enumerate(groups):
        q=p[g]; d,nearest=target.query(q); inside=roi_mask(q,cfg['roi_xy']); density=cKDTree(q).query_ball_point(q,.1,return_length=True)
        geom=shape(q) if len(q)>2 else {'linearity':0.,'normal_z':0.}
        bridge=d<=cfg['attachment_gap_m']; bridge_vox=len(np.unique(np.floor(q[bridge]/.05),axis=0))
        history=past.evidence(q); support=max((r['target_fraction'] for r in history),default=0.)
        persistent=min((r['unselected_fraction'] for r in history),default=0.)
        risk=dist[g]<cfg['background_risk_factor']*tau
        floor=(q[:,2]<cfg['floor_contact_z_m'])
        safe=inside&(q[:,2]>=cfg['z_min_added_m']); reasons=[]
        if A:
            if len(g)>cfg['maximum_fragment_points']: reasons.append('OVERSIZED_GRAPH_BLOCK')
            if inside.mean()<cfg['minimum_roi_fraction']: reasons.append('OUTSIDE_ORIGINAL_ROI')
            if np.quantile(d,.9)>cfg['maximum_p90_gap_m']: reasons.append('DISTANT_GRAPH_TAIL')
            if bridge_vox<cfg['minimum_bridge_voxels']: reasons.append('WEAK_BRIDGE_SUPPORT')
            if np.median(density)<cfg['minimum_neighbors'] or geom['linearity']<cfg['minimum_linearity']: reasons.append('WEAK_DENSITY_OR_SHAPE')
        if B:
            safe &= ~risk & ~floor
            if persistent>=cfg['persistent_unselected_fraction'] and support<cfg['past_target_fraction_min']: reasons.append('PERSISTENT_UNSELECTED_WITHOUT_TARGET_SUPPORT')
        if C and support<cfg['past_target_fraction_min']: reasons.append('NO_BOUNDED_PAST_TARGET_SUPPORT')
        if reasons: safe[:]=False
        if A and B and safe.any():
            # Risk removal must not leave an orphan tail behind a rejected bridge.
            connected=np.zeros(len(g),bool)
            for block in graph_groups(p,g[safe],cfg):
                gap=target.query(p[block])[0]
                bv=len(np.unique(np.floor(p[block][gap<=cfg['attachment_gap_m']]/.05),axis=0))
                if len(block)>=cfg['minimum_graph_points'] and bv>=cfg['minimum_bridge_voxels']:
                    connected |= np.isin(g,block)
            safe &= connected
        kept=g[safe]; rejected=g[~safe]
        evidence={'group':gi,'source_indices':g.tolist(),'accepted_source_indices':kept.tolist(),'rejected_source_indices':rejected.tolist(),
            'count':len(g),'linearity':geom['linearity'],'normal_z':geom['normal_z'],'median_neighbors_10cm':float(np.median(density)),
            'bridge_voxels':bridge_vox,'min_target_distance_m':float(d.min()),'p90_target_distance_m':float(np.quantile(d,.9)),
            'near_background_count':int(risk.sum()),'floor_contact_count':int(floor.sum()),'past':history,'reasons':reasons,
            'identity':'UNKNOWN','provenance':'AI_INFERRED','display':display(p,g,500),
            'bridge_edges':[{'source_index':int(i),'anchor_source_index':int(ids[a]),'distance_m':float(gap)} for i,a,gap in zip(g[bridge],nearest[bridge],d[bridge])][:100]}
        diagnostic.append(evidence)
        for i,a,gap in zip(g[safe],nearest[safe],d[safe]):
            accepted[int(i)]={'source_index':int(i),'anchor_source_index':int(ids[a]),'xyz':p[i].tolist(),
                'target_distance_m':float(gap),'background_distance_m':float(dist[i]),'z_m':float(p[i,2]),
                'within_original_roi':True,'reason':'DENSE_GRAPH_SHAPE' if A else 'COMPONENT20_WITH_FILTER',
                'group':gi,'past':history,'identity':'UNKNOWN','provenance':'AI_INFERRED'}
    added=np.array(sorted(accepted),dtype=int)
    return np.union1d(ids,added),list(accepted.values()),diagnostic

def axis_r3(p, base, members, cfg, history,t,fi,identity):
    # Only original current target can refresh the reliable direction reference.
    old=history.update(t,fi,identity,p[base],base)
    q=p[members]; result=skeleton(q,members,cfg)
    if 'axis' in result: source='CURRENT_RECOVERED_RELIABLE_AXIS'
    elif old and 'axis' in old:
        axis=np.array(old['axis']); cov=np.cov(q.T); vals=np.linalg.eigvalsh(cov)
        fraction=float(axis@cov@axis/max(vals[-1],1e-9))
        current_anchor='axis' in skeleton(p[base],base,cfg) and len(base)/len(members)>=cfg['current_anchor_local_axis_min_fraction']
        if current_anchor or fraction>=cfg['local_axis_variance_fraction_min']:
            result=supported_regions(q,members,axis,cfg); source='CURRENT_BASE_OR_BOUNDED_PAST_DIRECTION'
            if current_anchor: source='CURRENT_ANCHOR_LOCAL_AXIS'
        else: source='MISSING'
    else: source='MISSING'
    probes=[]
    if 'axis' not in result:
        cov=np.cov(q.T); vals,vecs=np.linalg.eigh(cov); radius=np.linalg.norm(q-np.median(q,axis=0),axis=1)
        _,centers,_,_=voxelize(q,cfg['voxel_m'])
        for name,local,support in [('CENTRAL_CURRENT_SUBSPACE',q[radius<=np.quantile(radius,.8)],members[radius<=np.quantile(radius,.8)]),
                                    ('UPPER_CURRENT_SUBSPACE',q[q[:,2]>np.median(q[:,2])],members[q[:,2]>np.median(q[:,2])]),
                                    ('UNIFORM_CURRENT_VOXEL_SUBSPACE',centers,members)]:
            if len(local)<cfg['cluster_min_points']: continue
            lv,lvec=np.linalg.eigh(np.cov(local.T)); axis=lvec[:,-1]; ratio=float(lv[-1]/max(lv[-2],1e-9))
            fraction=float(axis@cov@axis/max(vals[-1],1e-9)); angle=float(np.degrees(np.arccos(np.clip(abs(axis@vecs[:,-1]),0,1))))
            probes.append({'method':name,'eigen_ratio':ratio,'global_variance_fraction':fraction,'angle_degrees':angle,'support_source_indices':support.tolist()})
            if ratio>=cfg['local_axis_eigen_ratio_min'] and fraction>=cfg['local_axis_variance_fraction_min'] and angle<=cfg['local_axis_max_angle_degrees']:
                if axis[2]<0:axis=-axis
                result=supported_regions(q,members,axis,cfg); source=name; break
    result['direction']={'source':source,'reference':old.get('direction',{}).get('reference') if old else None,'local_probes':probes,
        'current_anchor_support_source_indices':base.tolist() if source=='CURRENT_ANCHOR_LOCAL_AXIS' else []}
    result['predicted_nodes']=[];result['anatomical_accuracy']='UNKNOWN'
    return result

def run():
    if RESULT.exists(): raise ValueError('Exclusive new output required; preserve failed runs')
    if not (E/'BASELINE_BEFORE.json').exists(): raise ValueError('Baseline required before experiment')
    RESULT.mkdir(); exp=read(HERE/'config_research_r3.json'); cfg=read(OUT/'RUN_MANIFEST.json')['config']; cfg.update(read(HERE/'config_research_r2.json'));cfg.update(exp)
    cat=read(OUT/'catalog.json');prior=Path(cfg['background_experiment']); bg=prior/'background.npz'; assert sha(bg)==cat['background']['background_file_sha256']
    tree=cKDTree(np.load(bg)['xyz']);tau=cat['background']['tolerance_m']; variants=exp['variants']; allstats={k:[] for k in variants};sources={}
    for rec in cat['sessions']:
        sid=rec['session_id'];meta,raw,hashes=load(sid);assert hashes==rec['source_sha256'];sources[sid]=hashes
        reg=None if sid==cat['background']['session'] else read(prior/(sid+'_registration.json'))
        past={k:Past(cfg) for k in variants}; axes={k:AxisHistory(cfg) for k in variants};postures={k:Posture(cfg) for k in variants}
        feedback_center=None;last_t=None;last_seen=None;generation=0; previous={}
        for fi in rec['available_frames']:
            base=read(OUT/sid/f'{fi:04d}.json');diag=read(R2/sid/f'{fi:04d}.json');q,p=frame_points(raw,meta['frames'][fi],reg)
            _,_,dist,fg=masks(q,p,tree,tau,cfg)
            with np.load(R2/sid/f'{fi:04d}_sources.npz') as sets: assert np.array_equal(fg,sets['foreground']);ids=sets['target']
            t=base['t_sec'];identity=base['body_3d'][0]['id'] if len(ids) else None
            if last_t is not None and (t<=last_t or t-last_t>cfg['max_gap_s']):feedback_center=None;last_seen=None
            if last_seen is not None and t-last_seen>cfg['max_gap_s']:feedback_center=None
            groups,_=cluster(p[fg],cfg); winner=choose(groups,p,fg,cfg,feedback_center,None)
            feed_ids=fg[groups[winner[1]]] if winner else np.array([],dtype=int)
            if winner:
                if feedback_center is None: generation+=1
                last_seen=t
            feed_identity='R3-BODY-'+str(generation) if winner else None
            for variant,switches in variants.items():
                anchor=feed_ids if variant=='r3_feedback' else ids; ident=feed_identity if variant=='r3_feedback' else identity
                if variant=='r3_feedback':
                    fr=[]
                    if len(anchor):
                        tr=cKDTree(p[anchor])
                        for g in groups:
                            ix=fg[g]
                            if np.array_equal(ix,anchor):continue
                            d=tr.query(p[ix])[0]
                            fr.append({'source_indices':ix.tolist(),'count':len(ix),'roi_fraction':float(roi_mask(p[ix],cfg['roi_xy']).mean()),'min_target_distance_m':float(d.min()),'p90_target_distance_m':float(np.quantile(d,.9))})
                else:fr=diag['fragments']
                past[variant].reset(t,ident)
                members,records,evidence=recover_r3(p,anchor,fg,fr,dist,tau,cfg,switches,past[variant])
                considered=set(i for e in evidence for i in e['source_indices'])
                for f in fr:
                    rest=np.array([i for i in f['source_indices'] if i not in considered],dtype=int)
                    if not len(rest):continue
                    evidence.append({'group':len(evidence),'source_indices':rest.tolist(),'accepted_source_indices':[],
                        'rejected_source_indices':rest.tolist(),'count':len(rest),'display':display(p,rest,500),
                        'reasons':['OUTSIDE_OR_WEAK_CURRENT_GRAPH_ATTACHMENT'],'near_background_count':int(np.sum(dist[rest]<2*tau)),
                        'floor_contact_count':int(np.sum(p[rest,2]<.08)),'past':past[variant].evidence(p[rest]),
                        'identity':'UNKNOWN','provenance':'AI_INFERRED','bridge_edges':[]})
                for r in records:r['raw_xyz']=q[r['source_index']].tolist()
                body=[]
                if len(members):
                    obj=describe_object(p,members,dist,p[np.setdiff1d(fg,members)],tau,cfg,ident)
                    if switches[3]:obj['skeleton']=axis_r3(p,anchor,members,cfg,axes[variant],t,fi,ident)
                    obj['skeleton']['predicted_nodes']=[];body=[obj]
                else:axes[variant].update(t,fi,ident,p[anchor],anchor)
                # Fixed experiments use past R1 anchors; feedback consumes its own recovered center/member evidence.
                past[variant].append(t,fi,ident,p,members if variant=='r3_feedback' else ids,fg)
                if variant=='r3_feedback':feedback_center=np.median(p[members],axis=0)[:2] if len(members) else feedback_center
                posture=postures[variant].update(t,p[members] if len(members) else None)
                sk=body[0]['skeleton'] if body else {'nodes':{}}; axis=sk.get('axis');prev=previous.get(variant)
                dot=float(np.dot(axis,prev['axis'])) if prev and fi==prev['fi']+1 and axis is not None and prev['axis'] is not None else None
                old_axis=base['body_3d'][0]['skeleton'].get('axis') if len(ids) else None
                stats={'sid':sid,'fi':fi,'target_count':len(members),'added_count':len(set(members)-set(ids)),
                    'deleted_count':len(set(ids)-set(members)),'anchor_difference_count':len(set(anchor)^set(ids)),
                    'recovered_from_anchor':len(records),'near_background_added_count':sum(r['background_distance_m']<2*tau for r in records),
                    'low_added_count':sum(r['z_m']<.08 for r in records),'valid_nodes':sum(n['valid'] for n in sk['nodes'].values()),
                    'axis_missing':bool(len(members) and axis is None),'new_axis_missing':bool(old_axis is not None and axis is None),
                    'direction_source':sk.get('direction',{}).get('source','CURRENT_AXIS' if axis else 'MISSING'),
                    'axis_large_turn':bool(dot is not None and abs(dot)<np.cos(np.pi/4)),
                    'center_shift_from_r1_m':float(np.linalg.norm(np.median(p[members],axis=0)-np.median(p[ids],axis=0))) if len(ids) and len(members) else None,
                    'posture_event':posture['event'],'target_id':ident,
                    'association_interruption':bool(prev and prev['identity'] is not None and ident!=prev['identity']),
                    'rejected_candidate_count':sum(len(e['rejected_source_indices']) for e in evidence)}
                allstats[variant].append(stats);previous[variant]={'axis':axis,'fi':fi,'identity':ident}
                folder=RESULT/variant/sid;folder.mkdir(parents=True,exist_ok=True)
                dump(folder/f'{fi:04d}.json',{'variant':variant,'session_id':sid,'frame_index':fi,'t_sec':t,'source_frame':meta['frames'][fi],
                    'source_sha256':hashes,'body_3d':body,'anchor_source_indices':anchor.tolist(),'added_members':records,
                    'background_risk_display':display(p,members[dist[members]<2*tau],1500),
                    'deleted_source_indices':sorted(set(ids)-set(members)),'connection_evidence':evidence,'posture':posture,'stats':stats,
                    'status':'EXPERIMENT_NOT_DEFAULT','identity':'UNKNOWN','identity_provenance':'AI_INFERRED',
                    'human_precision':None,'furniture_contamination_rate':None,'anatomical_accuracy':None})
            last_t=t
        print('R3',sid,len(rec['available_frames']),flush=True)
    summary={}
    for v,rows in allstats.items():
        action=[r for r in rows if r['sid']!=cat['background']['session']];empty=[r for r in rows if r['sid']==cat['background']['session']]
        summary[v]={k:sum(r[k] for r in action) for k in ['added_count','deleted_count','recovered_from_anchor','near_background_added_count','low_added_count','axis_missing','new_axis_missing','axis_large_turn','valid_nodes','association_interruption','anchor_difference_count','rejected_candidate_count']}
        shifts=[r['center_shift_from_r1_m'] for r in action if r['center_shift_from_r1_m'] is not None]
        summary[v].update(action_frames=len(action),empty_frames=len(empty),empty_targets=sum(r['target_count']>0 for r in empty),
            empty_added=sum(r['added_count'] for r in empty),center_shift_max_m=max(shifts,default=0),center_shift_p95_m=float(np.quantile(shifts,.95)),
            events=[{'sid':r['sid'],'fi':r['fi'],'event':r['posture_event']} for r in action if r['posture_event']],
            identity_accuracy='UNKNOWN',anatomical_accuracy='UNKNOWN',promotion='BLOCKED')
    dump(E/'EXPERIMENT_COMPARISON.json',{'summary':summary,'frames':allstats,'config_sha256':sha(HERE/'config_research_r3.json'),
        'code_sha256':sha(HERE/'experiment_r3.py'),'sources':sources,'background_sha256':sha(bg),'holdout_not_tuned':True,'default':'R1',
        'tracking_policy':{'fixed':'r3_graph/background/temporal/combined/r3 use R1 current anchors','feedback':'independent choose with previous recovered median XY'}})
    cases=read(E/'DIAGNOSTIC_STUDY.json')['rows']
    dump(RESULT/'experiments.json',{'summary':summary,'variants':list(variants),'default':'baseline','cases':[{'sid':r['sid'],'fi':r['fi'],'roles':['R3_HARD_OR_REMAINING_AXIS']} for r in cases]})
    print(summary,flush=True)

if __name__=='__main__':run()

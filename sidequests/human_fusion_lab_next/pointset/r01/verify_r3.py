"""Raw masks recomputed independently; all causal recoveries replayed and source means audited."""
from pathlib import Path
import time
import numpy as np
from scipy.spatial import cKDTree
from actions import load, read, dump, sha, HERE, OUT, R, T, choose
from core import roi_mask, cluster, SLOTS
from experiment_r3 import Past, recover_r3, AxisHistory, axis_r3
from research_r3 import E, RESULT
from research_actions import RESULT as R2

def run():
    cfg=read(OUT/'RUN_MANIFEST.json')['config'];cfg.update(read(HERE/'config_research_r2.json'));cfg.update(read(HERE/'config_research_r3.json'))
    frozen=read(E/'FROZEN_EXPERIMENT.json');assert frozen['config_research_r3.json']==sha(HERE/'config_research_r3.json')
    assert frozen['experiment_r3.py']==sha(HERE/'experiment_r3.py')
    cat=read(OUT/'catalog.json');prior=Path(cfg['background_experiment']);tree=cKDTree(np.load(prior/'background.npz')['xyz']);tau=cat['background']['tolerance_m']
    counts={v:{'frames':0,'nodes':0,'added_members':0,'causal_replays':0,'background_violations':0,'unbacked_nodes':0,'empty_targets':0} for v in cfg['variants']};sources={}
    for rec in cat['sessions']:
        final=rec['available_frames'][-1]
        while not all((RESULT/v/rec['session_id']/f'{final:04d}.json').exists() for v in counts):
            time.sleep(1)
        sid=rec['session_id'];meta,raw,hashes=load(sid);assert hashes==rec['source_sha256'];sources[sid]=hashes
        reg=None if sid==cat['background']['session'] else read(prior/(sid+'_registration.json'))
        past={v:Past(cfg) for v in counts};history={v:AxisHistory(cfg) for v in counts};feedback_center=None;last_t=None;last_seen=None
        for fi in rec['available_frames']:
            f=meta['frames'][fi]
            # Prefix view makes every row beyond the current source frame inaccessible here.
            prefix=raw[:f['offset_points']+f['count_points']]
            q=prefix[f['offset_points']:].astype('f8');p=q@R.T+T
            if reg:p=p@np.array(reg['R']).reshape(3,3).T+reg['t']
            valid=np.isfinite(q).all(axis=1)&np.any(q!=0,axis=1)&(np.linalg.norm(q,axis=1)>cfg['range_min_m'])&(np.linalg.norm(q,axis=1)<cfg['range_max_m'])
            domain=valid&(p[:,2]>=cfg['z_min_m'])&(p[:,2]<=cfg['z_max_m']);dist=np.full(len(p),np.inf);dist[domain]=tree.query(p[domain])[0]
            fg=np.flatnonzero(domain&(dist>tau));base=read(OUT/sid/f'{fi:04d}.json');old=set(base['selection']['selected_source_indices']);t=base['t_sec']
            assert len(fg)==base['fg_count'];diag=read(R2/sid/f'{fi:04d}.json')
            if last_t is not None and (t<=last_t or t-last_t>cfg['max_gap_s']):feedback_center=None;last_seen=None
            if last_seen is not None and t-last_seen>cfg['max_gap_s']:feedback_center=None
            groups,_=cluster(p[fg],cfg);winner=choose(groups,p,fg,cfg,feedback_center,None)
            feed=fg[groups[winner[1]]] if winner else np.array([],dtype=int)
            if winner:last_seen=t
            for v,switches in cfg['variants'].items():
                row=read(RESULT/v/sid/f'{fi:04d}.json');counts[v]['frames']+=1
                assert row['source_sha256']==hashes and row['source_frame']==f and row['session_id']==sid and row['frame_index']==fi
                assert row['identity']=='UNKNOWN' and not row['posture']['confirmed']
                anchor=np.array(row['anchor_source_indices'],dtype=int);aset=set(anchor.tolist())
                assert np.array_equal(anchor,feed) if v=='r3_feedback' else aset==old
                ident=row['body_3d'][0]['id'] if row['body_3d'] else None
                past[v].reset(t,ident)
                # Causal replay uses only prefix source view and previously verified members.
                recovered,records,_=recover_r3(p,anchor,fg,diag['fragments'],dist,tau,cfg,switches,past[v])
                members=np.array(row['body_3d'][0]['source_indices'],dtype=int) if row['body_3d'] else np.array([],dtype=int)
                assert np.array_equal(recovered,members);counts[v]['causal_replays']+=1
                membership=set(members.tolist());assert membership<=set(fg.tolist()) and aset<=membership
                assert len(members)==len(membership)
                added=membership-aset;assert {r['source_index'] for r in row['added_members']}==added
                counts[v]['added_members']+=len(added)
                assert row['deleted_source_indices']==sorted(old-membership)
                if sid==cat['background']['session']:counts[v]['empty_targets']+=bool(len(members))
                for r in row['added_members']:
                    i=r['source_index'];a=r['anchor_source_index']
                    assert i in added and a in aset and roi_mask(p[[i]],cfg['roi_xy'])[0] and dist[i]>tau and p[i,2]>=.04
                    assert np.allclose(r['raw_xyz'],q[i]) and np.allclose(r['xyz'],p[i]) and np.isclose(r['target_distance_m'],np.linalg.norm(p[i]-p[a]))
                    assert np.isclose(r['background_distance_m'],dist[i]) and r['identity']=='UNKNOWN'
                    if switches[1]:assert dist[i]>=2*tau and p[i,2]>=.08
                    for ref in r['past']:
                        assert ref['fi']<fi and 0<t-ref['t_sec']<=cfg['past_age_s'] and ref['target_id']==ident
                    if switches[2]:assert max(ref['target_fraction'] for ref in r['past'])>=cfg['past_target_fraction_min']
                for obj in row['body_3d']:
                    assert obj['point_count']==len(members) and set(obj['display_source_indices'])<=membership
                    assert np.allclose(obj['points'],p[obj['display_source_indices']],atol=.000051)
                    sk=obj['skeleton'];assert list(sk['nodes'])==SLOTS and sk['predicted_nodes']==[]
                    for n in sk['nodes'].values():
                        if n['valid']:
                            assert n['support_source_indices'] and set(n['support_source_indices'])<=membership
                            assert np.allclose(n['xyz'],p[n['support_source_indices']].mean(axis=0));counts[v]['nodes']+=1
                        else:assert n['xyz'] is None and not n['support_source_indices']
                    if switches[3]:
                        replay=axis_r3(p,anchor,members,cfg,history[v],t,fi,ident)
                        assert replay==sk
                        ref=sk['direction']['reference']
                        if ref:assert ref['fi']<fi and 0<t-ref['t_sec']<=cfg['axis_reference_max_age_s'] and ref['target_id']==ident
                    risk=row['background_risk_display'];assert set(risk['display_source_indices'])<=membership
                    assert np.allclose(np.array(risk['points']).reshape(-1,3),p[risk['display_source_indices']],atol=.000051)
                if not len(members):history[v].update(t,fi,ident,p[anchor],anchor)
                for e in row['connection_evidence']:
                    assert set(e['accepted_source_indices'])<=membership
                    assert not set(e['rejected_source_indices'])&added
                    d=e['display'];assert np.allclose(np.array(d['points']).reshape(-1,3),p[d['display_source_indices']],atol=.000051)
                    for edge in e['bridge_edges']:
                        assert edge['source_index'] in fg and edge['anchor_source_index'] in aset
                        assert np.isclose(edge['distance_m'],np.linalg.norm(p[edge['source_index']]-p[edge['anchor_source_index']]))
                past[v].append(t,fi,ident,p,members if v=='r3_feedback' else np.array(sorted(old)),fg)
                if v=='r3_feedback' and len(members):feedback_center=np.median(p[members],axis=0)[:2]
            last_t=t
        print('VERIFIED R3',sid,flush=True)
    assert all(c['frames']==1966 and c['empty_targets']==0 for c in counts.values())
    while not (E/'EXPERIMENT_COMPARISON.json').exists():time.sleep(1)
    comparison=read(E/'EXPERIMENT_COMPARISON.json');assert comparison['config_sha256']==sha(HERE/'config_research_r3.json')
    assert comparison['code_sha256']==sha(HERE/'experiment_r3.py')
    dump(E/'ALL_FRAME_VERIFICATION.json',{'status':'PASS','counts':counts,'sources':sources,
        'future_rows_inaccessible_during_replay':True,'causal_past_only_all_frames':True,'default':'R1',
        'identity_accuracy':'UNKNOWN','anatomical_accuracy':'UNKNOWN','code_sha256':sha(HERE/'verify_r3.py')})

if __name__=='__main__':run()

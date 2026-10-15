"""Independent current-source/prefix replay; all recorded members, not display samples."""
import argparse,sys,time
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2];PS=ROOT/'sidequests/human_fusion_lab_next/pointset/r01';sys.path.insert(0,str(PS))
from actions import read,dump,load,OUT,choose,sha,Posture
from core import cluster,roi_mask
from research_actions import frame_points,masks
from research_retention import E,RESULT,context,Past,recover,ledger
from experiment_r3 import recover_r3,Past as R3Past


def main(run_id):
    global recover
    root=RESULT/run_id;cfg2=read(root/'FROZEN_CONFIG.json');cat,cfg,prior,tree,tau=context();code=read(root/'FROZEN_SOURCE.json')
    assert sha(PS/'research_retention.py')==code['source_sha'],'frozen inference code changed'
    if cfg2.get('guard_source_sha'):
        import research_retention_guard as guard
        assert sha(PS/'research_retention_guard.py')==cfg2['guard_source_sha']
        recover=guard.guarded_recover
    coverage=np.load(E/'REFERENCE_FIT_SUPPORT.npz')['fit_frame_coverage'];baseline_id=read(E/'BASELINE_REPRODUCTION.json')['baseline_id']
    counts={v:{'frames':0,'source_records':0,'added':0,'prefix_member_equal':0,'nodes':0,'no_future':True} for v in cfg2['variants']};start=time.perf_counter();r3_verified=0
    r3cfg=dict(cfg);r3cfg.update(read(PS/'config_research_r2.json'));r3cfg.update(read(PS/'config_research_r3.json'))
    for rec in cat['sessions']:
        sid=rec['session_id'];meta,raw,hashes=load(sid);assert hashes==rec['source_sha256'];reg=None if sid==cat['background']['session'] else read(prior/(sid+'_registration.json'))
        past={v:Past(cfg2) for v in counts};post={v:Posture(cfg) for v in counts};post_id={v:None for v in counts};center=None;last_t=None;seen=None;generation=0;r1center=None;r1seen=None;r1t=None
        oldpast=R3Past(r3cfg)
        for fi in rec['available_frames']:
            f=meta['frames'][fi];prefix=raw[:f['offset_points']+f['count_points']];q,p=frame_points(prefix,f,reg)
            valid,domain,dist,fg=masks(q,p,tree,tau,cfg)
            with np.load(RESULT/baseline_id/sid/f'{fi:04d}.npz') as d:a={k:d[k] for k in d.files}
            assert np.array_equal(q.astype('f4'),a['raw_xyz'],equal_nan=True)
            assert np.array_equal(p,a['xyz'],equal_nan=True)
            assert np.array_equal(fg,a['foreground'])
            assert np.array_equal(np.flatnonzero(domain&(dist<=tau)),np.flatnonzero(a['first_terminal_reason']==6))
            assert np.all(a['global_row']==np.arange(len(q))+f['offset_points'])
            assert np.all(a['first_terminal_reason']>0) and len(a['first_terminal_reason'])==len(q)
            base=read(OUT/sid/f'{fi:04d}.json');baseids=np.array(base['selection']['selected_source_indices'],int);t=base['t_sec'];groups,_=cluster(p[fg],cfg)
            if r1t is not None and (t<=r1t or t-r1t>cfg['max_gap_s']):r1center=None;r1seen=None
            if r1seen is not None and t-r1seen>cfg['max_gap_s']:r1center=None
            baseline_winner=choose(groups,p,fg,cfg,r1center,None)
            assert np.array_equal(fg[groups[baseline_winner[1]]] if baseline_winner else np.empty(0,int),baseids)
            expected_ledger=ledger(q,p,tree,tau,cfg,groups,fg,baseids,r1center)
            with np.load(RESULT/baseline_id/sid/f'{fi:04d}_qualification.npz') as qualified:
                for k,val in expected_ledger.items():
                    actual=qualified[k] if k in qualified.files else a[k]
                    assert np.array_equal(val,actual,equal_nan=True),(sid,fi,'ledger recompute mismatch',k)
            if baseline_winner:r1center=baseline_winner[2][:2];r1seen=t
            r1t=t
            old_identity=base['body_3d'][0]['id'] if len(baseids) else None
            oldpast.reset(t,old_identity)
            diag=read(PS/'action_research_r2'/sid/f'{fi:04d}.json')
            oldmembers,_,_=recover_r3(p,baseids,fg,diag['fragments'],dist,tau,r3cfg,[True,True,True,False],oldpast)
            legacy=read(PS/'action_research_r3/r3_signed'/sid/f'{fi:04d}.json')
            legacyids=np.array(legacy['body_3d'][0]['source_indices'],int) if legacy['body_3d'] else np.empty(0,int)
            assert np.array_equal(oldmembers,legacyids),'R3 membership drift'
            oldpast.append(t,fi,old_identity,p,baseids,fg);r3_verified+=1
            if last_t is not None and (t<=last_t or t-last_t>cfg['max_gap_s']):center=None;seen=None
            if seen is not None and t-seen>cfg['max_gap_s']:center=None
            win=choose(groups,p,fg,cfg,center,None);feed=fg[groups[win[1]]] if win else np.empty(0,int)
            if win:
                if center is None:generation+=1
                seen=t
            bg=np.flatnonzero(domain&(dist<=tau));nearest=tree.query(p[bg])[1]
            allnearest=np.full(len(q),-1,dtype=int);allnearest[bg]=nearest
            for v in counts:
                anchor=feed if v=='feedback' else baseids;identity='RET-'+str(generation) if v=='feedback' and len(anchor) else (base['body_3d'][0]['id'] if len(anchor) else None)
                past[v].reset(t,identity);pool,added,evidence=recover(p,anchor,bg,cfg2,allnearest,coverage,past[v],v)
                downstream=anchor
                if v=='r3':
                    r3=read(PS/'action_research_r3/r3_signed'/sid/f'{fi:04d}.json');downstream=np.array(r3['body_3d'][0]['source_indices'],int) if r3['body_3d'] else anchor
                expected=np.union1d(downstream,added);row=read(root/v/sid/f'{fi:04d}.json')
                with np.load(root/v/sid/f'{fi:04d}_members.npz') as d:
                    assert np.array_equal(d['target'],expected) and np.array_equal(d['pool'],pool) and np.array_equal(d['added'],added)
                    assert np.array_equal(np.flatnonzero(d['recovery_state']==2),added)
                    assert np.array_equal(np.flatnonzero(d['recovery_state']>0),pool)
                ids=np.array(row['body_3d'][0]['source_indices'],int) if row['body_3d'] else np.empty(0,int)
                assert np.array_equal(ids,expected) and row['source_frame']==f and row['source_sha256']==hashes
                assert not row['posture']['confirmed']
                if identity is None or identity!=post_id[v]:post[v]=Posture(cfg)
                post_id[v]=identity
                assert row['posture']==post[v].update(t,p[ids] if len(ids) else None)
                for m in row['added_members']:
                    i=m['source_index'];assert np.array_equal(m['xyz'],p[i]) and np.array_equal(m['raw_xyz'],q[i]) and m['global_row']==f['offset_points']+i
                    assert i in bg and roi_mask(p[[i]],cfg['roi_xy'])[0]
                    assert all(x['fi']<fi and 0<x['age_s']<=cfg2['past_age_s'] for x in m['past'])
                for b in row['body_3d']:
                    for n in b['skeleton']['nodes'].values():
                        if n['valid']:
                            assert set(n['support_source_indices']).issubset(ids) and np.allclose(n['xyz'],p[n['support_source_indices']].mean(axis=0),atol=1e-12)
                            counts[v]['nodes']+=1
                c=counts[v];c['frames']+=1;c['source_records']+=len(q);c['added']+=len(added);c['prefix_member_equal']+=1
                past[v].append(t,fi,p[anchor])
                if v=='feedback':center=np.median(p[ids],axis=0)[:2] if len(ids) else None
            last_t=t
        print('VERIFIED',run_id,sid,flush=True)
    dump(root/'ALL_FRAME_VERIFICATION.json',{'variants':counts,'R3_exact_reproduced_frames':r3_verified,'elapsed_s':time.perf_counter()-start,'GT_entered_inference':False,
         'causal_prefix':'raw view truncated at current frame end, history rebuilt from session start','bounded_cache':'4 independent anchor frames; no refreshed inherited evidence',
         'verification_code_sha':sha(Path(__file__))})


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('run_id');a=p.parse_args();main(a.run_id)

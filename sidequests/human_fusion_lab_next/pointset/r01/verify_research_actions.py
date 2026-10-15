"""Independently bind R2 diagnostic/experiment members and means to current raw rows."""
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree
from actions import load, read, dump, sha, R, T
from core import roi_mask, skeleton
from research_actions import E, RESULT, HERE, OUT


def main():
    cat=read(OUT/'catalog.json');cfg=read(OUT/'RUN_MANIFEST.json')['config'];cfg.update(read(HERE/'config_research_r2.json'))
    prior=Path(cfg['background_experiment']);tree=cKDTree(np.load(prior/'background.npz')['xyz']);tau=cat['background']['tolerance_m']
    comparison=read(E/'EXPERIMENT_COMPARISON.json');variants=list(comparison['summary'])
    counts={v:{'frames':0,'target_frames':0,'supported_nodes':0,'added_members':0,'deleted_members':0,'history_frames':0} for v in variants}
    sources={};empty_targets={v:0 for v in variants}
    for rec in cat['sessions']:
        sid=rec['session_id'];meta,raw,hashes=load(sid);assert hashes==rec['source_sha256'];sources[sid]=hashes
        reg=None if sid==cat['background']['session'] else read(prior/(sid+'_registration.json'))
        for fi in rec['available_frames']:
            f=meta['frames'][fi];q=raw[f['offset_points']:f['offset_points']+f['count_points']].astype('f8');p=q@R.T+T
            if reg:p=p@np.array(reg['R']).reshape(3,3).T+reg['t']
            valid=np.isfinite(q).all(axis=1)&np.any(q!=0,axis=1)&(np.linalg.norm(q,axis=1)>cfg['range_min_m'])&(np.linalg.norm(q,axis=1)<cfg['range_max_m'])
            domain=valid&(p[:,2]>=cfg['z_min_m'])&(p[:,2]<=cfg['z_max_m']);distance=np.full(len(p),np.inf);distance[domain]=tree.query(p[domain])[0]
            fg=set(np.flatnonzero(domain&(distance>tau)).tolist())
            base=read(OUT/sid/f'{fi:04d}.json');old=set(base['selection']['selected_source_indices'])
            d=read(RESULT/sid/f'{fi:04d}.json');assert d['source_sha256']==hashes and d['source_frame']==f
            with np.load(RESULT/sid/f'{fi:04d}_sources.npz') as sets:
                assert set(sets['raw'].tolist())==set(np.flatnonzero(valid).tolist())
                assert set(sets['background_removed'].tolist())==set(np.flatnonzero(domain&(distance<=tau)).tolist())
                assert set(sets['foreground'].tolist())==fg and set(sets['target'].tolist())==old
                assert set(sets['unselected'].tolist())==fg-old
                assert set(sets['outside_domain'].tolist())==set(np.flatnonzero(valid&~domain).tolist())
                for key,layer in d['layers'].items():
                    assert layer['count']==len(sets[key]) and set(layer['display_source_indices'])<=set(sets[key])
                    assert np.allclose(np.array(layer['points']).reshape(-1,3),p[layer['display_source_indices']],atol=.000051)
            for v in variants:
                row=base if v=='baseline' else read(RESULT/v/sid/f'{fi:04d}.json')
                assert row['source_sha256']==hashes and row['frame_index']==fi and row['session_id']==sid
                counts[v]['frames']+=1;assert not row['posture']['confirmed']
                if sid==cat['background']['session']:empty_targets[v]+=len(row['body_3d'])
                for obj in row['body_3d']:
                    ids=obj['source_indices'];members=set(ids)
                    assert len(ids)==len(members)==obj['point_count'] and members<=fg and old<=members
                    assert all(type(i)is int and 0<=i<f['count_points'] for i in ids)
                    assert np.allclose(obj['points'],p[obj['display_source_indices']],atol=.000051)
                    assert np.allclose(obj['bbox']['min'],p[ids].min(axis=0)) and np.allclose(obj['bbox']['max'],p[ids].max(axis=0))
                    added=members-old;removed=old-members
                    counts[v]['target_frames']+=1;counts[v]['added_members']+=len(added);counts[v]['deleted_members']+=len(removed)
                    if v not in ['baseline','axis']:
                        records=row['added_members'];assert len(records)==len(added) and {r['source_index'] for r in records}==added
                        for r in records:
                            i=r['source_index'];a=r['anchor_source_index'];assert a in old and i not in old
                            assert roi_mask(p[[i]],cfg['roi_xy'])[0] and distance[i]>tau
                            assert np.isclose(r['background_distance_m'],distance[i]) and np.isclose(r['z_m'],p[i,2])
                            assert np.isclose(r['target_distance_m'],np.linalg.norm(p[i]-p[a]))
                            assert r['identity']=='UNKNOWN' and r['provenance']=='AI_INFERRED'
                            assert p[i,2]>=cfg['variants'][v]['z_min_m']
                            if r['reason']=='LOCAL_FOREGROUND_POINT':assert r['target_distance_m']<=cfg['variants'][v]['gap_m']+1e-12
                    if v=='axis':assert members==old
                    sk=obj['skeleton']
                    for n in sk['nodes'].values():
                        if n['valid']:
                            assert n['support_source_indices'] and set(n['support_source_indices'])<=members
                            assert np.allclose(n['xyz'],p[n['support_source_indices']].mean(axis=0));counts[v]['supported_nodes']+=1
                        else:assert n['xyz']is None and not n['support_source_indices']
                    for a,b in sk['edges']:assert sk['nodes'][a]['valid'] and sk['nodes'][b]['valid']
                    if v=='axis':
                        assert sk['predicted_nodes']==[]
                        ref=sk['direction']['reference']
                        if ref:
                            assert ref['fi']<fi
                            refrow=read(OUT/sid/f"{ref['fi']:04d}.json")
                            assert 0<base['t_sec']-refrow['t_sec']<=cfg['axis_reference_max_age_s']
                            assert ref['target_id']==obj['id'] and 'axis' in refrow['body_3d'][0]['skeleton']
                            assert np.allclose(abs(np.dot(ref['axis'],refrow['body_3d'][0]['skeleton']['axis'])),1.)
                            counts[v]['history_frames']+=1
                            if sk['direction']['source']=='PAST_DIRECTION_CURRENT_SUPPORT':
                                cov=np.cov(p[ids].T);vals,vecs=np.linalg.eigh(cov)
                                assert np.dot(ref['axis'],cov@ref['axis'])/vals[-1]>=cfg['axis_min_variance_fraction']-1e-10
                                assert abs(np.dot(ref['axis'],vecs[:,-1]))>=np.cos(np.deg2rad(cfg['axis_max_angle_degrees']))-1e-10
        print('VERIFIED',sid,flush=True)
    assert all(c['frames']==1966 and c['target_frames']==1934 and c['deleted_members']==0 for c in counts.values())
    assert all(v==0 for v in empty_targets.values())
    dump(E/'ALL_FRAME_SOURCE_VERIFICATION_R2.json',{'status':'PASS','counts':counts,'empty_holdout_targets':empty_targets,
         'sources':sources,'every_valid_node_current_target_supported':True,'source_coordinates_and_full_layers_verified':True,
         'future_or_predicted_nodes':0,'human_precision':None,'furniture_contamination_rate':None,'anatomical_accuracy':None,
         'code_sha256':{n:sha(HERE/n) for n in ['experiment_actions.py','research_actions.py','verify_research_actions.py']}})


if __name__=='__main__':main()

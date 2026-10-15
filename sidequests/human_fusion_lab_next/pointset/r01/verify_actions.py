"""Verify every output member and supported node against actual current raw points."""
from pathlib import Path
import numpy as np
from actions import OUT, HERE, EVIDENCE, R, T, read, load, dump, sha


if __name__=='__main__':
    manifest=read(OUT/'RUN_MANIFEST.json');prior=Path(manifest['config']['background_experiment'])
    catalog=read(OUT/'catalog.json');stats=[];total=0;unsupported=0
    for rec in catalog['sessions']:
        sid=rec['session_id'];meta,raw,hashes=load(sid);assert hashes==rec['source_sha256']
        reg=None if sid==catalog['background']['session'] else read(prior/(sid+'_registration.json'))
        observed=0;nodecount=0
        for fi in rec['available_frames']:
            row=read(OUT/sid/f'{fi:04d}.json');f=meta['frames'][fi]
            assert row['source_frame']==f and row['source_sha256']==hashes
            assert not row['posture']['confirmed'] and not row['selection']['uses_future_action_points']
            p=raw[f['offset_points']:f['offset_points']+f['count_points']].astype('f8')@R.T+T
            if reg:p=p@np.array(reg['R']).reshape(3,3).T+reg['t']
            for obj in row['body_3d']:
                ids=obj['source_indices'];members=set(ids)
                assert len(ids)==len(members)==obj['point_count']
                assert all(type(i)is int and 0<=i<f['count_points'] for i in ids)
                assert np.allclose(np.array(obj['points']),p[obj['display_source_indices']],atol=.000051)
                assert np.allclose(obj['bbox']['min'],p[ids].min(axis=0))
                assert np.allclose(obj['bbox']['max'],p[ids].max(axis=0))
                for n in obj['skeleton']['nodes'].values():
                    if n['valid']:
                        assert n['support_source_indices'] and set(n['support_source_indices'])<=members
                        assert np.allclose(n['xyz'],p[n['support_source_indices']].mean(axis=0))
                        nodecount+=1
                    else:assert n['xyz'] is None and not n['support_source_indices']
                if not any(n['valid'] for n in obj['skeleton']['nodes'].values()):unsupported+=1
                observed+=1
            total+=1
        stats.append({'sid':sid,'evaluated_frames':len(rec['available_frames']),'target_frames':observed,'supported_nodes':nodecount})
    assert total==1934+32
    assert stats[-1]['target_frames']==0
    assert sum(s['target_frames'] for s in stats[:-1])==1934
    dump(EVIDENCE/'ALL_FRAME_SOURCE_VERIFICATION.json',{'status':'PASS','frames':total,'sessions':stats,
         'body_axis_ambiguous_frames':unsupported,'every_supported_node_current_raw_mean':True,
         'anatomical_accuracy':None,'human_precision':None,
         'live_code_sha256':{p.name:sha(p) for p in HERE.glob('*.py') if p.name in ['actions.py','core.py','server.py']}})
    print('PASS',total,'frames; raw members and supported nodes verified; ambiguous-axis frames',unsupported)

"""Independent source binding, unchanged recovery and bounded sign causal replay."""
from pathlib import Path
import numpy as np
from actions import read, dump, load, sha, HERE, OUT
from research_r3 import E, RESULT
from research_actions import frame_points
from axis_sign_r3 import AxisSign, CURRENT_SOURCES

def run():
    frozen=read(E/'FROZEN_SIGN.json');assert all(sha(HERE/n)==s for n,s in frozen.items())
    cfg=read(OUT/'RUN_MANIFEST.json')['config'];cfg.update(read(HERE/'config_research_r2.json'));cfg.update(read(HERE/'config_research_r3.json'))
    cat=read(OUT/'catalog.json');prior=Path(cfg['background_experiment']);counts={v:{'frames':0,'nodes':0,'past_references':0,'members_unchanged':0} for v in ['r3_signed','r3_signed_feedback']}
    for rec in cat['sessions']:
        sid=rec['session_id'];meta,raw,hashes=load(sid);assert hashes==rec['source_sha256']
        reg=None if sid==cat['background']['session'] else read(prior/(sid+'_registration.json'));states={v:AxisSign(cfg) for v in counts};verified={v:{} for v in counts}
        for fi in rec['available_frames']:
            f=meta['frames'][fi];prefix=raw[:f['offset_points']+f['count_points']];_,p=frame_points(prefix,f,reg)
            for v in counts:
                base_v='r3_feedback' if v.endswith('feedback') else 'r3';base=read(RESULT/base_v/sid/f'{fi:04d}.json');row=read(RESULT/v/sid/f'{fi:04d}.json');body=row['body_3d']
                assert row['source_sha256']==hashes and row['source_frame']==f and row['identity']=='UNKNOWN'
                assert row['added_members']==base['added_members'] and row['anchor_source_indices']==base['anchor_source_indices'] and row['connection_evidence']==base['connection_evidence']
                assert row['posture']==base['posture'] and not row['posture']['confirmed']
                ids=np.array(body[0]['source_indices'],dtype=int) if body else np.array([],dtype=int);ident=body[0]['id'] if body else None
                sk=base['body_3d'][0]['skeleton'] if body else {};expected=states[v].update(row['t_sec'],fi,ident,sk,p,ids)
                if body:
                    result=body[0]['skeleton'];assert expected==result
                    assert body[0]['source_indices']==base['body_3d'][0]['source_indices']
                    for n in result['nodes'].values():
                        if n['valid']:
                            assert n['support_source_indices'] and set(n['support_source_indices'])<=set(ids)
                            assert np.allclose(n['xyz'],p[n['support_source_indices']].mean(axis=0));counts[v]['nodes']+=1
                        else:assert n['xyz'] is None and not n['support_source_indices']
                    assert result['predicted_nodes']==[]
                    if 'axis' in result:assert np.isclose(abs(np.dot(result['axis'],sk['axis'])),1.)
                    ref=result['orientation']['reference']
                    if ref:
                        assert ref['fi']<fi and 0<row['t_sec']-ref['t_sec']<=cfg['axis_reference_max_age_s'] and ref['target_id']==ident
                        ref_sk=verified[v][ref['fi']];assert ref_sk['direction']['source'] in CURRENT_SOURCES
                        assert np.allclose(ref['axis'],ref_sk['axis']);counts[v]['past_references']+=1
                    verified[v][fi]=result
                counts[v]['frames']+=1;counts[v]['members_unchanged']+=1
        print('SIGN VERIFIED',sid,flush=True)
    assert all(c['frames']==1966 and c['members_unchanged']==1966 for c in counts.values())
    dump(E/'SIGN_VERIFICATION.json',{'status':'PASS','counts':counts,'current_raw_means':True,'future_rows_inaccessible':True,
        'background_and_recovery_unchanged':True,'independent_current_reliable_sign_reference_only':True,'identity':'UNKNOWN','anatomical_accuracy':'UNKNOWN'})

if __name__=='__main__':run()

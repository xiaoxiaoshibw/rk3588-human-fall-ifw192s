"""Re-run current geometry from restored original recordings, preserving old outputs."""
import argparse
from pathlib import Path
import numpy as np
import yaml
from actions import HERE, OUT, read, dump, load, sha, choose
from core import cluster
from research_actions import frame_points
from research_scene_change import domain
from scene_change import FrozenSurfaces
from scene_static import static_reference_mask
from scene_geometry_ledger import GeometryLedger


def main(output):
    output.mkdir(parents=True,exist_ok=False)
    current=HERE/'action_research_scene_static';cat=read(OUT/'catalog.json');summary=read(current/'SUMMARY.json')
    cfg=summary['configuration']['frozen_r1'];controls=summary['configuration']['controls'];prior=Path(cfg['background_experiment'])
    if sha(prior/'background.npz')!=cat['background']['background_file_sha256']:raise ValueError('Frozen background drift')
    model=FrozenSurfaces(np.load(prior/'background.npz')['xyz'],cat['background']['tolerance_m'],controls)
    limits=read(current/'CALIBRATION.json')['limits'];cache=GeometryLedger(HERE/'action_research_retention/baseline_02')
    records=[];bindings={};missing=[]
    for rec in cat['sessions']:
        sid=rec['session_id']
        directory=HERE.parents[3]/'captures/remote'/sid
        if not (directory/'meta.json').exists() or not (directory/'points.bin').exists():
            missing.append(sid);continue
        meta,raw,hashes=load(sid)
        if hashes!=rec['source_sha256']:raise ValueError('Restored original SHA mismatch')
        bindings[sid]=hashes
        reg=None if sid==cat['background']['session'] else read(prior/(sid+'_registration.json'))
        last=seen=last_t=None
        for fi in rec['available_frames']:
            q,p=frame_points(raw,meta['frames'][fi],reg)
            cached_raw,cached_p,base=cache.frame(sid,fi)
            np.testing.assert_array_equal(q,cached_raw)
            np.testing.assert_allclose(p,cached_p,atol=1e-10,rtol=0,equal_nan=True)
            row=read(current/sid/f'{fi:04d}.json');assert row['source_frame']==meta['frames'][fi]
            nominal=p.copy();valid=domain(q,p,cfg);anchor=static_reference_mask(p,valid,cfg['roi_xy'])
            _,diag=model.compensate(p[anchor],limits)
            assert diag['status']==row['vibration']['status'],(sid,fi,'pose status')
            np.testing.assert_allclose(diag['R'],row['vibration']['R'],atol=1e-10,rtol=0)
            np.testing.assert_allclose(diag['t'],row['vibration']['t'],atol=1e-10,rtol=0)
            if diag['status']=='COMPENSATED':p=p@np.array(diag['R']).T+diag['t']
            valid=domain(q,p,cfg)
            fg,matched,dist,extra,ambiguous=model.split_pose_hypotheses(nominal,p,valid)
            np.testing.assert_array_equal(fg,row['scene_change']['new_source_indices'])
            np.testing.assert_array_equal(np.flatnonzero(matched),row['scene_change']['matched_source_indices'])
            np.testing.assert_array_equal(np.flatnonzero(ambiguous),row['scene_change']['pose_ambiguous_indices'])
            groups,_=cluster(p[fg],cfg)
            assert len(groups)==len(row['scene_clusters'])
            for group,proposal in zip(groups,row['scene_clusters']):
                np.testing.assert_array_equal(fg[group],proposal['source_indices'])
                np.testing.assert_allclose(proposal['points'],p[proposal['display_source_indices']],atol=.000051,rtol=0)
            t=base['t_sec']
            if last_t is not None and (t<=last_t or t-last_t>cfg['max_gap_s']):last=seen=None
            if seen is not None and t-seen>cfg['max_gap_s']:last=seen=None
            win=choose(groups,p,fg,cfg,last,None);ids=fg[groups[win[1]]] if win else np.empty(0,int)
            np.testing.assert_array_equal(ids,row['selection']['selected_source_indices'])
            if win:last=win[2][:2];seen=t
            last_t=t
            records.append({'sid':sid,'fi':fi,'original_xyz_equal_cache':True,'pose_equal':True,
                'foreground_equal':True,'all_clusters_equal':True,'selected_target_equal':True})
        if load(sid)[2]!=hashes:raise ValueError('Original input changed during verification')
        print(sid,len(rec['available_frames']),'ORIGINAL replay equal',flush=True)
    dump(output/'ORIGINAL_REPLAY_CHECK.json',{'status':'PASS_AVAILABLE_ORIGINALS','original_frames_checked':len(records),
        'frames':records,'current_sha256':bindings,'missing_sessions':missing,
        'background_source_original_status':'BLOCKED' if cat['background']['session'] in missing else 'AVAILABLE',
        'calibration_policy':'FROZEN_PRIOR_CAL_ENVELOPE_REUSED_NOT_RECALIBRATED',
        'restored_geometry_equals_cached_experiment':True,'semantic_accuracy':None,
        'code_sha256':{'check_scene_original.py':sha(HERE/'check_scene_original.py')}})


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,required=True)
    main(parser.parse_args().out)

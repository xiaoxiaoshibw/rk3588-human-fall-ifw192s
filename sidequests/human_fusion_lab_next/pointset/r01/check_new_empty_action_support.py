"""Bounded original-action diagnostic for a proposed empty map; no promotion."""
import argparse
from pathlib import Path
import numpy as np
from actions import HERE, OUT, read, dump, load, sha, choose
from core import cluster
from research_actions import frame_points
from research_scene_change import domain
from scene_change import FrozenSurfaces
from scene_static import static_reference_mask


def main(output):
    output.mkdir(parents=True, exist_ok=False)
    proposal=HERE.parents[3]/'docs/human_capture/evidence/2026-10-14_hfus_new_empty_221808_r1'
    analysis=read(proposal/'NEW_EMPTY_ANALYSIS.json')
    cfg=analysis['config']; controls=analysis['controls']; prior=Path(cfg['background_experiment'])
    old=FrozenSurfaces(np.load(prior/'background.npz')['xyz'],analysis['historical_tolerance_m'],controls)
    new=FrozenSurfaces(np.load(proposal/'background.npz')['xyz'],analysis['candidate_tolerance_m'],controls)
    limits=read(HERE/'action_research_scene_static/CALIBRATION.json')['limits']
    cat=read(OUT/'catalog.json'); rows=[]; hashes={}
    for rec in cat['sessions']:
        sid=rec['session_id']
        if sid==cat['background']['session']:continue
        meta,raw,source=load(sid)
        if source!=rec['source_sha256']:raise ValueError('Source changed')
        hashes[sid]=source
        reg=read(prior/(sid+'_registration.json'));frames=rec['available_frames']
        picks=sorted(set([frames[0],frames[len(frames)//2],frames[-1]]+[i for i in [30,124,192] if i in frames]))
        for fi in picks:
            q,p=frame_points(raw,meta['frames'][fi],reg);nominal=p.copy();valid=domain(q,p,cfg)
            _,diag=old.compensate(p[static_reference_mask(p,valid,cfg['roi_xy'])],limits)
            if diag['status']=='COMPENSATED':p=p@np.array(diag['R']).T+diag['t']
            valid=domain(q,p,cfg);fg,_,_,_,_=new.split_pose_hypotheses(nominal,p,valid)
            groups,_=cluster(p[fg],cfg);winner=choose(groups,p,fg,cfg,None,None)
            saved=read(HERE/'action_research_scene_static'/sid/f'{fi:04d}.json')
            target=np.asarray(saved['selection']['selected_source_indices'],int)
            kept=np.intersect1d(target,fg)
            rows.append({'sid':sid,'fi':fi,'old_candidate_points':len(target),'old_candidate_remaining_foreground':len(kept),
                'retention_fraction':len(kept)/len(target) if len(target) else None,
                'new_foreground_points':len(fg),'new_clusters':len(groups),'new_geometry_candidate':winner is not None,
                'alignment_status':diag['status'],'identity':'GEOMETRIC_CANDIDATE_NOT_HUMAN_GT'})
        if load(sid)[2]!=source:raise ValueError('Source changed during probe')
        print(sid,len(picks),'action probes',flush=True)
    dump(output/'ACTION_SUPPORT_CHECK.json',{'status':'BOUNDED_DIAGNOSTIC_NOT_ACCEPTANCE','frames':rows,'sources':hashes,
        'candidate_background_sha256':sha(proposal/'background.npz'),'action_frames_used_for_calibration':False,
        'background_promoted':False,'semantic_accuracy':None,'threshold_changes':False,
        'selection_policy':'INDEPENDENT_GEOMETRIC_CANDIDATE_PER_PROBE; NO_CAUSAL_TRACKING_REPLAY',
        'code_sha256':sha(HERE/'check_new_empty_action_support.py')})


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,required=True)
    main(parser.parse_args().out)

"""Independent new-empty candidate analysis; never replace historical background."""
import argparse
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree
from actions import HERE, OUT, read, dump, load, sha, choose
from core import voxelize, cluster
from research_actions import frame_points
from research_scene_change import domain
from scene_change import FrozenSurfaces
from scene_static import static_reference_mask


def main(sid, output):
    output.mkdir(parents=True,exist_ok=False)
    meta,raw,hashes=load(sid);cat=read(OUT/'catalog.json')
    frozen=read(HERE/'action_research_scene_static/SUMMARY.json')
    cfg=frozen['configuration']['frozen_r1'];controls=frozen['configuration']['controls']
    prior=Path(cfg['background_experiment']);tau=cat['background']['tolerance_m']
    old=FrozenSurfaces(np.load(prior/'background.npz')['xyz'],tau,controls)
    limits=read(HERE/'action_research_scene_static/CALIBRATION.json')['limits']
    folds={'fit':list(range(0,len(meta['frames']),3)),
           'cal':list(range(1,len(meta['frames']),3)),
           'holdout':list(range(2,len(meta['frames']),3))}
    bank={};alignments={};context=[]
    def aligned(fi):
        q,p=frame_points(raw,meta['frames'][fi],None);nominal=p.copy();valid=domain(q,p,cfg)
        anchor=static_reference_mask(p,valid,cfg['roi_xy']);_,diag=old.compensate(p[anchor],limits)
        alignments[fi]=diag
        if diag['status']=='COMPENSATED':p=p@np.array(diag['R']).T+diag['t']
        return q,p,nominal,domain(q,p,cfg)
    for fi in folds['fit']:
        q,p,nominal,valid=aligned(fi)
        # Failed nominal-to-old-reference alignment does not enter the new map.
        if alignments[fi]['status']!='COMPENSATED':continue
        keys,centers,_,_=voxelize(p[valid],cfg['voxel_m'])
        for key,center in zip(keys,centers):
            k=tuple(key);total,count=bank.get(k,(np.zeros(3),0));bank[k]=(total+center,count+1)
    accepted=sum(alignments[f]['status']=='COMPENSATED' for f in folds['fit'])
    if not accepted:raise ValueError('No supported FIT alignment; no new map')
    required=int(np.ceil(accepted*cfg['background_min_frame_fraction']))
    background=np.array([total/count for total,count in bank.values() if count>=required])
    tree=cKDTree(background);calibration=[]
    for fi in folds['cal']:
        q,p,nominal,valid=aligned(fi)
        if alignments[fi]['status']=='COMPENSATED':calibration.append(tree.query(p[valid])[0])
    if not calibration:raise ValueError('No supported CAL frames')
    measured=float(np.quantile(np.concatenate(calibration),cfg['background_calibration_quantile']))
    candidate_tau=min(cfg['background_tolerance_cap_m'],measured+cfg['voxel_m']/2)
    cap_reached=measured+cfg['voxel_m']/2>cfg['background_tolerance_cap_m']
    np.savez_compressed(output/'background.npz',xyz=background)
    proposed=FrozenSurfaces(background,candidate_tau,controls)
    for fi in folds['holdout']:
        q,p,nominal,valid=aligned(fi)
        old_fg,_,_,_,_=old.split_pose_hypotheses(nominal,p,valid)
        new_fg,matched,dist,_,ambiguous=proposed.split_pose_hypotheses(nominal,p,valid)
        groups,_=cluster(p[new_fg],cfg);winner=choose(groups,p,new_fg,cfg,None,None)
        d_old=old.tree.query(p[valid])[0];d_new=tree.query(p[valid])[0]
        context.append({'fi':fi,'domain_points':int(valid.sum()),'alignment_status':alignments[fi]['status'],
            'old_foreground':len(old_fg),'new_foreground':len(new_fg),'new_clusters':len(groups),
            'person_geometry_candidate':winner is not None,
            'old_distance_p50_p95_m':np.quantile(d_old,[.5,.95]).tolist(),
            'new_distance_p50_p95_m':np.quantile(d_new,[.5,.95]).tolist(),
            'pose_ambiguous_points':int(ambiguous.sum())})
    if load(sid)[2]!=hashes:raise ValueError('New input changed during analysis')
    dump(output/'NEW_EMPTY_ANALYSIS.json',{'session_id':sid,'frames':len(meta['frames']),
        'total_points':meta['total_points'],'source_sha256':hashes,'folds':folds,
        'fit_accepted_frames':accepted,'fit_min_presence_frames':required,'background_voxels':len(background),
        'calibration_quantile_m':measured,'candidate_tolerance_m':candidate_tau,
        'historical_tolerance_m':tau,'tolerance_cap_reached':cap_reached,'holdout':context,
        'alignment':{str(k):v for k,v in alignments.items()},
        'alignment_reference':'HISTORICAL_FROZEN_MAP; OLD_RT_NOMINAL_NOT_NEW_PHYSICAL_CALIBRATION',
        'new_background_status':'PROPOSED_DIAGNOSTIC_ONLY_NOT_DEFAULT',
        'new_session_identity':'USER_OFFERED_EMPTY_REFERENCE_CANDIDATE; NO_REVIEWED_POINT_IDENTITY_GT',
        'original_131958_recovered':False,'historical_background_replaced':False,
        'background_sha256':sha(output/'background.npz'),'config':cfg,'controls':controls,
        'code_sha256':{'analyze_scene_new_empty.py':sha(HERE/'analyze_scene_new_empty.py')}})
    print('NEW_EMPTY',len(context),'HOLDOUT frames; proposed voxels',len(background),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--sid',required=True);parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();main(args.sid,args.out)

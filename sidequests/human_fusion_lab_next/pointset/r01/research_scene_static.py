"""Explicit cached-XYZ continuation: protected anchors, all change proposals."""
import argparse
import copy
import sys
import time
from pathlib import Path
import numpy as np
import yaml
from actions import HERE, OUT, read, dump, sha, choose, Posture, describe_object
from core import cluster, roi_mask
from research_scene_change import domain
from scene_change import FrozenSurfaces
from scene_static import static_reference_mask, change_proposals
from scene_geometry_ledger import GeometryLedger


def main(output, ledger_folder):
    output.mkdir(parents=True,exist_ok=False);start=time.perf_counter()
    cat=read(OUT/'catalog.json');cfg=read(OUT/'RUN_MANIFEST.json')['config'];prior=Path(cfg['background_experiment'])
    controls=yaml.safe_load((HERE/'config_scene_change.yaml').read_text(encoding='utf8'))
    model=FrozenSurfaces(np.load(prior/'background.npz')['xyz'],cat['background']['tolerance_m'],controls)
    if sha(prior/'background.npz')!=cat['background']['background_file_sha256']:raise ValueError('Background changed')
    calibration=read(HERE/'action_research_scenechange_guarded/CALIBRATION.json')
    limits=calibration['limits'];cache=GeometryLedger(ledger_folder)
    before={str(HERE/n):sha(HERE/n) for n in ['core.py','actions.py','config.yaml','config_actions.yaml','scene_change.py']}
    before[str(prior/'background.npz')]=sha(prior/'background.npz')
    dump(output/'CALIBRATION.json',{**calibration,'anchor_policy':'OUTSIDE_FROZEN_ACTIVITY_ROI',
        'calibration_policy':'PREVIOUS_CAL_ENVELOPE_REUSED; FRESH_CAL_NOT_AVAILABLE',
        'original_bytes_available_now':False,'new_action_or_holdout_calibration':False})
    bg_sample=model.xyz[np.linspace(0,len(model.xyz)-1,min(len(model.xyz),cfg['display_sample_points']),dtype=int)]
    dump(output/'BACKGROUND_CONTEXT.json',{'points':np.round(bg_sample,4).tolist(),'sampled':True,
        'full_count':len(model.xyz),'source_sha256':sha(prior/'background.npz'),
        'role':'FROZEN_OBSERVATION_CONTEXT_NOT_CURRENT_FOREGROUND_OR_SEMANTIC_MESH'})
    records=[];states={}
    for rec in cat['sessions']:
        sid=rec['session_id'];folder=output/sid;folder.mkdir()
        last=seen=last_t=None;generation=0;posture_state=Posture(cfg)
        for fi in rec['available_frames']:
            q,p,base=cache.frame(sid,fi);nominal=p.copy();valid=domain(q,p,cfg)
            anchors=static_reference_mask(p,valid,cfg['roi_xy']);anchor_ids=np.flatnonzero(anchors)
            _,diag=model.compensate(p[anchor_ids],limits)
            diag.update(anchor_policy='OUTSIDE_FROZEN_ACTIVITY_ROI',anchor_input_count=len(anchor_ids),
                roi_excluded_count=int(np.count_nonzero(valid & ~anchors)),anchors_inside_roi=0)
            if diag['status']=='COMPENSATED':p=p@np.array(diag['R']).T+diag['t']
            valid=domain(q,p,cfg)
            fg,matched,dist,extra,ambiguous=model.split_pose_hypotheses(nominal,p,valid)
            groups,_=cluster(p[fg],cfg);t=base['t_sec']
            reset=last_t is not None and (t<=last_t or t-last_t>cfg['max_gap_s'])
            if reset or (seen is not None and t-seen>cfg['max_gap_s']):last=seen=None;posture_state=Posture(cfg)
            win=choose(groups,p,fg,cfg,last,None);ids=fg[groups[win[1]]] if win else np.empty(0,int);body=[]
            if win:
                if last is None:generation+=1
                last=win[2][:2];seen=t
                body=[describe_object(p,ids,dist,p[np.setdiff1d(fg,ids)],model.tau,cfg,'STATIC-'+str(generation))]
                body[0]['semantic_identity']='UNKNOWN_GEOMETRIC_PERSON_CANDIDATE'
            posture=posture_state.update(t,p[ids] if len(ids) else None);last_t=t
            proposals=change_proposals(p,fg,groups,cfg,dist,model.tau,body)
            proposal_ids=[i for row in proposals for i in row['source_indices']]
            assert len(proposal_ids)==len(set(proposal_ids)) and set(proposal_ids)<=set(fg.tolist())
            assert set(ids.tolist())<=set(fg.tolist()) and not matched[ids].any()
            assert not roi_mask(nominal[anchor_ids],cfg['roi_xy']).any()
            previous=read(HERE/'action_research_scenechange_guarded'/sid/f'{fi:04d}.json')
            oldids=np.array(previous['selection']['selected_source_indices'],int)
            sample=fg[np.linspace(0,len(fg)-1,min(len(fg),cfg['display_sample_points']),dtype=int)] if len(fg) else []
            row=copy.deepcopy(base)
            row.update(variant='scene_static',body_3d=body,full_3d=proposals,roi_3d=body,
                scene_clusters=proposals,posture=posture,foreground_display=np.round(p[sample],4).tolist(),
                fg_count=len(fg),roi_fg_count=int(roi_mask(p[fg],cfg['roi_xy']).sum()),background_removed=int(matched.sum()),
                vibration=diag,added_members=[],connection_evidence=[],
                input_provenance={'mode':'CACHED_XYZ_REGRESSION_NOT_ORIGINAL_RECORDING_REPLAY',
                    'original_bytes_available_now':False,'ledger_sha256':cache.hashes[str((cache.folder/sid/f'{fi:04d}.npz'))]},
                selection={'selected_source_indices':ids.tolist(),'candidate_count':len(groups),
                    'rejected_foreground':len(fg)-len(ids),'uses_future_action_points':False},
                scene_change={'new_source_indices':fg.tolist(),'matched_source_indices':np.flatnonzero(matched).tolist(),
                    'pose_ambiguous_indices':np.flatnonzero(ambiguous).tolist(),'surface_extra_removed':extra,
                    'pose_ambiguity_identity':'UNKNOWN','body_identity':'UNKNOWN','background_updated':False,
                    'noise_or_small_cluster_source_indices':np.setdiff1d(fg,proposal_ids).tolist()},
                delta={'old_count':len(oldids),'new_count':len(ids),'added_count':len(np.setdiff1d(ids,oldids)),
                    'removed_count':len(np.setdiff1d(oldids,ids))})
            dump(folder/f'{fi:04d}.json',row)
            states[diag['status']]=states.get(diag['status'],0)+1
            records.append({'sid':sid,'fi':fi,'target':len(ids),'previous_target':len(oldids),'fg':len(fg),
                'previous_fg':previous['fg_count'],'proposal_count':len(proposals),'vibration':diag,
                'previous_vibration':previous['vibration'],'human_precision':None,'furniture_contamination':None})
        print(sid,len(rec['available_frames']),'cached geometry frames complete',flush=True)
    assert len(records)==1966
    preserved={p:sha(Path(p))==h for p,h in before.items()}
    if not all(preserved.values()):raise ValueError('Frozen method changed')
    dump(output/'INPUT_PROVENANCE.json',cache.provenance())
    dump(output/'SUMMARY.json',{'frames':records,'status':'DEVELOPMENT_GEOMETRY_REGRESSION',
        'command':sys.argv,'elapsed_s':time.perf_counter()-start,'vibration_status_counts':states,
        'configuration':{'frozen_r1':cfg,'controls':controls},'preservation':preserved,
        'semantic_accuracy':'UNKNOWN','original_byte_verification':'BLOCKED_MISSING_INPUT',
        'source_sha256':cache.bindings['sources'],
        'code_sha256':{n:sha(HERE/n) for n in ['scene_geometry_ledger.py','scene_static.py','research_scene_static.py','scene_change.py']}})


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--geometry-ledger',type=Path,required=True)
    args=parser.parse_args();main(args.out,args.geometry_ledger)

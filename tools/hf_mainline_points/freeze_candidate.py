"""Select and freeze only from specified diagnosis, never excluded context/empty HOLDOUT."""
from pathlib import Path
import sys
import numpy as np
from scipy.spatial import cKDTree
ROOT=Path(__file__).resolve().parents[2];PS=ROOT/'sidequests/human_fusion_lab_next/pointset/r01';sys.path.insert(0,str(PS))
from actions import read,dump,load,sha,OUT
from research_retention import E,context,excluded
from research_actions import frame_points,masks
from core import roi_mask


def main():
    cat,cfg,prior,tree,tau=context();blocked=excluded();support=np.load(E/'REFERENCE_FIT_SUPPORT.npz')['fit_frame_coverage']
    hard={'082623':[119,124,192,231,232],'082717':[140,263],'082906':[94]}
    cases=[];measure=[];fitvalues=[];neighborvalues=[]
    for rec in cat['sessions'][:-1]:
        sid=rec['session_id'];meta,raw,hashes=load(sid);reg=read(prior/(sid+'_registration.json'))
        # Old diagnosis list is merely a case selector; excluded context wins.
        old=read(ROOT/'docs/human_capture/evidence/2026-10-14_hfus_pointset_actions_r2/DIAGNOSIS.json')['cases']
        frames=set(c['fi'] for c in old if c['sid']==sid)
        for f in hard.get(sid[-6:],[]):frames.update(range(max(0,f-3),min(rec['frame_count'],f+4)))
        frames={f for f in frames if not any(k in blocked.get(sid,set()) for k in range(max(0,f-4),f+1))}
        for fi in sorted(frames):
            cases.append({'sid':sid,'fi':fi});q,p=frame_points(raw,meta['frames'][fi],reg);_,domain,dist,fg=masks(q,p,tree,tau,cfg)
            base=read(OUT/sid/f'{fi:04d}.json');anchor=np.array(base['selection']['selected_source_indices'],int)
            if not len(anchor):continue
            bg=np.flatnonzero(domain&(dist<=tau));d=cKDTree(p[anchor]).query(p[bg])[0]
            ids=bg[(d<=.12)&roi_mask(p[bg],cfg['roi_xy'])]
            if not len(ids):continue
            nearest=tree.query(p[ids])[1];cover=support[nearest];neighbors=cKDTree(p[anchor]).query_ball_point(p[ids],.12,return_length=True)
            fitvalues.extend(cover.tolist());neighborvalues.extend(neighbors.tolist())
            measure.append({'sid':sid,'fi':fi,'pool':len(ids),'z_q':np.quantile(p[ids,2],[.1,.5,.9]).tolist(),
                            'fit_q':np.quantile(cover,[.1,.5,.9]).tolist(),'anchor_neighbors_q':np.quantile(neighbors,[.1,.5,.9]).tolist()})
    assert cases and fitvalues
    max_fit=int(np.quantile(fitvalues,.1))
    c={'attachment_m':.12,'minimum_anchor_neighbors':4,'maximum_fit_coverage':max_fit,
       'past_radius_m':.12,'past_age_s':.4,'past_frames':4,'max_gap_s':cfg['max_gap_s'],
       'variants':['local','reference','temporal','combined','r3','feedback'],'validation_status':'CONTEXT_HOLDOUT_FIRST_FROZEN_EVALUATION_HISTORICALLY_SEEN',
       'selection_reason':'Existing .12m diagnosis neighborhood; >=4 current anchor neighbors from original graph density; lowest FIT-coverage diagnosis decile risk; past .4s/4 frames bounded original precedent; no labels',
       'identity':'UNKNOWN','reference_normals':'MISSING','production_thresholds_unchanged':True}
    dump(E/'FROZEN_CASES.json',{'cases':cases,'excluded':{k:sorted(v) for k,v in blocked.items()},'measured':measure,
         'fit_q':np.quantile(fitvalues,[0,.1,.5,.9,1]).tolist(),'neighbors_q':np.quantile(neighborvalues,[0,.1,.5,.9,1]).tolist()})
    dump(PS/'config_research_retention.json',c)
    dump(E/'FROZEN_EXPERIMENT.json',{'config':c,'config_sha':sha(PS/'config_research_retention.json'),
         'case_sha':sha(E/'FROZEN_CASES.json'),'code_sha':sha(PS/'research_retention.py'),'holdout_used_for_selection':False})
    print('FROZEN',len(cases),'diagnostic frames, maximum FIT coverage',max_fit,flush=True)


if __name__=='__main__':main()

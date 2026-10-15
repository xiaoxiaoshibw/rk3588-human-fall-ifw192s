"""Read-only diagnostic study; no labels, future inference, or HOLDOUT selection."""
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree
from actions import HERE, ROOT, OUT, read, dump, load, sha
from research_actions import RESULT as R2, frame_points

E = ROOT/'docs/human_capture/evidence/2026-10-14_hfus_pointset_actions_r3'
RESULT = HERE/'action_research_r3'

def shape(q):
    vals, vecs = np.linalg.eigh(np.cov(q.T))
    return {'eigenvalues': vals.tolist(), 'linearity': float(1-vals[-2]/max(vals[-1],1e-9)),
            'planarity': float((vals[-2]-vals[0])/max(vals[-1],1e-9)),
            'normal_z': float(abs(vecs[2,0])), 'axis': vecs[:,-1].tolist()}

def study():
    cat = read(OUT/'catalog.json'); cfg = read(OUT/'RUN_MANIFEST.json')['config']
    prior = Path(cfg['background_experiment']); tree = cKDTree(np.load(prior/'background.npz')['xyz'])
    compare = read(ROOT/'docs/human_capture/evidence/2026-10-14_hfus_pointset_actions_r2/EXPERIMENT_COMPARISON.json')
    missing = [r for r in compare['frames']['axis'] if r['axis_missing']]
    cases = {(r['sid'],r['fi']) for r in missing}
    for sid,f in [('cap_20261013_082623',192),('cap_20261013_082623',119),('cap_20261013_082623',232),('cap_20261013_082717',140)]:
        cases.update((sid,k) for k in range(f-3,f+4))
    rows = []; sources = {}
    for rec in cat['sessions'][:-1]:
        sid = rec['session_id']; meta,raw,hashes = load(sid); assert hashes==rec['source_sha256']; sources[sid]=hashes
        reg = read(prior/(sid+'_registration.json'))
        for s,fi in sorted(cases):
            if s!=sid: continue
            diag = read(R2/sid/f'{fi:04d}.json')
            _,p = frame_points(raw,meta['frames'][fi],reg)
            with np.load(R2/sid/f'{fi:04d}_sources.npz') as sets: ids=sets['target']
            history=[]
            for k in range(max(0,fi-4),fi):
                _,pp=frame_points(raw,meta['frames'][k],reg)
                with np.load(R2/sid/f'{k:04d}_sources.npz') as sets:
                    history.append((k,pp[sets['target']],pp[sets['unselected']]))
            target=cKDTree(p[ids]); fragments=[]
            for f in diag['fragments']:
                ix=np.array(f['source_indices']); q=p[ix]; d=target.query(q)[0]; bg=tree.query(q)[0]
                close=d<=.28
                counts=cKDTree(q).query_ball_point(q,.10,return_length=True)
                past=[{'fi':k,'target_fraction_12cm':float(np.mean(cKDTree(a).query(q)[0]<=.12)) if len(a) else 0,
                       'unselected_fraction_8cm':float(np.mean(cKDTree(b).query(q)[0]<=.08)) if len(b) else 0} for k,a,b in history]
                fragments.append(dict(f,shape=shape(q),near_background_fraction=float(np.mean(bg<2*cat['background']['tolerance_m'])),
                    floor_fraction=float(np.mean(q[:,2]<.08)),median_neighbors_10cm=float(np.median(counts)),
                    bridge_points_28cm=int(close.sum()),bridge_voxels_5cm=len(np.unique(np.floor(q[close]/.05),axis=0)),past=past))
            regions={}
            for name,mask in [('all',np.ones(len(ids),bool)),('above_z_median',p[ids,2]>np.median(p[ids,2])),('central_80pct',np.linalg.norm(p[ids]-np.median(p[ids],axis=0),axis=1)<=np.quantile(np.linalg.norm(p[ids]-np.median(p[ids],axis=0),axis=1),.8))]:
                q=p[ids][mask]; regions[name]=dict(shape(q),count=len(q),extent=np.ptp(q,axis=0).tolist())
            rows.append({'sid':sid,'fi':fi,'r2_axis_missing':(sid,fi) in {(r['sid'],r['fi']) for r in missing},'target_count':len(ids),'regions':regions,'fragments':fragments,'identity':'UNKNOWN'})
        print('study',sid,flush=True)
    dump(E/'DIAGNOSTIC_STUDY.json',{'rows':rows,'remaining_axis_missing':missing,'sources':sources,'holdout_consumed':False,'provenance':'AI_INFERRED_NOT_GT'})
    for r in rows:
        if (r['sid'],r['fi']) in [('cap_20261013_082623',192),('cap_20261013_082623',119),('cap_20261013_082623',232),('cap_20261013_082717',140)]:
            print(r['sid'],r['fi'],'shape',r['regions']['all'],flush=True)
            for f in r['fragments']:
                if f['min_target_distance_m']<.6: print({k:v for k,v in f.items() if k!='source_indices'},flush=True)

if __name__=='__main__': study()

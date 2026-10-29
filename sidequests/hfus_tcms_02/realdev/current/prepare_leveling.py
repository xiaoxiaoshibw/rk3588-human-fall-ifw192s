"""Fit one source-bound offline ground transform using the existing estimator."""
import argparse
import json
import math
import sys
from pathlib import Path
import numpy as np
from run import ROOT,source,sha,put,SID

def main(out):
    out=out.absolute()
    if not out.resolve().is_relative_to((ROOT/'docs/human_fall/evidence').resolve()):raise ValueError('evidence output required')
    out.mkdir(exist_ok=False)
    fit_frames=list(range(0,50,2));held_frames=[50,75,99]
    put(out/'PLAN.json',dict(fit_frames=fit_frames,held_frames=held_frames,source_stride=1,
        estimator='existing floor_roi v3 -> four full-height patches -> existing TLS/SVD/RANSAC consensus; no changed thresholds',
        role='offline ground display, source bound; not physical extrinsics qualification',
        no_candidate_or_pose_points_for_fit=True,source_sha=sha(__file__)))
    sys.path.insert(0,str(ROOT/'pc_apps/human_replay'))
    from floor_roi import detect_floor_regions_v3
    from leveling_estimators import ESTIMATORS
    from leveling_quality import rotation,compare
    src=source()
    try:
        samples=[];rows=[];frame_ids=[]
        for fi in fit_frames:
            f=src.frame(fi);p=f['xyz'];ids=np.flatnonzero(np.isfinite(p).all(1)&np.any(p!=0,1))
            samples.append(p[ids]);rows.append(ids+f['offset'])
            frame_ids.append(np.full(len(ids),fi,dtype=int))
        p=np.concatenate(samples)
        seed_n,seed_d=ESTIMATORS['ransac'](samples[0][::8])
        if seed_n[2]<0:seed_n,seed_d=-seed_n,-seed_d
        if seed_n[2]<.8 or not .8<=seed_d<=1.8:raise ValueError('initial plane is not a plausible ground orientation')
        pitch=math.degrees(math.atan2(-seed_n[0],seed_n[2]));roll=math.degrees(math.asin(float(seed_n[1])))
        initial=rotation(pitch,roll)
        domain=detect_floor_regions_v3(p,np.concatenate(frame_ids),pitch,roll)
        def select(q):
            xy=(q@initial.T)[:,:2];codes=np.zeros(len(q),dtype=int)
            for i,(xl,xh,yl,yh) in enumerate(domain['regions'],1):
                codes[(xy[:,0]>=xl)&(xy[:,0]<xh)&(xy[:,1]>=yl)&(xy[:,1]<yh)]=i
            return codes
        codes=select(p);take=codes>0
        held=[]
        for fi in held_frames:
            q=src.frame(fi)['xyz'];q=q[np.isfinite(q).all(1)&np.any(q!=0,1)];hc=select(q)
            held.append(dict(ordinal=fi,points=q[hc>0],regions=hc[hc>0]))
        quality=compare(p[take],codes[take],held,initial[2])
        put(out/'QUALITY.json',quality)
        if quality['consensus']!='GOOD':raise ValueError('existing ground quality checks rejected selected domain; see QUALITY.json')
        fitted=quality['estimators'][quality['recommended']]
        domain['candidate'].update(normal_source=fitted['normal_source'],offset_source_m=fitted['offset_source_m'],pitch_deg=fitted['pitch_deg'],roll_deg=fitted['roll_deg'])
        candidate=domain['candidate'];n=np.array(candidate['normal_source']);d=candidate['offset_source_m']
        R=rotation(candidate['pitch_deg'],candidate['roll_deg']);t=np.array([0.,0.,d])
        assert np.allclose(R[2],n,atol=1e-10,rtol=0)
        assert np.allclose(R@R.T,np.eye(3),atol=1e-10,rtol=0) and abs(np.linalg.det(R)-1)<1e-10
        validation=[]
        for fi in held_frames:
            q=src.frame(fi)['xyz'];q=q[np.isfinite(q).all(1)&np.any(q!=0,1)]
            residual=q@n+d;ground=q[np.abs(residual)<=.08];z=(ground@R.T+t)[:,2]
            validation.append(dict(fi=fi,full_points=len(q),plane_band_points=len(ground),
                support_ratio=len(ground)/len(q),band_rms_m=float(np.sqrt(np.mean(z*z))),
                band_p95_m=float(np.percentile(np.abs(z),95)),
                note='band-conditioned geometric residual; not independent ground identity truth'))
        back=((p@R.T+t)-t)@R
        artifact=dict(kind='project_ground_leveling',sid=SID,source_sha256=src.binding,
            from_frame='RAW/innolidar',to_frame='GROUND_PROJECT',units='m',R=R.tolist(),t=t.tolist(),
            row_formula='p_ground = p_raw @ R.T + t',plane=candidate,fit_frames=fit_frames,
            held_frames=validation,domain=domain['regions'],quality='GOOD / unchanged existing gates',roundtrip_max_m=float(np.abs(back-p).max()),
            qualification=dict(physical_verified=False,extrinsics_verified=False,runtime_eligible=False),
            code_sha={str(k.relative_to(ROOT)):sha(k) for k in [Path(__file__),ROOT/'pc_apps/human_replay/floor_roi.py',ROOT/'pc_apps/human_replay/floor_sheet.py',ROOT/'pc_apps/human_replay/floor_detector.py',ROOT/'pc_apps/human_replay/leveling_quality.py',ROOT/'pc_apps/human_replay/leveling_estimators/ransac.py']})
        import hashlib
        artifact['transform_id']=hashlib.sha256(json.dumps(artifact,sort_keys=True,separators=(',',':')).encode()).hexdigest()
        artifact['to_frame']='GROUND_PROJECT/'+artifact['transform_id']
        put(out/'TRANSFORM.json',artifact)
        with (out/'FIT_ROWS.npz').open('xb') as f:np.savez_compressed(f,global_rows=np.concatenate(rows))
        print(json.dumps(dict(pitch_deg=candidate['pitch_deg'],roll_deg=candidate['roll_deg'],height_m=d,
            support=candidate['support_ratio'],validation=validation,transform_sha=sha(out/'TRANSFORM.json'))))
    finally:src.close()

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);main(ap.parse_args().out)

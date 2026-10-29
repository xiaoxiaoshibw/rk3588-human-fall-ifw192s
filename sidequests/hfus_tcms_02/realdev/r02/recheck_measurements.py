"""Targeted corrections from frozen arrays; does not reread/refit the real source."""
import json
import math
import numpy as np
from bootstrap import ROOT,OUT,write,sha


if __name__=='__main__':
    old=ROOT/'docs/human_fall/evidence/2026-10-17_hfus_ground_obs_r1'
    p=OUT/'measurement';p.mkdir(exist_ok=False)
    # Freeze quantities/denominators before loading result arrays.
    write(p/'DEFINITIONS_V1.json',dict(
        r='slant range ||p_raw||, m',rho='horizontal range sqrt(x*x+y*y), m',
        theta='ray depression angle from horizontal, rad',h='assumed sensor-plane distance, m; not measured height',
        measured='same frame + 1 deg azimuth bucket; consecutive sorted slant ranges Delta r, m',
        sample='old E1_ARRAYS gaps/gap_mid; FIT [0,20)s legacy selected TLS-compatible band only',
        denominator='adjacent row pairs; band by pair slant midpoint; not band point count or ground nearest neighbors',
        horizontal_formula='rho=h*cot(theta); abs(d rho/d theta)=(rho^2+h^2)/h',
        slant_formula='r=h*csc(theta); abs(d r/d theta)=r*sqrt(r^2-h^2)/h',
        assumptions='ideal flat plane + common azimuth single ray step; bucket gaps are NOT direct estimates of these ray step formulas',
        mask_correction='n.p=w_peak -> z=(w_peak-nx*x-ny*y)/nz; all old thresholds/crop kept',
        scope='correction only; no new ground solve, no new identity confirmation'))
    with np.load(old/'results/E1_ARRAYS.npz') as z:
        gaps=z['gaps'];mid=z['gap_mid']
    result=[]
    for lo in range(2,8):
        values=gaps[(mid>=lo)&(mid<lo+1)]
        row=dict(slant_midpoint_band_m=[lo,lo+1],pair_count=len(values),
            p05_m=float(np.percentile(values,5)) if len(values) else None,
            median_m=float(np.median(values)) if len(values) else None,
            p95_m=float(np.percentile(values,95)) if len(values) else None,
            no_sample='NO_EVIDENCE' if len(values)==0 else None,formula_references=[])
        for height in [1.10,1.3566335069482636]:
            r=lo+.5;rho=math.sqrt(r*r-height*height);step=math.radians(.5)
            row['formula_references'].append(dict(assumed_h_m=height,slant_r_m=r,horizontal_rho_m=rho,
                slant_delta_r_m=r*rho/height*step,horizontal_delta_rho_m=(rho*rho+height*height)/height*step,
                legacy_code_r2_over_h=r*r/height*step,
                legacy_report_if_R_is_slant=(r*r+height*height)/height*step,
                qualification='MODEL_REFERENCE_NOT_COMPARABLE_DIRECTLY_TO_BUCKET_GAPS'))
        result.append(row)
    with np.load(old/'results/E1_MASK.npz') as z:
        count=z['count'];bc=z['band_count'];zmin=z['zmin'];original=z['state']
    n=np.array([-.4546594173329524,-.02722635715441169,.8902491447378991]);w=-1.3785
    xs=(np.arange(512)-256+.5)*.25;gx,gy=np.meshgrid(xs,xs,indexing='ij')
    plane=(w-n[0]*gx-n[1]*gy)/n[2]
    state=np.zeros((512,512),dtype='u1');has=count>0;gap=zmin-plane
    state[has&(bc==0)&(gap<=.30)]=1
    state[has&(bc==0)&(gap>.30)]=3
    state[has&(bc>0)&(bc<5)]=3
    state[has&(bc>=5)]=2
    obs=np.argwhere(has);x0,y0=obs.min(axis=0);x1,y1=obs.max(axis=0)
    crop=(slice(x0,x1+1),slice(y0,y1+1))
    before=[int((original[crop]==i).sum()) for i in range(5)]
    after=[int((state[crop]==i).sum()) for i in range(5)]
    assert before==[2529,622,153,8,0] and after==[2529,207,153,423,0]
    assert np.all((original==state)|((original==1)&(state==3)))
    with (p/'CORRECTED_MASK.npz').open('xb') as f:
        np.savez_compressed(f,state=state,count=count,band_count=bc,zmin=zmin,candidate_plane_z=plane)
    write(p/'CORRECTIONS.json',dict(spacing=result,mask=dict(before=before,after=after,
        changed_cells=int((state!=original).sum()),reference_plane_old_upshift_m=float(-2*w/n[2]),
        valid_rows=int(count.sum()),compatible_band_rows=int(bc.sum()),
        identity='UNKNOWN, GROUND_CONFIRMED empty; labels describe legacy prior compatibility only'),
        old_artifact_sha={str(q.relative_to(old)):sha(q) for q in old.rglob('*') if q.is_file()},
        OB09_protocol_max=200000,OB09_actual=201101,OB09_overage=1101))
    print(json.dumps(dict(mask_before=before,mask_after=after,pairs=len(gaps),bands=result)))

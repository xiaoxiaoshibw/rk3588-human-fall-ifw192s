"""Original TLS admission gates and independent scalar metrics, no new estimator gates."""
import math
import numpy as np
from pathlib import Path
from prepare import E,load,save
from diagnostics import Q,tls,svd,scalar_check,residual

catalog=load(E/'00_input_catalog.json')
results={}
for record in catalog['sessions']:
    local=Path(record['local']);report=load(local/'report.json');reproduction=load(E/'01_reproduction.json')['sessions'][record['sid']]
    with np.load(local/'domain.npz',allow_pickle=False) as d:
        points=d['source_points'].copy()
    anchor=Q.rotation(report['config']['pitch_deg'],report['config']['roll_deg'])[2]
    n,offset=tls(points,anchor);sn,sd=svd(points,anchor)
    values,vectors=np.linalg.eigh(np.cov((points-points.mean(axis=0)).T))
    tangent=(points-points.mean(axis=0))@vectors[:,1:]
    ratio=float(max(0.,values[1])/max(values[2],1e-30));extents=np.ptp(tangent,axis=0).tolist()
    pitch=math.degrees(math.atan2(-n[0],n[2]));roll=math.degrees(math.asin(float(np.clip(n[1],-1,1))))
    angle=math.degrees(math.acos(float(np.clip(n@sn,-1,1))))
    offset_gap=abs(offset-sd)
    base=reproduction['baseline'];reasons=[]
    if ratio<Q.PROFILE['min_lambda2_lambda3'] or min(extents)<Q.PROFILE['min_tangent_extent_m']:reasons.append('GL_DEGENERATE_DOMAIN')
    if abs(pitch)>Q.PROFILE['max_abs_pitch_deg'] or abs(roll)>Q.PROFILE['max_abs_roll_deg'] or offset<=0:reasons.append('GL_IMPLAUSIBLE_POSE')
    if base['full']['status']!='PASS':reasons.append('GL_FULL_DOMAIN_QUALITY')
    if any(x['status']!='PASS' for x in base['regions'].values()):reasons.append('GL_REGION_QUALITY')
    if any(h['full']['status']!='PASS' or any(x['status']!='PASS' for x in h['regions'].values()) for h in base['holdouts']):reasons.append('GL_HOLDOUT_QUALITY')
    if angle>Q.PROFILE['tls_svd_gap_max_deg'] or offset_gap>Q.PROFILE['tls_svd_offset_max_m']:reasons.append('GL_TLS_SVD_NUMERIC_MISMATCH')
    assert reasons==report['estimators']['tls']['reject_reasons'],record['sid']
    assert (not reasons)==report['estimators']['tls']['valid']
    for h,s in zip(base['holdouts'],reproduction['independent_scalar_holdouts']):
        assert h['ordinal']==s['ordinal']
        for i in range(1,5):
            assert abs(h['regions'][str(i)]['p95_m']-s['regions'][str(i)]['p95_m'])<1e-12
            assert abs(h['regions'][str(i)]['rms_m']-s['regions'][str(i)]['rms_m'])<1e-12
    results[record['sid']]=dict(valid=not reasons,reject_reasons=reasons,
        joint_geometry=dict(lambda2_lambda3=ratio,tangent_extents_m=extents),pitch_deg=pitch,roll_deg=roll,
        independent_SVD_angle_deg=angle,independent_SVD_offset_gap_m=offset_gap,
        fixed_scalar_holdout_metrics_match=True,current_profile=dict(Q.PROFILE))
save('01_gate_cross_checks.json',results)
print('ORIGINAL_TLS_GATES_AND_SCALAR_CHECKS_PASS',len(results))

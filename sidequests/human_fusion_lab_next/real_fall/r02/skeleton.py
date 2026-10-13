"""Supported body regions throughout the episode; not calibrated joints."""
import importlib.util
import json
import numpy as np
from paths import ROOT, OUT

OLD=ROOT/'docs/human_capture/evidence/2026-10-09_hrskeleton_offline_r1'
spec=importlib.util.spec_from_file_location('existing_sko_geometry',OLD/'skeleton.py')
G=importlib.util.module_from_spec(spec);spec.loader.exec_module(G)
PARAMS=json.loads((OLD/'prototype_params_v1.json').read_text(encoding='utf8'))
SLOTS=['TOP_REGION','UPPER_TORSO','CHEST','PELVIS','LOWER_CENTER',
       'UPPER_A','UPPER_B','OUTER_A','OUTER_B','LOWER_A','LOWER_B','END_A','END_B']
EDGES=[('TOP_REGION','UPPER_TORSO'),('UPPER_TORSO','CHEST'),('CHEST','PELVIS'),('PELVIS','LOWER_CENTER'),
       ('UPPER_TORSO','UPPER_A'),('UPPER_TORSO','UPPER_B'),('UPPER_A','OUTER_A'),('UPPER_B','OUTER_B'),
       ('PELVIS','LOWER_A'),('PELVIS','LOWER_B'),('LOWER_A','END_A'),('LOWER_B','END_B')]


def estimate(points, source_rows, previous_axis=None):
    p=np.asarray(points,dtype='f8').reshape(-1,3)
    nodes={k:G.unknown('INSUFFICIENT_SUPPORT') for k in SLOTS}
    if len(p)!=len(source_rows) or len(set(source_rows))!=len(source_rows):raise ValueError('source row binding')
    if len(p)<30 or not np.isfinite(p).all():return {'nodes':nodes,'axis':None,'reason':'LOW_OR_INVALID_SUPPORT'},None
    center=np.mean(p,axis=0);values,vectors=np.linalg.eigh(np.cov((p-center).T))
    span=np.ptp(p,axis=0)
    # ponytail: intrinsic body-axis regions support lying as well as upright.
    # Anatomical left/right, elbows, knees and head identity require human joint GT.
    upright=span[2]>1 and np.quantile(p[:,2],.9)>1.2 and span[2]>max(span[:2])
    if upright:axis=np.array([0.,0.,1.])
    else:
        if values[-1]<=1e-9 or values[-1]/max(values[-2],1e-9)<PARAMS['axis_eigen_ratio_min']:
            return {'nodes':nodes,'axis':None,'reason':'AMBIGUOUS_BODY_AXIS'},None
        axis=vectors[:,-1]
        if previous_axis is None:
            if axis[2]<0:axis=-axis
        elif np.dot(axis,previous_axis)<0:axis=-axis
    lateral=np.cross(axis,[1.,0.,0.])
    if np.linalg.norm(lateral)<.1:lateral=np.cross(axis,[0.,1.,0.])
    lateral/=np.linalg.norm(lateral)
    depth=np.cross(lateral,axis);basis=np.column_stack([lateral,depth,axis])
    local=(p-center)@basis
    lo,hi=np.quantile(local[:,2],[.02,.98])
    if hi-lo<.35:return {'nodes':nodes,'axis':axis.tolist(),'reason':'SHORT_BODY_SUPPORT'},axis
    fractions=(local[:,2]-lo)/(hi-lo)
    norm=G.normalize({'receipt':{'rows':source_rows},'global_rows':source_rows,'xyz':local.tolist(),'invalid_source_rows':[]},PARAMS)
    bands=[(.88,1.03),(.70,.88),(.52,.70),(.33,.52),(-.03,.33)]
    def node(name,ids):
        n=G.observe(norm,ids.tolist(),PARAMS)
        if n['valid']:
            n['xyz']=(np.array(n['xyz'])@basis.T+center).tolist()
            n['semantic_status']='UNVERIFIED_BODY_REGION'
            n['reason']='POINT_SUPPORTED_REGION_NOT_CALIBRATED_JOINT'
        nodes[name]=n
    for name,(low,high) in zip(SLOTS[:5],bands):node(name,np.flatnonzero((fractions>=low)&(fractions<high)))
    lateral_coordinate=local[:,0]
    for label,sign in [('A',-1),('B',1)]:
        branch=sign*lateral_coordinate>.08
        node('UPPER_'+label,np.flatnonzero(branch&(fractions>=.52)&(fractions<.88)))
        node('OUTER_'+label,np.flatnonzero((sign*lateral_coordinate>.20)&(fractions>=.33)&(fractions<.88)))
        node('LOWER_'+label,np.flatnonzero(branch&(fractions>=.12)&(fractions<.33)))
        node('END_'+label,np.flatnonzero(branch&(fractions>=-.03)&(fractions<.12)))
    for a,b in [('LOWER_A','LOWER_B'),('END_A','END_B')]:
        if nodes[a]['valid'] and nodes[b]['valid'] and np.linalg.norm(np.array(nodes[a]['xyz'])-np.array(nodes[b]['xyz']))<.10:
            nodes[a]=G.unknown('BRANCHES_NOT_SEPARATED');nodes[b]=G.unknown('BRANCHES_NOT_SEPARATED')
    return {'nodes':nodes,'axis':axis.tolist(),'reason':'SUPPORTED_GEOMETRY_ONLY',
            'upright_axis_anchor':bool(upright),'axis_verticality':float(abs(axis[2])),
            'head_foot_identity':'UNVERIFIED_PREVIOUS_AXIS_SIGN','left_right_identity':'UNKNOWN',
            'edges':[[a,b] for a,b in EDGES if nodes[a]['valid'] and nodes[b]['valid']]},axis


def build():
    sid='cap_20261013_094333';track=json.loads((OUT/(sid+'_tracking.json')).read_text(encoding='utf8'))
    m=json.loads((OUT/(sid+'_foreground.json')).read_text(encoding='utf8'))
    p=np.memmap(OUT/(sid+'_foreground.bin'),dtype='<f4',mode='r').reshape(-1,4)
    rows=np.memmap(OUT/(sid+'_source_rows.bin'),dtype='<u4',mode='r')
    previous=None;last=None;counts=[]
    for r,f in zip(track['rows'],m['frames']):
        ids=r['source_fg_indices'];cloud=p[f['offset']:f['offset']+f['count'],:3][ids]
        bound=rows[f['offset']:f['offset']+f['count']][ids].tolist()
        if last is not None and r['t']-last>.5:previous=None
        r['skeleton'],axis=estimate(cloud,bound,previous)
        if axis is not None:previous=axis;last=r['t']
        if not r['observed']:previous=None
        counts.append(sum(n['valid'] for n in r['skeleton']['nodes'].values()))
    track['skeleton_slots']=SLOTS;track['skeleton_contract']='point-supported regions; anatomical joints/arms/left-right not calibrated'
    with (OUT/'process.json').open('x',encoding='utf8') as f:json.dump(track,f,ensure_ascii=False,allow_nan=False,separators=(',',':'))
    print('Skeleton frames',len(counts),'valid node min/max',min(counts),max(counts),'full13',sum(n==13 for n in counts))


if __name__=='__main__':build()

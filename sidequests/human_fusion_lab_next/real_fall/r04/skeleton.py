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


def estimate(points, source_rows, previous_axis=None, previous_lateral=None, dt=.1, reference_age=0.):
    p=np.asarray(points,dtype='f8').reshape(-1,3)
    nodes={k:G.unknown('INSUFFICIENT_SUPPORT') for k in SLOTS}
    if len(p)!=len(source_rows) or len(set(source_rows))!=len(source_rows):raise ValueError('source row binding')
    if len(p)<30 or not np.isfinite(p).all():return {'nodes':nodes,'axis':None,'reason':'LOW_OR_INVALID_SUPPORT'},None
    center=np.mean(p,axis=0);values,vectors=np.linalg.eigh(np.cov((p-center).T))
    span=np.ptp(p,axis=0)
    # ponytail: intrinsic body-axis regions support lying as well as upright.
    # Anatomical left/right, elbows, knees and head identity require human joint GT.
    upright=span[2]>1 and np.quantile(p[:,2],.9)>1.2 and span[2]>max(span[:2])
    weak=values[-1]<=1e-9 or values[-1]/max(values[-2],1e-9)<PARAMS['axis_eigen_ratio_min']
    measured_axis=None if weak else vectors[:,-1].copy()
    if weak:
        if previous_axis is None or reference_age>.25:
            return {'nodes':nodes,'axis':None,'reason':'AMBIGUOUS_BODY_AXIS'},None
        axis=np.asarray(previous_axis).copy()
    else:
        axis=measured_axis.copy()
        if previous_axis is None:
            if axis[2]<0:axis=-axis
        else:
            if np.dot(axis,previous_axis)<0:axis=-axis
            measured_axis=axis.copy()
            alpha=dt/(.12+dt)
            axis=(1-alpha)*np.asarray(previous_axis)+alpha*axis
            axis/=np.linalg.norm(axis)
    if previous_lateral is not None:
        lateral=np.asarray(previous_lateral).copy()-np.dot(previous_lateral,axis)*axis
    else:lateral=np.cross(axis,[1.,0.,0.])
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
            'basis_lateral':lateral.tolist(),'axis_measured':None if measured_axis is None else measured_axis.tolist(),'axis_prior_reference':bool(weak),'upright_axis_anchor':bool(upright),'axis_verticality':float(abs(axis[2])),
            'head_foot_identity':'UNVERIFIED_PREVIOUS_AXIS_SIGN','left_right_identity':'UNKNOWN',
            'edges':[[a,b] for a,b in EDGES if nodes[a]['valid'] and nodes[b]['valid']]},axis


def build():
    sid='cap_20261013_094333';track=json.loads((OUT/(sid+'_tracking.json')).read_text(encoding='utf8'))
    m=json.loads((OUT/(sid+'_foreground.json')).read_text(encoding='utf8'))
    p=np.memmap(OUT/(sid+'_foreground.bin'),dtype='<f4',mode='r').reshape(-1,4)
    rows=np.memmap(OUT/(sid+'_source_rows.bin'),dtype='<u4',mode='r')
    previous=None;lateral=None;last=None;axis_measured_time=None;counts=[];display_history={};edge_reference={}
    for r,f in zip(track['rows'],m['frames']):
        ids=r['source_fg_indices'];cloud=p[f['offset']:f['offset']+f['count'],:3][ids]
        bound=rows[f['offset']:f['offset']+f['count']][ids].tolist()
        if last is not None and r['t']-last>.5:previous=None
        r['skeleton'],axis=estimate(cloud,bound,previous,lateral,dt=.1 if last is None else r['t']-last,reference_age=0. if axis_measured_time is None else r['t']-axis_measured_time)
        if axis is not None:
            previous=axis;lateral=r['skeleton'].get('basis_lateral');
            if not r['skeleton'].get('axis_prior_reference'):axis_measured_time=r['t']
        if last is not None and r['t']-last>.5:display_history={};edge_reference={}
        stabilize_display(r['skeleton'],r['t'],display_history,edge_reference)
        last=r['t']
        if not r['observed']:previous=None
        counts.append(sum(n['valid'] for n in r['skeleton']['nodes'].values()))
    track['skeleton_slots']=SLOTS;track['skeleton_contract']='point-supported regions; anatomical joints/arms/left-right not calibrated'
    with (OUT/'process.json').open('x',encoding='utf8') as f:json.dump(track,f,ensure_ascii=False,allow_nan=False,separators=(',',':'))
    print('Skeleton frames',len(counts),'valid node min/max',min(counts),max(counts),'full13',sum(n==13 for n in counts))


def stabilize_display(skeleton, t, history, reference):
    # Display state never becomes measured support or fall evidence.
    for key,node in skeleton['nodes'].items():
        old=history.get(key)
        if node['valid']:
            measured=np.array(node['xyz'])
            if old and 0<t-old['t']<=.25:
                alpha=(t-old['t'])/(.08+t-old['t'])
                display=old['xyz']+alpha*(measured-old['xyz'])
            else:display=measured
            node.update(display_xyz=display.tolist(),display_predicted=False,display_opacity=1.)
            history[key]={'xyz':display,'t':t}
        elif old and 0<=t-old['t']<=.20:
            node.update(display_xyz=old['xyz'].tolist(),display_predicted=True,display_opacity=1-(t-old['t'])/.20)
        else:node.update(display_xyz=None,display_predicted=False,display_opacity=0.)
    edges=[];rejected=[]
    for a,b in skeleton.get('edges',[]):
        n,m=skeleton['nodes'][a],skeleton['nodes'][b]
        length=float(np.linalg.norm(np.array(n['xyz'])-m['xyz']))
        prior=reference.get((a,b))
        if prior is None and length>.03:reference[(a,b)]=length
        if prior is not None and not .5<=length/prior<=1.8:rejected.append([a,b])
        else:edges.append([a,b])
    skeleton['display_edges']=edges
    skeleton['unstable_connections']=rejected


if __name__=='__main__':build()

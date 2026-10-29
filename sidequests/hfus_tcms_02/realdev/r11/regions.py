"""Single registered principal-plane region variant for one RAW ROI contract."""
import numpy as np
from common import SK

BOUNDS=np.array([[.75,2.4],[.9,1.65],[-.4,1.85]])

def estimate(points, source_rows, *, coordinate_version, session_id):
    if coordinate_version!='RAW/innolidar' or session_id not in ('cap_20261018_110029','SYNTHETIC_IN_CONTRACT'):
        raise ValueError('unsupported coordinate/session contract')
    p=np.asarray(points,dtype='f8').reshape(-1,3)
    if len(p)!=len(source_rows) or len(set(source_rows))!=len(source_rows):raise ValueError('source row binding')
    # Canonical source-row order keeps reduction/quantile boundary behavior
    # invariant to input iteration order; this changes no geometric threshold.
    order=np.argsort(np.asarray(source_rows),kind='stable')
    p=p[order];source_rows=[source_rows[i] for i in order]
    nodes={k:SK.G.unknown('INSUFFICIENT_SUPPORT') for k in SK.SLOTS}
    def reject(reason):
        return dict(nodes={k:SK.G.unknown(reason) for k in SK.SLOTS},axis=None,basis_lateral=None,reason=reason,diagnostics=dict(input_points=len(p))),None
    if len(p)<30 or not np.isfinite(p).all():return reject('LOW_OR_INVALID_SUPPORT')
    if np.any(p<BOUNDS[:,0]) or np.any(p>BOUNDS[:,1]):raise ValueError('outside registered RAW ROI')
    center=np.mean(p,0);values,vectors=np.linalg.eigh(np.cov((p-center).T))
    if values[-1]<=1e-9 or values[-1]/max(values[-2],1e-9)<1.2:return reject('AMBIGUOUS_BODY_AXIS')
    if values[-2]/max(values[0],1e-9)<1.2:return reject('AMBIGUOUS_TRANSVERSE_PLANE')
    axis=vectors[:,-1].copy()
    if axis[2]<0:axis=-axis
    if abs(axis[2])<.6:return reject('OUTSIDE_UPRIGHT_RAW_CONTRACT')
    lateral=vectors[:,-2].copy()
    if lateral[np.argmax(np.abs(lateral))]<0:lateral=-lateral
    depth=np.cross(lateral,axis);basis=np.column_stack([lateral,depth,axis]);local=(p-center)@basis
    lo,hi=np.quantile(local[:,2],[.02,.98])
    if hi-lo<.35:return reject('SHORT_BODY_SUPPORT')
    frac=(local[:,2]-lo)/(hi-lo)
    mid=(frac>=.33)&(frac<.70)
    if mid.sum()<6:return reject('LOW_CORE_ANCHOR_SUPPORT')
    core=float(np.median(local[mid,0]));transverse=local[:,0]-core
    norm=SK.G.normalize(dict(receipt=dict(rows=source_rows),global_rows=source_rows,xyz=local.tolist(),invalid_source_rows=[]),SK.PARAMS)
    partitions={}
    def node(name,mask):
        ids=np.flatnonzero(mask)
        partitions[name]=dict(selected_raw_support_n=len(ids),span_local_m=None if not len(ids) else np.ptp(local[ids],0).tolist(),selected_rows=[source_rows[i] for i in ids])
        n=SK.G.observe(norm,ids.tolist(),SK.PARAMS)
        if n['valid']:
            raw=np.median(p[ids],0)
            n.update(xyz=raw.tolist(),xyz_local=((raw-center)@basis).tolist(),semantic_status='UNVERIFIED_BODY_REGION',reason='POINT_SUPPORTED_PRINCIPAL_PLANE_REGION_NOT_JOINT')
        nodes[name]=n
    for name,(low,high) in zip(SK.SLOTS[:5],[(.88,1.03),(.70,.88),(.52,.70),(.33,.52),(-.03,.33)]):
        node(name,(frac>=low)&(frac<high)&(np.abs(transverse)<=.18))
    for label,sign in [('A',-1),('B',1)]:
        side=sign*transverse>.18
        node('UPPER_'+label,side&(frac>=.52)&(frac<.88))
        eligible=side&(frac>=.33)&(frac<.88)
        distal=float(np.quantile(sign*transverse[eligible],.75)) if eligible.any() else float('inf')
        node('OUTER_'+label,eligible&(sign*transverse>=distal))
        node('LOWER_'+label,side&(frac>=.12)&(frac<.33))
        node('END_'+label,side&(frac>=-.03)&(frac<.12))
    for a,b in [('LOWER_A','LOWER_B'),('END_A','END_B')]:
        if nodes[a]['valid'] and nodes[b]['valid'] and np.linalg.norm(np.asarray(nodes[a]['xyz'])-nodes[b]['xyz'])<.1:
            nodes[a]=SK.G.unknown('BRANCHES_NOT_SEPARATED');nodes[b]=SK.G.unknown('BRANCHES_NOT_SEPARATED')
    out=dict(nodes=nodes,axis=axis.tolist(),basis_lateral=lateral.tolist(),reason='PRINCIPAL_PLANE_POINT_SUPPORTED_REGIONS_ONLY',edges=[[a,b] for a,b in SK.EDGES if nodes[a]['valid'] and nodes[b]['valid']],diagnostics=dict(eigenvalues=values.tolist(),core_transverse=core,partitions=partitions,coordinate='RAW/innolidar',session_contract=session_id))
    return out,axis

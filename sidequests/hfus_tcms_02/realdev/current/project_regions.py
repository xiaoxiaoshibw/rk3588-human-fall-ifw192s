"""Active project regions: causal sign identity and optional disjoint branch support.
Frozen S07F reference remains unchanged; no smoothing or fabricated nodes.
"""
import numpy as np
from project_dependencies import SK


class OrientationAmbiguous(ValueError):
    pass


def orient_lateral(lateral, previous=None):
    """Resolve only the +/- eigenvector ambiguity, never smooth or predict XYZ."""
    v=np.asarray(lateral,dtype=float)
    if v.shape!=(3,) or not np.isfinite(v).all() or abs(float(np.linalg.norm(v))-1)>1e-6:
        raise ValueError('unit finite lateral vector required')
    if previous is None:return v.copy(),False
    ref=np.asarray(previous,dtype=float)
    if ref.shape!=(3,) or not np.isfinite(ref).all() or abs(float(np.linalg.norm(ref))-1)>1e-6:
        raise ValueError('unit finite previous lateral required')
    dot=float(np.dot(v,ref))
    if abs(dot)<=1e-12:
        raise OrientationAmbiguous('orthogonal lateral reference cannot resolve sign')
    return (-v if dot<0 else v).copy(),dot<0

BOUNDS=np.array([[.75,2.4],[.9,1.65],[-.4,1.85]])

def estimate(points, source_rows, *, coordinate_version, session_id, previous_lateral=None,
             partition_branch=False, region_contract='legacy_raw_roi', ground_up=None):
    if coordinate_version!='RAW/innolidar' or not isinstance(session_id,str) or not session_id:
        raise ValueError('unsupported coordinate/session contract')
    if region_contract not in ('legacy_raw_roi','target_ground_v1'):
        raise ValueError('unsupported region contract')
    up=np.array([0.,0.,1.])
    if region_contract=='target_ground_v1':
        up=np.asarray(ground_up,dtype=float)
        if up.shape!=(3,) or not np.isfinite(up).all() or abs(float(np.linalg.norm(up))-1)>1e-6:
            raise ValueError('target region contract requires bound unit ground normal')
    p=np.asarray(points,dtype='f8').reshape(-1,3)
    if len(p)!=len(source_rows) or len(set(source_rows))!=len(source_rows):raise ValueError('source row binding')
    # Canonical source-row order keeps reduction/quantile boundary behavior
    # invariant to input iteration order; this changes no geometric threshold.
    order=np.argsort(np.asarray(source_rows),kind='stable')
    p=p[order];source_rows=[source_rows[i] for i in order]
    nodes={k:SK.G.unknown('INSUFFICIENT_SUPPORT') for k in SK.SLOTS}
    def reject(reason):
        return dict(nodes={k:SK.G.unknown(reason) for k in SK.SLOTS},axis=None,basis_lateral=None,reason=reason,diagnostics=dict(input_points=len(p),region_contract=region_contract)),None
    if len(p)<30 or not np.isfinite(p).all():return reject('LOW_OR_INVALID_SUPPORT')
    if region_contract=='legacy_raw_roi' and (np.any(p<BOUNDS[:,0]) or np.any(p>BOUNDS[:,1])):
        return reject('OUTSIDE_REGION_DEVELOPMENT_DOMAIN')
    center=np.mean(p,0);values,vectors=np.linalg.eigh(np.cov((p-center).T))
    if values[-1]<=1e-9 or values[-1]/max(values[-2],1e-9)<1.2:return reject('AMBIGUOUS_BODY_AXIS')
    if values[-2]/max(values[0],1e-9)<1.2:return reject('AMBIGUOUS_TRANSVERSE_PLANE')
    axis=vectors[:,-1].copy()
    if np.dot(axis,up)<0:axis=-axis
    if abs(float(np.dot(axis,up)))<.6:
        return reject('OUTSIDE_UPRIGHT_RAW_CONTRACT' if region_contract=='legacy_raw_roi' else 'OUTSIDE_UPRIGHT_GROUND_CONTRACT')
    lateral=vectors[:,-2].copy()
    if lateral[np.argmax(np.abs(lateral))]<0:lateral=-lateral
    try:lateral, sign_flipped = orient_lateral(lateral, previous_lateral)
    except OrientationAmbiguous:return reject('AMBIGUOUS_LATERAL_ORIENTATION')
    depth=np.cross(lateral,axis);basis=np.column_stack([lateral,depth,axis]);local=(p-center)@basis
    lo,hi=np.quantile(local[:,2],[.02,.98])
    if hi-lo<.35:return reject('SHORT_BODY_SUPPORT')
    frac=(local[:,2]-lo)/(hi-lo)
    mid=(frac>=.33)&(frac<.70)
    if mid.sum()<6:return reject('LOW_CORE_ANCHOR_SUPPORT')
    core=float(np.median(local[mid,0]));transverse=local[:,0]-core
    norm=SK.G.normalize(dict(receipt=dict(rows=source_rows),global_rows=source_rows,xyz=local,invalid_source_rows=[]),SK.PARAMS)
    # 冻结 normalize 返回列表；只转换一次，供 13 个区域共用。
    norm['xyz']=np.asarray(norm['xyz'],dtype=np.float64)
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
        # S07F: branch-band-consistent single support; band now matches UPPER (was [.33,.88)).
        eligible=side&(frac>=.52)&(frac<.88)
        distal=float(np.quantile(sign*transverse[eligible],.75)) if eligible.any() else float('inf')
        outer=eligible&(sign*transverse>=distal)
        node('UPPER_'+label,eligible&~outer if partition_branch else eligible)
        node('OUTER_'+label,outer)
        node('LOWER_'+label,side&(frac>=.12)&(frac<.33))
        node('END_'+label,side&(frac>=-.03)&(frac<.12))
    for a,b in [('LOWER_A','LOWER_B'),('END_A','END_B')]:
        if nodes[a]['valid'] and nodes[b]['valid'] and np.linalg.norm(np.asarray(nodes[a]['xyz'])-np.asarray(nodes[b]['xyz']))<.1:
            nodes[a]=SK.G.unknown('BRANCHES_NOT_SEPARATED');nodes[b]=SK.G.unknown('BRANCHES_NOT_SEPARATED')
    out=dict(nodes=nodes,axis=axis.tolist(),basis_lateral=lateral.tolist(),reason='PRINCIPAL_PLANE_POINT_SUPPORTED_REGIONS_ONLY',edges=[[a,b] for a,b in SK.EDGES if nodes[a]['valid'] and nodes[b]['valid']],diagnostics=dict(orientation_sign_flipped=sign_flipped,orientation_reference_used=previous_lateral is not None,branch_partition=partition_branch,eigenvalues=values.tolist(),core_transverse=core,partitions=partitions,coordinate='RAW/innolidar',session_contract=session_id,region_contract=region_contract,ground_up_raw=up.tolist()))
    return out,axis

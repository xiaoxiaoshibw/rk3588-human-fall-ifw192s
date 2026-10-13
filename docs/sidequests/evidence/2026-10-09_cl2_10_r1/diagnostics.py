"""Generic frozen-domain diagnostics; no production candidate or correction output.

ponytail: stdlib+NumPy, original TLS and quality implementation reused.
All alternatives are experiments, never an effective TLS or export.
"""
import math
import mmap
import sys
from pathlib import Path
import numpy as np
from prepare import E,load,save,sha

sys.path[:0]=[str(E/'candidate'),str(E/'frozen')]
from leveling_estimators import ESTIMATORS
import leveling_quality as Q

def residual(points,normal,offset):
    return np.einsum('ij,j->i',points,normal)+offset

def orient(normal,offset,anchor):
    length=float(np.linalg.norm(normal))
    normal,offset=normal/length,offset/length
    if normal@anchor<0:normal,offset=-normal,-offset
    return normal,float(offset)

def tls(points,anchor):
    return orient(*ESTIMATORS['tls'](points),anchor)

def svd(points,anchor):
    center=points.mean(axis=0)
    _,_,vectors=np.linalg.svd(points-center,full_matrices=False)
    normal=vectors[-1]
    return orient(normal,-float(normal@center),anchor)

def weighted_tls(points,weights,anchor):
    # Experiment only: positive weights preserve every FIT row; no gate/estimator replacement.
    assert len(weights)==len(points) and np.all(weights>0) and np.isfinite(weights).all()
    weights=weights/weights.sum()
    center=np.sum(points*weights[:,None],axis=0)
    centered=points-center
    _,vectors=np.linalg.eigh((centered*weights[:,None]).T@centered)
    normal=vectors[:,0]
    return orient(normal,-float(normal@center),anchor)

def metrics(points,normal,offset):
    original=Q.statistics(points,normal,offset)
    if not len(points):return original
    r=residual(points,normal,offset)
    return dict(original,signed_mean_m=float(r.mean()),signed_min_m=float(r.min()),signed_max_m=float(r.max()),
       p99_m=float(np.percentile(np.abs(r),99)),max_abs_m=float(np.abs(r).max()),
       positive_tail=int((r>Q.PROFILE['p95_max_m']).sum()),negative_tail=int((r<-Q.PROFILE['p95_max_m']).sum()))

def scalar_check(points,normal,offset):
    values=[math.fsum(float(q[k])*float(normal[k]) for k in range(3))+float(offset) for q in points]
    ordered=sorted(abs(v) for v in values)
    rank=.95*(len(ordered)-1);index=int(math.floor(rank));fraction=rank-index
    p95=ordered[index]*(1-fraction)+ordered[min(index+1,len(ordered)-1)]*fraction
    return dict(count=len(values),p95_m=p95,rank_zero_based=rank,lower=ordered[index],
                upper=ordered[min(index+1,len(ordered)-1)],rms_m=math.sqrt(math.fsum(v*v for v in values)/len(values)),
                signed_mean_m=math.fsum(values)/len(values),max_abs_m=max(ordered))

def corr(x,y):
    a=x-x.mean();b=y-y.mean()
    scale=float(np.linalg.norm(a)*np.linalg.norm(b))
    return float(a@b/scale) if scale else None

def geometry(points,normal,offset,initial):
    display=points@initial.T;r=residual(points,normal,offset)
    center=points.mean(axis=0)
    values,vectors=np.linalg.eigh(np.cov((points-center).T))
    tangent=(points-center)@vectors[:,1:]
    xy=display[:,:2];xy0=xy.mean(axis=0)
    gradient=np.linalg.lstsq(np.column_stack([xy-xy0,np.ones(len(xy))]),r,rcond=None)[0]
    return dict(count=len(points),source_center_m=center.tolist(),display_extent_m=np.ptp(display,axis=0).tolist(),
       tangent_extents_m=np.ptp(tangent,axis=0).tolist(),covariance_eigenvalues_m2=values.tolist(),
       lambda2_lambda3=float(max(0.,values[1])/max(values[2],1e-30)),
       corr_x=corr(xy[:,0],r),corr_y=corr(xy[:,1],r),
       gradient_x_m_per_m=float(gradient[0]),gradient_y_m_per_m=float(gradient[1]),
       residual_direction='unit plane normal in source coordinates',normal_source=normal.tolist())

def evaluate(points,codes,held,normal,offset):
    return dict(normal_source=normal.tolist(),offset_source_m=offset,full=metrics(points,normal,offset),
      regions={str(i):metrics(points[codes==i],normal,offset) for i in range(1,5)},
      holdouts=[dict(ordinal=h['ordinal'],full=metrics(h['points'],normal,offset),
        regions={str(i):metrics(h['points'][h['regions']==i],normal,offset) for i in range(1,5)}) for h in held])

def assert_history(actual,expected):
    for key in ['count','rms_m','p95_m','support_ratio','median_signed_m','status']:
        if isinstance(expected[key],float):assert abs(actual[key]-expected[key])<1e-12,(key,actual[key],expected[key])
        else:assert actual[key]==expected[key],(key,actual[key],expected[key])

def decode_and_verify(record):
    local=Path(record['local']);report=load(local/'report.json');meta=load(local/'meta.json')
    for name,key in [('meta.json','meta_sha256'),('points.bin','bin_sha256')]:
        assert sha(record['raw'][name])==report['source'][key],record['raw'][name]
    with np.load(local/'domain.npz',allow_pickle=False) as archive:
        frozen={key:archive[key].copy() for key in archive.files}
    initial=Q.rotation(report['config']['pitch_deg'],report['config']['roll_deg'])
    held_indices={(len(meta['frames'])-1)//3,2*(len(meta['frames'])-1)//3,len(meta['frames'])-1}
    fit=[];held=[];observations=[];invalid=0
    with Path(record['raw']['points.bin']).open('rb') as stream:
        with mmap.mmap(stream.fileno(),0,access=mmap.ACCESS_READ) as raw:
            assert len(raw)==meta['total_points']*28
            xyz=np.ndarray((meta['total_points'],3),dtype='<f4',buffer=raw,strides=(28,4))
            ring=np.ndarray((meta['total_points'],),dtype='<u2',buffer=raw,offset=16,strides=(28,))
            intensity=np.ndarray((meta['total_points'],),dtype='<f4',buffer=raw,offset=12,strides=(28,))
            end=0
            for ordinal,frame in enumerate(meta['frames']):
                lo=frame['offset_points'];hi=lo+frame['count_points'];assert lo==end;end=hi
                q=xyz[lo:hi].astype('f8')
                valid=np.isfinite(q).all(axis=1)&np.any(q!=0,axis=1)
                invalid+=int((~valid).sum());q=q[valid]
                rows=np.arange(lo,hi,dtype='i8')[valid]
                display=q@initial.T;membership=np.zeros(len(q),dtype='u1')
                for i,(xl,xh,yl,yh) in enumerate(report['config']['regions'],1):
                    mask=(display[:,0]>=xl)&(display[:,0]<xh)&(display[:,1]>=yl)&(display[:,1]<yh)
                    assert not membership[mask].any();membership[mask]=i
                keep=membership>0;q=q[keep];rows=rows[keep];membership=membership[keep]
                row=dict(ordinal=ordinal,seq=frame['seq'],points=q,rows=rows,regions=membership,
                         rings=ring[rows].copy(),intensity=intensity[rows].copy())
                observations.append(row)
                (held if ordinal in held_indices else fit).append(row)
            assert end==meta['total_points']
            del xyz,ring,intensity
    points=np.concatenate([x['points'] for x in fit]);codes=np.concatenate([x['regions'] for x in fit])
    ordinals=np.concatenate([np.full(len(x['points']),x['ordinal'],dtype='i8') for x in fit])
    rebuilt=dict(source_points=points,source_rows=np.concatenate([x['rows'] for x in fit]),region_codes=codes,
       frame_ordinals=ordinals,holdout_rows=np.concatenate([x['rows'] for x in held]),
       holdout_regions=np.concatenate([x['regions'] for x in held]),
       holdout_ordinals=np.concatenate([np.full(len(x['points']),x['ordinal'],dtype='i8') for x in held]))
    assert set(frozen)==set(rebuilt)
    for name in frozen:assert np.array_equal(frozen[name],rebuilt[name]),(record['sid'],name)
    assert not np.intersect1d(rebuilt['source_rows'],rebuilt['holdout_rows']).size
    return report,meta,initial,points,codes,ordinals,held,observations,invalid

def channel_description(observations,normal,offset,initial,region):
    points=np.concatenate([h['points'][h['regions']==region] for h in observations])
    rings=np.concatenate([h['rings'][h['regions']==region] for h in observations])
    intensity=np.concatenate([h['intensity'][h['regions']==region] for h in observations])
    display=points@initial.T;r=residual(points,normal,offset)
    cells=np.floor(display[:,:2]/.05).astype('i4')
    unique,inverse=np.unique(cells,axis=0,return_inverse=True)
    coverage=[dict(key=k.tolist(),count=int((inverse==i).sum()),
              ring_count=int(len(np.unique(rings[inverse==i])))) for i,k in enumerate(unique)]
    rows=[]
    for value in np.unique(rings):
        mask=rings==value;rr=r[mask];xy=display[mask,:2]
        rows.append(dict(ring=int(value),count=int(mask.sum()),signed_mean_m=float(rr.mean()),
           p95_m=float(np.percentile(np.abs(rr),95)),tail_count=int((np.abs(rr)>.05).sum()),
           display_xy_min_m=xy.min(axis=0).tolist(),display_xy_max_m=xy.max(axis=0).tolist()))
    finite=np.isfinite(intensity)
    return dict(count=len(points),ring_groups=rows,xy5cm_cells=coverage,
        fraction_points_in_multiring_cells=float(sum(x['count'] for x in coverage if x['ring_count']>1)/len(points)),
        finite_intensity_count=int(finite.sum()),corr_intensity_residual=corr(intensity[finite],r[finite]) if finite.sum()>1 else None,
        causal_status='Observational only: ring/intensity and XY/range/incidence/surface identity are confounded; no device bias calibration.')

def run():
    catalog=load(E/'00_input_catalog.json');baseline=load(E/'00_baseline.json')
    # Guard every input/core asset before using them, even if outside context is dirty.
    for path,digest in baseline['guards'].items():assert sha(path)==digest,path
    all_results={};reproduction={};target_frames=[];target_channels={}
    for record in catalog['sessions']:
        report,meta,initial,points,codes,ordinals,held,observations,invalid=decode_and_verify(record)
        anchor=initial[2];normal,offset=tls(points,anchor);sn,sd=svd(points,anchor)
        original=report['estimators']['tls'];base=evaluate(points,codes,held,normal,offset)
        assert np.max(np.abs(normal-np.array(original['normal_source'])))<1e-12
        assert abs(offset-original['offset_source_m'])<1e-12
        assert_history(base['full'],original['full'])
        for i in range(1,5):assert_history(base['regions'][str(i)],original['regions'][str(i)])
        for actual,expected in zip(base['holdouts'],original['holdouts']):
            assert actual['ordinal']==expected['ordinal'];assert_history(actual['full'],expected['full'])
            for i in range(1,5):assert_history(actual['regions'][str(i)],expected['regions'][str(i)])
        scalar=[dict(ordinal=h['ordinal'],regions={str(i):scalar_check(h['points'][h['regions']==i],normal,offset)
                     for i in range(1,5)}) for h in held]
        svd_difference=float(max(np.abs(residual(points,normal,offset)-residual(points,sn,sd))))
        geometry_fit={str(i):geometry(points[codes==i],normal,offset,initial) for i in range(1,5)}
        for i in range(1,5):geometry_fit[str(i)]['fit_share']=float(np.mean(codes==i))
        variants={};weights=np.empty(len(points))
        for i in range(1,5):weights[codes==i]=1./int((codes==i).sum())
        wn,wd=weighted_tls(points,weights,anchor);variants['D_ROI_EQUAL']=evaluate(points,codes,held,wn,wd)
        frame_ids,counts=np.unique(ordinals,return_counts=True)
        weights=1./counts[np.searchsorted(frame_ids,ordinals)]
        fn,fd=weighted_tls(points,weights,anchor);variants['D_FRAME_EQUAL']=evaluate(points,codes,held,fn,fd)
        for value in variants.values():
            # Raw TLS minimizes unweighted full FIT orthogonal squared error.
            assert value['full']['rms_m']>=base['full']['rms_m']-1e-12
            value['eligibility']='DIAGNOSTIC_ONLY: weighted covariance is not current raw TLS/SVD contract'
            value['all_fit_rows_retained']=True
            value['holdout_in_fit']=False
        local_planes={};local_holdouts=[]
        for i in range(1,5):
            nn,dd=tls(points[codes==i],anchor)
            angle=math.degrees(math.acos(float(np.clip(nn@normal,-1,1))))
            local_planes[str(i)]=dict(normal_source=nn.tolist(),offset_source_m=dd,angle_to_common_deg=angle,
                                      fit=metrics(points[codes==i],nn,dd))
        for h in held:
            local_holdouts.append(dict(ordinal=h['ordinal'],regions={str(i):metrics(h['points'][h['regions']==i],
               np.array(local_planes[str(i)]['normal_source']),local_planes[str(i)]['offset_source_m']) for i in range(1,5)}))
        variants['C_LOCAL_PLANES']=dict(planes=local_planes,holdouts=local_holdouts,
           eligibility='DIAGNOSTIC_ONLY: four distinct planes cannot constitute one rigid TLS transform',
           all_fit_rows_retained=True,holdout_in_fit=False)
        rigid=[];delta=np.array([.1,-.2,.3])
        for pitch,roll in [(1.,0.),(-1.,0.),(0.,1.),(0.,-1.)]:
            S=Q.rotation(pitch,roll);rn=S@normal;rd=offset-float(rn@delta)
            q=points@S.T+delta
            difference=float(np.max(np.abs(residual(q,rn,rd)-residual(points,normal,offset))))
            assert difference<1e-12
            rigid.append(dict(pitch_deg=pitch,roll_deg=roll,translation_m=delta.tolist(),max_residual_difference_m=difference))
        all_results[record['sid']]=dict(original_TLS_valid=original['valid'],original_recommended=report['recommended'],
           baseline=base,variants=variants,independent_SVD_max_FIT_residual_difference_m=svd_difference,
           rigid_coordinate_controls=rigid,fit_holdout_disjoint=True)
        reproduction[record['sid']]=dict(all_seven_domain_arrays_exact=True,invalid_raw_xyz_excluded_by_original_contract=invalid,
           original_ROI=report['config']['regions'],config=report['config'],frozen_TLS=original,
           baseline=base,geometry_fit=geometry_fit,independent_scalar_holdouts=scalar,
           fixed_holdout_ordinals=[h['ordinal'] for h in held],source=report['source'])
        if record['sid']==catalog['target']:
            for h in observations:
                target_frames.append(dict(ordinal=h['ordinal'],seq=h['seq'],role='HOLDOUT' if h['ordinal'] in {x['ordinal'] for x in held} else 'FIT',
                  regions={str(i):dict(metrics(h['points'][h['regions']==i],normal,offset),
                  geometry=geometry(h['points'][h['regions']==i],normal,offset,initial)) for i in range(1,5)}))
            target_channels={str(i):channel_description(observations,normal,offset,initial,i) for i in range(1,5)}
        print('REPRODUCED',record['sid'],len(points),original['valid'],
              [(h['ordinal'],h['regions']['2']['p95_m']) for h in base['holdouts']],flush=True)
    save('01_reproduction.json',dict(sessions=reproduction,target_frames=target_frames,
       metric_profile=dict(Q.PROFILE),runtime_selector_sha256=sha(E/'candidate/floor_sheet.py'),
       geometry_truth='UNKNOWN; nominal angle/reference height not verified physical GT'))
    save('01_channel_diagnostics.json',target_channels)
    save('02_shadow_ab_results.json',dict(kind='PREREGISTERED_DIAGNOSTICS_NOT_A_REPAIR',sessions=all_results,
       plane_or_point_changes_exported=False,safety_profile=dict(Q.PROFILE),
       target='cap_20261009_121647',TLS_status='BLOCKED',physical_root_cause='UNKNOWN',
       repair_candidate_implemented=False,plan_sha256=sha(E/'00_EXPERIMENT_PLAN.md')))
    print('ALL_DIAGNOSTICS_COMPLETE',len(all_results),flush=True)

if __name__=='__main__':run()

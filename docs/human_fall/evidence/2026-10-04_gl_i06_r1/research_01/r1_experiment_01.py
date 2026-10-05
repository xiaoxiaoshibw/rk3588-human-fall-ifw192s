"""Fixed-sample K study; per-case immutable ledger, final holdout separate."""
import argparse
import ctypes
import json
import itertools
import platform
import sys
import time
from pathlib import Path
import numpy as np
from r0_01 import HERE, ROOT, KINDS, SEEDS, digest, scene, settings, quality, plane_error, real_inputs, gd, g, write_new
from refinement_02 import run_variant, validate_packet


def compact_new(path,value):
    if path.parent.resolve()!=HERE or path.exists() or path.is_symlink():raise ValueError('new output required')
    with path.open('x',encoding='utf-8') as f:json.dump(value,f,allow_nan=False,separators=(',',':'))


def brief(v,points,regions,s,synthetic):
    w=v['W']
    best=max(w,key=lambda x:x['support_count']) if w else None
    holds=[]
    if best:
        for r in regions:
            holds.append(dict(region_id=r['region_id'],frame_group=r['frame_group'],
                         source_xyz_bounds=g._region(points[r['indices']]),
                         stats=gd.residual_stats(points[r['indices']],best['normal'],best['offset_m'])))
    return dict(variant_id=v['variant_id'],status=v['report']['status'],reason=v['report']['reasons'],
                W_sha=digest(w),best_support=v['scalar_full']['best_support'],
                best_gt_error=plane_error(best) if best and synthetic else None,
                worst_W_gt_error={k:max(plane_error(p)[k] for p in w) for k in ('normal_deg','offset_m')} if w and synthetic else None,
                best_plane=best,validation=holds,refinement_counts=v['refinement_counts'],
                scalar_full=v['scalar_full'],I05_counts=v['report']['counts'])


def compare(name,points,rows,regions,up,height,s,r0=None,repeats=1):
    tick=time.perf_counter()
    sampled,fit,iterator=gd.replay_sequence(points,rows,up,height,s)
    sampling=time.perf_counter()-tick
    tick=time.perf_counter();seq=list(iterator);raw=time.perf_counter()-tick
    packet=dict(schema=1,units='m',frame='research_source',source_sha=digest(points),fit_sha=digest(fit),
                sampled_sha=digest(sampled),raw_sha=digest(seq),settings_sha=digest(s))
    validate_packet(points,fit,sampled,seq,s,packet)
    if r0:
        assert r0['source_sha']==packet['source_sha'] and r0['raw_sha']==packet['raw_sha']
        assert r0['sampled_sha']==packet['sampled_sha'] and r0['settings_sha']==packet['settings_sha']
    variants=[]
    for k in (1,2,3):
        costs=[];first=None;first_sha=None
        for i in range(repeats):
            tick=time.perf_counter()
            sample2,fit2,it=gd.replay_sequence(points,rows,up,height,s)
            sampling2=time.perf_counter()-tick
            tick=time.perf_counter();seq2=list(it);raw2=time.perf_counter()-tick
            assert digest(seq2)==packet['raw_sha'] and digest(sample2)==packet['sampled_sha']
            tick=time.perf_counter();v=run_variant(points,sampled,fit,seq,up,height,s,k);total=time.perf_counter()-tick
            if k==1 and r0:assert v['W']==r0['W']
            tick=time.perf_counter();encoded=json.dumps(v,allow_nan=False,separators=(',',':')).encode();serialization=time.perf_counter()-tick
            semantic=dict(W=v['W'],details=[{key:value for key,value in d.items() if key!='lo_elapsed_s'} for d in v['details']],
                          status=v['report']['status'],counts=v['refinement_counts'])
            signature=digest(semantic)
            if first is None:first,first_sha=v,signature
            else:assert first_sha==signature,'repeat drift'
            costs.append(dict(repeat=i,sampling=sampling2,raw=raw2,LO=v['lo_elapsed_s'],
                              refine=v['report']['stage_elapsed_s']['refine'],decision=v['report']['stage_elapsed_s']['decision'],
                              variant_including_scalar_audit=total,serialization=serialization,serialized_bytes=len(encoded)))
        # full members/parameters/W saved only once; repeats identical by semantic SHA.
        compact_new(HERE/('r1_case_%s_K%d_01.json'%(name,k)),dict(packet=packet,variant=first,costs=costs,
                    semantic_sha=first_sha,baseline_r0_file='r0_case_'+name+'_01.json' if r0 else None))
        row=brief(first,points,regions,s,not name.startswith('real'))
        row.update(costs=costs,semantic_sha=first_sha)
        variants.append(row)
    return dict(case=name,packet=packet,variants=variants,physical_verified=False,
                validation_policy='all predetermined rows; never residual-filtered; groups distinct from FIT',
                initial_sampling_s=sampling,initial_raw_s=raw)


def process_peak():
    from ctypes import wintypes
    class PMC(ctypes.Structure):
        _fields_=[('cb',wintypes.DWORD),('PageFaultCount',wintypes.DWORD)]+[(n,ctypes.c_size_t) for n in
            ('PeakWorkingSetSize','WorkingSetSize','QuotaPeakPagedPoolUsage','QuotaPagedPoolUsage',
             'QuotaPeakNonPagedPoolUsage','QuotaNonPagedPoolUsage','PagefileUsage','PeakPagefileUsage')]
    counters=PMC();counters.cb=ctypes.sizeof(counters)
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.GetCurrentProcess.restype=wintypes.HANDLE
    psapi=ctypes.WinDLL('psapi',use_last_error=True)
    psapi.GetProcessMemoryInfo.argtypes=[wintypes.HANDLE,ctypes.POINTER(PMC),wintypes.DWORD]
    if not psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(),ctypes.byref(counters),counters.cb):raise ctypes.WinError(ctypes.get_last_error())
    return dict(peak_working_set_bytes=counters.PeakWorkingSetSize,working_set_bytes=counters.WorkingSetSize,
                peak_private_commit_bytes=counters.PeakPagefileUsage,method='separate process Windows GetProcessMemoryInfo; includes imports and whole process')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--memory',type=int);args=parser.parse_args()
    if args.memory:
        cloud,rows,_=scene('high_noise',7)
        s=settings(7);up=np.array([0.,0.,1.]);sampled,fit,it=gd.replay_sequence(cloud,rows,up,(.5,2.),s)
        base=process_peak();v=run_variant(cloud,sampled,fit,list(it),up,(.5,2.),s,args.memory)
        print(json.dumps(dict(k=args.memory,before=base,after=process_peak(),status=v['report']['status'],physical_verified=False)))
        return
    summary=[]
    for kind,seed,perm in itertools.product(KINDS,SEEDS,(False,True)):
        name='%s_%d_%s'%(kind,seed,perm)
        cloud,rows,regions=scene(kind,seed,perm)
        r0=json.loads((HERE/('r0_case_'+name+'_01.json')).read_text())
        row=compare(name,cloud,rows,regions,np.array([0.,0.,1.]),(.5,2.),settings(seed),r0,
                    repeats=3 if seed==7 and not perm else 1)
        summary.append(row);print(name,[v['status'] for v in row['variants']],flush=True)
    cloud,rows,regions,draft,s=real_inputs()
    for name,up in [('real_approved',draft['up_axis']),('real_historical_WHAT_IF_negative_X',[-draft['up_axis'][0],0.,draft['up_axis'][2]])]:
        r0=json.loads((HERE/('r0_case_'+name+'_01.json')).read_text())
        row=compare(name,cloud,rows,regions,g._unit_vector(up,'up'),draft['sensor_height_interval_m'],s,r0,repeats=3)
        summary.append(row)
    write_new(HERE/'r1_summary_01.json',dict(results=summary,physical_verified=False,
              robust_experiment='NOT_RUN: R0 gate not triggered; no weights or alternate score gate',
              runtime=dict(python=sys.version,numpy=np.__version__,platform=platform.platform(),board=False),
              cost_boundary='same sampled K; timing includes separate scalar audit; phase times not end-to-end native validation equivalent'))


if __name__=='__main__':main()

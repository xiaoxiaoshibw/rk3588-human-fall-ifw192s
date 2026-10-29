"""Explicit single-session streaming runner; no discovery, old main or data writes."""
import argparse
import ctypes
import json
import os
from pathlib import Path
import platform
import sys
import time
import traceback
import numpy as np
import scipy
from contracts import HERE, ROOT, ITEM, PREDEV, Source, digest, module, new_output, sha, write_new, save_array, protocol_gate, diagnostic_evaluation,layout_evidence
from pipeline import Engine, FrozenMap, DEFAULTS, LABELS


def peak_rss():
    if os.name=='nt':
        from ctypes import wintypes
        class Counters(ctypes.Structure):
            _fields_=[('cb',wintypes.DWORD),('faults',wintypes.DWORD)]+[(x,ctypes.c_size_t) for x in ['peak','working','pquota','quota','ppool','pool','page','ppage']]
        c=Counters();c.cb=ctypes.sizeof(c)
        handle=ctypes.windll.kernel32.GetCurrentProcess
        handle.restype=wintypes.HANDLE
        get=ctypes.windll.psapi.GetProcessMemoryInfo
        get.argtypes=[wintypes.HANDLE,ctypes.c_void_p,wintypes.DWORD]
        get.restype=wintypes.BOOL
        if not get(handle(),ctypes.byref(c),c.cb):raise OSError('RSS query failed')
        return c.peak
    import resource
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024


def environment():
    files=[p for p in HERE.rglob('*') if p.is_file() and p.suffix in ('.py','.js','.html','.md')]
    deps=[PREDEV/'contracts.py',PREDEV/'pipeline.py',PREDEV/'test_predev.py',PREDEV/'evaluate.py',
          ROOT/'sidequests/human_fusion_lab_next/pointset/r01/next_contract.py',ROOT/'sidequests/hfus_tcms/tcms.py',
          ROOT/'docs/human_fall/evidence/2026-10-16_hfus_tcms_01_r1/run_r1/THRESHOLDS.json']
    return dict(python=sys.version,executable=sys.executable,numpy=np.__version__,scipy=scipy.__version__,platform=platform.platform(),seed=17,
                argv=sys.argv,source_sha256={str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in files+deps},models='NOT_USED',GT='NOT_USED',
                coordinates='RAW_UNVERIFIED_INSTALLATION/v1; XYZ in source metres, no physical height',clock='device ns unanchored')


def execute(manifest,out,probe=False,frozen_probe=False):
    protocol_gate(manifest)
    layout_evidence(manifest['protocol'])
    if len(manifest.get('entries',[]))!=1:raise ValueError('One explicit source required')
    source=Source(manifest['entries'][0]);protocol=manifest['protocol'];started=time.perf_counter()
    env=environment();write_new(out/'ENVIRONMENT.json',env);write_new(out/'INPUT_MANIFEST.json',manifest)
    snapshot=out/'EXECUTED_SOURCE';snapshot.mkdir()
    for name in env['source_sha256']:
        path=snapshot/name;path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('xb') as f:f.write((ROOT/name).read_bytes())
    write_new(out/'SOURCE_PREFLIGHT.json',dict(sid=source.sid,source_sha256=source.binding,frames=len(source.frames),raw_rows=source.meta['total_points'],stride=28,
              duration_s=source.times[-1],max_gap_s=max(np.diff(source.stamps))/1e9,empty_frames=sum(f['count_points']==0 for f in source.frames),
              human_annotations=len(source.meta.get('human_annotations',[])),role='B',kind='REAL_DEVELOPMENT',independent_test=False))
    # Whole-session taint is registered BEFORE action XYZ is accessed.
    write_new(out/'OBSERVATION_HISTORY.json',dict(development_seen=True,dev_tainted=True,scope='ENTIRE_SESSION',sid=source.sid,
              first_processing_ns=time.time_ns(),observations=['Real scale probe / full run'],influences=['Candidate representation and main/reference comparison'],
              forbidden_independent_relabelling=True,user_facts=manifest['user_facts']))
    frozen=FrozenMap(out,source.binding,source.entry['coordinate_version'],protocol)
    run_version=digest(dict(manifest=manifest,code=env['source_sha256'],output=str(out)))
    variants=['scalable_reference','main'];engines={v:Engine(None,v,digest(env['source_sha256']),run_version=run_version,protocol_sha=digest(protocol)) for v in variants}
    dirs={}
    for v in variants:
        dirs[v]=out/v;dirs[v].mkdir()
    baseline=out/'b2_b3';baseline.mkdir()
    tcms=module('realdev_tcms',ROOT/'sidequests/hfus_tcms/tcms.py')
    window=tcms.Window(.15,10)
    thresholds=json.loads((ROOT/'docs/human_fall/evidence/2026-10-16_hfus_tcms_01_r1/run_r1/THRESHOLDS.json').read_text())['v0.15_w10']
    index=[];validation=[];validation_distances=[];qualification=None;ablation=[];growth_ablation=[];first_response={v:None for v in variants}
    ablation_engine=Engine(None,'no_frozen',digest(env['source_sha256']),run_version=run_version,protocol_sha=digest(protocol))
    no_growth=Engine(None,'no_growth',digest(env['source_sha256']),run_version=run_version,protocol_sha=digest(protocol))
    try:
        indices=list(range(10)) if probe else list(range(len(source.frames)))
        if frozen_probe:indices=list(range(300))+list(range(430,433))+list(range(730,733))+[779]
        for fi in indices:
            tick=time.perf_counter();f=source.frame(fi);t=f['relative_s']
            if t>=20 and frozen.map_id is None:
                frozen.freeze();frozen.bind_exact_time(source.stamps)
                for e in engines.values():e.map=frozen
                ablation_engine.map=frozen
                no_growth.map=frozen
            phase='MAP_BUILDING' if t<20 else 'TEMPORAL_VALIDATION' if t<28 else 'EMPTY_AUDIT' if t<30 else 'ACTION'
            qualified=bool(qualification and qualification['qualified_M0'] and fi>qualification['available_after_fi'])
            if t<20:frozen.add(f)
            import hashlib
            raw28=source.buffer[f['offset']*28:(f['offset']+len(f['xyz']))*28] if source.buffer is not None else b''
            entry=dict(fi=fi,time_ns=f['time_ns'],relative_s=t,offset_points=f['offset'],count_points=len(f['xyz']),
                       raw28_sha256=hashlib.sha256(raw28).hexdigest(),variants={})
            for v,e in engines.items():
                r,rows,hits=e.step(f,phase,qualified=qualified)
                stem=dirs[v]/('%04d'%fi)
                save_array(stem.with_suffix('.npz'),current=rows,map_hits=hits)
                write_new(stem.with_suffix('.json'),r)
                entry['variants'][v]=dict(record=str(stem.with_suffix('.json').relative_to(out)).replace('\\','/'),ledger=str(stem.with_suffix('.npz').relative_to(out)).replace('\\','/'),
                    candidates=len(r['candidates']),candidate_rows=r['accounting']['candidate_member_rows'],valid=r['accounting']['valid'],invalid=r['accounting']['invalid'],bg=r['accounting']['labels']['bg_match'])
                if t>=30 and r['candidates'] and first_response[v] is None:first_response[v]=dict(fi=fi,relative_s=t,candidates=len(r['candidates']),note='FIRST_ALGORITHM_RESPONSE_NOT_FIRST_VISIBLE_HUMAN')
                if v=='main' and 20<=t<28:
                    valid=(rows['flags']&1)!=0;bg=(rows['flags']&2)!=0
                    distances=frozen.match(f['xyz'],valid)[1][valid]
                    validation_distances.append(distances)
                    validation.append(dict(fi=fi,time_ns=f['time_ns'],raw=len(rows),valid=int(valid.sum()),matched=int(bg.sum()),
                                           nearest_distance_p95_m=float(np.quantile(distances,.95)) if len(distances) else None))
            # Pure old B2/B3 adapter receives identical RAW/current range.
            hits,rejected=tcms.support(f['xyz'],.15);scores,state=window.update(hits,f['time_ns']/1e9)
            br=dict(sid=source.sid,fi=fi,source_sha256=source.binding,coordinate_version=f['coordinate_version'],status=state,
                    raw_rows=len(f['xyz']),filtered_or_out_of_range_rows=rejected,thresholds_original=thresholds,tiles=[])
            for score in scores:
                br['tiles'].append(dict(score=score,source_rows=hits[tuple(score['tile'])][1].tolist(),active={m:tcms.active(score,thresholds,m) for m in ['B2','B3']}))
            write_new(baseline/('%04d.json'%fi),br)
            entry['b2_b3_active_tiles']={m:sum(x['active'][m] for x in br['tiles']) for m in ['B2','B3']}
            if any(a<=t<b for a,b in protocol['ablation_windows_s']):
                r,rows,mh=ablation_engine.step(f,phase,False)
                ad=out/'no_frozen'
                if not ad.exists():ad.mkdir()
                write_new(ad/('%04d.json'%fi),r);save_array(ad/('%04d.npz'%fi),current=rows,map_hits=mh)
                ablation.append(dict(fi=fi,relative_s=t,candidates=len(r['candidates']),candidate_rows=r['accounting']['candidate_member_rows']))
                if qualified:
                    gr,grows,gh=no_growth.step(f,phase,True);gd=out/'no_growth'
                    if not gd.exists():gd.mkdir()
                    write_new(gd/('%04d.json'%fi),gr);save_array(gd/('%04d.npz'%fi),current=grows,map_hits=gh)
                    growth_ablation.append(dict(fi=fi,relative_s=t,candidates=len(gr['candidates']),candidate_rows=gr['accounting']['candidate_member_rows']))
            if qualification is None and t<28 and fi+1<len(source.frames) and source.times[fi+1]>=28:
                total=sum(x['valid'] for x in validation);matched=sum(x['matched'] for x in validation)
                p95=float(np.quantile(np.concatenate(validation_distances),.95)) if validation_distances else None
                q=protocol['qualification'];numeric=bool(total and matched/total>=q['min_temporal_valid_coverage'] and p95 is not None and p95<=q['max_temporal_residual_p95_m'] and len(frozen.tree_ids)>=q['min_supported_surfaces'])
                qualified_result=bool(numeric and q.get('layout_consistent') is True and q.get('layout_evidence'))
                qualification=dict(available_after_fi=fi,coverage=matched/total if total else None,validation=validation,
                      candidate_map_exists=frozen.map_id is not None,qualified_M0=qualified_result,static_boundary_available=qualified_result,
                      numeric_thresholds=q,numeric_coverage_pass=bool(total and matched/total>=q['min_temporal_valid_coverage']),
                      temporal_residual_p95_m=p95,numeric_p95_pass=bool(p95 is not None and p95<=q['max_temporal_residual_p95_m']),
                      supported_surfaces=len(frozen.tree_ids),numeric_surface_support_pass=len(frozen.tree_ids)>=q['min_supported_surfaces'],
                      numeric_all_frame_p95_pass=bool(validation and all(x['nearest_distance_p95_m'] is not None and x['nearest_distance_p95_m']<=.08 for x in validation)),
                      reason='FINITE_M0_NUMERIC_AND_USER_LAYOUT_EVIDENCE; GROUND_SEPARATE_BLOCKED' if qualified_result else 'BLOCKED_LAYOUT_OR_NUMERIC_QUALIFICATION; GROUND_SEPARATE_BLOCKED',
                      thresholds_fitted_on_validation=False,ground_qualification=False)
                validation_distances=[]
            entry['elapsed_s']=time.perf_counter()-tick;index.append(entry)
            if fi%25==0:print(json.dumps(dict(fi=fi,t=t,surfaces=frozen.n,elapsed_s=time.perf_counter()-started,peak_rss_bytes=peak_rss())),flush=True)
            wall_limit=protocol['budget']['probe_wall_seconds' if probe or frozen_probe else 'full_wall_seconds']
            if peak_rss()>protocol['budget']['peak_rss_bytes']:raise MemoryError('Pre-registered RSS budget exceeded')
            if time.perf_counter()-started>wall_limit:raise TimeoutError('Pre-registered wall budget exceeded')
        if frozen.map_id and frozen.fingerprint()!=frozen.map_id:raise ValueError('Frozen matching arrays drift')
        final_binding={k:sha(source.folder/n) for k,n in [('meta','meta.json'),('points','points.bin')]}
        if final_binding!=source.binding:raise ValueError('Source changed while running')
        write_new(out/'QUALIFICATION.json',qualification or dict(qualified_M0=False,reason='PROBE_MAP_BUILDING_ONLY'))
        write_new(out/'EVALUATION.json',diagnostic_evaluation())
        ablations=dict(no_frozen=dict(status='PASS_SOFTWARE_EXECUTION_ONLY',frames=ablation,full_session='NOT_RUN'),
                    **{v:dict(status='BLOCKED',reason='NOT_APPLICABLE_FACTOR_DISABLED') for v in ['no_ground','no_continuation','no_growth','no_identity']})
        if growth_ablation:ablations['no_growth']=dict(status='PASS_SOFTWARE_EXECUTION_ONLY',frames=growth_ablation,full_session='NOT_RUN')
        write_new(out/'ABLATIONS.json',ablations)
        write_new(out/'INDEX.json',dict(schema='hfus-realdev-index/1',entries=[source.entry],frames=index,variants=variants,
                    map_id=frozen.map_id,development_seen=True,dev_tainted=True,cases=[],first_response=first_response,probe=probe or frozen_probe,
                    algorithm_differences=dict(map='Voxel-centroid/AABB replaces original local plane neighborhoods',
                        components='Occupied voxel centroid connectivity replaces original raw-radius connectivity',
                        main='Unknown orientation: removes RAW-axis transverse <=0.8m filter; same max extent, no ground',
                        qualified='Layout evidence is verified when present; finite M0 qualification only after validation. Ground remains separate; not original r01 equivalent')))
        size=sum(p.stat().st_size for p in out.rglob('*') if p.is_file())
        if size>protocol['budget']['output_bytes_per_full_run']:raise OSError('Output budget exceeded')
        write_new(out/'PERFORMANCE.json',dict(elapsed_s=time.perf_counter()-started,peak_rss_bytes=peak_rss(),output_bytes=size,frames=len(index),
                   raw_rows=sum(f['count_points'] for f in index),surfaces=frozen.n,eligible_surfaces=len(frozen.tree_ids) if frozen.map_id else None,
                   source_final=final_binding,map_fingerprint_after=frozen.fingerprint() if frozen.map_id else None,
                   budget=protocol['budget'],status='SUBMITTED_NOT_ACCEPTED',all_rows_processed=True))
        hashes={str(p.relative_to(out)).replace('\\','/'):sha(p) for p in out.rglob('*') if p.is_file()}
        write_new(out/'OUTPUT_INDEX.json',hashes)
    finally:source.close()


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--manifest',required=True);p.add_argument('--out',required=True);p.add_argument('--probe',action='store_true');p.add_argument('--frozen-probe',action='store_true');a=p.parse_args()
    out=new_output(a.out)
    try:execute(json.loads(Path(a.manifest).read_text(encoding='utf8')),out,a.probe,a.frozen_probe)
    except Exception as exc:
        write_new(out/'FAILURE.json',dict(type=type(exc).__name__,reason=str(exc),traceback=traceback.format_exc()))
        raise

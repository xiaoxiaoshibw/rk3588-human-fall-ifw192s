"""显式离线 W1+W2；默认生产入口不引用它，不拟合或输出跌倒事件。"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time

import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from core.capture_input import ROW_DTYPE, sha256_file
from core.range_background import RayBackground
from core.range_components import label_components
from core.range_contract import source_binding, binding_tuple, load_ground, distribution
from core.range_denoise import denoise
from core.range_image import ScanGrid
from core.range_tracker import RangeTracker, SETTINGS
from replay_range_frontend import ROOT, CALIBRATION, session_meta, reference_rows, compare, percentiles, write_json


def run(session, out, *, empty_prefix_frames, frontend, limit=None, reference_run=None, ground_path=None):
    if frontend != 'range_v1':
        raise ValueError('explicit offline frontend=range_v1 required')
    session,out=Path(session).resolve(),Path(out).resolve()
    for protected in (ROOT/'data',ROOT/'captures',session):
        p=protected.resolve()
        if out==p or p in out.parents or out in session.parents:
            raise ValueError('output must be a new directory outside source data')
    meta,msha=session_meta(session)
    psha=sha256_file(session/'points.bin')
    count=len(meta['frames']) if limit is None else limit
    if not 1 <= empty_prefix_frames < count <= len(meta['frames']):
        raise ValueError('invalid explicit prefix/replay length')
    az,el=(CALIBRATION/name for name in ('ifw192s_azimuth_192x256.csv','ifw192s_elevation_192x256.csv'))
    grid=ScanGrid.from_csv(az,el)
    identity=source_binding(session,meta,msha,psha,grid)
    identity.update(azimuth_sha256=sha256_file(az),elevation_sha256=sha256_file(el))
    binding=binding_tuple(identity)
    ground=load_ground(ground_path,identity) if ground_path else None
    # 推理阶段从不读取reference；仅完成该帧新目标后计算诊断。
    reference=reference_rows(Path(reference_run),meta,msha,psha) if reference_run else None
    tracker=RangeTracker()
    out.mkdir(parents=True,exist_ok=False)
    config=dict(frontend=frontend,empty_prefix_frames=empty_prefix_frames,tracker=SETTINGS,
                ground_sha256=sha256_file(ground_path) if ground_path else None,
                background_update=False,min_neighbours=2,min_component_points=15,merge=False)
    config_sha=hashlib.sha256(json.dumps(config,sort_keys=True).encode()).hexdigest()
    write_json(out/'CONFIG.json',dict(settings=config,sha256=config_sha,source_binding=identity))
    prefix,bg=[],None
    digest=hashlib.sha256()
    inference_digest=hashlib.sha256()
    costs,proxies=[],[]
    statuses={}
    t0=meta['frames'][0]['stamp_sec']*1000000000+meta['frames'][0]['stamp_nanosec']
    with (session/'points.bin').open('rb') as source, (out/'frames.jsonl').open('x',encoding='utf-8') as ledger, \
         (out/'timings.jsonl').open('x',encoding='utf-8') as timing_ledger:
        for index,info in enumerate(meta['frames'][:count]):
            start=time.perf_counter()
            raw=source.read(info['count_points']*ROW_DTYPE.itemsize)
            if len(raw)!=info['count_points']*ROW_DTYPE.itemsize:
                raise ValueError('truncated input')
            began=time.perf_counter()
            frame=grid.decode(raw,binding)
            if bg is None:
                prefix.append(frame)
                foreground=np.zeros(grid.shape,dtype=bool)
                status='prefix_warmup'
            else:
                result=bg.foreground(frame)
                foreground=result['mask']
                status=result['status']
                with np.errstate(invalid='ignore'):
                    foreground &= (frame.range_m>=.1)&(frame.range_m<=8)
            cleaned=denoise(frame,foreground)
            labels,components=label_components(frame,cleaned['mask'])
            front_done=time.perf_counter()
            stamp=(info['stamp_sec']*1000000000+info['stamp_nanosec']-t0)/1e9
            detail={}
            record=tracker.update(frame,labels,components,stamp,index,ground=ground,timings=detail)
            done=time.perf_counter()
            inference_serial=json.dumps(record,sort_keys=True,allow_nan=False)
            inference_digest.update(inference_serial.encode())
            target=set(record['target_source_rows'])
            diagnostic=None
            if reference:
                comparison=compare(frame,cleaned['mask'],components,reference[index])
                if comparison['reference_observed']:
                    best=comparison['diagnostic_best_component']
                    rows=set(components[best]['source_rows'].tolist()) if best is not None else set()
                    diagnostic=dict(reference_observed=True,target_present=bool(target),
                        diagnostic_component_points=len(rows),intersection_points=len(rows&target),
                        intersection_fraction=len(rows&target)/len(rows) if rows else None,
                        reason=None if rows else 'empty_diagnostic_component',
                        old_reference_points=len(reference[index]['target_source_rows']),
                        old_reference_intersection=len(target&set(reference[index]['target_source_rows'])))
                    proxies.append(dict(frame=index,**diagnostic))
            record.update(session=session.name,offset_points=info['offset_points'],status=status,
                source_binding=identity,config_sha256=config_sha,raw_sha256=hashlib.sha256(raw).hexdigest(),
                component_count=len(components),retained_component_count=sum(c['retained'] for c in components),
                inference_sha256=hashlib.sha256(inference_serial.encode()).hexdigest(),
                diagnostic=diagnostic)
            serialized=json.dumps(record,sort_keys=True,allow_nan=False)
            ledger.write(serialized+'\n')
            digest.update(serialized.encode())
            cost=dict(frame=index,status=status,frontend_ms=(front_done-began)*1000,
                tracking_ms=(done-front_done)*1000,features_ms=detail['features_ms'],
                algorithm_ms=(done-began)*1000,loop_ms=(time.perf_counter()-start)*1000)
            timing_ledger.write(json.dumps(cost,allow_nan=False)+'\n')
            costs.append(cost)
            statuses[status]=statuses.get(status,0)+1
            if index+1==empty_prefix_frames:
                bg=RayBackground(prefix,empty_prefix_declared=True,min_observations=min(10,empty_prefix_frames))
                prefix.clear()
    if sha256_file(session/'points.bin')!=psha or sha256_file(session/'meta.json')!=msha:
        raise ValueError('source changed during replay')
    ready=[c for c in costs if c['status']!='prefix_warmup']
    denominator=sum(r['diagnostic_component_points'] for r in proxies)
    n=len(proxies)
    summary=dict(schema='range_tracking_replay_v1',frames=count,source_binding=identity,settings=config,
        config_sha256=config_sha,algorithm_output_sha256=digest.hexdigest(),frames_sha256=sha256_file(out/'frames.jsonl'),
        inference_output_sha256=inference_digest.hexdigest(),
        statuses=statuses,performance={k:percentiles([c[k] for c in ready]) for k in
            ('frontend_ms','tracking_ms','features_ms','algorithm_ms','loop_ms')},
        performance_scope='PC packed bytes -> W1/W2 including features; loop adds read/diagnostic/JSON/buffered write, excludes timing recorder and prefix fit; startup SHA and CLI wall separate',
        performance_samples='post-prefix, including invalid-background/dropout frames',
        ready_performance={k:percentiles([c[k] for c in costs if c['status']=='ready']) for k in ('algorithm_ms','loop_ms')},
        proxy=dict(reference_observed_frames=n,target_present_frames=sum(r['target_present'] for r in proxies),
            target_presence_fraction=sum(r['target_present'] for r in proxies)/n if n else None,
            intersection_fraction=distribution([r['intersection_fraction'] for r in proxies]),
            below_97percent_frames=[r['frame'] for r in proxies if r['intersection_fraction'] is not None and r['intersection_fraction']<.97],
            weighted_component_intersection=sum(r['intersection_points'] for r in proxies)/denominator if denominator else None,
            component_row_denominator=denominator,scope='old-reference proxies only; target presence does not prove matching identity'),
        source_sha256={str(p.relative_to(ROOT)):sha256_file(p) for p in
            [Path(__file__).resolve(),ROOT/'src/human_fall_detection/scripts/replay_range_frontend.py',
             *sorted((ROOT/'src/human_fall_detection/core').glob('*.py'))]},
        human_identity_switch_rate='UNKNOWN',human_precision_recall='UNKNOWN',fall_effectiveness='UNKNOWN',
        bathroom_effectiveness='UNKNOWN',board_performance='UNKNOWN',deployed=False)
    write_json(out/'SUMMARY.json',summary)
    print(json.dumps(dict(frames=count,performance=summary['performance'],proxy=summary['proxy'])),flush=True)
    return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--session',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--frontend',choices=['range_v1'],required=True)
    parser.add_argument('--empty-prefix-frames',type=int,required=True)
    parser.add_argument('--limit',type=int)
    parser.add_argument('--reference-run',type=Path)
    parser.add_argument('--ground',type=Path)
    args=parser.parse_args()
    run(args.session,args.out,frontend=args.frontend,empty_prefix_frames=args.empty_prefix_frames,
        limit=args.limit,reference_run=args.reference_run,ground_path=args.ground)

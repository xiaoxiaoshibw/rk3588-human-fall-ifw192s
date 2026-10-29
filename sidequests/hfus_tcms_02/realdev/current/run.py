"""Run the active project pipeline on a bound session, retaining both variants."""
import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
import numpy as np
from project_regions import estimate
from project_dependencies import ROOT, SK, module, valid_nodes, measurements, CalibrationLayer
from coordinates import GroundCoordinates
from project_fall import FallRuntime, body_candidate
from target_points import components
from core.lidar_candidates import build_snapshot, build_background, prepare_background, rebuild_candidate
from region_runtime import RegionRuntime
from collections import Counter
from contextlib import nullcontext

HERE=Path(__file__).resolve().parent
S07=ROOT/'docs/human_fall/evidence/2026-10-18_hfus_tcms_02_s07_r1'
S07F=ROOT/'docs/human_fall/evidence/2026-10-18_hfus_tcms_02_s07f_r1'
LEVELING=ROOT/'docs/human_fall/evidence/2026-10-18_hfus_project_dev_r1/leveling_02/TRANSFORM.json'
SID='cap_20261018_110029'
GEOMETRY=ROOT/'src/human_fall_detection/config/single_target_geometry_v2.json'
LEGACY_FOREGROUND_BOUNDS=((.75,2.4),(.9,1.65),(-.4,1.85))

def sha(p):
    with Path(p).open('rb') as f:
        h=hashlib.sha256()
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
        return h.hexdigest()

def put(p,x):
    with Path(p).open('x',encoding='utf8',newline='\n') as f:
        f.write(x if isinstance(x,str) else json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')

def source(session=None):
    C=module('active_project_source',ROOT/'sidequests/hfus_tcms_02/realdev/r01/contracts.py')
    session=Path(session or ROOT/'data/sessions'/SID).resolve()
    binding={k:sha(session/n) for k,n in [('meta','meta.json'),('points','points.bin')]}
    return C.Source(dict(kind='REAL_DEVELOPMENT',role='B',independent_test=False,
        path=str(session),sid=session.name,coordinate_version='RAW/innolidar',source_sha256=binding))

def process(src,ledger,partition,ground_path=LEVELING,settings=None,background=None,
            search_bounds=None,empty_prefix_frames=0,timings=None,
            region_contract='target_ground_v1',stage_timings=None,support_history_guard=False,
            change_acquisition=False,history_hold_gate=False,human_entry_gate=True):
    records=[];previous=None;last=None;cal=CalibrationLayer(SK.EDGES);resets=[]
    sid=src.sid
    coordinates=GroundCoordinates(ground_path,sid,src.binding)
    regions=RegionRuntime(sid,partition,region_contract)
    runtime=FallRuntime(sid,'ground:'+coordinates.artifact['transform_id'],
                        dict(support_history_guard=support_history_guard,
                             human_entry_gate=human_entry_gate,
                             change_gate=change_acquisition,
                             history_hold_gate=history_hold_gate))
    background=prepare_background(background)
    empty=[];epoch=0;last_time=None;last_generation=None
    ground=dict(status='valid',frame='RAW/innolidar',normal=coordinates.R[2].tolist(),
                offset_m=float(coordinates.t[2]))
    bounds=np.asarray(LEGACY_FOREGROUND_BOUNDS)
    for fi in range(len(src.frames)):
        started=time.perf_counter()
        f=src.frame(fi);raw=f['xyz'];warmup=False
        if ledger is not None:
            mask=np.isfinite(raw).all(1)&np.any(raw!=0,1)&np.all(raw>=bounds[:,0],1)&np.all(raw<=bounds[:,1],1)
            rows=np.flatnonzero(mask)+f['offset'];sl=slice(ledger['indptr'][fi],ledger['indptr'][fi+1])
            assert np.array_equal(rows,ledger['global_rows'][sl])
            keep=ledger['keep'][sl];p=raw[mask][keep];rows=rows[keep]
            candidates,clusters=components(p,rows,coordinates)
            foreground_rows=rows.tolist()
        else:
            selected=np.flatnonzero(np.isfinite(raw).all(1)&np.any(raw!=0,1))
            if search_bounds is not None:
                selected=selected[np.all(raw[selected]>=search_bounds[:,0],1)&np.all(raw[selected]<=search_bounds[:,1],1)]
            if fi < empty_prefix_frames:
                empty.append(raw[selected])
                warmup=True
                if fi+1 == empty_prefix_frames:
                    background=prepare_background(build_background(empty,settings,frame_id='RAW/innolidar',
                        note='explicit declared-empty prefix; development assumption, no semantic GT'))
                    empty=[]
            snapshot=build_snapshot(raw[selected] if not warmup else np.empty((0,3)),settings,
                session_id=sid,time_epoch=epoch,snapshot_id=str(fi),source_stamp_s=src.times[fi],
                frame_id='RAW/innolidar',ground=ground,background=background)
            candidates=snapshot['candidates'];clusters=[]
            foreground_rows=(selected[snapshot['foreground_indices']]+f['offset']).tolist()
            for c in candidates:
                c['source_rows']=sorted((selected[c['evidence_indices']]+f['offset']).tolist())
                c['center_reference_m']=coordinates.points(c['center_source_m']).tolist()
                clusters.append(dict(candidate_id=c['candidate_id'],source_rows=c['source_rows'],
                    point_count=c['point_count'],reason='candidate'))
            for c in snapshot['rejected_clusters']:
                clusters.append(dict(candidate_id=None,source_rows=(selected[c['evidence_indices']]+f['offset']).tolist(),
                    point_count=len(c['evidence_indices']),reason=c['reason']))
        candidate_done=time.perf_counter()
        if last_time is not None and src.times[fi] <= last_time:epoch+=1
        last_time=src.times[fi]
        def rebuild_target(local_rows, _raw=raw, _selected=selected, _settings=settings,
                           _ground=ground, _offset=f['offset']):
            """Rebuild a composed measurement from accepted session rows.

            Geometry comes from the same array the candidates were built from;
            ``evidence_indices`` stay in the selected-subarray domain of this
            adapter, ``source_rows`` keep the session row mapping.
            """
            rows=np.asarray(local_rows,dtype=np.int64)
            composed=rebuild_candidate(_raw,rows,_settings,ground=_ground,
                                       frame_id='RAW/innolidar')
            composed['source_rows']=sorted((rows+_offset).tolist())
            composed['evidence_indices']=np.searchsorted(_selected,rows).tolist()
            composed['center_reference_m']=coordinates.points(composed['center_source_m']).tolist()
            return composed
        fall=runtime.step(src.times[fi],candidates,time_epoch=epoch,valid=not warmup,
            points=raw, row_offset=f['offset'], frame_seq=fi, ground=ground,
            rebuild=rebuild_target)
        track_done=time.perf_counter()
        if warmup:fall['acquisition']['reason']='declared_background_warmup'
        for cluster in clusters:
            cid=cluster['candidate_id']
            cluster['disposition']=('selected_unknown' if cid is not None and cid==fall['target_candidate_id']
                else (fall['acquisition'].get('rejected',{}).get(cid) or fall['acquisition']['reason'])
                if cluster['reason']=='candidate' else cluster['reason'])
        target_rows=np.asarray(fall['target_rows'],dtype=np.int64)
        p=raw[target_rows-f['offset']];rows=target_rows
        sk,cf,region_reset=regions.feed(p,rows.tolist(),fi,fall['track']['generation'],
            fall['track']['status']=='locked',coordinates.R[2])
        if region_reset:resets.append(fi)
        for n in sk['nodes'].values():
            if n['valid']:
                inds=np.searchsorted(rows,n['support_rows'])
                assert np.array_equal(rows[inds],n['support_rows'])
                assert np.array_equal(np.median(p[inds],axis=0),n['xyz'])
        if partition:
            for side in ('A','B'):
                parts=sk.get('diagnostics',{}).get('partitions',{})
                if 'UPPER_'+side in parts:
                    assert not set(parts['UPPER_'+side]['selected_rows'])&set(parts['OUTER_'+side]['selected_rows'])
        # Fall evidence uses only this frame's measured ground points; a rejected
        # frame still advances the track/fall clocks with no candidate.
        records.append(dict(fi=fi,t=src.times[fi],candidate_rows=len(p),valid_nodes=valid_nodes(sk),
            foreground_rows=foreground_rows,clusters=clusters,
            binding=dict(session_id=sid,coordinate_version='RAW/innolidar',time_epoch=epoch,
                         source_sha256=src.binding,ground_version=coordinates.artifact['transform_id']),
            bbox_raw=None if not len(p) else dict(min=p.min(0).tolist(),max=p.max(0).tolist()),
            center_raw=None if not len(p) else np.median(p,axis=0).tolist(),
            nodes=sk['nodes'],reason=sk['reason'],axis=sk.get('axis'),basis_lateral=sk.get('basis_lateral'),
            diagnostics=sk.get('diagnostics'),calibration=cf,**fall))
        finished=time.perf_counter()
        if timings is not None:timings.append(finished-started)
        if stage_timings is not None:
            stage_timings.append(dict(fi=fi,warmup=warmup,input_candidates_s=candidate_done-started,
                tracking_fall_s=track_done-candidate_done,regions_record_s=finished-track_done,
                total_s=finished-started,**runtime.timings_s))
    return records,resets

def main(out,session=None,ground_path=LEVELING,pipeline='raw',settings_path=GEOMETRY,
         background_path=None,search_bounds=None,empty_prefix_frames=0,
         region_contract='target_ground_v1',support_history_guard=False,
         change_acquisition=False,history_hold_gate=False,human_entry_gate=True):
    out=out.absolute();roots=(ROOT/'docs/evidence',ROOT/'docs/human_fall/evidence')
    if not any(out.resolve().is_relative_to(r.resolve()) for r in roots) or any(out.resolve()==r.resolve() for r in roots) or any(p.is_symlink() or p.is_junction() for p in [out,*out.parents] if p.exists()):
        raise ValueError('new evidence directory required')
    out.mkdir(parents=True,exist_ok=False)
    start=time.time()
    src=source(session)
    settings=json.loads(Path(settings_path).read_text(encoding='utf8'))
    background=None if background_path is None else json.loads(Path(background_path).read_text(encoding='utf8'))
    if background is not None and background.get('frame_id')!='RAW/innolidar':
        src.close();raise ValueError('background coordinate mismatch')
    if background is not None and empty_prefix_frames:
        src.close();raise ValueError('choose explicit background or declared empty prefix')
    if empty_prefix_frames < 0 or empty_prefix_frames >= len(src.frames):
        src.close();raise ValueError('empty prefix must leave processing frames')
    put(out/'RUN.json',dict(epoch=start,argv=sys.argv,source_sha={p.name:sha(p) for p in HERE.glob('*.py')},
        pipeline=pipeline,session=str(src.folder),sid=src.sid,input_sha=src.binding,
        input_scope=dict(kind='historical_foreground_ledger',raw_roi=LEGACY_FOREGROUND_BOUNDS,
            note='Region contract changes only the region stage, not historical input membership')
            if pipeline=='foreground' else dict(kind='raw_sensor',historical_roi_applied=False),
        settings=settings,settings_sha=sha(settings_path),empty_prefix_frames=empty_prefix_frames,
        region_contract=region_contract,
        human_entry_gate=human_entry_gate,
        candidate_history=dict(policy='experimental_guard' if support_history_guard else 'evidence_only',
            parameters=dict(cell_m=.1,center_gate_m=.5,max_gap_s=.3,min_support_overlap=.1),
            change_acquisition=dict(enabled=change_acquisition,
                min_frames=5,min_displacement_m=.3,
                selection_basis='causal_change_not_human_classification'),
            history_hold_gate=dict(enabled=history_hold_gate,
                policy='same_history_id_only'),
            semantic='UNKNOWN',no_online_background=True),
        search_bounds=None if search_bounds is None else search_bounds.tolist(),
        background=None if background_path is None else dict(path=str(Path(background_path).resolve()),sha256=sha(background_path)),
        ground=dict(path=str(Path(ground_path).resolve()),sha256=sha(ground_path)),
        fall=dict(core_sha={p.name:sha(p) for p in (ROOT/'src/human_fall_detection/core').glob('*.py')},
                  adapter_sha=sha(HERE/'project_fall.py'),confirmed='DISABLED_NO_HUMAN_LABEL',
                  max_state='suspected',position_policy='prediction_never_used_as_observation'),
        ledger_sha=sha(S07/'FOREGROUND_LEDGER.npz') if pipeline=='foreground' else None,
        data='REUSED_DEVELOPMENT',effect_metrics='UNKNOWN',
        variants=['orientation','partition'],frames=len(src.frames)))
    try:
        with (np.load(S07/'FOREGROUND_LEDGER.npz',allow_pickle=False) if pipeline=='foreground' else nullcontext(None)) as ledger:
            for name,partition in [('orientation',False),('partition',True)]:
                timings=[];stages=[]
                records,resets=process(src,ledger,partition,ground_path,settings,background,
                    search_bounds,empty_prefix_frames,timings,region_contract,stages,support_history_guard,
                    change_acquisition,history_hold_gate,human_entry_gate)
                put(out/(name+'_frames.jsonl'),''.join(json.dumps(r,separators=(',',':'),allow_nan=False)+'\n' for r in records))
                locked=[r for r in records if r['track']['status']=='locked']
                ids=sorted({r['track']['track_id'] for r in locked})
                put(out/(name+'_summary.json'),dict(frames=len(records),
                    acquisition_counts=dict(Counter(r['acquisition']['status'] for r in records)),
                    track_counts=dict(Counter(r['track']['status'] for r in records)),
                    first_lock_s=locked[0]['t'] if locked else None,track_ids=ids,reacquisitions=max(0,len(ids)-1),
                    transitions=[dict(fi=r['fi'],t=r['t'],**r['acquisition']) for i,r in enumerate(records)
                        if i==0 or r['acquisition']['status']!=records[i-1]['acquisition']['status']],
                    effect_metrics='UNKNOWN'))
                put(out/(name+'_timings.json'),dict(seconds=timings,p50=float(np.median(timings)),
                    p95=float(np.quantile(timings,.95)),p99=float(np.quantile(timings,.99)),max=max(timings),stages=stages,
                    platform='PC; not board performance; processing only, no live queue/publication age'))
                put(out/(name+'_epochs.json'),dict(reset_frames=resets,policy='invalidate orientation and calibration after rejected source frame; no coordinate history'))
                print(name,'done',flush=True)
                # Release the full ledger before evaluating the next variant.
                del records,locked
    finally:src.close()
    put(out/'FINISHED.json',dict(seconds=time.time()-start,exit_code=0))


if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--session',type=Path);ap.add_argument('--ground',type=Path,default=LEVELING)
    ap.add_argument('--pipeline',choices=['raw','foreground'],default='raw',
                    help='foreground retains its historical ledger and RAW ROI regardless of region contract')
    ap.add_argument('--region-contract',choices=['legacy_raw_roi','target_ground_v1'],default='target_ground_v1')
    ap.add_argument('--candidate-settings',type=Path,default=GEOMETRY)
    ap.add_argument('--support-history-guard',action='store_true',
                    help='experimental support-conflict rejection; known body-fragment regression, not default')
    ap.add_argument('--change-acquisition',action='store_true',
                    help='experimental single moving-history acquisition cue; semantic unknown, not human classification')
    ap.add_argument('--history-hold-gate',action='store_true',
                    help='experimental hold only the acquired history id; other histories cannot replace the target')
    ap.add_argument('--legacy-geometric-acquisition',action='store_true',
                    help='comparison only: allow original geometric acquisition without required height/recent motion')
    ap.add_argument('--background',type=Path)
    ap.add_argument('--empty-prefix-frames',type=int,default=0,
                    help='Explicitly declare an empty warmup prefix; freeze only after consuming it')
    ap.add_argument('--search-bounds',type=float,nargs=6,metavar=('XMIN','XMAX','YMIN','YMAX','ZMIN','ZMAX'))
    a=ap.parse_args();bounds=None if a.search_bounds is None else np.asarray(a.search_bounds).reshape(3,2)
    if bounds is not None and (not np.isfinite(bounds).all() or np.any(bounds[:,0]>=bounds[:,1])):
        ap.error('finite increasing search bounds required')
    main(a.out,a.session,a.ground,a.pipeline,a.candidate_settings,a.background,bounds,a.empty_prefix_frames,
         a.region_contract,a.support_history_guard,a.change_acquisition,a.history_hold_gate,
         not a.legacy_geometric_acquisition)

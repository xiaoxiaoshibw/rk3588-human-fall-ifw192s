"""Local raw IFW192S replay; optional ML prediction never feeds the geometry chain."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time
import numpy as np
from lidar_numpy_runtime import CausalCache, NumpyForest
from train_public_lidar import sha

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src/human_fall_detection'))
sys.path.insert(0,str(ROOT/'src/human_fall_detection/scripts'))
import roi_ablation as harness
import roi_timing
from core.pipeline import ReplayPipeline
from core.capture_input import ROW_DTYPE, POINT_STRIDE_BYTES


def percentiles(values):
    a=np.asarray(values)*1000
    return {'samples':len(a),'p50_ms':float(np.percentile(a,50)),
            'p95_ms':float(np.percentile(a,95)),'max_ms':float(a.max())} if len(a) else {'samples':0}


def run(session_dir, model_path, out):
    start=time.perf_counter();session=harness.load_session(session_dir);initialization=time.perf_counter()-start
    model=NumpyForest(model_path);ground=harness.load_ground(harness.DEFAULT_GROUND)
    calibration=sha(harness.DEFAULT_GROUND)
    original=ReplayPipeline.step
    reference=None; runs=[]; all_rows=[]; feature_inputs=[]; numpy_probabilities=[]
    # One warm-up pair followed by three serial, interleaved measured pairs.
    for round_index in range(4):
        for enabled in ([False,True] if round_index%2==0 else [True,False]):
            cache=CausalCache(30);rows=[];feature_ms=[];infer_ms=[];total_ms=[];decode_ms=[];processing_ms=[]
            digest=hashlib.sha256(); first_ready=None; segment_start=None; reset_count=0
            with (session_dir/'points.bin').open('rb') as stream:
                def observed(self,cloud,stamp,epoch,seq):
                    nonlocal first_ready,segment_start,reset_count
                    began=time.perf_counter();frame=session['frames'][seq]
                    stream.seek(frame['offset_points']*POINT_STRIDE_BYTES)
                    payload=stream.read(frame['count_points']*POINT_STRIDE_BYTES)
                    if len(payload)!=frame['count_points']*POINT_STRIDE_BYTES:raise ValueError('Truncated frame')
                    packed=np.frombuffer(payload,dtype=ROW_DTYPE)
                    raw=np.column_stack((packed['x'],packed['y'],packed['z'])).astype(np.float64)
                    if not np.isfinite(raw).all():raise ValueError('Nonfinite raw frame')
                    raw_done=time.perf_counter()
                    np.testing.assert_array_equal(raw,session['points'][frame['offset_points']:frame['offset_points']+frame['count_points']])
                    if seq<50:raw=np.empty((0,3))
                    decoded=time.perf_counter()
                    result=original(self,raw,stamp,epoch,seq)
                    step_done=time.perf_counter()
                    digest.update(json.dumps(dict(result=result,baseline=self.baseline),sort_keys=True,allow_nan=False).encode())
                    chain_done=time.perf_counter();feature_s=infer_s=0.;prediction=None;probabilities=None
                    targets=result['target_source_rows'];track=result['track'];before=len(cache.frames)
                    if enabled:
                        if len(targets)<10 or track['track_status']!='locked' or track['position_predicted']:
                            cache.clear();segment_start=None
                        else:
                            fstart=time.perf_counter()
                            x=cache.push(raw[np.asarray(targets,dtype=int)],stamp,
                                         (session['sid'],track['track_id']),
                                         (epoch,track['action_generation'],track['selection_version']),
                                         (calibration,track['calibration_version']))
                            feature_s=time.perf_counter()-fstart
                            if len(cache.frames)==1:
                                segment_start=stamp;reset_count+=1
                            if x is not None:
                                istart=time.perf_counter();p=model.predict_proba(x[None,:])[0]
                                infer_s=time.perf_counter()-istart;prediction=int(model.classes[np.argmax(p)])
                                probabilities=p.tolist()
                                if first_ready is None:first_ready={'frame':seq,'segment_start_s':segment_start,
                                    'source_time_s':stamp,'warmup_wait_s':stamp-segment_start,'frames':30}
                                if round_index==1:
                                    feature_inputs.append(x);numpy_probabilities.append(p)
                    finished=time.perf_counter()
                    if seq>=50:
                        feature_ms.append(feature_s);infer_ms.append(infer_s);decode_ms.append(decoded-began)
                        # Parity serialization and assertions measured separately from the processing path.
                        total_ms.append((decoded-began)+(chain_done-decoded)+(finished-chain_done))
                        processing_ms.append((raw_done-began)+(step_done-decoded)+(finished-chain_done))
                    rows.append({'frame':seq,'source_time_s':stamp,'target_rows':targets,'track':track,
                                 'prediction':prediction,'probabilities':probabilities,'cache_frames':len(cache.frames),
                                 'feature_s':feature_s,'inference_s':infer_s,'raw_read_decode_s':decoded-began,
                                 'whole_observed_call_s':finished-began})
                    return result
                ReplayPipeline.step=observed
                try:
                    roi_timing.replay(session,harness.build_arm_settings('A'),ground,50,len(session['frames']))
                finally:ReplayPipeline.step=original
            value=digest.hexdigest()
            if reference is None:reference=value
            assert reference==value,'ML sidecar changed complete geometry-chain output'
            if round_index:
                runs.append({'round':round_index,'model_enabled':enabled,'raw_read_decode':percentiles(decode_ms),
                             'feature_cache_and_summary':percentiles(feature_ms),'inference_all_frames':percentiles(infer_ms),
                             'inference_ready_only':percentiles([v for v in infer_ms if v>0]),
                             'whole_observed_call_including_audit':percentiles(total_ms),
                             'raw_decode_chain_model_excluding_audit':percentiles(processing_ms),
                             'warmup':first_ready,'resets':reset_count,'full_output_sha256':value})
                if round_index==1 and enabled:all_rows=rows
            print('replay',round_index,enabled,'ready',sum(r['prediction'] is not None for r in rows),flush=True)
    out.mkdir(parents=True,exist_ok=False)
    with (out/'frames.jsonl').open('x',encoding='utf-8') as f:
        for row in all_rows:f.write(json.dumps(row,allow_nan=False)+'\n')
    np.savez_compressed(out/'inference_inputs.npz',X=np.asarray(feature_inputs),p=np.asarray(numpy_probabilities))
    result={'session':session['sid'],'frames':len(session['frames']),'initial_decode_and_validation_s':initialization,
            'meta_sha256':sha(session_dir/'meta.json'),'points_sha256':sha(session_dir/'points.bin'),
            'calibration_path':str(harness.DEFAULT_GROUND),'calibration_sha256':calibration,
            'settings':harness.build_arm_settings('A'),'model_sha256':sha(model_path),'runs':runs,
            'complete_geometry_baseline_parity':True,'accuracy':'UNKNOWN','fall_recall':'UNKNOWN',
            'sensor_axis_alignment_to_MMFi':'UNKNOWN; raw XYZ passed unchanged, no target-domain alignment fitted',
            'scope':'PC raw file read/decode + full geometry chain + optional model sidecar; warm filesystem cache; no scheduling/ROS/network/display',
            'background':'first 50 frames declared empty by existing development harness; not independent person GT',
            'timing_limit':'includes parity assertions and full-output serialization, not board performance; model does not control fall state',
            'deployment':'NOT_DEPLOYED'}
    (out/'SUMMARY.json').write_text(json.dumps(result,indent=2),encoding='utf-8')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--session',type=Path,required=True)
    p.add_argument('--model',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    run(a.session,a.model,a.output)

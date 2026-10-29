"""只读合并W2、同步与测量来源审计；可运行既有规则旁路，不改变推理。"""
import argparse
import collections
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(Path(__file__).resolve().parent))
sys.path.insert(0,str(ROOT/'src/human_fall_detection'))
from core.capture_input import ROW_DTYPE, read_source_meta
from core.range_background import RayBackground
from core.range_components import label_components
from core.range_contract import binding_tuple, load_ground
from core.range_denoise import denoise
from core.range_image import ScanGrid
from core.lidar_candidates import rebuild_candidate
from core.features import FeatureExtractor
from core.fall_state import FallStateMachine
from core.baseline import StanceBaselineCollector
from core.range_posture import PostureObserver
from core.range_tracker import INFERENCE_KEYS
from sync_audit import audit as sync_audit, file_binding, read_json, digest, integer, timing

CALIBRATION=ROOT/'src/inno_lidar_ros/config/ifw192s'


def inference_serial(record):
    # W2 replay predates the runtime subset fix and hashes the complete tracker
    # record. Verify either exact known schema; never rehash or rewrite a ledger.
    for keys in (INFERENCE_KEYS, INFERENCE_KEYS + ('single_person_policy', 'dropped_fragments')):
        value=json.dumps({k:record[k] for k in keys if k in record},sort_keys=True,allow_nan=False)
        if hashlib.sha256(value.encode()).hexdigest()==record['inference_sha256']:
            return value
    raise ValueError('inference record SHA mismatch')


def row_statistics(original_rows, output_rows):
    """只审计来源，不采样；重复输出不增加真实测量。空分母返回null。"""
    output=list(output_rows)
    valid=lambda r: isinstance(r,(int,np.integer)) and not isinstance(r,(bool,np.bool_)) and r>=0
    if isinstance(original_rows,np.ndarray) and original_rows.ndim==1 and np.issubdtype(original_rows.dtype,np.integer):
        if np.any(original_rows<0) or len(np.unique(original_rows))!=len(original_rows):
            raise ValueError('original rows must be unique nonnegative integers')
        original=original_rows.tolist()
    else:
        original=list(original_rows)
        if not all(valid(r) for r in original) or len(set(original))!=len(original):
            raise ValueError('original rows must be unique nonnegative integers')
    legal=[int(r) for r in output if valid(r)]
    unique=set(legal); allowed=set(original)
    return dict(original_unique=len(original),output_rows=len(output),output_unique=len(unique),
        repeated_output_rows=len(legal)-len(unique),invalid_output_rows=len(output)-len(legal),
        foreign_unique_rows=len(unique-allowed),removed_unique_rows=len(allowed-unique),
        duplicate_fraction=(len(legal)-len(unique))/len(output) if output else None,
        denominator_reason=None if output else 'no_output_rows')


def integer_clock_ns(values):
    # epoch纳秒先按整数相减，避免转float后把1ns回退变成重复。
    result=timing(values)
    for key in ('median_positive_interval_s','max_positive_interval_s'):
        if result[key] is not None:result[key]/=1e9
    result['clock_storage']='integer_nanoseconds_before_difference'
    return result


class RuleBaseline:
    def __init__(self,session,ground,ground_sha):
        self.session=session; self.ground=ground; self.calibration=ground_sha or 'ground_unavailable'
        self.features=FeatureExtractor(session)
        self.state=FallStateMachine(session,dict(mode_verified=False,allow_confirmed=False))
        self.posture=PostureObserver()
        self.baseline_collector=StanceBaselineCollector(session)

    def update(self,frame,record):
        rows=record['target_source_rows']
        candidate=None
        target=next((t for t in record['tracks'] if t['track_id']==record['target_track_id']),None)
        if (record['target_track_id'] is not None and (not target or not target['observed']
                or target['position_predicted'] is not False or target['status']!='tracked'
                or target['source_rows']!=rows)):
            raise ValueError('rule input is not a stable measured target')
        if rows:
            xyz=frame.xyz[rows].astype(float)
            candidate=rebuild_candidate(xyz,np.arange(len(rows)),ground=self.ground,
                frame_id=self.ground['frame'] if self.ground else 'unbound')
        track_id=record['target_track_id'] or record.get('continuity_track_id')
        observation=dict(session_id=self.session,track_id=track_id,
            time_epoch=record['generation'],action_generation=record['generation'],
            selection_version=record['generation'],calibration_version=self.calibration,
            source_stamp_s=record['time_s'],
            track_status=('locked' if rows else 'held' if track_id else
                          'ambiguous' if record.get('target_reason') in
                          ('selected_target_ambiguous', 'single_person_selection_ambiguous') else 'unselected'),
            position_predicted=False,candidate=candidate,
            ground_relative_available=self.ground is not None)
        if self.ground is None:
            if self.baseline_collector.status in ('pending','ready'):
                self.baseline_collector.invalidate('ground_monitor_unavailable')
            snapshot=self.baseline_collector.snapshot()
        else:
            snapshot=self.baseline_collector.feed_automatic(candidate,dict(
                track_id=track_id,time_epoch=record['generation'],
                selection_version=record['generation'],action_generation=record['generation'],
                calibration_version=self.calibration,track_status=observation['track_status'],
                position_predicted=False),record['time_s'])
        baseline=snapshot['baseline']
        features=self.features.update(observation,baseline=baseline)
        posture=self.posture.update(features,record,frame.binding)
        state=self.state.update(features,observation,baseline=baseline,posture=posture)
        assert not state['confirmed_enabled'] and state['new_event'] is None
        return dict(frame=record['frame'],time_s=record['time_s'],track_id=record['target_track_id'],
            source_rows=list(rows),input_inference_sha256=record['inference_sha256'],
            features=features,state=state,posture=posture,baseline=snapshot,semantic='UNKNOWN')


def replay_bindings(replay,source):
    paths={name:replay/name for name in ('SUMMARY.json','CONFIG.json','frames.jsonl')}
    pinned={name:file_binding(path) for name,path in paths.items()}
    if any(v is None for v in pinned.values()):raise ValueError('incomplete W2 replay')
    summary=read_json(paths['SUMMARY.json']); config=read_json(paths['CONFIG.json'])
    if summary.get('schema')!='range_tracking_replay_v1':raise ValueError('unsupported replay schema')
    binding=summary.get('source_binding',{})
    if any(binding.get(k)!=source[n]['sha256'] for k,n in
           (('meta_sha256','meta.json'),('points_sha256','points.bin'))):
        raise ValueError('replay source SHA mismatch')
    if pinned['frames.jsonl']['sha256']!=summary.get('frames_sha256'):
        raise ValueError('replay ledger SHA mismatch')
    settings=config.get('settings')
    sha=hashlib.sha256(json.dumps(settings,sort_keys=True,allow_nan=False).encode()).hexdigest()
    if (sha!=config.get('sha256') or sha!=summary.get('config_sha256')
            or config.get('source_binding')!=binding or settings!=summary.get('settings')):
        raise ValueError('replay settings/binding mismatch')
    changes=[]
    manifest=summary.get('source_sha256',{})
    required=[ROOT/'src/human_fall_detection/scripts/replay_range_tracking.py',
              ROOT/'src/human_fall_detection/scripts/replay_range_frontend.py',
              *sorted((ROOT/'src/human_fall_detection/core').glob('*.py'))]
    provided={name.replace('\\','/') for name in manifest}
    changes.extend('missing_source:'+p.relative_to(ROOT).as_posix() for p in required
                   if p.relative_to(ROOT).as_posix() not in provided)
    for name,expected in manifest.items():
        p=(ROOT/name).resolve()
        if Path(name).is_absolute() or ROOT not in p.parents:raise ValueError('unsafe replay source path')
        actual=file_binding(p)
        if actual is None or actual['sha256']!=expected:changes.append(name)
    if not manifest:changes.append('missing_source_manifest')
    return summary,pinned,changes


def check_track_rows(frame,record,components,ground):
    decoded=frame.source_rows[frame.valid]
    retained={c['component_id']:set(c['source_rows'].tolist()) for c in components if c['retained']}
    retained_rows=set().union(*retained.values()) if retained else set()
    output=[]; used=set(); ids=set(); details=[]; missing=0
    for track in record['tracks']:
        tid=track['track_id']
        if tid in ids:raise ValueError('duplicate track id in frame')
        ids.add(tid)
        rows=track['source_rows']
        if (type(track['observed']) is not bool or type(track['position_predicted']) is not bool
                or track['observed']==track['position_predicted']):
            raise ValueError('observed/predicted flag conflict')
        if not track['observed']:
            missing+=1
            if rows or track['features'] is not None or track.get('velocity_m_s') is not None:
                raise ValueError('prediction contains measured rows/features')
            continue
        cids=track['component_ids']
        if len(cids)!=len(set(cids)) or used.intersection(cids) or any(c not in retained for c in cids):
            raise ValueError('component ownership is not one-to-one')
        allowed=set().union(*(retained[c] for c in cids)) if cids else set()
        stats=row_statistics(sorted(allowed),rows)
        if (not rows or stats['invalid_output_rows'] or stats['foreign_unique_rows']
                or stats['repeated_output_rows'] or stats['removed_unique_rows']):
            raise ValueError('track rows are not the unique current component union')
        points=frame.xyz[rows].astype(float); features=track['features']
        if type(features.get('point_count')) is not int or features['point_count']!=len(rows):
            raise ValueError('measured feature point count mismatch')
        for key,actual in (('center_m',np.median(points,axis=0)),('bbox_min_m',points.min(axis=0)),('bbox_max_m',points.max(axis=0))):
            if not np.allclose(features[key],actual,rtol=0,atol=1e-9):raise ValueError('measured geometry mismatch: '+key)
        if ground:
            heights=points@np.asarray(ground['normal'])+ground['offset_m']
            expected=np.percentile(heights,[10,50,90])
            values=[features['height_m'][k] for k in ('p10','median','p90')]
            if not np.allclose(values,expected,rtol=0,atol=1e-9):raise ValueError('measured height mismatch')
        output.extend(rows); used.update(cids)
        details.append(dict(track_id=tid,component_ids=cids,sampling=stats,
                            rows_sha256=digest(rows),mode='all_current_component_measurements'))
    overall=row_statistics(decoded,output)
    if overall['repeated_output_rows'] or overall['foreign_unique_rows']:raise ValueError('cross-track duplicate/foreign rows')
    target=next((t for t in record['tracks'] if t['track_id']==record['target_track_id']),None)
    if record['target_track_id'] is not None and target is None:raise ValueError('dangling target track id')
    expected=target['source_rows'] if target else []
    if (record['target_source_rows']!=expected or
            (target and (not target['observed'] or target['status']!='tracked'))):
        raise ValueError('target is not the selected stable measured track')
    if record['target_features']!=(target['features'] if target else None):raise ValueError('target feature mismatch')
    return dict(tracks=details,measured_output=overall,prediction_or_ambiguous_tracks=missing,
        retained_component_rows=len(retained_rows),unassigned_retained_rows=len(retained_rows-set(output)),
        target_rows=len(expected),removal_scope='not selected relative to decoded/retained sets; not physical point loss')


def run(session,out,replay_run=None,ground_path=None,alignment_path=None,previous=None,limit=None):
    session,out=Path(session).resolve(),Path(out).resolve()
    for protected in (session,ROOT/'data',ROOT/'captures'):
        p=protected.resolve()
        if out==p or p in out.parents or out in session.parents:raise ValueError('output must be outside source data')
    if out.exists():raise ValueError('output already exists')
    audit_paths=[Path(__file__).resolve(),Path(__file__).with_name('sync_audit.py').resolve(),
                 *sorted((ROOT/'src/human_fall_detection/core').glob('*.py')),
                 CALIBRATION/'ifw192s_azimuth_192x256.csv',CALIBRATION/'ifw192s_elevation_192x256.csv']
    audit_sources={str(p.relative_to(ROOT)):file_binding(p) for p in audit_paths}
    sync=sync_audit(session,alignment_path)
    if sync['binding']['meta.json'] is None or sync['binding']['points.bin'] is None:raise ValueError('missing LiDAR source bytes')
    raw_meta=(session/'meta.json').read_bytes()
    declared=json.loads(raw_meta.decode('utf-8-sig'))
    meta=read_source_meta(raw_meta,declared.get('sensor',{}).get('frame_id'),'m')
    frames=meta.get('frames',[]); offset=0
    if not isinstance(frames,list) or not frames:raise ValueError('empty source frames')
    for info in frames:
        if integer(info.get('offset_points'),'offset')!=offset:raise ValueError('noncontiguous source frames')
        offset+=integer(info.get('count_points'),'count')
    if offset!=meta.get('total_points') or offset*ROW_DTYPE.itemsize!=sync['binding']['points.bin']['bytes']:
        raise ValueError('source byte/count mismatch')
    az,el=(CALIBRATION/name for name in ('ifw192s_azimuth_192x256.csv','ifw192s_elevation_192x256.csv'))
    grid=ScanGrid.from_csv(az,el)
    changes=[]; replay=None; replay_files=None; record_stream=None; summary=None
    source=dict(session=session.name,meta_sha256=sync['binding']['meta.json']['sha256'],
        points_sha256=sync['binding']['points.bin']['sha256'],coordinate='RAW/'+meta['sensor']['frame_id'],
        units='m',coordinate_transform='identity',grid_sha256=grid.sha256,epoch='source_header_epoch',
        azimuth_sha256=file_binding(az)['sha256'],elevation_sha256=file_binding(el)['sha256'])
    if replay_run:
        replay=Path(replay_run).resolve()
        summary,replay_files,changes=replay_bindings(replay,sync['binding'])
        if summary['source_binding']!=source:raise ValueError('replay coordinate/grid/session mismatch')
        settings=summary['settings']
        if (settings.get('frontend')!='range_v1' or settings.get('merge') is not False
                or settings.get('background_update') is not False):raise ValueError('unsupported replay frontend settings')
        count=integer(summary['frames'],'replay frames')
        if not 0<count<=len(frames):raise ValueError('invalid replay frame count')
        if not 1<=integer(settings.get('empty_prefix_frames'),'empty prefix')<count:
            raise ValueError('invalid replay prefix length')
        if limit is not None:raise ValueError('limit is only for source-only mode; use a causal-prefix replay')
    else:
        count=len(frames) if limit is None else integer(limit,'limit')
        if not 0<count<=len(frames):raise ValueError('invalid source-only frame count')
    ground_files={}; ground=None; ground_sha=None
    if ground_path:
        gp=Path(ground_path).resolve()
        ground_before=file_binding(gp)
        declaration=read_json(gp)
        provenance=Path(declaration['provenance']['source']).resolve()
        ground_files={str(gp):ground_before,str(provenance):file_binding(provenance)}
        ground=load_ground(gp,source)
        if ground_files!={p:file_binding(Path(p)) for p in ground_files}:raise ValueError('ground changed while reading')
        ground_sha=ground_before['sha256']
    if summary and ground_sha!=summary['settings'].get('ground_sha256'):
        raise ValueError('ground must exactly match replay configuration, including unavailable')
    alignment_binding='NOT_PROVIDED'
    if alignment_path:
        declared_binding=read_json(alignment_path).get('source_binding')
        if declared_binding is None:alignment_binding='UNBOUND'
        elif declared_binding!={k:sync['binding'][k] for k in ('meta.json','points.bin','joint.json','camera_frames.jsonl','camera.mjpeg')}:
            raise ValueError('alignment source binding mismatch')
        else:alignment_binding='MATCH'
    joint=read_json(session/'joint.json') if sync['binding']['joint.json'] else None
    out.mkdir(parents=True,exist_ok=False)
    totals=collections.Counter(); rules=RuleBaseline(session.name,ground,ground_sha) if summary and not changes else None
    states=collections.Counter(); prefix=[]; bg=None; ledger_digest=hashlib.sha256(); inference_digest=hashlib.sha256()
    t0=None; processed=0
    try:
        if replay and not changes:record_stream=(replay/'frames.jsonl').open(encoding='utf-8')
        with (session/'points.bin').open('rb') as stream, (out/'SOURCE_ROWS.jsonl').open('x',encoding='utf-8') as ledger, \
             (out/'RULE_BASELINE.jsonl').open('x',encoding='utf-8') as rule_ledger:
            for index,info in enumerate(frames[:count] if not changes else []):
                raw=stream.read(info['count_points']*ROW_DTYPE.itemsize)
                if len(raw)!=info['count_points']*ROW_DTYPE.itemsize:raise ValueError('source truncated')
                frame=grid.decode(raw,binding_tuple(source))
                decoded=frame.source_rows[frame.valid].tolist()
                rejected={k:len(v) for k,v in frame.rejected.items()}
                partition=decoded+[int(r) for rows in frame.rejected.values() for r in rows]
                if len(partition)!=len(set(partition)) or sorted(partition)!=list(range(info['count_points'])):
                    raise ValueError('decode rows do not conserve raw measurements')
                row=dict(frame=index,offset_points=info['offset_points'],raw_rows=info['count_points'],
                    decoded_unique_rows=len(decoded),decode_rejected=rejected,raw_sha256=hashlib.sha256(raw).hexdigest(),
                    decode_duplicate_echo_rows=rejected['duplicate_rows'],sampling_mode='not_performed')
                totals['raw_rows']+=info['count_points']; totals['decoded_unique_rows']+=len(decoded)
                for key,value in rejected.items():totals['decode_'+key]+=value
                if record_stream:
                    line=record_stream.readline()
                    if not line:raise ValueError('replay shorter than declared')
                    record=json.loads(line)
                    serial=json.dumps(record,sort_keys=True,allow_nan=False)
                    ledger_digest.update(serial.encode())
                    inference=inference_serial(record)
                    inference_digest.update(inference.encode())
                    stamp=integer(info.get('stamp_sec'),'stamp_sec')*10**9+integer(info.get('stamp_nanosec'),'stamp_nanosec')
                    if t0 is None:t0=stamp
                    if (record['frame']!=index or record['offset_points']!=info['offset_points']
                            or record['raw_sha256']!=row['raw_sha256'] or record['source_binding']!=source
                            or record['config_sha256']!=summary['config_sha256'] or record['time_s']!=(stamp-t0)/1e9):
                        raise ValueError('replay frame/source/header clock binding mismatch')
                    if bg is None:
                        prefix.append(frame); foreground=np.zeros(grid.shape,dtype=bool)
                    else:
                        foreground=bg.foreground(frame)['mask']
                        with np.errstate(invalid='ignore'):foreground&=(frame.range_m>=.1)&(frame.range_m<=8)
                    clean=denoise(frame,foreground,settings['min_neighbours'])
                    _,components=label_components(frame,clean['mask'],settings['min_component_points'])
                    if index+1==settings['empty_prefix_frames']:
                        bg=RayBackground(prefix,empty_prefix_declared=True,min_observations=min(10,len(prefix))); prefix.clear()
                    row['replay']=check_track_rows(frame,record,components,ground)
                    totals['emitted_track_rows']+=row['replay']['measured_output']['output_rows']
                    totals['retained_component_rows']+=row['replay']['retained_component_rows']
                    for key in ('repeated_output_rows','foreign_unique_rows','invalid_output_rows'):
                        totals[key]+=row['replay']['measured_output'][key]
                    totals['unassigned_retained_rows']+=row['replay']['unassigned_retained_rows']
                    totals['prediction_or_ambiguous_tracks']+=row['replay']['prediction_or_ambiguous_tracks']
                    totals['target_rows']+=row['replay']['target_rows']
                    totals['target_observed_frames']+=bool(row['replay']['target_rows'])
                    rule=rules.update(frame,record)
                    rule_ledger.write(json.dumps(rule,sort_keys=True,allow_nan=False)+'\n')
                    states[rule['state']['state']]+=1
                ledger.write(json.dumps(row,sort_keys=True,allow_nan=False)+'\n')
                processed+=1
            if record_stream and record_stream.readline():raise ValueError('replay longer than declared')
        if summary and not changes:
            if (ledger_digest.hexdigest()!=summary['algorithm_output_sha256']
                    or inference_digest.hexdigest()!=summary['inference_output_sha256']):
                raise ValueError('replay aggregate SHA mismatch')
    finally:
        if record_stream:record_stream.close()
    camera_ns=[]
    if sync['binding']['camera_frames.jsonl']:
        with (session/'camera_frames.jsonl').open(encoding='utf-8-sig') as stream:
            camera_ns=[r.get('recv_unix_ns') if type(r.get('recv_unix_ns')) is int else None
                       for r in map(json.loads,stream)]
    quality=dict(header_integer_ns=integer_clock_ns([
        f['stamp_sec']*10**9+f['stamp_nanosec'] if type(f.get('stamp_sec')) is int and type(f.get('stamp_nanosec')) is int
        and 0<=f['stamp_nanosec']<10**9 else None for f in frames]),
        joint_state=joint.get('state') if joint else None,joint_error=joint.get('error') if joint else None,
        joint_declared_lidar_frames=joint.get('radar_frames') if joint else None,
        joint_declared_camera_frames=joint.get('camera_frames') if joint else None,
        actual_lidar_frames=len(frames),actual_camera_index_frames=sync['quality']['camera_host_receipt_time']['n'],
        camera_receipt_integer_ns=integer_clock_ns(camera_ns),
        current_lidar_bytes_complete=True,actual_sampling_loss='UNKNOWN',physical_sync_error_s='UNKNOWN')
    totals['measured_output_fraction_denominator']=totals['emitted_track_rows']
    previous_state=None; previous_sha=None
    audit_binding=dict(source=sync['binding'],replay=replay_files,ground_sha256=ground_sha,
        ground_files=ground_files,audit_sources=audit_sources,
        mode='replay_and_rules' if summary else 'source_only',frame_range=[0,count])
    if previous:
        previous_raw=(Path(previous)/'SUMMARY.json').read_bytes()
        old=json.loads(previous_raw.decode('utf-8-sig')); previous_sha=hashlib.sha256(previous_raw).hexdigest()
        old_digest=old.pop('content_sha256',None)
        if old.get('schema')!='range_experiment_audit_v1' or old_digest!=digest(old):
            raise ValueError('previous combined audit content SHA mismatch')
        previous_state='UNCHANGED' if old.get('binding')==audit_binding else 'STALE'
    # 所有源读取/质量计算之后再终检；地面和provenance同样属于输入。
    if sync['binding']!=sync_audit(session,alignment_path)['binding']:raise ValueError('source changed during combined audit')
    if replay_files and replay_files!={k:file_binding(replay/k) for k in replay_files}:raise ValueError('replay changed during combined audit')
    if ground_files!={p:file_binding(Path(p)) for p in ground_files}:raise ValueError('ground changed during combined audit')
    if audit_sources!={str(p.relative_to(ROOT)):file_binding(p) for p in audit_paths}:
        raise ValueError('audit source/calibration changed during run')
    result=dict(schema='range_experiment_audit_v1',status='STALE' if changes else 'SOFTWARE_AUDITED',
        source_binding=source,binding=audit_binding,
        source_code_changes=changes,previous_status=previous_state,previous_report_sha256=previous_sha,
        frames_processed=processed,totals=dict(totals),
        measured_duplicate_fraction=(totals['repeated_output_rows']/totals['emitted_track_rows']
                                    if totals['emitted_track_rows'] else None),
        duplicate_denominator_reason=None if totals['emitted_track_rows'] else 'no_emitted_measurement_rows',
        input_replay_inference_sha256=summary['inference_output_sha256'] if summary else None,
        sync_status=sync['status'],alignment_binding=alignment_binding,temporal_link_applied=False,
        quality=quality,rule_baseline=dict(executed=rules is not None,states=dict(states),confirmed_enabled=False,
            baseline_supplied=False,scope='existing FeatureExtractor/FallStateMachine on identical current rows; no fitted model or HMM comparison'),
        source_rows_sha256=file_binding(out/'SOURCE_ROWS.jsonl')['sha256'],
        rule_baseline_sha256=file_binding(out/'RULE_BASELINE.jsonl')['sha256'],
        human_point_precision_recall='UNKNOWN',human_identity_switch_rate='UNKNOWN',fall_bathroom_effectiveness='UNKNOWN',
        performance_scope='offline audit only; never added to or substituted for W1/W2 algorithm timing')
    result['content_sha256']=digest(result)
    for name,value in (('SYNC_AUDIT.json',sync),('SUMMARY.json',result)):
        with (out/name).open('x',encoding='utf-8') as f:json.dump(value,f,ensure_ascii=False,indent=2,allow_nan=False)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--session',required=True,type=Path)
    parser.add_argument('--out',required=True,type=Path)
    parser.add_argument('--replay-run',type=Path)
    parser.add_argument('--ground',type=Path)
    parser.add_argument('--alignment',type=Path)
    parser.add_argument('--previous',type=Path)
    parser.add_argument('--limit',type=int)
    args=parser.parse_args()
    result=run(args.session,args.out,args.replay_run,args.ground,args.alignment,args.previous,args.limit)
    print(json.dumps(dict(status=result['status'],frames=result['frames_processed'],totals=result['totals'],sync=result['sync_status'])))

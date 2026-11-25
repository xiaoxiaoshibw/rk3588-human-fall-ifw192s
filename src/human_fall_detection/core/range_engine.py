"""Shared live recognition engine; no ROS, sockets, Qt or device control."""
import base64
import hashlib
import json
import math
from pathlib import Path
import struct
import time
import uuid
import numpy as np
from .range_contract import binding_tuple
from .range_ground_alert import GroundAlertObserver,GroundAlertGapCandidate
from .range_demo_alert import DemoAlert
from .range_live import pointcloud_rows,preview_rgb
from .range_posture import PostureObserver
from .range_runtime import RangeRuntime, SettingsDriftError
from .range_skeleton import estimate,project_regions
from .range_png import png
from .range_wire import parse_cloud
from .range_site_ground import site_ground
from .human_belief import HumanPhysicalEvaluator, REVISION as HUMAN_PHYSICAL_REVISION, evaluator_failure_output
from .instant_tracker import InstantHumanTracker
from .silent_ground_refiner import GravityUpEstimator, SilentGroundRefiner


def _sanitize_json_value(obj):
    if isinstance(obj, dict):
        return {str(k): _sanitize_json_value(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize_json_value(v) for v in obj]
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, (float, np.floating)):
        v = float(obj)
        return v if math.isfinite(v) else None
    if isinstance(obj, np.ndarray):
        return _sanitize_json_value(obj.tolist())
    return obj


def _display_basis(normal):
    up = np.asarray(normal, dtype=np.float64)
    norm = float(np.linalg.norm(up))
    if norm <= 1e-9 or not np.isfinite(up).all():
        return None
    up = up / norm
    forward = np.array([1.0, 0.0, 0.0], dtype=np.float64) - up * float(up[0])
    if float(np.linalg.norm(forward)) < 1e-6:
        forward = np.array([0.0, 1.0, 0.0], dtype=np.float64) - up * float(up[1])
    forward = forward / float(np.linalg.norm(forward))
    left = np.cross(up, forward)
    return np.stack([forward, left, up])


def _compact_bbox(xyz, ground=None):
    if xyz is None or len(xyz) == 0:
        return None
    pts = np.asarray(xyz, dtype=np.float64)
    raw_min = np.min(pts, axis=0)
    raw_max = np.max(pts, axis=0)
    raw_center = np.median(pts, axis=0)
    out = dict(
        raw=dict(
            min=[round(float(v), 4) for v in raw_min],
            max=[round(float(v), 4) for v in raw_max],
            center=[round(float(v), 4) for v in raw_center],
        ),
        leveled=None,
    )
    if isinstance(ground, dict) and ground.get('normal') is not None and ground.get('offset_m') is not None:
        basis = _display_basis(ground['normal'])
        if basis is not None:
            lev = pts @ basis.T
            lev[:, 2] += float(ground['offset_m'])
            out['leveled'] = dict(
                min=[round(float(v), 4) for v in np.min(lev, axis=0)],
                max=[round(float(v), 4) for v in np.max(lev, axis=0)],
                center=[round(float(v), 4) for v in np.median(lev, axis=0)],
            )
    return out


def _compact_physical_v1(phys):
    if not isinstance(phys, dict):
        return None

    def _clean_belief(b):
        if not isinstance(b, dict):
            return None
        return {k: v for k, v in b.items() if k != 'source_rows'}

    tracks_out = {}
    for tid, detail in (phys.get('tracks') or {}).items():
        if not isinstance(detail, dict):
            continue
        prior = detail.get('prior')
        if isinstance(prior, dict):
            prior_out = {k: v for k, v in prior.items() if k not in ('thresholds', 'physical_thresholds')}
        else:
            prior_out = prior
        tracks_out[tid] = dict(
            belief=_clean_belief(detail.get('belief')),
            prior=prior_out,
            kinematics=detail.get('kinematics'),
        )

    rec = phys.get('recovery')
    rec_out = None
    if isinstance(rec, dict):
        rec_out = {k: v for k, v in rec.items() if k not in ('core_rows', 'recovered_rows')}

    return _sanitize_json_value(dict(
        variant=phys.get('variant'),
        revision=phys.get('revision'),
        status=phys.get('status'),
        error_codes=list(phys.get('error_codes') or []),
        errors=list(phys.get('errors') or []),
        frame=phys.get('frame'),
        time_s=phys.get('time_s'),
        target_track_id=phys.get('target_track_id'),
        target_belief=_clean_belief(phys.get('target_belief')),
        confirmed_track_ids=list(phys.get('confirmed_track_ids') or []),
        candidate_track_ids=list(phys.get('candidate_track_ids') or []),
        kinematics_noise_floor=phys.get('kinematics_noise_floor'),
        tracks=tracks_out,
        recovery=rec_out,
        timings=phys.get('timings'),
        semantic_truth=phys.get('semantic_truth', 'UNKNOWN'),
    ))


class RangeEngine:
    def __init__(self,grid,frame_id,identity=None,background=None,empty_prefix_frames=None,ground=None,body=False,diagnostics=False,
                 clock=time.monotonic,human_physical_v1=False,single_person_lock=False,
                 instant_start=False,mount_pitch_deg=26.0,mount_roll_deg=0.0,imu_axis_signs=(1.0,1.0,1.0),
                 instant_settings=None,refiner_settings=None):
        self.grid,self.frame_id=grid,frame_id
        self.clock=clock
        self.human_physical_v1=bool(human_physical_v1)
        self.single_person_lock=bool(single_person_lock)
        self.instant_start=bool(instant_start)
        if self.instant_start and (background is not None or empty_prefix_frames is not None):
            raise ValueError('instant_start cannot be combined with explicit background or empty_prefix_frames')
        self.identity=identity or dict(session='live_range_'+uuid.uuid4().hex,coordinate='RAW/'+frame_id,
            units='m',coordinate_transform='identity',grid_sha256=grid.sha256,epoch='live_source_header')
        if self.identity['coordinate']!='RAW/'+frame_id or self.identity['grid_sha256']!=grid.sha256:
            raise ValueError('live source/background binding mismatch')
        self.runtime=None
        self.gravity_estimator=None
        self.ground_refiner=None
        self.instant_tracker=None
        self.instant_physical=None
        self.instant_config_sha=None
        tracker_settings = (dict(single_person_lock=True, drop_fragment_candidates=True)
                            if self.single_person_lock else None)
        if self.instant_start:
            self.gravity_estimator = GravityUpEstimator(dict(
                mount_pitch_deg=mount_pitch_deg,
                mount_roll_deg=mount_roll_deg,
                imu_axis_signs=imu_axis_signs,
            ))
            self.ground_refiner = SilentGroundRefiner(
                self.gravity_estimator, settings=refiner_settings, frame_id=frame_id
            )
            self.instant_tracker = InstantHumanTracker(
                shape=grid.shape,
                gravity_up=self.ground_refiner.normal,
                settings=instant_settings,
            )
            if self.human_physical_v1:
                self.instant_physical = HumanPhysicalEvaluator()
            instant_cfg = dict(
                mode='instant_start_silent_refinement_v1',
                gravity=self.gravity_estimator.settings,
                refiner=self.ground_refiner.settings,
                tracker=self.instant_tracker.settings,
                human_physical_v1=self.human_physical_v1,
            )
            self.instant_config_sha = hashlib.sha256(
                json.dumps(instant_cfg, sort_keys=True, separators=(',', ':')).encode('utf-8')
            ).hexdigest()
        elif background is not None or empty_prefix_frames is not None:
            self.runtime=RangeRuntime(grid,self.identity,empty_prefix_frames=empty_prefix_frames or 50,ground=ground,
                ground_sha=hashlib.sha256(json.dumps(ground,sort_keys=True).encode()).hexdigest() if ground else None,
                detailed=False,human_physical_v1=self.human_physical_v1,tracker_settings=tracker_settings)
            if background is not None:
                if background.binding!=(binding_tuple(self.identity),grid.sha256):raise ValueError('background binding mismatch')
                self.runtime.background=background
        self.body=body;self.defer_body=False;self.body_job=None
        self.diagnostics=bool(diagnostics)
        self.alert=GroundAlertObserver();self.alert_candidate=GroundAlertGapCandidate();self.posture=PostureObserver()
        self.demo_alert=DemoAlert(self.runtime.config['demo_alert'] if self.runtime else None)
        self.index=-1;self.previous=None;self.disabled=None;self.processed=0;self.ground_frame=None
        if self.instant_start:
            self.ground_status=self.ground_refiner.status_dict(self.identity['session'])
        else:
            self.ground_status=dict(available=ground is not None,reason='not_loaded' if ground is None else 'bound')
        self.background_header=getattr(background,'last_declared_header',None)

    def feed_imu(self,ax,ay,az,gx=0.0,gy=0.0,gz=0.0,stamp_s=None):
        """喂入雷达静止 IMU 样本（仅 instant_start 生效；线程安全）。"""
        if self.gravity_estimator is None:
            return False
        return self.gravity_estimator.feed_imu(ax,ay,az,gx,gy,gz,stamp_s=stamp_s)

    def invalidate(self,reason):
        self.disabled=reason;self.clear_history()
        if self.runtime:self.runtime.ground=None
        if self.ground_refiner is not None:
            self.ground_refiner.reset()
        self.ground_status=dict(available=False,reason=reason)

    def clear_history(self):
        config=self.runtime.config if self.runtime else None
        self.alert=GroundAlertObserver(config['ground_alert'] if config else None)
        self.alert_candidate=GroundAlertGapCandidate()
        self.demo_alert=DemoAlert(config['demo_alert'] if config else None)
        self.posture=PostureObserver(config['posture'] if config else None);self.body_job=None
        if self.instant_tracker is not None:
            self.instant_tracker.reset(increment_generation=True)
        if self.instant_physical is not None:
            self.instant_physical.reset()
        if self.runtime:
            from core.features import FeatureExtractor
            from core.fall_state import FallStateMachine
            self.runtime.features=FeatureExtractor(self.identity['session'],config['feature_defaults'])
            self.runtime.state=FallStateMachine(self.identity['session'],config['fall'])
            self.runtime.posture=PostureObserver(config['posture'])
            if getattr(self.runtime,'human_physical',None) is not None:
                self.runtime.human_physical.reset()
            if self.runtime.baseline_collector.status in ('pending','ready'):
                self.runtime.baseline_collector.invalidate('runtime_history_invalidated')

    def install_ground(self,path,site_id,upstream):
        ground,sha=self.prepare_ground(path,site_id)
        self.install_prepared_ground(ground,sha,upstream)

    def prepare_ground(self,path,site_id):
        """File validation may run in the fit IO worker; no engine mutation."""
        if self.runtime is None:raise ValueError('ground requires background')
        ground=site_ground(path,self.frame_id,self.grid.sha256,site_id,self.identity)
        return ground,hashlib.sha256(Path(path).read_bytes()).hexdigest()

    def install_prepared_ground(self,ground,sha,upstream):
        """Only the recognition writer installs an already validated plane."""
        if self.disabled:raise ValueError('source invalidated before ground install')
        if ground['source'].get('upstream')!=upstream or ground['source'].get('identity')!=self.identity:
            raise ValueError('ground source binding mismatch')
        last=ground['fitLastHeader'];stamp=last['sec']+last['nsec']/1e9
        if self.previous and (last['seq']>self.previous[0] or stamp>self.previous[1]):
            raise ValueError('ground fit is from the future')
        self.runtime.ground=ground
        self.runtime.ground_sha=sha
        self.runtime.config['ground_sha256']=self.runtime.ground_sha
        from core.range_runtime import serial
        self.runtime.config_sha=hashlib.sha256(serial(self.runtime.config).encode()).hexdigest()
        self.clear_history()
        self.ground_status=dict(available=False,reason='awaiting_current_patch_check',
                               sha256=self.runtime.ground_sha,binding=ground['siteBinding'])

    def invalid(self,reason):
        epoch = (self.instant_tracker.generation if self.instant_tracker is not None
                 else self.runtime.tracker.generation if self.runtime else 0)
        return dict(schema_version=1,kind='target_state',session_id=self.identity['session'],
            time_epoch=epoch,
            selection_version=0,source=None,target_mode='local_range_automatic',track_id=None,track_status='unselected',
            observability='invalid',bbox_observed=False,position_predicted=False,target_source_rows=[],fall_status='unknown',
            acquisition=dict(reason=reason),semantic='unknown',confirmed_enabled=False)

    def validate_ground(self,frame,ground):
        from .range_features import bound_ground
        bound = bound_ground(frame,ground)
        if ground and ground.get('monitor'):
            from .range_site_ground import monitor
            check=monitor(frame.xyz[frame.source_rows[frame.valid]],ground)
            self.ground_status=dict(check,sha256=self.runtime.ground_sha,binding=ground['siteBinding'])
            if not check['available']:
                self.clear_history()
        else:
            from .range_features import bound_ground
            available=ground is not None and bound_ground(frame,ground) is not None
            self.ground_status=dict(available=available,
                reason='bound_plane_geometry_only' if available else 'not_loaded' if ground is None else 'ground_binding_invalid',
                sha256=self.runtime.ground_sha,physicalGroundTruth='UNKNOWN')
            if ground is not None and not available:
                self.clear_history();return None
        # Frozen display orientation is distinct from current height evidence.
        # Occlusion must suspend height without making the entire view tilt back.
        if bound is not None and self.runtime.ground_sha:
            self.ground_status['displayPlane'] = dict(
                sessionId=self.identity['session'], normal=ground['normal'],
                offsetM=ground['offset_m'], groundSha256=self.runtime.ground_sha,
                frameId=self.frame_id, scope='bound_display_only')
        return ground if self.ground_status['available'] else None

    def process(self,raw,received=None,wire_sha256=None,preview=True):
        self.body_job=None;self.ground_frame=None
        stage=time.perf_counter();costs={}
        started=self.clock();received=started if received is None else received
        if self.disabled:return self.invalid(self.disabled)
        try:
            if self.grid.sha256!=self.identity['grid_sha256']:
                self.invalidate('calibration_changed_requires_rebind');return self.invalid(self.disabled)
            if started-received>.5:
                self.clear_history();return self.invalid('local_input_expired')
            msg=parse_cloud(raw) if isinstance(raw,(bytes,bytearray,memoryview)) else raw
            wire_sha256=hashlib.sha256(raw).hexdigest() if wire_sha256 is None else wire_sha256
            if len(wire_sha256)!=64:raise ValueError('missing original ROS wire fingerprint')
            h=msg.header;stamp=h.stamp.secs+h.stamp.nsecs/1e9
            if h.frame_id!=self.frame_id or stamp<=0:raise ValueError('unexpected frame or invalid stamp')
            if self.previous is None and self.background_header is not None:
                if h.seq<=self.background_header[0] or stamp<=self.background_header[1]:
                    self.invalidate('background_source_epoch_mismatch');return self.invalid(self.disabled)
            if self.runtime and self.runtime.ground and self.runtime.ground.get('fitLastHeader'):
                gh=self.runtime.ground['fitLastHeader']
                if h.seq<=gh['seq'] or stamp<=gh['sec']+gh['nsec']/1e9:
                    self.invalidate('ground_source_epoch_mismatch');return self.invalid(self.disabled)
            if self.previous is not None:
                last_seq,last_stamp=self.previous
                if h.seq<=last_seq or stamp<=last_stamp:
                    self.invalidate('source_rewound_requires_rebind');return self.invalid(self.disabled)
                self.index+=h.seq-last_seq
            else:self.index=0
            self.previous=(h.seq,stamp)
            packed=pointcloud_rows(msg)
            costs['adapt_ms']=(time.perf_counter()-stage)*1000;stage=time.perf_counter()
            if self.instant_start:
                return self._process_instant(packed,h,stamp,wire_sha256,received,started,costs,preview)
            if self.runtime:
                selected_before=self.runtime.tracker.selected
                result,frame,components=self.runtime.update(packed,stamp,self.index,ground_validator=self.validate_ground)
                record,rule=result['tracking'],result['rule'];rows=record['target_source_rows']
                state=rule['state']['state'];features=rule['features'];height=features.get('height_median_m')
                hb=features.get('height_m') or {}
                measured=bool(rows) and features.get('observable') and features.get('ground_relative')
                demo_level=self.demo_alert.update(dict(i=self.index,t=stamp,tid=record['target_track_id'],
                    n=len(rows) if measured else 0,hm=height if measured else None,
                    ht=hb.get('max') if measured else None,sp=features.get('horizontal_extent_m') if measured else None,
                    generation=record['generation'],binding=frame.binding,reset=features.get('reset_now')))
                demo=dict(variant='horizontal_low_posture_v1',level=demo_level,active=demo_level>0,
                    state='unavailable' if not measured else 'sustained' if demo_level==2 else
                          'suspected' if demo_level==1 else 'pending' if self.demo_alert.eligible else 'not_matched',
                    durationSec=self.demo_alert.duration,confirmedEnabled=False,semantic='UNKNOWN')
                reason=result['status'] if result['status']!='ready' else record['target_reason'] or 'current_target'
                generation=record['generation'];track=record['target_track_id']
                alert=self.alert.update(dict(frameIndex=self.index,stampSec=stamp,trackId=track,generation=generation,
                    measured=bool(rows),heightMedianM=height,observationGap=rule['features'].get('observation_gap')))[0]
                tracks=record['tracks']
                unique=(len(tracks)==1 and tracks[0]['status']=='predicted' and
                        record['target_reason']=='no_stable_current_measurement')
                candidate=self.alert_candidate.update(dict(frameIndex=self.index,stampSec=stamp,trackId=track,
                    generation=generation,binding=frame.binding,measured=bool(rows),heightMedianM=height,
                    continuityTrackId=tracks[0]['track_id'] if unique else None,uniquePredictedTrack=unique,
                    groundAvailable=self.ground_status['available'],
                    ambiguous=record['target_reason'] in ('competing_target_scores', 'selected_target_ambiguous', 'single_person_selection_ambiguous'),resetNow=rule['features'].get('reset_now')))
                posture=rule.get('posture')
                if posture is None:
                    posture=self.posture.update(rule['features'],record,frame.binding)
            else:
                frame=self.grid.decode(packed,binding_tuple(self.identity));rows=[];track=None;generation=0
                state='unknown';height=None;reason='background_not_declared'
                self.demo_alert.update(dict(i=self.index,t=stamp,tid=None,n=0,hm=None,ht=None,sp=None))
                demo=dict(variant='horizontal_low_posture_v1',level=0,active=False,state='unavailable',
                    durationSec=0.,confirmedEnabled=False,semantic='UNKNOWN')
                alert=self.alert.update(dict(frameIndex=self.index,stampSec=stamp,measured=False,trackId=None,heightMedianM=None))[0]
                posture=None
                candidate=self.alert_candidate.update(dict(frameIndex=self.index,stampSec=stamp,measured=False))
            costs['runtime_ms']=(time.perf_counter()-stage)*1000;stage=time.perf_counter()
            self.ground_frame=frame
            try:pose=project_regions(estimate(frame.xyz[rows] if rows and preview else [],rows if preview else []),frame)
            except (ValueError,TypeError,FloatingPointError):pose=project_regions(estimate([],[]),frame)
            costs['skeleton_ms']=(time.perf_counter()-stage)*1000;stage=time.perf_counter()
            encoded=png(preview_rgb(frame)) if preview else None
            depth=dict(metadata=dict(format='lidar_range_image',version=2,width=self.grid.shape[1],height=self.grid.shape[0],
                nativeTransform='rotate180',orientation='native_grid_rotated_180_for_view',gridSha256=self.grid.sha256,
                quantity='radial_range',units='m',validPixels=int(frame.valid.sum()),targetPixels=len(rows)),
                previewSha256=hashlib.sha256(encoded).hexdigest() if encoded else None)
            bbox = _compact_bbox(frame.xyz[rows], self.runtime.ground if self.runtime else None) if rows else None
            bundle=dict(version=1,wireSha256=wire_sha256,heightMedianM=height,groundAlert=alert,
                measurement=(dict(topHeightM=hb.get('max'),horizontalExtentM=features.get('horizontal_extent_m'),
                    descentRateMps=features.get('descent_rate_m_s'),axisVerticality=features.get('axis_verticality'))
                    if self.runtime else None),
                sourceBinding=dict(self.identity),background=dict(status=result['status'] if self.runtime else 'background_not_declared',
                    configSha256=self.runtime.config_sha if self.runtime else None),
                ground=self.ground_status,fallEvidence=rule['state'] if self.runtime else None,
                groundAlertCandidate=candidate,demoFallCandidate=demo,posture=posture,skeleton=pose,bbox=bbox,depth=depth,preview=base64.b64encode(encoded).decode() if encoded else None,bodyCandidates=None)
            costs['image_ms']=(time.perf_counter()-stage)*1000
            if self.body:
                if self.defer_body:self.body_job=(frame,rows)
                else:bundle['bodyCandidates']=self.make_body((frame,rows))
            if self.clock()-received>.5:
                self.clear_history()
                expired=self.invalid('local_result_expired')
                expired['performance']=dict(process_ms=(self.clock()-started)*1000,
                    local_age_ms=(self.clock()-received)*1000,stages=costs,
                    runtime=result['timings'] if self.runtime else {})
                return expired
            self.processed+=1
            out = dict(schema_version=1,kind='target_state',session_id=self.identity['session'],time_epoch=generation,
                selection_version=0,source=dict(seq=h.seq,stamp_secs=h.stamp.secs,stamp_nsecs=h.stamp.nsecs,frame_id=h.frame_id),
                target_mode='local_range_automatic',track_id=track,track_status='locked' if rows else 'unselected',
                observability='valid',bbox_observed=bool(rows),position_predicted=False,target_source_rows=rows,
                fall_status=state,acquisition=dict(reason=reason),semantic='unknown',confirmed_enabled=False,
                local_range=bundle,performance=dict(process_ms=(self.clock()-started)*1000,
                    local_age_ms=(self.clock()-received)*1000,processed=self.processed,stages=costs,
                    runtime=result['timings'] if self.runtime else {}),
                diagnostics=dict(tracking=dict(
                    reason=record['target_reason'],continuityTrackId=record.get('continuity_track_id'),
                    tracks=[dict({k:t.get(k) for k in ('track_id','status','component_ids','selection_score','reason')},
                                 point_count=len(t.get('source_rows') or []))
                            for t in record['tracks'][:32]],trackCount=len(record['tracks']),
                    associationEdges={tid:edges[:8] for tid,edges in list(record['association_edges'].items())[:32]},
                    associationEdgeCount=sum(len(v) for v in record['association_edges'].values()),
                    compositions=[dict(trackId=c['track_id'],componentIds=c['component_ids'][:32],
                        accepted=c['accepted'],reason=c['reason'],metrics=c['metrics']) for c in record['compositions'][:32]],
                    ambiguousComponentIds=record['ambiguous_component_ids'][:32],
                    ambiguousComponentCount=len(record['ambiguous_component_ids'])) if self.runtime else None,
                    detail=self.diagnostic_detail(frame,components,record,rule,selected_before) if self.runtime and self.diagnostics else None))
            if self.human_physical_v1 and self.runtime:
                out['human_physical_v1'] = _compact_physical_v1(result.get('human_physical_v1'))
            return out
        except SettingsDriftError as exc:
            self.invalidate('settings_drift_requires_new_runtime: '+str(exc));return self.invalid(self.disabled)
        except (ValueError,TypeError,KeyError,AttributeError,OverflowError,struct.error,UnicodeError,FloatingPointError) as exc:
            self.invalidate('invalid_source_requires_rebind: '+str(exc));return self.invalid(self.disabled)

    def _process_instant(self,packed,h,stamp,wire_sha256,received,started,costs,preview):
        """开机直接算 + 后台无感精修路径：免 50 帧空场、免阻塞地面拟合。"""
        stage = time.perf_counter()
        frame = self.grid.decode(packed, binding_tuple(self.identity))
        decode_ms = (time.perf_counter() - stage) * 1000.0
        stage = time.perf_counter()

        cur_up = self.ground_refiner.normal
        cur_offset = self.ground_refiner.offset_m
        instant_out = self.instant_tracker.step(
            frame, stamp, self.index, gravity_up=cur_up, ground_offset_m=cur_offset,
        )
        track_ms = (time.perf_counter() - stage) * 1000.0
        stage = time.perf_counter()

        # 后台无感精修：直立脚底观测 + 静态非前景底面周期拟合（永不阻塞、不清轨迹）
        for fh, fu, fv in instant_out['foot_observations']:
            self.ground_refiner.observe_upright_foot(fh, fu, fv)
        if self.ground_refiner.is_check_due():
            smask = instant_out['static_mask']
            srows = frame.source_rows[smask]
            static_xyz = frame.xyz[srows] if len(srows) else None
        else:
            static_xyz = None
        refined_changed = self.ground_refiner.observe_frame(static_xyz)
        if refined_changed:
            self.instant_tracker.set_gravity_up(self.ground_refiner.normal)
        self.ground_status = self.ground_refiner.status_dict(self.identity['session'])
        refined_ground = self.ground_refiner.bound_plane(frame)
        refine_ms = (time.perf_counter() - stage) * 1000.0
        stage = time.perf_counter()

        record = instant_out['tracking']
        rows = record['target_source_rows']
        track = record['target_track_id']
        generation = record['generation']
        state = instant_out['fall_status']
        meas = dict(instant_out['measurement'])
        height = instant_out['height_median_m']
        # 若本帧刚完成精修，补齐本帧相对精修地面的绝对高度
        if refined_ground is not None and height is None and rows:
            off_now = float(refined_ground['offset_m'])
            n_now = np.asarray(refined_ground['normal'], dtype=np.float64)
            ph_now = frame.xyz[rows].astype(np.float64) @ n_now + off_now
            height = round(float(np.median(ph_now)), 4)
            meas['topHeightM'] = round(float(np.percentile(ph_now, 95.0)), 4)
            meas['bottomHeightM'] = round(float(np.percentile(ph_now, 5.0)), 4)
            meas['groundRelativeAvailable'] = True

        measured_ground = bool(rows) and (refined_ground is not None) and (height is not None)
        demo_level = self.demo_alert.update(dict(
            i=self.index, t=stamp, tid=track,
            n=len(rows) if measured_ground else 0,
            hm=height if measured_ground else None,
            ht=meas.get('topHeightM') if measured_ground else None,
            sp=meas.get('horizontalExtentM') if measured_ground else None,
            generation=generation, binding=frame.binding,
            reset=bool(record.get('reset_reason')),
        ))
        demo = dict(
            variant='horizontal_low_posture_v1', level=demo_level, active=demo_level > 0,
            state=('unavailable' if not measured_ground else 'sustained' if demo_level == 2 else
                   'suspected' if demo_level == 1 else 'pending' if self.demo_alert.eligible else 'not_matched'),
            durationSec=self.demo_alert.duration, confirmedEnabled=False, semantic='UNKNOWN',
        )
        alert = self.alert.update(dict(
            frameIndex=self.index, stampSec=stamp, trackId=track, generation=generation,
            measured=bool(rows), heightMedianM=height, observationGap=False,
        ))[0]
        candidate = self.alert_candidate.update(dict(
            frameIndex=self.index, stampSec=stamp, trackId=track, generation=generation,
            binding=frame.binding, measured=bool(rows), heightMedianM=height,
            continuityTrackId=record.get('continuity_track_id') if not rows else None,
            uniquePredictedTrack=False, groundAvailable=self.ground_status['available'],
            ambiguous=False, resetNow=bool(record.get('reset_reason')),
        ))

        phys_out = None
        phys_ms = 0.0
        if self.instant_physical is not None:
            p0 = time.perf_counter()
            if refined_ground is not None:
                try:
                    phys_out = self.instant_physical.evaluate(
                        frame, record,
                        background=self.instant_tracker.background_adapter,
                        ground=refined_ground,
                    )
                except Exception as exc:  # noqa: BLE001
                    self.instant_physical.reset()
                    phys_out = evaluator_failure_output(record, exc, (time.perf_counter() - p0) * 1000.0)
                phys_ms = (time.perf_counter() - p0) * 1000.0
            else:
                phys_out = dict(
                    variant='human_physical_v1', revision=HUMAN_PHYSICAL_REVISION,
                    status='awaiting_ground_offset', error_codes=[], errors=[],
                    frame=self.index, time_s=stamp, target_track_id=track,
                    target_belief=None, confirmed_track_ids=[], candidate_track_ids=[],
                    kinematics_noise_floor=self.instant_physical.kinematics.noise_floor(),
                    tracks={}, recovery=None, timings=dict(physical_total_ms=0.0),
                    semantic_truth='UNKNOWN',
                )
        costs['runtime_ms'] = (time.perf_counter() - stage) * 1000.0 + decode_ms + track_ms + refine_ms
        stage = time.perf_counter()

        self.ground_frame = frame
        try:
            pose = project_regions(estimate(frame.xyz[rows] if rows and preview else [], rows if preview else []), frame)
        except (ValueError, TypeError, FloatingPointError):
            pose = project_regions(estimate([], []), frame)
        costs['skeleton_ms'] = (time.perf_counter() - stage) * 1000.0
        stage = time.perf_counter()

        encoded = png(preview_rgb(frame)) if preview else None
        depth = dict(
            metadata=dict(
                format='lidar_range_image', version=2, width=self.grid.shape[1], height=self.grid.shape[0],
                nativeTransform='rotate180', orientation='native_grid_rotated_180_for_view',
                gridSha256=self.grid.sha256, quantity='radial_range', units='m',
                validPixels=int(frame.valid.sum()), targetPixels=len(rows),
            ),
            previewSha256=hashlib.sha256(encoded).hexdigest() if encoded else None,
        )
        dp = self.ground_status.get('displayPlane') or {}
        bbox_ground = (
            dict(normal=dp['normal'], offset_m=dp['offsetM'])
            if dp.get('normal') is not None else None
        )
        bbox = _compact_bbox(frame.xyz[rows], bbox_ground) if rows else None
        bundle = dict(
            version=1, wireSha256=wire_sha256, heightMedianM=height, groundAlert=alert,
            measurement=meas, sourceBinding=dict(self.identity),
            background=dict(
                status='adaptive_ready', declaration='instant_adaptive_far_bg',
                configSha256=self.instant_config_sha,
                validCells=instant_out['valid_cells'], fgSeedCells=instant_out['fg_seed_cells'],
            ),
            ground=self.ground_status,
            fallEvidence=instant_out['fall_evidence'],
            kinematics=instant_out['kinematics'],
            groundAlertCandidate=candidate, demoFallCandidate=demo,
            posture=instant_out['posture'], skeleton=pose, bbox=bbox, depth=depth,
            preview=base64.b64encode(encoded).decode() if encoded else None,
            bodyCandidates=None,
        )
        costs['image_ms'] = (time.perf_counter() - stage) * 1000.0
        if self.body:
            if self.defer_body:
                self.body_job = (frame, rows)
            else:
                bundle['bodyCandidates'] = self.make_body((frame, rows))

        rt_timings = dict(
            decode_ms=decode_ms,
            instant_tracker_ms=track_ms,
            silent_refine_ms=refine_ms,
            physical_total_ms=phys_ms,
        )
        if phys_out and isinstance(phys_out.get('timings'), dict):
            rt_timings.update(phys_out['timings'])

        if self.clock() - received > .5:
            self.clear_history()
            expired = self.invalid('local_result_expired')
            expired['performance'] = dict(
                process_ms=(self.clock() - started) * 1000.0,
                local_age_ms=(self.clock() - received) * 1000.0,
                stages=costs, runtime=rt_timings,
            )
            return expired

        self.processed += 1
        reason = record['target_reason'] or 'current_target'
        out = dict(
            schema_version=1, kind='target_state', session_id=self.identity['session'], time_epoch=generation,
            selection_version=0,
            source=dict(seq=h.seq, stamp_secs=h.stamp.secs, stamp_nsecs=h.stamp.nsecs, frame_id=h.frame_id),
            target_mode='instant_kinematic_automatic', track_id=track,
            track_status='locked' if rows else 'unselected',
            observability='valid', bbox_observed=bool(rows), position_predicted=False,
            target_source_rows=rows, fall_status=state, acquisition=dict(reason=reason),
            semantic='unknown', confirmed_enabled=False,
            local_range=bundle,
            performance=dict(
                process_ms=(self.clock() - started) * 1000.0,
                local_age_ms=(self.clock() - received) * 1000.0,
                processed=self.processed, stages=costs, runtime=rt_timings,
            ),
            diagnostics=dict(
                tracking=dict(
                    reason=record['target_reason'], continuityTrackId=record.get('continuity_track_id'),
                    tracks=[
                        dict(
                            {k: t.get(k) for k in ('track_id', 'status', 'component_ids', 'selection_score',
                                                   'reason', 'fall_state', 'drop_top_m', 'vel_top_mps', 'still_sec')},
                            point_count=int(t.get('point_count') or 0),
                        )
                        for t in record['tracks'][:32]
                    ],
                    trackCount=len(record['tracks']),
                    associationEdges={}, associationEdgeCount=0,
                    compositions=[], ambiguousComponentIds=[], ambiguousComponentCount=0,
                ),
                detail=None,
            ),
        )
        if self.human_physical_v1 and phys_out is not None:
            out['human_physical_v1'] = _compact_physical_v1(phys_out)
        return out

    def diagnostic_detail(self,frame,components,record,rule,selected_before):
        # Bounded derived summaries only; never raw XYZ or a second selector.
        summaries=[]
        for component in components[:32]:
            rows=np.asarray(component['source_rows'],dtype='<i8')
            xyz=frame.xyz[rows]
            summaries.append(dict(componentId=component['component_id'],points=len(rows),
                retained=bool(component['retained']),minPoints=component.get('min_points'),
                rowsSha256=hashlib.sha256(rows.tobytes()).hexdigest(),rowSample=rows[:8].tolist(),
                centerM=np.median(xyz,axis=0).tolist() if len(rows) else None,
                spanM=np.ptp(xyz,axis=0).tolist() if len(rows) else None))
        features=rule['features']
        return dict(version=1,componentCount=len(components),components=summaries,
            componentsOmitted=max(0,len(components)-32),selectedBefore=selected_before,
            selectedNow=record['target_track_id'],continuityTrackId=record.get('continuity_track_id'),
            selectionReason=record['target_reason'] or ('retained_selected_track' if selected_before==record['target_track_id'] else 'best_unique_score'),
            trackerResetReason=record['reset_reason'],expiredTrackIds=record['expired_track_ids'][:32],
            historyResetReason=features.get('history_reset_reason'),historyResetNow=features.get('reset_now'),
            observationGap=features.get('observation_gap',False),historySamples=features.get('history_samples'),
            measured=bool(record['target_source_rows']),rawCloudRecorded=False)


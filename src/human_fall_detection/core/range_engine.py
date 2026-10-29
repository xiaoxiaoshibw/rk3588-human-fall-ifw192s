"""Shared live recognition engine; no ROS, sockets, Qt or device control."""
import base64
import hashlib
import json
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

class RangeEngine:
    def __init__(self,grid,frame_id,identity=None,background=None,empty_prefix_frames=None,ground=None,body=False,diagnostics=False):
        self.grid,self.frame_id=grid,frame_id
        self.identity=identity or dict(session='live_range_'+uuid.uuid4().hex,coordinate='RAW/'+frame_id,
            units='m',coordinate_transform='identity',grid_sha256=grid.sha256,epoch='live_source_header')
        if self.identity['coordinate']!='RAW/'+frame_id or self.identity['grid_sha256']!=grid.sha256:
            raise ValueError('live source/background binding mismatch')
        self.runtime=None
        if background is not None or empty_prefix_frames is not None:
            self.runtime=RangeRuntime(grid,self.identity,empty_prefix_frames=empty_prefix_frames or 50,ground=ground,
                ground_sha=hashlib.sha256(json.dumps(ground,sort_keys=True).encode()).hexdigest() if ground else None,detailed=False)
            if background is not None:
                if background.binding!=(binding_tuple(self.identity),grid.sha256):raise ValueError('background binding mismatch')
                self.runtime.background=background
        self.body=body;self.defer_body=False;self.body_job=None
        self.diagnostics=bool(diagnostics)
        self.alert=GroundAlertObserver();self.alert_candidate=GroundAlertGapCandidate();self.posture=PostureObserver()
        self.demo_alert=DemoAlert(self.runtime.config['demo_alert'] if self.runtime else None)
        self.index=-1;self.previous=None;self.disabled=None;self.processed=0;self.ground_frame=None
        self.ground_status=dict(available=ground is not None,reason='not_loaded' if ground is None else 'bound')
        self.background_header=getattr(background,'last_declared_header',None)

    def invalidate(self,reason):
        self.disabled=reason;self.clear_history()
        if self.runtime:self.runtime.ground=None
        self.ground_status=dict(available=False,reason=reason)

    def clear_history(self):
        config=self.runtime.config if self.runtime else None
        self.alert=GroundAlertObserver(config['ground_alert'] if config else None)
        self.alert_candidate=GroundAlertGapCandidate()
        self.demo_alert=DemoAlert(config['demo_alert'] if config else None)
        self.posture=PostureObserver(config['posture'] if config else None);self.body_job=None
        if self.runtime:
            from core.features import FeatureExtractor
            from core.fall_state import FallStateMachine
            self.runtime.features=FeatureExtractor(self.identity['session'],config['feature_defaults'])
            self.runtime.state=FallStateMachine(self.identity['session'],config['fall'])
            self.runtime.posture=PostureObserver(config['posture'])
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
        return dict(schema_version=1,kind='target_state',session_id=self.identity['session'],
            time_epoch=self.runtime.tracker.generation if self.runtime else 0,
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
        started=time.monotonic();received=started if received is None else received
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
            bundle=dict(version=1,wireSha256=wire_sha256,heightMedianM=height,groundAlert=alert,
                sourceBinding=dict(self.identity),background=dict(status=result['status'] if self.runtime else 'background_not_declared',
                    configSha256=self.runtime.config_sha if self.runtime else None),
                ground=self.ground_status,fallEvidence=rule['state'] if self.runtime else None,
                groundAlertCandidate=candidate,demoFallCandidate=demo,posture=posture,skeleton=pose,depth=depth,preview=base64.b64encode(encoded).decode() if encoded else None,bodyCandidates=None)
            costs['image_ms']=(time.perf_counter()-stage)*1000
            if self.body:
                if self.defer_body:self.body_job=(frame,rows)
                else:bundle['bodyCandidates']=self.make_body((frame,rows))
            if time.monotonic()-received>.5:
                self.clear_history()
                expired=self.invalid('local_result_expired')
                expired['performance']=dict(process_ms=(time.monotonic()-started)*1000,
                    local_age_ms=(time.monotonic()-received)*1000,stages=costs,
                    runtime=result['timings'] if self.runtime else {})
                return expired
            self.processed+=1
            return dict(schema_version=1,kind='target_state',session_id=self.identity['session'],time_epoch=generation,
                selection_version=0,source=dict(seq=h.seq,stamp_secs=h.stamp.secs,stamp_nsecs=h.stamp.nsecs,frame_id=h.frame_id),
                target_mode='local_range_automatic',track_id=track,track_status='locked' if rows else 'unselected',
                observability='valid',bbox_observed=bool(rows),position_predicted=False,target_source_rows=rows,
                fall_status=state,acquisition=dict(reason=reason),semantic='unknown',confirmed_enabled=False,
                local_range=bundle,performance=dict(process_ms=(time.monotonic()-started)*1000,
                    local_age_ms=(time.monotonic()-received)*1000,processed=self.processed,stages=costs,
                    runtime=result['timings'] if self.runtime else {}),
                diagnostics=dict(tracking=dict(
                    reason=record['target_reason'],continuityTrackId=record.get('continuity_track_id'),
                    tracks=[{k:t.get(k) for k in ('track_id','status','component_ids','selection_score','reason')}
                            for t in record['tracks'][:32]],trackCount=len(record['tracks']),
                    associationEdges={tid:edges[:8] for tid,edges in list(record['association_edges'].items())[:32]},
                    associationEdgeCount=sum(len(v) for v in record['association_edges'].values()),
                    compositions=[dict(trackId=c['track_id'],componentIds=c['component_ids'][:32],
                        accepted=c['accepted'],reason=c['reason'],metrics=c['metrics']) for c in record['compositions'][:32]],
                    ambiguousComponentIds=record['ambiguous_component_ids'][:32],
                    ambiguousComponentCount=len(record['ambiguous_component_ids'])) if self.runtime else None,
                    detail=self.diagnostic_detail(frame,components,record,rule,selected_before) if self.runtime and self.diagnostics else None))
        except SettingsDriftError as exc:
            self.invalidate('settings_drift_requires_new_runtime: '+str(exc));return self.invalid(self.disabled)
        except (ValueError,TypeError,KeyError,AttributeError,OverflowError,struct.error,UnicodeError,FloatingPointError) as exc:
            self.invalidate('invalid_source_requires_rebind: '+str(exc));return self.invalid(self.disabled)

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


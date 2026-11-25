"""Recorded clouds through RangeService and the ROS adapter's initializer.

No whole-session background/ground is estimated. The saved live empty-scene
capture has a declaration; ordinary action sessions have none and stay unbound.
Batch mode pauses the source clock while fitting: deterministic algorithm and
lifecycle checks, never a measurement of board timing or transport performance.
"""
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
from types import SimpleNamespace as NS

import numpy as np

ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'src/human_fall_detection'),str(ROOT/'pc_apps/range_fall')]
from core.capture_input import ROW_DTYPE, sha256_file
from core.range_engine import RangeEngine
from core.range_image import ScanGrid
from core.range_initialization import SiteInitialization
from core.range_service import RangeService
from live_replay_check import driver_message
from live_tracking_check import wire_message
import session_compare as sc

LIVE_CAPTURE=ROOT/'docs/evidence/2026-10-29_ground_region_fix'


class SourceClock:
    def __init__(self):self.now=0.
    def __call__(self):return self.now
    def advance(self, seconds):self.now+=seconds


def activity(state):
    bundle=state.get('local_range') or {}
    hint=bundle.get('demoFallCandidate') or {}
    posture=bundle.get('posture') or {}
    evidence=bundle.get('fallEvidence') or {}
    measured=bool(state.get('source') and state.get('target_source_rows')
                  and (bundle.get('ground') or {}).get('available'))
    phase=state.get('fall_status','unknown') if measured else 'unknown'
    level=hint.get('level',0) if measured else 0
    eligible=measured and hint.get('state') in ('pending','suspected','sustained')
    label=('unknown' if not measured else 'fall_suspected' if phase=='suspected'
        else ('low_horizontal_sustained' if level==2 else 'low_horizontal_candidate') if level
        else phase if phase in ('descending','recovering')
        else 'low_horizontal_pending' if eligible else posture.get('state','unknown'))
    return dict(label=label,posture=posture.get('state','unknown'),state=phase,level=level,
        low_duration_s=hint.get('durationSec',0.) if measured else 0.,measured=measured,
        low_eligible=bool(eligible),reason_codes=evidence.get('reason_codes') or [],
        posture_reason=posture.get('reason'),human_semantic='UNKNOWN',confirmed=False)


class ServiceReplay:
    def __init__(self,name,*,output=None,deterministic=False):
        started=time.perf_counter()
        self.name,self.index=name,0
        self.deterministic=deterministic
        self.clock=SourceClock() if deterministic else time.monotonic
        self.archive=self.stream=self.temp=None
        self.stop=threading.Event()
        self.grid=sc.load_grid()
        if name=='site_empty':
            capture=LIVE_CAPTURE/'activation_capture'
            meta=json.loads((capture/'capture.json').read_text(encoding='utf8'))
            declaration=json.loads((LIVE_CAPTURE/'activation_binding.json').read_text(encoding='utf8'))
            original=json.loads((LIVE_CAPTURE/'board_live_ground_fit.json').read_text(encoding='utf8'))
            self.archive=np.load(capture/'clouds.npz',allow_pickle=False)
            archive_sha=sha256_file(capture/'clouds.npz')
            if archive_sha!=meta['archive_sha256']:
                self.archive.close()
                raise ValueError('recorded live capture checksum mismatch')
            # The fit header marks that recorded service's input start, not a
            # plane choice. Its plane and all later points are never installed.
            start_seq=original['headers'][0]['seq']
            self.frames=[(i,h) for i,h in enumerate(meta['headers']) if h['seq']>=start_seq]
            self.declared=declaration.get('user_declared_empty_scene') is True
            self.source_kind='recorded_live_ros_layout'
            source_sha=archive_sha
            self.frame_id=original['binding']['frameId']
        else:
            if name not in ('houdao','qiandao','huanmandiedao','jixiedaiwanyao'):
                raise ValueError('unknown service replay source')
            self.session=ROOT/'data/sessions'/('cap_20261028_'+name)
            meta=json.loads((self.session/'meta.json').read_text(encoding='utf8'))
            self.frames=[(i,dict(f,sec=f['stamp_sec'],nsec=f['stamp_nanosec'],
                frame_id=meta['sensor']['frame_id'])) for i,f in enumerate(meta['frames'])]
            self.stream=(self.session/'points.bin').open('rb')
            self.declared=False
            self.source_kind='packed_recording_ros_standin'
            self.frame_id=meta['sensor']['frame_id']
            source_sha=sha256_file(self.session/'points.bin')
        self.count=len(self.frames)
        self.identity=dict(session='service_replay_'+name,coordinate='RAW/'+self.frame_id,units='m',
            coordinate_transform='identity',grid_sha256=self.grid.sha256,epoch=source_sha)
        self.engine=RangeEngine(self.grid,self.frame_id,self.identity,
            empty_prefix_frames=50 if self.declared else None,diagnostics=True,clock=self.clock)
        self.service=RangeService(self.engine,release_id='LOCAL_SHARED_SERVICE_REPLAY',clock=self.clock)
        if output is None:
            self.temp=tempfile.TemporaryDirectory(prefix='ldiar_service_replay_')
            output=Path(self.temp.name)
        output=Path(output).resolve()
        for protected in (ROOT/'data',ROOT/'captures'):
            protected=protected.resolve()
            if output==protected or protected in output.parents:
                self.close()
                raise ValueError('service replay output must be outside data/captures')
        self.initializer=SiteInitialization(self.service,declared_empty=self.declared,
            output=output/'site_ground' if self.declared else None,site_id='replay_'+name,
            upstream='ros:/innolidar_points',stop=self.stop)
        first=self.frames[0][1]
        self.base=first['sec']+first['nsec']/1e9
        self.heartbeat=None
        if not deterministic:
            def heartbeat():
                while not self.stop.wait(.05):self.service.snapshot()
            self.heartbeat=threading.Thread(target=heartbeat,daemon=True,name='replay-service-heartbeat')
            self.heartbeat.start()
        self.prepare_s=time.perf_counter()-started

    def close(self):
        self.stop.set()
        if hasattr(self,'initializer'):self.initializer.close()
        if getattr(self,'heartbeat',None) is not None:self.heartbeat.join(1.)
        if self.stream is not None:self.stream.close()
        if self.archive is not None:self.archive.close()
        if self.temp is not None:self.temp.cleanup()

    def _message(self,index):
        ordinal,h=self.frames[index]
        if self.archive is not None:
            data=self.archive['wire_%03d'%ordinal].tobytes()
            if hashlib.sha256(data).hexdigest()!=h['wire_sha256']:
                raise ValueError('recorded cloud data checksum mismatch')
            msg=NS(header=NS(seq=h['seq'],stamp=NS(secs=h['sec'],nsecs=h['nsec']),frame_id=h['frame_id']),
                fields=[NS(**f) for f in h['fields']],data=data,
                **{k:h[k] for k in ('width','height','point_step','row_step','is_bigendian')})
        else:
            self.stream.seek(h['offset_points']*ROW_DTYPE.itemsize)
            data=self.stream.read(h['count_points']*ROW_DTYPE.itemsize)
            if len(data)!=h['count_points']*ROW_DTYPE.itemsize:raise ValueError('truncated source recording')
            msg=driver_message(np.frombuffer(data,ROW_DTYPE),dict(seq=h['seq'],stamp_sec=h['sec'],stamp_nanosec=h['nsec']),self.frame_id)
        serialized=wire_message(msg)
        msg.serialize=lambda stream:stream.write(serialized)
        return msg,h

    def next(self,visuals=True,trace=False):
        if self.index>=self.count:return None
        started=time.perf_counter()
        if self.deterministic and self.initializer.status['ground']=='fitting':
            deadline=time.monotonic()+65
            while self.initializer.status['ground']=='fitting' and time.monotonic()<deadline:
                self.initializer.observe(None)
                self.stop.wait(.005)
            if self.initializer.status['ground']=='fitting':raise RuntimeError('fit completion deadline exceeded')
        msg,h=self._message(self.index)
        stamp=h['sec']+h['nsec']/1e9
        if self.deterministic:self.clock.now=max(self.clock.now,stamp-self.base)
        loop_started=time.perf_counter()
        self.service.submit(msg)
        result=self.service.process_latest()
        self.initializer.observe(result)
        self.service.process_preview()
        state=self.service.snapshot()
        bundle=state.get('local_range') or {}
        measurement=bundle.get('measurement') or {}
        ground=bundle.get('ground') or {}
        frame=self.engine.ground_frame if state.get('source') else None
        rows=state.get('target_source_rows') or []
        plane=self.engine.runtime.ground if self.engine.runtime else None
        basis=sc.display_basis(plane['normal']) if plane else np.eye(3)
        offset=plane['offset_m'] if plane else 0.
        empty=dict(status='disabled',added=0,added_beyond_supplemental=0,geometry=None,depth_box=None)
        from pseudo_live import target_geometry,target_rectangle
        entry=dict(i=self.index,t=stamp-self.base,tid=state.get('track_id'),n=len(rows),
            rows_sha256=hashlib.sha256(np.asarray(rows,dtype='<i8').tobytes()).hexdigest(),
            activity=activity(state),hm=bundle.get('heightMedianM'),ht=measurement.get('topHeightM'),
            extent=measurement.get('horizontalExtentM'),descent=measurement.get('descentRateMps'),
            verticality=measurement.get('axisVerticality'),
            geometry=target_geometry(frame.xyz,rows,basis,offset) if frame is not None and ground.get('available') else None,
            depth_box=target_rectangle(frame.valid,frame.source_rows,rows) if frame is not None and bundle.get('preview') else None,
            supplemental=dict(empty),exploration=dict(empty),runtime_ms=(time.perf_counter()-loop_started)*1000,
            pipeline=dict(mode='service',causal=True,declaredEmptyPrefix=self.declared,
                initialization=dict(self.initializer.status),background=(bundle.get('background')or{}).get('status'),
                groundAvailable=bool(ground.get('available')),sourceKind=self.source_kind,
                coordinates='ground_display' if plane else 'RAW',
                timing='source_clock_paused_during_fit' if self.deterministic else 'PC_request_driven_wall_clock',
                previewAvailable=bool(bundle.get('preview')),
                previewSha256=(bundle.get('depth') or {}).get('previewSha256'),
                reason=(state.get('acquisition')or{}).get('reason'),health=state['health']),
            source=state.get('source'),wire_sha256=bundle.get('wireSha256'))
        if trace:entry['service_state']=state
        if visuals:
            # Consume the same published auxiliary product as Qt. A missing or
            # expired preview must stay missing, never be rebuilt from the engine.
            entry['depth']='data:image/png;base64,'+bundle['preview'] if bundle.get('preview') else None
            if frame is None:
                scene_rows=[]
            else:
                scene_rows=frame.source_rows[frame.valid]
                if len(scene_rows)>2200:scene_rows=scene_rows[np.linspace(0,len(scene_rows)-1,2200,dtype=int)]
            entry['scene']=sc.quantize(sc.to_display(frame.xyz[scene_rows],basis,offset)) if frame is not None else []
            selected=np.asarray(rows,dtype=int)
            if len(selected)>1800:selected=selected[np.linspace(0,len(selected)-1,1800,dtype=int)]
            entry['target']=sc.quantize(sc.to_display(frame.xyz[selected],basis,offset)) if frame is not None else []
            entry['extra']=[];entry['wider']=[]
        entry['processing_ms']=(time.perf_counter()-started)*1000
        self.index+=1
        return entry

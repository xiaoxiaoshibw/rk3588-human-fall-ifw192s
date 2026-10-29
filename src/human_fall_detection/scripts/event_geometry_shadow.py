"""Read-only geometry telemetry beside the existing region/fall output.

No publishers, event-log writes, model loading or changes to the original state.
The release entry configures ML/src so this uses the same tested NumPy kernel
as offline replay, rather than a second implementation.
"""
import hashlib
import json
from pathlib import Path

import numpy as np

from fall_geometry import FallGeometryRuntime


class LiveGeometryShadow:
    def __init__(self, regions):
        self.regions=regions
        self.runtime=self.latest=self.plane_key=None
        self.errors=0
        path=Path(__file__).resolve().parents[3]/'ML/src/fall_geometry.py'
        self.source_sha256=hashlib.sha256(path.read_bytes()).hexdigest()

    @staticmethod
    def binding(state):
        return dict(source=state.get('source'),session_id=state.get('session_id'),
            track_id=state.get('track_id'),time_epoch=state.get('time_epoch'),
            action_generation=state.get('action_generation'),selection_version=state.get('selection_version'),
            calibration=state.get('calibration'),ground=state.get('ground'),
            target_source_rows=state.get('target_source_rows'))

    def process(self, points, result):
        self.regions.process(points,result)
        state=result['state'];self.latest=None
        try:
            ground=state.get('ground') or {}
            key=json.dumps(ground,sort_keys=True,allow_nan=False)
            if self.runtime is None or key!=self.plane_key:
                self.runtime=FallGeometryRuntime(ground.get('normal'),ground.get('offset_m'))
                self.plane_key=key
            rows=state.get('target_source_rows') or []
            if any(not isinstance(v,(int,np.integer)) or isinstance(v,bool) for v in rows):
                raise ValueError('invalid target row type')
            if np.iscomplexobj(points):raise ValueError('complex target points')
            raw=np.asarray(points,dtype=np.float64) if points is not None else np.empty((0,3))
            ids=np.asarray(rows,dtype=np.int64)
            if raw.ndim!=2 or raw.shape[1]!=3 or (ids<0).any() or (ids>=len(raw)).any() or len(np.unique(ids))!=len(ids):
                raise ValueError('invalid target provenance')
            observed=bool(state.get('track_status')=='locked' and not state.get('position_predicted')
                and state.get('observability')!='invalid' and len(ids)>=10)
            stamp=(state.get('source') or {}).get('source_stamp_s')
            output=self.runtime.push(raw[ids],stamp,(state.get('session_id'),state.get('track_id')),
                (state.get('time_epoch'),state.get('action_generation'),state.get('selection_version')),
                (json.dumps(state.get('calibration'),sort_keys=True),key),observed=observed)
            self.latest=dict(binding=self.binding(state),output=output)
        except (ValueError,TypeError,KeyError,OverflowError,FloatingPointError,np.linalg.LinAlgError):
            self.errors+=1
            if self.runtime is not None:self.runtime._clear_motion()

    def state(self,payload):
        state=self.regions.state(payload)
        current=(self.latest is not None and state.get('observability')!='invalid'
            and state.get('track_status')=='locked' and not state.get('position_predicted')
            and self.latest['binding']==self.binding(state))
        if not current:
            if self.runtime is not None:self.runtime._clear_motion()
            output=dict(state='unknown',reason='NO_CURRENT_SOURCE_BOUND_MEASUREMENT',
                evidence=None,new_event=None,event_id=None,observed=False,confirmed_enabled=False)
        else:output=self.latest['output']
        # A nested candidate is telemetry only; it never enters result['event'],
        # the production fall state machine or its event persistence path.
        state['event_geometry_shadow']=dict(output,mode='shadow',enabled=True,
            geometry_source_sha256=self.source_sha256,model_loaded=False,
            physical_validity='UNKNOWN',errors=self.errors)
        return state

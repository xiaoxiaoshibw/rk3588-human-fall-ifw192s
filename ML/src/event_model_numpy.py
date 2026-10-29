"""Masked GRU event scorer, Python 3.8 + NumPy only; never a confirmed alarm.

PyTorch gate order/equations: r,z,n; reset multiplies the entire hidden candidate
affine expression including its bias. Missing normalized values use their mean
with separate mask bits, never fabricated physical zeros.
"""
from collections import deque
import hashlib
import json
import math
from pathlib import Path

import numpy as np

from fall_candidate_runtime import file_sha256
from fall_geometry import FallGeometryRuntime
from human_pointset import valid_binding

FEATURES=('centroid_height_m','inclination_deg','vertical_span_m','vertical_velocity_m_s',
          'points','dt_s','observed','valid')
TASK='geometry_event_gru_v1'
SCHEMA='geometry_frame_masked_v1'
EPISODE=dict(high=.8,low=.2,positive_s=.3,release_s=.5,context_s=.5,max_gap_s=.5,history_s=2.)


def sigmoid(x):
    exp=np.exp(-np.abs(x))
    return np.where(x>=0,1./(1.+exp),exp/(1.+exp))


def transform(values,mask,mean,scale):
    if any(np.iscomplexobj(v) for v in (values,mean,scale)):
        raise ValueError('Complex event features are unsupported')
    values=np.asarray(values,dtype=np.float64);mask=np.asarray(mask)
    mean,scale=np.asarray(mean,dtype=np.float64),np.asarray(scale,dtype=np.float64)
    if (values.shape[-1:]!=(8,) or mask.shape!=values.shape or mask.dtype!=np.bool_ or
            np.isinf(values).any() or not np.array_equal(np.isfinite(values),mask) or mean.shape!=(8,) or scale.shape!=(8,) or
            not np.isfinite(mean).all() or not np.isfinite(scale).all() or np.any(scale<=0)):
        raise ValueError('Invalid masked event features or normalizer')
    raw=values.copy()
    if np.any(raw[...,4][mask[...,4]]<0):
        raise ValueError('Negative point count')
    raw[...,4]=np.log1p(raw[...,4])
    normalized=np.zeros(raw.shape,dtype=np.float64)
    with np.errstate(over='raise',invalid='raise',divide='raise'):
        normalized[mask]=((np.where(mask,raw,mean)-mean)/scale)[mask]
    return np.concatenate((normalized,mask.astype(np.float64)),axis=-1)


class NumpyEventGRU:
    def __init__(self,path):
        with np.load(path,allow_pickle=False) as data:
            if any(data[name].dtype.kind!='f' for name in data.files):
                raise ValueError('Event GRU arrays must be floating point')
            arrays={name:data[name].astype(np.float64) for name in data.files}
        names=('mean','scale','weight_ih','weight_hh','bias_ih','bias_hh','head_weight','head_bias')
        if set(arrays)!=set(names) or not all(np.isfinite(a).all() for a in arrays.values()):
            raise ValueError('Invalid event GRU weight archive')
        self.__dict__.update(arrays)
        self.hidden_size=self.weight_hh.shape[1] if self.weight_hh.ndim==2 else 0
        h=self.hidden_size
        shapes=dict(mean=(8,),scale=(8,),weight_ih=(3*h,16),weight_hh=(3*h,h),
                    bias_ih=(3*h,),bias_hh=(3*h,),head_weight=(1,h),head_bias=(1,))
        if not 1<=h<=64 or any(arrays[k].shape!=s for k,s in shapes.items()) or np.any(self.scale<=0):
            raise ValueError('Invalid event GRU dimensions/scale')

    def step(self,x,hidden=None):
        if np.iscomplexobj(x) or np.iscomplexobj(hidden):raise ValueError('Complex GRU state')
        x=np.asarray(x,dtype=np.float64)
        hidden=np.zeros(self.hidden_size) if hidden is None else np.asarray(hidden,dtype=np.float64)
        if x.shape!=(16,) or hidden.shape!=(self.hidden_size,) or not np.isfinite(x).all() or not np.isfinite(hidden).all():
            raise ValueError('Invalid event GRU step input')
        with np.errstate(over='raise',invalid='raise',divide='raise'):
            ir,iz,inn=np.split(self.weight_ih@x+self.bias_ih,3)
            hr,hz,hn=np.split(self.weight_hh@hidden+self.bias_hh,3)
            reset,update=sigmoid(ir+hr),sigmoid(iz+hz)
            candidate=np.tanh(inn+reset*hn)
            output=(1-update)*candidate+update*hidden
            probability=float(sigmoid((self.head_weight@output+self.head_bias)[0]))
        return probability,output


class TimedScoreLatch:
    def __init__(self,settings):
        self.settings=settings;self.counter=0;self.active=None;self.gap()

    def gap(self):
        self.positive_since=self.negative_since=None
        self.last_time=None

    def update(self,p,t):
        s=self.settings;event=None
        if not math.isfinite(p) or not 0<=p<=1 or not math.isfinite(t):
            self.gap();raise ValueError('Invalid event probability/time')
        if self.last_time is not None and (t<=self.last_time or t-self.last_time>s['max_gap_s']):self.gap()
        self.last_time=t
        self.positive_since=(t if self.positive_since is None else self.positive_since) if p>=s['high'] else None
        self.negative_since=(t if self.negative_since is None else self.negative_since) if p<=s['low'] else None
        if self.positive_since is not None and t-self.positive_since+1e-9>=s['positive_s'] and self.active is None:
            self.counter+=1;self.active='event-gru:%d'%self.counter
            event=dict(event_id=self.active,kind='ml_fall_candidate',source_stamp_s=t,
                       fall_probability=p,physically_verified=False)
        if self.negative_since is not None and t-self.negative_since+1e-9>=s['release_s']:
            self.active=None
        return event


class EventEvidenceRuntime:
    def __init__(self,manifest_path,ground=None):
        path=Path(manifest_path);self.manifest=json.loads(path.read_text(encoding='utf-8'))
        self.manifest_sha256=file_sha256(path);doc=self.manifest
        if (doc.get('task')!=TASK or doc.get('feature_schema')!=SCHEMA or doc.get('gate_order')!='rzn' or
                doc.get('feature_names')!=list(FEATURES) or doc.get('fusion') not in ('geometry_gate','temporal_only') or
                doc.get('training_status') not in ('trained','untrained_validation_fixture')):
            raise ValueError('Unsupported event model contract')
        model=path.parent/doc['model']
        if Path(doc['model']).name!=doc['model'] or file_sha256(model)!=doc['model_sha256']:
            raise ValueError('Event model path/SHA mismatch')
        self.model=NumpyEventGRU(model);self.model_sha256=doc['model_sha256']
        s=doc.get('episode',{})
        if (set(s)!=set(EPISODE) or not all(isinstance(v,(int,float)) and not isinstance(v,bool) and
            math.isfinite(v) and v>0 for v in s.values()) or not s['low']<s['high']<=1 or
                s['context_s']>s['history_s']):
            raise ValueError('Invalid second-based event episode')
        self.settings=s
        self.event_serial=0
        self.geometry=FallGeometryRuntime(ground['normal'],ground['offset_m']) if ground else None
        self.reset()

    def reset(self):
        self.key=self.last_time=self.started=self.hidden=None
        self.history=deque();self.latch=TimedScoreLatch(self.settings);self.last_geometry_id=None
        if self.geometry is not None:self.geometry.reset()

    def _result(self,state,probability=None,event=None,reason=None):
        return dict(state=state,reason=reason,fall_probability=probability,new_event=event,
                    event_id=self.latch.active,confirmed_enabled=False,manifest_sha256=self.manifest_sha256,
                    model_sha256=self.model_sha256,training_status=self.manifest['training_status'],
                    score_semantics='annotated fall onset to first contact; not whole-clip posture')

    def _unknown(self,reason):
        self.hidden=self.started=None;self.history.clear();self.latch.gap()
        return self._result('unknown',reason=reason)

    def push(self,points,timestamp,identity,generation,calibration,observed=True):
        if self.geometry is None:return self._unknown('missing_ground')
        if isinstance(timestamp,bool):
            self.geometry._clear_motion();self.geometry.last_time=None;self.last_time=None
            return self._unknown('invalid_time')
        if not isinstance(observed,(bool,np.bool_)) or np.iscomplexobj(points):
            self.geometry._clear_motion()
            return self._unknown('invalid_observation')
        try:
            geometry=self.geometry.push(points,timestamp,identity,generation,calibration,observed=observed)
        except (TypeError,ValueError,FloatingPointError,OverflowError,np.linalg.LinAlgError):
            self.geometry._clear_motion()
            return self._unknown('invalid_points_or_time')
        return self.push_evidence(geometry.get('evidence'),timestamp,identity,generation,calibration,
                                  observed=observed,geometry_output=geometry)

    def push_evidence(self,evidence,timestamp,identity,generation,calibration,observed=True,geometry_output=None):
        key=(identity,generation,calibration)
        if not all(valid_binding(v) for v in key):
            self.reset();return self._unknown('invalid_binding')
        if key!=self.key:
            # The point-based caller already consumed this frame in the geometry
            # branch. Reset model state without resetting its parallel geometry.
            self.hidden=self.started=self.last_time=None;self.history.clear()
            self.latch=TimedScoreLatch(self.settings);self.last_geometry_id=None;self.key=key
        if isinstance(timestamp,bool) or not isinstance(timestamp,(int,float,np.integer,np.floating)) or not math.isfinite(timestamp):
            self.last_time=None;return self._unknown('invalid_time')
        t=float(timestamp);dt=None if self.last_time is None else t-self.last_time;self.last_time=t
        if dt is not None and (dt<=0 or dt>self.settings['max_gap_s']):return self._unknown('time_discontinuity')
        if not isinstance(observed,(bool,np.bool_)) or not observed or not evidence or evidence.get('valid') is not True:
            return self._unknown('not_measured')
        try:
            raw=[evidence.get(k,np.nan) if evidence.get(k) is not None else np.nan for k in FEATURES]
            if np.iscomplexobj(raw):return self._unknown('invalid_measurement')
            values=np.asarray(raw,dtype=np.float64)
            values[5:]=[np.nan if dt is None else dt,1.,1.]
            if not np.isfinite(values[[0,2,4]]).all() or values[4]<10:return self._unknown('invalid_measurement')
            x=transform(values,np.isfinite(values),self.model.mean,self.model.scale)
            p,self.hidden=self.model.step(x,self.hidden)
        except (TypeError,ValueError,FloatingPointError,OverflowError):return self._unknown('invalid_model_input')
        if self.started is None:self.started=t
        if t-self.started+1e-9<self.settings['context_s']:return self._result('warming',probability=None)
        self.history.append((t,p))
        while self.history and t-self.history[0][0]>self.settings['history_s']:self.history.popleft()
        if self.manifest['training_status']!='trained':return self._result('untrained_fixture',p)
        event=None
        if self.manifest['fusion']=='temporal_only':
            event=self.latch.update(p,t)
        elif geometry_output is not None:
            if geometry_output.get('event_id') is None:self.latch.active=None
            candidate=geometry_output.get('new_event')
            if candidate and candidate['event_id']!=self.last_geometry_id:
                self.last_geometry_id=candidate['event_id']
                if max(v for _,v in self.history)>=self.settings['high']:
                    self.latch.active='event-gru:'+candidate['event_id']
                    event=dict(candidate,event_id=self.latch.active,kind='ml_fall_candidate',
                               fall_probability=p,history_peak=max(v for _,v in self.history))
        if event is not None:
            self.event_serial+=1
            prefix=hashlib.sha256((self.manifest_sha256+repr(self.key)).encode()).hexdigest()[:16]
            self.latch.active='event-gru:%s:%d'%(prefix,self.event_serial)
            event.update(event_id=self.latch.active,model_sha256=self.model_sha256,
                         manifest_sha256=self.manifest_sha256)
        return self._result('fall_candidate_active' if self.latch.active else 'scored',p,event)

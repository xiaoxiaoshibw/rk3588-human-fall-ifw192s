"""Separated causal axis, descent evidence, and weak continuation ablations."""
import argparse
import copy
import sys
import time
from pathlib import Path
import numpy as np
from actions import HERE, read, dump, sha, choose
from core import skeleton, roi_mask
from experiment_actions import supported_regions
from next_dev import node_metrics, aggregate
from next_contract import validate_frozen_inputs

TEMPORAL = {'axis_reference_max_age_s': .5, 'armed_max_age_s': 2., 'descent_min_drop_m': .20,
            'fast_descent_mps': .35, 'weak_min_points': 100, 'weak_gate_m': .30,
            'weak_max_age_s': .5, 'ambiguity_ratio': .9}


class RecentAxis:
    def __init__(self,cfg):self.cfg=copy.deepcopy(cfg);self.reference=None;self.last=None;self.identity=None
    def update(self,t,fi,identity,p,ids,sk):
        if self.last is not None and (t<=self.last or t-self.last>self.cfg['max_gap_s'] or identity!=self.identity):self.reference=None
        self.last,self.identity=t,identity
        if not len(ids):self.reference=None;return copy.deepcopy(sk)
        if self.reference and t-self.reference['device_time']>TEMPORAL['axis_reference_max_age_s']:self.reference=None
        result=copy.deepcopy(sk);axis=sk.get('axis');ref=copy.deepcopy(self.reference)
        if axis is None:return result
        if ref and np.dot(axis,ref['axis'])<0:
            axis=-np.array(axis);result=supported_regions(p[ids],ids,axis,self.cfg)
        result['orientation']={'reference':ref,'source':'PAST_SIGN_CURRENT_AXIS' if ref else 'CURRENT_AXIS', 'identity':'UNKNOWN'}
        result['display_xyz']=None;result['predicted_nodes']=[]
        # Only current, non-ambiguous measured axes refresh a reference.
        self.reference={'fi':fi,'device_time':t,'identity':identity,'axis':np.asarray(axis).tolist(),'source_rows':ids.tolist()}
        return result


class RecentEvent:
    def __init__(self,cfg):
        self.cfg=copy.deepcopy(cfg);self.last=None;self.identity=None;self.armed=None;self.low_since=None;self.emitted=False;self.transition=None
    def update(self,t,fi,identity,p,ids):
        reset=self.last is not None and (t<=self.last or t-self.last>self.cfg['max_gap_s'] or identity!=self.identity)
        if reset or not len(ids):self.armed=None;self.low_since=None;self.emitted=False;self.transition=None
        self.last,self.identity=t,identity
        if not len(ids):return {'state':'LOST','event':None,'confirmed':False,'time_reset':reset}
        q=p[ids];median,p90=np.quantile(q[:,2],[.5,.9]);span=np.quantile(q,.98,axis=0)-np.quantile(q,.02,axis=0)
        low=p90<=self.cfg['lying_p90_m'] and max(span[:2])>=self.cfg['lying_min_extent_xy_m'] and span[2]<=self.cfg['lying_max_extent_z_m']
        upright=p90>=self.cfg['standing_p90_m'] and span[2]>=self.cfg['standing_extent_z_m']
        observation={'fi':fi,'device_time':t,'identity':identity,'source_rows':ids.tolist(),'height_median_m':float(median)}
        if self.armed and t-self.armed['device_time']>TEMPORAL['armed_max_age_s']:self.armed=None
        if upright:
            self.armed=observation;self.emitted=False
        event=None;velocity=None;kind=None
        if low:
            if self.low_since is None:
                self.low_since=t;self.transition=None
                if self.armed:
                    dt=t-self.armed['device_time'];drop=self.armed['height_median_m']-median
                    if dt>0 and drop>=TEMPORAL['descent_min_drop_m']:
                        velocity=-float(drop/dt)
                        kind='FAST_DESCENT_TO_LOW' if -velocity>=TEMPORAL['fast_descent_mps'] else 'SLOW_DESCENT_TO_LOW'
                        self.transition={'kind':kind,'before':copy.deepcopy(self.armed),'after':observation,
                                         'drop_m':float(drop),'velocity_mps':velocity,'confirmed':False}
            sustained=t-self.low_since>=self.cfg['lying_hold_s']
            state='SUSTAINED_LOW_POSTURE' if sustained else 'LOW_PENDING'
            if sustained and self.transition and not self.emitted:
                event=copy.deepcopy(self.transition);event['low_confirmation']=observation;self.emitted=True
        else:
            self.low_since=None;self.transition=None;state='STANDING' if upright else 'NON_LOW_GEOMETRIC_POSTURE'
        return {'state':state,'event':event,'confirmed':False,'time_reset':reset,'armed':copy.deepcopy(self.armed),
                'vertical_velocity_mps':velocity,'height_median':float(median),'height_p90':float(p90),'extent':span.tolist(),
                'reason':'CONTROLLED_LYING_NOT_TRUE_FALL_TP; IDENTITY_UNKNOWN'}


class WeakContinuation:
    def __init__(self,cfg):self.cfg=copy.deepcopy(cfg);self.last_t=None;self.center=None;self.strong_seen=None;self.generation=0
    def update(self,t,groups,p,fg):
        if self.last_t is not None and (t<=self.last_t or t-self.last_t>self.cfg['max_gap_s']):self.center=self.strong_seen=None
        self.last_t=t
        if self.strong_seen is not None and t-self.strong_seen>TEMPORAL['weak_max_age_s']:self.center=self.strong_seen=None
        eligible=[]
        for g in groups:
            win=choose([g],p,fg,self.cfg,self.center,None)
            if win is not None:eligible.append((win[0],g,win[2]))
        eligible.sort(key=lambda x:x[0],reverse=True)
        if len(eligible)>1 and eligible[1][0]>=eligible[0][0]*TEMPORAL['ambiguity_ratio']:
            return np.empty(0,int),None,'UNKNOWN_MULTIPLE_STRONG'
        if eligible:
            _,g,c=eligible[0]
            if self.center is None:self.generation+=1
            self.center=c[:2];self.strong_seen=t
            return fg[g],'WEAK-GEOMETRY-'+str(self.generation),'STRONG_GEOMETRIC_UNKNOWN_IDENTITY'
        if self.center is None:return np.empty(0,int),None,'LOST_NO_STRONG_REFERENCE'
        candidates=[]
        for g in groups:
            ids=fg[g];q=p[ids];span=np.quantile(q,.98,axis=0)-np.quantile(q,.02,axis=0)
            if len(ids)<TEMPORAL['weak_min_points'] or len(ids)>=self.cfg['person_min_points']:continue
            if roi_mask(q,self.cfg['roi_xy']).mean()<self.cfg['person_min_roi_fraction'] or max(span)>self.cfg['person_max_span_m']:continue
            if np.linalg.norm(np.median(q,axis=0)[:2]-self.center)<=TEMPORAL['weak_gate_m']:candidates.append(ids)
        if len(candidates)!=1:return np.empty(0,int),None,'UNKNOWN_MULTIPLE_WEAK' if candidates else 'LOST_NO_WEAK'
        # Weak measurements do not refresh strong_seen or create an identity.
        return candidates[0],'WEAK-GEOMETRY-'+str(self.generation),'WEAK_CONTINUATION_IDENTITY_UNKNOWN'


class RecentNonLowEvent(RecentEvent):
    """Contract r2: bounded reliable non-low evidence, not standing-only memory.

    Thresholds are unchanged. A current measured axis is a geometric reliability
    gate, never proof of human identity. History contains source IDs and scalars.
    """
    def __init__(self,cfg):
        super().__init__(cfg);self.nonlow=[]

    def update(self,t,fi,identity,p,ids):
        reset=self.last is not None and (t<=self.last or t-self.last>self.cfg['max_gap_s'] or identity!=self.identity)
        if reset or not len(ids):self.nonlow=[]
        self.nonlow=[o for o in self.nonlow if 0<=t-o['device_time']<=TEMPORAL['armed_max_age_s']]
        if len(ids)>=self.cfg['person_min_points']:
            q=p[ids];median,p90=np.quantile(q[:,2],[.5,.9]);span=np.quantile(q,.98,axis=0)-np.quantile(q,.02,axis=0)
            low=p90<=self.cfg['lying_p90_m'] and max(span[:2])>=self.cfg['lying_min_extent_xy_m'] and span[2]<=self.cfg['lying_max_extent_z_m']
            if not low and 'axis' in skeleton(q,ids,self.cfg):
                self.nonlow.append({'fi':fi,'device_time':t,'identity':identity,'source_rows':ids.tolist(),
                                    'height_median_m':float(median),'reliability':'CURRENT_MEASURED_AXIS_NONLOW_GEOMETRY_NOT_IDENTITY'})
        if self.nonlow:self.armed=copy.deepcopy(max(self.nonlow,key=lambda o:o['height_median_m']))
        result=super().update(t,fi,identity,p,ids)
        result['event_contract']='RECENT_RELIABLE_NONLOW_R2'
        return result


def run(e):
    manifest=validate_frozen_inputs(e);cfg=manifest['config'];selection=read(e/'SELECTION.json')
    base_group='D' if selection['outcome']=='GEOMETRIC_CANDIDATE' else 'B'
    code_bindings={n:sha(HERE/n) for n in ['next_temporal.py','next_dev.py','core.py','actions.py','experiment_actions.py','next_contract.py']}
    dump(e/'TEMPORAL_MANIFEST.json',{'base_group':base_group,'parameters':TEMPORAL,'code_sha256':code_bindings,
         'single_factors':{'E_axis':'axis sign only, same source members and old posture','F_event':'event only, same members and old skeleton','G_weak':'association only, same geometry and old skeleton/posture'},
         'negative_policy':{'controlled_lying':'NOT_TRUE_FALL_TP','initial_low':'SYNTHETIC_CONTRACT_AND_GEOMETRIC_REPLAY',
             'active_slow_lying':'NO_INDEPENDENT_ACTION_GT','sit_bend_kneel_furniture_fov_occlusion':'NOT_RUN_UNVERIFIED_CATEGORY_COVERAGE',
             'false_alarms_per_hour':'NOT_RUN_NO_LONG_SESSION','MPJPE_PCK':'BLOCKED_NO_JOINT_GT'},'command':sys.argv})
    records={g:[] for g in ['E_axis','F_event','G_weak']};events=[]
    from actions import Posture
    for session in read(e/'catalog.json')['sessions']:
        sid=session['session_id'];axis=RecentAxis(cfg);event=RecentEvent(cfg);weak=WeakContinuation(cfg);weakposture=Posture(copy.deepcopy(cfg));weak_identity=None;previous={}
        from next_dev import load
        _,raw,source_hashes=load(sid)
        if source_hashes!=manifest['source_sha256'][sid]:raise ValueError('Temporal source drift')
        del raw
        for fi in session['available_frames']:
            base=read(e/'runs'/base_group/sid/f'{fi:04d}.json');t=base['device_time'];ids=np.array(base['selection']['selected_source_indices'],int)
            if sha(e/'common'/sid/f'{fi:04d}.npz')!=base['common_sha256'] or sha(e/'runs'/base_group/sid/f'{fi:04d}_members.npz')!=base['member_sha256']:
                raise ValueError('Temporal frozen input content changed')
            with np.load(e/'common'/sid/f'{fi:04d}.npz') as data:p=data['xyz'].copy()
            with np.load(e/'runs'/base_group/sid/f'{fi:04d}_members.npz') as data:arrays={k:data[k].copy() for k in data.files}
            sk=base['body_3d'][0]['skeleton'] if len(ids) else skeleton(p[ids],ids,cfg);identity=base['body_3d'][0]['id'] if len(ids) else None
            started=time.perf_counter();signed=axis.update(t,fi,identity,p,ids,sk);axis_ms=(time.perf_counter()-started)*1000
            started=time.perf_counter();posture=event.update(t,fi,identity,p,ids);event_ms=(time.perf_counter()-started)*1000
            fg=arrays['foreground'];labels=arrays['cluster_id'][fg];groups=[np.flatnonzero(labels==c) for c in np.unique(labels) if c>=0]
            started=time.perf_counter();weakids,weakidentity,status=weak.update(t,groups,p,fg);weak_ms=(time.perf_counter()-started)*1000
            if weakidentity!=weak_identity:
                weakposture=Posture(copy.deepcopy(cfg));weak_identity=weakidentity
            for group,currentids,currentsk,currentposture,currentidentity in [('E_axis',ids,signed,base['posture'],identity),('F_event',ids,sk,posture,identity),
                    ('G_weak',weakids,skeleton(p[weakids],weakids,cfg),weakposture.update(t,p[weakids] if len(weakids) else None),weakidentity)]:
                row=copy.deepcopy(base);folder=e/'runs'/group/sid;folder.mkdir(parents=True,exist_ok=True);row['variant']=group;row['temporal_base']=base_group
                row['posture']=currentposture;row['temporal_code_sha256']=sha(HERE/'next_temporal.py');row['temporal_parameters']=copy.deepcopy(TEMPORAL)
                row['selection']['selected_source_indices']=currentids.tolist()
                body=[]
                if len(currentids):
                    sample=currentids[np.linspace(0,len(currentids)-1,min(len(currentids),cfg['display_sample_points']),dtype=int)]
                    body=[{'id':currentidentity,'kind':'AUTOMATIC_CANDIDATE','points':p[sample].tolist(),'display_source_indices':sample.tolist(),'source_indices':currentids.tolist(),
                           'point_count':len(currentids),'bbox':{'min':p[currentids].min(axis=0).tolist(),'max':p[currentids].max(axis=0).tolist()},'skeleton':currentsk,
                           'semantic_identity':'UNKNOWN','model_status':'NOT_USED','independence':{'score_0_100':0,'separation_status':'UNKNOWN'},'rf_xyz_prob':0,'pointnet_prob':0}]
                row.update(body_3d=body,roi_3d=body,full_3d=body,association_status=status if group=='G_weak' else 'FROZEN_GEOMETRY')
                copied={k:v.copy() for k,v in arrays.items()};copied['selected']=currentids
                copied['terminal_reason'][copied['terminal_reason']==5]=4;copied['terminal_reason'][currentids]=5
                np.savez_compressed(folder/f'{fi:04d}_members.npz',**copied);row['member_sha256']=sha(folder/f'{fi:04d}_members.npz')
                dump(folder/f'{fi:04d}.json',row)
                metrics=node_metrics(currentsk,previous.get(group),currentidentity,t,cfg);previous[group]={'identity':currentidentity,'t':t,'sk':currentsk}
                records[group].append({'sid':sid,'fi':fi,'selected_count':len(currentids),'fg_count':len(fg),
                                       'cpu_ms':{'E_axis':axis_ms,'F_event':event_ms,'G_weak':weak_ms}[group],'state':currentposture['state'],**metrics})
                for n in currentsk['nodes'].values():
                    if n['valid']:assert set(n['support_source_indices'])<=set(currentids.tolist()) and np.allclose(n['xyz'],p[n['support_source_indices']].mean(axis=0))
                if group=='F_event' and currentposture['event']:events.append({'sid':sid,'fi':fi,'source_sha256':base['source_sha256'],**currentposture['event']})
        print('TEMPORAL',sid,'complete',flush=True)
    dump(e/'TEMPORAL_STATS.json',records);dump(e/'EVENT_EVIDENCE.json',events)
    dump(e/'TEMPORAL_SUMMARY.json',{'base_group':base_group,'groups':{g:aggregate(rs) for g,rs in records.items()},'events':len(events),
         'event_accuracy':'BLOCKED_NO_TRUE_FALL_OR_NEGATIVE_IDENTITY_GT','command':sys.argv,'stage_status':'TEMPORAL_COMPLETED'})


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--evidence',type=Path,required=True);args=parser.parse_args();run(args.evidence.resolve())

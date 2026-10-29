"""Offline masked-GRU preflight, optional fitting and NumPy export.

Default CLI only audits inputs. Training is a separate --train operation; this
module does not use test-person arrays for normalization, fitting or epoch choice.
"""
import argparse
import json
from pathlib import Path

import numpy as np
import torch
from torch import nn

from event_model_numpy import FEATURES,TASK,SCHEMA,EPISODE,transform,NumpyEventGRU
from fall_candidate_runtime import file_sha256


class EventScorer(nn.Module):
    def __init__(self,hidden_size=8):
        super().__init__()
        if not isinstance(hidden_size,int) or isinstance(hidden_size,bool) or not 1<=hidden_size<=64:
            raise ValueError('Invalid hidden size')
        self.gru=nn.GRU(16,hidden_size,batch_first=True)
        self.head=nn.Linear(hidden_size,1)

    def forward(self,x,hidden=None):
        states,hidden=self.gru(x,hidden)
        return self.head(states).squeeze(-1),hidden


def load_cache(path):
    doc=json.loads((path/'INPUT.json').read_text(encoding='utf-8'))
    if (doc.get('schema')!='fall_event_cache_v1' or doc.get('feature_names')!=list(FEATURES) or
            file_sha256(path/'frames.npz')!=doc.get('frame_cache_sha256')):
        raise ValueError('Event cache schema/features/SHA mismatch')
    with np.load(path/'frames.npz',allow_pickle=False) as data:
        X,mask,times,segments,bindings=(data[k].copy() for k in
            ('features','feature_mask','timestamps_s','segment_index','bindings'))
    if (np.iscomplexobj(X) or np.iscomplexobj(times) or np.isinf(X).any() or
            times.ndim!=1 or X.shape!=(len(times),8) or mask.shape!=X.shape or mask.dtype!=np.bool_ or
            not np.array_equal(mask,np.isfinite(X)) or not len(times) or
            not np.isfinite(times).all() or np.any(np.diff(times)<=0) or
            segments.shape!=times.shape or segments.dtype.kind not in 'iu' or
            bindings.shape!=times.shape or doc.get('frames')!=len(times)):
        raise ValueError('Invalid event cache arrays')
    observed=segments>=0
    if (not np.all(mask[observed][:,[0,2,4,6,7]]) or not np.all(X[observed,6:]==1) or
            np.any(X[observed,4]<10)):
        raise ValueError('Segment claims valid but required measurements are absent')
    for i in range(1,len(times)):
        if segments[i]>=0 and segments[i]==segments[i-1]:
            if times[i]-times[i-1]>EPISODE['max_gap_s'] or bindings[i]!=bindings[i-1]:
                raise ValueError('Segment crosses time gap or binding')
    warmed=np.zeros(len(times),dtype=np.bool_);segment_start=None
    for i in range(len(times)):
        if segments[i]<0:segment_start=None;continue
        if segment_start is None or (i and segments[i]!=segments[i-1]):segment_start=times[i]
        warmed[i]=times[i]-segment_start+1e-9>=EPISODE['context_s']
    y=np.full(len(times),-1,dtype=np.int64);audit=[]
    for window in doc.get('windows',[]):
        if window.get('label') is None or window.get('certainty')!='confirmed':
            audit.append(dict(event_id=window['id'],usable_frames=0,reason='unknown_annotation'));continue
        if window['label'] not in (0,1):raise ValueError('Invalid event label')
        if 'event_impact' not in window or 'clock_uncertainty_s' not in window:
            raise ValueError('Rebuild cache with contact time and timing uncertainty')
        uncertainty=float(window['clock_uncertainty_s'])
        if not np.isfinite(uncertainty) or not 0<=uncertainty<=.2:
            raise ValueError('Invalid training annotation uncertainty')
        begin,finish=window['event_start'],window['event_end']
        if not np.isfinite([begin,finish]).all() or begin>finish:raise ValueError('Invalid annotation interval')
        start=begin+uncertainty
        end=(window['event_impact'] if window['label']==1 else finish)
        if end is None:raise ValueError('Positive event lacks contact time')
        if not np.isfinite(end) or not begin<=end<=finish:raise ValueError('Invalid contact time')
        end-=uncertainty
        selected=(times>=start)&(times<=end)
        if np.any(y[selected]>=0):raise ValueError('Overlapping supervision intervals')
        y[selected]=window['label']
        count=int(np.sum(selected&observed&warmed))
        audit.append(dict(event_id=window['id'],label=window['label'],usable_frames=count,
                          reason='usable' if count else 'no_unambiguous_observed_interval'))
    y[~(observed&warmed)]=-1
    # All entries remain in the audit, even when no frame can contribute loss.
    return dict(metadata=doc,X=X,mask=mask,times=times,segments=segments,y=y,path=path,event_audit=audit)


def preflight(index_path):
    index=json.loads(index_path.read_text(encoding='utf-8'))
    groups={name:set(index[name+'_subjects']) for name in ('train','validation','test')}
    if (any(len(index[role+'_subjects'])!=len(values) for role,values in groups.items()) or
            any(not values or any(not isinstance(s,str) or not s for s in values) for values in groups.values()) or
            any(groups[a]&groups[b] for a,b in (('train','validation'),('train','test'),('validation','test')))):
        raise ValueError('Explicit nonempty person-isolated train/validation/test split required')
    records=[];seen=set();contents=set()
    for value in index['caches']:
        path=(index_path.parent/value).resolve()
        doc=json.loads((path/'INPUT.json').read_text(encoding='utf-8'))
        if doc.get('schema')!='fall_event_cache_v1' or doc.get('feature_names')!=list(FEATURES):
            raise ValueError('Held-out/train cache metadata schema mismatch')
        subject=doc.get('subject');roles=[role for role,people in groups.items() if subject in people]
        if len(roles)!=1:raise ValueError('Unknown/ambiguous cache subject')
        if doc.get('session') in seen or doc.get('frame_cache_sha256') in contents:
            raise ValueError('Duplicate session/cache content across records')
        seen.add(doc['session']);contents.add(doc['frame_cache_sha256'])
        if file_sha256(path/'frames.npz')!=doc['frame_cache_sha256']:
            raise ValueError('Cache SHA mismatch')
        records.append(dict(path=path,subject=subject,session=doc['session'],role=roles[0],
                            metadata_sha256=file_sha256(path/'INPUT.json'),cache_sha256=doc['frame_cache_sha256']))
    if not records or any(not any(r['role']==role for r in records) for role in groups):
        raise ValueError('Every declared split needs recorded sessions')
    training=[load_cache(r['path']) for r in records if r['role']=='train']
    labels=np.concatenate([r['y'][r['y']>=0] for r in training])
    report=dict(schema='fall_event_training_preflight_v1',index_sha256=file_sha256(index_path),
                records=[dict(r,path=str(r['path'])) for r in records],
                train_positive_frames=int(np.sum(labels==1)),train_negative_frames=int(np.sum(labels==0)),
                training_ready=bool(np.any(labels==0) and np.any(labels==1)),
                retained_events=sum(len(r['metadata'].get('windows',[])) for r in training),
                event_audit=[event for r in training for event in r['event_audit']],
                training_events_without_usable_supervision=[event for r in training for event in r['event_audit'] if not event['usable_frames']],
                person_split_qualification='metadata-declared subject IDs; not independent identity verification',
                test_arrays_read_for_training=False,unlabelled_frames='ignored for loss, retained as causal context')
    return training,report


def normalizer(training):
    rows=np.concatenate([r['X'][r['segments']>=0] for r in training])
    raw=rows.copy()
    if np.any(raw[:,4][np.isfinite(raw[:,4])]<0):raise ValueError('Negative point count')
    raw[:,4]=np.log1p(raw[:,4])
    mean=[];scale=[]
    for column in raw.T:
        visible=column[np.isfinite(column)]
        if not len(visible):raise ValueError('No measured training values for a feature')
        mean.append(float(visible.mean()));scale.append(max(float(visible.std()),1e-6))
    return np.asarray(mean),np.asarray(scale)


def export(model,mean,scale,out,status='untrained_validation_fixture',fusion='geometry_gate'):
    if status not in ('trained','untrained_validation_fixture') or fusion not in ('geometry_gate','temporal_only'):
        raise ValueError('Invalid event export qualification')
    out.mkdir(parents=True,exist_ok=False)
    arrays=dict(mean=np.asarray(mean),scale=np.asarray(scale))
    state=model.state_dict()
    for key in ('weight_ih','weight_hh','bias_ih','bias_hh'):
        arrays[key]=state['gru.'+key+'_l0'].detach().cpu().numpy()
    arrays['head_weight']=state['head.weight'].detach().cpu().numpy()
    arrays['head_bias']=state['head.bias'].detach().cpu().numpy()
    with (out/'weights.npz').open('xb') as stream:np.savez_compressed(stream,**arrays)
    NumpyEventGRU(out/'weights.npz')
    manifest=dict(task=TASK,feature_schema=SCHEMA,feature_names=list(FEATURES),gate_order='rzn',
                  model='weights.npz',model_sha256=file_sha256(out/'weights.npz'),
                  training_status=status,fusion=fusion,episode=EPISODE,
                  physical_validity='UNKNOWN',confirmed_enabled=False,
                  input_encoding='8 normalized measurements + 8 availability masks; log1p point count',
                  source_sha256={p.name:file_sha256(p) for p in (Path(__file__),Path(__file__).with_name('event_model_numpy.py'))})
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2,allow_nan=False),encoding='utf-8')
    return out/'manifest.json'


def fit(index_path,out,epochs=20,hidden_size=8,seed=42):
    if not isinstance(epochs,int) or isinstance(epochs,bool) or epochs<1:raise ValueError('Positive fixed epoch budget required')
    training,report=preflight(index_path)
    if not report['training_ready']:raise ValueError('Training requires both confirmed positive and negative samples')
    mean,scale=normalizer(training)
    torch.manual_seed(seed);model=EventScorer(hidden_size)
    optimizer=torch.optim.AdamW(model.parameters(),lr=.001,weight_decay=.01)
    out.mkdir(parents=True,exist_ok=False)
    (out/'PROTOCOL.json').write_text(json.dumps(dict(report=report,epochs=epochs,seed=seed,hidden_size=hidden_size,
        epoch_selection='fixed final epoch; no validation/test arrays used',
        gradient_context_s=2.,normalization='training measurements only'),indent=2),encoding='utf-8')
    losses=[]
    for _ in range(epochs):
        total=0.;steps=0
        for record in training:
            encoded=transform(record['X'],record['mask'],mean,scale).astype(np.float32)
            times,segments,labels=record['times'],record['segments'],record['y'];i=0
            while i<len(times):
                if segments[i]<0:i+=1;continue
                segment=segments[i];hidden=None
                while i<len(times) and segments[i]==segment:
                    end=i+1
                    while end<len(times) and segments[end]==segment and times[end]-times[i]<2.:end+=1
                    logits,hidden=model(torch.from_numpy(encoded[i:end][None]),hidden)
                    selected=labels[i:end]>=0
                    if np.any(selected):
                        loss=nn.functional.binary_cross_entropy_with_logits(logits[0,selected],
                            torch.from_numpy(labels[i:end][selected].astype(np.float32)))
                        optimizer.zero_grad();loss.backward();nn.utils.clip_grad_norm_(model.parameters(),5.)
                        optimizer.step();total+=float(loss.detach());steps+=1
                    hidden=hidden.detach();i=end
        losses.append(total/steps if steps else None)
    path=export(model.eval(),mean,scale,out/'model',status='trained')
    (out/'TRAINING.json').write_text(json.dumps(dict(losses=losses,manifest=str(path),test_evaluated=False),indent=2),encoding='utf-8')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--index',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--train',action='store_true');parser.add_argument('--epochs',type=int,default=20)
    args=parser.parse_args()
    if args.train:report=fit(args.index,args.output,args.epochs)
    else:
        _,report=preflight(args.index);args.output.mkdir(parents=True,exist_ok=False)
        (args.output/'PREFLIGHT.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))

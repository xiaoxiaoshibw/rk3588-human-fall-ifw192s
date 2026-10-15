"""Bounded sign convention from independently current-supported axes; original R3 retained."""
import copy
from pathlib import Path
import numpy as np
from actions import HERE, OUT, read, load, dump, sha
from research_r3 import E, RESULT
from research_actions import frame_points
from experiment_actions import supported_regions

CURRENT_SOURCES={'CURRENT_RECOVERED_RELIABLE_AXIS','CURRENT_ANCHOR_LOCAL_AXIS','CENTRAL_CURRENT_SUBSPACE','UPPER_CURRENT_SUBSPACE','UNIFORM_CURRENT_VOXEL_SUBSPACE'}

class AxisSign:
    def __init__(self,cfg):self.cfg=cfg;self.reference=None;self.last=None;self.identity=None
    def update(self,t,fi,identity,sk,p,members):
        if self.last is not None and (t<=self.last or t-self.last>self.cfg['max_gap_s'] or identity!=self.identity):self.reference=None
        self.last=t;self.identity=identity
        if not len(members):self.reference=None;return sk
        if self.reference and t-self.reference['t_sec']>self.cfg['axis_reference_max_age_s']:self.reference=None
        result=copy.deepcopy(sk);axis=sk.get('axis');source=sk.get('direction',{}).get('source','MISSING');ref=copy.deepcopy(self.reference)
        if axis is None:result['orientation']={'source':'MISSING','reference':None,'flipped':False};return result
        axis=np.array(axis);flipped=ref is not None and np.dot(axis,ref['axis'])<0
        if flipped:
            axis=-axis;result=supported_regions(p[members],members,axis,self.cfg)
            for key in ['direction','predicted_nodes','anatomical_accuracy']:result[key]=copy.deepcopy(sk[key])
        result['orientation']={'source':'BOUNDED_PAST_SIGN_CURRENT_AXIS' if ref else 'CURRENT_SIGN_NO_REFERENCE','reference':ref,'flipped':bool(flipped),
            'identity':'UNKNOWN','note':'Unoriented current line unchanged; coarse regions recomputed from current members only'}
        if source in CURRENT_SOURCES:
            # Every refresh comes from an independent current strong observation, never a carried direction.
            self.reference={'fi':fi,'t_sec':t,'target_id':identity,'axis':axis.tolist(),'current_source':source}
        result['predicted_nodes']=[];return result

def run():
    freeze=read(HERE/'config_axis_sign_r3.json');assert freeze['status']=='FROZEN_DIAGNOSTIC_ACTIONS_BEFORE_FULL_REPLAY'
    cfg=read(OUT/'RUN_MANIFEST.json')['config'];cfg.update(read(HERE/'config_research_r2.json'));cfg.update(read(HERE/'config_research_r3.json'))
    cat=read(OUT/'catalog.json');prior=Path(cfg['background_experiment']);stats={v:[] for v in ['r3_signed','r3_signed_feedback']};counts={v:0 for v in stats}
    for v in stats:
        if (RESULT/v).exists():raise ValueError('Exclusive new sign experiment required')
    sources={}
    for rec in cat['sessions']:
        sid=rec['session_id'];meta,raw,hashes=load(sid);assert hashes==rec['source_sha256'];sources[sid]=hashes
        reg=None if sid==cat['background']['session'] else read(prior/(sid+'_registration.json'))
        signs={v:AxisSign(cfg) for v in stats};previous={}
        for fi in rec['available_frames']:
            f=meta['frames'][fi];_,p=frame_points(raw,meta['frames'][fi],reg)
            for v in stats:
                base_v='r3_feedback' if v.endswith('feedback') else 'r3';row=read(RESULT/base_v/sid/f'{fi:04d}.json');new=copy.deepcopy(row);new['variant']=v
                body=new['body_3d'];members=np.array(body[0]['source_indices'],dtype=int) if body else np.array([],dtype=int);identity=body[0]['id'] if body else None
                sk=body[0]['skeleton'] if body else {};result=signs[v].update(row['t_sec'],fi,identity,sk,p,members)
                if body:body[0]['skeleton']=result
                axis=result.get('axis');prev=previous.get(v);dot=float(np.dot(axis,prev['axis'])) if prev and fi==prev['fi']+1 and axis is not None and prev['axis'] is not None else None
                s=new['stats'];s['valid_nodes']=sum(n['valid'] for n in result.get('nodes',{}).values());s['sign_flip']=bool(dot is not None and dot<0)
                s['axis_large_turn']=bool(dot is not None and abs(dot)<np.cos(np.pi/4));s['orientation_adjusted']=result.get('orientation',{}).get('flipped',False)
                s['slot_max_jump_m']=max((float(np.linalg.norm(np.subtract(n['xyz'],prev['nodes'][k]['xyz']))) for k,n in result.get('nodes',{}).items() if prev and fi==prev['fi']+1 and n['valid'] and prev['nodes'][k]['valid']),default=0.)
                for n in result.get('nodes',{}).values():
                    if n['valid']:assert set(n['support_source_indices'])<=set(members) and np.allclose(n['xyz'],p[n['support_source_indices']].mean(axis=0))
                ref=result.get('orientation',{}).get('reference')
                if ref:assert ref['fi']<fi and 0<row['t_sec']-ref['t_sec']<=cfg['axis_reference_max_age_s'] and ref['current_source'] in CURRENT_SOURCES
                assert new['added_members']==row['added_members'] and new['anchor_source_indices']==row['anchor_source_indices']
                previous[v]={'axis':axis,'fi':fi,'nodes':result.get('nodes',{})};stats[v].append(s);counts[v]+=1
                folder=RESULT/v/sid;folder.mkdir(parents=True,exist_ok=True);dump(folder/f'{fi:04d}.json',new)
        print('SIGN REPLAY',sid,flush=True)
    summary={}
    for v,rows in stats.items():
        action=[r for r in rows if not r['sid'].endswith('131958')];empty=[r for r in rows if r['sid'].endswith('131958')]
        summary[v]={k:sum(r[k] for r in action) for k in ['added_count','near_background_added_count','axis_missing','new_axis_missing','sign_flip','axis_large_turn','orientation_adjusted','valid_nodes']}
        summary[v].update(frames=len(rows),empty_targets=sum(r['target_count']>0 for r in empty),slot_jump_max_m=max(r['slot_max_jump_m'] for r in action),
            identity_accuracy='UNKNOWN',anatomical_accuracy='UNKNOWN',promotion='BLOCKED')
    dump(E/'SIGN_COMPARISON.json',{'summary':summary,'frames':stats,'sources':sources,'config_sha256':sha(HERE/'config_axis_sign_r3.json'),'code_sha256':sha(HERE/'axis_sign_r3.py'),
        'recovery_unchanged':True,'old_failed_sign_versions_preserved':True,'holdout_not_tuned':True})
    print(summary,flush=True)

if __name__=='__main__':run()

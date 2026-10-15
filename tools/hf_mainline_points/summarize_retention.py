"""Report all changes, including every new geometric regression; identities remain unknown."""
import sys
from pathlib import Path
from collections import defaultdict
import numpy as np
ROOT=Path(__file__).resolve().parents[2];PS=ROOT/'sidequests/human_fusion_lab_next/pointset/r01';sys.path.insert(0,str(PS))
from actions import read,dump,OUT
from research_retention import RESULT,E


def observe(body,previous):
    if not body:return {'missing':False,'axis':None,'flip':False,'jump':0.,'nodes':{}},None
    sk=body[0]['skeleton'];axis=sk.get('axis');flip=False;jump=0.
    if previous:
        if axis is not None and previous['axis'] is not None:flip=np.dot(axis,previous['axis'])<0
        for k,n in sk['nodes'].items():
            old=previous['nodes'][k]
            if n['valid'] and old['valid']:jump=max(jump,float(np.linalg.norm(np.subtract(n['xyz'],old['xyz']))))
    return {'missing':axis is None,'axis':axis,'flip':bool(flip),'jump':jump,'nodes':sk['nodes']},{'axis':axis,'nodes':sk['nodes']}


def main(run_id):
    root=RESULT/run_id;stats=read(root/'FRAME_METRICS.json')['frames'];cat=read(OUT/'catalog.json');base_metrics={};comparisons=[]
    for rec in cat['sessions']:
        sid=rec['session_id'];prev={}
        for fi in rec['available_frames']:
            metrics={}
            for v,path in [('R1',OUT),('R2',PS/'action_research_r2/component20'),('R3',PS/'action_research_r3/r3_signed')]:
                row=read(path/sid/f'{fi:04d}.json');m,prev[v]=observe(row['body_3d'],prev.get(v));m['count']=row['body_3d'][0]['point_count'] if row['body_3d'] else 0
                m['event']=row['posture']['event'];metrics[v]=m
            base_metrics[(sid,fi)]=metrics
    byvariant={};session=[];holdout=[];regressions=[]
    for v in read(root/'FROZEN_CONFIG.json')['variants']:
        rows=[r for r in stats if r['variant']==v]
        for r in rows:
            old=base_metrics[(r['sid'],r['fi'])];reference=old['R3'] if v=='r3' else old['R1']
            r['new_axis_missing']=bool(r['axis_missing'] and not reference['missing']);r['new_axis_flip']=bool(r['axis_flip'] and not reference['flip'])
            r['slot_jump_delta_m']=r['max_slot_jump_m']-reference['jump'];r['event_changed']=r['event']!=old['R1']['event']
            if r['new_axis_missing'] or r['new_axis_flip'] or r['slot_jump_delta_m']>.01 or r['event_changed'] or r['deleted_count'] or (r['center_offset_m'] or 0)>.02:
                regressions.append(dict(r))
        def summary(part):
            shifts=[r['center_offset_m'] for r in part if r['center_offset_m'] is not None]
            return {'frames':len(part),'pool':sum(r['pool_count'] for r in part),'recovered_UNKNOWN':sum(r['added_count'] for r in part),
                'original_target_deleted':sum(r['deleted_count'] for r in part),'target_missing':sum(r['baseline_count']>0 and not r['target_count'] for r in part),
                'center_p95_m':float(np.quantile(shifts,.95)) if shifts else None,'center_max_m':max(shifts,default=None),
                'axis_missing':sum(r['axis_missing'] for r in part),'new_axis_missing':sum(r['new_axis_missing'] for r in part),
                'axis_flips':sum(r['axis_flip'] for r in part),'new_axis_flips':sum(r['new_axis_flip'] for r in part),
                'max_slot_jump_m':max((r['max_slot_jump_m'] for r in part),default=0),'event_changes':sum(r['event_changed'] for r in part),
                'human_recall':None,'furniture_contamination':None,'furniture_denominator':None,'furniture_status':'NOT_EVALUATED'}
        byvariant[v]=summary(rows)
        holdout.append({'variant':v,'historically_seen':True,'new_independent_test':False,'validation_status':read(root/'FROZEN_CONFIG.json')['validation_status'],**summary([r for r in rows if r['context_holdout']])})
        for rec in cat['sessions']:
            part=[r for r in rows if r['sid']==rec['session_id']];session.append({'variant':v,'sid':rec['session_id'],'recorded_activity_context_not_GT':rec['activity'],**summary(part)})
    baseline={v:{'axis_missing':sum(x[v]['missing'] for x in base_metrics.values()),'axis_flips':sum(x[v]['flip'] for x in base_metrics.values()),
                 'max_slot_jump_m':max(x[v]['jump'] for x in base_metrics.values()),'events':[(s,f,x[v]['event']) for (s,f),x in base_metrics.items() if x[v]['event']]} for v in ['R1','R2','R3']}
    worst={v:sorted([r for r in stats if r['variant']==v],key=lambda r:(r['new_axis_missing'],r['center_offset_m'] or 0,r['max_slot_jump_m']),reverse=True)[:30] for v in byvariant}
    dump(root/'ANALYSIS.json',{'summary':byvariant,'baseline':baseline,'by_session':session,'context_holdout':holdout,'all_new_geometric_regressions':regressions,'worst_frames':worst,
         'note':'80 scored frames are subset of1966, history seen; no denominator pooling; all recovery points UNKNOWN; added count is not human effect',
         'original_9_R3_missing':[{'sid':s,'fi':f} for (s,f),x in base_metrics.items() if x['R3']['missing']]})
    print(byvariant,flush=True)


if __name__=='__main__':main(sys.argv[1])

"""Single-factor event contract rework on frozen B; old zero-event run preserved."""
import argparse
import copy
import sys
import shutil
from pathlib import Path
import numpy as np
from actions import HERE,read,dump,sha
from next_contract import validate_frozen_inputs
from next_dev import load
from next_temporal import RecentNonLowEvent,TEMPORAL


def run(e):
    m=validate_frozen_inputs(e);group='F_event_r2';out=e/'runs'/group;out.mkdir(exist_ok=False)
    code={n:sha(HERE/n) for n in ['event_next_r2.py','next_temporal.py','core.py','next_dev.py','next_contract.py']}
    dump(e/'EVENT_R2_MANIFEST.json',{'run_id':'event_contract_r2','group':group,'base':'B','parameters':TEMPORAL,
         'code_sha256':code,'previous':'F_event/events=0 retained','comparison_consumed':True,
         'change':'standing-only qualification -> recent measured-axis reliable non-low peak; same 2s window and .20m drop',
         'cause':'controlled low-entry ages since standing 2.695s/3.214s; requirement says reliable non-low',
         'true_fall_TP':'BLOCKED_NO_INDEPENDENT_GT','command':sys.argv})
    events=[];stats=[]
    for session in read(e/'catalog.json')['sessions']:
        sid=session['session_id'];_,raw,hashes=load(sid);assert hashes==m['source_sha256'][sid];del raw
        state=RecentNonLowEvent(m['config']);check=RecentNonLowEvent(m['config'])
        folder=out/sid;folder.mkdir()
        for fi in session['available_frames']:
            base=read(e/'runs/B'/sid/f'{fi:04d}.json');common=e/'common'/sid/f'{fi:04d}.npz';members=e/'runs/B'/sid/f'{fi:04d}_members.npz'
            assert sha(common)==base['common_sha256'] and sha(members)==base['member_sha256']
            with np.load(common) as d:p=d['xyz']
            ids=np.array(base['selection']['selected_source_indices'],int);identity=base['body_3d'][0]['id'] if len(ids) else None
            posture=state.update(base['device_time'],fi,identity,p,ids)
            assert posture==check.update(base['device_time'],fi,identity,p,ids)
            row=copy.deepcopy(base);row.update(variant=group,extra_run_id='event_contract_r2',posture=posture,event_code_sha256=code)
            # Exact byte copy, no filesystem alias that could corrupt the old group.
            shutil.copyfile(members,folder/f'{fi:04d}_members.npz')
            dump(folder/f'{fi:04d}.json',row)
            stats.append({'sid':sid,'fi':fi,'state':posture['state'],'event':posture['event'] is not None,
                          'source_sha256':hashes,'device_time':base['device_time']})
            if posture['event']:events.append({'sid':sid,'fi':fi,'source_sha256':hashes,'run_id':'event_contract_r2',**posture['event']})
        print('EVENT R2',sid,'complete',flush=True)
    dump(e/'EVENT_R2_EVIDENCE.json',events);dump(e/'EVENT_R2_STATS.json',stats)
    dump(e/'EVENT_R2_SUMMARY.json',{'frames':len(stats),'events':len(events),'by_session':{s['session_id']:sum(r['event'] for r in stats if r['sid']==s['session_id']) for s in read(e/'catalog.json')['sessions']},
         'fast':sum(r['kind']=='FAST_DESCENT_TO_LOW' for r in events),'slow':sum(r['kind']=='SLOW_DESCENT_TO_LOW' for r in events),
         'initial_low':'NO_DESCENT_WITHOUT_PRIOR_NONLOW','accuracy':'BLOCKED_NO_TRUE_FALL_GT','same_current_members':'B exact byte copies','stage_status':'EVENT_R2_COMPLETE','command':sys.argv})


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--evidence',type=Path,required=True);args=parser.parse_args();run(args.evidence.resolve())

"""Append mutually exclusive candidate end states; retain original first deletion causes."""
import sys,time
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2];PS=ROOT/'sidequests/human_fusion_lab_next/pointset/r01';sys.path.insert(0,str(PS))
from actions import read,dump,sha,OUT
from research_retention import E,RESULT
def main(run_id):
 root=RESULT/run_id
 while not (root/'FRAME_METRICS.json').exists():time.sleep(2)
 baseline_id=read(E/'BASELINE_REPRODUCTION.json')['baseline_id'];cat=read(OUT/'catalog.json');variants=read(root/'FROZEN_CONFIG.json')['variants'];counts={v:{'frames':0,'records':0,'target':0,'recovery_reject':0} for v in variants}
 for rec in cat['sessions']:
  sid=rec['session_id']
  for fi in rec['available_frames']:
   with np.load(RESULT/baseline_id/sid/f'{fi:04d}_qualification.npz') as a:first=a['first_terminal_reason']
   for v in variants:
    with np.load(root/v/sid/f'{fi:04d}_members.npz') as a:members=a['target'];state=a['recovery_state']
    final=first.copy();final[state==1]=11;final[members]=10
    assert np.all(final>0) and len(final)==len(first)
    assert np.array_equal(np.flatnonzero(final==10),members)
    path=root/v/sid/f'{fi:04d}_final_terminal.npz'
    if path.exists():raise ValueError('Never overwrite final ledger')
    np.savez_compressed(path,final_terminal_reason=final)
    c=counts[v];c['frames']+=1;c['records']+=len(final);c['target']+=len(members);c['recovery_reject']+=int(np.sum(state==1))
  print('FINAL TERMINAL',run_id,sid,flush=True)
 dump(root/'FINAL_TERMINAL_CONSERVATION.json',{'variants':counts,'code_sha':sha(Path(__file__)),
   'codebook':'original1..9, final10=TARGET (original or restored current record),11=RECOVERY_REJECT (considered pool); first_terminal_reason remains separate and unchanged',
   'recovery_not_reached':'recovery_state0; isolated_cleanup NOT_APPLICABLE Python',
   'identity':'UNKNOWN','records_equals_mutually_exclusive_final_state_sum':True})
if __name__=='__main__':main(sys.argv[1])

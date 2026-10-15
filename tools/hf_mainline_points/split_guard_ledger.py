"""Materialize per-frame guard provenance, preserving the original streamed ledger."""
import sys,time,json
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2];PS=ROOT/'sidequests/human_fusion_lab_next/pointset/r01';sys.path.insert(0,str(PS))
from actions import read,dump,sha
from research_retention import E,RESULT
def main(run_id):
 root=RESULT/run_id
 while not (root/'GUARD_BINDING.json').exists():time.sleep(2)
 count=0;reasons={};rejected=0
 with (E/(run_id+'_GUARD_DECISIONS.jsonl')).open(encoding='utf8') as lines:
  for line in lines:
   row=json.loads(line);p=root/row['variant']/row['sid']/f"{row['fi']:04d}_guard.json"
   with np.load(root/row['variant']/row['sid']/f"{row['fi']:04d}_members.npz") as m:
    assert np.array_equal(m['added'],row['after_guard_added_source_indices'])
    assert set(row['guard_rejected_source_indices']).issubset(np.flatnonzero(m['recovery_state']==1))
   dump(p,row);count+=1;rejected+=len(row['guard_rejected_source_indices'])
   for reason in row['reasons']:reasons[reason]=reasons.get(reason,0)+1
 dump(root/'GUARD_VERIFICATION.json',{'frames_variants':count,'rejected_point_records':rejected,'reason_frame_counts_overlap':reasons,
      'source_sha':sha(Path(__file__)),'identity':'UNKNOWN','rejection_is_geometric_risk_not_furniture_identity':True})
 print('GUARD VERIFIED',count,rejected,reasons,flush=True)
if __name__=='__main__':main(sys.argv[1])

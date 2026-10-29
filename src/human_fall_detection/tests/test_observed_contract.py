"""Consumers must use the authority's measurement, including a non-snapshot ID."""
import copy,sys,unittest
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from core.node_runtime import FallNodeCore
from core.pipeline import ReplayPipeline
from core.lidar_candidates import build_snapshot
from test_hf07_node import VALID_GROUND,standing_person

class ObservedContract(unittest.TestCase):
 def test_node_and_replay_consume_returned_rows_not_snapshot_id(self):
  p=standing_person(count=80); g=copy.deepcopy(VALID_GROUND)
  for runtime in (FallNodeCore('s',ground=g,target_mode='automatic'),ReplayPipeline('s',target_mode='automatic')):
   runtime.ground=g
   c=build_snapshot(p,session_id='s',time_epoch=0,snapshot_id='s',ground=g)['candidates'][0]
   c=dict(c,candidate_id='combined:original',evidence_indices=list(range(10,70)),point_count=60)
   def step(candidates,epoch,stamp,**kw):
    state=runtime.tracker.select('t1',epoch,candidate=c,source_stamp_s=stamp,receive_s=stamp)
    return state,{},c
   runtime.acquisition.step=step
   if isinstance(runtime,ReplayPipeline):result=runtime.step(p,100.,0,1)
   else:result=runtime.process(p,100.,seq=1,stamp_secs=100,stamp_nsecs=0,now=100.)['state']
   self.assertEqual(result['target_source_rows'],list(range(10,70)))

if __name__=='__main__':unittest.main()

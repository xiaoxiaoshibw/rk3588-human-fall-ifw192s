"""Actual support versus visibility changes; synthetic software contracts only."""
import copy,sys,unittest
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from core.candidate_history import CandidateHistory
from core.lidar_candidates import rebuild_candidate,build_snapshot
from core.target_acquisition import TargetAcquisition
from core.tracking import TargetTracker
G=dict(status='valid',normal=[0.,0.,1.],offset_m=0.)

def item(p,rows):
 c=rebuild_candidate(p,np.asarray(rows),ground=G);c['candidate_id']='c';return c

class SupportMotion(unittest.TestCase):
 def test_fixed_horizontal_and_vertical_members_do_not_acquire(self):
  for horizontal in (False,True):
   p=np.array([[2+.02*k,0,z] for k in range(150) for z in np.linspace(.1,1.7,25)]) if horizontal else np.array([[2,y,.1+.02*k] for k in range(150) for y in np.linspace(0,.3,7)])
   n=25 if horizontal else 7;a=TargetAcquisition(TargetTracker('s'))
   for i in range(25):
    rows=np.arange(2*i*n,(2*i+50)*n)
    state,acq,observed=a.step([item(p,rows)],0,i*.1,points=p,ground=G)
    self.assertIsNone(state['track_id']);self.assertIsNone(observed)
   self.assertEqual(acq['rejected']['c'],'entry_motion_explained_by_visibility')
 def test_real_translation_with_resampling_locks_then_holds_still(self):
  grid=np.stack(np.meshgrid(np.linspace(2,2.25,7),np.linspace(0,.3,7),np.linspace(.1,1.7,30)),-1).reshape(-1,3)
  a=TargetAcquisition(TargetTracker('s'))
  for i in range(40):
   p=grid+np.array([.06*min(i,24),0,0]);p=p[::-1] if i%2 else p
   state,acq,obs=a.step([item(p,np.arange(len(p)))],0,i*.1,points=p,ground=G)
  self.assertEqual(state['track_status'],'locked');self.assertIsNotNone(obs)
 def test_analysis_is_pure_and_next_commit_does_not_reset(self):
  p=np.array([[2,y,z] for y in np.linspace(0,.3,7) for z in np.linspace(.1,1.7,30)])
  c=item(p,np.arange(len(p)));h=CandidateHistory();h.step([c],0.,('s',),points=p,ground=G)
  before=copy.deepcopy(h.summary());ledger=copy.deepcopy(h.ledger);next_id=h._next_id
  for _ in range(3):
   a=h.analyze([c],.1,('s',),points=p,ground=G)
   self.assertEqual(len(a['edges'][0]),1)
  self.assertEqual(h.summary(),before);self.assertEqual(h.ledger,ledger);self.assertEqual(h._next_id,next_id)
  h.step([c],'0.1',('s',),points=p,ground=G)
  self.assertEqual(h.ledger[0]['observed_frames'],2)
 def test_source_rows_override_subset_indices_and_local_rows_respect_offset(self):
  p=np.array([[2,y,z] for y in np.linspace(0,.3,7) for z in np.linspace(.1,1.7,30)])
  h=CandidateHistory();c=item(p,np.arange(30,180));c['source_rows']=(np.arange(30,180)+1000).tolist();c['evidence_indices']=list(range(150))
  h.step([c],0.,('s',),points=p,row_offset=1000,ground=G)
  np.testing.assert_array_equal(h.measured_centers()[h.ledger[0]['history_id']],np.median(p[30:180],axis=0))
  c.pop('source_rows');c['evidence_indices']=list(range(30,180));h.step([c],.1,('s',),points=p,row_offset=2000,ground=G)
  self.assertEqual(h.ledger[0]['source_rows'],list(range(2030,2180)))
 def test_rebuild_matches_original_snapshot_geometry_and_rejects_bad_rows(self):
  p=np.array([[2,y,z] for y in np.linspace(0,.3,7) for z in np.linspace(.1,1.7,30)])
  c=build_snapshot(p,session_id='s',time_epoch=0,snapshot_id='s',ground=G)['candidates'][0]
  rebuilt=rebuild_candidate(p,np.asarray(c['evidence_indices']),ground=G)
  self.assertEqual(dict(c, candidate_id=None),dict(rebuilt,candidate_id=None))
  for ids in ([0,0],[-1],[len(p)],[.5],[]):
   with self.assertRaises(ValueError):rebuild_candidate(p,ids,ground=G)

class MotionPerturbations(unittest.TestCase):
 def sequence(self, count, permutation=False):
  grid=np.stack(np.meshgrid(np.linspace(2,2.2,4),np.linspace(0,.3,5),np.linspace(.1,1.7,12)),-1).reshape(-1,3)
  a=TargetAcquisition(TargetTracker('prefix'));result=[]
  for i in range(count):
   p=grid+[.06*min(i,24),0,0]
   if permutation:p=p[::-1]
   state,acq,obs=a.step([item(p,np.arange(len(p)))],0,i*.1,points=p,ground=G)
   result.append(dict(track=state,acquisition=acq,selected=None if obs is None else sorted(map(tuple,p[obs['evidence_indices']]))))
  return result
 def test_causal_prefix_and_repeat(self):
  self.assertEqual(self.sequence(18),self.sequence(40)[:18])
  self.assertEqual(self.sequence(40),self.sequence(40))
 def test_row_permutation_preserves_selection_and_identity(self):
  a,b=self.sequence(35),self.sequence(35,True)
  for x,y in zip(a,b):
   self.assertEqual(x['track'],y['track']);self.assertEqual(x['selected'],y['selected'])
 def test_static_visibility_with_density_and_boundary_offsets(self):
  for step,offset in ((.015,-1e-6),(.02,1e-6),(.025,.04999)):
   p=np.array([[2+step*k+offset,0,z] for k in range(150) for z in np.linspace(.1,1.7,17)])
   a=TargetAcquisition(TargetTracker('static'))
   for i in range(25):
    rows=np.arange(2*i*17,(2*i+50)*17)
    # Density varies while XYZ remains a fixed stationary surface.
    if i%2:rows=rows[::2]
    state,_,obs=a.step([item(p,rows)],0,i*.1,points=p,ground=G)
    self.assertIsNone(state['track_id']);self.assertIsNone(obs)

if __name__=='__main__':unittest.main()

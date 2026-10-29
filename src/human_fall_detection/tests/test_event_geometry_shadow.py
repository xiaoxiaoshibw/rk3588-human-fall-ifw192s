"""Source-bound shadow telemetry must never modify original outputs/events."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

import numpy as np

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'src/human_fall_detection/scripts'))
from single_target_node import configure_paths
configure_paths(ROOT)
from event_geometry_shadow import LiveGeometryShadow
from prepare_single_target_bundle import prepare


class Regions:
    def process(self,points,result):pass
    def state(self,payload):return dict(payload,regions={'unchanged':True})


def state(t=0.):
    return dict(session_id='s',track_id='t1',time_epoch=0,action_generation=1,
        selection_version=1,calibration=dict(calibration_id='c1'),
        ground=dict(status='ok',normal=[0.,0.,1.],offset_m=0.),
        target_source_rows=list(range(40)),track_status='locked',position_predicted=False,
        observability='valid',source=dict(source_stamp_s=t,seq=int(t*10)),
        fall_status='upright',confirmed_enabled=False)


class EventShadowTest(unittest.TestCase):
    def setUp(self):
        rng=np.random.RandomState(3);self.points=rng.normal(0,.03,(40,3))
        self.points[:,2]+=np.linspace(.1,1.8,40)

    def test_original_state_events_and_source_points_unchanged(self):
        shadow=LiveGeometryShadow(Regions());s=state()
        result=dict(state=s,event=None,snapshot=dict(keep=True));before=copy.deepcopy(result)
        points=self.points.copy();shadow.process(points,result)
        self.assertEqual(before,result);np.testing.assert_array_equal(points,self.points)
        merged=shadow.state(s);geometry=merged.pop('event_geometry_shadow')
        self.assertEqual(merged,dict(s,regions={'unchanged':True}))
        self.assertEqual(geometry['state'],'upright');self.assertTrue(geometry['observed'])
        self.assertFalse(geometry['confirmed_enabled']);self.assertFalse(geometry['model_loaded'])
        json.dumps(geometry,allow_nan=False)

    def test_stale_rebound_and_bad_provenance_cannot_reuse_measurements(self):
        shadow=LiveGeometryShadow(Regions());s=state();shadow.process(self.points,dict(state=s))
        for changed in (dict(source=dict(source_stamp_s=1.)),dict(track_id='other'),
                        dict(action_generation=2),dict(observability='invalid'),
                        dict(track_status='occluded'),dict(position_predicted=True)):
            out=shadow.state(dict(s,**changed))['event_geometry_shadow']
            self.assertEqual(out['state'],'unknown');self.assertIsNone(out['evidence'])
        for ids in ([0]*40,[999],[-1],[1.5],[True]):
            bad=dict(s,target_source_rows=ids);shadow.process(self.points,dict(state=bad))
            self.assertEqual(shadow.state(bad)['event_geometry_shadow']['state'],'unknown')
        self.assertGreaterEqual(shadow.errors,5)

    def test_ground_change_and_missing_ground_reset_evidence(self):
        shadow=LiveGeometryShadow(Regions());s=state();shadow.process(self.points,dict(state=s))
        s=state(.1);s['ground']=None;shadow.process(self.points,dict(state=s))
        self.assertEqual(shadow.state(s)['event_geometry_shadow']['reason'],'missing_ground')
        s=state(.2);s['ground']['offset_m']=.1;shadow.process(self.points,dict(state=s))
        out=shadow.state(s)['event_geometry_shadow']['evidence']
        self.assertIsNone(out['vertical_velocity_m_s'])

    def test_positive_geometry_is_telemetry_only_and_never_a_production_event(self):
        shadow=LiveGeometryShadow(Regions());events=[]
        z=np.linspace(.05,1.85,30)
        body=np.concatenate([np.column_stack([np.full(30,x),np.full(30,y),z])
                             for x,y in ((-.04,-.04),(-.04,.04),(.04,-.04),(.04,.04))])
        for i in range(22):
            t=i/10.;angle=np.radians(max(0.,min(90.,(t-.5)*180.)))
            rotation=np.array([[np.cos(angle),0,np.sin(angle)],[0,1,0],[-np.sin(angle),0,np.cos(angle)]])
            points=body@rotation.T+np.array([0.,0.,.1])
            s=state(t);s['target_source_rows']=list(range(len(points)))
            wrapped=dict(state=s,event=None);shadow.process(points,wrapped)
            output=shadow.state(s)['event_geometry_shadow']
            self.assertIsNone(wrapped['event']);self.assertEqual(s['fall_status'],'upright')
            if output['new_event']:events.append(output['new_event'])
        self.assertEqual(len(events),1)

    def test_bundle_feature_is_explicit_and_changes_release_identity(self):
        import tarfile
        with tempfile.TemporaryDirectory() as tmp:
            releases=[]
            for enabled in (False,True):
                path=Path(tmp)/('%s.tar'%enabled);prepare(ROOT,path,geometry_shadow=enabled)
                with tarfile.open(path) as stream:
                    doc=json.load(stream.extractfile('RELEASE.json'))
                    self.assertEqual(doc['features']['event_geometry_shadow'],enabled)
                    self.assertIsNotNone(stream.extractfile('ML/src/fall_geometry.py'))
                    self.assertNotIn('ML/src/event_model_numpy.py',stream.getnames())
                    releases.append(doc['release_id'])
            self.assertNotEqual(*releases)


if __name__=='__main__':unittest.main()

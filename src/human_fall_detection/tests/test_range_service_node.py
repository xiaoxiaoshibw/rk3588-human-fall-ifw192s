"""Run the actual ROS entry with injected transport modules, no ROS installation."""
import importlib.util
import json
from pathlib import Path
import sys
import time
from types import SimpleNamespace as NS
import unittest
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location('range_service_node', ROOT/'src/human_fall_detection/scripts/range_service_node.py')
node = importlib.util.module_from_spec(spec)
spec.loader.exec_module(node)


class NodeTests(unittest.TestCase):
    def modules(self, conflict=False):
        self.states, self.publishers, self.closed = [], [], []
        self.initialized = []
        self.started = time.monotonic()
        def publisher(topic, typ, **kwargs):
            self.publishers.append(topic)
            return NS(publish=lambda msg:self.states.append(json.loads(msg.data)))
        def subscriber(topic, typ, callback, **kwargs):
            from test_range_service import RangeServiceTests, ros_standin
            case = RangeServiceTests()
            case.setUp()
            # Wrong frame is intentionally rejected; callbacks still counted.
            callback(ros_standin(case.fixture.raw(0)))
            return NS(get_num_connections=lambda:1, unregister=lambda:self.closed.append(topic))
        rospy = NS(init_node=lambda *a,**k:self.initialized.append((a,k)), get_name=lambda:'/range_recognition_service',
            Publisher=publisher, Subscriber=subscriber, is_shutdown=lambda:time.monotonic()-self.started>.25)
        rosgraph = NS(Master=lambda name:NS(getSystemState=lambda:([
            ('/single_target_live/state',['/legacy'])] if conflict else [],[],[])))
        return {'rospy':rospy, 'rosgraph':rosgraph, 'sensor_msgs':NS(),
                'sensor_msgs.msg':NS(PointCloud2=object), 'std_msgs':NS(),
                'std_msgs.msg':NS(String=lambda data:NS(data=data))}

    def test_real_entry_heartbeat_shutdown_and_callback_rejection(self):
        modules = self.modules()
        with patch.dict(sys.modules, modules):
            self.assertEqual(node.main(['--config',str(ROOT/'src/human_fall_detection/config/range_service_v1.json'),
                '--release-id','node-fixture']),0)
        self.assertEqual(self.publishers,['/single_target_live/state'])
        self.assertTrue(self.closed)
        self.assertTrue(self.states)
        self.assertTrue(any(s['health']['received']>0 for s in self.states))
        self.assertEqual(self.states[-1]['acquisition']['reason'],'service_stopped')
        self.assertEqual(self.states[-1]['target_source_rows'],[])
        self.assertIsNone(self.states[-1]['groundBinding'])
        self.assertTrue(all(s['service']['releaseId']=='node-fixture' for s in self.states))

    def test_real_entry_refuses_legacy_publisher_before_registering_state(self):
        modules = self.modules(conflict=True)
        with patch.dict(sys.modules, modules), self.assertRaisesRegex(RuntimeError,'/legacy'):
            node.main(['--config',str(ROOT/'src/human_fall_detection/config/range_service_v1.json')])
        self.assertEqual(self.publishers,[])
        self.assertEqual(self.initialized,[], 'publisher conflict must be checked before ROS name registration')

    def test_fit_io_worker_and_install_failure_do_not_stop_recognition(self):
        import numpy as np
        from unittest.mock import Mock
        for stage in ('poll', 'save', 'install', 'slow_save', 'slow_reap', 'shutdown_during_spawn'):
            with self.subTest(stage=stage), tempfile.TemporaryDirectory() as directory:
                modules = self.modules()
                engine = NS(disabled=None, frame_id='innolidar', identity={},
                    runtime=NS(ground=None, ground_sha=None, config={}, config_sha=None),
                    ground_frame=NS(xyz=np.zeros((1,3)), source_rows=np.array([[0]]), valid=np.array([[True]])),
                    clear_history=Mock(), prepare_ground=Mock(return_value=({},'0'*64)),
                    install_prepared_ground=Mock())
                if stage == 'install':engine.install_prepared_ground.side_effect = ValueError('synthetic install rejected')
                class Service:
                    def __init__(self):
                        self.count=0;self.preview=False;self.ground_clears=0
                        self.queue=NS(wait=lambda seconds:time.sleep(.001))
                    def submit(self,msg):pass
                    def clear_ground_binding(self):self.ground_clears+=1
                    def process_latest(self):
                        self.count+=1
                        h=dict(seq=self.count, stamp_secs=100+self.count//10,
                               stamp_nsecs=self.count%10*100000000, frame_id='innolidar')
                        return dict(source=h, local_range=dict(wireSha256='0'*64))
                    def snapshot(self,*args):
                        return dict(service=dict(releaseId='fixture'), health=dict(received=self.count))
                    def note_published(self,*args):pass
                    def note_publish_started(self):pass
                service=Service()
                job=NS(close=Mock(), poll=Mock(return_value=dict(status='geometry_accepted')))
                if stage=='poll':job.poll.side_effect=RuntimeError('synthetic child failed')
                save=Mock(return_value=Path(directory)/'SITE_GROUND.json')
                if stage=='save':save.side_effect=FileExistsError('synthetic existing output')
                progress=[]
                def slow(*a,**k):
                    before=service.count
                    time.sleep(.08)
                    progress.append(service.count-before)
                    return Path(directory)/'SITE_GROUND.json'
                if stage=='slow_save':save.side_effect=slow
                if stage=='slow_reap':job.poll.side_effect=lambda: (slow(),dict(status='geometry_accepted'))[1]
                def create_job(*a,**k):
                    if stage=='shutdown_during_spawn':time.sleep(.3)
                    return job
                with patch.dict(sys.modules,modules), patch.object(node,'RangeEngine',return_value=engine), \
                     patch.object(node,'RangeService',return_value=service), \
                     patch.object(node,'GroundFitJob',side_effect=create_job), patch.object(node,'save_fit',save):
                    self.assertEqual(node.main(['--config',str(ROOT/'src/human_fall_detection/config/range_service_v1.json'),
                        '--declare-empty-prefix','--site-id','SYNTHETIC','--fit-ground-out',directory]),0)
                if stage=='shutdown_during_spawn':
                    self.assertTrue(job.close.called, 'job created during shutdown must be reaped instead of installed')
                    continue
                if stage.startswith('slow_'):
                    self.assertTrue(progress)
                    self.assertGreater(progress[0],20,'fit completion IO/reaping blocked recognition')
                    continue
                self.assertGreater(service.ground_clears, 0)
                self.assertGreater(service.count, 35, 'fit failure must leave main recognition alive')
                self.assertIsNone(engine.runtime.ground)
                self.assertTrue(any('fit_failed' in s['service'].get('initialization',{}).get('ground','') for s in self.states))


if __name__=='__main__':
    unittest.main()

"""本地回放、完整覆盖账本、有界发布与HTTP契约。"""
import json
from pathlib import Path
import sys
import threading
import unittest
from unittest import mock
import numpy as np
from urllib.request import urlopen
from functools import partial
from http.server import ThreadingHTTPServer

import runtime_replay as runtime
sys.path.insert(0,str(runtime.ROOT/'tools'))
import test_range_experiment as fixture


class QueueTests(unittest.TestCase):
    def test_display_byte_dedup_matches_existing_exactly(self):
        rng=np.random.default_rng(567)
        for size in (1,30,5000):
            points=rng.normal(size=(size,3))
            points=np.vstack((points,points,[[0,0,0],[-.06,-.06,-.06],[.06,.06,.06]]))
            for cap in (1,24,10000):
                expected=runtime.view.sc.voxel_pick(points,.06,cap,'same-seed')
                np.testing.assert_array_equal(expected,runtime.display_pick(points,.06,cap,'same-seed'))

    def test_every_overwrite_has_ledger_beyond_128(self):
        q=runtime.PacedQueue(); dropped=[]
        for i in range(300):
            old=q.put(dict(frame=i))
            if old:dropped.append(old)
        self.assertEqual(len(dropped),299)
        self.assertTrue(all(r['disposition']=='dropped' for r in dropped))
        self.assertEqual(q.take()['frame'],299)
        self.assertIsNone(q.take())
        self.assertEqual(q.queue.dropped,299)

    def test_publication_cache_has_bound_and_overflow_visible(self):
        cache=runtime.Publications(3)
        for i in range(10):cache.publish(dict(i=i))
        state=cache.since(0)
        self.assertEqual([r['seq'] for r in state['rows']],[8,9,10])
        self.assertEqual(state['oldest_seq'],8)
        self.assertEqual(cache.since(9)['rows'][0]['frame'],dict(i=9))

    def test_working_set_is_actual_positive_measurement(self):
        self.assertGreater(runtime.memory_bytes(),0)

    def test_memory_reader_reuses_ctypes_types(self):
        import ctypes
        runtime.memory_bytes()
        before = len(ctypes._pointer_type_cache)
        for _ in range(500): runtime.memory_bytes()
        self.assertEqual(len(ctypes._pointer_type_cache),before)


class ReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):fixture.RangeExperimentTests.setUpClass()

    def setUp(self):
        self.f=fixture.RangeExperimentTests();self.f.setUp();self.addCleanup(self.f.doCleanups)

    def test_all_frames_matches_existing_and_consumed_recheck(self):
        audit=self.f.root/'audit';runtime.view.experiment.run(self.f.session,audit,self.f.replay)
        result=runtime.run(self.f.session,self.f.root/'runtime',empty_prefix_frames=1,
            compare_run=self.f.replay,compare_rules=audit)
        self.assertEqual(result['processed_frames'],4)
        self.assertEqual(result['dropped_frames'],0)
        self.assertEqual(result['differences'],[])
        self.assertEqual(result['consumed_sequence_differences'],[])
        rows=runtime.view.records(self.f.root/'runtime/ARRIVALS.jsonl')
        for r in rows:
            self.assertLessEqual(r['arrival_mono_s'],r['enqueued_mono_s'])
            self.assertLessEqual(r['enqueued_mono_s'],r['started_mono_s'])
            self.assertLessEqual(r['started_mono_s'],r['completed_mono_s'])
            self.assertLessEqual(r['completed_mono_s'],r['published_mono_s'])

    def test_paced_overload_no_silent_drop_or_fabricated_prefix(self):
        result=runtime.run(self.f.session,self.f.root/'paced',empty_prefix_frames=1,
            paced=True,speed=100.,processing_delay_s=.04)
        rows=runtime.view.records(self.f.root/'paced/ARRIVALS.jsonl')
        self.assertEqual(result['input_frames'],4)
        self.assertEqual(result['processed_frames']+result['dropped_frames'],4)
        self.assertGreater(result['dropped_frames'],0)
        self.assertEqual(len(rows),4)
        self.assertEqual(result['consumed_sequence_differences'],[])
        self.assertEqual(result['queue_max_depth'],1)

    def test_opt_in_alert_and_body_export_preserves_target_and_default_rules(self):
        out=self.f.root/'combined'
        runtime.run(self.f.session,out,empty_prefix_frames=1,alert_variant='ground_alert_v1',body_candidates=True)
        doc=json.loads((out/'analysis.json').read_text())
        from analysis import AnalysisStore
        AnalysisStore.validate(doc)
        self.assertEqual(doc['alertAlgorithm']['id'],'ground_alert_v1')
        self.assertEqual(doc['bodyAlgorithm']['id'],'range_topology_branches_v2')
        self.assertTrue(all(r['state']=='unknown' for r in doc['frames']))
        self.assertTrue(all(not r['groundAlert']['active'] for r in doc['frames']))
        self.assertEqual(doc['intervals'],[])
        self.assertTrue(all('bodyCandidates' in r for r in doc['frames']))

    def test_output_guard_and_same_layout_http(self):
        with self.assertRaises(ValueError):runtime.run(self.f.session,self.f.session/'bad',empty_prefix_frames=1)
        out=self.f.root/'page';out.mkdir()
        first=dict(i=0,t=0,n=0,tid=None,st='unknown',rs=[],hm=None,ht=None,sp=None,rt=None,vt=None,
            bb=None,c=None,cam=None,bl=None,bg=[],tg=[],generation=0)
        runtime.make_page(out,self.f.session,4,None,first,0)
        self.assertIn('window.RANGE_RUNTIME=true',(out/'index.html').read_text(encoding='utf-8'))
        server=ThreadingHTTPServer(('127.0.0.1',0),partial(runtime.Handler,directory=str(out)))
        server.publications=runtime.Publications();server.camera=None
        worker=threading.Thread(target=server.serve_forever);worker.start()
        try:
            server.publications.publish(first)
            with urlopen('http://127.0.0.1:%d/api/frames?after=0'%server.server_port) as r:
                self.assertEqual(json.load(r)['rows'][0]['frame'],first)
            with urlopen('http://127.0.0.1:%d/'%server.server_port) as r:
                self.assertIn('rangeRuntimeAppend',r.read().decode('utf-8'))
        finally:server.shutdown();worker.join();server.server_close()

    def test_bad_delay_and_port_create_no_output(self):
        for kwargs in (dict(processing_delay_s=float('nan')),dict(processing_delay_s=float('inf')),
                       dict(serve=-1,paced=True),dict(serve=65536,paced=True),dict(open_browser=True)):
            out=self.f.root/'invalid'
            with self.assertRaises(ValueError):runtime.run(self.f.session,out,empty_prefix_frames=1,**kwargs)
            self.assertFalse(out.exists())

    def test_worker_failure_retains_arrivals_and_releases_server(self):
        real = runtime.display_frame
        def fail(frame,result,*args,**kwargs):
            if result['tracking']['frame'] >= 1:raise RuntimeError('injected display failure')
            return real(frame,result,*args,**kwargs)
        servers=[]; factory=runtime.ThreadingHTTPServer
        def record_server(*args,**kwargs):
            server=factory(*args,**kwargs);servers.append(server);return server
        out=self.f.root/'failed'
        with mock.patch.object(runtime,'display_frame',side_effect=fail), \
             mock.patch.object(runtime,'ThreadingHTTPServer',side_effect=record_server):
            with self.assertRaisesRegex(RuntimeError,'worker failed'):
                runtime.run(self.f.session,out,empty_prefix_frames=1,paced=True,serve=0)
        rows=runtime.view.records(out/'ARRIVALS.jsonl')
        self.assertTrue(any(r['disposition']=='failed' for r in rows))
        self.assertTrue(all('disposition' in r for r in rows))
        self.assertEqual(json.loads((out/'FAILURE.json').read_text())['status'],'failed')
        self.assertIn('injected display failure',(out/'ERROR.log').read_text())
        self.assertTrue(servers);self.assertEqual(servers[0].socket.fileno(),-1)

    def test_verification_failure_releases_server_and_preserves_ledgers(self):
        servers=[];factory=runtime.ThreadingHTTPServer
        def record_server(*args,**kwargs):
            server=factory(*args,**kwargs);servers.append(server);return server
        out=self.f.root/'verify_failed'
        with mock.patch.object(runtime.view,'verify',side_effect=ValueError('injected binding change')), \
             mock.patch.object(runtime,'ThreadingHTTPServer',side_effect=record_server):
            with self.assertRaisesRegex(ValueError,'binding change'):
                runtime.run(self.f.session,out,empty_prefix_frames=1,paced=True,serve=0)
        self.assertEqual(servers[0].socket.fileno(),-1)
        self.assertTrue((out/'CONSUMED.json').exists());self.assertTrue((out/'FAILURE.json').exists())

    def test_interrupt_retains_arrival_dispositions(self):
        out=self.f.root/'cancelled'
        with mock.patch.object(runtime,'display_frame',side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):runtime.run(self.f.session,out,empty_prefix_frames=1)
        self.assertEqual(runtime.view.records(out/'ARRIVALS.jsonl')[0]['disposition'],'failed')
        self.assertEqual(json.loads((out/'FAILURE.json').read_text())['status'],'cancelled')

    def test_static_camera_export_and_actual_summary(self):
        jpeg=b'\xff\xd8synthetic\xff\xd9'
        camera=([dict(offset=0,length=len(jpeg),recv_unix_ns=1792700000100000000)],jpeg)
        out=self.f.root/'camera'
        with mock.patch.object(runtime.view.sc,'read_camera',return_value=camera):
            runtime.run(self.f.session,out,empty_prefix_frames=1)
        self.assertEqual((out/'camera/c000.jpg').read_bytes(),jpeg)
        page=(out/'replay.html').read_text(encoding='utf-8')
        self.assertIn('0.30',page);self.assertIn('PC离线全帧运行时',page)


if __name__=='__main__':unittest.main()

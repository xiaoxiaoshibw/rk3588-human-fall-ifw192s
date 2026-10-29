"""ROS-message stand-ins exercise the actual resident service lifecycle."""
import base64
import copy
import hashlib
import struct
import time
import threading
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

import numpy as np

from test_range_frontend import scene
from test_range_tracking import step, measurement
from core.range_engine import RangeEngine
from core.range_service import RangeService, assert_single_publisher
from core.range_tracker import RangeTracker
from core.range_wire import parse_cloud


def wire(msg):
    def text(s):
        b = s.encode('utf8')
        return struct.pack('<I', len(b))+b
    h = msg.header
    return (struct.pack('<III', h.seq, h.stamp.secs, h.stamp.nsecs)+text(h.frame_id)
        +struct.pack('<III', msg.height, msg.width, len(msg.fields))
        +b''.join(text(f.name)+struct.pack('<IBI', f.offset, f.datatype, f.count) for f in msg.fields)
        +struct.pack('<?III', msg.is_bigendian, msg.point_step, msg.row_step, len(msg.data))
        +msg.data+struct.pack('<?', msg.is_dense))


def ros_standin(raw):
    msg = parse_cloud(raw)
    msg.serialize = lambda stream: stream.write(wire(msg))
    return msg


class RangeServiceTests(unittest.TestCase):
    def test_engine_reports_settings_drift_separately(self):
        from core.range_posture import SETTINGS
        old = SETTINGS['max_gap_s']
        try:
            SETTINGS['max_gap_s'] = -1
            result = self.engine.process(self.fixture.raw(0), preview=False)
            self.assertIn('settings_drift_requires_new_runtime', result['acquisition']['reason'])
        finally:
            SETTINGS['max_gap_s'] = old

    def test_demo_hint_cleared_on_invalidated_history_and_missing_ground(self):
        self.engine.demo_alert.update(dict(i=0,t=0.,tid='a',n=50,hm=.3,ht=.4,sp=.7))
        self.engine.demo_alert.update(dict(i=1,t=.1,tid='a',n=50,hm=.3,ht=.4,sp=.7))
        self.assertIsNotNone(self.engine.demo_alert.start)
        self.engine.clear_history()
        self.assertIsNone(self.engine.demo_alert.start)
        self.send(0, False)
        result = self.service.snapshot()['local_range']['demoFallCandidate']
        self.assertEqual(result['state'], 'unavailable')
        self.assertEqual(result['level'], 0)
        self.assertFalse(result['active'])
        self.assertFalse(result['confirmedEnabled'])

    def test_ttl_clears_runtime_posture_and_baseline_before_next_frame(self):
        self.send(0, False)
        runtime = self.engine.runtime
        runtime.posture.last_frame = 99
        runtime.baseline_collector.status = 'ready'
        runtime.baseline_collector.baseline = {'baseline_version': 1}
        runtime.baseline_collector._baseline_counter = 1
        self.service.last_received = time.monotonic() - 1
        self.assertIsNone(self.service.snapshot()['source'])
        self.send(1, False)
        self.assertNotEqual(runtime.posture.last_frame, 99)
        self.assertEqual(runtime.baseline_collector.status, 'idle')
        self.assertEqual(runtime.baseline_collector.retired[-1]['baseline_version'], 1)

    def test_ground_binding_survives_recognition_ttl_but_not_rebind(self):
        self.engine.runtime.ground_sha = 'a' * 64
        for i in range(6):
            self.send(i, i >= 2)
        before = self.service.snapshot()
        self.assertEqual(before['groundBinding']['sha256'], 'a' * 64)
        self.assertTrue(before['target_source_rows'])
        self.service.last_received = time.monotonic() - 1
        stale = self.service.snapshot()
        self.assertIsNone(stale['source'])
        self.assertEqual(stale['target_source_rows'], [])
        self.assertIsNone(stale['local_range'])
        self.assertTrue(before['groundBinding']['supportCurrent'])
        self.assertFalse(stale['groundBinding']['supportCurrent'])
        self.assertEqual(stale['groundBinding']['displayPlane'], before['groundBinding']['displayPlane'])
        self.service.clear_ground_binding()
        self.assertIsNone(self.service.snapshot()['groundBinding'])
        self.engine.runtime.ground_sha = 'b' * 64
        self.send(6)
        self.assertEqual(self.service.snapshot()['groundBinding']['sha256'], 'b' * 64)
        self.engine.identity['grid_sha256'] = 'changed'
        self.service.submit(ros_standin(self.fixture.raw(7)))
        self.service.process_latest()
        self.assertIsNone(self.service.snapshot()['groundBinding'])

    def test_preview_expiry_is_separate_from_superseded_result(self):
        self.send(0, False)
        self.service.clock = lambda: time.monotonic() + 1
        self.assertFalse(self.service.process_preview())
        health = self.service.snapshot()['health']
        self.assertEqual(health['previewTtlExpired'], 1)
        self.assertEqual(health['previewSuperseded'], 0)
        self.service.clock = time.monotonic
        self.send(1, False)
        from core.range_png import png as encode
        def replace_state(image):
            data = encode(image)
            with self.service.lock:self.service.state = dict(self.service.state)
            return data
        with patch('core.range_service.png', side_effect=replace_state):
            self.assertFalse(self.service.process_preview())
        health = self.service.snapshot()['health']
        self.assertEqual(health['previewTtlExpired'], 1)
        self.assertEqual(health['previewSuperseded'], 1)
        self.assertEqual(health['previewComputed'], 1)

    def test_temporary_floor_occlusion_does_not_destroy_raw_track(self):
        engine = self.engine
        engine.runtime.ground.update(monitor={'fixture': True}, siteBinding={'siteId': 'test'})
        engine.runtime.ground_sha = 'a' * 64
        with patch('core.range_site_ground.monitor', return_value=dict(available=True, reason='current_patch_support')) as monitor:
            for i in range(6):
                state = self.send(i, i >= 2)
            tid, epoch = state['track_id'], state['time_epoch']
            self.assertIsNotNone(tid)
            monitor.return_value = dict(available=False, reason='ground_patch_support_or_residual_failed')
            for i in range(6, 9):
                state = self.send(i)
                self.assertEqual(state['track_id'], tid)
                self.assertEqual(state['time_epoch'], epoch)
                self.assertTrue(state['target_source_rows'])
                self.assertIsNone(state['local_range']['heightMedianM'])
                self.assertFalse(state['local_range']['groundAlert']['active'])
                plane = state['local_range']['ground']['displayPlane']
                self.assertEqual(plane['scope'], 'bound_display_only')
                self.assertEqual(plane['groundSha256'], 'a' * 64)
            monitor.return_value = dict(available=True, reason='current_patch_support')
            state = self.send(9)
            self.assertEqual(state['track_id'], tid)
            self.assertEqual(state['time_epoch'], epoch)
            self.assertIsNotNone(state['local_range']['heightMedianM'])
            self.assertFalse(state['local_range']['groundAlert']['active'])
            # A real plane replacement is still a binding change.
            engine.runtime.ground['offset_m'] += .1
            state = self.send(10)
            self.assertGreater(state['time_epoch'], epoch)

    def test_concurrent_callbacks_commit_in_receive_order(self):
        service = self.service
        original = service.queue.put
        entered, release = threading.Event(), threading.Event()
        def delayed(item):
            if item[1].header.seq == 50:
                entered.set()
                if not release.wait(2):raise RuntimeError('barrier timeout')
            original(item)
        service.queue.put = delayed
        first = threading.Thread(target=service.submit, args=(ros_standin(self.fixture.raw(0)),))
        second = threading.Thread(target=service.submit, args=(ros_standin(self.fixture.raw(1)),))
        first.start()
        try:
            self.assertTrue(entered.wait(2))
            second.start()
            second.join(.05)
        finally:
            release.set();first.join(2);second.join(2)
        self.assertFalse(first.is_alive() or second.is_alive())
        self.assertEqual(service.queue.take()[1].header.seq, 51)
        self.assertEqual([h['seq'] for h in service.queue.drain_overwritten()['headers']], [50])

    def test_overload_headers_are_bounded_recovery_cannot_join_low_duration(self):
        for i in range(25):state=self.send(i,i>=2)
        self.assertTrue(state['local_range']['groundAlert']['active'])
        for i in range(25,225):self.service.submit(ros_standin(self.fixture.raw(i)))
        state=self.service.process_latest()
        health=self.service.snapshot()['health']
        self.assertEqual(health['overwritten'],199)
        self.assertEqual(len(health['overwrittenHeaders']),128)
        self.assertEqual(health['overwrittenHeaderOverflow'],71)
        self.assertEqual(health['overwrittenHeaders'][-1]['seq'],273)
        self.assertEqual(state['target_source_rows'],[])  # long source gap requires rebind
        self.assertIsNone(state.get('local_range',{}).get('heightMedianM'))

    def test_diagnostic_switch_does_not_change_synthetic_results(self):
        import json
        other=RangeEngine(self.grid,'lidar',dict(self.engine.identity),empty_prefix_frames=2,
            ground=copy.deepcopy(self.engine.runtime.ground),diagnostics=True)
        for i in range(28):
            raw=self.fixture.raw(i,not (i<2 or i in (9,10)))
            a=self.engine.process(raw,preview=False)
            b=other.process(raw,preview=False)
            self.assertIn('rawCloudRecorded',b['diagnostics']['detail'])
            self.assertLess(len(json.dumps(b['diagnostics'])),100000)
            for result in (a,b):result.pop('performance',None);result.pop('diagnostics',None)
            self.assertEqual(a['target_source_rows'],b['target_source_rows'])
            self.assertEqual(a['track_id'],b['track_id'])
            self.assertEqual(a['fall_status'],b['fall_status'])
            self.assertEqual(a['local_range']['groundAlert'],b['local_range']['groundAlert'])

    def test_input_processing_and_publication_health_are_independent(self):
        clock,engine,service,msg=self.clock_service()
        service.submit(msg);service.process_latest();service.note_publish_started();service.note_published(2.)
        clock[0]=.6;service.submit(msg)
        state=service.snapshot()
        self.assertEqual(state['health']['inputStatus'],'receiving')
        self.assertEqual(state['health']['recognitionStatus'],'no_progress')
        self.assertEqual(state['health']['publicationStatus'],'silent')
        service.processing_since=.1;service.note_publish_started();clock[0]=1.2
        state=service.snapshot()
        self.assertEqual(state['health']['inputStatus'],'silent')
        self.assertEqual(state['health']['recognitionStatus'],'processing_stalled')
        self.assertEqual(state['health']['publicationStatus'],'publishing_stalled')

    def clock_service(self):
        clock = [0.]
        class Engine:
            clears = 0
            def invalid(self, reason):
                return dict(session_id='clock-fixture', time_epoch=3, source=None,
                    track_id=None, target_source_rows=[], acquisition=dict(reason=reason))
            def clear_history(self):
                self.clears += 1
            def process(self, *args, **kwargs):
                return dict(self.invalid('current'), source=dict(seq=1), observability='valid',
                    local_range=dict(groundAlert=dict(active=True)))
        engine = Engine()
        service = RangeService(engine, preview=False, clock=lambda:clock[0])
        msg = NS(data=b'', fields=[], serialize=lambda stream:stream.write(b'synthetic'))
        return clock, engine, service, msg

    def test_result_ttl_is_bound_to_its_source_not_newer_callbacks(self):
        clock, engine, service, msg = self.clock_service()
        original = engine.process
        def slow(*a, **k):
            clock[0] = .45
            return original(*a, **k)
        engine.process = slow
        service.submit(msg);service.process_latest()
        clock[0] = .9;service.submit(msg)
        clock[0] = .94
        state = service.snapshot()
        self.assertIsNone(state['source'], '940ms-old source cannot advertise ttlMs=500 as valid')

    def test_inflight_result_cannot_revive_history_invalidated_by_heartbeat(self):
        clock, engine, service, msg = self.clock_service()
        service.submit(msg);service.process_latest()
        entered, release = threading.Event(), threading.Event()
        original = engine.process
        def blocked(*a, **k):
            entered.set()
            if not release.wait(2):raise RuntimeError('test barrier timeout')
            return original(*a, **k)
        engine.process = blocked
        clock[0] = .6;service.submit(msg)
        worker = threading.Thread(target=service.process_latest)
        worker.start()
        try:
            self.assertTrue(entered.wait(2))
            clock[0] = .7;service.submit(msg)
            self.assertIsNone(service.snapshot()['source'])
        finally:
            release.set();worker.join(2)
        self.assertFalse(worker.is_alive())
        self.assertIsNone(service.snapshot()['source'], 'inflight old history must not reactivate the hint')
        self.assertGreater(engine.clears, 0)

    def setUp(self):
        from pathlib import Path
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parents[3]/'pc_apps/range_fall'))
        from test_live_engine import LiveEngineTests
        self.fixture = LiveEngineTests()
        self.grid, self.engine = self.fixture.make()
        self.service = RangeService(self.engine, 'test-release')

    def send(self, index, target=True):
        raw = self.fixture.raw(index, target)
        msg = ros_standin(raw)
        self.service.submit(msg)
        state = self.service.process_latest()
        self.assertEqual(state['local_range']['wireSha256'], hashlib.sha256(raw).hexdigest())
        return state

    def test_single_decode_bounded_slot_and_async_preview_no_old_frame(self):
        self.service.submit(ros_standin(self.fixture.raw(0, False)))
        self.service.submit(ros_standin(self.fixture.raw(1, False)))
        with patch.object(self.grid, 'decode', wraps=self.grid.decode) as decode:
            first = self.service.process_latest()
            self.assertEqual(decode.call_count, 1)
        self.assertEqual(self.service.queue.dropped, 1)
        self.assertIsNone(first['local_range']['preview'])
        self.send(2)
        self.assertEqual(self.service.previews.dropped, 1)
        self.assertTrue(self.service.process_preview())
        result = self.service.snapshot()
        bundle = result['local_range']
        self.assertEqual(result['source']['seq'], 52)
        self.assertEqual(hashlib.sha256(base64.b64decode(bundle['preview'])).hexdigest(), bundle['depth']['previewSha256'])

    def test_publisher_wakes_on_state_and_preview_updates(self):
        # A preview-augmented state lives only until the next recognition result;
        # a 20 Hz polling publisher can miss that window, so both updates wake it.
        self.service.updated.clear()
        self.service.submit(ros_standin(self.fixture.raw(0, False)))
        self.service.process_latest()
        self.assertTrue(self.service.updated.is_set())
        self.service.updated.clear()
        self.send(2)
        self.assertTrue(self.service.updated.is_set())
        self.service.updated.clear()
        self.assertTrue(self.service.process_preview())
        self.assertTrue(self.service.updated.is_set())

    def test_stale_epoch_clears_aux_and_resets_before_recovery_not_on_client_reconnect(self):
        for i in range(8):
            self.send(i, i >= 2)
        bg = self.engine.runtime.background
        # Reading/connecting/disconnecting clients cannot mutate the engine.
        for _ in range(5):
            self.service.snapshot()
        self.assertIs(self.engine.runtime.background, bg)
        self.engine.runtime.tracker.generation = 3
        self.send(8)
        self.service.last_received = time.monotonic()-1
        state = self.service.snapshot()
        self.assertEqual(state['time_epoch'], 3)
        self.assertIsNone(state['source'])
        self.assertIsNone(state['local_range'])
        self.assertFalse(self.service.process_preview())
        self.send(9)
        self.assertFalse(self.service.clear_pending.is_set())
        self.assertIs(self.engine.runtime.background, bg)

    def test_missing_ground_valid_ground_mismatch_and_restart(self):
        self.engine.runtime.ground = None
        for i in range(6):
            state = self.send(i, i >= 2)
        self.assertTrue(state['target_source_rows'])
        self.assertIsNone(state['local_range']['heightMedianM'])
        self.engine.runtime.ground = dict(status='valid', binding=self.engine.identity, frame='lidar', normal=[0,0,1], offset_m=.5)
        self.engine.runtime.ground_sha = 'a' * 64
        state = self.send(6)
        # Ground rebinding resets tracker; reacquisition needs real measurements.
        for i in range(7,10):
            state = self.send(i)
        self.assertIsNotNone(state['local_range']['heightMedianM'])
        plane = state['local_range']['ground']['displayPlane']
        self.assertEqual(plane['sessionId'], self.engine.identity['session'])
        self.assertEqual(plane['normal'], [0, 0, 1])
        self.assertEqual(plane['groundSha256'], 'a' * 64)
        self.assertEqual(plane['frameId'], 'lidar')
        self.engine.identity['grid_sha256'] = 'changed'
        self.service.submit(ros_standin(self.fixture.raw(10)))
        self.assertIsNone(self.service.process_latest()['source'])
        restarted = RangeEngine(self.grid, 'lidar')
        self.assertNotEqual(restarted.identity['session'], self.engine.identity['session'])
        state = restarted.process(self.fixture.raw(10))
        self.assertEqual(state['acquisition']['reason'], 'background_not_declared')

    def test_bad_input_and_long_gap_require_rebind(self):
        self.service.submit(object())
        state = self.service.process_latest()
        self.assertIsNone(state['source'])
        self.assertIn('invalid_ros_message', state['acquisition']['reason'])
        self.setUp()
        for i in range(6):
            self.send(i, i >= 2)
        state = self.send(40)
        self.assertEqual(state['acquisition']['reason'], 'background_requires_explicit_rebind')
        self.assertEqual(state['target_source_rows'], [])

    def test_exact_ros_layout_fingerprint_not_repacked_rows(self):
        from core.range_live import pointcloud_rows
        msg = ros_standin(self.fixture.raw(0))
        # Organized big-endian message with padding and float64 timestamps.
        rows = pointcloud_rows(msg)
        dtype = np.dtype([('x','>f4'),('y','>f4'),('z','>f4'),('intensity','>f4'),('ring','>u2'),('timestamp','>f8')])
        big = np.zeros(len(rows), dtype=dtype)
        for name in big.dtype.names:
            big[name] = rows[name]
        msg.width, msg.height = len(rows)//2, 2
        msg.data = b''.join(big[i*msg.width:(i+1)*msg.width].tobytes()+b'PADDING' for i in range(2))
        msg.row_step = msg.width*msg.point_step+7
        msg.is_bigendian, msg.is_dense = True, True
        raw = wire(msg)
        self.service.submit(msg)
        state = self.service.process_latest()
        self.assertEqual(state['local_range']['wireSha256'], hashlib.sha256(raw).hexdigest())
        self.assertNotEqual(hashlib.sha256(pointcloud_rows(msg).tobytes()).hexdigest(), hashlib.sha256(raw).hexdigest())

    def test_actual_board_genpy_synthetic_wire_vector(self):
        # Generated read-only with the installed ROS1 genpy on the board; no live data.
        raw = bytes.fromhex('63000000640000007b0000001400000073796e7468657469635f776972655f636865636b0100000001000000010000000100000078000000000701000000000400000004000000040000000000803f01')
        self.assertEqual(wire(parse_cloud(raw)), raw)
        self.assertEqual(hashlib.sha256(raw).hexdigest(), 'f694a962d38aab9b9fdabde8a5ad31803cfd280e8d99cb91ece9c26660e7f174')

    def test_duplicate_canonical_publishers_fail_before_registration(self):
        assert_single_publisher([('/single_target_live/state', ['/new'])], '/single_target_live/state', '/new')
        with self.assertRaisesRegex(RuntimeError, '/old'):
            assert_single_publisher([('/single_target_live/state', ['/old'])], '/single_target_live/state', '/new')

    def test_unique_short_hole_preserves_preference_but_not_measurement_or_duration(self):
        tracker = RangeTracker()
        for i in range(3):
            row = step(tracker, [(2,0,.5)], i*.1, i)
        tid = row['target_track_id']
        row = step(tracker, [], .3, 3)
        self.assertEqual(row['continuity_track_id'], tid)
        self.assertIsNone(row['target_track_id'])
        self.assertEqual(row['target_source_rows'], [])
        row = step(tracker, [(2,0,.5)], .4, 4)
        self.assertEqual(row['target_track_id'], tid)
        row = step(tracker, [], .8, 8)
        self.assertIsNone(row['continuity_track_id'])

    def test_short_hole_retains_bound_history_but_cannot_invent_descent(self):
        from test_range_runtime import RuntimeTests
        runtime, _ = RuntimeTests().make(True)
        tracker = RangeTracker()
        def rules(i, centers):
            frame, labels, components = measurement(centers)
            frame.binding = runtime.binding
            record = tracker.update(frame, labels, components, i*.1, i, ground=runtime.ground)
            record['inference_sha256'] = 'fixture'
            return runtime.rules(frame, record, {})
        for i in range(6):
            result = rules(i, [(2,0,.5)])
        count = len(runtime.features.history)
        tid = result['track_id']
        result = rules(6, [])
        self.assertFalse(result['features']['observable'])
        self.assertEqual(len(runtime.features.history), count)
        self.assertEqual(runtime.features._last_track_id, tid)
        result = rules(7, [(2,0,.05)])
        self.assertTrue(result['features']['observation_gap'])
        self.assertIsNone(result['features']['descent_rate_m_s'])
        self.assertEqual(result['features']['near_ground_duration_s'], 0.)
        self.assertNotEqual(result['state']['state'], 'suspected')

    def test_client_snapshots_do_not_restart_active_low_posture_history(self):
        # UI clients have only the read path; a continuous source owns all clocks.
        for i in range(25):
            state = self.send(i, i >= 2)
        self.assertTrue(state['local_range']['groundAlert']['active'])
        alert = copy.deepcopy(self.engine.alert.current)
        feature_count = len(self.engine.runtime.features.history)
        for _ in range(10):
            self.service.snapshot()  # old/new client reads; no lifecycle mutation
        self.assertEqual(self.engine.alert.current, alert)
        self.assertEqual(len(self.engine.runtime.features.history), feature_count)
        state = self.send(25)
        hint = state['local_range']['groundAlert']
        self.assertTrue(hint['active'])
        self.assertEqual(hint['startFrame'], alert['startFrame'])
        self.assertEqual(hint['triggerFrame'], alert['triggerFrame'])


if __name__ == '__main__':
    unittest.main()

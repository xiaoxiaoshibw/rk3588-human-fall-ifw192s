"""ROS message stand-ins -> resident service -> fake Foxglove -> real C#/Qt.

The service instance lives across two native-client windows. Loopback only.
"""
import asyncio
import json
from pathlib import Path
import struct
import sys
import threading
import time
import unittest
from unittest.mock import patch

import numpy as np
import websockets
import test_integration as fixtures

ROOT = fixtures.ROOT
sys.path.insert(0, str(ROOT/'pc_apps/range_fall'))
from live_replay_check import driver_message
from live_tracking_check import wire_message
from core.capture_input import ROW_DTYPE
from core.range_background import RayBackground
from core.range_contract import binding_tuple
from core.range_engine import RangeEngine
from core.range_image import ScanGrid
from core.range_service import RangeService


def ros_string(value):
    b = json.dumps(value, allow_nan=False, separators=(',', ':')).encode()
    return struct.pack('<I', len(b))+b


class BoardServiceChecks(unittest.TestCase):
    setUp = fixtures.TestApp.setUp
    run_service = fixtures.TestApp.run_service

    def test_resident_algorithm_survives_two_qt_clients_and_async_preview(self):
        meta = json.loads((fixtures.SESSION/'meta.json').read_text('utf8'))
        tables = ROOT/'src/inno_lidar_ros/config/ifw192s'
        grid = ScanGrid.from_csv(tables/'ifw192s_azimuth_192x256.csv', tables/'ifw192s_elevation_192x256.csv')
        identity = dict(session='OFFLINE_BOARD_RESIDENT', coordinate='RAW/innolidar', grid_sha256=grid.sha256, units='m')
        prefix, messages = [], []
        with (fixtures.SESSION/'points.bin').open('rb') as stream:
            for i in list(range(50))+list(range(100,170)):
                info = meta['frames'][i]
                stream.seek(info['offset_points']*28)
                raw = stream.read(info['count_points']*28)
                if i < 50:
                    prefix.append(grid.decode(raw, binding_tuple(identity)))
                else:
                    msg = driver_message(np.frombuffer(raw, ROW_DTYPE), info, 'innolidar')
                    wire = wire_message(msg)
                    msg.serialize = lambda stream, b=wire: stream.write(b)
                    messages.append((msg, wire))
        engine = RangeEngine(grid, 'innolidar', identity, RayBackground(prefix, empty_prefix_declared=True))
        floor_support = {'available': True, 'reason': 'current_patch_support'}
        service = RangeService(engine, release_id='OFFLINE_RESIDENT_FIXTURE')
        background = engine.runtime.background
        instance = engine.identity['session']
        ready, stop = threading.Event(), threading.Event()
        context, errors, calls = {}, [], []

        async def scenario():
            # Process before any client exists: no subscription dependency.
            for msg, _ in messages[:10]:
                service.submit(msg)
                service.process_latest()
            context['preclientProcessed'] = service.processed
            connections = 0

            async def client(ws):
                nonlocal connections
                connection = connections
                connections += 1
                channels = [dict(id=1, topic='/innolidar_points', encoding='ros1', schemaName='sensor_msgs/PointCloud2'),
                            dict(id=2, topic='/single_target_live/state', encoding='ros1', schemaName='std_msgs/String')]
                await ws.send(json.dumps(dict(op='advertise', channels=channels)))
                subscriptions = {}
                while len(subscriptions) < 2:
                    request = json.loads(await ws.recv())
                    calls.append(request)
                    self.assertEqual(request['op'], 'subscribe')
                    subscriptions.update({v['channelId']:v['id'] for v in request['subscriptions']})
                if connection == 1:
                    plane = json.loads((ROOT/'docs/evidence/2026-10-23_range_p0_w2/BOUND_GROUND.json').read_text('utf8'))
                    plane['binding'] = identity
                    engine.runtime.ground = plane  # explicitly offline fixture, never site evidence
                    engine.runtime.ground_sha = 'a' * 64
                    plane.update(monitor={'fixture': True}, siteBinding={'siteId': 'offline-test'})
                start = time.monotonic()
                try:
                    for j, (msg, wire) in enumerate(messages[10+connection*30:40+connection*30]):
                        await asyncio.sleep(max(0, start+j*.15-time.monotonic()))
                        floor_support['available'] = connection == 0 or j < 10
                        floor_support['reason'] = 'current_patch_support' if floor_support['available'] else 'ground_patch_support_or_residual_failed'
                        await ws.send(struct.pack('<BIQ',1,subscriptions[1],0)+wire)
                        service.submit(msg)
                        await asyncio.to_thread(service.process_latest)
                        # Primary result has no PNG; client must accept current target first.
                        await ws.send(struct.pack('<BIQ',1,subscriptions[2],0)+ros_string(service.snapshot()))
                        await asyncio.to_thread(service.process_preview)
                        await ws.send(struct.pack('<BIQ',1,subscriptions[2],0)+ros_string(service.snapshot()))
                    while not stop.is_set():
                        await asyncio.sleep(.05)
                        await ws.send(struct.pack('<BIQ',1,subscriptions[2],0)+ros_string(service.snapshot()))
                except websockets.ConnectionClosed:
                    pass

            async with websockets.serve(client, '127.0.0.1', 0, subprotocols=['foxglove.websocket.v1'], compression=None) as server:
                context['url'] = 'ws://127.0.0.1:%d'%server.sockets[0].getsockname()[1]
                ready.set()
                while not stop.is_set():
                    await asyncio.sleep(.03)

        def serve():
            try:
                asyncio.run(scenario())
            except BaseException as exc:
                errors.append(repr(exc))
                ready.set()

        monitor_patch = patch('core.range_site_ground.monitor', side_effect=lambda *a: dict(floor_support))
        monitor_patch.start()
        worker = threading.Thread(target=serve)
        worker.start()
        try:
            self.assertTrue(ready.wait(10))
            self.assertFalse(errors, errors)
            self.assertEqual(context['preclientProcessed'], 10)
            reports = []
            for client in range(2):
                self.out = self.out/('client%d'%client)
                self.out.mkdir()
                report = self.run_service(['--smoke', '--smoke-live', context['url'], '--live-duration-ms', '6200',
                    '--smoke-depth', '--screenshot', str(self.out/'window.png')])
                reports.append(report)
                frames = [r for r in report['log'] if r['eventType']=='published' and r['info']['mode']=='live']
                matched = [r for r in frames if r['info'].get('depth') and r['info']['targetCount']]
                self.assertGreaterEqual(len(matched), 15)
                for r in matched:
                    result = r['info']['result']
                    self.assertEqual(result['service']['releaseId'], 'OFFLINE_RESIDENT_FIXTURE')
                    self.assertEqual(r['info']['targetMode'], 'range_service_automatic')
                    self.assertEqual(r['info']['sessionId'], instance)
                    self.assertFalse(r['info']['confirmedEnabled'])
                    self.assertEqual(result['heightMedianM'] is None, not result['groundStatus']['available'])
                level = json.loads((self.out/'LIVE_LEVEL.json').read_text('utf8'))
                self.assertEqual(level['available'], client == 1)
                self.assertEqual(level['automatic'], client == 1)
                if client == 1:
                    self.assertTrue(level['active'])
                    self.assertLess(level['residualDeg'], .001)
                    self.assertFalse(level['snapshot']['result']['groundStatus']['available'])
                    self.assertIsNone(level['snapshot']['result']['heightMedianM'])
                self.assertIs(engine.runtime.background, background)
                self.assertEqual(engine.identity['session'], instance)
                final = json.loads((self.out/'LIVE_END.json').read_text('utf8'))['snapshot']
                self.assertEqual(final.get('targetCount'), 0)
                self.assertIsNone(final.get('result'))
                self.assertIsNone(final.get('depth'))
                unexpected = [r['message'] for r in report['log'] if r['eventType']=='nativeStderr'
                              and 'Layout polish loop detected' not in r['message']]
                self.assertEqual(unexpected, [])
        finally:
            stop.set()
            worker.join(10)
            monitor_patch.stop()
        self.assertFalse(worker.is_alive())
        self.assertFalse(errors, errors)
        (self.out/'RESIDENT_SUMMARY.json').write_text(json.dumps(dict(preclientProcessed=10,
            finalProcessed=service.processed, sameBackground=engine.runtime.background is background,
            sameInstance=engine.identity['session']==instance, calls=calls,
            scope='offline ROS stand-in + fake Foxglove + real native rendering; no board IO'), indent=2), encoding='utf8')


if __name__ == '__main__':
    unittest.main()

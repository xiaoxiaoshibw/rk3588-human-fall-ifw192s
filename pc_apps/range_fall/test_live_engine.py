import asyncio
import base64
import hashlib
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest

import numpy as np
import websockets

from live_engine import LiveEngine,parse_cloud,site_ground
from live_bridge import Bridge
from live_replay_check import driver_message
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'src/human_fall_detection/tests'))
from test_range_frontend import scene
from core.capture_input import ROW_DTYPE
from core.range_contract import binding_tuple
from core.range_runtime import RangeRuntime
from core.range_background import RayBackground


def wire_message(msg):
    def text(value):
        raw=value.encode();return struct.pack('<I',len(raw))+raw
    h=msg.header
    fields=b''.join(text(f.name)+struct.pack('<IBI',f.offset,f.datatype,f.count) for f in msg.fields)
    return (struct.pack('<III',h.seq,h.stamp.secs,h.stamp.nsecs)+text(h.frame_id)
        +struct.pack('<III',msg.height,msg.width,len(msg.fields))+fields
        +struct.pack('<?III',msg.is_bigendian,msg.point_step,msg.row_step,len(msg.data))+msg.data+b'\x00')


class LiveEngineTests(unittest.TestCase):
    def make(self,prefix=2,ground=True,body=False):
        grid,_,_=scene(np.full((8,24),3.))
        engine=LiveEngine(grid,'lidar',empty_prefix_frames=prefix,body=body)
        if ground:
            engine.runtime.ground=dict(status='valid',binding=engine.identity,frame='lidar',normal=[0,0,1],offset_m=.5)
        return grid,engine

    def raw(self,i,target=True):
        depth=np.full((8,24),3.)
        if target:depth[2:6,8:14]=2.
        _,packed,_=scene(depth)
        msg=driver_message(np.frombuffer(packed,ROW_DTYPE),dict(seq=i+50,stamp_sec=100+i//10,stamp_nanosec=i%10*100000000),'lidar')
        return wire_message(msg)

    def test_driver_layout_and_same_runtime_target_geometry(self):
        grid,engine=self.make()
        oracle=RangeRuntime(grid,engine.identity,empty_prefix_frames=2,ground=engine.runtime.ground)
        from core.range_live import pointcloud_rows
        for i in range(30):
            raw=self.raw(i,i>=2);msg=parse_cloud(raw);state=engine.process(raw)
            expected,_,_=oracle.update(pointcloud_rows(msg),msg.header.stamp.secs+msg.header.stamp.nsecs/1e9,i)
            self.assertEqual(state['target_source_rows'],expected['tracking']['target_source_rows'])
            self.assertEqual(state['track_id'],expected['tracking']['target_track_id'])
            bundle=state['local_range']
            self.assertEqual(bundle['wireSha256'],hashlib.sha256(raw).hexdigest())
            self.assertEqual(bundle['depth']['previewSha256'],hashlib.sha256(base64.b64decode(bundle['preview'])).hexdigest())
        self.assertTrue(state['target_source_rows'])
        self.assertFalse(state['confirmed_enabled'])

    def test_no_background_still_has_current_depth_and_no_fabricated_target(self):
        grid,_=self.make();engine=LiveEngine(grid,'lidar')
        state=engine.process(self.raw(0))
        self.assertEqual(state['acquisition']['reason'],'background_not_declared')
        self.assertEqual(state['target_source_rows'],[])
        self.assertEqual(state['local_range']['groundAlert']['state'],'unavailable')
        self.assertTrue(state['local_range']['preview'])

    def test_duplicate_bad_frame_and_expiry_clear_state(self):
        _,engine=self.make()
        engine.process(self.raw(0));state=engine.process(self.raw(0))
        self.assertIsNone(state['source']);self.assertIn('rebind',state['acquisition']['reason'])
        _,engine=self.make();state=engine.process(b'bad')
        self.assertIsNone(state['source'])
        _,engine=self.make();state=engine.process(self.raw(0),received=0)
        self.assertEqual(state['acquisition']['reason'],'local_input_expired')
        self.assertIsNone(engine.alert.previous)
        self.assertIsNone(engine.posture.last_frame)
        for raw in (self.raw(0)[:-1],self.raw(0)+b'bad'):
            with self.assertRaises(ValueError):parse_cloud(raw)

    def test_ground_and_history_invalidated_by_calibration_and_source_changes(self):
        _,engine=self.make()
        for i in range(5):engine.process(self.raw(i,i>=2))
        engine.identity['grid_sha256']='changed'
        state=engine.process(self.raw(5))
        self.assertEqual(state['acquisition']['reason'],'calibration_changed_requires_rebind')
        self.assertIsNone(engine.runtime.ground);self.assertIsNone(engine.alert.previous)
        _,engine=self.make();engine.process(self.raw(0));engine.invalidate('source_changed')
        self.assertIsNone(engine.runtime.ground);self.assertEqual(len(engine.runtime.features.history),0)

    def test_current_ground_monitor_reuses_single_decode(self):
        from unittest.mock import patch
        from test_live_ground import accepted_fixture
        grid,engine=self.make()
        engine.runtime.ground.update(monitor=accepted_fixture({'frameId':'lidar'}, {}, {})['monitor'],siteBinding={})
        with patch.object(grid,'decode',wraps=grid.decode) as decode:
            state=engine.process(self.raw(0,False))
            self.assertEqual(decode.call_count,1)
        self.assertFalse(state['local_range']['ground']['available'])
        self.assertIsNone(state['local_range']['heightMedianM'])

    def test_stale_clear_keeps_current_epoch_after_ground_rebind(self):
        _,engine=self.make()
        engine.runtime.tracker.generation=3
        state=engine.invalid('required_cloud_stale')
        self.assertEqual(state['time_epoch'],3)
        self.assertEqual(state['target_source_rows'],[])
        self.assertIsNone(state['source'])

    def test_live_ground_rejects_offline_and_wrong_site_provenance(self):
        grid,engine=self.make()
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/'ground.json';p.write_text('{"status":"valid"}')
            with self.assertRaisesRegex(ValueError,'site/frame'):site_ground(p,'lidar',grid.sha256,'test',engine.identity)
            binding=dict(siteId='test',frameId='lidar',gridSha256=grid.sha256);plane=dict(normal=[0,0,1],offset_m=.5)
            source=Path(temp)/'provenance.json';source.write_text(json.dumps(dict(binding=binding,plane=plane)))
            p.write_text(json.dumps(dict(format='live_site_ground/1',binding=binding,plane=plane,
                provenance=dict(source=str(source),sha256=hashlib.sha256(source.read_bytes()).hexdigest()))))
            with self.assertRaisesRegex(ValueError,'accepted quality'):site_ground(p,'lidar',grid.sha256,'test',engine.identity)
            from test_live_ground import accepted_fixture
            fixture=accepted_fixture(binding,plane,engine.identity)
            source.write_text(json.dumps(fixture))
            doc=json.loads(p.read_text());doc['provenance']['sha256']=hashlib.sha256(source.read_bytes()).hexdigest()
            p.write_text(json.dumps(doc))
            actual=site_ground(p,'lidar',grid.sha256,'test',engine.identity)
            self.assertEqual(actual['binding'],engine.identity)
            with self.assertRaises(ValueError):site_ground(p,'lidar',grid.sha256,'other',engine.identity)
            source.write_text('{}')
            with self.assertRaisesRegex(ValueError,'provenance changed'):site_ground(p,'lidar',grid.sha256,'test',engine.identity)

    def test_frozen_background_uses_only_declared_past_measurements(self):
        grid,engine=self.make();from core.range_live import pointcloud_rows
        prefix=[grid.decode(pointcloud_rows(parse_cloud(self.raw(i,False))),binding_tuple(engine.identity)) for i in range(2)]
        background=RayBackground(prefix,empty_prefix_declared=True,min_observations=2)
        live=LiveEngine(grid,'lidar',engine.identity,background)
        for i in range(20):state=live.process(self.raw(i+100))
        self.assertTrue(state['target_source_rows'])
        self.assertEqual(state['local_range']['groundAlert']['state'],'unavailable')
        background.last_declared_header=(999,999.)
        live=LiveEngine(grid,'lidar',engine.identity,background)
        self.assertEqual(live.process(self.raw(0))['acquisition']['reason'],'background_source_epoch_mismatch')


class BridgeTests(unittest.IsolatedAsyncioTestCase):
    async def test_read_only_subscription_and_bounded_client_queue(self):
        grid,_,_=scene(np.full((8,24),3.));bridge=Bridge(LiveEngine(grid,'lidar'),'ws://127.0.0.1:1')
        async with websockets.serve(bridge.client,'127.0.0.1',0,subprotocols=['foxglove.websocket.v1'],origins=[None]) as server:
            port=server.sockets[0].getsockname()[1]
            async with websockets.connect('ws://127.0.0.1:%d'%port,subprotocols=['foxglove.websocket.v1'],proxy=None) as client:
                self.assertEqual(json.loads(await client.recv())['op'],'advertise')
                await client.send(json.dumps(dict(op='subscribe',subscriptions=[dict(id=8,channelId=2)])))
                await asyncio.sleep(.02)
                bridge.publish(2,b'test')
                raw=await asyncio.wait_for(client.recv(),1)
                self.assertEqual(struct.unpack_from('<I',raw,1)[0],8);self.assertEqual(raw[13:],b'test')
                await client.send(json.dumps(dict(op='publish',channelId=99)))
                with self.assertRaises(websockets.ConnectionClosed):await client.recv()
        self.assertEqual(bridge.received,0)


if __name__=='__main__':unittest.main()

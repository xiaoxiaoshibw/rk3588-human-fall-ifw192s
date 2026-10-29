"""Real native-client TTL/epoch regressions with recorded loopback-only input."""
import asyncio
import copy
import json
import struct
import sys
import threading
import time
import unittest

import numpy as np
import websockets
import test_integration as fixtures

sys.path.insert(0,str(fixtures.ROOT/'pc_apps/range_fall'))
from live_replay_check import driver_message
from live_tracking_check import wire_message
from core.capture_input import ROW_DTYPE
from core.range_background import RayBackground
from core.range_contract import binding_tuple
from core.range_engine import RangeEngine
from core.range_image import ScanGrid
from core.range_service import RangeService


class ServiceTtlTests(unittest.TestCase):
    setUp=fixtures.TestApp.setUp
    run_service=fixtures.TestApp.run_service

    def scenario(self,mode,missing_ack=False):
        root=fixtures.ROOT
        meta=json.loads((fixtures.SESSION/'meta.json').read_text('utf8'))
        tables=root/'src/inno_lidar_ros/config/ifw192s'
        grid=ScanGrid.from_csv(tables/'ifw192s_azimuth_192x256.csv',tables/'ifw192s_elevation_192x256.csv')
        identity=dict(session='OFFLINE_TTL_FIXTURE',coordinate='RAW/innolidar',grid_sha256=grid.sha256,units='m')
        prefix=[];messages=[]
        with (fixtures.SESSION/'points.bin').open('rb') as stream:
            for i in list(range(50))+list(range(100,110)):
                info=meta['frames'][i];stream.seek(info['offset_points']*28)
                raw=stream.read(info['count_points']*28)
                if i<50:prefix.append(grid.decode(raw,binding_tuple(identity)))
                else:
                    msg=driver_message(np.frombuffer(raw,ROW_DTYPE),info,'innolidar')
                    wire=wire_message(msg);msg.serialize=lambda f,b=wire:f.write(b)
                    messages.append((msg,wire))
        engine=RangeEngine(grid,'innolidar',identity,RayBackground(prefix,empty_prefix_declared=True))
        if missing_ack or mode.startswith('ground-'):
            # Explicitly offline plane, rebound only to this fixture identity.
            plane=json.loads((root/'docs/evidence/2026-10-23_range_p0_w2/BOUND_GROUND.json').read_text('utf8'))
            plane['binding']=dict(identity)
            engine.runtime.ground=plane
            engine.runtime.ground_sha='a'*64
        service=RangeService(engine,release_id='OFFLINE_TTL')
        for msg,wire in messages:
            service.submit(msg);service.process_latest()
        service.process_preview()
        state=service.snapshot()
        self.assertTrue(state['target_source_rows'])
        plain=copy.deepcopy(state)
        plain.get('local_range',{}).pop('preview',None)
        raw=messages[-1][1]
        ready,stop=threading.Event(),threading.Event();context={};errors=[]

        async def serve():
            async def client(ws):
                await ws.send(json.dumps(dict(op='advertise',channels=[
                    dict(id=1,topic='/innolidar_points',encoding='ros1',schemaName='sensor_msgs/PointCloud2'),
                    dict(id=2,topic='/single_target_live/state',encoding='ros1',schemaName='std_msgs/String')])))
                subs={}
                while len(subs)<2:
                    req=json.loads(await ws.recv())
                    self.assertEqual(req['op'],'subscribe')
                    subs.update({v['channelId']:v['id'] for v in req['subscriptions']})
                async def send(value):
                    b=json.dumps(value,allow_nan=False).encode()
                    await ws.send(struct.pack('<BIQI',1,subs[2],0,len(b))+b)
                try:
                    if mode=='depth-late':
                        # Let startup/replay ACK settle so the cloud's 500 ms TTL is
                        # measured from a quiet client, not the first live handover.
                        await asyncio.sleep(.2)
                        await ws.send(struct.pack('<BIQ',1,subs[1],0)+raw)
                        await asyncio.sleep(.05)
                        await send(plain)
                        await asyncio.sleep(.42)
                        await send(state)
                        while not stop.is_set():await asyncio.sleep(.03)
                        return
                    if mode.startswith('ground-'):
                        await asyncio.sleep(.2)  # allow the native window startup to settle
                    await ws.send(struct.pack('<BIQ',1,subs[1],0)+raw)
                    if mode=='bad-ground':
                        state['local_range']['ground']['displayPlane']['groundSha256']='b'*64
                    elif mode.startswith('bad-'):
                        state['source']=None
                        if mode=='bad-protocol':state['service']['protocol']='range_recognition/999'
                        elif mode=='bad-instance':state['service']['instanceId']='different-source'
                        elif mode=='bad-capabilities':state['service']['capabilities']=[]
                    if mode=='late':await asyncio.sleep(.7)
                    await send(state)
                    if mode.startswith('ground-') and mode!='ground-silent':
                        await asyncio.sleep(.48)
                        invalid=copy.deepcopy(state)
                        invalid['source']=None;invalid['local_range']=None
                        invalid['track_id']=None;invalid['track_status']='unselected'
                        invalid['target_source_rows']=[];invalid['bbox_observed']=False
                        invalid['fall_status']='unknown';invalid['observability']='invalid'
                        invalid['acquisition']['reason']='history_invalidated_during_processing'
                        invalid['groundBinding']['supportCurrent']=False
                        if mode in ('ground-sha','ground-old'):
                            invalid['groundBinding']['sha256']='b'*64
                            invalid['groundBinding']['displayPlane']['groundSha256']='b'*64
                        if mode=='ground-tamper':invalid['groundBinding']['displayPlane']['offsetM']+=.1
                        if mode=='ground-epoch':invalid['time_epoch']+=1
                        if mode=='ground-session':
                            invalid['session_id']='OTHER_SESSION'
                            invalid['service']['instanceId']='OTHER_SESSION'
                            invalid['groundBinding']=None
                        await send(invalid)
                        for _ in range(12):
                            await asyncio.sleep(.15)
                            await send(state if mode=='ground-old' else invalid)
                    elif mode in ('silent-state','ground-silent'):
                        # State publisher/transport stops while raw input keeps
                        # arriving. Advancing synthetic headers, held recorded XYZ.
                        for i in range(1,22):
                            await asyncio.sleep(.1)
                            h=state['source'];ns=h['stamp_nsecs']+i*100000000
                            advancing=struct.pack('<III',h['seq']+i,h['stamp_secs']+ns//1000000000,ns%1000000000)+raw[12:]
                            await ws.send(struct.pack('<BIQ',1,subs[1],0)+advancing)
                    elif mode=='epoch':
                        await asyncio.sleep(.43)
                        changed=copy.deepcopy(state)
                        changed['time_epoch']+=1;changed['source']['seq']+=1
                        await send(changed)
                    else:
                        for _ in range(4):
                            await asyncio.sleep(.2)
                            await send(state)  # duplicate heartbeat cannot renew the original cloud
                    while not stop.is_set():await asyncio.sleep(.03)
                except websockets.ConnectionClosed:pass
            async with websockets.serve(client,'127.0.0.1',0,subprotocols=['foxglove.websocket.v1'],compression=None) as server:
                context['url']='ws://127.0.0.1:%d'%server.sockets[0].getsockname()[1];ready.set()
                while not stop.is_set():await asyncio.sleep(.03)
        def thread():
            try:asyncio.run(serve())
            except BaseException as exc:errors.append(repr(exc));ready.set()
        worker=threading.Thread(target=thread);worker.start()
        try:
            self.assertTrue(ready.wait(5));self.assertFalse(errors,errors)
            options=['--smoke','--smoke-live',context['url'],'--live-duration-ms','2400',
                '--screenshot',str(self.out/'window.png')]
            if missing_ack:options+=['--ack-fault','missing-live']
            report=self.run_service(options)
        finally:stop.set();worker.join(5)
        self.assertFalse(worker.is_alive());self.assertFalse(errors,errors)
        measured=[r for r in report['log'] if r['eventType']=='published' and r.get('info',{}).get('mode')=='live' and r['info']['targetCount']]
        if mode=='depth-late':
            self.assertTrue(measured)
            self.assertTrue(any(r['eventType']=='depthUpdate' for r in report['log']),report['log'])
            self.assertEqual(report['directBoardCalls'],0)
            return
        if mode.startswith('ground-'):
            self.assertTrue(measured)
            final=json.loads((self.out/'LIVE_LEVEL.json').read_text('utf8'))
            self.assertEqual(final['snapshot']['targetCount'],0)
            self.assertIsNone(final['snapshot'].get('result'))
            if mode in ('ground-stale','ground-epoch'):
                self.assertTrue(final['available'],final)
                self.assertEqual(final['snapshot']['liveGroundStatus']['sha256'],'a'*64)
            else:
                self.assertFalse(final['available'],final)
                self.assertFalse(final['snapshot'].get('liveGroundStatus'))
            return
        if mode=='late' or mode.startswith('bad-'):self.assertEqual(measured,[])
        else:
            self.assertTrue(measured)
            reason='state stream stale' if mode=='silent-state' else 'identity changed' if mode=='epoch' else 'result expired'
            cleared=[r for r in report['log'] if r['eventType']=='liveStatus' and reason in r.get('message','') and r.get('clearTarget')]
            self.assertTrue(cleared,report['log'])
            self.assertLess(cleared[0]['atMs']-measured[0]['atMs'],230)
            self.assertFalse(any(r['atMs']>cleared[0]['atMs'] for r in measured))
        self.assertEqual(report['directBoardCalls'],0)
        if mode.startswith('bad-'):
            errors=[r['message'] for r in report['log'] if r['eventType']=='liveStatus']
            self.assertTrue(any(('ground display binding' if mode=='bad-ground' else 'recognition service') in message.lower() for message in errors),errors)
        if missing_ack and mode!='bad-ground':
            self.assertEqual(measured[0]['info']['result']['groundStatus']['displayPlane']['groundSha256'], 'a'*64)
            held=json.loads((self.out/'ACK_HELD.json').read_text('utf8'))
            self.assertGreater(held['targetCount'],0)
            self.assertIsNotNone(held['result']['heightMedianM'])
            final=json.loads((self.out/'LIVE_END.json').read_text('utf8'))['snapshot']
            self.assertEqual(final['targetCount'],0)
            self.assertIsNone(final.get('result'))
            self.assertIsNone(final.get('depth'))

    def test_repeated_heartbeat_does_not_renew_result_ttl(self):self.scenario('repeat')
    def test_result_arriving_after_source_ttl_is_not_displayed(self):self.scenario('late')
    def test_epoch_change_clears_previous_identity_immediately(self):self.scenario('epoch')
    def test_missing_ack_does_not_block_expiry_clear(self):self.scenario('repeat',True)
    def test_missing_ack_does_not_block_identity_clear(self):self.scenario('epoch',True)
    def test_invalid_heartbeat_protocol_is_rejected(self):self.scenario('bad-protocol')
    def test_mismatched_ground_version_is_rejected(self):self.scenario('bad-ground',True)
    def test_invalid_heartbeat_instance_is_rejected(self):self.scenario('bad-instance')
    def test_missing_heartbeat_capabilities_are_rejected(self):self.scenario('bad-capabilities')
    def test_state_publication_silence_is_distinct_from_raw_input_silence(self):self.scenario('silent-state')
    def test_late_preview_refreshes_displayed_depth_only(self):self.scenario('depth-late')
    def test_invalid_recognition_keeps_bound_level_view(self):self.scenario('ground-stale')
    def test_changed_ground_sha_clears_view_until_new_source(self):self.scenario('ground-sha')
    def test_changed_session_clears_view(self):self.scenario('ground-session')
    def test_changed_plane_with_same_sha_is_rejected(self):self.scenario('ground-tamper')
    def test_state_stream_silence_clears_binding(self):self.scenario('ground-silent')
    def test_older_source_cannot_restore_replaced_ground(self):self.scenario('ground-old')
    def test_tracker_epoch_change_keeps_same_ground_binding(self):self.scenario('ground-epoch')


if __name__=='__main__':unittest.main()

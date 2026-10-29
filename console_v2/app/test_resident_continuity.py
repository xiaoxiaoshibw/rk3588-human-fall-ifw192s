"""Continuous derived low-pose input while two real Qt clients open/close.

Recorded XYZ is held constant with explicit synthetic advancing headers. This
checks service/client lifecycle and hint continuity, never physical fall effect.
"""
import asyncio
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
from core.range_contract import load_ground
from core.range_engine import RangeEngine
from core.range_image import ScanGrid
from core.range_service import RangeService


class ResidentContinuityTests(unittest.TestCase):
    setUp=fixtures.TestApp.setUp
    run_service=fixtures.TestApp.run_service

    def test_active_hint_history_survives_two_real_qt_windows_on_continuous_source(self):
        root=fixtures.ROOT;session=root/'data/sessions/cap_20261017_113516'
        meta=json.loads((session/'meta.json').read_text('utf8'))
        reference=json.loads((root/'docs/evidence/2026-10-26_unified_flow/run780_final/analysis.json').read_text('utf8'))
        identity=reference['sourceBinding'];tables=root/'src/inno_lidar_ros/config/ifw192s'
        grid=ScanGrid.from_csv(tables/'ifw192s_azimuth_192x256.csv',tables/'ifw192s_elevation_192x256.csv')
        plane=load_ground(root/'docs/evidence/2026-10-26_unified_flow/ground780/BOUND_GROUND.json',identity)
        engine=RangeEngine(grid,'innolidar',identity,empty_prefix_frames=50,ground=plane)
        service=RangeService(engine,release_id='OFFLINE_CONTINUOUS_LOW_STANDIN')
        with (session/'points.bin').open('rb') as stream:
            for i,info in enumerate(meta['frames'][:701]):
                stream.seek(info['offset_points']*28);raw=stream.read(info['count_points']*28)
                msg=driver_message(np.frombuffer(raw,ROW_DTYPE),info,'innolidar')
                wire=wire_message(msg);msg.serialize=lambda f,b=wire:f.write(b)
                service.submit(msg);state=service.process_latest()
        self.assertTrue(state['local_range']['groundAlert']['active'])
        self.assertTrue(state['local_range']['demoFallCandidate']['active'])
        background=engine.runtime.background;trigger=engine.alert.current['triggerFrame']
        template=np.frombuffer(raw,ROW_DTYPE).copy();last=meta['frames'][700]
        start_ns=last['stamp_sec']*1000000000+last['stamp_nanosec']
        ready,stop=threading.Event(),threading.Event();context={};errors=[];clients={};records=[]

        async def scenario():
            async def client(ws):
                await ws.send(json.dumps(dict(op='advertise',channels=[
                    dict(id=1,topic='/innolidar_points',encoding='ros1',schemaName='sensor_msgs/PointCloud2'),
                    dict(id=2,topic='/single_target_live/state',encoding='ros1',schemaName='std_msgs/String')])))
                subscriptions={};clients[ws]=subscriptions
                try:
                    async for data in ws:
                        req=json.loads(data)
                        self.assertEqual(req['op'],'subscribe')
                        subscriptions.update({x['channelId']:x['id'] for x in req['subscriptions']})
                except websockets.ConnectionClosed:
                    pass
                finally:clients.pop(ws,None)

            async def source():
                index=0;anchor=time.monotonic()
                while not stop.is_set():
                    index+=1
                    await asyncio.sleep(max(0,anchor+index*.104-time.monotonic()))
                    ns=start_ns+index*104000000
                    info=dict(seq=last['seq']+index,stamp_sec=ns//1000000000,stamp_nanosec=ns%1000000000)
                    msg=driver_message(template,info,'innolidar');wire=wire_message(msg)
                    msg.serialize=lambda f,b=wire:f.write(b)
                    service.submit(msg);await asyncio.to_thread(service.process_latest)
                    await asyncio.to_thread(service.process_preview)
                    state=service.snapshot();hint=(state.get('local_range') or {}).get('groundAlert') or {}
                    records.append(dict(index=index,clients=len(clients),active=hint.get('active'),triggerFrame=hint.get('triggerFrame')))
                    for ws,subs in list(clients.items()):
                        if len(subs)<2:continue
                        b=json.dumps(state,allow_nan=False).encode()
                        try:
                            await ws.send(struct.pack('<BIQ',1,subs[1],0)+wire)
                            await ws.send(struct.pack('<BIQI',1,subs[2],0,len(b))+b)
                        except websockets.ConnectionClosed:pass
            async with websockets.serve(client,'127.0.0.1',0,subprotocols=['foxglove.websocket.v1'],compression=None) as server:
                task=asyncio.create_task(source())
                context['url']='ws://127.0.0.1:%d'%server.sockets[0].getsockname()[1];ready.set()
                try:
                    while not stop.is_set():await asyncio.sleep(.03)
                finally:
                    await task
        def run():
            try:asyncio.run(scenario())
            except BaseException as exc:errors.append(repr(exc));ready.set()
        worker=threading.Thread(target=run);worker.start()
        base=self.out
        try:
            self.assertTrue(ready.wait(5));self.assertFalse(errors,errors)
            for i in range(2):
                self.out=base/('client%d'%i);self.out.mkdir()
                report=self.run_service(['--smoke','--smoke-live',context['url'],'--live-duration-ms','3400',
                    '--screenshot',str(self.out/'window.png')])
                measured=[r['info'] for r in report['log'] if r['eventType']=='published' and r.get('info',{}).get('targetCount',0)>0 and r['info'].get('mode')=='live']
                self.assertGreaterEqual(len(measured),15)
                self.assertTrue(all(r['result']['groundAlert']['active'] and r['result']['groundAlert']['triggerFrame']==trigger for r in measured))
                self.assertTrue(all(r['result']['demoFallCandidate']['active'] and not r['result']['demoFallCandidate']['confirmedEnabled'] for r in measured))
                self.assertIs(engine.runtime.background,background)
                self.assertEqual(engine.alert.current['triggerFrame'],trigger)
        finally:
            stop.set();worker.join(5)
        self.assertFalse(worker.is_alive());self.assertFalse(errors,errors)
        self.assertTrue(any(r['clients']==0 for r in records),'source must continue without Qt clients')
        self.assertTrue(all(r['active'] and r['triggerFrame']==trigger for r in records))
        (base/'CONTINUOUS_HINT.json').write_text(json.dumps(dict(frames=records,triggerFrame=trigger,
            sameBackground=engine.runtime.background is background,health=service.snapshot()['health'],
            scope='offline held-XYZ/advancing-header simulation; no physical fall or board performance conclusion'),indent=2),encoding='utf8')


if __name__=='__main__':unittest.main()

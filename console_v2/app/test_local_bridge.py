"""Local recorded messages -> real live engine -> loopback bridge -> C#/Qt.

Uses only a fake upstream on loopback. No real board calls or raw recording.
"""
import asyncio
import hashlib
import json
from pathlib import Path
import sys
import threading
import time
import unittest

import numpy as np
import websockets
import test_integration as fixtures

ROOT=fixtures.ROOT
sys.path.insert(0,str(ROOT/'pc_apps/range_fall'))
from live_engine import LiveEngine
from live_bridge import Bridge
from live_replay_check import driver_message
from test_live_engine import wire_message
from core.range_background import RayBackground
from core.range_contract import binding_tuple
from core.range_image import ScanGrid
from core.capture_input import ROW_DTYPE


class LocalBridgeChecks(unittest.TestCase):
    setUp=fixtures.TestApp.setUp
    run_service=fixtures.TestApp.run_service

    def test_real_386_messages_local_tracking_depth_body_and_native_ack(self):
        session=ROOT/'data/sessions/cap_20261018_110029'
        meta=json.loads((session/'meta.json').read_text('utf8'))
        tables=ROOT/'src/inno_lidar_ros/config/ifw192s'
        grid=ScanGrid.from_csv(tables/'ifw192s_azimuth_192x256.csv',tables/'ifw192s_elevation_192x256.csv')
        identity=dict(session='local_fixture',coordinate='RAW/innolidar',grid_sha256=grid.sha256,units='m')
        prefix=[];messages=[]
        with (session/'points.bin').open('rb') as stream:
            for index in list(range(50))+list(range(110,140)):
                info=meta['frames'][index];stream.seek(info['offset_points']*28);raw=stream.read(info['count_points']*28)
                if index<50:prefix.append(grid.decode(raw,binding_tuple(identity)))
                else:messages.append(wire_message(driver_message(np.frombuffer(raw,ROW_DTYPE),info,'innolidar')))
        background=RayBackground(prefix,empty_prefix_declared=True)
        engine=LiveEngine(grid,'innolidar',identity,background,body=True)
        tamper=getattr(self,'tamper',False)
        if tamper:
            original=engine.process
            def corrupt(*args,**kwargs):
                result=original(*args,**kwargs)
                if result.get('local_range'):result['local_range']['wireSha256']='0'*64
                return result
            engine.process=corrupt
        plane=json.loads((ROOT/'docs/evidence/2026-10-23_range_p0_w2/BOUND_GROUND.json').read_text('utf8'))
        plane['binding']=identity
        no_ground=getattr(self,'no_ground',False)
        if not no_ground:engine.runtime.ground=plane
        fit_report=None
        if getattr(self,'fit_site',False):
            from live_ground import fit_site
            headers=[dict(seq=m['seq'],sec=m['stamp_sec'],nsec=m['stamp_nanosec'],frame_id='innolidar')
                     for m in meta['frames'][:28]]
            fit_report=fit_site([f.xyz[f.source_rows[f.valid]] for f in prefix[:28]],headers,
                dict(siteId='MOCK_OFFLINE',frameId='innolidar',gridSha256=grid.sha256),
                dict(upstream=None,identity=identity))
            self.assertEqual(fit_report['status'],'geometry_accepted',fit_report.get('reason'))
        ready=threading.Event();stop=threading.Event();state={};calls=[];failures=[]
        async def scenario():
            bridge=None
            async def upstream(ws):
                channels=[dict(id=1,topic='/innolidar_points',encoding='ros1',schemaName='sensor_msgs/PointCloud2')]
                await ws.send(json.dumps(dict(op='advertise',channels=channels)))
                calls.append(json.loads(await ws.recv()))
                while not stop.is_set() and not any(c['subscriptions'] for c in bridge.clients.values()):await asyncio.sleep(.01)
                start=time.monotonic()
                from struct import pack
                try:
                    for i,raw in enumerate(messages):
                        await asyncio.sleep(max(0,start+i*.104-time.monotonic()))
                        await ws.send(pack('<BIQ',1,1,0)+raw)
                    while not stop.is_set():await asyncio.sleep(.05)
                except websockets.ConnectionClosed:pass
            async with websockets.serve(upstream,'127.0.0.1',0,subprotocols=['foxglove.websocket.v1'],compression=None) as source:
                bridge=Bridge(engine,'ws://127.0.0.1:%d'%source.sockets[0].getsockname()[1])
                if getattr(self,'fit_site',False):
                    from live_ground import save_fit
                    fit_report['source']['upstream']=bridge.upstream
                    engine.install_ground(save_fit(fit_report,self.out/'offline_fit'),'MOCK_OFFLINE',bridge.upstream)
                async with websockets.serve(bridge.client,'127.0.0.1',0,subprotocols=['foxglove.websocket.v1'],compression=None,origins=[None]) as server:
                    state['url']='ws://127.0.0.1:%d'%server.sockets[0].getsockname()[1];ready.set()
                    tasks=[asyncio.create_task(bridge.receive()),asyncio.create_task(bridge.worker()),asyncio.create_task(bridge.body_worker())]
                    while not stop.is_set():await asyncio.sleep(.03)
                    bridge.stop.set()
                    for task in tasks:task.cancel()
                    await asyncio.gather(*tasks,return_exceptions=True)
                    bridge.close()
                    state['bridge']=bridge.summary()
        def serve():
            try:asyncio.run(scenario())
            except BaseException as exc:failures.append(repr(exc));ready.set()
        worker=threading.Thread(target=serve);worker.start()
        try:
            self.assertTrue(ready.wait(10));self.assertFalse(failures,failures)
            # 缺地面用例保持3D可见，覆盖目标框真实GPU管线；其余核对2D预览。
            view_args=[] if no_ground else ['--smoke-depth']
            duration='49000' if getattr(self,'long_window',False) else '6000'
            report=self.run_service(['--smoke','--smoke-live',state['url'],'--live-duration-ms',duration,
                '--screenshot',str(self.out/'window.png')]+view_args)
        finally:stop.set();worker.join(10)
        if 'bridge' in state:(self.out/'bridge.json').write_text(json.dumps(state['bridge'],ensure_ascii=False,indent=2),'utf8')
        self.assertFalse(worker.is_alive());self.assertFalse(failures,failures)
        unexpected=[r['message'] for r in report['log'] if r['eventType']=='nativeStderr'
                    and 'Layout polish loop detected' not in r['message']]
        self.assertEqual(unexpected,[])
        self.assertTrue(calls);self.assertTrue(all(c['op']=='subscribe' for c in calls))
        if tamper:
            self.assertTrue(any(r.get('eventType')=='liveStatus' and 'SHA mismatch' in r.get('message','') for r in report['log']))
            self.assertFalse(any(r['info']['targetCount'] for r in report['log'] if r['eventType']=='published'))
            return
        published=[r for r in report['log'] if r['eventType']=='published' and r['info']['mode']=='live']
        matched=[r for r in published if r['info'].get('depth')]
        measured=[r for r in matched if r['info']['targetCount']>0]
        self.assertGreaterEqual(len(published),25)
        self.assertGreaterEqual(len(matched),20)
        self.assertGreaterEqual(len(measured),15)
        if no_ground:
            self.assertTrue(all(r['info']['result']['heightMedianM'] is None for r in measured))
            self.assertTrue(all(r['info']['result']['groundAlert']['state']=='unavailable' for r in measured))
        if getattr(self,'fit_site',False):
            self.assertTrue(all(r['info']['result']['heightMedianM'] is not None for r in measured))
            last_measured=max(i for i,r in enumerate(report['log']) if r['eventType']=='published'
                              and r.get('info',{}).get('targetCount',0)>0)
            self.assertTrue(any(r['eventType']=='liveStatus' and r.get('clearTarget')
                and 'stale:' not in r.get('message','') for r in report['log'][last_measured+1:]),
                'current-epoch invalid heartbeat must clear Qt before the raw-cloud TTL')
        self.assertTrue(any(any(p['pointCount']>0 for p in (r['info']['result'].get('bodyCandidates') or {}).get('parts',[])) for r in measured))
        acks=[json.loads(r['command']) for r in report['log'] if r['eventType']=='command' and json.loads(r['command'])['op']=='ack']
        by_id={r['submissionId']:r for r in acks}
        for r in matched:
            info=r['info'];ack=by_id[r['submissionId']]
            self.assertEqual(info['depth']['previewSha256'],ack['depthSha256'])
            self.assertEqual(info['targetSha256'],ack['targetSha256'])
            self.assertFalse(info['confirmedEnabled'])
        self.assertEqual(report['jointMutationRequests'],0);self.assertEqual(report['directBoardCalls'],0)
        for name in ('LIVE_3D','LIVE_2D','LIVE_END'):
            probe=json.loads((self.out/(name+'.json')).read_text('utf8'))
            self.assertTrue(probe['screenshotSaved'])
        final=json.loads((self.out/'LIVE_END.json').read_text('utf8'))['snapshot']
        self.assertEqual(final.get('targetCount'),0)
        self.assertIsNone(final.get('result'))
        self.assertIsNone(final.get('depth'))
        (self.out/'bridge.json').write_text(json.dumps(state['bridge'],ensure_ascii=False,indent=2),'utf8')

    def test_local_result_with_wrong_wire_sha_is_rejected(self):
        self.tamper=True
        self.test_real_386_messages_local_tracking_depth_body_and_native_ack()

    def test_tracking_without_ground_keeps_low_posture_unavailable(self):
        self.no_ground=True
        self.test_real_386_messages_local_tracking_depth_body_and_native_ack()

    def test_ram_site_fit_loads_current_ground_through_native_rendering(self):
        self.fit_site=True
        self.test_real_386_messages_local_tracking_depth_body_and_native_ack()

    def test_long_render_window_records_disconnected_end_probe(self):
        self.long_window=True
        self.no_ground=True
        self.test_real_386_messages_local_tracking_depth_body_and_native_ack()


if __name__=='__main__':unittest.main()

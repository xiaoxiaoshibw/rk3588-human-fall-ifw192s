"""Loopback-only Foxglove adapter: read upstream raw clouds, run local algorithms.

Never forwards client commands upstream, writes ROS topics, records clouds or
changes a board service. Without a declared empty background it shows range only.
"""
import argparse
import asyncio
import json
import hashlib
from pathlib import Path
import struct
import time
from concurrent.futures import ProcessPoolExecutor
from urllib.parse import urlparse

import websockets

from live_engine import LiveEngine,memory_background,site_ground,parse_cloud,ROOT
from core.range_image import ScanGrid


def ros_text(value):
    raw=json.dumps(value,allow_nan=False,separators=(',',':')).encode()
    return struct.pack('<I',len(raw))+raw


class Bridge:
    def __init__(self,engine,upstream,ground_out=None,site_id=None):
        uri=urlparse(upstream)
        if uri.scheme not in ('ws','wss') or uri.username or uri.password:raise ValueError('invalid upstream URL')
        self.engine,self.upstream=engine,upstream
        self.engine.defer_body=True;self.body_pending=None;self.body_changed=asyncio.Event()
        self.body_overwritten=self.body_processed=0
        self.body_errors=0
        self.body_pool=ProcessPoolExecutor(max_workers=1) if engine.body else None
        self.clients={};self.pending=None;self.changed=asyncio.Event();self.stop=asyncio.Event()
        self.received=self.overwritten=self.client_overwritten=0;self.epoch=0;self.last_received=0.
        self.samples=[];self.error=None
        self.ground_out,self.site_id=ground_out,site_id
        self.fit_samples=[];self.fit_headers=[];self.fit_future=None;self.fit_report=None;self.fit_pool=None
        self.clear_pending=False;self.invalidate_pending=None;self.stale_cleared=False
        self.state_published=0
        self.client_ready=asyncio.Event()

    def publish(self,channel,payload):
        if channel==2:self.state_published+=1
        for client in list(self.clients.values()):
            for subscription,cid in list(client['subscriptions'].items()):
                if cid!=channel:continue
                packet=struct.pack('<BIQ',1,subscription,time.time_ns())+payload
                queue=client['queue']
                if queue.full():queue.get_nowait();self.client_overwritten+=1
                queue.put_nowait(packet)

    async def client(self,ws):
        client=dict(subscriptions={},queue=asyncio.Queue(4));self.clients[id(ws)]=client
        channels=[dict(id=1,topic='/innolidar_points',encoding='ros1',schemaName='sensor_msgs/PointCloud2',schema=''),
            dict(id=2,topic='/single_target_live/state',encoding='ros1',schemaName='std_msgs/String',schema='string data')]
        await ws.send(json.dumps(dict(op='advertise',channels=channels)))
        async def send():
            while True:await asyncio.wait_for(ws.send(await client['queue'].get()),2)
        task=asyncio.create_task(send())
        try:
            async for raw in ws:
                if not isinstance(raw,str):raise ValueError('read-only bridge does not accept publications')
                msg=json.loads(raw)
                if msg.get('op')=='subscribe':
                    if len(msg['subscriptions'])>8:raise ValueError('too many subscriptions')
                    for sub in msg['subscriptions']:
                        sid,cid=sub['id'],sub['channelId']
                        if type(sid)is not int or not 0<=sid<2**32 or cid not in (1,2):raise ValueError('invalid subscription')
                        if len(client['subscriptions'])>=8 and sid not in client['subscriptions']:raise ValueError('too many subscriptions')
                        client['subscriptions'][sid]=cid
                    if set(client['subscriptions'].values())=={1,2}:self.client_ready.set()
                elif msg.get('op')=='unsubscribe':
                    for sid in msg['subscriptionIds']:client['subscriptions'].pop(sid,None)
                else:raise ValueError('read-only bridge accepts subscriptions only')
        except (websockets.ConnectionClosed,ValueError,KeyError,TypeError):pass
        finally:
            self.clients.pop(id(ws),None);task.cancel()
            await asyncio.gather(task,return_exceptions=True)

    async def receive(self):
        while not self.stop.is_set():
            try:
                async with websockets.connect(self.upstream,subprotocols=['foxglove.websocket.v1'],max_size=33554432,
                                               max_queue=2,open_timeout=5,proxy=None) as ws:
                    subscribed=None
                    async for msg in ws:
                        if self.stop.is_set():break
                        if isinstance(msg,str):
                            event=json.loads(msg)
                            if event.get('op')=='advertise':
                                channel=next((c for c in event['channels'] if c['topic']=='/innolidar_points'),None)
                                if channel is not None and channel['id']!=subscribed:
                                    if channel.get('schemaName')!='sensor_msgs/PointCloud2' or channel.get('encoding')!='ros1':
                                        raise ValueError('upstream PointCloud2 schema mismatch')
                                    if subscribed is not None:raise ValueError('upstream channel changed; rebind required')
                                    subscribed=channel['id']
                                    await ws.send(json.dumps(dict(op='subscribe',subscriptions=[dict(id=1,channelId=subscribed)])))
                            elif event.get('op')=='unadvertise' and subscribed in event.get('channelIds',[]):
                                raise ValueError('upstream channel withdrawn')
                            continue
                        if len(msg)<13 or msg[0]!=1 or struct.unpack_from('<I',msg,1)[0]!=1:continue
                        raw=msg[13:];received=time.monotonic()
                        try:parse_cloud(raw)
                        except (ValueError,struct.error,UnicodeError) as exc:
                            self.epoch+=1;self.pending=self.body_pending=None
                            self.invalidate_pending='invalid_wire_requires_rebind';self.publish(2,ros_text(self.engine.invalid(str(exc))));continue
                        self.received+=1;self.last_received=received
                        self.stale_cleared=False
                        self.publish(1,raw)
                        if self.pending is not None:self.overwritten+=1
                        self.pending=(self.epoch,raw,received);self.changed.set()
                    if not self.stop.is_set():raise OSError('upstream connection closed')
            except (OSError,ValueError,websockets.WebSocketException,asyncio.TimeoutError) as exc:
                self.error=str(exc);self.epoch+=1;self.pending=None
                self.clear_pending=True
                self.publish(2,ros_text(self.engine.invalid('upstream_disconnected')))
                try:await asyncio.wait_for(self.stop.wait(),1)
                except asyncio.TimeoutError:pass

    async def worker(self):
        last_heartbeat=0.
        while not self.stop.is_set():
            try:await asyncio.wait_for(self.changed.wait(),.1)
            except asyncio.TimeoutError:pass
            self.changed.clear();item=self.pending;self.pending=None
            if self.invalidate_pending:
                self.engine.invalidate(self.invalidate_pending);self.invalidate_pending=None
            if self.clear_pending:
                self.engine.clear_history();self.body_pending=None;self.clear_pending=False
            if self.fit_future is not None and self.fit_future.done():
                from live_ground import save_fit
                self.fit_report=self.fit_future.result();self.fit_future=None
                path=save_fit(self.fit_report,self.ground_out)
                if path and not self.engine.disabled:
                    self.engine.install_ground(path,self.site_id,self.upstream)
                    self.fit_report['runtimeLoaded']=dict(afterSource=self.engine.previous,sha256=self.engine.runtime.ground_sha)
            if item is not None:
                epoch,raw,received=item
                result=await asyncio.to_thread(self.engine.process,raw,received)
                if epoch!=self.epoch:continue
                if self.clear_pending or self.invalidate_pending:continue
                if self.ground_out and self.fit_report is None and self.fit_future is None and result.get('source'):
                    from live_ground import FIT_FRAMES,HELD_FRAMES,fit_site
                    h=parse_cloud(raw).header
                    header=dict(seq=h.seq,sec=h.stamp.secs,nsec=h.stamp.nsecs,frame_id=h.frame_id,
                                wire_sha256=hashlib.sha256(raw).hexdigest())
                    if self.fit_headers and header['seq']!=self.fit_headers[-1]['seq']+1:
                        self.fit_report=dict(status='unavailable',reason='fit_source_discontinuous',headers=self.fit_headers)
                        from live_ground import save_fit
                        save_fit(self.fit_report,self.ground_out)
                        self.fit_samples=[]
                    else:
                        frame=self.engine.ground_frame
                        self.fit_samples.append(frame.xyz[frame.source_rows[frame.valid]].copy())
                        self.fit_headers.append(header)
                        if len(self.fit_samples)==FIT_FRAMES+HELD_FRAMES:
                            self.fit_pool=ProcessPoolExecutor(max_workers=1)
                            self.fit_future=asyncio.get_running_loop().run_in_executor(self.fit_pool,fit_site,
                                self.fit_samples,self.fit_headers,dict(siteId=self.site_id,frameId=self.engine.frame_id,
                                gridSha256=self.engine.grid.sha256),dict(upstream=self.upstream,identity=self.engine.identity))
                            self.fit_samples=[]
                self.publish(2,ros_text(result))
                if self.engine.body_job is not None and result.get('source'):
                    if self.body_pending is not None:self.body_overwritten+=1
                    self.body_pending=(epoch,self.engine.body_job,result,received);self.body_changed.set()
                source=result.get('source');bundle=result.get('local_range') or {}
                self.samples.append(dict(source=source,reason=result['acquisition']['reason'],
                    targetCount=len(result['target_source_rows']),trackId=result['track_id'],
                    bodyCounts={p['part']:len(p['sourceRows']) for p in (bundle.get('bodyCandidates') or {}).get('parts',[])},
                    groundAlert=(bundle.get('groundAlert') or {}).get('state'),performance=result.get('performance')))
                self.samples[-1].update(heightMedianM=bundle.get('heightMedianM'),ground=bundle.get('ground'),
                    fallState=result.get('fall_status'),groundAlertEvidence=bundle.get('groundAlert'),
                    fallEvidence=bundle.get('fallEvidence'),
                    groundAlertCandidate=bundle.get('groundAlertCandidate'),
                    targetRowsSha256=hashlib.sha256(json.dumps(result['target_source_rows']).encode()).hexdigest(),
                    wireSha256=bundle.get('wireSha256'),posture=bundle.get('posture'))
                if len(self.samples)>15000:self.samples.pop(0)
            now=time.monotonic()
            if now-self.last_received>.5 and now-last_heartbeat>.5:
                if not self.stale_cleared:
                    self.engine.clear_history();self.body_pending=None;self.stale_cleared=True
                self.publish(2,ros_text(self.engine.invalid('required_cloud_stale')));last_heartbeat=now

    async def body_worker(self):
        while not self.stop.is_set():
            await self.body_changed.wait();self.body_changed.clear()
            item=self.body_pending;self.body_pending=None
            if item is None:continue
            epoch,job,result,received=item
            if self.body_pool is None:continue
            try:body=await asyncio.get_running_loop().run_in_executor(self.body_pool,LiveEngine.make_body,job)
            except Exception:
                self.body_errors+=1;continue
            if epoch!=self.epoch or time.monotonic()-received>.35 or body is None:continue
            packet=dict(result,local_range=dict(result['local_range'],bodyCandidates=body))
            self.body_processed+=1;self.publish(2,ros_text(packet))
            for sample in reversed(self.samples):
                if sample['source']==packet['source']:
                    sample['bodyCounts']={p['part']:len(p['sourceRows']) for p in body['parts']}
                    sample['bodyAgeMs']=(time.monotonic()-received)*1000;break

    def close(self):
        if self.body_pool is not None:self.body_pool.shutdown(wait=True,cancel_futures=True)
        if self.fit_pool is not None:self.fit_pool.shutdown(wait=True,cancel_futures=True)

    def summary(self):
        return dict(schema='local_range_bridge/1',received=self.received,processed=self.engine.processed,
            pendingOverwritten=self.overwritten,clientOverwritten=self.client_overwritten,error=self.error,
            bodyProcessed=self.body_processed,bodyOverwritten=self.body_overwritten,
            bodyErrors=self.body_errors,
            statePublished=self.state_published,groundFit=self.fit_report,
            runtimeGround=self.engine.runtime.ground if self.engine.runtime else None,
            semantic='UNKNOWN',confirmedEnabled=False,rawCloudsRecorded=False,boardMutations=0,
            backgroundAvailable=self.engine.runtime is not None,samples=self.samples)


async def run(args):
    for destination in (args.ready,args.report):
        if destination:
            target=Path(destination).resolve()
            for protected in (ROOT/'data',ROOT/'captures'):
                p=protected.resolve()
                if target==p or p in target.parents:raise ValueError('diagnostics must be outside source data')
    tables=ROOT/'src/inno_lidar_ros/config/ifw192s'
    grid=ScanGrid.from_csv(tables/'ifw192s_azimuth_192x256.csv',tables/'ifw192s_elevation_192x256.csv')
    identity=background=None
    if bool(args.background_url)!=bool(args.background_manifest):raise ValueError('both background URL and manifest required')
    if args.background_url:identity,background=memory_background(args.background_url,args.background_manifest,grid)
    if args.declare_empty_prefix and background is not None:raise ValueError('choose frozen background or new declared prefix')
    engine=LiveEngine(grid,args.frame_id,identity,background,empty_prefix_frames=50 if args.declare_empty_prefix else None,body=args.body_candidates)
    if args.ground:
        if engine.runtime is None:raise ValueError('ground alerts require a declared background')
        engine.install_ground(args.ground,args.site_id,args.upstream)
    if args.fit_ground_out and (not args.site_id or engine.runtime is None or args.ground):
        raise ValueError('site fitting requires site id, declared background, and no preloaded ground')
    bridge=Bridge(engine,args.upstream,args.fit_ground_out,args.site_id)
    async with websockets.serve(bridge.client,'127.0.0.1',args.port,subprotocols=['foxglove.websocket.v1'],
                                compression=None,origins=[None],max_size=65536,max_queue=4) as server:
        port=server.sockets[0].getsockname()[1]
        ready=dict(url='ws://127.0.0.1:%d'%port,prefix='/single_target_live/',
                   background='declared_memory' if background else 'declared_next_50' if args.declare_empty_prefix else 'not_declared',ground=bool(args.ground))
        if args.ready:
            with Path(args.ready).open('x',encoding='utf8') as stream:json.dump(ready,stream)
        print(json.dumps(ready),flush=True)
        if args.wait_client:
            await asyncio.wait_for(bridge.client_ready.wait(),60)
        tasks=[asyncio.create_task(bridge.receive()),asyncio.create_task(bridge.worker()),asyncio.create_task(bridge.body_worker())]
        try:
            if args.duration:await asyncio.sleep(args.duration)
            else:await asyncio.Future()
        finally:
            bridge.stop.set()
            for task in tasks:task.cancel()
            await asyncio.gather(*tasks,return_exceptions=True)
            bridge.close()
            if args.report:
                with Path(args.report).open('x',encoding='utf8') as stream:json.dump(bridge.summary(),stream,ensure_ascii=False,indent=2)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--upstream',default='ws://192.168.31.58:8765');parser.add_argument('--frame-id',default='innolidar')
    parser.add_argument('--port',type=int,default=8952);parser.add_argument('--background-url');parser.add_argument('--background-manifest',type=Path)
    parser.add_argument('--ground',type=Path);parser.add_argument('--site-id');parser.add_argument('--body-candidates',action='store_true')
    parser.add_argument('--fit-ground-out',type=Path,help='one RAM-only site fit, derived evidence directory')
    parser.add_argument('--wait-client',action='store_true',help='start bounded upstream window only after Qt subscribes')
    parser.add_argument('--declare-empty-prefix',action='store_true',help='explicit declaration: the next 50 source frames are empty; do not use with a person present')
    parser.add_argument('--ready',type=Path);parser.add_argument('--report',type=Path);parser.add_argument('--duration',type=float)
    args=parser.parse_args(argv)
    if not 0<=args.port<=65535 or args.duration is not None and (not 0<args.duration<=86400):parser.error('invalid port/duration')
    try:asyncio.run(run(args))
    except KeyboardInterrupt:pass


if __name__=='__main__':main()

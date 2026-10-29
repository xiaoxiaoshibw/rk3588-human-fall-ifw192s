"""A slow local recorder and slower inference must not stall the full-rate scene."""
import base64
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import socketserver
import struct
import threading
import time
import unittest

import test_integration as fixtures


class TestLiveFlow(unittest.TestCase):
    setUp = fixtures.TestApp.setUp
    run_service = fixtures.TestApp.run_service

    def test_full_rate_clouds_survive_slow_inference_and_two_second_status(self):
        advertised_headers = []
        stale_only=getattr(self,'stale_only',False)
        class Foxglove(socketserver.BaseRequestHandler):
            def handle(self):
                try:
                    self.request.settimeout(8)
                    header = b''
                    while b'\r\n\r\n' not in header:
                        header += self.request.recv(8192)
                    advertised_headers.append(header.decode())
                    key = next(v.split(b':', 1)[1].strip() for v in header.split(b'\r\n') if v.lower().startswith(b'sec-websocket-key:'))
                    accept = base64.b64encode(hashlib.sha1(key+b'258EAFA5-E914-47DA-95CA-C5AB0DC85B11').digest())
                    self.request.sendall(b'HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: '+accept+b'\r\nSec-WebSocket-Protocol: foxglove.websocket.v1\r\n\r\n')
                    channels = [dict(id=1, topic='/innolidar_points', encoding='ros1', schemaName='sensor_msgs/PointCloud2'),
                                dict(id=2, topic='/single_target_live/state', encoding='ros1', schemaName='std_msgs/String')]
                    self.request.sendall(fixtures.ws_frame(1,json.dumps(dict(op='advertise',channels=channels)).encode()))
                    time.sleep(.1)
                    raw = struct.pack('<ffffId', 2., 0., .5, 10., 1, 100.)
                    start = time.monotonic()
                    for i in range(25):
                        time.sleep(max(0,start+i*.1-time.monotonic()))
                        sec, nsec = 100+i//10, (i%10)*100000000
                        meta = dict(sensor=dict(frame_id='lidar'), frames=[dict(stamp_sec=sec,stamp_nanosec=nsec,count_points=1)])
                        cloud = fixtures.cloud_message(raw,meta,0,seq=100+i)
                        def send(sid,payload):
                            self.request.sendall(fixtures.ws_frame(2,struct.pack('<BIQ',1,sid,0)+payload))
                        send(1,cloud)
                        if i >= 2 and (i-2) % 5 == 0:
                            # Inference completes two cloud intervals later.
                            result_index=i-2
                            result_sec,result_nsec=100+result_index//10,(result_index%10)*100000000
                            state = dict(schema_version=1,kind='target_state',session_id='paced',time_epoch=0,
                                         source=dict(seq=100+result_index,stamp_secs=result_sec,stamp_nsecs=result_nsec,frame_id='lidar'),
                                         target_mode='automatic',track_id=None,track_status='unselected',
                                         observability='valid',bbox_observed=False,position_predicted=False,
                                         target_source_rows=[],fall_status='unknown')
                            if stale_only:
                                state.update(source=None,observability='invalid',
                                    acquisition=dict(reason='required_cloud_stale'),
                                    sensor_quality=dict(cloud=dict(age_s=15000.)))
                            send(2,fixtures.text(json.dumps(state)))
                    time.sleep(3)
                except (OSError, StopIteration):
                    pass
        class SlowRecorder(BaseHTTPRequestHandler):
            def log_message(self,*args): pass
            def reply(self):
                payload=b'{"state":"idle"}'
                try:
                    self.send_response(200); self.send_header('Content-Length',str(len(payload))); self.end_headers(); self.wfile.write(payload)
                except (BrokenPipeError,ConnectionResetError): pass
            def do_GET(self):
                time.sleep(2)
                self.reply()
            def do_POST(self):
                self.rfile.read(int(self.headers.get('Content-Length',0)))
                self.reply()
        ws=socketserver.ThreadingTCPServer(('127.0.0.1',0),Foxglove); ws.daemon_threads=True
        joint=ThreadingHTTPServer(('127.0.0.1',0),SlowRecorder); joint.daemon_threads=True
        for server in (ws,joint): threading.Thread(target=server.serve_forever,daemon=True).start()
        try:
            report=self.run_service(['--smoke','--smoke-live',f'ws://127.0.0.1:{ws.server_address[1]}',
                                     '--joint-url',f'http://127.0.0.1:{joint.server_port}/','--smoke-joint',
                                     '--live-duration-ms','4300'])
            frames=[r for r in report['log'] if r['eventType']=='published' and r['info']['mode']=='live']
            indices={r['info']['frameIndex'] for r in frames}
            self.assertGreaterEqual(len(indices),23,sorted(indices))
            first = frames[0]['atMs']
            self.assertTrue(any(first+400<r['atMs']<first+1400 for r in frames),'Cloud dispatch stalled behind recorder HTTP')
            self.assertLess(max(b['atMs']-a['atMs'] for a,b in zip(frames,frames[1:])),350)
            matched={r['info']['frameIndex'] for r in frames if r['info'].get('result') is not None}
            self.assertEqual(matched,set() if stale_only else {100,105,110,115,120})
            if stale_only:
                diagnostic=next(r['info']['algorithmInput'] for r in frames if r['info'].get('algorithmInput'))
                self.assertEqual(diagnostic,dict(status='invalid',reason='required_cloud_stale',cloudAgeSec=15000.,
                    service=None,capabilityStatus='legacy_protocol_new_capabilities_unavailable'))
            self.assertEqual(max(r['info']['stream']['sequenceGaps'] for r in frames),0)
            self.assertTrue(any('permessage-deflate' in header for header in advertised_headers))
        finally:
            for server in (ws,joint): server.shutdown(); server.server_close()

    def test_stale_algorithm_input_is_visible_while_full_rate_clouds_continue(self):
        self.stale_only=True
        self.test_full_rate_clouds_survive_slow_inference_and_two_second_status()


if __name__ == '__main__': unittest.main()

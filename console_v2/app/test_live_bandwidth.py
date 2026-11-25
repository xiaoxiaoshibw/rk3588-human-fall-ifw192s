"""Bridge-side sampling must stop full clouds without stopping algorithm state."""
import base64
import hashlib
import json
import socketserver
import struct
import threading
import time
import unittest

import test_integration as fixtures


class TestLiveBandwidth(unittest.TestCase):
    setUp = fixtures.TestApp.setUp
    run_service = fixtures.TestApp.run_service

    def test_bridge_sampling_keeps_same_frame_results(self):
        commands = []
        class Bridge(socketserver.BaseRequestHandler):
            def handle(self):
                enabled = set()
                try:
                    self.request.settimeout(6)
                    header = b''
                    while b'\r\n\r\n' not in header:
                        header += self.request.recv(8192)
                    key = next(x.split(b':', 1)[1].strip() for x in header.split(b'\r\n') if x.lower().startswith(b'sec-websocket-key:'))
                    accept = base64.b64encode(hashlib.sha1(key+b'258EAFA5-E914-47DA-95CA-C5AB0DC85B11').digest())
                    self.request.sendall(b'HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Accept: '+accept+b'\r\nSec-WebSocket-Protocol: foxglove.websocket.v1\r\n\r\n')
                    channels = [dict(id=1, topic='/innolidar_points', encoding='ros1', schemaName='sensor_msgs/PointCloud2'),
                                dict(id=2, topic='/single_target_live/state', encoding='ros1', schemaName='std_msgs/String')]
                    self.request.sendall(fixtures.ws_frame(1, json.dumps(dict(op='advertise', channels=channels)).encode()))
                    def exact(n):
                        data = b''
                        while len(data) < n:
                            part = self.request.recv(n-len(data))
                            if not part:
                                raise OSError('closed')
                            data += part
                        return data
                    def read_commands():
                        try:
                            while True:
                                first = exact(2)
                                n = first[1] & 127
                                if n == 126:
                                    n = struct.unpack('>H', exact(2))[0]
                                elif n == 127:
                                    n = struct.unpack('>Q', exact(8))[0]
                                mask = exact(4)
                                body = bytes(v ^ mask[i % 4] for i, v in enumerate(exact(n)))
                                if first[0] & 15 != 1:
                                    continue
                                msg = json.loads(body)
                                commands.append(msg)
                                if msg['op'] == 'subscribe':
                                    enabled.update(x['id'] for x in msg['subscriptions'])
                                elif msg['op'] == 'unsubscribe':
                                    enabled.difference_update(msg['subscriptionIds'])
                        except (OSError, ValueError):
                            pass
                    reader = threading.Thread(target=read_commands, daemon=True)
                    reader.start()
                    def send(sid, payload):
                        self.request.sendall(fixtures.ws_frame(2, struct.pack('<BIQ', 1, sid, 0)+payload))
                    time.sleep(.15)
                    for i in range(32):
                        sec, nsec = 100+i//10, i % 10*100000000
                        if 1 in enabled:
                            meta = dict(sensor=dict(frame_id='lidar'), frames=[dict(stamp_sec=sec, stamp_nanosec=nsec, count_points=1)])
                            send(1, fixtures.cloud_message(struct.pack('<ffffId', 2., 0., .5, 10., 1, 100.), meta, 0, seq=100+i))
                        if 2 in enabled:
                            state = dict(schema_version=1, kind='target_state', session_id='sampled', time_epoch=0,
                                source=dict(seq=100+i, stamp_secs=sec, stamp_nsecs=nsec, frame_id='lidar'),
                                target_mode='automatic', track_id=None, track_status='unselected', observability='valid',
                                bbox_observed=False, position_predicted=False, target_source_rows=[], fall_status='unknown')
                            send(2, fixtures.text(json.dumps(state)))
                        time.sleep(.1)
                    time.sleep(1)
                except OSError:
                    pass
        server = socketserver.ThreadingTCPServer(('127.0.0.1', 0), Bridge)
        server.daemon_threads = True
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            report = self.run_service(['--smoke', '--smoke-live', f'ws://127.0.0.1:{server.server_address[1]}',
                '--smoke-point-interval-ms', '250', '--live-duration-ms', '4000'])
            frames = [r['info'] for r in report['log'] if r['eventType'] == 'published' and r['info']['mode'] == 'live']
            self.assertGreaterEqual(len(frames), 7)
            self.assertLessEqual(len(frames), 13)
            self.assertTrue(all(f['stream']['pointIntervalMs'] == 250 for f in frames))
            self.assertGreaterEqual(sum(f.get('result') is not None for f in frames), 7)
            unsubs = [c['subscriptionIds'] for c in commands if c['op'] == 'unsubscribe']
            self.assertGreaterEqual(len(unsubs), 7)
            self.assertTrue(all(ids == [1] for ids in unsubs), unsubs)
        finally:
            server.shutdown()
            server.server_close()

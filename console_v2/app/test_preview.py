"""Continuous preview against a loopback camera, including duplicate images/stalls."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
from pathlib import Path
import subprocess
import sys
import threading
import time
import unittest
from unittest import mock

from PIL import Image
import test_integration as fixtures

sys.path.insert(0, str(fixtures.ROOT / 'pc_apps/console'))
import joint_capture as joint


class PreviewHeaders(unittest.TestCase):
    def test_preview_configuration_uses_requested_url_without_starting_recording(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(joint.Recorder, '_preview_pump', lambda self: None):
            recorder = joint.Recorder(Path(tmp)/'unused')
            try:
                recorder.latest = b'old'
                status = recorder.configure_preview({'camera_url': 'http://127.0.0.1:1234/stream'})
                self.assertEqual(status['camera_url'], 'http://127.0.0.1:1234/stream')
                self.assertEqual(status['state'], 'idle')
                self.assertIsNone(recorder.latest)
                self.assertFalse((Path(tmp)/'unused').exists())
                with self.assertRaises(ValueError): recorder.configure_preview({'camera_url': 'file:///tmp/camera'})
                recorder.thread = mock.Mock();recorder.thread.is_alive.return_value = True
                with self.assertRaises(ValueError): recorder.configure_preview({'camera_url': 'http://127.0.0.1:2/stream'})
                recorder.thread = None
            finally:
                recorder.close()

    def test_same_sequence_is_204_but_identical_new_source_frame_is_fresh(self):
        import tempfile
        import urllib.request
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(joint.Recorder, '_preview_pump', lambda self: None):
            server, recorder = joint.start_server(Path(tmp)/'unused', Path(joint.__file__).with_name('joint_capture.html'))
            try:
                recorder.data['camera_url'] = 'http://127.0.0.1:1/stream'
                with recorder.lock:
                    recorder._set_latest(b'same-jpeg-bytes')
                base = 'http://127.0.0.1:%d/api/preview' % server.server_port
                with urllib.request.urlopen(base) as response:
                    self.assertEqual(response.read(), b'same-jpeg-bytes')
                    self.assertEqual(response.headers['X-Preview-Sequence'], '1')
                with urllib.request.urlopen(base+'?after=1') as response:
                    self.assertEqual(response.status, 204)
                    self.assertEqual(response.read(), b'')
                with recorder.lock:
                    recorder._set_latest(b'same-jpeg-bytes')
                    recorder.preview_received_s = time.monotonic()-2
                with urllib.request.urlopen(base+'?after=1') as response:
                    self.assertEqual(response.status, 200)
                    self.assertEqual(response.headers['X-Preview-Sequence'], '2')
                    self.assertGreaterEqual(float(response.headers['X-Preview-Age-Ms']), 1999)
                self.assertFalse((Path(tmp)/'unused').exists())
            finally:
                recorder.close();server.shutdown();server.server_close()


class TestContinuousPreview(unittest.TestCase):
    setUp = fixtures.TestApp.setUp

    def run_preview(self, stale):
        output = io.BytesIO()
        Image.new('RGB',(320,180),(35,120,180)).save(output,'JPEG')
        jpeg = output.getvalue()
        done_event = threading.Event()
        state = {'connections':0, 'first':None}
        class Camera(BaseHTTPRequestHandler):
            def log_message(self,*args): pass
            def do_GET(self):
                state['connections'] += 1
                if state['first'] is None: state['first']=time.monotonic()
                try:
                    self.send_response(200)
                    self.send_header('Content-Type','multipart/x-mixed-replace; boundary=frame')
                    self.end_headers()
                    while not done_event.wait(.1):
                        if stale and time.monotonic()-state['first']>2: continue
                        self.wfile.write(b'--frame\r\nContent-Type: image/jpeg\r\n\r\n'+jpeg+b'\r\n')
                        self.wfile.flush()
                except OSError: pass
        camera=ThreadingHTTPServer(('127.0.0.1',0),Camera)
        threading.Thread(target=camera.serve_forever,daemon=True).start()
        server,recorder=joint.start_server(self.out/'never_created',Path(joint.__file__).with_name('joint_capture.html'))
        recorder.data['camera_url']='http://127.0.0.1:%d/stream'%camera.server_port
        args=[str(fixtures.SDK),str(fixtures.DLL),'--session',str(fixtures.SESSION),'--host',str(fixtures.HOST),
              '--report',str(self.out/'run.json'),'--joint-url','http://127.0.0.1:%d/'%server.server_port,
              '--preview-report',str(self.out/'preview.json')]
        if stale: args+=['--preview-stale']
        try:
            result=subprocess.run(args,cwd=fixtures.ROOT,capture_output=True,timeout=30)
            (self.out/'stdout.txt').write_bytes(result.stdout);(self.out/'stderr.txt').write_bytes(result.stderr)
            self.assertEqual(result.returncode,0,result.stderr.decode(errors='replace'))
            report=json.loads((self.out/'preview.json').read_text(encoding='utf8'))
            self.assertEqual(report['status'],'PASS',report)
            if not stale:
                self.assertGreaterEqual(report['checks'][0]['previewFps'],8)
                self.assertEqual(state['connections'],1,'Preview opened duplicate upstream streams')
            service=json.loads((self.out/'run.json').read_text(encoding='utf8'))
            self.assertEqual(service['jointMutationRequests'],0)
            self.assertEqual(recorder.status()['state'],'idle')
            self.assertFalse((self.out/'never_created').exists())
        finally:
            done_event.set();recorder.close();server.shutdown();server.server_close()
            camera.shutdown();camera.server_close()

    def test_continuous_static_camera_at_ten_fps_while_point_cloud_plays(self):
        self.run_preview(False)

    def test_stalled_camera_is_hidden_and_collapsing_stops_preview(self):
        self.run_preview(True)


if __name__=='__main__': unittest.main()

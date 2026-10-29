"""Local fault injection only; all artifacts live in TemporaryDirectory."""
import json
import os
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../scripts'))
import capture_server
from core.fifo import FifoCleaner
from core.recorder import Recorder, RecordError
from core.session_store import SessionStore


class CaptureLifecycle(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.cfg = dict(capture_server.DEFAULT_CONFIG, staging_dir=self.tmp.name,
                        sessions_db=os.path.join(self.tmp.name, 'sessions.json'),
                        fifo_keep=0, disk_floor_mb=0, fifo_interval_sec=600)
        self.store = SessionStore(self.cfg['sessions_db'])

    def test_fifo_removes_extracted_and_active_bag(self):
        sid = 'cap_fault'
        self.store.upsert(dict(session_id=sid, state='failed', created_iso='2026'))
        folder = os.path.join(self.tmp.name, sid)
        os.mkdir(folder)
        for path in [os.path.join(folder, n) for n in ('points.bin', 'meta.json')] + [
                os.path.join(self.tmp.name, sid+s) for s in
                ('.bag', '.bag.active', '.manifest.json', '.reserve')]:
            with open(path, 'wb') as f:
                f.write(b'artifact')
        self.assertTrue(FifoCleaner(self.store, self.cfg).run_once())
        self.assertFalse(os.path.exists(folder))
        self.assertFalse(os.path.exists(os.path.join(self.tmp.name, sid+'.bag.active')))

    def test_popen_failure_is_terminal_and_retryable(self):
        rec = Recorder(self.store, self.cfg)
        with patch('core.recorder.subprocess.Popen', side_effect=OSError('injected')):
            with self.assertRaises(RecordError):
                rec.start('cap_spawn')
        self.assertFalse(rec.is_recording())
        self.assertEqual(self.store.get('cap_spawn')['state'], 'failed')

    def test_close_stops_recorder(self):
        server = capture_server._Server(('127.0.0.1', 0), capture_server._Handler, self.cfg)
        with patch.object(server.recorder, 'close', create=True) as close:
            server.server_close()
            close.assert_called_once()

    def test_delete_extracting_is_busy_and_keeps_files(self):
        server = capture_server._Server(('127.0.0.1', 0), capture_server._Handler, self.cfg)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            server.store.upsert(dict(session_id='cap_extract', state='extracting', created_iso='2026'))
            req = urllib.request.Request('http://127.0.0.1:%d/api/v1/sessions/cap_extract' %
                                         server.server_port, method='DELETE')
            try:
                with urllib.request.urlopen(req) as response:
                    status = response.status
            except urllib.error.HTTPError as exc:
                status = exc.code
                exc.close()
            self.assertEqual(status, 409)
            self.assertEqual(server.store.get('cap_extract')['state'], 'extracting')
        finally:
            server.shutdown()
            server.server_close()
            thread.join(3)


if __name__ == '__main__':
    unittest.main()

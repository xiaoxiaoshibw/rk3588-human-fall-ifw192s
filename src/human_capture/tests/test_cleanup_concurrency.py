"""Deterministic interleavings; disposable files only."""
import os
import sys
import threading
import http.client
import subprocess
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(__file__))
import test_capture_lifecycle as lifecycle
from core.fifo import FifoCleaner
from core.fifo import remove_session_artifacts
from core.recorder import RecordError, Recorder
import capture_server


class CleanupConcurrency(unittest.TestCase):
    setUp = lifecycle.CaptureLifecycle.setUp
    def seed(self):
        sid = 'cap_concurrent'
        self.store.upsert(dict(session_id=sid, state='ready', created_iso='2026'))
        path = os.path.join(self.tmp.name, sid + '.bag')
        with open(path, 'wb') as fh:
            fh.write(b'disposable')
        return sid, path

    def test_extraction_wins_after_fifo_snapshot(self):
        sid, path = self.seed()
        cleaner = FifoCleaner(self.store, self.cfg)
        original = cleaner._pick_oldest_by_priority
        snapshot = threading.Event()
        resume = threading.Event()
        result = []
        def pick(rows):
            snapshot.set()
            self.assertTrue(resume.wait(3))
            return original(rows)
        with patch.object(cleaner, '_pick_oldest_by_priority', side_effect=pick):
            thread = threading.Thread(target=lambda: result.append(cleaner.run_once()))
            thread.start()
            self.assertTrue(snapshot.wait(3))
            self.assertTrue(self.store.transition(sid, 'extracting')[0])
            resume.set()
            thread.join(3)
        self.assertFalse(thread.is_alive())
        self.assertEqual(result, [False])
        self.assertTrue(os.path.exists(path))
        self.assertEqual(self.store.get(sid)['state'], 'extracting')

    def test_cleanup_wins_before_state_transition(self):
        for state in ('extracting', 'transferring'):
            with self.subTest(state=state):
                sid, path = self.seed()
                entered, resume, requested, done = [threading.Event() for _ in range(4)]
                original = os.unlink
                outcomes = []
                def unlink(name, *args, **kwargs):
                    if name == path:
                        entered.set()
                        self.assertTrue(resume.wait(3))
                    return original(name, *args, **kwargs)
                def migrate():
                    requested.set()
                    outcomes.append(self.store.transition(sid, state))
                    done.set()
                with patch('core.fifo.os.unlink', side_effect=unlink):
                    cleaner = threading.Thread(target=FifoCleaner(self.store, self.cfg).run_once)
                    cleaner.start()
                    self.assertTrue(entered.wait(3))
                    worker = threading.Thread(target=migrate)
                    worker.start()
                    self.assertTrue(requested.wait(3))
                    try:
                        self.assertFalse(done.wait(.05), 'transition escaped cleanup ownership')
                    finally:
                        resume.set()
                        cleaner.join(3)
                        worker.join(3)
                self.assertFalse(cleaner.is_alive() or worker.is_alive())
                self.assertFalse(outcomes[0][0])
                self.assertEqual(self.store.get(sid)['state'], 'purged')
                # New independent temporary session for the next subcase.
                self.store.delete(sid)

    def test_partial_failure_keeps_retryable_registration(self):
        sid, path = self.seed()
        folder = os.path.join(self.tmp.name, sid)
        os.mkdir(folder)
        points = os.path.join(folder, 'points.bin')
        with open(points, 'wb') as fh:
            fh.write(b'disposable')
        original = os.unlink
        def fail(name, *args, **kwargs):
            if name == points:
                raise PermissionError('injected points failure')
            return original(name, *args, **kwargs)
        with patch('core.fifo.os.unlink', side_effect=fail):
            self.assertFalse(FifoCleaner(self.store, self.cfg).run_once())
        self.assertFalse(os.path.exists(path))
        self.assertTrue(os.path.exists(points))
        self.assertIsNotNone(self.store.get(sid))
        self.assertFalse(self.store.transition(sid, 'extracting')[0])
        retry_cfg = dict(self.cfg, fifo_keep=100)
        self.assertTrue(FifoCleaner(self.store, retry_cfg).run_once())
        self.assertFalse(FifoCleaner(self.store, self.cfg).run_once())
        self.assertEqual(self.store.get(sid)['state'], 'purged')

    def test_recorder_error_still_closes_real_threads_and_socket(self):
        server = capture_server._Server(('127.0.0.1', 0), capture_server._Handler, self.cfg)
        try:
            with patch.object(server.recorder, 'close', side_effect=RecordError('recorder_shutdown_timeout')):
                with self.assertRaisesRegex(RecordError, 'recorder_shutdown_timeout'):
                    server.server_close()
            self.assertEqual(server.socket.fileno(), -1)
            self.assertFalse(server.fifo._thread.is_alive())
            self.assertFalse(server._extract_thread.is_alive())
            server.server_close()
        finally:
            server.server_close()

    def test_later_error_preserves_first_and_closes_socket(self):
        server = capture_server._Server(('127.0.0.1', 0), capture_server._Handler, self.cfg)
        real_stop = server.fifo.stop
        def stop():
            real_stop()
            raise RuntimeError('fifo_cleanup_error')
        try:
            with patch.object(server.recorder, 'close', side_effect=RecordError('original_recorder_error')), patch.object(server.fifo, 'stop', side_effect=stop):
                with self.assertRaisesRegex(RecordError, 'original_recorder_error'):
                    server.server_close()
            self.assertEqual(server.socket.fileno(), -1)
            self.assertFalse(server._extract_thread.is_alive())
            self.assertFalse(server.fifo._thread.is_alive())
        finally:
            server.server_close()

    def http_server(self):
        server = capture_server._Server(('127.0.0.1', 0), capture_server._Handler, self.cfg)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        def finish():
            server.shutdown()
            server.server_close()
            thread.join(3)
        self.addCleanup(finish)
        return server

    def request(self, server, method, path, body=None):
        conn = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=5)
        try:
            data = None if body is None else json.dumps(body).encode('utf8')
            conn.request(method, '/api/v1/sessions/'+path, body=data,
                         headers={} if data is None else {'Content-Type':'application/json'})
            response = conn.getresponse()
            return response.status, response.read()
        finally:
            conn.close()

    def test_delete_state_interleaving_uses_same_owner(self):
        sid, path = self.seed()
        server = self.http_server()
        entered, resume = threading.Event(), threading.Event()
        original = os.unlink
        result = []
        def unlink(name, *args, **kwargs):
            if name == path:
                entered.set()
                self.assertTrue(resume.wait(3))
            return original(name, *args, **kwargs)
        with patch('core.fifo.os.unlink', side_effect=unlink):
            deleting = threading.Thread(target=lambda: result.append(self.request(server, 'DELETE', sid)))
            deleting.start()
            self.assertTrue(entered.wait(3))
            migrated = []
            migrating = threading.Thread(target=lambda: migrated.append(self.store.transition(sid, 'extracting')))
            migrating.start()
            resume.set()
            deleting.join(3)
            migrating.join(3)
        self.assertEqual(result[0][0], 200)
        self.assertFalse(migrated[0][0])
        self.assertIsNone(self.store.get(sid))
        self.assertEqual(self.request(server, 'DELETE', sid)[0], 404)

    def test_stream_owns_files_until_complete(self):
        sid, _ = self.seed()
        folder = os.path.join(self.tmp.name, sid)
        os.mkdir(folder)
        payload = b'disposable download'
        with open(os.path.join(folder, 'points.bin'), 'wb') as fh:
            fh.write(payload)
        server = self.http_server()
        entered, resume, cleaned = [threading.Event() for _ in range(3)]
        original = capture_server._Handler._serve_session_file_locked
        results = []
        def serving(handler, *args):
            entered.set()
            self.assertTrue(resume.wait(3))
            return original(handler, *args)
        with patch.object(capture_server._Handler, '_serve_session_file_locked', serving):
            download = threading.Thread(target=lambda: results.append(self.request(server, 'GET', sid+'/files/points.bin')))
            download.start()
            self.assertTrue(entered.wait(3))
            def cleanup():
                FifoCleaner(self.store, self.cfg).run_once()
                cleaned.set()
            cleaner = threading.Thread(target=cleanup)
            cleaner.start()
            try:
                self.assertFalse(cleaned.wait(.05))
            finally:
                resume.set()
                download.join(3)
                cleaner.join(3)
        self.assertEqual(results, [(200, payload)])
        self.assertEqual(self.store.get(sid)['state'], 'purged')

    def test_redirected_directory_is_refused_before_any_unlink(self):
        sid, bag = self.seed()
        target = os.path.join(self.tmp.name, 'separate_target')
        os.mkdir(target)
        file_path = os.path.join(target, 'points.bin')
        with open(file_path, 'wb') as fh:
            fh.write(b'disposable must survive')
        link = os.path.join(self.tmp.name, sid)
        if os.name == 'nt':
            import _winapi
            _winapi.CreateJunction(target, link)
        else:
            os.symlink(target, link, target_is_directory=True)
        self.assertFalse(FifoCleaner(self.store, self.cfg).run_once())
        self.assertTrue(os.path.exists(bag))
        self.assertTrue(os.path.exists(file_path))

    def test_process_transition_serializes_with_cleanup(self):
        sid, path = self.seed()
        entered, resume = threading.Event(), threading.Event()
        original = os.unlink
        def unlink(name, *args, **kwargs):
            if name == path:
                entered.set()
                self.assertTrue(resume.wait(5))
            return original(name, *args, **kwargs)
        code = ('import sys; sys.path.insert(0, sys.argv[1]); from core.session_store import SessionStore; '
                's=SessionStore(sys.argv[2]); print("requesting", flush=True); '
                'print(s.transition(sys.argv[3], "extracting"), flush=True)')
        with patch('core.fifo.os.unlink', side_effect=unlink):
            cleaner = threading.Thread(target=FifoCleaner(self.store, self.cfg).run_once)
            cleaner.start()
            self.assertTrue(entered.wait(3))
            process = subprocess.Popen([sys.executable, '-B', '-W', 'error', '-c', code,
                os.path.abspath(os.path.join(os.path.dirname(__file__), '..')), self.cfg['sessions_db'], sid],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                self.assertEqual(process.stdout.readline().strip(), 'requesting')
                self.assertIsNone(process.poll())
            finally:
                resume.set()
                cleaner.join(3)
            output, error = process.communicate(timeout=5)
        self.assertEqual(process.returncode, 0, error)
        self.assertIn('False', output)

    def test_real_watcher_timeout_and_repeat_close(self):
        server = capture_server._Server(('127.0.0.1', 0), capture_server._Handler, self.cfg)
        recorder = server.recorder
        entered, release = threading.Event(), threading.Event()
        def watch(rec):
            entered.set()
            release.wait(3)
            with recorder._lock:
                recorder._current = None
        with patch('core.recorder.subprocess.Popen', return_value=SimpleNamespace()), patch.object(recorder, '_watch_owned', side_effect=watch), patch('core.recorder._kill_pg'):
            recorder.start('cap_watch')
            self.assertTrue(entered.wait(3))
            real_join = recorder._watcher.join
            try:
                with patch.object(recorder._watcher, 'join', side_effect=lambda timeout: real_join(0)):
                    with self.assertRaisesRegex(RecordError, 'recorder_shutdown_timeout'):
                        server.server_close()
                    self.assertTrue(recorder._watcher.is_alive())
                    self.assertTrue(server.shutdown_state['recorder_watcher_alive'])
                    self.assertTrue(server.shutdown_state['socket_closed'])
                    self.assertFalse(server.shutdown_state['extractor_alive'])
                    self.assertFalse(server.shutdown_state['fifo_alive'])
            finally:
                release.set()
                real_join(3)
            server.server_close()
            self.assertFalse(recorder._watcher.is_alive())
            with self.assertRaisesRegex(RecordError, 'recorder_closed'):
                recorder.start('cap_after_close')

    def test_live_extractor_timeout_reports_alive_and_still_closes_socket(self):
        server = self.http_server()
        sid = 'cap_extract_live'
        bag = os.path.join(self.tmp.name, sid+'.bag')
        with open(bag, 'wb') as fh:
            fh.write(b'disposable')
        server.store.upsert(dict(session_id=sid, state='extracting', created_iso='2026', bag_path=bag))
        entered, release = threading.Event(), threading.Event()
        def extracting(*args):
            entered.set()
            self.assertTrue(release.wait(5))
            return dict(frames=[], total_points=0)
        with patch.object(capture_server, 'extract', side_effect=extracting):
            try:
                self.assertTrue(entered.wait(3))
                self.assertEqual(self.request(server, 'DELETE', sid)[0], 409)
                real_join = server._extract_thread.join
                with patch.object(server._extract_thread, 'join', side_effect=lambda timeout: real_join(0)):
                    with self.assertRaisesRegex(RuntimeError, 'extractor_shutdown_timeout'):
                        server.server_close()
                self.assertTrue(server.shutdown_state['extractor_alive'])
                self.assertTrue(server.shutdown_state['socket_closed'])
                self.assertFalse(server.shutdown_state['fifo_alive'])
            finally:
                release.set()
                server._extract_thread.join(3)
        server.server_close()
        self.assertFalse(server.shutdown_state['extractor_alive'])

    def test_fifo_error_alone_preserves_error_and_closes_other_resources(self):
        server = self.http_server()
        real_stop = server.fifo.stop
        def stop():
            real_stop()
            raise RuntimeError('fifo_cleanup_error')
        with patch.object(server.fifo, 'stop', side_effect=stop):
            with self.assertRaisesRegex(RuntimeError, 'fifo_cleanup_error'):
                server.server_close()
        self.assertTrue(server.shutdown_state['socket_closed'])
        self.assertFalse(server.shutdown_state['extractor_alive'])
        self.assertFalse(server.shutdown_state['fifo_alive'])

    def test_normal_close_reaps_actual_recorder_watcher(self):
        recorder = Recorder(self.store, self.cfg)
        with patch('core.recorder.subprocess.Popen', return_value=SimpleNamespace(poll=lambda: 0)), patch('core.recorder._kill_pg'):
            recorder.start('cap_normal_close')
            recorder.close()
        self.assertFalse(recorder._watcher.is_alive())
        self.assertIsNone(recorder.current_session_id())
        recorder.close()

    def test_delete_failure_is_500_and_registration_survives(self):
        sid, path = self.seed()
        server = self.http_server()
        real_unlink = os.unlink
        def fail(name, *args, **kwargs):
            if name == path:
                raise PermissionError('injected')
            return real_unlink(name, *args, **kwargs)
        with patch('core.fifo.os.unlink', side_effect=fail):
            self.assertEqual(self.request(server, 'DELETE', sid)[0], 500)
        self.assertTrue(server.store.get(sid)['cleanup_pending'])
        self.assertFalse(server.store.transition(sid, 'transferring')[0])
        self.assertEqual(self.request(server, 'DELETE', sid)[0], 200)

    def test_metadata_routes_cannot_bypass_cleanup_protocol(self):
        sid, path = self.seed()
        server = self.http_server()
        self.assertEqual(self.request(server, 'PATCH', sid, {'state':'purged'})[0], 409)
        self.assertEqual(self.request(server, 'POST', '', dict(session_id=sid, state='purged', created_iso='2026'))[0], 409)
        self.assertEqual(self.request(server, 'POST', '', dict(session_id='cap_new_purged', state='purged', created_iso='2026'))[0], 409)
        self.assertEqual(self.request(server, 'POST', '', dict(session_id='cap_injected', state='ready', created_iso='2026', cleanup_pending=True))[0], 409)
        self.assertEqual(server.store.get(sid)['state'], 'ready')
        self.assertTrue(os.path.exists(path))

    def test_spawn_to_watcher_has_no_unowned_recording_window(self):
        recorder = Recorder(self.store, self.cfg)
        spawning, spawn_done, watching, release, migrated = [threading.Event() for _ in range(5)]
        result = []
        def spawn(*args, **kwargs):
            spawning.set()
            self.assertTrue(spawn_done.wait(3))
            return SimpleNamespace(poll=lambda: 0)
        def watch(rec):
            watching.set()
            release.wait(3)
            with recorder._lock:
                recorder._current = None
        def migrate():
            result.append(self.store.transition('cap_handoff', 'failed'))
            migrated.set()
        with patch('core.recorder.subprocess.Popen', side_effect=spawn), patch.object(recorder, '_watch_owned', side_effect=watch):
            starting = threading.Thread(target=lambda: recorder.start('cap_handoff'))
            starting.start()
            self.assertTrue(spawning.wait(3))
            changing = threading.Thread(target=migrate)
            changing.start()
            try:
                self.assertFalse(migrated.wait(.05))
                spawn_done.set()
                self.assertTrue(watching.wait(3))
                self.assertFalse(migrated.wait(.05))
            finally:
                spawn_done.set()
                release.set()
                starting.join(3)
                changing.join(3)
                recorder.close()
        self.assertTrue(result[0][0])

    def test_failed_delete_of_legacy_purged_row_is_fifo_retryable(self):
        sid, path = self.seed()
        # Model a legacy purged registry row whose file was left behind.
        self.store.transition(sid, 'purged')
        server = self.http_server()
        original = os.unlink
        def fail(name, *args, **kwargs):
            if name == path:
                raise PermissionError('injected')
            return original(name, *args, **kwargs)
        with patch('core.fifo.os.unlink', side_effect=fail):
            self.assertEqual(self.request(server, 'DELETE', sid)[0], 500)
        self.assertTrue(self.store.get(sid)['cleanup_pending'])
        self.assertTrue(FifoCleaner(self.store, dict(self.cfg, fifo_keep=100)).run_once())
        self.assertFalse(os.path.exists(path))
        self.assertFalse(self.store.get(sid)['cleanup_pending'])

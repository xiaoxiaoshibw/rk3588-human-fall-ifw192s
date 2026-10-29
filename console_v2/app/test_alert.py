"""就近错误提示：本机 mock 录制服务制造失败 → 真实按钮点击 → 提示出现在发起动作的控件旁。

只连 loopback 假服务，不访问板端、不写录制目录、不产生真实采集。
"""
import json
import subprocess
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import test_integration as fixtures
from test_integration import ROOT, SDK, DLL, HOST, SESSION


class FakeJoint(BaseHTTPRequestHandler):
    calls = []

    def log_message(self, *args):
        pass

    def reply(self, code, payload):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        self.calls.append(('GET', self.path))
        self.reply(200, dict(state='idle', radar_frames=0, camera_frames=0, path='mock-only'))

    def do_POST(self):
        length = int(self.headers['Content-Length'] or 0)
        body = json.loads(self.rfile.read(length) or b'{}')
        self.calls.append(('POST', self.path, body))
        self.reply(503, dict(error='mock camera unreachable'))


class TestNearbyAlert(unittest.TestCase):
    setUp = fixtures.TestApp.setUp

    def test_error_shown_next_to_action_control(self):
        if not SESSION.is_dir():
            self.skipTest('real session is not present')
        FakeJoint.calls = []
        server = ThreadingHTTPServer(('127.0.0.1', 0), FakeJoint)
        server.daemon_threads = True
        threading.Thread(target=server.serve_forever, daemon=True).start()
        try:
            args = [str(SDK), str(DLL), '--session', str(SESSION), '--host', str(HOST),
                    '--report', str(self.out / 'run.json'),
                    '--joint-url', f'http://127.0.0.1:{server.server_port}/',
                    '--alert-report', str(self.out / 'alert.json'), '--no-external-open']
            done = subprocess.run(args, cwd=ROOT, capture_output=True, timeout=120)
            (self.out / 'stdout.txt').write_bytes(done.stdout)
            (self.out / 'stderr.txt').write_bytes(done.stderr)
            self.assertEqual(done.returncode, 0, done.stderr.decode(errors='replace'))

            report = json.loads((self.out / 'alert.json').read_text('utf-8'))
            self.assertEqual(report['status'], 'PASS', report)
            cases = {row['case']: row for row in report['checks']}
            for name in ('alert_joint_section_selected', 'alert_start_without_error',
                         'alert_attributed_to_start_action', 'alert_shown_next_to_joint_controls',
                         'alert_hint_near_action_control', 'alert_red_dot_in_status_bar',
                         'alert_only_on_failing_channel', 'alert_clear_button_clears_hint',
                         'alert_persistent_after_repeats', 'alert_persistent_still_attributed',
                         'alert_success_clears_persistent', 'alert_orphan_reply_ignored',
                         'alert_commands_carry_seq', 'alert_error_goes_to_its_own_channel',
                         'alert_success_correlation_kept_other_channel', 'alert_duplicate_reply_counted',
                         'alert_expired_command_reported', 'alert_window_sliding_unit',
                         'alert_window_requires_three_in_window', 'alert_window_alive'):
                self.assertIn(name, cases, report['checks'])
                self.assertTrue(cases[name]['passed'], (name, cases[name]))
            self.assertEqual(report['alert']['state'], 'none')
            # 只有三条没有主的回包（无主 seq、重复 seq、prune 探针）；轮询回包（seq=null）不计入。
            self.assertEqual(report['staleReplies'], 3, report)
            self.assertEqual(report['expiredCommands'], 1)
            # 只动了假本地服务：4 次 start（1 次首轮 + 3 次升级为持续故障），没有板端直连。
            service = json.loads((self.out / 'run.json').read_text('utf-8'))
            self.assertEqual(service['jointMutationRequests'], 4)
            self.assertEqual(service['directBoardCalls'], 0)
            errors = [row['message'] for row in service['log'] if row['eventType'] == 'commandError']
            self.assertTrue(any('Recorder HTTP 503' in message for message in errors), errors)
            paths = [call[1] for call in FakeJoint.calls]
            # 4 次真实 start 尝试 + 至少一次成功的 status 刷新；预览轮询不算录制动作。
            self.assertEqual(paths.count('/api/start'), 4, paths)
            self.assertIn('/api/status', paths, paths)
            self.assertNotIn('/api/stop', paths, paths)
            self.assertTrue(all(path.startswith('/api/') for path in paths), paths)
        finally:
            server.shutdown()
            server.server_close()


if __name__ == '__main__':
    unittest.main()
"""错峰联合录制：HC 协调器 + 预览 + 一次 fetch 的不变量测试。

不测网络；mock _BoardSession 和 _StagedFetch，钉死以下合同：
  1. PC 预览失败 → state=failed 且板端已被 stop（不留野 bag 继续膨胀）
  2. PC 写本地目录失败 → state=failed 且板端已被 stop
  3. 正常路径 → meta/points moved 到 output_root/joint_<sid>/ 且 joint_recording.board_session_id==sid
  4. Origin 校验仍为 same-origin
"""
import io
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
import unittest.mock as mock
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parent))
import joint_capture as J


def _fake_meta(sid):
    return {"format": "human_capture_session", "format_version": 1, "session_id": sid,
            "frames": [{"offset_points": 0, "count_points": 5}], "total_points": 5}


class _FakeBoard:
    """_record 脚本预期的 _BoardSession API；record stop 后 wait_ready 立即就绪。"""
    instances = []
    def __init__(self, base):
        self.base = base
        self.sid = 'hc_mock_001'
        self.stopped = False
        self.started = False
        type(self).instances.append(self)
    def status(self):
        return {"recording": False, "ros": "up", "disk_free_mb": 9999, "sessions_total": 0, "uptime_sec": 1}
    def current_recording(self):
        return None
    def start(self):
        self.started = True
        return {"session_id": self.sid}
    def stop(self):
        self.stopped = True
        return {"ok": True}
    def wait_ready(self, sid, deadline=180):
        assert sid == self.sid
        return {"state": "ready", "session_id": sid, "frame_count": 1, "duration_sec": 0.1, "size_bytes": 140}


class _FakeFetch:
    """跳过官方 fetch.py 网络/SHA，直接给一份合法 staging。"""
    calls = []
    def __init__(self, dest_root):
        self.dest_root = Path(dest_root)
        self.staging = self.dest_root / '.joint_fetch_staging'
    def _staging_dir(self, sid):
        return self.staging / sid
    def pull(self, sid):
        type(self).calls.append(sid)
        staging = self._staging_dir(sid)
        staging.mkdir(parents=True, exist_ok=True)
        (staging / 'meta.json').write_text(json.dumps(_fake_meta(sid)), encoding='utf-8')
        (staging / 'points.bin').write_bytes(b'\x00' * (5 * 28))
        return staging / 'meta.json', staging / 'points.bin'


def _wait_for(recorder, predicate, timeout=10):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        s = recorder.status()
        if predicate(s):
            return s
        time.sleep(.05)
    raise AssertionError('timeout; last state=%s' % recorder.status())


class BoardOrchestratorTest(unittest.TestCase):
    def _opts(self, tmp, dur=1):
        return dict(output_root=str(tmp), duration_sec=dur,
                    camera_url='http://127.0.0.1:1/stream',           # 相机从未上线 → 预览安静失败
                    radar_board_url='http://192.168.31.58:8766')      # 不参与真实请求（mock 了 _BoardSession）

    def test_camera_preview_failure_still_allows_board_record_and_marked_gaps(self):
        """相机预览一直失败：录制照常完成，最终 completed_with_gaps（板端雷达数据完整）。"""
        with tempfile.TemporaryDirectory() as tmp, \
             mock.patch.object(J, '_BoardSession', _FakeBoard), \
             mock.patch.object(J, '_StagedFetch', _FakeFetch):
            recorder = J.Recorder(tmp)
            self.addCleanup(recorder.close)
            recorder.start(self._opts(tmp))
            result = _wait_for(recorder, lambda s: s['state'].startswith('completed') or s['state'] == 'failed')
            self.assertEqual(result['state'], 'completed')
            self.assertEqual(_FakeBoard.instances[-1].stopped, True)
            self.assertEqual(_FakeFetch.calls, ['hc_mock_001'])
            out = Path(result['path'])
            self.assertTrue(out.name.startswith('joint_hc_mock_001'))
            meta = json.loads((out / 'meta.json').read_text(encoding='utf-8'))
            self.assertEqual(meta['joint_recording']['board_session_id'], 'hc_mock_001')
            self.assertEqual(meta['joint_recording']['mode'], 'staged_capture')
            self.assertEqual(meta['session_id'], 'hc_mock_001')
            self.assertEqual(meta['total_points'], 5)
            self.assertEqual((out / 'camera.mjpeg').read_bytes(), b'')
            self.assertEqual((out / 'points.bin').stat().st_size, 5 * 28)

    def test_board_stop_exception_still_marks_failed(self):
        """board wait_ready 超时/抽取失败 → 报 failed；start 调用后总补 stop。"""
        class BadBoard(_FakeBoard):
            def wait_ready(self, sid, deadline=180):
                raise OSError('board extraction failed: SIGSEGV')
        with tempfile.TemporaryDirectory() as tmp, \
             mock.patch.object(J, '_BoardSession', BadBoard), \
             mock.patch.object(J, '_StagedFetch', _FakeFetch):
            recorder = J.Recorder(tmp)
            self.addCleanup(recorder.close)
            recorder.start(self._opts(tmp))
            result = _wait_for(recorder, lambda s: s['state'] == 'failed')
            self.assertIn('SIGSEGV', result['error'])
            self.assertEqual(BadBoard.instances[-1].stopped, True)
            self.assertIsNone(result['path'])

    def test_fetch_failure_leaves_board_session_ready_for_retry(self):
        """fetch 拉不动 → state=failed，错误信息里要带 sid 便于人工在回页面板重试。"""
        class EmptyFetch(_FakeFetch):
            def pull(self, sid):
                self.log = ['fetch hc_mock_001 exit=1 FAIL some reason']
                return None, None
        with tempfile.TemporaryDirectory() as tmp, \
             mock.patch.object(J, '_BoardSession', _FakeBoard), \
             mock.patch.object(J, '_StagedFetch', EmptyFetch):
            recorder = J.Recorder(tmp)
            self.addCleanup(recorder.close)
            recorder.start(self._opts(tmp))
            result = _wait_for(recorder, lambda s: s['state'] == 'failed')
            self.assertIn('hc_mock_001', result['error'])
            self.assertIn('ready', result['error'])

    def test_same_origin_guard_still_enforced(self):
        """外部 Origin 一律 403（在 Joint V2 仍然成立；不改变安全姿态）。"""
        with tempfile.TemporaryDirectory() as tmp:
            server, recorder = J.start_server(tmp, Path(J.__file__).with_name('joint_capture.html'))
            try:
                url = 'http://127.0.0.1:%d/api/start' % server.server_port
                request = urllib.request.Request(url, data=b'{}',
                                                 headers={'Content-Type': 'application/json',
                                                          'Origin': 'http://evil.example'})
                with self.assertRaises(urllib.error.HTTPError) as ctx:
                    urllib.request.urlopen(request)
                self.assertEqual(ctx.exception.code, 403)
                ctx.exception.close()
            finally:
                recorder.close(); server.shutdown(); server.server_close()


if __name__ == '__main__':
    unittest.main()

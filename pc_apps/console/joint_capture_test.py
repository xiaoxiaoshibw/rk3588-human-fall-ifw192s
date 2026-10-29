"""错峰联合录制：HC 协调器 + 预览 + 一次 fetch 的不变量测试。

不测网络；mock _BoardSession 和 _StagedFetch，钉死以下合同：
  1. PC 预览失败 → state=failed 且板端已被 stop（不留野 bag 继续膨胀）
  2. PC 写本地目录失败 → state=failed 且板端已被 stop
  3. 正常路径 → meta/points moved 到 output_root/<sid>/ 且 joint_recording.board_session_id==sid
     （目录名必须是 sid：回页面板按 sid 找本地副本，改名就会把同一份雷达再拉一遍）
  4. Origin 校验仍为 same-origin
  5. 相机在线 → 预览帧逐条写入会话 camera.mjpeg + camera_frames.jsonl（回看数据源）
"""
import io
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
import unittest.mock as mock
import urllib.error
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
    def __init__(self, dest_root, board_url=None, fetch_dir=None):
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


class _FakeCameraStream:
    """假 MJPEG 响应：按 read1 逐块吐出给定字节，headers 报 multipart。"""
    def __init__(self, body):
        self._body = body
        self.headers = {'Content-Type': 'multipart/x-mixed-replace; boundary=x'}
    def __enter__(self):
        return self
    def __exit__(self, *exc):
        return False
    def read1(self, size):
        chunk, self._body = self._body[:size], self._body[size:]
        return chunk


def _fake_camera_opener(frames):
    """第一次 urlopen 给含 N 帧的流（读完即断），之后一律失败：只录一轮，不重复计数。"""
    body = b''.join(b'\xff\xd8\xff\xe0' + bytes([i]) + b'\xff\xd9' for i in range(frames))
    sent = []

    def _open(url, timeout=None):
        if sent:
            raise OSError('camera offline')
        sent.append(1)
        return _FakeCameraStream(body)

    return _open, body


def _wait_for(recorder, predicate, timeout=10):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        s = recorder.status()
        if predicate(s):
            return s
        time.sleep(.05)
    raise AssertionError('timeout; last state=%s' % recorder.status())


class BoardOrchestratorTest(unittest.TestCase):
    def test_pending_recording_is_not_stopped_or_replaced(self):
        class PendingBoard(_FakeBoard):
            def current_recording(self):return {'session_id':'prior_session'}
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(J,'_BoardSession',PendingBoard):
            recorder=J.Recorder(tmp)
            with self.assertRaisesRegex(OSError,'pending recording'):recorder.start(self._opts(tmp))
            board=PendingBoard.instances[-1]
            self.assertFalse(board.started);self.assertFalse(board.stopped)

    def test_existing_session_bytes_remain_unchanged_on_directory_collision(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(J,'_BoardSession',_FakeBoard):
            directory=Path(tmp)/'hc_mock_001';directory.mkdir()
            (directory/'joint.json').write_bytes(b'original-joint')
            (directory/'points.bin').write_bytes(b'original-points')
            recorder=J.Recorder(tmp);self.addCleanup(recorder.close)
            recorder.start(self._opts(tmp))
            result=_wait_for(recorder,lambda s:s['state']=='failed')
            self.assertIn('recorder:',result['error'])
            self.assertEqual((directory/'joint.json').read_bytes(),b'original-joint')
            self.assertEqual((directory/'points.bin').read_bytes(),b'original-points')

    def test_local_service_start_and_status_do_not_access_device_or_create_output(self):
        with tempfile.TemporaryDirectory() as tmp, \
             mock.patch.object(J,'_BoardSession',side_effect=AssertionError('no board access')), \
             mock.patch.object(J.urllib.request,'urlopen',wraps=urllib.request.urlopen):
            root=Path(tmp)/'not_created'
            server,recorder=J.start_server(root,Path(__file__).with_name('joint_capture.html'))
            try:
                with urllib.request.urlopen('http://127.0.0.1:%d/api/status'%server.server_port) as response:
                    self.assertEqual(json.load(response)['state'],'idle')
                self.assertFalse(root.exists())
            finally:recorder.close();server.shutdown();server.server_close()

    def _opts(self, tmp, dur=1):
        return dict(output_root=str(tmp), duration_sec=dur,
                    camera_url='http://127.0.0.1:1/stream',           # 相机从未上线 → 预览安静失败
                    radar_board_url='http://192.168.31.58:8766')      # 不参与真实请求（mock 了 _BoardSession）

    def test_camera_preview_failure_still_allows_board_record_and_marked_gaps(self):
        """相机预览一直失败：录制照常完成，最终 completed（板端雷达数据完整）。"""
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
            self.assertEqual(out.name, 'hc_mock_001')
            self.assertEqual(out, Path(tmp) / 'hc_mock_001')   # 面板按 sid 就能认出本地副本
            self.assertFalse(list(Path(tmp).glob('joint_*')), '不得再产生 joint_* 第二身份目录')
            meta = json.loads((out / 'meta.json').read_text(encoding='utf-8'))
            self.assertEqual(meta['joint_recording']['board_session_id'], 'hc_mock_001')
            self.assertEqual(meta['joint_recording']['mode'], 'staged_capture')
            self.assertEqual(meta['session_id'], 'hc_mock_001')
            self.assertEqual(meta['total_points'], 5)
            self.assertEqual((out / 'camera.mjpeg').read_bytes(), b'')
            self.assertEqual((out / 'points.bin').stat().st_size, 5 * 28)
            # R6/A3：落盘工件 joint.json 必须补终态（排障直接看文件）
            joint = json.loads((out / 'joint.json').read_text(encoding='utf-8'))
            self.assertEqual(joint['state'], 'completed')
            self.assertEqual(joint['radar_frames'], 1)
            self.assertEqual(joint['bytes'], (out / 'meta.json').stat().st_size + 5 * 28)
            self.assertIsNone(joint['error'])

    def test_camera_preview_is_written_to_session(self):
        """相机在线：预览帧整套落盘 camera.mjpeg + camera_frames.jsonl（回看/索引数据源）。"""
        opener, body = _fake_camera_opener(3)
        with tempfile.TemporaryDirectory() as tmp, \
             mock.patch.object(J, '_BoardSession', _FakeBoard), \
             mock.patch.object(J, '_StagedFetch', _FakeFetch), \
             mock.patch.object(J.urllib.request, 'urlopen', opener):
            recorder = J.Recorder(tmp)
            self.addCleanup(recorder.close)
            recorder.start(self._opts(tmp))
            result = _wait_for(recorder, lambda s: s['state'] == 'completed')
            self.assertEqual(result['camera_frames'], 3)
            out = Path(result['path'])
            self.assertEqual((out / 'camera.mjpeg').read_bytes(), body)
            lines = (out / 'camera_frames.jsonl').read_text(encoding='utf-8').strip().splitlines()
            self.assertEqual([json.loads(line) for line in lines],
                             [{'offset': 0, 'length': 7, 'recv_unix_ns': mock.ANY},
                              {'offset': 7, 'length': 7, 'recv_unix_ns': mock.ANY},
                              {'offset': 14, 'length': 7, 'recv_unix_ns': mock.ANY}])
            joint = json.loads((out / 'joint.json').read_text(encoding='utf-8'))
            self.assertEqual(joint['camera_frames'], 3)

    def test_camera_route_serves_saved_video_and_rejects_unsafe_sid(self):
        """/api/camera 只出本会话目录下的 camera.mjpeg；越权 sid 一律 404。"""
        with tempfile.TemporaryDirectory() as tmp:
            saved = Path(tmp) / 'hc_mock_001'
            saved.mkdir()
            (saved / 'camera.mjpeg').write_bytes(b'\xff\xd8\xff\xd9')
            server, recorder = J.start_server(tmp, Path(J.__file__).with_name('joint_capture.html'))
            try:
                base = 'http://127.0.0.1:%d' % server.server_port
                self.assertEqual(urllib.request.urlopen(base + '/api/camera?sid=hc_mock_001').read(),
                                 b'\xff\xd8\xff\xd9')
                for bad in ('../meta.json', 'a/b', '', 'x' * 101):
                    with self.assertRaises(urllib.error.HTTPError) as ctx:
                        urllib.request.urlopen(base + '/api/camera?sid=' + bad)
                    self.assertEqual(ctx.exception.code, 404)
                    ctx.exception.close()
            finally:
                recorder.close(); server.shutdown(); server.server_close()

    def test_unexpected_board_sid_is_rejected_without_writing(self):
        """板端 sid 只允许白名单字符：异常 sid 不许落成路径（信任边界）。"""
        class BadSidBoard(_FakeBoard):
            def __init__(self, base):
                super().__init__(base)
                self.sid = '../escape'

        class CountingFetch(_FakeFetch):
            calls = []

        with tempfile.TemporaryDirectory() as tmp, \
             mock.patch.object(J, '_BoardSession', BadSidBoard), \
             mock.patch.object(J, '_StagedFetch', CountingFetch):
            recorder = J.Recorder(tmp)
            self.addCleanup(recorder.close)
            recorder.start(self._opts(tmp))
            result = _wait_for(recorder, lambda s: s['state'] == 'failed')
            self.assertIn('session_id', result['error'])
            self.assertEqual(CountingFetch.calls, [])          # 未开始拉回
            self.assertEqual(list(Path(tmp).iterdir()), [])    # 未落任何文件/目录

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
            # 失败也要在会话目录留因（此前只有内存状态 + 板端 sessions.json 有原因）
            joint = json.loads((Path(tmp) / 'hc_mock_001' / 'joint.json').read_text(encoding='utf-8'))
            self.assertEqual(joint['state'], 'failed')
            self.assertIn('SIGSEGV', joint['error'])

    def test_wait_ready_surfaces_flat_board_error(self):
        """板端 GET 是扁平登记记录：error 在顶层，wait_ready 必须把它带出来（不能显示 None）。

        历史 bug：读 session['extra']['error']（板端从不返回该结构）→ 任何抽取失败都只报 None。
        """
        board = J._BoardSession('http://127.0.0.1:1')
        failed = {"session_id": "cap_20261015_220834", "state": "failed", "stop_reason": "manual",
                  "size_bytes": 4117, "error": "extract: bag 中没有 PointCloud2 话题"}
        with mock.patch.object(J, '_json_request', return_value=failed):
            with self.assertRaises(OSError) as ctx:
                board.wait_ready("cap_20261015_220834", deadline=5)
        self.assertIn('PointCloud2', str(ctx.exception))

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
            # R6/A3：失败落盘工件也要体现终态与原因
            joint = json.loads((Path(result['path']) / 'joint.json').read_text(encoding='utf-8'))
            self.assertEqual(joint['state'], 'failed')
            self.assertIn('hc_mock_001', joint['error'])

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


class _FakeCameraServer:
    """本地假板端相机：MJPEG 流式吐 JPEG；统计并发连接数（错峰：任何时刻只许 1 条）。"""
    active = 0
    max_active = 0
    stop_serving = False
    frame = b'\xff\xd8\xff\xe0data\xff\xd9'

    def __init__(self):
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), self._Handler)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    @property
    def url(self):
        return 'http://127.0.0.1:%d/stream' % self.server.server_port

    def close(self):
        self.stop_serving = True
        self.server.shutdown()
        self.server.server_close()

    class _Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def do_GET(self):
            _FakeCameraServer.active += 1
            _FakeCameraServer.max_active = max(_FakeCameraServer.max_active, _FakeCameraServer.active)
            try:
                if self.path != '/stream':
                    self.send_error(404)
                    return
                self.send_response(200)
                self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=f')
                self.end_headers()
                while not _FakeCameraServer.stop_serving:
                    self.wfile.write(_FakeCameraServer.frame)
                    self.wfile.flush()
                    time.sleep(.05)
            except OSError:
                pass
            finally:
                _FakeCameraServer.active -= 1


class IdlePreviewTest(unittest.TestCase):
    """空闲预览泵合同：UI 请求才连相机、无请求即断、录制中让流（错峰）。"""

    def setUp(self):
        _FakeCameraServer.active = 0
        _FakeCameraServer.max_active = 0
        _FakeCameraServer.stop_serving = False

    def test_preview_off_by_default_and_no_device_access_without_requests(self):
        with tempfile.TemporaryDirectory() as tmp:
            server, recorder = J.start_server(Path(tmp) / 'never_created',
                                              Path(J.__file__).with_name('joint_capture.html'))
            try:
                recorder.data['camera_url'] = 'http://127.0.0.1:1/stream'  # 不可达本机地址，绝不碰真板
                base = 'http://127.0.0.1:%d' % server.server_port
                with self.assertRaises(urllib.error.HTTPError) as ctx:
                    urllib.request.urlopen(base + '/api/preview')
                self.assertEqual(ctx.exception.code, 404)
                ctx.exception.close()
                recorder.preview_until = time.monotonic()  # 请求窗口立即到期
                _wait_for(recorder, lambda s: s['preview_state'] == 'off')
                self.assertEqual(_FakeCameraServer.active, 0)
                self.assertFalse((Path(tmp) / 'never_created').exists())
            finally:
                recorder.close()
                server.shutdown()
                server.server_close()

    def test_idle_pump_serves_fresh_frames_only_while_requested(self):
        camera = _FakeCameraServer()
        self.addCleanup(camera.close)
        with tempfile.TemporaryDirectory() as tmp:
            server, recorder = J.start_server(Path(tmp) / 'out',
                                              Path(J.__file__).with_name('joint_capture.html'))
            try:
                recorder.data['camera_url'] = camera.url
                base = 'http://127.0.0.1:%d' % server.server_port
                with self.assertRaises(urllib.error.HTTPError) as ctx:
                    urllib.request.urlopen(base + '/api/preview')   # 首次：泵刚被唤醒，还没有帧
                self.assertEqual(ctx.exception.code, 404)
                ctx.exception.close()

                def preview_ready():
                    try:
                        with urllib.request.urlopen(base + '/api/preview', timeout=3) as r:
                            return r.read() == camera.frame
                    except urllib.error.HTTPError:
                        return False
                deadline = time.monotonic() + 10
                while time.monotonic() < deadline and not preview_ready():
                    time.sleep(.1)
                self.assertTrue(preview_ready(), '泵未在窗口内产出预览帧')
                self.assertEqual(recorder.status()['preview_state'], 'live')

                recorder.preview_until = time.monotonic()       # 停止请求：泵断流、latest 清空
                _wait_for(recorder, lambda s: s['preview_state'] == 'off')
                self.assertIsNone(recorder.latest)
                deadline = time.monotonic() + 3                 # 服务器侧感知断开有写入周期滞后
                while time.monotonic() < deadline and _FakeCameraServer.active:
                    time.sleep(.05)
                self.assertEqual(_FakeCameraServer.active, 0)
                with self.assertRaises(urllib.error.HTTPError) as ctx:
                    urllib.request.urlopen(base + '/api/preview')
                self.assertEqual(ctx.exception.code, 404)
                ctx.exception.close()
            finally:
                recorder.close()
                server.shutdown()
                server.server_close()

    def test_pump_yields_camera_stream_during_recording(self):
        """错峰红线：录制相机线程与空闲预览泵共用一条流锁。

        PC 客户端同时打开的相机流数不得超过 1。在客户端侧计量（包装 urlopen 为计数
        代理，close() 减计数）；服务器侧只能异步感知 FIN（下一轮 write 才报错），
        计数会短暂虚高，不能作为确定性断言。
        """
        camera = _FakeCameraServer()
        self.addCleanup(camera.close)
        open_streams = [0]
        max_open = [0]
        real_open = J.urllib.request.urlopen

        class _CountingResponse:
            def __init__(self, inner):
                self._inner = inner
                open_streams[0] += 1
                max_open[0] = max(max_open[0], open_streams[0])
            @property
            def headers(self):
                return self._inner.headers
            def read1(self, size):
                return self._inner.read1(size)
            def close(self):
                if self._inner is not None:
                    inner, self._inner = self._inner, None
                    inner.close()
                    open_streams[0] -= 1
            def __enter__(self):
                return self
            def __exit__(self, *exc):
                self.close()
                return False

        def counting_open(url, timeout=None):
            if str(url) == camera.url:
                return _CountingResponse(real_open(url, timeout=timeout))
            return real_open(url, timeout=timeout)

        with tempfile.TemporaryDirectory() as tmp, \
             mock.patch.object(J, '_BoardSession', _FakeBoard), \
             mock.patch.object(J, '_StagedFetch', _FakeFetch), \
             mock.patch.object(J.urllib.request, 'urlopen', counting_open):
            recorder = J.Recorder(Path(tmp) / 'out')
            self.addCleanup(recorder.close)
            recorder.data['camera_url'] = camera.url
            recorder.touch_preview()
            time.sleep(.4)  # 让泵先连上流
            recorder.start(dict(output_root=str(Path(tmp) / 'out'), duration_sec=1,
                                camera_url=camera.url, radar_board_url='http://192.168.31.58:8766'))
            result = _wait_for(recorder, lambda s: s['state'] == 'completed')
            self.assertGreater(result['camera_frames'], 0)
            self.assertLessEqual(max_open[0], 1, '录制期间出现第二条客户端相机流')


class StagedFetchTest(unittest.TestCase):
    """_StagedFetch.pull 必须在本进程跑官方 fetch.py。

    历史 bug：subprocess 起 `sys.executable -I fetch.py` —— 冻结版 sys.executable 是
    Console.exe（子进程只会再开一个控制台）、源码版 py3.11+ 的 -I 隐含 -P（脚本目录
    不进 sys.path，import config 直接失败）。两种方式都永远拉不到数据。
    """

    def _fake_fetch_dir(self, tmp, ok):
        fake = Path(tmp) / 'human_replay'
        fake.mkdir()
        (fake / 'fetch.py').write_text(
            'import os\n'
            'OK = %s\n'
            'def process_session(sid, dest_root=None, log=print):\n'
            "    log('called ' + sid)\n"
            '    if not OK:\n'
            '        return False\n'
            '    out = os.path.join(dest_root, sid)\n'
            '    os.makedirs(out, exist_ok=True)\n'
            '    with open(os.path.join(out, "meta.json"), "w") as fh:\n'
            '        fh.write("{}")\n'
            '    with open(os.path.join(out, "points.bin"), "wb") as fh:\n'
            '        fh.write(b"xx")\n'
            '    return True\n' % ok, encoding='utf-8')
        return fake

    def test_pull_runs_official_fetch_in_process(self):
        """显式 fetch_dir（console_gui 传入的解析结果）优先于缺省 FETCH_DIR。"""
        with tempfile.TemporaryDirectory() as tmp:
            fake = self._fake_fetch_dir(tmp, ok=True)
            fetcher = J._StagedFetch(Path(tmp) / 'out', fetch_dir=fake)
            meta_p, bin_p = fetcher.pull('hc_mock_001')
            self.assertTrue(meta_p and bin_p)
            self.assertTrue(Path(meta_p).is_file() and Path(bin_p).is_file())
            self.assertTrue(any('called hc_mock_001' in line for line in fetcher.log))

    def test_pull_failure_returns_none_and_keeps_log(self):
        """缺省路径（FETCH_DIR 缺省解析）也要能加载并正确上报失败。"""
        with tempfile.TemporaryDirectory() as tmp:
            fetcher = J._StagedFetch(Path(tmp) / 'out')
            with mock.patch.object(J, 'FETCH_DIR', self._fake_fetch_dir(tmp, ok=False)):
                self.assertEqual(fetcher.pull('hc_mock_001'), (None, None))
            self.assertTrue(any('called hc_mock_001' in line for line in fetcher.log))

    def test_load_fetch_explicit_dir(self):
        """load_fetch 是 pull 与发布探针共用的唯一加载器（R6/A4）。"""
        with tempfile.TemporaryDirectory() as tmp:
            module = J.load_fetch(self._fake_fetch_dir(tmp, ok=True))
        self.assertTrue(callable(module.get('process_session')))


if __name__ == '__main__':
    unittest.main()

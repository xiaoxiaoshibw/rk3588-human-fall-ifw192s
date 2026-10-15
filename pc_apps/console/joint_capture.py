"""PC 错峰联合录制：雷达先全量存板(HC 通道)，相机预览同步落盘；停止后一次性拉回雷达。

CPU 错峰：录制时板上网口只走相机预览流；雷达 rosbag/抽取都在 SD 卡上完成，
完成后 PC 用官方 fetch.py 一次性回拉 meta.json/points.bin，无逐段切片。
不重写 HC 状态机；不重写 fetch.py 校验（SHA/布局）；不写板。

本地会话目录名 = 板端 sid：与回页面板的拉回同名同源，同一段录制只有一个身份，
面板按 sid 直接看到本地副本，不会再拉第二遍。
"""
import json
import os
from pathlib import Path
import re
import runpy
import shutil
import sys
import threading
import time
import uuid
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MAX_FRAME = 32 * 1024 * 1024
MIN_FREE = 256 * 1024 ** 2
BOARD_STATUS = '/api/v1/status'
BOARD_CURRENT = '/api/v1/record/current'
BOARD_START = '/api/v1/record/start'
BOARD_STOP = '/api/v1/record/stop'
BOARD_SESSION = '/api/v1/sessions'
DEFAULT_OUTPUT_ROOT = Path(__file__).resolve().parents[2] / 'captures' / 'remote'
# 官方 fetch.py 目录缺省：源码运行 = 平级 pc_apps/human_replay；冻结运行 = _MEIPASS 内嵌副本
# （Console.spec datas）。有 ENV/INI 旁路时由 console_gui 经 fetch_dir 参数传入同一份解析结果。
_HERE = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parent))
FETCH_DIR = next((d for d in (_HERE / 'human_replay', _HERE.parent / 'human_replay')
                  if (d / 'fetch.py').is_file()), _HERE / 'human_replay')


def load_fetch(fetch_dir=None):
    """进程内加载官方 fetch.py（唯一权威实现）；pull 与发布探针共用，绝不再起子进程。

    返回 runpy 的模块 globals（含 process_session 与 config 模块 C）。
    """
    fetch_dir = Path(fetch_dir) if fetch_dir else FETCH_DIR
    if str(fetch_dir) not in sys.path:
        sys.path.insert(0, str(fetch_dir))
    return runpy.run_path(str(fetch_dir / 'fetch.py'))


def _json_request(method, url, body=None, timeout=8):
    data = json.dumps(body).encode('utf-8') if body is not None else None
    request = urllib.request.Request(url, data=data, method=method)
    if data is not None:
        request.add_header('Content-Type', 'application/json')
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = response.read()
        return json.loads(payload) if payload else {}


def board_url(base, path):
    return urllib.parse.urljoin(base if base.endswith('/') else base + '/', path.lstrip('/'))


def validate_board_base(base):
    parsed = urllib.parse.urlsplit(base)
    if parsed.scheme not in ('http', 'https') or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('invalid board service URL')
    return base.rstrip('/')


def jpeg_frames(response):
    """Bounded streaming JPEG parser; keep only complete SOI-to-EOI images."""
    buf = b''
    while True:
        chunk = response.read1(65536)
        if not chunk:
            raise OSError('camera stream ended')
        buf += chunk
        while True:
            start = buf.find(b'\xff\xd8\xff')
            if start < 0:
                buf = buf[-2:]
                break
            buf = buf[start:]
            end = buf.find(b'\xff\xd9', 3)
            if end < 0:
                break
            yield buf[:end + 2]
            buf = buf[end + 2:]
        if len(buf) > MAX_FRAME:
            raise ValueError('camera frame exceeds limit')


class _BoardSession:
    """HC 控制面薄封装：start/stop 幂等词、stop 后按 sid 等 ready。"""
    def __init__(self, base):
        self.base = validate_board_base(base)
        self.idem = uuid.uuid4().hex[:12]

    def status(self):
        return _json_request('GET', board_url(self.base, BOARD_STATUS))

    def current_recording(self):
        try:
            return _json_request('GET', board_url(self.base, BOARD_CURRENT))
        except urllib.error.HTTPError as exc:
            if exc.code == 204:
                return None
            raise

    def start(self):
        return _json_request('POST', board_url(self.base, BOARD_START), body={'idempotency_key': self.idem})

    def stop(self):
        return _json_request('POST', board_url(self.base, BOARD_STOP), body={'idempotency_key': self.idem})

    def wait_ready(self, sid, deadline=180):
        """等 capture_server 把刚停的 bag 完成 bag2session.extract → state=ready; 返回登记记录."""
        t0 = time.monotonic()
        while time.monotonic() - t0 < deadline:
            try:
                session = _json_request('GET', board_url(self.base, '%s/%s' % (BOARD_SESSION, sid)))
                if session.get('state') == 'ready' and session.get('frame_count'):
                    return session
                if session.get('state') == 'failed':
                    raise OSError('board extraction failed: %s' % (session.get('extra') or {}).get('error'))
            except urllib.error.HTTPError as exc:
                if exc.code not in (404,):
                    raise
            time.sleep(1)
        raise TimeoutError('board session %s did not become ready within %ds' % (sid, deadline))


class _StagedFetch:
    """进程内跑官方 fetch.process_session → staging/<sid>/{meta.json,points.bin}；最后整体 move 到会话目录。

    为什么不再 subprocess 起 `sys.executable -I fetch.py`：冻结版 sys.executable 是
    Console.exe 本身（子进程只会再开一个控制台，永远拉不到数据）；源码版 py3.11+ 的
    -I 隐含 -P，脚本目录不进 sys.path（fetch.py 的 `import config` 直接失败）。
    同进程 runpy 一份官方实现，两种运行方式行为一致；SHA/布局校验仍由 fetch.py 做。
    """
    def __init__(self, dest_root, board_url=None, fetch_dir=None):
        self.dest_root = Path(dest_root)
        self.staging = self.dest_root / '.joint_fetch_staging'
        self.board_url = board_url
        self.fetch_dir = fetch_dir
        self.log = []

    def _staging_dir(self, sid):
        return self.staging / sid

    def pull(self, sid):
        """拉官方实现 → staging；返回 (meta_p, bin_p) 或 (None, None)（失败原因见 self.log）。"""
        self.staging.mkdir(parents=True, exist_ok=True)
        meta_p, bin_p = self._staging_dir(sid) / 'meta.json', self._staging_dir(sid) / 'points.bin'
        try:
            fetch = load_fetch(self.fetch_dir)
            if self.board_url:
                fetch['C'].BOARD_URL = self.board_url  # 页面自定义板端地址须传导给官方 fetch
            ok = fetch['process_session'](sid, str(self.staging), log=self.log.append)
        except BaseException as exc:
            self.log.append('fetch %s: %s: %s' % (sid, type(exc).__name__, exc))
            return None, None
        if not ok or not meta_p.is_file() or not bin_p.is_file():
            return None, None
        return meta_p, bin_p


class Recorder:
    def __init__(self, root=None, fetch_dir=None):
        self.root = Path(root or os.environ.get('JOINT_OUTPUT_ROOT') or DEFAULT_OUTPUT_ROOT).resolve()
        self.fetch_dir = fetch_dir  # 官方 fetch.py 目录（console_gui 传入其 _replay_dir 解析结果）
        self.lock = threading.RLock()
        self.thread = None
        self.latest = None
        self.t0 = None
        self.stop_event = threading.Event()
        self.data = dict(state='idle', output_root=str(self.root), camera_url='http://192.168.31.58:8081/stream',
                         radar_board_url='http://192.168.31.58:8766', radar_frames=0, camera_frames=0,
                         bytes=0, error=None, session_id=None, path=None)
        self.path = None
        self._camera_error = None

    def status(self):
        with self.lock:
            result = dict(self.data)
            if result['state'] == 'recording' and self.t0 is not None:
                result['elapsed_sec'] = round((time.monotonic_ns() - self.t0) / 1e9, 2)
            return result

    def start(self, options):
        camera = options.get('camera_url', 'http://192.168.31.58:8081/stream')
        board_base = options.get('radar_board_url', 'http://192.168.31.58:8766')
        camera_parsed = urllib.parse.urlsplit(camera)
        if camera_parsed.scheme not in ('http', 'https') or not camera_parsed.hostname or camera_parsed.username or camera_parsed.password:
            raise ValueError('invalid camera URL')
        board_base = validate_board_base(board_base)
        duration = float(options.get('duration_sec', 300))
        if not 1 <= duration <= 300:
            raise ValueError('duration must be 1..300 seconds (board limit)')
        destination = str(options.get('output_root') or self.root)
        if destination.startswith(('\\\\', '//')):
            raise ValueError('choose a local disk, not a network share')
        root = Path(destination).expanduser()
        if not root.is_absolute():
            raise ValueError('output root must be absolute')
        root.mkdir(parents=True, exist_ok=True)
        if shutil.disk_usage(root).free < MIN_FREE:
            raise OSError('insufficient local disk space')
        root = root.resolve()
        with self.lock:
            if self.thread and self.thread.is_alive():
                raise ValueError('already recording or stopping')
            self.stop_event.clear()
            self._camera_error = None
            self.latest = None
            board = _BoardSession(board_base)
            status = board.status()
            if status.get('recording'):
                raise OSError('board is already recording: %s' % (status.get('session_id') or 'unknown'))
            current = board.current_recording()
            if current and current.get('session_id'):
                board.stop()
            self.root = root
            self.data = dict(state='starting', output_root=str(root), camera_url=camera, radar_board_url=board_base,
                             radar_frames=0, camera_frames=0, bytes=0, error=None,
                             session_id=None, path=None, camera_recovering=False,
                             synchronization='BOARD_MASTER_CLOCK_pc_camera_host_receipt')
            self.thread = threading.Thread(target=self._run, args=(board, duration), daemon=True)
            self.thread.start()
        return self.status()

    def stop(self):
        with self.lock:
            if self.thread and self.thread.is_alive():
                self.data['state'] = 'stopping'
                self.stop_event.set()
        return self.status()

    def close(self):
        self.stop()
        if self.thread:
            self.thread.join(timeout=15)

    def _fail(self, message):
        with self.lock:
            self.data['error'] = str(message)
            self.data['state'] = 'failed'
        self.stop_event.set()

    def _camera_preview_only(self, url, mj_path, frames_path):
        """录制中：预览逐帧写入会话 camera.mjpeg，并把字节位置+主机接收时刻记进
        camera_frames.jsonl（接收时刻非硬件同步，只作定位索引）。断开重连续写同一文件。
        """
        out = open(str(mj_path), 'ab')
        index = open(str(frames_path), 'a', encoding='utf-8')
        try:
            while not self.stop_event.is_set():
                try:
                    with urllib.request.urlopen(url, timeout=3) as response:
                        if 'multipart/' not in response.headers.get('Content-Type', ''):
                            raise ValueError('camera is not an MJPEG stream')
                        for jpeg in jpeg_frames(response):
                            if self.stop_event.is_set():
                                return
                            offset = out.tell()
                            out.write(jpeg)
                            out.flush()
                            index.write(json.dumps({'offset': offset, 'length': len(jpeg),
                                                    'recv_unix_ns': time.time_ns()}) + '\n')
                            index.flush()
                            with self.lock:
                                self.latest = jpeg
                                self.data['camera_recovering'] = False
                                self.data['camera_frames'] += 1
                except Exception as exc:
                    if self.stop_event.is_set():
                        return
                    with self.lock:
                        self._camera_error = str(exc)
                        self.data['camera_recovering'] = True
                    self.stop_event.wait(2)
        finally:
            out.close()
            index.close()

    def _run(self, board, duration):
        path = None
        try:
            session = board.start()
            with self.lock:
                self.data['state'] = 'recording'
                self.t0 = time.monotonic_ns()
                self.data['session_id'] = session.get('session_id')
                self.data['path'] = None
            sid = self.data['session_id']
            if not sid:
                raise OSError('board start did not return session_id')
            # 会话目录名 = 板端 sid（不是 joint_<sid>）：同一段录制只有一个身份。
            # 否则回页面板按 sid 找本地副本找不到，会把同一份雷达再拉一遍
            # （现场：cap_20261015_142730 与 joint_cap_20261015_142730 各 237 MB）。
            # 板端 sid 来自网络响应，只允许回放器白名单字符，不落成路径。
            if not re.fullmatch(r'[A-Za-z0-9_-]{1,100}', sid):
                raise ValueError('unexpected board session_id: %r' % sid)
            root = self.root
            out_dir = root / sid
            out_dir.mkdir(parents=True, exist_ok=True)
            # 相机预览逐帧写进会话目录（camera.mjpeg + 逐帧索引）；雷达在板上录，
            # 停板后先关相机文件再继续组装，两者互不影响。
            camera_path = out_dir / 'camera.mjpeg'
            camera_frames_path = out_dir / 'camera_frames.jsonl'
            preview = threading.Thread(target=self._camera_preview_only,
                                       args=(self.data['camera_url'], camera_path,
                                             camera_frames_path), daemon=True)
            preview.start()
            self.stop_event.wait(duration)
            board.stop()
            self.stop_event.set()          # 先停相机线程，等它把已收帧落盘
            preview.join(timeout=10)
            if not camera_path.exists():
                camera_path.write_bytes(b'')   # 相机未上线：空占位，会话仍可回放雷达
            elif not camera_path.stat().st_size:
                camera_frames_path.unlink(missing_ok=True)
            with self.lock:
                self.data['state'] = 'stopping'
                self.data['stop_host_unix_ns'] = time.time_ns()
            ready = board.wait_ready(sid, deadline=180)
            joint_info = dict(
                state='assembling', mode='staged_capture', session_id=sid,
                created_iso=time.strftime('%Y-%m-%dT%H:%M:%S%z'),
                synchronization=self.data['synchronization'])
            (out_dir / 'joint.json').write_text(json.dumps(joint_info, ensure_ascii=False, indent=2),
                                                encoding='utf-8')
            with self.lock:
                self.path = out_dir
                self.data['path'] = str(out_dir)
            # 一次性拉回：官方 fetch.py --sid（含 SHA/布局校验） → staging，到位再整体换名到会话目录
            fetcher = _StagedFetch(root, board.base, self.fetch_dir)
            with self.lock:
                self.data['state'] = 'saving'
                self.data['radar_frames'] = int(ready.get('frame_count') or 0)
                self.data['duration_sec'] = round((time.monotonic_ns() - self.t0) / 1e9, 2)
            meta_p, bin_p = fetcher.pull(sid)
            points_path = out_dir / 'points.bin'
            meta_path = out_dir / 'meta.json'
            finish_ok = bool(meta_p and bin_p)
            if finish_ok:
                shutil.move(str(meta_p), str(meta_path))
                shutil.move(str(bin_p), str(points_path))
                final_meta = json.loads(meta_path.read_text(encoding='utf-8'))
                final_meta.setdefault('joint_recording', {})
                final_meta['joint_recording'].update(mode='staged_capture', board_session_id=sid)
                meta_path.write_text(json.dumps(final_meta, ensure_ascii=False, indent=2), encoding='utf-8')
                shutil.rmtree(str(fetcher._staging_dir(sid)), ignore_errors=True)
            with self.lock:
                self.data['state'] = 'completed' if finish_ok else 'failed'
                self.data['camera_recovering'] = False
                self.data['bytes'] = (points_path.stat().st_size if points_path.exists() else 0) + (meta_path.stat().st_size if meta_path.exists() else 0)
                if not finish_ok:
                    self.data['error'] = ('fetch 拉回失败；板端会话 %s 仍为 ready，可在回页面板重试。\n%s'
                                          % (sid, '\n'.join(fetcher.log[-3:])))
                # 落盘工件补终态（排障直接看文件；写失败不影响已完成的会话数据）
                joint_info.update(state=self.data['state'], finished_iso=time.strftime('%Y-%m-%dT%H:%M:%S%z'),
                                  radar_frames=self.data['radar_frames'],
                                  camera_frames=self.data['camera_frames'],
                                  bytes=self.data['bytes'], error=self.data['error'])
            try:
                (out_dir / 'joint.json').write_text(json.dumps(joint_info, ensure_ascii=False, indent=2),
                                                    encoding='utf-8')
            except OSError:
                pass
        except Exception as exc:
            if self.data.get('session_id'):
                # 板已开始录但 PC 出错；尝试停板以免 bag 持续膨胀
                try:
                    board.stop()
                except Exception:
                    pass
            self._fail('recorder: %s' % exc)
        finally:
            self.stop_event.set()

    # _fetch_chunk 已不需要：一次性官方 fetch.py --sid 全量落地，sha/meta 校验由官方权威实现做。


def start_server(root, html_path, fetch_dir=None):
    recorder = Recorder(root, fetch_dir)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass

        def reply(self, status, data, kind='application/json; charset=utf-8'):
            body = json.dumps(data, ensure_ascii=False).encode('utf-8') if isinstance(data, dict) else data
            self.send_response(status)
            self.send_header('Content-Type', kind)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            route = urllib.parse.urlsplit(self.path).path
            if route == '/':
                self.reply(200, Path(html_path).read_bytes(), 'text/html; charset=utf-8')
            elif route == '/api/status':
                self.reply(200, recorder.status())
            elif route == '/api/preview' and recorder.latest:
                self.reply(200, recorder.latest, 'image/jpeg')
            elif route == '/api/camera':
                self._serve_camera()
            else:
                self.reply(404, {'error': 'not found'})

        def _serve_camera(self):
            """GET /api/camera?sid=<会话目录名>：流式发出该会话录下的 camera.mjpeg。"""
            sid = (urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query).get('sid') or [''])[0]
            safe = bool(re.fullmatch(r'[A-Za-z0-9_-]{1,100}', sid))
            path = recorder.root / sid / 'camera.mjpeg' if safe else None
            if not path or not path.is_file() or not path.stat().st_size:
                self.reply(404, {'error': '没有这个会话的相机视频'})
                return
            self.send_response(200)
            self.send_header('Content-Type', 'video/x-mjpeg')
            self.send_header('Content-Length', str(path.stat().st_size))
            self.end_headers()
            with open(str(path), 'rb') as fh:
                shutil.copyfileobj(fh, self.wfile)

        def do_POST(self):
            origin = self.headers.get('Origin')
            if origin and origin != 'http://127.0.0.1:%d' % self.server.server_port:
                self.reply(403, {'error': 'local same-origin requests only'})
                return
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 8192 or not self.headers.get('Content-Type', '').startswith('application/json'):
                    raise ValueError('JSON body required, maximum 8192 bytes')
                options = json.loads(self.rfile.read(length))
                if not isinstance(options, dict):
                    raise ValueError('JSON object required')
                if self.path == '/api/start':
                    result = recorder.start(options)
                elif self.path == '/api/stop':
                    result = recorder.stop()
                elif self.path == '/api/open-folder':
                    os.startfile(recorder.status().get('path') or str(recorder.root))
                    result = recorder.status()
                else:
                    self.reply(404, {'error': 'not found'})
                    return
                self.reply(200, result)
            except (ValueError, OSError, TypeError) as exc:
                self.reply(400, {'error': str(exc)})

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, recorder

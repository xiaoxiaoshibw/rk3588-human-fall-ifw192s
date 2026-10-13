"""PC 错峰联合录制：雷达先全量存板(HC 通道)，相机仅预览；停止后逐段拉回雷达。

CPU 错峰：录制时板上网口只走相机预览流；雷达 rosbag/抽取都在 SD 卡上完成，
完成后 PC 才按段增量回拉 meta.json/points.bin，再按 frames 行上切片。
不重写 HC 状态机；不重写 fetch.py 校验（SHA/布局）；不写板。
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
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
PC_FETCH_DIR = Path(__file__).resolve().parent.parent / 'human_replay'
FETCH_SCRIPT = PC_FETCH_DIR / 'fetch.py'


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
    """一次性 fetch_fetch.py --sid → staging/<sid>/{meta.json,points.bin}；最后整体 move 到会话目录。"""
    def __init__(self, dest_root):
        self.dest_root = Path(dest_root)
        self.staging = self.dest_root / '.joint_fetch_staging'
        self.log = []

    def _staging_dir(self, sid):
        return self.staging / sid

    def pull(self, sid):
        """fetch.py --sid：拉官方实现（SHA/布局校验） → staging；返回 (meta_p, bin_p) 或 (None, None)。"""
        self.staging.mkdir(parents=True, exist_ok=True)
        cmd = [sys.executable, '-I', str(FETCH_SCRIPT), '--sid', sid, '--dest', str(self.staging)]
        try:
            out = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            self.log.append('fetch %s exit=%d %s' % (sid, out.returncode, (out.stdout or '').strip()[-240:]))
            meta_p, bin_p = self._staging_dir(sid) / 'meta.json', self._staging_dir(sid) / 'points.bin'
            if out.returncode != 0 or not meta_p.exists() or not bin_p.exists():
                self.log.append((out.stderr or '').strip()[-300:])
                return None, None
            return meta_p, bin_p
        except subprocess.TimeoutExpired:
            self.log.append('fetch %s timeout' % sid)
            return None, None


class Recorder:
    def __init__(self, root=None):
        self.root = Path(root or os.environ.get('JOINT_OUTPUT_ROOT') or DEFAULT_OUTPUT_ROOT).resolve()
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

    def _camera_preview_only(self, url):
        """During recording: only preview JPEGs, never write; on error surface and end preview."""
        while not self.stop_event.is_set():
            try:
                with urllib.request.urlopen(url, timeout=3) as response:
                    if 'multipart/' not in response.headers.get('Content-Type', ''):
                        raise ValueError('camera is not an MJPEG stream')
                    for jpeg in jpeg_frames(response):
                        if self.stop_event.is_set():
                            return
                        with self.lock:
                            self.latest = jpeg
                            self.data['camera_recovering'] = False
                            self.data['camera_frames'] = 1
            except Exception as exc:
                if self.stop_event.is_set():
                    return
                with self.lock:
                    self._camera_error = str(exc)
                    self.data['camera_recovering'] = True
                self.stop_event.wait(2)

    def _run(self, board, duration):
        path = None
        try:
            session = board.start()
            with self.lock:
                self.data['state'] = 'recording'
                self.t0 = time.monotonic_ns()
                self.data['session_id'] = session.get('session_id')
                self.data['path'] = None
            preview = threading.Thread(target=self._camera_preview_only,
                                       args=(self.data['camera_url'],), daemon=True)
            preview.start()
            self.stop_event.wait(duration)
            board.stop()
            with self.lock:
                self.data['state'] = 'stopping'
                self.data['stop_host_unix_ns'] = time.time_ns()
            sid = self.data['session_id']
            if not sid:
                raise OSError('board start did not return session_id')
            ready = board.wait_ready(sid, deadline=180)
            # 创建 session 目录、保留空 camera.mjpeg 以便回放器将此会话当 video-only 段
            root = self.root
            out_dir = root / ('joint_' + sid)
            out_dir.mkdir(parents=True, exist_ok=True)
            (out_dir / 'camera.mjpeg').write_bytes(b'')
            (out_dir / 'joint.json').write_text(json.dumps(dict(
                state='assembling', mode='staged_capture', session_id=sid,
                created_iso=time.strftime('%Y-%m-%dT%H:%M:%S%z'),
                synchronization=self.data['synchronization']), ensure_ascii=False, indent=2))
            with self.lock:
                self.path = out_dir
                self.data['path'] = str(out_dir)
            # 一次性拉回：官方 fetch.py --sid（含 SHA/布局校验） → staging，到位再整体换名到会话目录
            fetcher = _StagedFetch(root)
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


def start_server(root, html_path):
    recorder = Recorder(root)

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
            else:
                self.reply(404, {'error': 'not found'})

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

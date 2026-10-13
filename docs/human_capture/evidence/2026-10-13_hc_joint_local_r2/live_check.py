"""Actual camera/radar read-only stream smoke; all recorded data stays on PC."""
import json
from pathlib import Path
import sys
import threading
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
CONSOLE = ROOT / 'pc_apps/console'
sys.path.insert(0, str(CONSOLE))
sys.path.insert(0, str(ROOT / 'pc_apps/human_replay'))
import joint_capture as J
import human_replay_lib as H
from playwright.sync_api import sync_playwright


def main():
    server, recorder = J.start_server(ROOT / 'captures/remote', CONSOLE / 'joint_capture.html')
    class Shell(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(CONSOLE), **kwargs)
        def log_message(self, *_args): pass
    shell = ThreadingHTTPServer(('127.0.0.1', 0), Shell)
    threading.Thread(target=shell.serve_forever, daemon=True).start()
    errors = []
    result = {'environment': 'WINDOWS_PC_REAL_EXISTING_STREAMS', 'board_writes': 'NONE; MJPEG GET and Foxglove subscribe only', 'runs': []}
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(channel='msedge')
            page = browser.new_page(viewport={'width': 1440, 'height': 1100})
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto('http://127.0.0.1:%d/console.html?capture_port=%d' % (shell.server_port, server.server_port))
            page.get_by_text('USB＋雷达联合录制', exact=True).click()
            frame = page.frame_locator('#f')
            frame.locator('#start').wait_for()
            for mode in ('automatic', 'manual'):
                frame.locator('#duration').fill('30' if mode == 'automatic' else '60')
                frame.locator('#start').click()
                frame.locator('#state').filter(has_text='正在联合录制').wait_for(timeout=15000)
                page.wait_for_timeout(800)
                assert frame.locator('#preview').evaluate('(img) => img.naturalWidth > 0')
                page.screenshot(path=str(OUT / (mode + '_recording.png')), full_page=True)
                if mode == 'manual': frame.locator('#stop').click()
                frame.locator('#state').filter(has_text='已保存到本机').wait_for(timeout=45000)
                status = recorder.status()
                directory = Path(status['path'])
                meta = json.loads((directory / 'meta.json').read_text(encoding='utf-8'))
                assert status['camera_frames'] > 0 and status['radar_frames'] > 0, status
                assert directory.parent == ROOT / 'captures/remote'
                assert (directory / 'points.bin').stat().st_size == meta['total_points'] * 28
                assert status['session_id'] in H._local_sessions(str(directory.parent))
                result['runs'].append(dict(mode=mode, status=status, replay_listing_ok=True,
                                           points_size=(directory / 'points.bin').stat().st_size,
                                           raw_radar_size=(directory / 'radar.ros1').stat().st_size,
                                           camera_size=(directory / 'camera.mjpeg').stat().st_size))
                page.screenshot(path=str(OUT / (mode + '_completed.png')), full_page=True)
            result['browser_errors'] = errors
            assert not errors, errors
            browser.close()
        result['ok'] = True
    finally:
        recorder.close()
        server.shutdown(); server.server_close()
        shell.shutdown(); shell.server_close()
        (OUT / 'LIVE_CHECK.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__': main()

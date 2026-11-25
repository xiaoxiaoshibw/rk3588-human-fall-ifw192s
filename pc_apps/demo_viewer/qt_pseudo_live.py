"""Qt window for the existing local, offline-preprocessed replay page."""
import argparse
import json
import sys
import threading
from http.server import HTTPServer
from pathlib import Path

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtWidgets import QApplication
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile
from PySide6.QtWebEngineWidgets import QWebEngineView

from pseudo_live import Handler


class LocalPage(QWebEnginePage):
    def __init__(self, profile, origin, parent=None):
        super().__init__(profile, parent)
        self.origin = origin

    def acceptNavigationRequest(self, url, kind, is_main_frame):
        return url.scheme() == 'http' and url.host() == '127.0.0.1' and url.port() == self.origin


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--smoke-report', type=Path)
    args = parser.parse_args()
    if args.smoke_report and args.smoke_report.exists():
        raise ValueError('smoke report must be a new file')
    server = HTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    app = QApplication(sys.argv[:1])
    view = QWebEngineView()
    profile = QWebEngineProfile(view)  # off-the-record; no persistent browser profile
    page = LocalPage(profile, server.server_port, view)
    view.setPage(page)
    view.setWindowTitle('人体候选 · 离线预处理伪实时回放')
    view.resize(1500, 950)
    view.load(QUrl('http://127.0.0.1:%d/' % server.server_port))
    view.show()
    if args.smoke_report:
        finished = [False]
        def finish(status, detail):
            if finished[0]:
                return
            finished[0] = True
            image = args.smoke_report.with_suffix('.png')
            saved = view.grab().save(str(image))
            with args.smoke_report.open('x', encoding='utf8') as f:
                json.dump(dict(status=status if saved else 'screenshot_failed', detail=detail,
                               screenshot=str(image)), f, ensure_ascii=False, indent=2)
            app.exit(0 if status == 'ok' and saved else 2)
        def check():
            page.runJavaScript("JSON.stringify({frame:document.getElementById('frame').textContent,depth:document.getElementById('depth').naturalWidth,status:document.getElementById('status').textContent})",
                               lambda result: inspect(result))
        def inspect(result):
            try:
                data = json.loads(result)
                if data['frame'] != '—' and data['depth'] == 256:
                    page.runJavaScript("document.getElementById('pause').click()")
                    QTimer.singleShot(800, pause_snapshot)
                elif '出错' in data['status']:
                    finish('failed', data)
                else:
                    QTimer.singleShot(300, check)
            except (TypeError, ValueError, KeyError) as error:
                finish('failed', str(error))
        def pause_snapshot():
            page.runJavaScript("JSON.stringify({frame:document.getElementById('frame').textContent,status:document.getElementById('status').textContent})", check_paused)
        def check_paused(result):
            try:
                first = json.loads(result)
                def verify(next_result):
                    try:
                        second = json.loads(next_result)
                        ok = first['frame'] == second['frame'] and second['status'] == '已暂停'
                        finish('ok' if ok else 'failed', dict(first=first, second=second))
                    except (TypeError, ValueError, KeyError) as error:
                        finish('failed', str(error))
                QTimer.singleShot(700, lambda: page.runJavaScript("JSON.stringify({frame:document.getElementById('frame').textContent,status:document.getElementById('status').textContent})", verify))
            except (TypeError, ValueError, KeyError) as error:
                finish('failed', str(error))
        def loaded(ok):
            if not ok:
                finish('failed', 'page load failed')
            else:
                page.runJavaScript("document.getElementById('autoPause').checked=false; document.getElementById('start').click()")
                QTimer.singleShot(300, check)
        view.loadFinished.connect(loaded)
        QTimer.singleShot(30000, lambda: finish('timeout', 'no first frame'))
    try:
        return app.exec()
    finally:
        server.shutdown()
        thread.join()
        if Handler.replay:
            Handler.replay.close()
            Handler.replay = None
        server.server_close()


if __name__ == '__main__':
    sys.exit(main())

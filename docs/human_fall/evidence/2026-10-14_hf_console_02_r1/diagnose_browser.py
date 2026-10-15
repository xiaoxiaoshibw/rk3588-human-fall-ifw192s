import http.server
import json
from functools import partial
from pathlib import Path
import sys
import threading

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "pc_apps/console"))
import console_gui as G

replay, pointset, real_fall = G._start_replay_server(), G._start_fall_server(), G._start_real_fall_server()
shell = http.server.ThreadingHTTPServer(
    ("127.0.0.1", 0),
    partial(http.server.SimpleHTTPRequestHandler, directory=str(ROOT / "pc_apps/console")),
)
threading.Thread(target=shell.serve_forever, daemon=True).start()
errors, failures = [], []
with sync_playwright() as pw:
    browser = pw.chromium.launch(channel="msedge", headless=True)
    page = browser.new_page(viewport={"width": 1640, "height": 1080})
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on("console", lambda message: errors.append(message.text) if message.type == "error" else None)
    page.on("requestfailed", lambda request: failures.append({"url": request.url, "error": request.failure}))
    url = "http://127.0.0.1:%d/%s" % (
        shell.server_address[1], G._shell_url(replay, pointset, real_fall_port=real_fall)
    )
    page.goto(url, wait_until="networkidle")
    page.locator(".card").filter(has=page.get_by_text("真人倒地回放", exact=True)).click()
    frame = page.frame_locator("#f")
    frame.locator("#status").wait_for()
    page.wait_for_timeout(7000)
    result = {
        "ports": {"replay": replay, "pointset": pointset, "real_fall": real_fall},
        "iframe_src": page.locator("#f").get_attribute("src"),
        "status": frame.locator("#status").inner_text(),
        "frame_value": frame.locator("#frame").input_value(),
        "errors": errors,
        "request_failures": failures,
    }
    page.screenshot(path=str(OUT / "BROWSER_DIAGNOSTIC_01.png"), full_page=True)
    browser.close()
shell.shutdown()
shell.server_close()
with (OUT / "BROWSER_DIAGNOSTIC_01.json").open("x", encoding="utf-8") as stream:
    json.dump(result, stream, ensure_ascii=False, indent=2)
print(json.dumps(result, ensure_ascii=False, indent=2))

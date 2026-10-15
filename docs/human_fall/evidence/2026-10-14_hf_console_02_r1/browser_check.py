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

replay = G._start_replay_server()
pointset = G._start_fall_server()
real_fall = G._start_real_fall_server()
assert pointset and real_fall
shell = http.server.ThreadingHTTPServer(
    ("127.0.0.1", 0),
    partial(http.server.SimpleHTTPRequestHandler, directory=str(ROOT / "pc_apps/console")),
)
threading.Thread(target=shell.serve_forever, daemon=True).start()
errors = []
with sync_playwright() as pw:
    browser = pw.chromium.launch(channel="msedge", headless=True)
    page = browser.new_page(viewport={"width": 1640, "height": 1080})
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on("console", lambda message: errors.append(message.text) if message.type == "error" else None)
    url = "http://127.0.0.1:%d/%s" % (
        shell.server_address[1], G._shell_url(replay, pointset, real_fall_port=real_fall)
    )
    page.goto(url, wait_until="networkidle")
    cards = page.locator(".card")
    names = [name.strip() for name in cards.locator(".name").all_text_contents()]
    assert "骨架与倒地检测" in names and "真人倒地回放" in names
    page.screenshot(path=str(OUT / "CONSOLE_HOME.png"), full_page=True)

    real_card = page.locator(".card").filter(has=page.get_by_text("真人倒地回放", exact=True))
    real_card.click()
    real_frame = page.frame_locator("#f")
    real_frame.locator("#status").wait_for()
    real_frame.locator('[data-frame="72"]').click()
    real_frame.locator("#status").filter(has_text="帧 72 / 163").wait_for()
    assert real_frame.locator("#alert").inner_text() == "告警保持"
    assert real_frame.locator("canvas").count() == 2
    real_iframe_src = page.locator("#f").get_attribute("src")
    assert real_iframe_src == "http://127.0.0.1:%d/" % real_fall
    page.screenshot(path=str(OUT / "CONSOLE_REAL_FALL.png"), full_page=True)

    page.locator("#back").click()
    pointset_card = page.locator(".card").filter(has=page.get_by_text("骨架与倒地检测", exact=True))
    pointset_card.click()
    pointset_iframe_src = page.locator("#f").get_attribute("src")
    assert pointset_iframe_src == "http://127.0.0.1:%d/" % pointset
    page.frame_locator("#f").locator("body").wait_for()
    browser.close()

shell.shutdown()
shell.server_close()
result = {
    "browser": "headless Microsoft Edge; actual console HTML and both live services",
    "home_cards": names,
    "real_fall_iframe": real_iframe_src,
    "pointset_iframe": pointset_iframe_src,
    "real_frame_72_alert": True,
    "two_webgl_views": True,
    "console_errors": errors,
}
with (OUT / "BROWSER_CHECK.json").open("x", encoding="utf-8") as stream:
    json.dump(result, stream, ensure_ascii=False, indent=2)
assert not errors, errors
print("CONSOLE HOME + BOTH FALL DEMOS PASS")

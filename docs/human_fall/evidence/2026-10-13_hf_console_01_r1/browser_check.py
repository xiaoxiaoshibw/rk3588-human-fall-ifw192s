import http.server
import json
from pathlib import Path
import sys
import threading
from functools import partial
from playwright.sync_api import sync_playwright

ROOT=Path.cwd();OUT=Path(__file__).parent
sys.path.insert(0,str(ROOT/'pc_apps/console'))
import console_gui as G
replay=G._start_replay_server();fall=G._start_fall_server();assert fall
shell=http.server.ThreadingHTTPServer(('127.0.0.1',0),partial(http.server.SimpleHTTPRequestHandler,directory=str(ROOT/'pc_apps/console')))
threading.Thread(target=shell.serve_forever,daemon=True).start()
errors=[]
with sync_playwright() as pw:
    browser=pw.chromium.launch(channel='msedge',headless=True)
    page=browser.new_page(viewport={'width':1640,'height':1080})
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.on('console',lambda m:errors.append(m.text) if m.type=='error' else None)
    page.goto('http://127.0.0.1:%d/%s'%(shell.server_address[1],G._shell_url(replay,fall)),wait_until='networkidle')
    page.screenshot(path=str(OUT/'CONSOLE_HOME.png'),full_page=True)
    card=page.locator('.card').filter(has=page.get_by_text('骨架与倒地检测',exact=True))
    assert card.count()==1;card.click()
    frame=page.frame_locator('#f');frame.locator('#status').wait_for()
    frame.locator('[data-frame="72"]').click()
    frame.locator('#status').filter(has_text='帧 72 /').wait_for()
    assert frame.locator('canvas').count()==2
    assert frame.locator('#track').inner_text()=='REAL-01'
    assert frame.locator('#alert').inner_text()=='告警保持'
    page.screenshot(path=str(OUT/'CONSOLE_EMBEDDED_ALARM.png'),full_page=True)
    iframe_src=page.locator('#f').get_attribute('src');assert iframe_src=='http://127.0.0.1:%d/'%fall
    page.locator('#back').click();card.click()
    assert frame.locator('#frame').input_value()=='72'
    frame.locator('#session').select_option('cap_20261013_131958')
    frame.locator('#status').filter(has_text='帧 0 / 96').wait_for()
    assert frame.locator('#track').inner_text()=='未锁定'
    browser.close()
shell.shutdown();shell.server_close()
with (OUT/'BROWSER_CHECK.json').open('x',encoding='utf8') as f:
    json.dump({'replay_port':replay,'fall_port':fall,'iframe_src':iframe_src,'retained_frame_after_back':72,'empty_no_lock':True,'errors':errors,'browser':'actual headless Edge, console shell + live iframe servers'},f,ensure_ascii=False,indent=2)
assert not errors,errors
print('CONSOLE IFRAME PASS')

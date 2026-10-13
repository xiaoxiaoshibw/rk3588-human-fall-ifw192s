"""Real Chromium UI test; isolated headless fallback when CUA cannot initialize."""
import json
from playwright.sync_api import sync_playwright
from prepare import OUT

OUT=OUT/'browser_r2'
OUT.mkdir(exist_ok=False)

records=[];errors=[]
with sync_playwright() as pw:
    browser=pw.chromium.launch(channel='msedge',headless=True)
    page=browser.new_page(viewport={'width':1450,'height':1000})
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.on('console',lambda m:errors.append(m.text) if m.type=='error' else None)
    page.goto('http://127.0.0.1:8929/',wait_until='networkidle')
    page.wait_for_function("document.getElementById('status').textContent.includes('startup_background')")
    records.append({'action':'initial','status':page.locator('#status').inner_text()})
    assert page.locator('canvas').count()==2
    page.locator('#frame').fill('21');page.locator('#frame').press('Tab')
    page.wait_for_function("document.getElementById('status').textContent.startsWith('帧 21 /')")
    assert page.locator('#track').inner_text()=='REAL-01'
    page.locator('#side').click();page.screenshot(path=str(OUT/'BROWSER_UPRIGHT.png'),full_page=True)
    records.append({'action':'upright21','status':page.locator('#status').inner_text(),'state':page.locator('#state').inner_text()})
    page.locator('#alarm').click()
    page.wait_for_function("document.getElementById('status').textContent.startsWith('帧 72 /')")
    assert page.locator('#state').inner_text()=='疑似倒地'
    page.screenshot(path=str(OUT/'BROWSER_ALARM_SIDE.png'),full_page=True)
    page.locator('#top').click();page.screenshot(path=str(OUT/'BROWSER_ALARM_TOP.png'),full_page=True)
    records.append({'action':'alarm72','status':page.locator('#status').inner_text(),'height':page.locator('#height').inner_text()})
    page.locator('#mode').select_option('room');page.screenshot(path=str(OUT/'BROWSER_ALARM_ROOM.png'),full_page=True)
    page.locator('#next').click();page.wait_for_function("document.getElementById('status').textContent.startsWith('帧 73 /')")
    page.locator('#prev').click();page.wait_for_function("document.getElementById('status').textContent.startsWith('帧 72 /')")
    page.locator('#play').click();page.wait_for_function("Number(document.getElementById('frame').value)>74")
    page.locator('#play').click();assert page.locator('#play').inner_text()=='播放'
    page.locator('#frame').fill('150');page.locator('#frame').press('Tab')
    page.wait_for_function("document.getElementById('status').textContent.startsWith('帧 150 /')")
    page.locator('#fit').click();page.screenshot(path=str(OUT/'BROWSER_RECOVERY.png'),full_page=True)
    assert page.locator('#state').inner_text()=='直立'
    records.append({'action':'recovery150','status':page.locator('#status').inner_text(),'state':page.locator('#state').inner_text()})
    page.locator('#reset').click();page.wait_for_function("document.getElementById('status').textContent.startsWith('帧 0 /')")
    assert page.locator('#events').inner_text().startswith('1 次')
    for query in ['i=-1','i=164','i=NaN','i=1&i=2']:
        res=page.request.get('http://127.0.0.1:8929/api/frame?'+query);assert res.status==400
    with (OUT/'BROWSER_CHECK.json').open('x',encoding='utf8') as f:
        json.dump({'records':records,'errors':errors,'invalid_requests':4,'browser':'headless Edge Chromium','reason':'CUA initialization failed: missing kernel assets path; actual WebGL browser rendering'},f,ensure_ascii=False,indent=2)
    browser.close()
assert not errors,errors
print('BROWSER PASS',len(records),'records / 4 invalid HTTP checks')

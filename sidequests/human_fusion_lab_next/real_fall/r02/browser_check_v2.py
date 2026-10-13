import json
from playwright.sync_api import sync_playwright
from paths import OUT

OUT=OUT/'browser_v2'
OUT.mkdir(exist_ok=False)
records=[];errors=[]
with sync_playwright() as pw:
    browser=pw.chromium.launch(channel='msedge',headless=True)
    page=browser.new_page(viewport={'width':1640,'height':1080})
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.on('console',lambda m:errors.append(m.text) if m.type=='error' else None)
    page.goto('http://127.0.0.1:8931/',wait_until='networkidle')
    page.wait_for_function("document.getElementById('status').textContent.startsWith('帧 0 /')")
    assert page.locator('canvas').count()==2
    for fi,name in [(10,'MIXTURE_RISK'),(21,'UPRIGHT'),(43,'DESCENT'),(72,'ALARM'),(97,'HOLD'),(109,'AMBIGUOUS'),(130,'RECOVER'),(150,'UPRIGHT_AGAIN')]:
        page.locator('#frame').fill(str(fi));page.locator('#frame').press('Tab')
        page.wait_for_function("document.getElementById('status').textContent.startsWith('帧 %d /')"%fi)
        page.locator('#side').click();page.screenshot(path=str(OUT/('BROWSER_'+name+'.png')),full_page=True)
        records.append({'frame':fi,'state':page.locator('#state').inner_text(),'nodes':page.locator('#nodeCount').inner_text(),'alert':page.locator('#alert').inner_text()})
        assert page.locator('#track').inner_text()=='REAL-01'
        if fi in (72,97):assert page.locator('#alert').inner_text()=='告警保持'
        if fi==109:assert page.locator('#nodeCount').inner_text()=='0 / 13'
    page.locator('[data-frame="72"]').click();page.wait_for_function("document.getElementById('status').textContent.startsWith('帧 72 /')")
    page.locator('tr[data-key="CHEST"]').click();assert page.locator('tr[data-key="CHEST"]').get_attribute('class')=='selected'
    page.locator('#top').click();page.screenshot(path=str(OUT/'BROWSER_ALARM_TOP.png'),full_page=True)
    page.locator('#bones').uncheck();page.locator('#bones').check();page.locator('#box').uncheck();page.locator('#box').check()
    page.locator('#mode').select_option('room');page.screenshot(path=str(OUT/'BROWSER_ALARM_ROOM.png'),full_page=True)
    page.locator('#next').click();page.wait_for_function("document.getElementById('status').textContent.startsWith('帧 73 /')")
    page.locator('#prev').click();page.wait_for_function("document.getElementById('status').textContent.startsWith('帧 72 /')")
    page.locator('#play').click();page.wait_for_function("Number(document.getElementById('frame').value)>74");page.locator('#play').click()
    assert page.locator('#play').inner_text()=='播放全过程'
    page.locator('#session').select_option('cap_20261013_131958');page.wait_for_function("document.getElementById('status').textContent.startsWith('帧 0 / 96')")
    assert page.locator('#track').inner_text()=='未锁定';assert page.locator('#alert').inner_text()=='无'
    page.screenshot(path=str(OUT/'BROWSER_EMPTY.png'),full_page=True)
    page.locator('[data-frame="21"]').click();page.wait_for_function("document.getElementById('status').textContent.startsWith('帧 21 / 163')")
    page.locator('#reset').click();page.wait_for_function("document.getElementById('status').textContent.startsWith('帧 0 / 163')")
    for query in ['sid=bad&i=0','sid=cap_20261013_094333&i=-1','sid=cap_20261013_094333&i=164','sid=cap_20261013_094333&i=1&i=2']:
        res=page.request.get('http://127.0.0.1:8931/api/frame?'+query);assert res.status==400
    response=page.request.get('http://127.0.0.1:8931/api/frame?sid=cap_20261013_094333&i=72').json()
    node=response['row']['skeleton']['nodes']['CHEST'];assert len(node['support_xyz'])==node['support_n']
    with (OUT/'BROWSER_CHECK.json').open('x',encoding='utf8') as f:
        json.dump({'records':records,'errors':errors,'invalid400':4,'browser':'actual headless Edge WebGL; CUA unavailable in previous turn'},f,ensure_ascii=False,indent=2)
    browser.close()
assert not errors,errors
print('Browser process PASS',len(records),'stages / empty / controls / node support')

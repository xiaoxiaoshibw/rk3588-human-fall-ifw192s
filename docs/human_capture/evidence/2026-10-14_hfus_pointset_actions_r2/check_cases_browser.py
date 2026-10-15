import sys
from pathlib import Path
from playwright.sync_api import sync_playwright
H=Path('D:/Code/ldiar/sidequests/human_fusion_lab_next/pointset/r01');sys.path.insert(0,str(H))
from research_actions import E, read, dump

diag=read(E/'DIAGNOSIS.json');changes=read(E/'DIFFICULT_FRAME_CHANGES.json')
keys={(c['sid'],c['fi']) for c in diag['cases'] if c['roles'][0]!='AXIS_OR_NEIGHBOR'}
keys.update((c['sid'],c['fi']) for c in diag['ambiguity_frames'])
keys.update((c['sid'],c['fi']) for v in ['point20','component20','low20'] for c in changes[v]['new_axis_missing'])
rows=[];errors=[]
with sync_playwright() as pw:
    browser=pw.chromium.launch(channel='msedge');page=browser.new_page(viewport={'width':1600,'height':1100})
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.goto('http://127.0.0.1:8944/');page.wait_for_function('record!==null')
    page.locator('#diagnose').check();page.wait_for_function('diagnostic!==null')
    for sid,fi in sorted(keys):
        page.evaluate('async ([sid,f])=>{if(current.session_id!==sid)await choose(catalog.sessions.find(s=>s.session_id===sid));await loadFrame(f)}',[sid,fi])
        assert page.evaluate('([s,f])=>record?.session_id===s&&fi===f&&diagnostic?.sid===s&&diagnostic?.fi===f',[sid,fi])
        for view in ['front','top','orbit']:page.locator('#'+view).click()
        rows.append(page.evaluate('({sid:record.session_id,fi,target:obj?.point_count??0,nodes:Object.values(obj?.skeleton.nodes??{}).filter(n=>n.valid).length,source_sha256:record.source_sha256})'))
    page.evaluate("async ()=>{await choose(catalog.sessions.find(s=>s.session_id==='cap_20261013_082906'));await loadFrame(90)}")
    page.locator('#variant').select_option('axis');page.wait_for_function("experiment?.variant==='axis'")
    assert '方向参考 f' in page.locator('#metrics').inner_text()
    assert page.locator('#experimentDownload').is_visible()
    response=page.request.get('http://127.0.0.1:8944'+page.locator('#experimentDownload').get_attribute('href'))
    assert response.ok and response.json()['variant']=='axis'
    for suffix in ['sid=not-a-session&fi=0&variant=axis','sid=cap_20261013_082623&fi=9999&variant=axis','sid=cap_20261013_082623&fi=0&variant=../../bad']:
        assert page.request.get('http://127.0.0.1:8944/api/experiment?dataset=actions&'+suffix).status==400
    assert page.request.get('http://127.0.0.1:8944/api/diagnostic?dataset=actions&sid=cap_20261013_131958&fi=1').status==400
    assert not errors,errors
    dump(E/'BROWSER_ALL_DIAGNOSTIC_CASES.json',{'status':'PASS','cases':rows,'views':['front','top','orbit'],
         'all_79_original_ambiguities':True,'new_hard_frames':True,'malformed_api_refused':True,'experimental_export_binding':True,'errors':errors})
    browser.close()

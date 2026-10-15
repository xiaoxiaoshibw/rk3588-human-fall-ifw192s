"""Actual r01 page and console iframe, without creating human labels."""
import json
import sys
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from playwright.sync_api import sync_playwright

HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3]
E=ROOT/'docs/human_capture/evidence/2026-10-14_hfus_pointset_actions_r1'


if __name__=='__main__':
    console=ROOT/'pc_apps/console'
    sys.path.insert(0,str(console))
    import console_gui
    port=console_gui._start_fall_server()
    shell=ThreadingHTTPServer(('127.0.0.1',0),partial(SimpleHTTPRequestHandler,directory=str(console)))
    threading.Thread(target=shell.serve_forever,daemon=True).start()
    with sync_playwright() as pw:
        browser=pw.chromium.launch(channel='msedge');page=browser.new_page(viewport={'width':1500,'height':1050})
        errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto('http://127.0.0.1:8944/')
        page.wait_for_function('obj !== null && record !== null')
        assert page.locator('#dataset').input_value()=='actions'
        assert page.locator('#mode').input_value()=='body_3d'
        assert not page.locator('#parts').is_visible()
        assert not page.locator('#context').is_checked()
        assert page.locator('#sessions button').count()==9
        page.screenshot(path=str(E/'CENTRAL_STANDING_V2.png'),full_page=True)
        records=[]
        for button in page.locator('#sessions button').all():
            sid=button.get_attribute('data-sid');button.click()
            page.wait_for_function('(sid)=>record !== null && record.session_id===sid',arg=sid)
            records.append(page.evaluate('({sid:record.session_id,frame:fi,target:obj?.point_count??0,state:record.posture.state})'))
        page.locator('#sessions button[data-sid="cap_20261013_082829"]').click()
        page.wait_for_function("record !== null && record.session_id==='cap_20261013_082829'")
        page.locator('#time').fill('30');page.locator('#time').dispatch_event('input')
        page.wait_for_function('record !== null && fi===30')
        assert page.evaluate('obj.point_count')>300
        page.locator('#orbit').click();page.screenshot(path=str(E/'CENTRAL_SUPINE_V2.png'),full_page=True)
        page.locator('#play').click();page.wait_for_function('fi>=33 && record !== null');page.locator('#play').click()
        page.locator('#context').check();page.screenshot(path=str(E/'FOREGROUND_CONTEXT_COMPARE_V2.png'),full_page=True)
        page.locator('#context').uncheck()
        page.goto('http://127.0.0.1:8944/?dataset=actions&sid=cap_20261013_082623&fi=145')
        page.wait_for_function('record !== null && fi===145 && obj !== null')
        assert page.evaluate('record.posture.event')=='DOWN_POSTURE_CANDIDATE'
        page.screenshot(path=str(E/'CENTRAL_DOWN_EVENT_V2.png'),full_page=True)
        page.locator('#dataset').select_option('legacy')
        page.wait_for_function("catalog !== null && catalog.sessions[0].session_id==='cap_20261010_175227' && record !== null")
        assert page.locator('#sessions button').count()==9
        assert page.locator('#parts').is_visible()
        assert page.evaluate('obj !== null')
        shell_url='http://127.0.0.1:%d/console.html?replay_port=8901&fall_port=%d'%(shell.server_port,port)
        page.goto(shell_url);page.locator('#apps .card').count()
        # The existing console renders its app cards from APPS. Use the actual named card.
        page.get_by_text('骨架与倒地检测',exact=True).click()
        frame=page.frame_locator('#f')
        frame.locator('#sessions button').first.wait_for()
        assert frame.locator('#dataset').input_value()=='actions'
        frame.locator('#cloud').wait_for()
        page.screenshot(path=str(E/'CONSOLE_POINTSET_IFRAME_V2.png'),full_page=True)
        assert not errors,errors
        with (E/'BROWSER_ACTIONS_V2.json').open('x',encoding='utf8') as f:json.dump({'status':'PASS','nine_sessions':records,
             'default':'body_3d_only_no_background','legacy_preserved':True,'console_dynamic_port':port,
             'console_iframe':'actual local console page and same-process backend','play_seek_event':True,
             'human_labels_written':False,'errors':errors},f,ensure_ascii=False,indent=2)
        browser.close()
    shell.shutdown();shell.server_close()

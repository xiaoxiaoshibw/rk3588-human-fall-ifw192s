"""Actual Edge r01 page + console iframe; synthetic gap is explicitly isolated."""
import copy
import json
import sys
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

from playwright.sync_api import sync_playwright
from research_actions import ROOT, E, read, dump


def main():
    screenshots=E/'browser_attempt_02';screenshots.mkdir()
    console=ROOT/'pc_apps/console';sys.path.insert(0,str(console));import console_gui
    port=console_gui._start_fall_server()
    shell=ThreadingHTTPServer(('127.0.0.1',0),partial(SimpleHTTPRequestHandler,directory=str(console)))
    threading.Thread(target=shell.serve_forever,daemon=True).start()
    checks=[];errors=[]
    with sync_playwright() as pw:
        browser=pw.chromium.launch(channel='msedge');page=browser.new_page(viewport={'width':1700,'height':1250})
        page.on('pageerror',lambda e:errors.append(str(e)))
        def ready(sid=None,fi=None):
            page.wait_for_function('([s,f])=>record!==null&&(!s||record.session_id===s)&&(f===null||record.frame_index===f)',arg=[sid,fi])
        page.goto('http://127.0.0.1:8944/');ready()
        assert page.locator('#variant').input_value()=='baseline'
        assert page.request.get('http://127.0.0.1:8944/api/version').json()['page_version'].endswith('/R2')
        assert page.locator('#sessions button').count()==9
        sessions=[]
        for b in page.locator('#sessions button').all():
            sid=b.get_attribute('data-sid');b.click();ready(sid)
            sessions.append(page.evaluate('({sid:record.session_id,fi,points:obj?.point_count??0})'))
        assert sessions[-1]['points']==0 and sessions[-1]['fi']==2
        checks.append('all nine sessions including real empty missing target')
        page.goto('http://127.0.0.1:8944/?dataset=actions&sid=cap_20261013_082623&fi=192');ready('cap_20261013_082623',192)
        page.locator('#diagnose').check();page.wait_for_function('diagnostic!==null&&diagnostic.fi===192')
        assert page.locator('#layers canvas').count()==5
        page.locator('#top').click();page.screenshot(path=str(screenshots/'R2_F192_BASELINE_FIVE_LAYERS.png'),full_page=True)
        page.locator('#variant').select_option('component20');page.wait_for_function("experiment?.variant==='component20'&&fi===192")
        assert page.evaluate('experiment.stats.added_count')==214
        assert page.evaluate('experiment.stats.valid_nodes')==8
        assert page.evaluate('baselineRecord.body_3d[0].point_count')==1145
        page.screenshot(path=str(screenshots/'R2_F192_COMPONENT_COMPARE.png'),full_page=True)
        for v in ['point12','point20','low20','axis','baseline']:
            page.locator('#variant').select_option(v)
            page.wait_for_function('(v)=>record!==null&&(v==="baseline"?experiment===null:experiment?.variant===v)',arg=v)
        checks.append('all single-factor choices and rollback to baseline')
        # Synchronized rotations and actual frame-local source hit inspection.
        page.locator('#orbit').click()
        before=page.evaluate('yaw');c=page.locator('#layer_target').bounding_box()
        page.mouse.move(c['x']+80,c['y']+80);page.mouse.down();page.mouse.move(c['x']+110,c['y']+95);page.mouse.up()
        assert page.evaluate('yaw')!=before
        pt=page.evaluate("(()=>{const c=$('layer_target'),q=layerProject(diagnostic.layers.target.points[0],c),r=c.getBoundingClientRect();return [r.left+q[0],r.top+q[1]]})()")
        page.mouse.click(*pt);assert 'source' in page.locator('#sourceHover').inner_text()
        response=page.request.get('http://127.0.0.1:8944/api/source-members?sid=cap_20261013_082623&fi=192&dataset=actions')
        assert response.ok and response.body().startswith(b'PK')
        checks.append('synchronized 3D orbit, source-index click, full NPZ export')
        page.locator('#diagnose').uncheck();page.wait_for_function('diagnostic===null&&record!==null')
        page.locator('#time').fill('193');page.locator('#time').dispatch_event('input');ready('cap_20261013_082623',193)
        page.locator('#play').click();page.wait_for_function('fi>=196&&record!==null');page.locator('#play').click()
        assert page.locator('#play').inner_text()=='播放'
        fi=page.evaluate('fi');page.wait_for_timeout(350);assert page.evaluate('fi')==fi
        checks.append('seek and play/pause do not advance after pause')
        changes=read(E/'DIFFICULT_FRAME_CHANGES.json')
        fixed=changes['axis']['resolved_axis_missing'][0]
        page.goto(f"http://127.0.0.1:8944/?sid={fixed['sid']}&fi={fixed['fi']}");ready(fixed['sid'],fixed['fi'])
        assert page.evaluate('Object.values(obj.skeleton.nodes).filter(n=>n.valid).length')==0
        page.locator('#variant').select_option('axis');page.wait_for_function("experiment?.variant==='axis'")
        assert page.evaluate('Object.values(obj.skeleton.nodes).filter(n=>n.valid).length')>0
        assert page.evaluate('obj.skeleton.predicted_nodes.length')==0
        page.screenshot(path=str(screenshots/'R2_HISTORY_CURRENT_SUPPORT.png'),full_page=True)
        # Existing ambiguity and all new hard frames remain visible and inspectable.
        hard=set((r['sid'],r['fi']) for v in ['point20','component20','low20'] for r in changes[v]['new_axis_missing'])
        for sid,fi in sorted(hard):
            page.goto(f'http://127.0.0.1:8944/?sid={sid}&fi={fi}');ready(sid,fi)
            page.locator('#variant').select_option('component20');page.wait_for_function("experiment?.variant==='component20'")
            assert page.evaluate('Object.values(obj.skeleton.nodes).every(n=>!n.valid)')
            page.screenshot(path=str(screenshots/f'R2_NEW_HARD_{sid}_{fi}.png'),full_page=True)
        page.goto('http://127.0.0.1:8944/?sid=cap_20261013_082623&fi=192');ready('cap_20261013_082623',192)
        assert page.evaluate('Object.values(obj.skeleton.nodes).every(n=>!n.valid)')
        checks.append('baseline ambiguity, supported historical direction, all three new hard frames')
        page.locator('header details').evaluate('(e)=>e.open=true')
        page.locator('#reviewQueue a').last.click();ready('cap_20261013_082623',145)
        assert page.evaluate('record.posture.event')=='DOWN_POSTURE_CANDIDATE' and not page.evaluate('record.posture.confirmed')
        checks.append('actual event link navigates to current candidate without confirmed fall')
        # Browser-only fixture: source files and diagnostic labels are never written.
        def gap(route):
            data=route.fetch().json();data['body_3d']=[];data['posture']={'state':'LOST','event':None,'confirmed':False,'time_reset':True}
            data['t_sec']+=2.;route.fulfill(json=data)
        page.route('**/api/frame?*',gap)
        page.locator('#next').click();ready('cap_20261013_082623',146)
        assert page.evaluate('obj===null') and '时间gap' in page.locator('#metrics').inner_text()
        page.evaluate("$('message').textContent='SYNTHETIC browser fixture: missing target and time gap, not measured evidence'")
        page.screenshot(path=str(screenshots/'SYNTHETIC_BROWSER_GAP.png'),full_page=True);page.unroute('**/api/frame?*',gap)
        checks.append('SYNTHETIC gap/missing UI; real causal reset in unit test')
        page.locator('#dataset').select_option('legacy');page.wait_for_function("catalog?.sessions[0].session_id==='cap_20261010_175227'&&record!==null")
        assert page.locator('#parts').is_visible() and page.locator('#researchControls').is_hidden()
        page.locator('#dataset').select_option('actions');ready('cap_20261013_082623',145)
        checks.append('legacy/action switch preserves original annotation flow')
        page.goto(f'http://127.0.0.1:{shell.server_port}/console.html?replay_port=8901&fall_port={port}')
        page.get_by_text('骨架与倒地检测',exact=True).click();frame=page.frame_locator('#f');frame.locator('#variant').wait_for()
        assert frame.locator('#variant').input_value()=='baseline';frame.locator('#diagnose').check()
        frame.locator('#layer_target').wait_for()
        inner=next(f for f in page.frames if f.url.startswith(f'http://127.0.0.1:{port}/'))
        inner.wait_for_function('diagnostic!==null')
        page.screenshot(path=str(screenshots/'R2_CONSOLE_ORIGINAL_PAGE.png'),full_page=True)
        checks.append('actual console shell iframe loads same r01 with baseline default and research')
        assert not errors,errors
        dump(E/'BROWSER_R2.json',{'status':'PASS','browser':'actual Microsoft Edge','sessions':sessions,'checks':checks,'errors':errors,
             'console_dynamic_port':port,'labels_written':False,'synthetic_gap_is_not_real_evidence':True,'new_default_adopted':False,
             'screenshots_directory':str(screenshots)})
        browser.close()
    shell.shutdown();shell.server_close()


if __name__=='__main__':main()

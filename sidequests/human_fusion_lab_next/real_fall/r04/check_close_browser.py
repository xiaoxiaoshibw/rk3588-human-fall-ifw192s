"""Real Edge interaction checks on existing pages, no labels saved."""
import argparse
import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright
from close_data_bg import HERE,PS,dump


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',required=True);args=p.parse_args();out=Path(args.out).resolve()
    out.mkdir(parents=True,exist_ok=True);children=[]
    with (out/'BROWSER_SERVERS.log').open('x',encoding='utf8') as log:
        try:
            for script,port in [(HERE/'server.py',8932),(PS/'server.py',8942)]:
                child=subprocess.Popen([sys.executable,'-B','-W','error',str(script),'--port',str(port)],cwd=script.parent,
                                       stdout=log,stderr=log,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                children.append(child)
                for _ in range(120):
                    if child.poll() is not None:raise RuntimeError('server exited')
                    try:
                        with urllib.request.urlopen(f'http://127.0.0.1:{port}/',timeout=1) as r:
                            if r.status==200:break
                    except OSError:time.sleep(.25)
                else:raise RuntimeError('server startup timeout')
            with sync_playwright() as pw:
                browser=pw.chromium.launch(channel='msedge');page=browser.new_page(viewport={'width':1440,'height':1050})
                errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
                page.goto('http://127.0.0.1:8932/');page.wait_for_function('current!==null')
                info=page.request.get('http://127.0.0.1:8932/api/info').json()
                assert len(info['sessions']['cap_20261013_094333']['events'])==1
                for frame in [47,109,118,72]:
                    page.locator('#frame').fill(str(frame));page.locator('#frame').dispatch_event('change')
                    page.wait_for_function(f'current.row.frame==={frame}')
                    for view in ['side','top','fit']:page.locator('#'+view).click()
                    r=page.request.get(f'http://127.0.0.1:8932/api/support?sid=cap_20261013_094333&i={frame}&key=CHEST')
                    assert r.status==200 and r.json()['measured'] and r.json()['points']
                page.screenshot(path=str(out/'R04_WEAK_AND_EVENT.png'))
                page.locator('#reset').click();page.wait_for_function('current.row.frame===0')
                page.locator('#play').click();page.wait_for_function('current.row.frame>=3');page.locator('#play').click()
                paused=page.evaluate('current.row.frame');page.wait_for_timeout(350);assert page.evaluate('current.row.frame')==paused
                fps=page.evaluate('''() => new Promise(resolve=>{let n=0;const start=performance.now();function tick(t){n++;if(t-start<1500)requestAnimationFrame(tick);else resolve(n*1000/(t-start));}requestAnimationFrame(tick);})''')
                again=page.request.get('http://127.0.0.1:8932/api/info').json();assert again==info
                for query in ['sid=bad&i=0','sid=cap_20261013_094333&i=-1','sid=cap_20261013_094333&i=164','sid=cap_20261013_094333&i=0&i=1','sid=cap_20261013_094333&i=0&mode=bad']:
                    assert page.request.get('http://127.0.0.1:8932/api/frame?'+query).status==400
                page.goto('http://127.0.0.1:8942/?sid=cap_20261010_180557&fi=10');page.wait_for_function('record?.frame_index===10')
                page.locator('header details').evaluate('(e)=>e.open=true')
                page.wait_for_function('document.querySelector("#reviewQueue").textContent.includes("155")')
                assert '31 个未知点' in page.locator('#reviewQueue').inner_text()
                assert '155 条比较行' in page.locator('#reviewQueue').inner_text()
                assert page.locator('#reviewQueue a').evaluate_all('(links)=>links.every(a=>a.origin===location.origin)')
                assert page.evaluate('record.roi_3d.length')==0
                page.locator('#mode').select_option('full_3d');page.wait_for_function('obj!==null')
                assert 'GT最佳簇上界' in page.locator('#metrics').inner_text()
                assert '当前所选簇覆盖' in page.locator('#metrics').inner_text()
                page.screenshot(path=str(out/'REVIEW_QUEUE_S8.png'),full_page=True)
                q=page.request.get('http://127.0.0.1:8942/api/review-queue').json()
                assert q['status']=='PROPOSED' and not q['human_review_completed']
                assert page.request.post('http://127.0.0.1:8942/api/parts',data={'schema_version':'wrong'}).status==400
                # SYNTHETIC UI race only: intercept POST in memory, never submit any human label.
                page.evaluate('''() => {const realFetch=window.fetch;window.fetch=(url,opts)=>opts?.method==='POST'?new Promise(resolve=>{window.syntheticSaveResolve=()=>resolve(new Response(JSON.stringify({saved:true}),{status:200,headers:{'Content-Type':'application/json'}}));}):realFetch(url,opts);selected=new Set([obj.display_source_indices[0]]);}''')
                page.locator('#reviewer').fill('SYNTHETIC_UI_TEST_NO_LABEL_WRITE')
                page.locator('#save').click();page.wait_for_function('typeof window.syntheticSaveResolve==="function"')
                page.locator('#next').click();page.wait_for_function('record?.frame_index===11')
                page.evaluate("selected=new Set([obj.display_source_indices[0]]);document.querySelector('#part').value='HEAD'")
                before=page.evaluate('reviewedParts.size');page.evaluate('window.syntheticSaveResolve()');page.wait_for_timeout(100)
                assert page.evaluate('reviewedParts.size')==before
                assert not errors,errors
                dump(out/'BROWSER_CHECK.json',{'passed':True,'pageerrors':errors,'render_callback_fps':fps,
                     'checks':['47/109/118 current support','72 prototype immutable','seek/reset/pause no event duplication',
                               'invalid query 400','S8 ROI/full preserved','deep link','31 POINT /155 ROW separated','runtime vs oracle displayed','SYNTHETIC_UI_RACE: pending save cannot color next frame'],
                     'human_labels_written':False,'URLs':['http://127.0.0.1:8932/','http://127.0.0.1:8942/'],
                     'command':sys.argv,'console_packaging':'NOT_RUN_OUT_OF_CURRENT_AUTHORIZATION'})
                browser.close()
        finally:
            for child in children:
                child.terminate();child.wait(timeout=10)
    print('real browser checks PASS')

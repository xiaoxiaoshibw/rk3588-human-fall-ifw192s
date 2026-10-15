"""Real headed Edge interaction and rendered multiview inspection, no GT writes."""
from playwright.sync_api import sync_playwright
import sys
from research_r3 import E, RESULT
from actions import read, dump, sha, HERE, OUT

def main():
    signed='--signed' in sys.argv;selected_variant='r3_signed' if signed else 'r3'
    folder=E/('browser_signed_01' if signed else 'browser_attempt_03');folder.mkdir();errors=[];rows=[]
    comparison=read(E/'EXPERIMENT_COMPARISON.json');study=read(E/'DIAGNOSTIC_STUDY.json')
    hard=[('cap_20261013_082623',192),('cap_20261013_082717',140),('cap_20261013_082623',119),('cap_20261013_082623',232)]
    catalog=read(OUT/'catalog.json');limits={r['session_id']:r['frame_count'] for r in catalog['sessions']}
    neighbors=[(r['sid'],f) for r in study['remaining_axis_missing'] for f in [r['fi']-1,r['fi'],r['fi']+1] if 0<=f<limits[r['sid']]]
    cases=list(dict.fromkeys(hard+[(r['sid'],r['fi']) for r in study['rows']]+neighbors+[(r['sid'],r['fi']) for r in comparison['frames']['r3'] if r['new_axis_missing']]))
    with sync_playwright() as pw:
        browser=pw.chromium.launch(channel='msedge',headless=False)
        page=browser.new_page(viewport={'width':1640,'height':1250});page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto('http://127.0.0.1:8944/')
        page.wait_for_function('record!==null')
        assert page.locator('#variant').input_value()=='baseline'
        assert page.request.get('http://127.0.0.1:8944/api/version').json()['default']=='R1_BASELINE'
        for b in page.locator('#sessions button').all():
            sid=b.get_attribute('data-sid');b.click();page.wait_for_function('(s)=>record?.session_id===s',arg=sid)
            if sid.endswith('131958'): assert page.evaluate('obj===null&&fi===2')
        for case_index,(sid,fi) in enumerate(cases):
            # Bound renderer lifetime during repeated large source-bound navigation.
            previous_page=page;page=browser.new_page(viewport={'width':1640,'height':1250})
            page.on('pageerror',lambda e:errors.append(str(e)));previous_page.close()
            page.goto(f'http://127.0.0.1:8944/?sid={sid}&fi={fi}&variant={selected_variant}')
            page.wait_for_function('([s,f,v])=>record?.session_id===s&&record.frame_index===f&&experiment?.variant===v',arg=[sid,fi,selected_variant])
            page.locator('#compare').check();page.wait_for_function('r2CompareRecord!==null&&record!==null')
            for view in ['front','top','orbit']:
                page.locator('#'+view).click();page.wait_for_timeout(80)
                if (sid,fi) in hard or (sid.endswith('082906') and fi==96):
                    page.screenshot(path=str(folder/f'{sid}_{fi}_{view}.png'),full_page=True)
            actual=page.evaluate('({sid:record.session_id,fi,points:obj?.point_count,nodes:obj?Object.values(obj.skeleton.nodes).filter(n=>n.valid).length:0,axis:obj?.skeleton.axis,source:obj?.skeleton.direction?.source,added:experiment.stats.added_count,rejected:experiment.connection_evidence.reduce((s,e)=>s+e.rejected_source_indices.length,0),r1:baselineRecord.body_3d[0]?.point_count,r2:r2CompareRecord.body_3d[0]?.point_count,predicted:obj?.skeleton.predicted_nodes})')
            expected=read(RESULT/selected_variant/sid/f'{fi:04d}.json');assert actual['added']==expected['stats']['added_count'];assert actual['predicted']==[]
            rows.append(actual)
            with (folder/'case_progress.jsonl').open('a',encoding='utf8') as f:
                import json
                f.write(json.dumps(actual)+'\n')
            if case_index%10==0:print('BROWSER',case_index,len(cases),sid,fi,flush=True)
        sid,fi=hard[0];page.goto(f'http://127.0.0.1:8944/?sid={sid}&fi={fi}')
        page.wait_for_function('record?.frame_index===192')
        page.locator('#compare').check();page.wait_for_function('r2CompareRecord!==null&&record!==null')
        for v in ['component20','r3_graph','r3_background','r3_temporal','r3_combined','r3','r3_feedback','r3_signed','r3_signed_feedback','axis','baseline']:
            page.locator('#variant').select_option(v);page.wait_for_function('(v)=>record!==null&&(v==="baseline"?experiment===null:experiment?.variant===v)',arg=v)
        page.locator('#variant').select_option(selected_variant);page.wait_for_function('(v)=>experiment?.variant===v',arg=selected_variant)
        page.locator('#diagnose').check();page.wait_for_function('diagnostic!==null&&record!==null')
        assert page.locator('#layers canvas').count()==5
        c=page.locator('#cloud').bounding_box();before=page.evaluate('[yaw,pitch]')
        page.mouse.move(c['x']+80,c['y']+80);page.mouse.down();page.mouse.move(c['x']+140,c['y']+100);page.mouse.up()
        assert before!=page.evaluate('[yaw,pitch]')
        pt=page.evaluate("(()=>{const p=projected[0].q,r=$('cloud').getBoundingClientRect();return [r.left+p[0],r.top+p[1]]})()")
        page.mouse.click(*pt);assert 'source' in page.locator('#evidenceNote').inner_text()
        response=page.request.get('http://127.0.0.1:8944'+page.locator('#experimentDownload').get_attribute('href'));assert response.ok and response.json()['identity']=='UNKNOWN'
        for b,(jump_sid,jump_f) in zip(page.locator('#hardJumps button').all(),hard):
            b.click();page.wait_for_function('([s,f])=>record!==null&&record.session_id===s&&record.frame_index===f',arg=[jump_sid,jump_f])
        page.locator('#play').click();page.wait_for_function('fi>=235&&record!==null');page.locator('#play').click();pause=page.evaluate('fi');page.wait_for_timeout(400);assert page.evaluate('fi')==pause
        for url in ['/api/experiment?sid=cap_20261013_082623&fi=192&variant=../r3','/api/experiment?sid=cap_20261013_131958&fi=0&variant=r3','/api/experiment?sid=unknown&fi=0&variant=r3']:
            assert page.request.get('http://127.0.0.1:8944'+url).status==400
        page.locator('#dataset').select_option('legacy');page.wait_for_function('record!==null&&$("mode").value==="full_3d"');assert page.locator('#r3Controls').is_hidden()
        assert not errors
        dump(E/('BROWSER_SIGNED.json' if signed else 'BROWSER_R3.json'),{'status':'PASS','headed_real_browser':'Microsoft Edge','cases':rows,'views':['front','top','orbit'],
            'checks':['R1 default retained','all sessions / real empty HOLDOUT','R1/R2/R3 same frame','all R3 ablations / rollback',
            'pointer orbit / source click','hard frame one-click navigation','seek play pause','JSON full-source export','invalid input refused','legacy preserved'],
            'errors':errors,'source_sha256':{n:sha(HERE/n) for n in ['app.js','index.html','server.py']},'identity':'UNKNOWN'})
        browser.close()

if __name__=='__main__':main()

"""Cached-geometry/source partition and real-browser checks; no original-byte claim."""
import argparse
import json
import threading
from pathlib import Path
from http.server import ThreadingHTTPServer
import numpy as np
from scipy.spatial import cKDTree
from playwright.sync_api import sync_playwright
from actions import HERE, OUT, read, dump
from core import roi_mask
from research_scene_change import domain
from scene_geometry_ledger import GeometryLedger
from server import Handler


def main(evidence):
    evidence.mkdir(parents=True,exist_ok=False)
    output=HERE/'action_research_scene_static';summary=read(output/'SUMMARY.json')
    cfg=summary['configuration']['frozen_r1'];cat=read(OUT/'catalog.json');prior=Path(cfg['background_experiment'])
    cache=GeometryLedger(HERE/'action_research_retention/baseline_02')
    bg=cKDTree(np.load(prior/'background.npz')['xyz']);tau=cat['background']['tolerance_m'];checks=[]
    for rec in cat['sessions']:
        sid=rec['session_id']
        for fi in rec['available_frames']:
            q,nominal,base=cache.frame(sid,fi);r=read(output/sid/f'{fi:04d}.json')
            assert r['input_provenance']['ledger_sha256']==cache.hashes[str(cache.folder/sid/f'{fi:04d}.npz')]
            p=nominal@np.array(r['vibration']['R']).T+r['vibration']['t'];valid=domain(q,p,cfg)
            fg=set(r['scene_change']['new_source_indices']);matched=set(r['scene_change']['matched_source_indices'])
            assert fg.isdisjoint(matched) and fg|matched==set(np.flatnonzero(valid).tolist())
            active=np.flatnonzero(valid);known=active[bg.query(nominal[active])[0]<=tau]
            assert set(known.tolist())<=matched
            proposals=r['scene_clusters'];ids=[i for row in proposals for i in row['source_indices']]
            assert len(ids)==len(set(ids)) and set(ids)<=fg
            assert set(ids)|set(r['scene_change']['noise_or_small_cluster_source_indices'])==fg
            assert set(r['selection']['selected_source_indices'])<=set(ids)
            for row in proposals+r['body_3d']:
                np.testing.assert_allclose(row['points'],p[row['display_source_indices']],atol=.000051,rtol=0)
                for n in row['skeleton']['nodes'].values():assert set(n['support_source_indices'])<=set(row['source_indices'])
                if row in proposals and not row['selected_target_candidate']:
                    assert all(not n['valid'] for n in row['skeleton']['nodes'].values())
            anchor_valid=domain(q,nominal,cfg)&~roi_mask(nominal,cfg['roi_xy'])
            assert int(anchor_valid.sum())==r['vibration']['anchor_input_count'] and r['vibration']['anchors_inside_roi']==0
            checks.append({'sid':sid,'fi':fi,'target':len(r['selection']['selected_source_indices']),
                'proposals':len(proposals),'fg':len(fg),'geometry_only':True})
        print('CHECKED',sid,len(rec['available_frames']),flush=True)
    assert len(checks)==1966
    dump(evidence/'GEOMETRY_CHECK.json',{'status':'PASS','frames':checks,'original_byte_check':'BLOCKED_MISSING_INPUT',
        'original_byte_verification_pass':False,'known_background_promoted':0,'anchor_inputs_inside_roi':0,
        'human_identity_accuracy':None,'full_fov_proposals_are_not_person_count':True})
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler);threading.Thread(target=server.serve_forever,daemon=True).start()
    errors=[];visits=[]
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(channel='msedge');page=browser.new_page(viewport={'width':1600,'height':1200})
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.goto('http://127.0.0.1:%d/?dataset=actions&variant=scene_static&fi=0'%server.server_port)
            page.wait_for_function("record?.variant==='scene_static' && obj !== null")
            page.locator('#bgScene').check()
            page.screenshot(path=str(evidence/'PROTECTED_ANCHORS_SCENE.png'),full_page=True)
            page.locator('#mode').select_option('full_3d')
            page.wait_for_function("document.getElementById('object').options.length===record.scene_clusters.length")
            count=page.evaluate('record.scene_clusters.length');assert count>0
            for option in page.locator('#object option').all():
                page.locator('#object').select_option(option.get_attribute('value'))
                assert page.evaluate('obj.semantic_identity')=='UNKNOWN'
            page.screenshot(path=str(evidence/'ALL_NEW_3D_CLUSTERS.png'),full_page=True)
            page.locator('#mode').select_option('body_3d')
            index=page.evaluate('obj.display_source_indices[0]')
            page.evaluate('(i)=>showSource(i)',arg=index)
            page.wait_for_function("document.getElementById('sourceLedger').textContent.includes('CACHED_XYZ_ONLY')")
            source=json.loads(page.locator('#sourceLedger').text_content())
            assert not source['original_bytes_available'] and source['opaque_hex_12_27'] is None
            assert source['new_point'] and source['target']
            for button in page.locator('#sessions button').all():
                sid=button.get_attribute('data-sid');button.click()
                page.wait_for_function("sid=>record?.session_id===sid&&record?.variant==='scene_static'",arg=sid)
                visits.append(page.evaluate('({sid:record.session_id,fi,clusters:record.scene_clusters.length,target:obj?.point_count??0})'))
            page.locator('#sessions button[data-sid="cap_20261013_082829"]').click()
            page.wait_for_function("record?.session_id==='cap_20261013_082829'")
            page.locator('#time').fill('30');page.locator('#time').dispatch_event('input')
            page.wait_for_function("record?.frame_index===30&&record?.variant==='scene_static'")
            page.screenshot(path=str(evidence/'SUPINE_WITH_FROZEN_CONTEXT.png'),full_page=True)
            page.locator('#variant').select_option('scene_change')
            page.wait_for_function("record?.variant==='scene_change'")
            assert page.locator('#bgSceneLabel').is_hidden()
            page.locator('#variant').select_option('baseline')
            page.wait_for_function('experiment===null && record !== null')
            assert page.locator('#mode').input_value()=='body_3d'
            assert not errors,errors
            dump(evidence/'BROWSER_CHECK.json',{'status':'PASS','errors':errors,'visits':visits,
                'all_clusters_and_frozen_context':True,'source_missing_marker':True,'legacy_variants_preserved':True})
            browser.close()
    finally:server.shutdown();server.server_close()


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,required=True)
    main(parser.parse_args().out)

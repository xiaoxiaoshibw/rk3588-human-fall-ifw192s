"""Verify source membership and the actual same-page scene-change controls."""
import argparse
import json
import sys
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
import numpy as np
from playwright.sync_api import sync_playwright
from actions import HERE, OUT, load, read, dump
from core import R, T
from research_actions import frame_points
from research_scene_change import domain
from scipy.spatial import cKDTree
from server import Handler


def main(evidence):
    evidence.mkdir(parents=True, exist_ok=False)
    output = HERE/'action_research_scenechange_guarded'; summary = read(output/'SUMMARY.json')
    cfg = summary['configuration']['frozen_r1']; prior = Path(cfg['background_experiment'])
    cat = read(OUT/'catalog.json'); frame_count = 0; records = []
    background = cKDTree(np.load(prior/'background.npz')['xyz'])
    for rec in cat['sessions']:
        sid = rec['session_id']; meta, raw, hashes = load(sid)
        assert hashes == summary['input_sha256'][sid]
        reg = None if sid == cat['background']['session'] else read(prior/(sid+'_registration.json'))
        for fi in rec['available_frames']:
            row = read(output/sid/f'{fi:04d}.json')
            ids = row['selection']['selected_source_indices']; new = row['scene_change']['new_source_indices']
            matched = row['scene_change']['matched_source_indices']
            assert len(set(new)) == len(new) and len(set(matched)) == len(matched)
            assert set(ids) <= set(new) and not set(new) & set(matched)
            assert all(0 <= i < meta['frames'][fi]['count_points'] for i in new+matched)
            q, p = frame_points(raw, meta['frames'][fi], reg)
            nominal = p.copy()
            p = p @ np.array(row['vibration']['R']).T + row['vibration']['t']
            valid = domain(q, p, cfg); active = np.flatnonzero(valid)
            known = active[background.query(nominal[active])[0] <= cat['background']['tolerance_m']]
            assert set(known) <= set(matched), 'Pose compensation promoted known background'
            for obj in row['body_3d']:
                assert obj['source_indices'] == ids and obj['point_count'] == len(ids)
                displayed = obj['display_source_indices']
                np.testing.assert_allclose(obj['points'], p[displayed], atol=.000051, rtol=0)
                for node in obj['skeleton']['nodes'].values():
                    assert set(node['support_source_indices']) <= set(ids)
            frame_count += 1
        group = [r for r in summary['frames'] if r['sid'] == sid]
        records.append({'sid':sid, 'frames':len(group), 'target_frames':sum(r['target']>0 for r in group),
            'baseline_target_frames':sum(r['baseline_target']>0 for r in group),
            'foreground_points':sum(r['fg'] for r in group), 'baseline_foreground_points':sum(r['baseline_fg'] for r in group),
            'surface_extra_removed':sum(r['surface_extra_removed'] for r in group),
            'target_points':sum(r['target'] for r in group), 'baseline_target_points':sum(r['baseline_target'] for r in group)})
    assert frame_count == 1966
    dump(evidence/'SOURCE_CHECK.json', {'frames':frame_count,'status':'PASS', 'sessions':records,
        'known_background_promoted_to_new_points':0,
        'human_precision':None,'furniture_contamination':None,'no_semantic_gt_fabricated':True})
    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    errors = []; visits = []
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(channel='msedge')
            page = browser.new_page(viewport={'width':1500,'height':1100})
            page.on('pageerror', lambda e: errors.append(str(e)))
            page.goto('http://127.0.0.1:%d/' % server.server_port)
            page.wait_for_function('record !== null && obj !== null')
            assert page.locator('#variant').input_value() == 'baseline'
            page.locator('#variant').select_option('scene_change')
            page.wait_for_function("experiment?.variant==='scene_change' && record?.vibration !== undefined")
            page.screenshot(path=str(evidence/'SCENE_CHANGE_STANDING.png'),full_page=True)
            for button in page.locator('#sessions button').all():
                sid = button.get_attribute('data-sid'); button.click()
                page.wait_for_function('(sid)=>record?.session_id===sid && experiment?.variant==="scene_change"',arg=sid)
                visits.append(page.evaluate('({sid:record.session_id,fi,target:obj?.point_count??0,vibration:record.vibration.status})'))
            page.locator('#sessions button[data-sid="cap_20261013_082829"]').click()
            page.wait_for_function("record?.session_id==='cap_20261013_082829'")
            page.locator('#time').fill('30');page.locator('#time').dispatch_event('input')
            page.wait_for_function('fi===30 && record?.frame_index===30 && experiment?.frame_index===30')
            page.screenshot(path=str(evidence/'SCENE_CHANGE_SUPINE.png'),full_page=True)
            if page.evaluate('obj !== null'):
                index = page.evaluate('obj.display_source_indices[0]')
                page.evaluate('(index)=>showSource(index)',arg=index)
                page.wait_for_function("document.getElementById('sourceLedger').textContent.includes('new_point')")
                source = json.loads(page.locator('#sourceLedger').text_content())
                assert source['local_index'] == index and source['target'] and source['new_point'] and not source['background_match']
            page.locator('#next').click()
            page.wait_for_function('fi===31 && record?.frame_index===31 && experiment?.frame_index===31')
            page.locator('#variant').select_option('baseline')
            page.wait_for_function('experiment===null && record !== null')
            assert not errors, errors
            dump(evidence/'BROWSER_CHECK.json', {'status':'PASS','visits':visits,'errors':errors,
                 'variant_switch_and_seek':True,'source_row_readback':True,'old_default_preserved':True})
            browser.close()
    finally:
        server.shutdown();server.server_close()


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,required=True)
    main(parser.parse_args().out)

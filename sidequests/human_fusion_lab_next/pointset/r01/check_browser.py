"""Actual browser checks without writing invented human labels."""
import json
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
E = HERE.parents[3]/'docs/human_capture/evidence/2026-10-13_hfus_pointset_01_r1'
with sync_playwright() as p:
    browser = p.chromium.launch(channel='msedge')
    page = browser.new_page(viewport={'width': 1400, 'height': 1050})
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto('http://127.0.0.1:8941/')
    page.wait_for_function("record !== null && obj !== null")
    assert page.locator('#sessions button').count() == 9
    assert page.locator('#mode').input_value() == 'roi_3d'
    assert 'PointNet' in page.locator('#metrics').inner_text()
    first = page.evaluate('fi')
    page.locator('#next').click()
    page.wait_for_function('record.frame_index === 1')
    page.locator('#mode').select_option('full_3d')
    page.locator('#model').select_option('pointnet_prob')
    page.locator('#front').click()
    page.locator('#top').click()
    page.locator('#orbit').click()
    page.locator('#play').click()
    page.wait_for_function('fi >= 3')
    page.locator('#play').click()
    page.locator('#mode').select_option('reference')
    assert page.evaluate("obj.kind") == 'EXISTING_MANUAL_REFERENCE'
    page.locator('#annotate').check()
    point = page.evaluate('projected.find(p=>p.q[0]>50&&p.q[0]<canvas.width-50&&p.q[1]>50&&p.q[1]<450).q')
    page.locator('#cloud').click(position={'x': point[0], 'y': point[1]})
    assert page.evaluate('selected.size') > 0
    page.locator('#save').click()
    assert '审核人' in page.locator('#message').inner_text()
    # Check validation failure instead of manufacturing reviewed human labels.
    r = page.request.post('http://127.0.0.1:8941/api/parts', data={'schema_version': 'wrong'})
    assert r.status == 400
    statuses = []
    for i in range(9):
        page.locator('#sessions button').nth(i).click()
        page.wait_for_function(f"current.session_id === catalog.sessions[{i}].session_id && record.session_id === current.session_id && record.frame_index === 0")
        page.locator('#mode').select_option('full_3d')
        statuses.append(page.locator('#status').inner_text())
    page.locator('#mode').select_option('reference')
    assert page.evaluate('obj===null'), 'S9 must not forge valid manual references'
    page.locator('#sessions button').nth(1).click()
    page.wait_for_function("record.session_id==='cap_20261010_175429' && obj!==null")
    page.screenshot(path=str(E/'REFERENCE_PREVIEW.png'), full_page=True)
    page.locator('#mode').select_option('full_3d')
    page.screenshot(path=str(E/'AUTOMATIC_PREVIEW.png'), full_page=True)
    assert not errors, errors
    (E/'BROWSER_CHECK.json').write_text(json.dumps({'passed': True, 'errors': errors, 'sessions': statuses,
                                                  'checks': ['9-session switch', 'frame step', 'playback', '3D/XY/reference modes', 'model switch', 'views', 'part point selection', 'missing reviewer rejected', 'bad annotation binding 400', 'S9 reference UNKNOWN'],
                                                  'human_labels_written_by_test': False}, ensure_ascii=False, indent=2), encoding='utf-8')
    browser.close()
print('Nine-session browser checks passed')
